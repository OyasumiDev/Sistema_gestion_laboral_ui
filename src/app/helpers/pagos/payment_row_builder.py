import flet as ft
from typing import Dict, Any, Callable, Optional


class PaymentRowBuilder:
    """
    Constructor de filas compactas para pagos.
    - Pendientes (edición): columnas deben calzar con COLUMNS_EDICION (16 columnas).
    - Confirmados (lectura/compacto): columnas deben calzar con COLUMNS_COMPACTAS_CONFIRMADO (11 columnas).
    - Usa las claves del motor PaymentViewMath: descuentos_view, prestamos_view, total_vista, saldo_ajuste, deposito, efectivo.
    """

    def __init__(self, font_size: int = 11):
        self.font_size = font_size

    # -------------------- utilidades --------------------
    def _t_money(self, v: Any) -> str:
        try:
            return f"${float(v):,.2f}"
        except Exception:
            return "$0.00"

    def _fmt2(self, v: Any) -> str:
        try:
            return f"{float(v or 0):.2f}"
        except Exception:
            return "0.00"

    def _nombre(self, pago: Dict[str, Any]) -> str:
        return str(
            pago.get("nombre_completo")
            or pago.get("nombre_empleado")
            or pago.get("nombre")
            or ""
        )

    # --------------------
    # FILA DE LECTURA (CONFIRMADOS)
    # Orden COLUMNS_COMPACTAS_CONFIRMADO:
    # id_pago, id_empleado, nombre, monto_base, descuentos, prestamos,
    # deposito, saldo, efectivo, total, estado
    # --------------------
    def build_row_lectura(self, pago: Dict[str, Any], valores: Dict[str, Any]) -> ft.DataRow:
        id_pago = int(pago.get("id_pago_nomina") or pago.get("id_pago") or 0)
        num = pago.get("numero_nomina", "")
        nombre = self._nombre(pago)

        monto_base = float(pago.get("monto_base") or valores.get("monto_base", 0.0) or 0.0)
        descuentos = valores.get("descuentos_view", 0.0)
        prestamos = valores.get("prestamos_view", 0.0)
        deposito = valores.get("deposito", pago.get("pago_deposito", 0.0))
        saldo = valores.get("saldo_ajuste", 0.0)
        efectivo = valores.get("efectivo", 0.0)
        total = valores.get("total_vista", 0.0)
        estado = str(pago.get("estado", ""))

        cells = [
            ft.DataCell(ft.Text(str(id_pago), size=self.font_size)),
            ft.DataCell(ft.Text(str(num), size=self.font_size)),
            ft.DataCell(ft.Text(nombre, size=self.font_size)),
            ft.DataCell(ft.Text(self._t_money(monto_base), size=self.font_size)),
            ft.DataCell(ft.Text(self._t_money(descuentos), size=self.font_size)),
            ft.DataCell(ft.Text(self._t_money(prestamos), size=self.font_size)),
            ft.DataCell(ft.Text(self._t_money(deposito), size=self.font_size)),
            ft.DataCell(ft.Text(self._t_money(saldo), size=self.font_size)),
            ft.DataCell(ft.Text(self._t_money(efectivo), size=self.font_size)),
            ft.DataCell(ft.Text(self._t_money(total), size=self.font_size)),
            ft.DataCell(ft.Text(estado, size=self.font_size)),
        ]
        row = ft.DataRow(cells=cells)
        row._id_pago = id_pago  # hint para refrescos
        return row

    # --------------------
    # FILA DE EDICIÓN (PENDIENTES)
    # Orden COLUMNS_EDICION:
    # id_pago, id_empleado, nombre, fecha_pago, horas, sueldo_hora, monto_base,
    # descuentos, prestamos, saldo, deposito(TF), efectivo, total, ediciones, acciones, estado
    # --------------------
    def build_row_edicion(
        self,
        pago: Dict[str, Any],
        valores: Dict[str, Any],
        *,
        on_editar_descuentos: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_editar_prestamos: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_confirmar: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_eliminar: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_deposito_change: Optional[Callable[[int, str], None]] = None,
        on_deposito_blur: Optional[Callable[[int], None]] = None,
        on_deposito_submit: Optional[Callable[[int], None]] = None,
    ) -> ft.DataRow:
        id_pago = int(pago.get("id_pago_nomina") or pago.get("id_pago") or 0)
        num = pago.get("numero_nomina", "")
        nombre = self._nombre(pago)

        fecha_pago = str(pago.get("fecha_pago", ""))

        horas = float(pago.get("horas") or 0.0)
        sueldo_hora = float(pago.get("sueldo_por_hora") or pago.get("sueldo_hora") or 0.0)
        monto_base = float(pago.get("monto_base") or 0.0)

        descuentos = valores.get("descuentos_view", 0.0)
        prestamos = valores.get("prestamos_view", 0.0)
        saldo = valores.get("saldo_ajuste", 0.0)
        deposito = valores.get("deposito", 0.0)
        efectivo = valores.get("efectivo", 0.0)
        total = valores.get("total_vista", 0.0)
        estado = str(pago.get("estado", "PENDIENTE") or "PENDIENTE")

        tf_deposito = ft.TextField(
            value=self._fmt2(deposito),
            text_align=ft.TextAlign.RIGHT,
            width=90,
            height=28,
            dense=True,
            text_size=self.font_size,
            content_padding=ft.padding.all(6),
            on_change=(lambda e, pid=id_pago: on_deposito_change(pid, e.control.value)) if on_deposito_change else None,
            on_blur=(lambda e, pid=id_pago: on_deposito_blur(pid)) if on_deposito_blur else None,
            on_submit=(lambda e, pid=id_pago: on_deposito_submit(pid)) if on_deposito_submit else None,
        )

        ediciones_row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.icons.REMOVE_CIRCLE_OUTLINE,
                    tooltip="Editar descuentos",
                    on_click=(lambda e, p=pago: on_editar_descuentos(p)) if on_editar_descuentos else None,
                    icon_color=ft.colors.AMBER_700,
                ),
                ft.IconButton(
                    icon=ft.icons.ACCOUNT_BALANCE_WALLET,
                    tooltip="Editar préstamos",
                    on_click=(lambda e, p=pago: on_editar_prestamos(p)) if on_editar_prestamos else None,
                    icon_color=ft.colors.BLUE_600,
                ),
            ],
            spacing=4,
        )

        acciones_row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.icons.CHECK,
                    tooltip="Confirmar pago",
                    icon_color=ft.colors.GREEN_600,
                    on_click=(lambda e, p=pago: on_confirmar(p)) if on_confirmar else None,
                ),
                ft.IconButton(
                    icon=ft.icons.DELETE_OUTLINE,
                    tooltip="Eliminar pago",
                    icon_color=ft.colors.RED_500,
                    on_click=(lambda e, p=pago: on_eliminar(p)) if on_eliminar else None,
                ),
            ],
            spacing=4,
        )

        cells = [
            ft.DataCell(ft.Text(str(id_pago), size=self.font_size)),                     # 0 id_pago
            ft.DataCell(ft.Text(str(num), size=self.font_size)),                        # 1 id_empleado
            ft.DataCell(ft.Text(nombre, size=self.font_size)),                          # 2 nombre
            ft.DataCell(ft.Text(fecha_pago, size=self.font_size)),                      # 3 fecha_pago
            ft.DataCell(ft.Text(f"{horas:.2f}", size=self.font_size)),                  # 4 horas
            ft.DataCell(ft.Text(self._t_money(sueldo_hora), size=self.font_size)),      # 5 sueldo_hora
            ft.DataCell(ft.Text(self._t_money(monto_base), size=self.font_size)),       # 6 monto_base
            ft.DataCell(ft.Text(self._t_money(descuentos), size=self.font_size)),       # 7 descuentos
            ft.DataCell(ft.Text(self._t_money(prestamos), size=self.font_size)),        # 8 prestamos
            ft.DataCell(ft.Text(self._t_money(saldo), size=self.font_size)),            # 9 saldo
            ft.DataCell(tf_deposito),                                                   # 10 depósito (editable)
            ft.DataCell(ft.Text(self._t_money(efectivo), size=self.font_size)),         # 11 efectivo
            ft.DataCell(ft.Text(self._t_money(total), size=self.font_size)),            # 12 total
            ft.DataCell(ediciones_row),                                                 # 13 ediciones
            ft.DataCell(acciones_row),                                                  # 14 acciones
            ft.DataCell(ft.Text(estado, size=self.font_size)),                          # 15 estado
        ]

        row = ft.DataRow(cells=cells)
        row._id_pago = id_pago  # hint para refrescos
        return row

    # --------------------
    # FILA COMPACTA (EXPANSIBLE CONFIRMADOS)
    # Mismo orden que lectura para mantener consistencia y facilitar sort.
    # --------------------
    def build_row_compacto(self, pago: Dict[str, Any], valores: Dict[str, Any]) -> ft.DataRow:
        id_pago = int(pago.get("id_pago_nomina") or pago.get("id_pago") or 0)
        num = pago.get("numero_nomina", "")
        nombre = self._nombre(pago)

        monto_base = float(pago.get("monto_base") or valores.get("monto_base", 0.0) or 0.0)
        descuentos = valores.get("descuentos_view", 0.0)
        prestamos = valores.get("prestamos_view", 0.0)
        deposito = valores.get("deposito", pago.get("pago_deposito", 0.0))
        saldo = valores.get("saldo_ajuste", 0.0)
        efectivo = valores.get("efectivo", 0.0)
        total = valores.get("total_vista", 0.0)
        estado = str(pago.get("estado", ""))

        cells = [
            ft.DataCell(ft.Text(str(id_pago), size=self.font_size)),
            ft.DataCell(ft.Text(str(num), size=self.font_size)),
            ft.DataCell(ft.Text(nombre, size=self.font_size)),
            ft.DataCell(ft.Text(self._t_money(monto_base), size=self.font_size)),
            ft.DataCell(ft.Text(self._t_money(descuentos), size=self.font_size)),
            ft.DataCell(ft.Text(self._t_money(prestamos), size=self.font_size)),
            ft.DataCell(ft.Text(self._t_money(deposito), size=self.font_size)),
            ft.DataCell(ft.Text(self._t_money(saldo), size=self.font_size)),
            ft.DataCell(ft.Text(self._t_money(efectivo), size=self.font_size)),
            ft.DataCell(ft.Text(self._t_money(total), size=self.font_size)),
            ft.DataCell(ft.Text(estado, size=self.font_size)),
        ]
        row = ft.DataRow(cells=cells)
        row._id_pago = id_pago  # hint para refrescos
        return row
