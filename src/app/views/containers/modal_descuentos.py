import flet as ft
from decimal import Decimal, InvalidOperation
from app.core.app_state import AppState
from app.models.discount_model import DiscountModel
from app.models.descuento_detalles_model import DescuentoDetallesModel
from app.models.payment_model import PaymentModel

class ModalDescuentos(ft.AlertDialog):
    def __init__(self, pago_data: dict, on_confirmar):
        super().__init__(
            modal=True,
            title=ft.Text("Cargando..."),
            open=False
        )

        self.page = AppState().page
        self.pago_data = pago_data
        self.on_confirmar = on_confirmar
        self.id_pago = pago_data["id_pago"]
        self.numero_nomina = pago_data["numero_nomina"]

        self.discount_model = DiscountModel()
        self.detalles_model = DescuentoDetallesModel()
        self.payment_model = PaymentModel()

        self.pagado = not self.es_pago_editable()

        self.aplicado_imss = ft.Checkbox(label="Aplicar IMSS", value=True, on_change=self._update_total)
        self.aplicado_transporte = ft.Checkbox(label="Aplicar Transporte", value=False, on_change=self._update_total)
        self.aplicado_comida = ft.Checkbox(label="Aplicar Comida", value=False, on_change=self._update_total)

        self.monto_imss = ft.TextField(label="Monto IMSS", value="50.0", width=200, on_change=self._update_total)
        self.monto_transporte = ft.TextField(label="Monto Transporte", value="0.0", width=200, visible=False, on_change=self._update_total)
        self.monto_comida = ft.TextField(label="Monto Comida", value="0.0", width=200, visible=False, on_change=self._update_total)
        self.monto_extra = ft.TextField(label="Monto Extra", value="0.0", width=200, on_change=self._update_total)
        self.descripcion_extra = ft.TextField(label="Descripción Extra", multiline=True, expand=True, min_lines=2, max_lines=5)

        self.total_text = ft.Text(value="Total descuentos: $0.00", weight="bold", size=14)

        self.content = ft.Column([
            ft.Text("Aplicar Descuentos", size=18, weight="bold"),
            ft.Row([self.aplicado_imss, self.monto_imss], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([self.aplicado_transporte, self.monto_transporte], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([self.aplicado_comida, self.monto_comida], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),
            ft.Row([self.monto_extra], alignment=ft.MainAxisAlignment.START),
            self.descripcion_extra,
            ft.Divider(),
            self.total_text
        ], width=600, height=580, scroll=ft.ScrollMode.AUTO)

        self.actions = [
            ft.TextButton("Cancelar", on_click=lambda _: self.close()),
            ft.ElevatedButton("Aceptar", on_click=self._guardar_datos, disabled=self.pagado)
        ]

        self._datos_guardados = self._cargar_datos_guardados()

        if self.pagado:
            self._bloquear_inputs()

        if self._datos_guardados:
            self._aplicar_datos_guardados(self._datos_guardados)

        self._set_titulo_empleado()

    def _set_titulo_empleado(self):
        nombre_empleado = self.obtener_nombre_empleado()
        self.title = ft.Text(f"Descuentos del trabajador: {nombre_empleado} (ID: {self.numero_nomina})")
        if self.page:
            self.page.update()

    def close(self):
        self.open = False
        if self.page:
            self.page.update()

    def mostrar(self):
        print(f"🟢 Mostrando ModalDescuentos para ID: {self.id_pago}")
        if self.page and self not in self.page.overlay:
            self.page.overlay.append(self)
        self.open = True
        if self.page:
            self.page.update()
        self._update_total()

    def obtener_nombre_empleado(self) -> str:
        try:
            query = """
                SELECT e.nombre_completo
                FROM empleados e
                JOIN pagos p ON p.numero_nomina = e.numero_nomina
                WHERE p.id_pago = %s
            """
            result = self.discount_model.db.get_data(query, (self.id_pago,), dictionary=True)
            return result.get("nombre_completo", "Empleado desconocido")
        except Exception as e:
            print(f"❌ Error al obtener nombre del empleado: {e}")
            return "Empleado desconocido"

    def es_pago_editable(self) -> bool:
        try:
            result = self.payment_model.get_by_id(self.id_pago)
            return result.get("data", {}).get("estado") == "pendiente"
        except Exception:
            return False

    def _cargar_datos_guardados(self):
        datos = self.detalles_model.obtener_por_id_pago(self.id_pago)
        if datos:
            print(f"✅ Datos de descuentos cargados: {datos}")
        else:
            print(f"ℹ️ No hay datos previos de descuentos para el pago ID {self.id_pago}")
        return datos

    def _aplicar_datos_guardados(self, datos):
        self.aplicado_imss.value = bool(datos.get("aplicado_imss", False))
        self.monto_imss.value = str(datos.get("monto_imss", "50.0"))

        self.aplicado_transporte.value = bool(datos.get("aplicado_transporte", False))
        self.monto_transporte.value = str(datos.get("monto_transporte", "0.0"))
        self.monto_transporte.visible = self.aplicado_transporte.value

        self.aplicado_comida.value = bool(datos.get("aplicado_comida", False))
        self.monto_comida.value = str(datos.get("monto_comida", "0.0"))
        self.monto_comida.visible = self.aplicado_comida.value

        self.monto_extra.value = str(datos.get("monto_extra", "0.0"))
        self.descripcion_extra.value = datos.get("descripcion_extra", "")

        self._update_total()

    def _update_total(self, _=None):
        self.monto_transporte.visible = self.aplicado_transporte.value
        self.monto_comida.visible = self.aplicado_comida.value
        if self.page:
            self.page.update()

        total = Decimal("0.0")
        if self.aplicado_imss.value:
            total += self._parse_decimal(self.monto_imss.value)
        if self.aplicado_transporte.value:
            total += self._parse_decimal(self.monto_transporte.value)
        if self.aplicado_comida.value:
            total += self._parse_decimal(self.monto_comida.value)
        total += self._parse_decimal(self.monto_extra.value)

        self.total_text.value = f"Total descuentos: ${total:.2f}"
        if self.page:
            self.page.update()

    def _parse_decimal(self, value):
        try:
            return round(Decimal(str(value).replace(',', '.').strip()), 2)
        except InvalidOperation:
            return Decimal("0.0")

    def _guardar_datos(self, _):
        detalles = {
            "aplicado_imss": self.aplicado_imss.value,
            "monto_imss": self._parse_decimal(self.monto_imss.value) if self.aplicado_imss.value else 0.0,
            "aplicado_transporte": self.aplicado_transporte.value,
            "monto_transporte": self._parse_decimal(self.monto_transporte.value) if self.aplicado_transporte.value else 0.0,
            "aplicado_comida": self.aplicado_comida.value,
            "monto_comida": self._parse_decimal(self.monto_comida.value) if self.aplicado_comida.value else 0.0,
            "aplicado_extra": bool(self.monto_extra.value.strip()) or bool(self.descripcion_extra.value.strip()),
            "monto_extra": self._parse_decimal(self.monto_extra.value),
            "descripcion_extra": self.descripcion_extra.value.strip()
        }

        self.discount_model.guardar_descuentos_completos(
            id_pago=self.id_pago,
            numero_nomina=self.numero_nomina,
            aplicar_imss=detalles["aplicado_imss"],
            monto_imss=detalles["monto_imss"],
            aplicar_transporte=detalles["aplicado_transporte"],
            monto_transporte=detalles["monto_transporte"],
            aplicar_comida=detalles["aplicado_comida"],
            monto_comida=detalles["monto_comida"],
            aplicar_extra=detalles["aplicado_extra"],
            monto_extra=detalles["monto_extra"],
            descripcion_extra=detalles["descripcion_extra"]
        )

        self.detalles_model.guardar_o_actualizar_detalles(self.id_pago, detalles)

        if self.on_confirmar:
            self.on_confirmar(detalles)
        self.close()

    def _bloquear_inputs(self):
        self.aplicado_imss.disabled = True
        self.aplicado_transporte.disabled = True
        self.aplicado_comida.disabled = True
        self.monto_imss.read_only = True
        self.monto_transporte.read_only = True
        self.monto_comida.read_only = True
        self.monto_extra.read_only = True
        self.descripcion_extra.read_only = True
