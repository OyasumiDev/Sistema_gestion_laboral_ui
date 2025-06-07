import flet as ft
from datetime import datetime
from decimal import Decimal

from app.core.app_state import AppState
from app.models.loan_model import LoanModel
from app.models.detalles_pagos_prestamo_model import DetallesPagosPrestamoModel
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
        self.id_pago = pago_data["id_pago"]
        self.estado_pago = pago_data.get("estado", "pendiente")

        self.loan_model = LoanModel()
        self.pago_model = LoanPaymentModel()
        self.detalles_model = DetallesPagosPrestamoModel()
        self.empleado_model = EmployesModel()
        self.E = E_PAGOS_PRESTAMO

        empleado = self.empleado_model.get_by_numero_nomina(self.numero_nomina)
        self.nombre_empleado = empleado.get("nombre_completo", "Desconocido")

        self.id_prestamo = None
        self.prestamos_disponibles = []
        self.pagos = []
        self.total_pagado = 0
        self.saldo_restante = 0

        self.dialog = ft.AlertDialog(modal=True)
        self.interes_dropdown = None
        self.monto_input = None
        self.observaciones_input = None
        self.saldo_con_interes = ft.Text("-")
        self.resumen_text = ft.Text("")
        self.prestamo_dropdown = None
        self.puede_editar = False

        self.detalle_guardado = None
        self._cargar_datos()

    def mostrar(self):
        if self.page and self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    def _cerrar(self, e=None):
        self.dialog.open = False
        self.page.update()

    def _cargar_datos(self):
        self.prestamos_disponibles = self.loan_model.get_prestamos_por_empleado(self.numero_nomina)

        if self.prestamos_disponibles:
            for p in self.prestamos_disponibles:
                detalle = self.detalles_model.get_detalle(self.id_pago, p["id_prestamo"])
                if detalle:
                    self.detalle_guardado = detalle
                    self.id_prestamo = p["id_prestamo"]
                    break
            if not self.id_prestamo:
                self.id_prestamo = self.prestamos_disponibles[0]["id_prestamo"]
        else:
            ModalAlert.mostrar_info("Sin préstamo", f"No hay préstamos registrados para {self.numero_nomina}")
            return

        self._set_prestamo(self.id_prestamo)


    def _set_prestamo(self, id_prestamo: int):
        self.id_prestamo = id_prestamo
        prestamo = next((p for p in self.prestamos_disponibles if p["id_prestamo"] == id_prestamo), None)
        if not prestamo:
            ModalAlert.mostrar_info("Error", "No se encontró el préstamo seleccionado.")
            return

        self.saldo_restante = float(prestamo["saldo_prestamo"])
        self.pagos = self.pago_model.get_by_prestamo(self.id_prestamo)["data"]
        self.total_pagado = sum(float(p["monto_pagado"]) for p in self.pagos)

        existe = self.pago_model.existe_pago_pendiente_para_pago_nomina(
            id_pago_nomina=self.id_pago,
            id_prestamo=self.id_prestamo
        )

        self.puede_editar = self.estado_pago != "pagado" and self.saldo_restante > 0 and not existe
        self._construir_modal()

        if self.detalle_guardado:
            self.monto_input.value = str(self.detalle_guardado["monto_guardado"])
            self.observaciones_input.value = self.detalle_guardado["observaciones"] or ""
            self.interes_dropdown.value = str(self.detalle_guardado["interes_guardado"])

        self.resumen_text.value = self._obtener_resumen()
        self._recalcular_montos()
        self.page.update()

    def _construir_modal(self):
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
            on_change=self._recalcular_montos,
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

        self.prestamo_dropdown = ft.Dropdown(
            label="Préstamo seleccionado" if not self.puede_editar else "Seleccionar préstamo",
            value=str(self.id_prestamo),
            options=[
                ft.dropdown.Option(str(self.id_prestamo), f"ID {self.id_prestamo} - Saldo: ${float(self.saldo_restante):.2f}")
            ] if not self.puede_editar else [
                ft.dropdown.Option(str(p["id_prestamo"]), f"ID {p['id_prestamo']} - Saldo: ${float(p['saldo_prestamo']):.2f}")
                for p in self.prestamos_disponibles
            ],
            on_change=(None if not self.puede_editar else lambda e: self._set_prestamo(int(e.control.value))),
            disabled=not self.puede_editar,
            width=350
        )

        mensaje_solo_lectura = ft.Text(
            "Este pago ya fue confirmado o ya hay un pago pendiente para este préstamo.",
            color=ft.colors.RED,
            weight=ft.FontWeight.BOLD
        ) if not self.puede_editar else ft.Container()

        self.boton_guardar = ft.ElevatedButton("Guardar Detalle", icon=ft.icons.SAVE, on_click=self._guardar_detalle)

        acciones = ft.Row(
            [
                *( [self.boton_guardar] if self.puede_editar else [] ),
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
                    ft.Text(f"Pagos del préstamo de: {self.nombre_empleado} (ID: {self.numero_nomina})", style=ft.TextThemeStyle.TITLE_MEDIUM),
                    mensaje_solo_lectura,
                    self.prestamo_dropdown,
                    ft.Divider(),
                    ft.Text("Últimos pagos realizados", weight=ft.FontWeight.BOLD),
                    tabla_historial,
                    ft.Divider(),
                    ft.Text("Registrar nuevo pago", weight=ft.FontWeight.BOLD),
                    ft.Row([self.monto_input, self.interes_dropdown, self.saldo_con_interes], spacing=20),
                    self.observaciones_input,
                    self.resumen_text,
                    acciones
                ],
                spacing=15
            )
        )


    def _recalcular_montos(self, _=None):
        try:
            interes = int(self.interes_dropdown.value or "0")
            saldo_actual = Decimal(str(self.saldo_restante)).quantize(Decimal("0.01"))
            interes_aplicado = (saldo_actual * Decimal(interes) / 100).quantize(Decimal("0.01"))
            saldo_total = saldo_actual + interes_aplicado

            self.saldo_con_interes.value = f"Saldo + interés: ${saldo_total:.2f}"

            monto_valido = False
            try:
                monto = Decimal(str(self.monto_input.value)).quantize(Decimal("0.01"))
                total_por_pagar = saldo_total - monto

                if monto <= 0 or monto > saldo_total or total_por_pagar < 0:
                    self.monto_input.border_color = ft.colors.RED
                else:
                    self.monto_input.border_color = ft.colors.GREEN
                    monto_valido = True

            except:
                self.monto_input.border_color = ft.colors.RED

            if self.boton_guardar:
                self.boton_guardar.disabled = not monto_valido

        except Exception as ex:
            print(f"❌ Error al calcular interés: {ex}")
            self.saldo_con_interes.value = "-"
            self.monto_input.border_color = ft.colors.RED
            if self.boton_guardar:
                self.boton_guardar.disabled = True

        self.resumen_text.value = self._obtener_resumen()
        self.page.update()


    def _obtener_resumen(self):
        try:
            interes = int(self.interes_dropdown.value or "0")
            saldo = Decimal(str(self.saldo_restante))
            interes_aplicado = (saldo * Decimal(interes) / 100).quantize(Decimal("0.01"))
            saldo_total = saldo + interes_aplicado

            monto_ingresado = Decimal(self.monto_input.value or "0").quantize(Decimal("0.01"))
            total_pagado = self.total_pagado + monto_ingresado
            total_por_pagar = saldo_total - monto_ingresado

            return f"💰 Total pagado: ${total_pagado:.2f} | 💸 Total por pagar: ${total_por_pagar:.2f}"
        except:
            return f"💰 Total pagado: ${self.total_pagado:.2f} | 💸 Total por pagar: ---"

    def _guardar_detalle(self, _):
        try:
            monto = Decimal(str(self.monto_input.value or "0")).quantize(Decimal("0.01"))
            interes = int(self.interes_dropdown.value)
            observaciones = self.observaciones_input.value.strip()

            saldo_decimal = Decimal(str(self.saldo_restante)).quantize(Decimal("0.01"))
            interes_aplicado = (saldo_decimal * Decimal(interes) / 100).quantize(Decimal("0.01"))
            saldo_total = (saldo_decimal + interes_aplicado).quantize(Decimal("0.01"))

            total_por_pagar = saldo_total - monto
            if monto <= 0:
                ModalAlert.mostrar_info("Error", "El monto debe ser mayor a 0.")
                return

            if monto > saldo_total:
                ModalAlert.mostrar_info("Advertencia", f"El monto no puede ser mayor al saldo con interés (${saldo_total})")
                return

            if total_por_pagar < 0:
                ModalAlert.mostrar_info("Error", "El total por pagar no puede quedar negativo.")
                return

            if self.detalle_guardado:
                if (float(self.detalle_guardado["monto_guardado"]) == float(monto) and
                    int(self.detalle_guardado["interes_guardado"]) == interes and
                    (self.detalle_guardado["observaciones"] or "") == observaciones):
                    ModalAlert.mostrar_info("Sin cambios", "No se detectaron cambios en el detalle.")
                    return

            resultado = self.detalles_model.upsert_detalle(
                id_pago=self.id_pago,
                id_prestamo=self.id_prestamo,
                monto=float(monto),
                interes=interes,
                observaciones=observaciones
            )

            if resultado["status"] == "success":
                ModalAlert.mostrar_info("Guardado", "El detalle fue almacenado correctamente.")
                self.dialog.open = False
                self.on_confirmar(None)
            else:
                ModalAlert.mostrar_info("Error", resultado["message"])

        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"Error al guardar detalle: {ex}")

        self.page.update()