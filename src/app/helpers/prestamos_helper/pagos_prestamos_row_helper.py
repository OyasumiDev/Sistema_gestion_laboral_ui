import flet as ft
from typing import Callable
from app.core.enums.e_pagos_prestamos import E_PAGOS_PRESTAMO as E
from app.helpers.boton_factory import crear_boton_editar, crear_boton_eliminar


class PagosPrestamosRowHelper:
    def build_fila_pago(
        self,
        pago: dict,
        editable: bool,
        on_edit: Callable = None,
        on_delete: Callable = None
    ) -> ft.DataRow:
        """
        Construye una fila visual para un pago de préstamo.
        Si `editable` es True, se muestran botones de editar y eliminar.
        """

        acciones = []
        if editable:
            if on_edit:
                acciones.append(crear_boton_editar(lambda e: on_edit(pago)))
            if on_delete:
                acciones.append(crear_boton_eliminar(lambda e: on_delete(pago)))

        # Valores con parseo y fallback
        try:
            pago_id = pago.get(E.ID_PAGO_PRESTAMO.value, "-")
            fecha_gen = pago.get(E.PAGO_FECHA_PAGO.value, "-")
            fecha_real = pago.get(E.PAGO_FECHA_REAL.value, "-")
            monto_pagado = float(pago.get(E.PAGO_MONTO_PAGADO.value, 0))
            interes_aplicado = float(pago.get(E.PAGO_INTERES_APLICADO.value, 0))
            interes_porcentaje = pago.get(E.PAGO_INTERES_PORCENTAJE.value, "0")
            saldo_restante = float(pago.get(E.PAGO_SALDO_RESTANTE.value, 0))
            observaciones = pago.get(E.PAGO_OBSERVACIONES.value, "")
            saldo_con_interes = saldo_restante + interes_aplicado
        except Exception as ex:
            print(f"❌ Error al construir fila de pago: {ex}")
            monto_pagado = 0
            interes_aplicado = 0
            saldo_restante = 0
            saldo_con_interes = 0
            interes_porcentaje = "0"
            fecha_gen = fecha_real = "-"
            observaciones = "-"
            pago_id = "-"

        return ft.DataRow(cells=[
            ft.DataCell(ft.Text(str(pago_id))),
            ft.DataCell(ft.Text(str(fecha_gen))),
            ft.DataCell(ft.Text(str(fecha_real))),
            ft.DataCell(ft.Text(f"${monto_pagado:.2f}")),
            ft.DataCell(ft.Text(f"${saldo_restante:.2f}")),
            ft.DataCell(ft.Text(f"${saldo_con_interes:.2f}")),
            ft.DataCell(ft.Text(f"{interes_porcentaje}%")),
            ft.DataCell(ft.Text(str(observaciones))),
            ft.DataCell(ft.Row(acciones, spacing=5))
        ])


    def get_columnas(self) -> list:
        return [
            ft.DataColumn(ft.Text("ID")),
            ft.DataColumn(ft.Text("Fecha programada")),
            ft.DataColumn(ft.Text("Fecha real")),
            ft.DataColumn(ft.Text("Pagado")),
            ft.DataColumn(ft.Text("Saldo restante")),
            ft.DataColumn(ft.Text("Saldo + interés")),
            ft.DataColumn(ft.Text("Interés (%)")),
            ft.DataColumn(ft.Text("Observaciones")),
            ft.DataColumn(ft.Text("Acciones")),
        ]

