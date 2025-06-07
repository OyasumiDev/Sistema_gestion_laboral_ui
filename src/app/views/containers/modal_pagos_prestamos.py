import flet as ft
from datetime import datetime
from decimal import Decimal

from app.core.app_state import AppState
from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.employes_model import EmployesModel
from app.views.containers.modal_alert import ModalAlert
from app.core.enums.e_loan_payment_model import E_PAGOS_PRESTAMO


class ModalPrestamos:
    def __init__(self, pago_data: dict, on_confirmar):
        self.page = AppState().page
        self.pago_data = pago_data
        self.on_confirmar = on_confirmar
        self.numero_nomina = pago_data["numero_nomina"]
        self.estado_pago = pago_data.get("estado", "pendiente")
        self.puede_editar = self.estado_pago != "pagado"

        # Modelos
        self.loan_model = LoanModel()
        self.pago_model = LoanPaymentModel()
        self.empleado_model = EmployesModel()
        self.E = E_PAGOS_PRESTAMO

        # Empleado
        empleado = self.empleado_model.get_by_numero_nomina(self.numero_nomina)
        self.nombre_empleado = empleado.get("nombre_completo", "Desconocido")

        # Datos de préstamo
        self.id_prestamo = None
        self.pagos = []
        self.total_pagado = 0
        self.saldo_restante = 0

        # Widgets (inicializados aquí pero construidos en _construir_modal)
        self.interes_dropdown = None
        self.monto_input = None
        self.observaciones_input = None
        self.saldo_con_interes = ft.Text("-")
        self.resumen_text = ft.Text("")

        # Modal
        self.dialog = ft.AlertDialog(modal=True)

        # Cargar datos del préstamo y construir el modal
        self._cargar_datos()


    def mostrar(self):
        print(f"🟢 Mostrando ModalPrestamos para empleado {self.numero_nomina}")
        
        if not self._cargar_datos():
            print("🟥 No hay préstamo activo, no se muestra modal.")
            return

        if self.page and self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)

        self.dialog.open = True
        if self.page:
            self.page.update()


    def _cerrar(self, e=None):
        self.dialog.open = False
        self.page.update()

    def _cargar_datos(self) -> bool:
        prestamo = self.loan_model.get_prestamo_activo_por_empleado(self.numero_nomina)
        if not prestamo:
            ModalAlert.mostrar_info("Sin préstamo", f"No hay préstamo activo para {self.numero_nomina}")
            return False

        self.id_prestamo = prestamo["id_prestamo"]
        self.saldo_restante = float(prestamo["saldo_prestamo"])
        self.pagos = self.pago_model.get_by_prestamo(self.id_prestamo)["data"]
        self.total_pagado = sum(float(p["monto_pagado"]) for p in self.pagos)

        self._construir_modal()
        return True



    def _construir_modal(self):
        hoy = datetime.today().strftime("%Y-%m-%d")

        self.interes_dropdown = ft.Dropdown(
            label="Interés %",
            value="10",
            options=[ft.dropdown.Option("5"), ft.dropdown.Option("10"), ft.dropdown.Option("15")],
            disabled=not self.puede_editar,
            on_change=self._recalcular_montos if self.puede_editar else None,
            width=100
        )

        self.monto_input = ft.TextField(
            label="Monto a pagar",
            width=180,
            on_change=self._recalcular_montos if self.puede_editar else None,
            disabled=not self.puede_editar
        )

        self.observaciones_input = ft.TextField(
            label="Observaciones",
            hint_text="Descripción adicional (opcional)",
            multiline=True,
            min_lines=2,
            max_lines=3,
            disabled=not self.puede_editar
        )

        self.saldo_con_interes = ft.Text(value="Saldo + interés: -", weight=ft.FontWeight.BOLD)

        rows = []
        for p in self.pagos[-5:]:
            interes_aplicado = float(p["interes_aplicado"])
            saldo = float(p["saldo_restante"])
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(p["fecha_pago"])),
                ft.DataCell(ft.Text(f"${float(p['monto_pagado']):.2f}")),
                ft.DataCell(ft.Text(f"{p['interes_porcentaje']}%")),
                ft.DataCell(ft.Text(f"${interes_aplicado:.2f}")),
                ft.DataCell(ft.Text(f"${saldo:.2f}")),
            ]))

        tabla_historial = ft.DataTable(
            columns=[
                ft.DataColumn(label=ft.Text("Fecha")),
                ft.DataColumn(label=ft.Text("Monto")),
                ft.DataColumn(label=ft.Text("Interés")),
                ft.DataColumn(label=ft.Text("Aplicado")),
                ft.DataColumn(label=ft.Text("Saldo")),
            ],
            rows=rows,
            column_spacing=20,
            data_row_max_height=38
        )

        mensaje_solo_lectura = ft.Text(
            "Este pago ya fue confirmado. Solo lectura.",
            color=ft.colors.RED,
            weight=ft.FontWeight.BOLD
        ) if not self.puede_editar else ft.Container()

        resumen = ft.Text(
            self._obtener_resumen(),
            weight=ft.FontWeight.BOLD,
            size=14
        )

        acciones = ft.Row(
            [
                *( [ft.ElevatedButton("Registrar Pago", icon=ft.icons.CHECK, on_click=self._guardar_pago)] if self.puede_editar else [] ),
                ft.TextButton("Cancelar", on_click=self._cerrar)
            ],
            alignment=ft.MainAxisAlignment.END,
            spacing=20
        )

        self.dialog.content = ft.Container(
            padding=20,
            width=700,
            content=ft.Column(
                controls=[
                    ft.Text(
                        f"Pagos del préstamo de: {self.nombre_empleado} (ID: {self.numero_nomina})",
                        style=ft.TextThemeStyle.TITLE_MEDIUM
                    ),
                    mensaje_solo_lectura,
                    ft.Divider(),
                    ft.Text("Últimos pagos realizados", weight=ft.FontWeight.BOLD),
                    tabla_historial,
                    ft.Divider(),
                    ft.Text("Registrar nuevo pago", weight=ft.FontWeight.BOLD),
                    ft.Row([self.monto_input, self.interes_dropdown, self.saldo_con_interes], spacing=20),
                    self.observaciones_input,
                    resumen,
                    acciones
                ],
                spacing=15
            )
        )
        self._recalcular_montos()


    def _recalcular_montos(self, _=None):
        try:
            interes = int(self.interes_dropdown.value or "0")
            saldo_actual = Decimal(str(self.saldo_restante)).quantize(Decimal("0.01"))
            interes_aplicado = (saldo_actual * Decimal(interes) / 100).quantize(Decimal("0.01"))
            saldo_total = saldo_actual + interes_aplicado

            self.saldo_con_interes.value = f"Saldo + interés: ${saldo_total:.2f}"
        except Exception as ex:
            print(f"❌ Error al calcular interés: {ex}")
            self.saldo_con_interes.value = "-"

        self.resumen_text.value = self._obtener_resumen()
        self.page.update()


    def _obtener_resumen(self):
        return f"💰 Total pagado: ${self.total_pagado:.2f} | 💸 Total por pagar: ${self.saldo_restante:.2f}"

    def _guardar_pago(self, _):
        try:
            monto = Decimal(str(self.monto_input.value or "0")).quantize(Decimal("0.01"))
            interes = int(self.interes_dropdown.value)
            observaciones = self.observaciones_input.value.strip()

            saldo_decimal = Decimal(str(self.saldo_restante)).quantize(Decimal("0.01"))
            interes_aplicado = (saldo_decimal * Decimal(interes) / 100).quantize(Decimal("0.01"))
            saldo_total = (saldo_decimal + interes_aplicado).quantize(Decimal("0.01"))

            if monto <= 0:
                ModalAlert.mostrar_info("Error", "El monto debe ser mayor a 0.")
                return

            if monto > saldo_total:
                ModalAlert.mostrar_info("Advertencia", f"El monto no puede ser mayor al saldo con interés (${saldo_total})")
                return

            hoy = datetime.today().strftime("%Y-%m-%d")

            resultado = self.pago_model.add_payment(
                id_prestamo=self.id_prestamo,
                monto_pagado=float(monto),
                fecha_pago=hoy,
                fecha_generacion=hoy,
                interes_porcentaje=interes,
                fecha_real_pago=hoy,
                observaciones=observaciones
            )

            if resultado["status"] == "success":
                ModalAlert.mostrar_info("Éxito", resultado["message"])
                self.dialog.open = False
                self.on_confirmar(None)
            else:
                ModalAlert.mostrar_info("Error", resultado["message"])

        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"Error al registrar pago: {ex}")
        self.page.update()

