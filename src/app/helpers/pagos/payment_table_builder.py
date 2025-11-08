import flet as ft
from typing import List, Dict, Optional, Callable, Iterable


class PaymentTableBuilder:
    """
    Builder centralizado de tablas de pagos (compactas).
    - Encabezados compactos y anchos fijos por columna.
    - Soporte de ordenamiento (sorting) por columna con indicador visual.
    - Opción de incluir una barra de filtros encima de la tabla.
    - Diseñado para laptop de 16 pulgadas: filas pequeñas, fuente reducida y scroll interno.
    """

    DEFAULT_WIDTHS: Dict[str, int] = {
        "id_pago": 60,
        "id_empleado": 70,
        "nombre": 150,
        "fecha_pago": 95,
        "horas": 70,  # CHANGE: ancho consistente para indicador de orden
        "sueldo_hora": 90,
        "monto_base": 110,  # CHANGE: evita recortes con flechas ▲▼
        "descuentos": 95,
        "prestamos": 95,
        "saldo": 85,
        "deposito": 95,
        "efectivo": 95,
        "total": 110,  # CHANGE: total amplio para indicadores
        "ediciones": 85,
        "acciones": 100,
        "estado": 80,
    }

    # Columnas típicamente numéricas (alineación/prop numérica)
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
    ) -> ft.DataTable:
        """
        Construye una DataTable compacta.

        Args:
            columns: lista de claves (ej. ["id_pago", "nombre", "saldo"])
            rows: filas opcionales (ft.DataRow)
            sortable_cols: columnas habilitadas para ordenar; si es None, se asume todas
            on_sort: callback (col_key, ascending) cuando se hace click en el header
            sort_key: clave de la columna actualmente ordenada (para pintar indicador)
            sort_ascending: dirección de orden actual (True=ASC, False=DESC)
            column_labels: mapping opcional key->texto a mostrar en header
            tooltip_labels: mapping opcional key->tooltip para header
        """
        rows = rows or []
        sortable_set = set(sortable_cols) if sortable_cols is not None else set(columns)

        # Índice de columna ordenada para que Flet pinte indicador ▲/▼
        sort_col_index = columns.index(sort_key) if (sort_key in columns) else None

        def _make_header(key: str, idx: int) -> ft.DataColumn:
            base_label = (column_labels or {}).get(key, key.replace("_", " ").title())
            label_text = (
                self.mark_sorted_column(base_label, sort_ascending) if sort_key == key else base_label
            )  # CHANGE: indicador visual de orden
            tooltip = (tooltip_labels or {}).get(key)

            # El label va envuelto para poder asignar un ancho fijo
            label = ft.Container(
                content=ft.Text(
                    label_text,
                    size=self.font_size,
                    weight=ft.FontWeight.BOLD,
                ),
                width=self.DEFAULT_WIDTHS.get(key, 90),
                tooltip=tooltip,
            )

            # DataColumn soporta on_sort nativamente en Flet
            col = ft.DataColumn(
                label=label,
                numeric=(key in self.NUMERIC_COLS),
                on_sort=(
                    (lambda e, k=key: on_sort(k, e.ascending))
                    if (on_sort is not None and key in sortable_set)
                    else None
                ),
            )
            return col

        table = ft.DataTable(
            columns=[_make_header(c, i) for i, c in enumerate(columns)],
            rows=rows,
            heading_row_height=self.heading_row_height,
            data_row_min_height=self.data_row_min_height,
            data_row_max_height=self.data_row_max_height,
            column_spacing=self.column_spacing,
            sort_column_index=sort_col_index,
            sort_ascending=sort_ascending if sort_col_index is not None else True,
        )
        return table

    def mark_sorted_column(self, label_text: str, ascending: bool) -> str:
        # CHANGE: añade flecha asc/desc a la etiqueta de columna ordenada
        arrow = "▲" if ascending else "▼"
        return f"{label_text} {arrow}"

    # ----------------------------------------------------
    # Fila/Barra de filtros (opcional)
    # ----------------------------------------------------
    def build_filter_bar(
        self,
        *,
        filters_for: Iterable[str],
        values: Optional[Dict[str, str]] = None,
        on_change: Optional[Callable[[str, str], None]] = None,
        placeholder_map: Optional[Dict[str, str]] = None,
    ) -> ft.Row:
        """
        Construye una barra de filtros compacta con TextField por columna.

        Args:
            filters_for: claves de columnas con filtro (ej. ["id_empleado", "id_pago"])
            values: valores iniciales por clave
            on_change: callback (key, value) al escribir en un filtro
            placeholder_map: textos opcionales por filtro (ej. {"id_empleado": "Filtrar empleado..."})
        """
        values = values or {}
        placeholder_map = placeholder_map or {}

        filters = []
        for key in filters_for:
            filters.append(
                ft.Container(
                    content=ft.TextField(
                        value=str(values.get(key, "")),
                        height=32,
                        text_size=self.font_size,
                        dense=True,
                        content_padding=ft.padding.symmetric(6, 8),
                        width=self.DEFAULT_WIDTHS.get(key, 120),
                        hint_text=placeholder_map.get(key, f"Filtrar {key}"),
                        on_change=(lambda e, k=key: on_change(k, e.control.value)) if on_change else None,
                    ),
                    padding=ft.padding.only(right=6),
                )
            )

        return ft.Row(controls=filters, spacing=6, wrap=True)

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
    ) -> ft.Container:
        """
        Envuelve la tabla en un contenedor con scroll vertical interno.
        Si se pasan top_controls (ej. una barra de filtros), se muestran arriba.
        """
        col_controls: List[ft.Control] = []
        if top_controls:
            col_controls.extend(top_controls)
        col_controls.append(table)

        return ft.Container(
            content=ft.Column(
                controls=col_controls,
                scroll=ft.ScrollMode.ALWAYS,  # ✅ Scroll vertical
                expand=True,
            ),
            width=width,
            height=height,
            expand=False,
        )
