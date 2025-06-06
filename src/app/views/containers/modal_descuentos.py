import flet as ft
from decimal import Decimal
from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert
from app.models.discount_model import DiscountModel
from app.models.descuento_detalles_model import DescuentoDetallesModel

VALOR_DEFECTO_IMSS = 50.0
VALOR_DEFECTO_OTROS = 50.0


class ModalDescuentos:
    def __init__(self, pago: dict, on_confirmar):
        self.page = AppState().page
        self.pago = pago
        self.pagado = pago.get("estado") == "pagado"
        self.on_confirmar = on_confirmar
        self.discount_model = DiscountModel()
        self.detalles_model = DescuentoDetallesModel()

        # === Controles ===
        self.chk_imss = ft.Checkbox(label="Aplicar IMSS", disabled=self.pagado)
        self.input_imss = ft.TextField(width=100, keyboard_type=ft.KeyboardType.NUMBER, on_change=self._recalcular_total, disabled=self.pagado)

        self.chk_transporte = ft.Checkbox(label="Aplicar Transporte", on_change=self._toggle_transporte, disabled=self.pagado)
        self.input_transporte = ft.TextField(visible=False, width=100, keyboard_type=ft.KeyboardType.NUMBER, on_change=self._recalcular_total, disabled=self.pagado)

        self.chk_comida = ft.Checkbox(label="Aplicar Comida", on_change=self._toggle_comida, disabled=self.pagado)
        self.input_comida = ft.TextField(visible=False, width=100, keyboard_type=ft.KeyboardType.NUMBER, on_change=self._recalcular_total, disabled=self.pagado)

        self.chk_extra = ft.Checkbox(label="Aplicar Descuento Extra", on_change=self._toggle_extra, disabled=self.pagado)
        self.input_extra = ft.TextField(label="Monto Extra", value="", visible=False, width=100, keyboard_type=ft.KeyboardType.NUMBER, on_change=self._recalcular_total, disabled=self.pagado)
        self.input_motivo = ft.TextField(label="Motivo (opcional)", value="", visible=False, multiline=True, min_lines=1, max_lines=4, expand=True, disabled=self.pagado)

        self.total_display = ft.Text("Total: $0.00", weight=ft.FontWeight.BOLD)

        # === Diálogo ===
        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Descuentos para empleado #{self.pago['numero_nomina']}", size=20, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    self._row(self.chk_imss, self.input_imss),
                    self._row(self.chk_transporte, self.input_transporte),
                    self._row(self.chk_comida, self.input_comida),
                    self.chk_extra,
                    self.input_extra,
                    self.input_motivo,
                    self.total_display
                ], spacing=15),
                width=500,
                padding=25
            ),
            actions=self._build_actions(),
            on_dismiss=self._cerrar
        )

        self._cargar_detalles_guardados()
        self._recalcular_total()

    def _row(self, checkbox, inputfield):
        return ft.Row([checkbox, inputfield], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    def _toggle_transporte(self, e):
        self.input_transporte.visible = self.chk_transporte.value
        self._recalcular_total()
        self.page.update()

    def _toggle_comida(self, e):
        self.input_comida.visible = self.chk_comida.value
        self._recalcular_total()
        self.page.update()

    def _toggle_extra(self, e):
        self.input_extra.visible = self.chk_extra.value
        self.input_motivo.visible = self.chk_extra.value
        self._recalcular_total()
        self.page.update()

    def _recalcular_total(self, e=None):
        total = Decimal("0.00")
        try:
            if self.chk_imss.value:
                total += Decimal(self.input_imss.value or "0")
            if self.chk_transporte.value:
                total += Decimal(self.input_transporte.value or "0")
            if self.chk_comida.value:
                total += Decimal(self.input_comida.value or "0")
            if self.chk_extra.value:
                total += Decimal(self.input_extra.value or "0")
        except Exception:
            pass

        self.total_display.value = f"Total: ${total:.2f}"
        self.page.update()

    def mostrar(self):
        print("🔄 Mostrando modal de descuentos...")
        self._cargar_detalles_guardados()
        self._recalcular_total()
        if self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    def _cerrar(self, e=None):
        self.dialog.open = False
        self.page.update()

    def _build_actions(self):
        if self.pagado:
            return [ft.ElevatedButton("Cerrar", on_click=self._cerrar)]
        else:
            return [
                ft.TextButton("Cancelar", on_click=self._cerrar),
                ft.ElevatedButton("Confirmar", on_click=self._confirmar)
            ]

    def _confirmar(self, e):
        try:
            def parse_float(value):
                try:
                    return float(value.strip()) if value else 0.0
                except:
                    raise ValueError

            detalles = {
                "aplicar_imss": self.chk_imss.value,
                "monto_imss": parse_float(self.input_imss.value) if self.chk_imss.value else 0.0,
                "aplicar_transporte": self.chk_transporte.value,
                "monto_transporte": parse_float(self.input_transporte.value) if self.chk_transporte.value else 0.0,
                "aplicar_comida": self.chk_comida.value,
                "monto_comida": parse_float(self.input_comida.value) if self.chk_comida.value else 0.0,
                "aplicar_extra": self.chk_extra.value,
                "monto_extra": parse_float(self.input_extra.value) if self.chk_extra.value else 0.0,
                "descripcion_extra": self.input_motivo.value.strip() if self.chk_extra.value else ""
            }

            print(f"💾 Guardando detalles para el pago {self.pago['id_pago']}: {detalles}")
            resultado = self.detalles_model.guardar_detalles(
                id_pago=self.pago["id_pago"],
                detalles=detalles
            )
            print(f"📬 Resultado de guardado: {resultado}")

            self._cerrar()
            self.on_confirmar(detalles)

        except ValueError:
            ModalAlert.mostrar_info("Error", "Por favor revisa que todos los montos sean numéricos válidos.")

    def _cargar_detalles_guardados(self):
        print(f"🔍 Buscando detalles guardados para el pago {self.pago['id_pago']}")
        if not self.detalles_model.tiene_datos_para_pago(self.pago["id_pago"]):
            print("⚠️ No hay detalles guardados. Cargando predeterminados...")
            self.chk_imss.value = True
            self.input_imss.value = str(VALOR_DEFECTO_IMSS)
            self.chk_transporte.value = False
            self.input_transporte.value = str(VALOR_DEFECTO_OTROS)
            self.input_transporte.visible = False
            self.chk_comida.value = False
            self.input_comida.value = str(VALOR_DEFECTO_OTROS)
            self.input_comida.visible = False
            self.chk_extra.value = False
            self.input_extra.value = ""
            self.input_extra.visible = False
            self.input_motivo.value = ""
            self.input_motivo.visible = False
            self.page.update()
            return

        detalles = self.detalles_model.obtener_detalles(self.pago["id_pago"])
        print(f"✅ Detalles obtenidos: {detalles}")

        self.chk_imss.value = bool(detalles.get("aplicar_imss", False))
        self.input_imss.value = str(detalles.get("monto_imss", ""))

        self.chk_transporte.value = bool(detalles.get("aplicar_transporte", False))
        self.input_transporte.value = str(detalles.get("monto_transporte", ""))
        self.input_transporte.visible = self.chk_transporte.value

        self.chk_comida.value = bool(detalles.get("aplicar_comida", False))
        self.input_comida.value = str(detalles.get("monto_comida", ""))
        self.input_comida.visible = self.chk_comida.value

        self.chk_extra.value = bool(detalles.get("aplicar_extra", False))
        self.input_extra.value = str(detalles.get("monto_extra", ""))
        self.input_motivo.value = detalles.get("descripcion_extra", "")
        self.input_extra.visible = self.chk_extra.value
        self.input_motivo.visible = self.chk_extra.value

        self.page.update()
        self._recalcular_total()
