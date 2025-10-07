# app/helpers/pagos/sorting_filter_payment_helper.py
from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union
import re
import flet as ft


NumericType = Union[int, float]


class PaymentSortFilterHelper:
    """
    Helper genérico para filtrar y ordenar tablas de pagos (ft.DataTable).

    • Filtro por Id de empleado: mantiene un snapshot de filas originales y muestra
      solo las que coinciden con los Ids buscados.
    • Orden por columnas: Id Pago, Monto Base y Total (o cualquier otra que definas).
    • Funciones atajo para tus dos tablas estándar:
        - bind_standard_sorters_to_pendientes(datatable)  -> usa índices [0, 6, 12]
        - bind_standard_sorters_to_confirmado(datatable)  -> usa índices [0, 3, 9]

    Cómo usar (ejemplo rápido):
        helper = PaymentSortFilterHelper()
        helper.bind_standard_sorters_to_pendientes(self.tabla_pendientes)

        # Filtro por empleados "1,3,5-7"
        ids = helper.parse_id_query("1,3,5-7")
        helper.filter_by_employee_ids(self.tabla_pendientes, employee_col_index=1, employee_ids=ids)

        # Limpiar filtro:
        helper.clear_filter(self.tabla_pendientes)
    """

    # --------------------- API pública ---------------------

    def __init__(self):
        # id(datatable) -> snapshot completo de filas (sin filtros aplicados)
        self._snapshots: Dict[int, List[ft.DataRow]] = {}
        # id(datatable) -> estado de filtro actual (set de ids o None)
        self._active_filters: Dict[int, Optional[set[int]]] = {}

    # ---- Binding de sorters (genérico) ----
    def bind_sorting(
        self,
        datatable: ft.DataTable,
        sort_specs: Sequence[Tuple[int, str]],
        on_after_sort: Optional[Callable[[ft.DataTable], None]] = None,
    ) -> None:
        """
        Conecta callbacks de ordenamiento a columnas existentes.

        :param datatable: ft.DataTable objetivo.
        :param sort_specs: lista de pares (col_index, tipo),
                           tipo en {"int", "money", "float", "text"}.
        :param on_after_sort: callback opcional tras ordenar (ej. recalcular totales de grupo).
        """
        # Garantiza snapshot inicial (para poder limpiar filtros más adelante).
        self._ensure_snapshot(datatable)

        # Asegura que hay columnas suficientes.
        if not datatable.columns:
            return

        # Mapa: col_index -> tipo
        spec_map = {idx: tp for idx, tp in sort_specs}

        for i, col in enumerate(datatable.columns):
            if i not in spec_map:
                continue
            tp = spec_map[i]

            # Reemplaza/inyecta el callback de sorteo en el DataColumn.
            def _make_on_sort(index: int, t: str):
                def _on_sort(e: ft.DataColumnSortEvent):
                    ascending = e.ascending
                    self.sort_table(datatable, column_index=index, value_type=t, ascending=ascending)
                    if on_after_sort:
                        on_after_sort(datatable)
                return _on_sort

            col.on_sort = _make_on_sort(i, tp)

        datatable.update()

    # ---- Atajos para tus tablas estándar ----
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

    # ---- Ordenar una tabla ----
    def sort_table(
        self,
        datatable: ft.DataTable,
        *,
        column_index: int,
        value_type: str = "text",
        ascending: bool = True,
    ) -> None:
        """
        Ordena las filas actuales de la tabla por la columna indicada.

        :param column_index: índice de columna a ordenar.
        :param value_type: "int" | "money" | "float" | "text".
        :param ascending: True=ascendente, False=descendente.
        """
        if not datatable.rows:
            return

        # Orden estable; clave robusta por tipo de dato.
        def key_fn(row: ft.DataRow) -> Union[str, NumericType]:
            return self._cell_value_as(row, column_index, value_type)

        datatable.rows = sorted(datatable.rows, key=key_fn, reverse=not ascending)
        datatable.sort_column_index = column_index
        datatable.sort_ascending = ascending
        datatable.update()

    # ---- Filtro por Id de empleado (columna numérica) ----
    def filter_by_employee_ids(
        self,
        datatable: ft.DataTable,
        *,
        employee_col_index: int,
        employee_ids: Iterable[int],
    ) -> None:
        """
        Aplica filtro en la tabla, mostrando sólo filas cuyo Id empleado esté en 'employee_ids'.
        Se apoya en un snapshot interno de todas las filas (sin filtro).
        """
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
                # si no se puede leer, la descartamos
                continue

        datatable.rows = filtered
        datatable.update()

    def clear_filter(self, datatable: ft.DataTable) -> None:
        """Restaura la tabla a su snapshot original (sin filtros)."""
        tid = id(datatable)
        if tid in self._snapshots:
            datatable.rows = list(self._snapshots[tid])
            self._active_filters[tid] = None
            datatable.update()

    # --------------------- Utilidades públicas ---------------------

    @staticmethod
    def parse_id_query(query: str) -> List[int]:
        """
        Parsea consultas como:
            "12" -> [12]
            "12,15,20" -> [12,15,20]
            "5-8" -> [5,6,7,8]
            "1,3-5,10" -> [1,3,4,5,10]
        Ignora espacios y entradas inválidas.
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
                    if x <= y:
                        ids.extend(range(x, y + 1))
                    else:
                        ids.extend(range(y, x + 1))
                except Exception:
                    # ignorar rango inválido
                    pass
            else:
                try:
                    ids.append(int(p))
                except Exception:
                    pass
        # único y ordenado
        return sorted(set(ids))

    # --------------------- Internos ---------------------

    def _ensure_snapshot(self, datatable: ft.DataTable) -> None:
        """Guarda snapshot inicial si no existe para este DataTable."""
        tid = id(datatable)
        if tid not in self._snapshots:
            self._snapshots[tid] = list(datatable.rows or [])

    @staticmethod
    def _money_to_float(s: Union[str, float, int]) -> float:
        """
        Convierte representaciones como "$9,974.76", "9,974.76", "$-7.80", "-$7.80"
        o numéricos a float robusto.
        """
        if isinstance(s, (int, float)):
            return float(s)
        if not s:
            return 0.0
        txt = str(s).strip()
        # Mantener solo dígitos, '.', '-' (soporta signos y separadores)
        txt = re.sub(r"[^\d\.\-]", "", txt)
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

    def _cell_value_as(self, row: ft.DataRow, index: int, value_type: str) -> Union[str, NumericType]:
        """
        Lee el valor de una celda como tipo indicado.
        value_type: "int" | "money" | "float" | "text"
        """
        try:
            cell = row.cells[index]
            raw = getattr(cell.content, "value", cell.content)
        except Exception:
            raw = ""

        if value_type == "int":
            try:
                return int(self._money_to_float(raw))
            except Exception:
                return 0
        elif value_type == "money" or value_type == "float":
            return self._money_to_float(raw)
        else:
            return self._text_value(raw)

    # --------------------- Extras convenientes ---------------------

    def apply_filter_and_sort(
        self,
        datatable: ft.DataTable,
        *,
        employee_col_index: Optional[int] = None,
        employee_ids: Optional[Iterable[int]] = None,
        sort_by: Optional[Tuple[int, str, bool]] = None,
    ) -> None:
        """
        Aplica (opcionalmente) filtro y luego orden en una sola llamada.
        :param employee_col_index: índice de la columna 'Id Empleado'.
        :param employee_ids: ids a mantener (None = sin filtro).
        :param sort_by: (col_index, value_type, ascending) o None para saltar sort.
        """
        if employee_col_index is not None and employee_ids is not None:
            self.filter_by_employee_ids(datatable, employee_col_index=employee_col_index, employee_ids=employee_ids)
        else:
            # si no hay filtro, asegúrate de tener snapshot y deja filas actuales
            self._ensure_snapshot(datatable)

        if sort_by is not None:
            col_idx, val_type, asc = sort_by
            self.sort_table(datatable, column_index=col_idx, value_type=val_type, ascending=asc)

    # ------------- Integración con grupos (opcional) -------------

    def sort_rows_inplace(
        self,
        rows: List[ft.DataRow],
        *,
        column_index: int,
        value_type: str,
        ascending: bool = True,
    ) -> List[ft.DataRow]:
        """
        Útil si quieres ordenar fuera del DataTable (p. ej., al construir filas).
        Devuelve la lista ordenada (no modifica 'rows' original).
        """
        def key_fn(r: ft.DataRow):
            return self._cell_value_as(r, column_index, value_type)
        return sorted(rows, key=key_fn, reverse=not ascending)
