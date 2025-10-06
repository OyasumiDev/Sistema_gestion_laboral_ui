import flet as ft
from typing import Dict, Any, Callable, Optional


class PaymentRowBuilder:
    """
    Constructor de filas compactas para pagos.
    Se adapta a lectura, edición o vista compacta.
    """

    def __init__(self, font_size: int = 11):
        self.font_size = font_size

    # --------------------
    # FILA DE LECTURA
    # --------------------
    def build_row_lectura(self, pago: Dict[str, Any], valores: Dict[str, Any]) -> ft.DataRow:
        """
        Construye una fila de solo lectura (texto).
        """
        cells = [
            ft.DataCell(ft.Text(str(pago.get("id_pago_nomina") or pago.get("id_pago")), size=self.font_size)),
            ft.DataCell(ft.Text(str(pago.get("numero_nomina")), size=self.font_size)),
            ft.DataCell(ft.Text(str(pago.get("nombre_empleado", "")), size=self.font_size)),
            ft.DataCell(ft.Text(str(pago.get("fecha_pago", "")), size=self.font_size)),
            ft.DataCell(ft.Text(f"${valores['descuentos']:.2f}", size=self.font_size)),
            ft.DataCell(ft.Text(f"${valores['prestamos']:.2f}", size=self.font_size)),
            ft.DataCell(ft.Text(f"${valores['saldo']:.2f}", size=self.font_size)),
            ft.DataCell(ft.Text(f"${valores['efectivo']:.2f}", size=self.font_size)),
            ft.DataCell(ft.Text(f"${valores['total']:.2f}", size=self.font_size)),
            ft.DataCell(ft.Text(str(pago.get("estado", "")), size=self.font_size)),
        ]
        return ft.DataRow(cells=cells)

    # --------------------
    # FILA DE EDICIÓN
    # --------------------
    def build_row_edicion(
        self,
        pago: Dict[str, Any],
        valores: Dict[str, Any],
        *,
        on_editar_descuentos: Optional[Callable] = None,
        on_editar_prestamos: Optional[Callable] = None,
        on_confirmar: Optional[Callable] = None,
        on_eliminar: Optional[Callable] = None,
        on_deposito_change: Optional[Callable[[str], None]] = None,
        on_deposito_blur: Optional[Callable[[], None]] = None,
        on_deposito_submit: Optional[Callable[[], None]] = None,
    ) -> ft.DataRow:
        """
        Construye una fila editable (con TextField en depósito y botones de acción).
        """
        id_pago = int(pago.get("id_pago_nomina") or pago.get("id_pago"))

        cells = [
            ft.DataCell(ft.Text(str(id_pago), size=self.font_size)),
            ft.DataCell(ft.Text(str(pago.get("numero_nomina")), size=self.font_size)),
            ft.DataCell(ft.Text(str(pago.get("nombre_empleado", "")), size=self.font_size)),
            ft.DataCell(ft.Text(str(pago.get("fecha_pago", "")), size=self.font_size)),
            ft.DataCell(ft.Text(f"${valores['descuentos']:.2f}", size=self.font_size)),
            ft.DataCell(ft.Text(f"${valores['prestamos']:.2f}", size=self.font_size)),
            ft.DataCell(ft.Text(f"${valores['saldo']:.2f}", size=self.font_size)),
            ft.DataCell(
                ft.TextField(
                    value=str(valores.get("deposito", 0.0)),
                    text_align=ft.TextAlign.RIGHT,
                    width=85,
                    height=28,
                    content_padding=ft.padding.all(6),
                    text_size=self.font_size,
                    on_change=(lambda e: on_deposito_change(e.control.value)) if on_deposito_change else None,
                    on_blur=(lambda e: on_deposito_blur()) if on_deposito_blur else None,
                    on_submit=(lambda e: on_deposito_submit()) if on_deposito_submit else None,
                )
            ),
            ft.DataCell(ft.Text(f"${valores['efectivo']:.2f}", size=self.font_size)),
            ft.DataCell(ft.Text(f"${valores['total']:.2f}", size=self.font_size)),
            ft.DataCell(
                ft.Row(
                    [
                        ft.IconButton(icon=ft.icons.EDIT, tooltip="Editar descuentos", on_click=lambda e: on_editar_descuentos(pago)) if on_editar_descuentos else None,
                        ft.IconButton(icon=ft.icons.SAVINGS, tooltip="Editar préstamos", on_click=lambda e: on_editar_prestamos(pago)) if on_editar_prestamos else None,
                        ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN, tooltip="Confirmar", on_click=lambda e: on_confirmar(pago)) if on_confirmar else None,
                        ft.IconButton(icon=ft.icons.DELETE_OUTLINE, icon_color=ft.colors.RED, tooltip="Eliminar", on_click=lambda e: on_eliminar(pago)) if on_eliminar else None,
                    ],
                    spacing=4,
                )
            ),
            ft.DataCell(ft.Text(str(pago.get("estado", "")), size=self.font_size)),
        ]

        # Filtramos los None
        cells = [c for c in cells if c is not None]

        return ft.DataRow(cells=cells)

    # --------------------
    # FILA COMPACTA (EXPANSIBLE)
    # --------------------
    def build_row_compacto(self, pago: Dict[str, Any], valores: Dict[str, Any]) -> ft.DataRow:
        """
        Fila ultra compacta para tablas dentro de expansibles.
        """
        cells = [
            ft.DataCell(ft.Text(str(pago.get("id_pago_nomina") or pago.get("id_pago")), size=self.font_size)),
            ft.DataCell(ft.Text(str(pago.get("numero_nomina")), size=self.font_size)),
            ft.DataCell(ft.Text(str(pago.get("nombre_empleado", "")), size=self.font_size)),
            ft.DataCell(ft.Text(f"${valores['monto_base']:.2f}", size=self.font_size)),
            ft.DataCell(ft.Text(f"${valores['descuentos']:.2f}", size=self.font_size)),
            ft.DataCell(ft.Text(f"${valores['prestamos']:.2f}", size=self.font_size)),
            ft.DataCell(ft.Text(f"${valores['saldo']:.2f}", size=self.font_size)),
            ft.DataCell(ft.Text(f"${valores['efectivo']:.2f}", size=self.font_size)),
            ft.DataCell(ft.Text(f"${valores['total']:.2f}", size=self.font_size)),
        ]
        return ft.DataRow(cells=cells)
