# app/helpers/pagos/payment_table_builder.py
from __future__ import annotations

import flet as ft
from typing import List, Dict, Optional, Callable, Iterable, Any


class PaymentTableBuilder:
    """
    Builder centralizado de tablas de pagos (compactas).

    Objetivos:
    - Encabezados compactos con anchos fijos por columna (estabilidad visual).
    - Soporte de ordenamiento (sorting) por columna con indicador visual (▲/▼).
    - Opción de incluir una barra de filtros encima de la tabla.
    - Diseñado para laptop: filas pequeñas, fuente reducida y scroll interno.

    Importante (Flet):
    - sort_column_index + sort_ascending funcionan mejor si controlas bien None/int.
    - on_sort puede variar entre builds (a veces no trae e.ascending).
    """

    DEFAULT_WIDTHS: Dict[str, int] = {
        "id_pago": 60,
        "id_empleado": 70,
        "nombre": 150,
        "fecha_pago": 95,
        "horas": 70,
        "sueldo_hora": 90,
        "monto_base": 110,
        "descuentos": 95,
        "prestamos": 95,
        "saldo": 85,
        "deposito": 95,
        "efectivo": 95,
        "total": 110,
        "ediciones": 85,
        "acciones": 100,
        "estado": 80,
    }

    # Columnas típicamente numéricas (alineación y render numérico)
    NUMERIC_COLS = {
        "id_pago", "id_empleado",
        "horas", "sueldo_hora",
        "monto_base", "descuentos", "prestamos",
        "saldo", "deposito", "efectivo", "total",
    }

    def __init__(self):
        # Configuración compacta fija
        self.heading_row_height = 28
        self.data_row_min_height = 26
        self.data_row_max_height = 30
        self.font_size = 11
        self.column_spacing = 6

        # Defaults visuales para headers
        self._header_pad = ft.padding.symmetric(horizontal=6, vertical=4)

    # ----------------------------------------------------
    # Helpers internos
    # ----------------------------------------------------
    def _col_width(self, key: str, fallback: int = 90) -> int:
        """Devuelve ancho fijo de columna; siempre un int válido."""
        try:
            w = int(self.DEFAULT_WIDTHS.get(key, fallback))
            return max(50, w)  # nunca permitir demasiado pequeño
        except Exception:
            return int(fallback)

    @staticmethod
    def _safe_bool(v: Any, default: bool = True) -> bool:
        try:
            return bool(v)
        except Exception:
            return default

    # ----------------------------------------------------
    # Tabla compacta con soporte de sorting
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
        # Anti “doble indicador”: algunas versiones pintan flecha nativa + texto con ▲/▼
        disable_sort_indicator_in_label: bool = False,
    ) -> ft.DataTable:
        """
        Construye una DataTable compacta.

        Args:
            columns: lista de claves (ej. ["id_pago", "nombre", "saldo"])
            rows: filas opcionales (ft.DataRow)
            sortable_cols: columnas habilitadas para ordenar; si es None -> todas
            on_sort: callback (col_key, ascending) al ordenar
            sort_key: clave de la columna actualmente ordenada (para indicador visual)
            sort_ascending: dirección actual (True=ASC, False=DESC)
            column_labels: mapping opcional key->texto header
            tooltip_labels: mapping opcional key->tooltip header
            disable_sort_indicator_in_label:
                Si True, NO agrega ▲/▼ al texto del header (dejas solo el indicador nativo de Flet).
        """
        columns = list(columns or [])
        rows = rows or []
        column_labels = column_labels or {}
        tooltip_labels = tooltip_labels or {}

        sortable_set = set(sortable_cols) if sortable_cols is not None else set(columns)

        # Índice de columna ordenada (Flet pinta flecha nativa si lo soporta)
        sort_col_index: Optional[int] = None
        if sort_key and sort_key in columns:
            try:
                sort_col_index = columns.index(sort_key)
            except Exception:
                sort_col_index = None

        def _on_sort_event(e: Any, key: str) -> None:
            """
            Handler robusto para sorting:
            - En algunos builds llega e.ascending
            - En otros solo llega e.column_index o nada útil => togglear manualmente
            """
            if on_sort is None:
                return

            asc: Optional[bool] = None

            # Caso 1: e.ascending (común)
            try:
                if hasattr(e, "ascending"):
                    asc = bool(e.ascending)
            except Exception:
                asc = None

            # Caso 2: sin ascending => togglear si es la misma columna
            if asc is None:
                try:
                    if sort_key == key:
                        asc = not bool(sort_ascending)
                    else:
                        asc = True
                except Exception:
                    asc = True

            try:
                on_sort(key, bool(asc))
            except Exception:
                # nunca romper UI por handler externo
                pass

        def _make_header(key: str) -> ft.DataColumn:
            base_label = column_labels.get(key, key.replace("_", " ").title())

            # Indicador manual en label (opcional)
            if (not disable_sort_indicator_in_label) and (sort_key == key):
                label_text = self.mark_sorted_column(base_label, bool(sort_ascending))
            else:
                label_text = base_label

            tooltip = tooltip_labels.get(key)

            # Container para fijar ancho y evitar “salto” visual
            label = ft.Container(
                content=ft.Text(
                    label_text,
                    size=self.font_size,
                    weight=ft.FontWeight.BOLD,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    no_wrap=True,
                ),
                width=self._col_width(key),
                padding=self._header_pad,
                alignment=ft.alignment.center_left if key not in self.NUMERIC_COLS else ft.alignment.center_right,
                tooltip=tooltip,
            )

            return ft.DataColumn(
                label=label,
                numeric=(key in self.NUMERIC_COLS),
                on_sort=((lambda e, k=key: _on_sort_event(e, k)) if (callable(on_sort) and key in sortable_set) else None),
            )

        table = ft.DataTable(
            columns=[_make_header(c) for c in columns],
            rows=rows,
            heading_row_height=self.heading_row_height,
            data_row_min_height=self.data_row_min_height,
            data_row_max_height=self.data_row_max_height,
            column_spacing=self.column_spacing,
            # Sorting props (Flet)
            sort_column_index=sort_col_index,
            sort_ascending=self._safe_bool(sort_ascending, True) if sort_col_index is not None else True,
        )
        return table

    def mark_sorted_column(self, label_text: str, ascending: bool) -> str:
        """Añade flecha asc/desc a la etiqueta de columna ordenada."""
        arrow = "▲" if ascending else "▼"
        return f"{label_text} {arrow}"

    # ----------------------------------------------------
    # Barra de filtros (opcional)
    # ----------------------------------------------------
    def build_filter_bar(
        self,
        *,
        filters_for: Iterable[str],
        values: Optional[Dict[str, str]] = None,
        on_change: Optional[Callable[[str, str], None]] = None,
        placeholder_map: Optional[Dict[str, str]] = None,
        debounce_ms: Optional[int] = None,
    ) -> ft.Row:
        """
        Construye una barra de filtros compacta con TextField por columna.

        Nota:
        - debounce_ms se deja como parámetro “documental”.
          El debounce real conviene hacerlo en el Container (con page.run_task / Timer),
          para no acoplar este helper a Page.
        """
        values = values or {}
        placeholder_map = placeholder_map or {}

        controls: List[ft.Control] = []

        for key in list(filters_for or []):
            tf = ft.TextField(
                value=str(values.get(key, "")),
                height=32,
                text_size=self.font_size,
                dense=True,
                content_padding=ft.padding.symmetric(6, 8),
                width=self._col_width(key, fallback=120),
                hint_text=placeholder_map.get(key, f"Filtrar {key}"),
                on_change=(lambda e, k=key: on_change(k, e.control.value)) if callable(on_change) else None,
            )
            controls.append(ft.Container(content=tf, padding=ft.padding.only(right=6)))

        return ft.Row(controls=controls, spacing=6, wrap=True)

    # ----------------------------------------------------
    # Wrapper con scroll y (opcional) controles arriba
    # ----------------------------------------------------
    def wrap_scroll(
        self,
        table: ft.DataTable,
        height: int = 220,
        width: int = 1600,
        *,
        top_controls: Optional[List[ft.Control]] = None,
        scroll_mode: ft.ScrollMode = ft.ScrollMode.ALWAYS,
    ) -> ft.Container:
        """
        Envuelve la tabla en un contenedor con scroll vertical interno.
        Si se pasan top_controls (ej. filtros), se muestran arriba.

        Importante:
        - Para que el scroll funcione estable, el contenedor debe tener height fijo.
        """
        col_controls: List[ft.Control] = []
        if top_controls:
            col_controls.extend([c for c in top_controls if c is not None])
        col_controls.append(table)

        return ft.Container(
            content=ft.Column(
                controls=col_controls,
                scroll=scroll_mode,
                expand=True,
                tight=True,  # evita espacios raros
            ),
            width=int(width),
            height=int(height),
            expand=False,
        )
