from __future__ import annotations
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union, Literal
import re
import flet as ft

NumericType = Union[int, float]


class PaymentSortFilterHelper:
    """
    Helper para filtrar/ordenar DataTables y priorizar/ordenar listas de dicts.

    Incluye:
    • refresh_snapshot(): resetea snapshot de la DataTable (evita snapshots viejos).
    • sort_table(), sort_rows_inplace(): orden para DataTable y listas de filas.
    • bind_sorting(): vincula ordenamiento por columna (con atajos estándar).
    • prioritize_or_filter_table_by_columns(): prioriza o filtra en DataTable
      por prefijos de id_empleado / id_pago (pendientes y pagadas).
    • sort_records(), prioritize_records_by_filters(): para listas de dicts (expansibles).
    • parse_id_query(): soporta patrones "1,2,5-9" para filtros de IDs.
    """

    def __init__(self):
        # id(datatable) -> snapshot completo de filas (estado base sin filtros)
        self._snapshots: Dict[int, List[ft.DataRow]] = {}
        # id(datatable) -> estado de filtro activo (si decides usar set(ids))
        self._active_filters: Dict[int, Optional[set[int]]] = {}

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------
    def _ensure_snapshot(self, datatable: ft.DataTable) -> None:
        tid = id(datatable)
        if tid not in self._snapshots:
            self._snapshots[tid] = list(datatable.rows or [])

    def refresh_snapshot(self, datatable: ft.DataTable) -> None:
        """Reemplaza el snapshot con el estado actual de la tabla."""
        self._snapshots[id(datatable)] = list(datatable.rows or [])

    # ------------------------------------------------------------------
    # Binding de sorters (genérico)
    # ------------------------------------------------------------------
    def bind_sorting(
        self,
        datatable: ft.DataTable,
        sort_specs: Sequence[Tuple[int, str]],
        on_after_sort: Optional[Callable[[ft.DataTable], None]] = None,
    ) -> None:
        """
        Vincula callbacks de sort por columna.
        sort_specs: lista de (indice_columna, tipo_valor: "int"|"money"|"float"|"text")
        """
        self._ensure_snapshot(datatable)
        if not datatable.columns:
            return

        spec_map = {idx: tp for idx, tp in sort_specs}

        for i, col in enumerate(datatable.columns):
            if i not in spec_map:
                continue
            tp = spec_map[i]

            def _make_on_sort(index=i, t=tp):
                def _on_sort(e: ft.DataColumnSortEvent):
                    ascending = getattr(e, "ascending", True)
                    self.sort_table(datatable, column_index=index, value_type=t, ascending=ascending)
                    if on_after_sort:
                        on_after_sort(datatable)
                return _on_sort

            try:
                col.on_sort = _make_on_sort()  # type: ignore[attr-defined]
            except Exception:
                # versiones antiguas podrían no soportarlo; ignorar
                pass

        datatable.update()

    # Atajos (ajusta índices según tus tablas)
    def bind_standard_sorters_to_pendientes(
        self,
        datatable: ft.DataTable,
        on_after_sort: Optional[Callable[[ft.DataTable], None]] = None,
        *,
        id_pago_idx: int = 0,
        monto_base_idx: int = 5,
        total_idx: int = 11,
    ) -> None:
        """
        Pendientes: índices por defecto tentativos -> ajusta a tu tabla.
        """
        self.bind_sorting(
            datatable,
            sort_specs=[(id_pago_idx, "int"), (monto_base_idx, "money"), (total_idx, "money")],
            on_after_sort=on_after_sort,
        )

    def bind_standard_sorters_to_confirmado(
        self,
        datatable: ft.DataTable,
        on_after_sort: Optional[Callable[[ft.DataTable], None]] = None,
        *,
        id_pago_idx: int = 0,   # "id_pago"
        monto_base_idx: int = 5,  # "monto_base"
        total_idx: int = 11,      # "total"
    ) -> None:
        """
        Confirmados (expansibles): coincide con COLUMNS del módulo expansible:
        ["id_pago"(0), "id_empleado"(1), "nombre"(2), "horas"(3), "sueldo_hora"(4),
         "monto_base"(5), "descuentos"(6), "prestamos"(7), "deposito"(8),
         "saldo"(9), "efectivo"(10), "total"(11), ...]
        """
        self.bind_sorting(
            datatable,
            sort_specs=[(id_pago_idx, "int"), (monto_base_idx, "money"), (total_idx, "money")],
            on_after_sort=on_after_sort,
        )

    # ------------------------------------------------------------------
    # Ordenar una DataTable
    # ------------------------------------------------------------------
    def sort_table(
        self,
        datatable: ft.DataTable,
        *,
        column_index: int,
        value_type: str = "text",
        ascending: bool = True,
    ) -> None:
        if not datatable.rows:
            return

        def key_fn(row: ft.DataRow) -> Union[str, NumericType]:
            return self._cell_value_as(row, column_index, value_type)

        datatable.rows = sorted(datatable.rows, key=key_fn, reverse=not ascending)
        datatable.sort_column_index = column_index
        datatable.sort_ascending = ascending
        datatable.update()

    # ------------------------------------------------------------------
    # Filtros/priorizaciones en DataTable (pendientes / pagadas)
    # ------------------------------------------------------------------
    def prioritize_or_filter_table_by_columns(
        self,
        datatable: ft.DataTable,
        *,
        id_empleado_col: int,
        id_pago_col: int,
        id_empleado_prefix: str = "",
        id_pago_prefix: str = "",
        match_mode: Literal["or", "and"] = "or",
        mode: Literal["prioritize", "filter"] = "prioritize",
    ) -> None:
        """
        Reordena (prioritize) o reduce (filter) filas de una DataTable en base a prefijos.

        - id_empleado_col: índice de columna con el ID de empleado.
        - id_pago_col: índice de columna con el ID de pago.
        - match_mode: "or" (default) ó "and" para combinar prefijos.
        - mode: "prioritize" (pone matching arriba) o "filter" (deja sólo matching).
        """
        self._ensure_snapshot(datatable)
        base_rows = list(self._snapshots[id(datatable)])

        emp_pref = self._norm_digits_prefix(id_empleado_prefix)
        pago_pref = self._norm_digits_prefix(id_pago_prefix)

        if not emp_pref and not pago_pref:
            datatable.rows = base_rows
            datatable.update()
            return

        def row_matches(r: ft.DataRow) -> bool:
            emp_val = str(self._cell_value_as(r, id_empleado_col, "int"))
            pago_val = str(self._cell_value_as(r, id_pago_col, "int"))
            emp_ok = emp_val.startswith(emp_pref) if emp_pref else False
            pago_ok = pago_val.startswith(pago_pref) if pago_pref else False
            return (emp_ok or pago_ok) if match_mode == "or" else (emp_ok and pago_ok)

        matching: List[ft.DataRow] = []
        non_matching: List[ft.DataRow] = []
        for r in base_rows:
            (matching if row_matches(r) else non_matching).append(r)

        if mode == "filter":
            datatable.rows = matching
        else:
            datatable.rows = matching + non_matching
        datatable.update()

    # Wrappers de conveniencia con índices por defecto (ajústalos si difieren)
    def apply_standard_filters_to_pendientes_table(
        self,
        datatable: ft.DataTable,
        *,
        id_empleado_prefix: str = "",
        id_pago_prefix: str = "",
        match_mode: Literal["or", "and"] = "or",
        mode: Literal["prioritize", "filter"] = "prioritize",
        id_empleado_idx: int = 1,  # suele ser 1: ["id_pago", "id_empleado", ...]
        id_pago_idx: int = 0,
    ) -> None:
        self.prioritize_or_filter_table_by_columns(
            datatable,
            id_empleado_col=id_empleado_idx,
            id_pago_col=id_pago_idx,
            id_empleado_prefix=id_empleado_prefix,
            id_pago_prefix=id_pago_prefix,
            match_mode=match_mode,
            mode=mode,
        )

    def apply_standard_filters_to_confirmado_table(
        self,
        datatable: ft.DataTable,
        *,
        id_empleado_prefix: str = "",
        id_pago_prefix: str = "",
        match_mode: Literal["or", "and"] = "or",
        mode: Literal["prioritize", "filter"] = "prioritize",
        id_empleado_idx: int = 1,  # según COLUMNS del expansible
        id_pago_idx: int = 0,      # según COLUMNS del expansible
    ) -> None:
        self.prioritize_or_filter_table_by_columns(
            datatable,
            id_empleado_col=id_empleado_idx,
            id_pago_col=id_pago_idx,
            id_empleado_prefix=id_empleado_prefix,
            id_pago_prefix=id_pago_prefix,
            match_mode=match_mode,
            mode=mode,
        )

    # ------------------------------------------------------------------
    # Filtro duro por Id de empleado (EXCLUYE filas)
    # ------------------------------------------------------------------
    def filter_by_employee_ids(
        self,
        datatable: ft.DataTable,
        *,
        employee_col_index: int,
        employee_ids: Iterable[int],
    ) -> None:
        self._ensure_snapshot(datatable)
        ids = set(int(x) for x in employee_ids)
        tid = id(datatable)
        self._active_filters[tid] = ids
        base_rows = self._snapshots[tid]
        filtered: List[ft.DataRow] = []

        for r in base_rows:
            try:
                val = self._cell_value_as(r, employee_col_index, "int")
                if int(val) in ids:
                    filtered.append(r)
            except Exception:
                continue

        datatable.rows = filtered
        datatable.update()

    def clear_filter(self, datatable: ft.DataTable) -> None:
        tid = id(datatable)
        if tid in self._snapshots:
            datatable.rows = list(self._snapshots[tid])
            self._active_filters[tid] = None
            datatable.update()

    # ------------------------------------------------------------------
    # Priorizar (no excluir) por prefijo de texto en UNA columna
    # ------------------------------------------------------------------
    def prioritize_by_prefix(
        self,
        datatable: ft.DataTable,
        *,
        column_index: int,
        prefix: str,
    ) -> None:
        """
        Reordena filas poniendo primero las que cumplen str(celda).startswith(prefix).
        Si prefix está vacío, restaura snapshot.
        """
        self._ensure_snapshot(datatable)
        base_rows = list(self._snapshots[id(datatable)])

        prefix = (prefix or "").strip()
        if not prefix:
            datatable.rows = base_rows
            datatable.update()
            return

        matching: List[ft.DataRow] = []
        non_matching: List[ft.DataRow] = []

        for r in base_rows:
            txt = self._text_value(self._get_cell_content(r, column_index))
            if txt.startswith(prefix):
                matching.append(r)
            else:
                non_matching.append(r)

        datatable.rows = matching + non_matching
        datatable.update()

    # ------------------------------------------------------------------
    # Utilidades públicas
    # ------------------------------------------------------------------
    @staticmethod
    def parse_id_query(query: str) -> List[int]:
        """
        Convierte '1,2,5-8' -> [1,2,5,6,7,8]
        """
        if not query:
            return []
        ids: List[int] = []
        parts = [p.strip() for p in str(query).split(",") if p.strip()]
        for p in parts:
            if "-" in p:
                a, b = p.split("-", 1)
                try:
                    x, y = int(a.strip()), int(b.strip())
                    ids.extend(range(min(x, y), max(x, y) + 1))
                except Exception:
                    continue
            else:
                try:
                    ids.append(int(p))
                except Exception:
                    continue
        return sorted(set(ids))

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------
    @staticmethod
    def _norm_digits_prefix(s: str) -> str:
        s = (s or "").strip()
        return "".join(ch for ch in s if ch.isdigit())

    @staticmethod
    def _money_to_float(s: Union[str, float, int]) -> float:
        """
        Soporta:
        - "$1,234.56"  -> 1234.56
        - "1.234,56"   -> 1234.56
        - "1 234,56"   -> 1234.56
        - "1234"       -> 1234.0
        """
        if isinstance(s, (int, float)):
            return float(s)
        if not s:
            return 0.0

        txt = str(s).strip()
        txt = re.sub(r"[^\d,.\-]", "", txt)

        has_comma = "," in txt
        has_dot = "." in txt
        if has_comma and has_dot:
            if txt.rfind(",") > txt.rfind("."):
                txt = txt.replace(".", "")
                txt = txt.replace(",", ".")
                try:
                    return float(txt)
                except Exception:
                    return 0.0
            else:
                txt = txt.replace(",", "")
                try:
                    return float(txt)
                except Exception:
                    return 0.0
        elif has_comma and not has_dot:
            parts = txt.split(",")
            if len(parts) == 2 and len(parts[1]) in (2, 3):
                txt = txt.replace(",", ".")
                try:
                    return float(txt)
                except Exception:
                    return 0.0
            txt = txt.replace(",", "")
            try:
                return float(txt)
            except Exception:
                return 0.0
        else:
            txt = txt.replace(",", "")
            try:
                return float(txt)
            except Exception:
                return 0.0

    @staticmethod
    def _text_value(x: Any) -> str:
        try:
            return str(getattr(x, "value", x))
        except Exception:
            return str(x)

    @staticmethod
    def _get_cell_content(row: ft.DataRow, index: int) -> Any:
        try:
            cell = row.cells[index]
            return getattr(cell.content, "value", cell.content)
        except Exception:
            return ""

    def _cell_value_as(self, row: ft.DataRow, index: int, value_type: str) -> Union[str, NumericType]:
        raw = self._get_cell_content(row, index)

        if value_type == "int":
            try:
                return int(round(self._money_to_float(raw)))
            except Exception:
                return 0
        if value_type in {"money", "float"}:
            return self._money_to_float(raw)
        return self._text_value(raw)

    # ------------------------------------------------------------------
    # ------------- Integración con listas (expansibles) ----------------
    # ------------------------------------------------------------------
    def sort_records(
        self,
        items: List[Dict[str, Any]],
        *,
        key: str,
        asc: bool = True,
        compute_total: Optional[Callable[[Dict[str, Any]], float]] = None,
        emp_field: str = "numero_nomina",
        id_pago_fields: Tuple[str, str] = ("id_pago_nomina", "id_pago"),
    ) -> List[Dict[str, Any]]:
        """
        Ordena listas de dicts por clave conocida. Para 'total' puede usarse
        compute_total(row) que devuelva el total visible recalculado.
        """
        def k(row: Dict[str, Any]):
            if key == "id_pago":
                return int(row.get(id_pago_fields[0]) or row.get(id_pago_fields[1]) or 0)
            if key == "id_empleado":
                return int(row.get(emp_field) or 0)
            if key == "monto_base":
                return float(row.get("monto_base") or 0.0)
            if key == "total":
                if compute_total:
                    return float(compute_total(row))
                return float(row.get("monto_base") or 0.0)
            return 0

        return sorted(items, key=k, reverse=not asc)

    @staticmethod
    def prioritize_records_by_filters(
        items: List[Dict[str, Any]],
        *,
        emp_field: str = "numero_nomina",
        id_pago_fields: Tuple[str, str] = ("id_pago_nomina", "id_pago"),
        id_empleado_prefix: str = "",
        id_pago_prefix: str = "",
        match_mode: Literal["or", "and"] = "or",
    ) -> List[Dict[str, Any]]:
        """
        PRIORIZA (no excluye) registros dict poniendo primero los que coinciden
        con los prefijos dados. match_mode controla la lógica: "or" (default) o "and".
        """
        emp_pref = (id_empleado_prefix or "").strip()
        pago_pref = (id_pago_prefix or "").strip()

        def matches(row: Dict[str, Any]) -> bool:
            emp_ok = str(row.get(emp_field, "")).startswith(emp_pref) if emp_pref else False
            pago_val = str(row.get(id_pago_fields[0]) or row.get(id_pago_fields[1]) or "")
            pago_ok = pago_val.startswith(pago_pref) if pago_pref else False
            if not emp_pref and not pago_pref:
                return False
            return (emp_ok or pago_ok) if match_mode == "or" else (emp_ok and pago_ok)

        matching = [r for r in items if matches(r)]
        non_matching = [r for r in items if not matches(r)]
        return matching + non_matching

    # ------------------------------------------------------------------
    # Ordenar filas sueltas (fuera del DataTable)
    # ------------------------------------------------------------------
    def sort_rows_inplace(
        self,
        rows: List[ft.DataRow],
        *,
        column_index: int,
        value_type: str,
        ascending: bool = True,
    ) -> List[ft.DataRow]:
        def key_fn(r: ft.DataRow):
            return self._cell_value_as(r, column_index, value_type)
        return sorted(rows, key=key_fn, reverse=not ascending)
