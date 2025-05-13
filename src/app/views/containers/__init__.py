from datetime import datetime
import pandas as pd
import flet as ft
from urllib.parse import urlparse, parse_qs
from decimal import Decimal

from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert
from app.models.loan_payment_model import LoanPaymentModel
from app.models.loan_model import LoanModel
from app.core.invokers.file_open_invoker import FileOpenInvoker
from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.core.enums.e_loan_payment_model import E_PAGOS_PRESTAMO
from app.core.enums.e_prestamos_model import E_PRESTAMOS


class PagosPrestamoContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20)
        self.page = AppState().page
        self.pago_model = LoanPaymentModel()
        self.prestamo_model = LoanModel()
        self.tabla_pagos = ft.DataTable(columns=[], rows=[], expand=True)

        self.orden_actual = "id_pago_prestamo"
        self.orden_desc = False
        self.interes_fijo = 10.0

        self.fila_resumen = None
        self.fila_nueva = None

        self.importador = FileOpenInvoker(
            page=self.page,
            on_select=self._procesar_importacion,
            allowed_extensions=["xlsx"]
        )
        self.exportador = FileSaveInvoker(
            page=self.page,
            on_save=self._guardar_exportacion,
            save_dialog_title="Guardar pagos en Excel",
            file_name="pagos_prestamo.xlsx",
            allowed_extensions=["xlsx"]
        )

        self.boton_agregar = self._boton_estilizado("Agregar", ft.icons.ADD, self._agregar_fila_pago)

        self.layout = ft.Column(
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[]
        )
        self.content = self.layout

        self.did_mount()

    def _crear_fila_nueva(self, monto_total, saldo_actual):
        hoy = datetime.today().strftime("%Y-%m-%d")
        nuevo_id = str(self.pago_model.get_next_id())

        interes_selector = ft.Dropdown(
            label="Interés %",
            value="10",
            options=[
                ft.dropdown.Option("5"),
                ft.dropdown.Option("10"),
                ft.dropdown.Option("15")
            ],
            width=80
        )

        monto_input = ft.TextField(label="Monto a Pagar", value="", width=100)
        observaciones_input = ft.TextField(label="Observaciones", value="", width=160)

        saldo_actual_decimal = Decimal(str(saldo_actual))
        saldo_con_interes_text = ft.Text(value="-", width=100)

        def actualizar_interes(e):
            try:
                interes = int(interes_selector.value)
                interes_aplicado = saldo_actual_decimal * Decimal(interes) / 100
                nuevo_saldo = saldo_actual_decimal + interes_aplicado
                saldo_con_interes_text.value = f"${nuevo_saldo:.2f}"
            except:
                saldo_con_interes_text.value = "-"
            self.page.update()

        interes_selector.on_change = actualizar_interes
        actualizar_interes(None)

        def confirmar_pago():
            try:
                monto = float(monto_input.value.strip())
                interes = int(interes_selector.value)
                if monto <= 0:
                    raise ValueError("Monto inválido")

                resultado = self.pago_model.add_payment(
                    id_prestamo=int(self.id_prestamo),
                    monto_pagado=monto,
                    fecha_pago=hoy,
                    fecha_generacion=hoy,
                    interes_porcentaje=interes,
                    fecha_real_pago=hoy,
                    observaciones=observaciones_input.value.strip()
                )

                ModalAlert.mostrar_info("Resultado", resultado["message"])
                self._cargar_pagos(int(self.id_prestamo))

            except Exception as ex:
                ModalAlert.mostrar_info("Error", f"Fallo al registrar pago: {str(ex)}")

        return ft.DataRow(cells=[
            ft.DataCell(ft.Text(nuevo_id)),
            ft.DataCell(ft.Text(hoy)),
            ft.DataCell(ft.Text(hoy)),
            ft.DataCell(monto_input),
            ft.DataCell(ft.Text(f"${monto_total:.2f}")),
            ft.DataCell(ft.Text(f"${saldo_actual:.2f}")),
            ft.DataCell(saldo_con_interes_text),
            ft.DataCell(interes_selector),
            ft.DataCell(observaciones_input),
            ft.DataCell(ft.Row([
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, on_click=lambda _: confirmar_pago()),
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600, on_click=lambda _: self._cargar_pagos(int(self.id_prestamo)))
            ]))
        ])
