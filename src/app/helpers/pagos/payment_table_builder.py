import flet as ft
from typing import List


class PaymentTableBuilder:
    """
    Builder centralizado de tablas de pagos (compactas).
    Diseñado para laptop de 16 pulgadas: filas pequeñas, fuente reducida y scroll interno.
    """

    DEFAULT_WIDTHS = {
        "id_pago": 60,
        "id_empleado": 70,
        "nombre": 150,
        "fecha_pago": 95,
        "horas": 65,
        "sueldo_hora": 90,
        "monto_base": 100,
        "descuentos": 95,
        "prestamos": 95,
        "saldo": 85,
        "deposito": 95,
        "efectivo": 95,
        "total": 95,
        "ediciones": 85,
        "acciones": 100,
        "estado": 80,
    }

    def __init__(self):
        # Configuración compacta fija
        self.heading_row_height = 28
        self.data_row_min_height = 26
        self.data_row_max_height = 30
        self.font_size = 11
        self.column_spacing = 6

    def build_table(
        self, columns: List[str], rows: List[ft.DataRow] | None = None
    ) -> ft.DataTable:
        """
        Construye una tabla DataTable compacta con las columnas especificadas.
        - columns: lista de claves (ej. ["id_pago", "nombre", "saldo"])
        - rows: filas opcionales
        """
        rows = rows or []

        def H(key: str) -> ft.DataColumn:
            return ft.DataColumn(
                label=ft.Container(
                    ft.Text(
                        key.replace("_", " ").title(),
                        size=self.font_size,
                        weight=ft.FontWeight.BOLD,
                    ),
                    width=self.DEFAULT_WIDTHS.get(key, 90),
                )
            )

        return ft.DataTable(
            columns=[H(c) for c in columns],
            rows=rows,
            heading_row_height=self.heading_row_height,
            data_row_min_height=self.data_row_min_height,
            data_row_max_height=self.data_row_max_height,
            column_spacing=self.column_spacing,
        )

    def wrap_scroll(
        self, table: ft.DataTable, height: int = 220, width: int = 1600
    ) -> ft.Container:
        """
        Envuelve la tabla en un contenedor con scroll vertical interno.
        Compatible con Flet 0.24+ (Container no acepta 'scroll').
        """
        return ft.Container(
            content=ft.Column(
                controls=[table],
                scroll=ft.ScrollMode.ALWAYS,  # ✅ Scroll vertical
                expand=True,
            ),
            width=width,
            height=height,
            expand=False,
        )
