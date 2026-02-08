# app/helpers/pagos/payment_table_builder.py
# Flet 0.24: acciones clickeables + sin "ediciones" + spacing estable + wrap_scroll compatible
from __future__ import annotations

import flet as ft
from typing import List, Dict, Optional, Callable, Iterable, Any


class PaymentTableBuilder:
    """
    Builder centralizado de DataTable para pagos (Flet 0.24).

    Objetivos (pedidos):
    ✅ 1) Acciones (IconButtons) SIEMPRE clickeables dentro de DataTable.
    ✅ 2) Sin columna "ediciones" (si llega, se filtra).
    ✅ 3) Sin "mark_sorted_column" / sin iconos / sin flechas en headers para sorting.
       - Se mantiene sorting nativo del DataTable (on_sort), pero el header NO cambia visualmente.
    ✅ 4) wrap_scroll() compatible con tus containers (acepta width=...).
    ✅ 5) get_table_width(): ancho recomendado para no cortar el scroll horizontal.

    Reglas para hit-test (acciones):
    - TODO lo visible debe vivir dentro del width real de la celda.
    - NO usar column_spacing negativo.
    - Wrapper fijo + clip HARD_EDGE en acciones para que no exista "visible pero no clickeable".
    """

    # ---------------------------
    # Anchos por defecto (fuente de verdad)
    # ---------------------------
    DEFAULT_WIDTHS: Dict[str, int] = {
        "id_pago": 65,
        "id_empleado": 85,
        "nombre": 170,
        "fecha_pago": 80,
        "horas": 60,
        "sueldo_hora": 95,
        "monto_base": 95,
        "descuentos": 95,
        "prestamos": 95,
        "saldo": 85,
        "deposito": 105,
        "efectivo": 90,
        "total": 115,

        # 4 iconos (descuentos, prestamos, confirmar, borrar)
        # 4*28 + 3*4 = 124 -> dejamos margen minimo
        "acciones": 200,

        "estado": 70,
    }

    NUMERIC_COLS = {
        "id_pago", "id_empleado",
        "horas", "sueldo_hora",
        "monto_base", "descuentos", "prestamos",
        "saldo", "deposito", "efectivo", "total",
    }

    ACTION_COLS = {"acciones"}
    STATE_COLS = {"estado"}
    # Whitelist exacta de columnas sorteables para pagos
    ALLOWED_SORTABLE_COLS = {
        "id_pago",
        "id_empleado",
        "horas",
        "sueldo_hora",
        "monto_base",
        "descuentos",
        "prestamos",
        "deposito",
        "saldo",
        "efectivo",
        "total",
    }

    def __init__(self):
        # Layout compacto
        self.heading_row_height = 28
        self.data_row_min_height = 26
        self.data_row_max_height = 30
        self.font_size = 11

        # Estable (sin hacks negativos)
        self.column_spacing = 0
        self._horizontal_margin = 0

        self._header_pad = ft.padding.symmetric(horizontal=6, vertical=4)

        # ---- Ajustes finos de aire ----
        self._gap_total_right = 16
        self._gap_acciones_left = 0

        # Ajuste Acciones <-> Estado (compacto)
        self._gap_acciones_right = 0
        self._gap_estado_left = 6
        # Empuje visual de "estado" hacia la izquierda (superpone con acciones)
        # Empuje del contenido de "estado" hacia acciones
        self._estado_pull_left = 80
        # Empuje del header "Estado" (alineado con el contenido)
        self._estado_header_pull_left = 80

        # Estado de sort interno por columna (para toggle asc/desc sin iconos)
        self._sort_state: Dict[str, bool] = {}

    # ----------------------------------------------------
    # Helpers
    # ----------------------------------------------------
    def _col_width(self, key: str, fallback: int = 90) -> int:
        try:
            w = int(self.DEFAULT_WIDTHS.get(key, fallback))
            return max(50, w)
        except Exception:
            return int(fallback)

    @staticmethod
    def _safe_bool(v: Any, default: bool = True) -> bool:
        try:
            return bool(v)
        except Exception:
            return default

    # ----------------------------------------------------
    # ✅ Ancho total recomendado (para containers)
    # ----------------------------------------------------
    def get_table_width(
        self,
        columns: List[str],
        *,
        buffer: int = 16,
        include_horizontal_margin: bool = True,
    ) -> int:
        """
        Devuelve el ancho total recomendado para envolver la tabla.

        Úsalo así en tu container:
            width = table_builder.get_table_width(COL_KEYS, buffer=16)
            table_container.width = width

        buffer:
        - Si se CORTA al final del scroll: SUBE buffer (16 -> 32 -> 48)
        - Si sobra demasiado: BAJA buffer (48 -> 16 -> 8)
        """
        cols = [c for c in (columns or []) if c != "ediciones"]
        total = 0
        for k in cols:
            total += self._col_width(k, fallback=90)

        if include_horizontal_margin:
            total += int(self._horizontal_margin) * 2

        total += int(buffer)
        return max(300, int(total))

    # ----------------------------------------------------
    # build_table
    # ----------------------------------------------------
    def build_table(
        self,
        columns: List[str],
        rows: Optional[List[ft.DataRow]] = None,
        *,
        sortable_cols: Optional[Iterable[str]] = None,
        on_sort: Optional[Callable[[str, bool], None]] = None,
        sort_key: Optional[str] = None,
        sort_ascending: bool = True,
        column_labels: Optional[Dict[str, str]] = None,
        tooltip_labels: Optional[Dict[str, str]] = None,
        # Si False, no muestra indicador (flecha) de sorting
        show_sort_indicator: bool = False,
        # ⚠️ Se conserva por compat, pero aquí ya no se usa para pintar flechas en header
        disable_sort_indicator_in_label: bool = True,
    ) -> ft.DataTable:
        """
        Crea el DataTable con:
        - columnas filtradas (sin 'ediciones')
        - headers sin flechas / sin iconos de sorting
        - sorting nativo opcional (on_sort) en DataColumn.on_sort

        NOTA:
        - Flet maneja el indicador visual por su cuenta si sort_column_index está seteado.
        - Nosotros NO alteramos el texto del header (sin ▲▼, sin iconos).
        """
        columns = list(columns or [])
        rows = rows or []
        column_labels = column_labels or {}
        tooltip_labels = tooltip_labels or {}

        # Blindaje: fuera "ediciones"
        columns = [c for c in columns if c != "ediciones"]

        sortable_set = set(sortable_cols) if sortable_cols is not None else set(columns)
        sortable_set &= self.ALLOWED_SORTABLE_COLS

        sort_col_index: Optional[int] = None
        if sort_key and sort_key in columns:
            try:
                sort_col_index = columns.index(sort_key)
            except Exception:
                sort_col_index = None

        def _on_sort_event(e: Any, key: str) -> None:
            """
            Handler robusto:
            - Si Flet trae e.ascending, lo usamos
            - Si no, alternamos asc/desc por columna (2 estados)
            """
            if on_sort is None:
                return

            asc: Optional[bool] = None
            try:
                if hasattr(e, "ascending"):
                    asc = bool(e.ascending)
            except Exception:
                asc = None

            if asc is None:
                try:
                    # toggle interno por columna
                    prev = self._sort_state.get(key)
                    asc = True if prev is None else (not bool(prev))
                except Exception:
                    asc = True

            try:
                self._sort_state[key] = bool(asc)
                on_sort(key, bool(asc))
            except Exception:
                pass

        def _make_header(key: str) -> ft.DataColumn:
            # ✅ SIN mark_sorted_column y sin indicadores custom
            label_text = column_labels.get(key, key.replace("_", " ").title())

            tooltip = tooltip_labels.get(key)
            is_numeric = key in self.NUMERIC_COLS

            if key in self.ACTION_COLS:
                header_align = ft.alignment.center
            elif key in self.STATE_COLS:
                header_align = ft.alignment.center
            else:
                header_align = ft.alignment.center_right if is_numeric else ft.alignment.center_left

            text = ft.Text(
                str(label_text),
                size=self.font_size,
                weight=ft.FontWeight.BOLD,
                overflow=ft.TextOverflow.ELLIPSIS,
                no_wrap=True,
            )

            if key in self.ACTION_COLS:
                content = ft.Row([text], alignment=ft.MainAxisAlignment.CENTER, expand=True)
            else:
                content = text

            label = ft.Container(
                content=content,
                width=self._col_width(key),
                padding=self._header_pad,
                alignment=ft.alignment.center if key in self.ACTION_COLS else header_align,
                tooltip=tooltip,
                margin=ft.margin.only(left=-self._estado_header_pull_left, right=0, top=0, bottom=0)
                if key in self.STATE_COLS else None,
            )

            return ft.DataColumn(
                label=label,
                numeric=is_numeric,
                # ✅ Sorting nativo (sin “iconos” ni “mark_*”)
                on_sort=((lambda e, k=key: _on_sort_event(e, k)) if (callable(on_sort) and key in sortable_set) else None),
            )

        return ft.DataTable(
            columns=[_make_header(c) for c in columns],
            rows=rows,
            heading_row_height=self.heading_row_height,
            data_row_min_height=self.data_row_min_height,
            data_row_max_height=self.data_row_max_height,
            column_spacing=self.column_spacing,
            horizontal_margin=self._horizontal_margin,
            # Sorting nativo (opcional)
            sort_column_index=sort_col_index if show_sort_indicator else None,
            sort_ascending=self._safe_bool(sort_ascending, True) if (show_sort_indicator and sort_col_index is not None) else True,
        )

    # ----------------------------------------------------
    # wrap_cell (clave de hit-test)
    # ----------------------------------------------------
    def wrap_cell(self, key: str, control: ft.Control, *, fallback: int = 90) -> ft.DataCell:
        """
        Envuelve controles en un Container con width fijo para:
        - alinear header y data
        - asegurar hit-test correcto (especialmente en acciones)

        Ajuste pedido:
        - acercar "estado" a "acciones" reduciendo el aire.
        """
        w = self._col_width(key, fallback=fallback)
        is_numeric = key in self.NUMERIC_COLS
        is_actions = key in self.ACTION_COLS
        is_estado = key in self.STATE_COLS

        pad = ft.padding.only(left=4, right=6, top=0, bottom=0)

        if key == "total":
            pad = ft.padding.only(left=4, right=self._gap_total_right, top=0, bottom=0)

        if is_actions:
            # compacta acciones para evitar gap con estado
            pad = ft.padding.only(
                left=self._gap_acciones_left,
                right=self._gap_acciones_right,
                top=0,
                bottom=0,
            )

        if is_estado:
            pad = ft.padding.only(
                left=self._gap_estado_left,
                right=2,
                top=0,
                bottom=0,
            )

        # Alignment
        if is_actions:
            # Pegar acciones hacia la derecha para quedar junto a "estado"
            align = ft.alignment.center_right
        elif is_estado:
            align = ft.alignment.center
        else:
            align = ft.alignment.center_right if is_numeric else ft.alignment.center_left

        # HITBOX blindado para acciones
        if is_actions:
            control = ft.Container(
                content=control,
                width=w,
                height=max(28, self.data_row_max_height),
                alignment=ft.alignment.center_right,
                padding=0,
            )

        return ft.DataCell(
            ft.Container(
                content=control,
                width=w,
                height=max(28, self.data_row_max_height) if is_actions else None,
                alignment=align,
                padding=pad,
                margin=ft.margin.only(left=-self._estado_pull_left, right=0, top=0, bottom=0)
                if is_estado else None,
                clip_behavior=ft.ClipBehavior.HARD_EDGE if is_actions else ft.ClipBehavior.NONE,
            )
        )

    # ----------------------------------------------------
    # ✅ wrap_scroll (compat con Pagos Editables)
    # ----------------------------------------------------
    def wrap_scroll(
        self,
        control: ft.Control,
        *,
        width: int | float | None = None,
        height: int | float | None = None,
        expand: bool = False,
        padding: int = 0,
        scroll: ft.ScrollMode = ft.ScrollMode.ALWAYS,
    ) -> ft.Control:
        """
        Envuelve el control (usualmente DataTable) en un Row con scroll horizontal.

        ✅ Compat clave:
        - Acepta width=... (porque tu código actual ya lo manda, y antes te tronaba).
        - Si ya tienes scroll horizontal externo (ej. PagosScrollHelper),
          evita usar este wrapper para no anidar scrolls.

        Ejemplo:
            table = builder.build_table(...)
            w = builder.get_table_width(cols, buffer=16)
            return builder.wrap_scroll(table, width=w, padding=0)
        """
        row = ft.Row([control], scroll=scroll)
        return ft.Container(
            content=row,
            width=width,
            height=height,
            expand=expand,
            padding=padding,
        )
