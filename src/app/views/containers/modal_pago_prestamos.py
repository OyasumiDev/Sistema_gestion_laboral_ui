import flet as ft
from datetime import datetime
from decimal import Decimal
from app.core.app_state import AppState
from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.prestamo_detalles_model import PrestamoDetallesModel
from app.views.containers.modal_alert import ModalAlert


class ModalPagoPrestamo:
    def __init__(self, pago: dict, on_success=None):
        self.page = AppState().page
        self.pago = pago
        self.pagado = pago.get("estado") == "pagado"
        self.numero_nomina = pago["numero_nomina"]
        self.id_pago = pago["id_pago"]
        self.on_success = on_success

        self.loan_model = LoanModel()
        self.payment_model = LoanPaymentModel()
        self.detalles_model = PrestamoDetallesModel()

    def mostrar(self):
        try:
            prestamo = self.loan_model.get_prestamo_activo_por_empleado(self.numero_nomina)
            if not prestamo:
                ModalAlert.mostrar_info("Sin préstamo", "El empleado no tiene préstamos activos.")
                return

            self.id_pago_prestamo = prestamo["id_prestamo"]
            self.monto_total = Decimal(prestamo["monto"])
            self.saldo = Decimal(prestamo["saldo"])
            self.interes = int(prestamo["interes"])
            self.hoy = datetime.today().strftime("%Y-%m-%d")

            # === Controles ===
            self.input_monto = ft.TextField(label="Monto a pagar", value="", width=150,
                                            on_change=self._actualizar_total, disabled=self.pagado)
            self.input_observaciones = ft.TextField(label="Observaciones (opcional)", value="",
                                                    width=250, disabled=self.pagado)
            self.total_con_interes_text = ft.Text(value="", weight="bold")

            self.dialogo = ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Préstamo #{self.id_pago_prestamo} para empleado {self.numero_nomina}"),
                content=ft.Column([
                    ft.Text(f"💳 Monto del préstamo: ${self.monto_total:.2f}"),
                    ft.Text(f"💸 Saldo restante: ${self.saldo:.2f}"),
                    ft.Text(f"📈 Interés aplicado: {self.interes}%"),
                    self.input_monto,
                    self.input_observaciones,
                    self.total_con_interes_text
                ], tight=True),
                actions=self._build_actions(),
                actions_alignment=ft.MainAxisAlignment.END,
                on_dismiss=self._cerrar
            )

            self._cargar_detalles_guardados()
            self._actualizar_total()
            if self.dialogo not in self.page.overlay:
                self.page.overlay.append(self.dialogo)
            self.dialogo.open = True
            self.page.update()

        except Exception as ex:
            ModalAlert.mostrar_info("Error interno", str(ex))

    def _build_actions(self):
        if self.pagado:
            return [ft.ElevatedButton("Cerrar", on_click=self._cerrar)]
        else:
            return [
                ft.TextButton("Cancelar", on_click=self._cerrar),
                ft.ElevatedButton("Confirmar", on_click=self._confirmar_pago)
            ]

    def _actualizar_total(self, e=None):
        try:
            val = Decimal(self.input_monto.value.strip())
            interes_monto = (self.saldo * Decimal(self.interes) / 100).quantize(Decimal("0.01"))
            nuevo_saldo = (self.saldo + interes_monto - val).quantize(Decimal("0.01"))
            self.total_con_interes_text.value = f"🔮 Total con interés: ${self.saldo + interes_monto:.2f} → Nuevo saldo: ${nuevo_saldo:.2f}"
        except:
            self.total_con_interes_text.value = "🔮 Ingrese un monto válido"
        self.page.update()

    def _confirmar_pago(self, e=None):
        try:
            if not self.input_monto.value.strip():
                raise ValueError("Ingrese un monto válido.")

            monto = Decimal(self.input_monto.value.strip())
            if monto <= 0:
                raise ValueError("El monto debe ser mayor a cero.")

            resultado = self.detalles_model.guardar_detalle(
                id_pago=self.id_pago,
                id_pago_prestamo=self.id_pago_prestamo,
                monto_pagado=monto,
                interes_aplicado=self.interes,
                fecha_pago=self.hoy,
                desde_nomina=True,
                observaciones=self.input_observaciones.value.strip()
            )

            ModalAlert.mostrar_info("Resultado", resultado["message"])
            self._cerrar()
            if self.on_success:
                self.on_success()

        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"Error al registrar pago: {ex}")

    def _cargar_detalles_guardados(self):
        print(f"🔍 Buscando detalles guardados para pago #{self.id_pago} y préstamo #{self.id_pago_prestamo}")
        detalle = self.detalles_model.obtener_detalle(self.id_pago, self.id_pago_prestamo)
        if detalle:
            print(f"✅ Detalles encontrados: {detalle}")
            self.input_monto.value = str(detalle.get("monto_pagado", ""))
            self.input_observaciones.value = detalle.get("observaciones", "")
        else:
            print("⚠️ No hay detalles previos. Cargando valores predeterminados.")
            self.input_monto.value = ""
            self.input_observaciones.value = ""
        self.page.update()

    def _cerrar(self, e=None):
        self.dialogo.open = False
        self.page.update()

