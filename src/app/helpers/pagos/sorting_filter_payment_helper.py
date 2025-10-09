from __future__ import annotations
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union
import re
import flet as ft

NumericType = Union[int, float]


class PaymentSortFilterHelper:
    """
    Helper genérico para filtrar y ordenar tablas de pagos (ft.DataTable) y
    para priorizar listas de registros (diccionarios) usadas en paneles expansibles.

    Novedades:
    • prioritize_by_prefix(): prioriza filas en DataTable por prefijo (no excluye).
    • prioritize_records_by_filters(): prioriza listas de dicts por id_empleado / id_pago (no excluye),
      ideal para tu contenedor expansible.
    • Métodos existentes se mantienen sin cambios de firma.
    """

    def __init__(self):
        # id(datatable) -> snapshot completo de filas (sin filtros aplicados)
        self._snapshots: Dict[int, List[ft.DataRow]] = {}
        # id(datatable) -> estado de filtro actual (set de ids o None)
        self._active_filters: Dict[int, Optional[set[int]]] = {}

    # ------------------------------------------------------------------
    # Binding de sorters (genérico)
    # ------------------------------------------------------------------
    def bind_sorting(
        self,
        datatable: ft.DataTable,
        sort_specs: Sequence[Tuple[int, str]],
        on_after_sort: Optional[Callable[[ft.DataTable], None]] = None,
    ) -> None:
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
                    ascending = e.ascending
                    self.sort_table(datatable, column_index=index, value_type=t, ascending=ascending)
                    if on_after_sort:
                        on_after_sort(datatable)
                return _on_sort

            col.on_sort = _make_on_sort()

        datatable.update()

    # Atajos estándar
    def bind_standard_sorters_to_pendientes(
        self,
        datatable: ft.DataTable,
        on_after_sort: Optional[Callable[[ft.DataTable], None]] = None,
    ) -> None:
        """Pendientes (COLUMNS_EDICION): id_pago=0, monto_base=6, total=12."""
        self.bind_sorting(
            datatable,
            sort_specs=[(0, "int"), (6, "money"), (12, "money")],
            on_after_sort=on_after_sort,
        )

    def bind_standard_sorters_to_confirmado(
        self,
        datatable: ft.DataTable,
        on_after_sort: Optional[Callable[[ft.DataTable], None]] = None,
    ) -> None:
        """Confirmados (COLUMNS_COMPACTAS_CONFIRMADO): id_pago=0, monto_base=3, total=9."""
        self.bind_sorting(
            datatable,
            sort_specs=[(0, "int"), (3, "money"), (9, "money")],
            on_after_sort=on_after_sort,
        )

    # ------------------------------------------------------------------
    # Ordenar una tabla
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
    # NUEVO: Priorizar (no excluir) en DataTable por prefijo de texto
    # ------------------------------------------------------------------
    def prioritize_by_prefix(
        self,
        datatable: ft.DataTable,
        *,
        column_index: int,
        prefix: str,
    ) -> None:
        """
        Reordena filas de 'datatable' poniendo primero las que cumplan
        str(celda).startswith(prefix). No elimina filas.
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
    def _ensure_snapshot(self, datatable: ft.DataTable) -> None:
        tid = id(datatable)
        if tid not in self._snapshots:
            self._snapshots[tid] = list(datatable.rows or [])

    @staticmethod
    def _money_to_float(s: Union[str, float, int]) -> float:
        if isinstance(s, (int, float)):
            return float(s)
        if not s:
            return 0.0
        txt = re.sub(r"[^\d\.\-]", "", str(s))
        if txt in ("", "-", ".", "-.", ".-"):
            return 0.0
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
                return int(self._money_to_float(raw))
            except Exception:
                return 0
        if value_type in {"money", "float"}:
            return self._money_to_float(raw)
        return self._text_value(raw)

    # ------------------------------------------------------------------
    # Extras convenientes
    # ------------------------------------------------------------------
    def apply_filter_and_sort(
        self,
        datatable: ft.DataTable,
        *,
        employee_col_index: Optional[int] = None,
        employee_ids: Optional[Iterable[int]] = None,
        sort_by: Optional[Tuple[int, str, bool]] = None,
    ) -> None:
        if employee_col_index is not None and employee_ids is not None:
            self.filter_by_employee_ids(datatable, employee_col_index=employee_col_index, employee_ids=employee_ids)
        else:
            self._ensure_snapshot(datatable)

        if sort_by is not None:
            col_idx, val_type, asc = sort_by
            self.sort_table(datatable, column_index=col_idx, value_type=val_type, ascending=asc)

    # ------------------------------------------------------------------
    # ------------- Integración con grupos (expansibles) ---------------
    # ------------------------------------------------------------------
    @staticmethod
    def prioritize_records_by_filters(
        items: List[Dict[str, Any]],
        *,
        emp_field: str = "numero_nomina",
        id_pago_fields: Tuple[str, str] = ("id_pago_nomina", "id_pago"),
        id_empleado_prefix: str = "",
        id_pago_prefix: str = "",
    ) -> List[Dict[str, Any]]:
        """
        PRIORIZA (no excluye) registros tipo dict, poniendo primero los que coinciden
        con los prefijos dados. Útil al construir cada panel del contenedor expansible.

        Ejemplo de uso en tu contenedor:
            items = PaymentSortFilterHelper.prioritize_records_by_filters(
                items, id_empleado_prefix=filtros.get("id_empleado",""), id_pago_prefix=filtros.get("id_pago","")
            )
        """
        emp_pref = (id_empleado_prefix or "").strip()
        pago_pref = (id_pago_prefix or "").strip()

        def matches(row: Dict[str, Any]) -> bool:
            ok = True
            if emp_pref:
                ok = ok and str(row.get(emp_field, "")).startswith(emp_pref)
            if pago_pref:
                v = str(row.get(id_pago_fields[0]) or row.get(id_pago_fields[1]) or "")
                ok = ok and v.startswith(pago_pref)
            return ok

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
