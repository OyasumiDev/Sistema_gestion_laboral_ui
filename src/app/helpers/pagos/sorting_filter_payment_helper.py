from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union, Literal
import re
import math
import flet as ft

NumericType = Union[int, float]


class PaymentSortFilterHelper:
    """
    Helper robusto para:
      - Ordenar DataTables (sin crashear por variaciones de Flet en eventos on_sort).
      - Priorizar/filtrar filas por prefijos (id_empleado / id_pago).
      - Ordenar/priorizar listas de dicts (útil en vistas expansibles).

    Objetivo de diseño:
      - NO tocar DB.
      - NO depender de que Flet siempre entregue e.ascending.
      - Soportar celdas con ft.Text, ft.TextField, y wrappers (Container con content).
      - Evitar crashes si la tabla/control aún no está montado (safe_update).

    ✅ Recomendación de uso (muy importante para evitar crashes):
      - Elige UNA estrategia:
        A) Sorting "por datos" (recomendado):
           - Tu PaymentTableBuilder llama on_sort(key, asc) -> tú ordenas en tu lista (PagosRepo/helper)
             y RECONSTRUYES filas/tabla.
           - En este caso NO uses bind_sorting() en la misma tabla.
        B) Sorting "en tabla" (manual):
           - Usas bind_sorting() y este helper reordena datatable.rows.
           - En este caso en PaymentTableBuilder pasa on_sort=None (o sortable_cols vacío).

      - Si reconstruyes datatable.rows desde cero (nuevo listado), llama refresh_snapshot(datatable).
    """

    def __init__(self):
        # id(datatable) -> snapshot de filas base (sin filtros/priorización)
        self._snapshots: Dict[int, List[ft.DataRow]] = {}
        # id(datatable) -> filtro activo por ids (si usas filter_by_employee_ids)
        self._active_filters: Dict[int, Optional[set[int]]] = {}
        # id(datatable) -> (last_col_index, last_ascending) para toggle cuando Flet no da e.ascending
        self._sort_state: Dict[int, Tuple[int, bool]] = {}

    # ------------------------------------------------------------------
    # Safe update
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_update(ctrl: Optional[ft.Control]) -> None:
        try:
            if ctrl is not None and getattr(ctrl, "page", None) is not None:
                ctrl.update()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------
    def _ensure_snapshot(self, datatable: ft.DataTable) -> None:
        tid = id(datatable)
        if tid not in self._snapshots:
            self._snapshots[tid] = list(datatable.rows or [])

    def refresh_snapshot(self, datatable: ft.DataTable) -> None:
        """Reemplaza snapshot con el estado actual de la tabla."""
        self._snapshots[id(datatable)] = list(datatable.rows or [])

    # ------------------------------------------------------------------
    # Binding de sorting (manual sobre datatable.rows)
    # ------------------------------------------------------------------
    def bind_sorting(
        self,
        datatable: ft.DataTable,
        sort_specs: Sequence[Tuple[int, str]],
        on_after_sort: Optional[Callable[[ft.DataTable], None]] = None,
    ) -> None:
        """
        Vincula callbacks de sorting por columna.

        sort_specs: lista de (indice_columna, tipo_valor)
          tipo_valor: "int" | "money" | "float" | "text"

        ⚠️ Nota:
        - Si tu tabla ya fue construida con PaymentTableBuilder(on_sort=...), NO uses bind_sorting.
        """
        if not isinstance(datatable, ft.DataTable):
            return

        self._ensure_snapshot(datatable)
        if not datatable.columns:
            return

        spec_map = {idx: tp for idx, tp in sort_specs}

        for i, col in enumerate(datatable.columns):
            if i not in spec_map:
                continue

            value_type = spec_map[i]

            def _make_on_sort(index=i, t=value_type):
                def _on_sort(e: Any):
                    # 1) Tomar ascending si existe
                    asc: Optional[bool] = None
                    try:
                        if hasattr(e, "ascending"):
                            asc = bool(getattr(e, "ascending"))
                    except Exception:
                        asc = None

                    # 2) Fallback: toggle por estado interno si no vino asc
                    tid = id(datatable)
                    if asc is None:
                        last = self._sort_state.get(tid)
                        if last and last[0] == index:
                            asc = not bool(last[1])
                        else:
                            asc = True

                    # 3) Ordenar
                    self.sort_table(
                        datatable,
                        column_index=index,
                        value_type=t,
                        ascending=bool(asc),
                    )

                    # 4) Guardar estado + callback
                    self._sort_state[tid] = (index, bool(asc))
                    if callable(on_after_sort):
                        try:
                            on_after_sort(datatable)
                        except Exception:
                            pass
                return _on_sort

            # Asignación defensiva (algunas builds viejas no dejan setear)
            try:
                col.on_sort = _make_on_sort()  # type: ignore[attr-defined]
            except Exception:
                pass

        self._safe_update(datatable)

    # ------------------------------------------------------------------
    # Atajos alineados con TUS columnas reales
    # ------------------------------------------------------------------
    def bind_standard_sorters_to_pendientes(
        self,
        datatable: ft.DataTable,
        on_after_sort: Optional[Callable[[ft.DataTable], None]] = None,
        *,
        id_pago_idx: int = 0,
        monto_base_idx: int = 6,   # ✅ COLUMNS_EDICION -> monto_base (idx 6)
        total_idx: int = 12,       # ✅ COLUMNS_EDICION -> total (idx 12)
    ) -> None:
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
        id_pago_idx: int = 0,
        monto_base_idx: int = 3,   # ✅ confirmados compactos -> monto_base (idx 3)
        total_idx: int = 9,        # ✅ confirmados compactos -> total (idx 9)
    ) -> None:
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
        if not isinstance(datatable, ft.DataTable):
            return
        rows = list(datatable.rows or [])
        if not rows:
            return

        def key_fn(row: ft.DataRow) -> Union[str, NumericType]:
            return self._cell_value_as(row, column_index, value_type)

        try:
            rows_sorted = sorted(rows, key=key_fn, reverse=not bool(ascending))
            datatable.rows = rows_sorted
            datatable.sort_column_index = int(column_index)
            datatable.sort_ascending = bool(ascending)
        except Exception:
            # No romper UI si hay un valor raro
            return

        self._safe_update(datatable)

    # ------------------------------------------------------------------
    # Filtros/priorizaciones en DataTable (prefijos)
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
        self._ensure_snapshot(datatable)
        base_rows = list(self._snapshots.get(id(datatable), list(datatable.rows or [])))

        emp_pref = self._norm_digits_prefix(id_empleado_prefix)
        pago_pref = self._norm_digits_prefix(id_pago_prefix)

        if not emp_pref and not pago_pref:
            datatable.rows = base_rows
            self._safe_update(datatable)
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

        datatable.rows = matching if mode == "filter" else (matching + non_matching)
        self._safe_update(datatable)

    def apply_standard_filters_to_pendientes_table(
        self,
        datatable: ft.DataTable,
        *,
        id_empleado_prefix: str = "",
        id_pago_prefix: str = "",
        match_mode: Literal["or", "and"] = "or",
        mode: Literal["prioritize", "filter"] = "prioritize",
        id_empleado_idx: int = 1,
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
        id_empleado_idx: int = 1,
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

    # ------------------------------------------------------------------
    # Filtro duro por IDs de empleado (excluye filas)
    # ------------------------------------------------------------------
    def filter_by_employee_ids(
        self,
        datatable: ft.DataTable,
        *,
        employee_col_index: int,
        employee_ids: Iterable[int],
    ) -> None:
        self._ensure_snapshot(datatable)
        tid = id(datatable)
        ids = set(int(x) for x in employee_ids)
        self._active_filters[tid] = ids
        base_rows = list(self._snapshots.get(tid, list(datatable.rows or [])))

        filtered: List[ft.DataRow] = []
        for r in base_rows:
            try:
                val = self._cell_value_as(r, employee_col_index, "int")
                if int(val) in ids:
                    filtered.append(r)
            except Exception:
                continue

        datatable.rows = filtered
        self._safe_update(datatable)

    def clear_filter(self, datatable: ft.DataTable) -> None:
        tid = id(datatable)
        if tid in self._snapshots:
            datatable.rows = list(self._snapshots[tid])
            self._active_filters[tid] = None
            self._safe_update(datatable)

    # ------------------------------------------------------------------
    # Utilidades públicas
    # ------------------------------------------------------------------
    @staticmethod
    def parse_id_query(query: str) -> List[int]:
        """Convierte '1,2,5-8' -> [1,2,5,6,7,8]"""
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
    # Internos de parsing
    # ------------------------------------------------------------------
    @staticmethod
    def _norm_digits_prefix(s: str) -> str:
        s = (s or "").strip()
        return "".join(ch for ch in s if ch.isdigit())

    @staticmethod
    def _money_to_float(s: Any) -> float:
        """
        Soporta:
        - "$1,234.56"  -> 1234.56
        - "1.234,56"   -> 1234.56
        - "1 234,56"   -> 1234.56
        - "1234"       -> 1234.0
        """
        try:
            if isinstance(s, (int, float)):
                f = float(s)
                if math.isnan(f) or math.isinf(f):
                    return 0.0
                return f
            if s is None:
                return 0.0
            txt = str(s).strip()
            if not txt:
                return 0.0

            txt = re.sub(r"[^\d,.\-]", "", txt)

            has_comma = "," in txt
            has_dot = "." in txt
            if has_comma and has_dot:
                # decide decimal por el último separador
                if txt.rfind(",") > txt.rfind("."):
                    txt = txt.replace(".", "").replace(",", ".")
                else:
                    txt = txt.replace(",", "")
            elif has_comma and not has_dot:
                # si parece decimal
                parts = txt.split(",")
                if len(parts) == 2 and len(parts[1]) in (2, 3):
                    txt = txt.replace(",", ".")
                else:
                    txt = txt.replace(",", "")
            else:
                txt = txt.replace(",", "")

            f = float(txt)
            if math.isnan(f) or math.isinf(f):
                return 0.0
            return f
        except Exception:
            return 0.0

    @staticmethod
    def _text_value(x: Any) -> str:
        try:
            return str(getattr(x, "value", x))
        except Exception:
            try:
                return str(x)
            except Exception:
                return ""

    @staticmethod
    def _get_cell_content(row: ft.DataRow, index: int) -> Any:
        """
        Extrae "lo que se ve" en una celda, tolerando:
        - ft.Text (value)
        - ft.TextField (value)
        - ft.Container(content=ft.Text(...)) (baja un nivel)
        """
        try:
            cell = row.cells[index]
        except Exception:
            return ""

        c = getattr(cell, "content", None)
        if c is None:
            return ""

        # Caso directo: Text/TextField u otro con .value
        try:
            if hasattr(c, "value"):
                return getattr(c, "value")
        except Exception:
            pass

        # Caso Container con content interno
        inner = getattr(c, "content", None)
        if inner is not None:
            try:
                if hasattr(inner, "value"):
                    return getattr(inner, "value")
            except Exception:
                pass

        return c

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
    # Integración con listas (expansibles)
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
        def k(row: Dict[str, Any]):
            if key == "id_pago":
                return int(row.get(id_pago_fields[0]) or row.get(id_pago_fields[1]) or 0)
            if key == "id_empleado":
                return int(row.get(emp_field) or 0)
            if key == "monto_base":
                return float(row.get("monto_base") or 0.0)
            if key == "total":
                if compute_total:
                    try:
                        return float(compute_total(row))
                    except Exception:
                        return float(row.get("monto_base") or 0.0)
                return float(row.get("monto_base") or 0.0)
            return 0

        return sorted(items, key=k, reverse=not bool(asc))

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
        return sorted(list(rows or []), key=key_fn, reverse=not bool(ascending))
