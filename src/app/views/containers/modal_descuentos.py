# app/views/containers/modal_descuentos.py
import flet as ft
from decimal import Decimal, InvalidOperation

from app.core.app_state import AppState
from app.models.discount_model import DiscountModel
from app.models.descuento_detalles_model import DescuentoDetallesModel
from app.models.payment_model import PaymentModel
from app.core.enums.e_payment_model import E_PAYMENT
from app.core.enums.e_prestamos_model import E_PRESTAMOS
from app.core.enums.e_discount_model import E_DISCOUNT


class ModalDescuentos(ft.AlertDialog):
    """
    Modal de descuentos:
    - Si el pago de nómina está 'pendiente' -> editar libremente y re-confirmar cuantas veces sea necesario.
    - Si el pago de nómina está 'pagado'     -> solo lectura.
    - 'Cancelar' guarda/actualiza BORRADOR (no afecta totales del pago).
    - 'Aceptar' aplica el borrador -> descuentos confirmados y actualiza el pago.
    """

    def __init__(self, pago_data: dict, on_confirmar=None):
        super().__init__(modal=True, title=ft.Text("Cargando..."), open=False)

        self.page = AppState().page
        self.pago_data = dict(pago_data or {})
        self.on_confirmar = on_confirmar

        # Espera keys: id_pago (== id_pago_nomina), numero_nomina
        self.id_pago = int(self.pago_data.get("id_pago"))
        self.numero_nomina = int(self.pago_data.get("numero_nomina"))

        # Modelos
        self.discount_model = DiscountModel()
        self.detalles_model = DescuentoDetallesModel()
        self.payment_model = PaymentModel()

        # Estado de pago
        self.pagado = not self._es_pago_pendiente()  # True => solo lectura SIEMPRE

        # ¿Hay confirmados? (solo para precargar la UI, ya NO bloquea edición)
        self.tiene_desc_confirmados = self.discount_model.tiene_descuentos_guardados(self.id_pago)

        # Controles UI
        self.aplicado_imss = ft.Checkbox(label="Aplicar IMSS", value=True, on_change=self._update_total)
        self.monto_imss = ft.TextField(label="Monto IMSS", value="50.0", width=200, on_change=self._update_total)

        self.aplicado_transporte = ft.Checkbox(label="Aplicar Transporte", value=False, on_change=self._update_total)
        self.monto_transporte = ft.TextField(
            label="Monto Transporte", value="0.0", width=200, visible=False, on_change=self._update_total
        )

        self.aplicado_extra = ft.Checkbox(label="Aplicar Descuento Extra", value=False, on_change=self._update_total)
        self.monto_extra = ft.TextField(label="Monto Extra", value="0.0", width=200, on_change=self._update_total)
        self.descripcion_extra = ft.TextField(
            label="Descripción Extra", multiline=True, expand=True, min_lines=2, max_lines=5
        )

        self.total_text = ft.Text(value="Total descuentos: $0.00", weight="bold", size=14)

        self.content = ft.Column(
            [
                ft.Text("Aplicar Descuentos", size=18, weight="bold"),
                ft.Row([self.aplicado_imss, self.monto_imss], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([self.aplicado_transporte, self.monto_transporte], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(),
                ft.Row([self.aplicado_extra, self.monto_extra], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                self.descripcion_extra,
                ft.Divider(),
                self.total_text,
            ],
            width=600,
            height=560,
            scroll=ft.ScrollMode.AUTO,
        )

        self.btn_cancelar = ft.TextButton("Cancelar", on_click=self._cancelar)
        # ✅ Se deshabilita SOLO si el pago ya está pagado
        self.btn_aceptar = ft.ElevatedButton("Aceptar", on_click=self._aceptar, disabled=self.pagado)
        self.actions = [self.btn_cancelar, self.btn_aceptar]

        # Cargar estado inicial (confirmados o borrador)
        self._set_titulo_empleado()
        self._cargar_estado_inicial()
        self._apply_readonly_if_needed()
        self._update_total()

    # ---------------- Public API ----------------
    def mostrar(self):
        # Usar page.dialog es más estable para modales
        if self.page:
            self.page.dialog = self
            self.open = True
            self.page.update()

    def close(self):
        self.open = False
        if self.page:
            self.page.update()

    # ---------------- Internos: datos ----------------
    def _set_titulo_empleado(self):
        nombre_empleado = self._obtener_nombre_empleado()
        self.title = ft.Text(f"Descuentos del trabajador: {nombre_empleado} (ID: {self.numero_nomina})")
        if self.page:
            self.page.update()

    def _obtener_nombre_empleado(self) -> str:
        try:
            q = """
                SELECT e.nombre_completo
                FROM empleados e
                JOIN pagos p ON p.numero_nomina = e.numero_nomina
                WHERE p.id_pago_nomina = %s
            """
            r = self.discount_model.db.get_data(q, (self.id_pago,), dictionary=True) or {}
            return r.get("nombre_completo", "Empleado desconocido")
        except Exception:
            return "Empleado desconocido"

    def _es_pago_pendiente(self) -> bool:
        try:
            rs = self.payment_model.get_by_id(self.id_pago) or {}
            data = rs.get("data") or {}
            estado = str(data.get(E_PAYMENT.ESTADO.value, "")).lower()
            return estado == "pendiente"
        except Exception:
            return False

    def _cargar_estado_inicial(self):
        """
        Si hay descuentos confirmados -> precargar la UI con esos valores.
        Si no -> cargar/crear borrador. En ambos casos, si el pago está 'pendiente', la UI queda editable.
        """
        if self.tiene_desc_confirmados:
            dlist = self.discount_model.get_descuentos_por_pago(self.id_pago) or []
            # Reset
            self.aplicado_imss.value = False; self.monto_imss.value = "0.0"
            self.aplicado_transporte.value = False; self.monto_transporte.value = "0.0"
            self.aplicado_extra.value = False; self.monto_extra.value = "0.0"
            self.descripcion_extra.value = ""
            for d in dlist:
                tipo = str(d.get(E_DISCOUNT.TIPO.value, ""))
                monto = float(d.get(E_DISCOUNT.MONTO_DESCUENTO.value, 0) or 0)
                if tipo == "retenciones_imss":
                    self.aplicado_imss.value = True; self.monto_imss.value = f"{monto:.2f}"
                elif tipo == "transporte":
                    self.aplicado_transporte.value = True; self.monto_transporte.value = f"{monto:.2f}"
                elif tipo == "descuento_extra":
                    self.aplicado_extra.value = True; self.monto_extra.value = f"{monto:.2f}"
                    self.descripcion_extra.value = d.get(E_DISCOUNT.DESCRIPCION.value) or ""
            self.monto_transporte.visible = self.aplicado_transporte.value
            return

        # Sin confirmados: traer/crear borrador
        det = self.detalles_model.obtener_por_id_pago(self.id_pago) or {}
        if det:
            self.aplicado_imss.value = bool(det.get(self.detalles_model.COL_APLICADO_IMSS, False))
            self.monto_imss.value = self._to_str(det.get(self.detalles_model.COL_MONTO_IMSS, "50.0"))

            self.aplicado_transporte.value = bool(det.get(self.detalles_model.COL_APLICADO_TRANSPORTE, False))
            self.monto_transporte.value = self._to_str(det.get(self.detalles_model.COL_MONTO_TRANSPORTE, "0.0"))
            self.monto_transporte.visible = self.aplicado_transporte.value

            self.aplicado_extra.value = bool(det.get(self.detalles_model.COL_APLICADO_EXTRA, False))
            self.monto_extra.value = self._to_str(det.get(self.detalles_model.COL_MONTO_EXTRA, "0.0"))
            self.descripcion_extra.value = det.get(self.detalles_model.COL_DESCRIPCION_EXTRA, "") or ""
        else:
            self.aplicado_imss.value = True;  self.monto_imss.value = "50.0"
            self.aplicado_transporte.value = False; self.monto_transporte.value = "0.0"; self.monto_transporte.visible = False
            self.aplicado_extra.value = False; self.monto_extra.value = "0.0"; self.descripcion_extra.value = ""

    # ---------------- Internos: UI / validación ----------------
    def _apply_readonly_if_needed(self):
        if not self.pagado:
            return
        # Solo lectura si el pago ya está pagado
        self.aplicado_imss.disabled = True;     self.monto_imss.read_only = True
        self.aplicado_transporte.disabled = True; self.monto_transporte.read_only = True
        self.aplicado_extra.disabled = True;    self.monto_extra.read_only = True
        self.descripcion_extra.read_only = True
        self.btn_aceptar.disabled = True
        if self.page:
            self.page.update()

    def _update_total(self, _=None):
        self.monto_transporte.visible = self.aplicado_transporte.value
        if self.page:
            self.page.update()

        total = Decimal("0.00")
        if self.aplicado_imss.value:
            total += self._parse_decimal(self.monto_imss.value)
        if self.aplicado_transporte.value:
            total += self._parse_decimal(self.monto_transporte.value)
        if self.aplicado_extra.value:
            total += self._parse_decimal(self.monto_extra.value)

        self.total_text.value = f"Total descuentos: ${total:.2f}"
        if self.page:
            self.page.update()

    @staticmethod
    def _parse_decimal(value) -> Decimal:
        try:
            return round(Decimal(str(value).replace(",", ".").strip()), 2)
        except (InvalidOperation, TypeError):
            return Decimal("0.00")

    @staticmethod
    def _to_str(v) -> str:
        try:
            if v is None or v == "":
                return "0.0"
            return f"{float(v):.2f}"
        except Exception:
            return "0.0"

    # ---------------- Acciones ----------------
    def _cancelar(self, _):
        # Guardar BORRADOR solo si el pago está pendiente
        if not self.pagado:
            self._guardar_borrador()
        self.close()

    def _aceptar(self, _):
        """
        Aplica el borrador a 'descuentos' (confirmados) y actualiza los totales del pago.
        Siempre permitido si el pago está 'pendiente'; si está 'pagado' solo cierra.
        """
        try:
            if self.pagado:
                self.close()
                return

            # 1) Guardar/actualizar borrador según UI
            self._guardar_borrador()

            # 2) Pasar borrador -> confirmados y limpiar borrador (idempotente)
            res = self.detalles_model.aplicar_a_descuentos_y_limpiar(self.id_pago, self.discount_model)
            if res.get("status") != "success":
                raise Exception(res.get("message", "Error al confirmar descuentos."))

            # 3) Recalcular y actualizar pago
            self._recalcular_y_actualizar_pago()

            # 4) Notificar al contenedor para refrescar la fila/tabla
            if self.on_confirmar:
                self.on_confirmar({"id_pago": self.id_pago})

            # 5) Cerrar (seguirá editable en próximas aperturas mientras el pago esté pendiente)
            self.close()
        except Exception as ex:
            print(f"❌ Error al confirmar descuentos: {ex}")
            self.close()

    # ---------------- Persistencia borrador / actualización pago ----------------
    def _borrador_payload(self) -> dict:
        return {
            self.detalles_model.COL_APLICADO_IMSS: bool(self.aplicado_imss.value),
            self.detalles_model.COL_MONTO_IMSS: float(self._parse_decimal(self.monto_imss.value))
            if self.aplicado_imss.value else None,

            self.detalles_model.COL_APLICADO_TRANSPORTE: bool(self.aplicado_transporte.value),
            self.detalles_model.COL_MONTO_TRANSPORTE: float(self._parse_decimal(self.monto_transporte.value))
            if self.aplicado_transporte.value else None,

            self.detalles_model.COL_APLICADO_EXTRA: bool(self.aplicado_extra.value),
            self.detalles_model.COL_MONTO_EXTRA: float(self._parse_decimal(self.monto_extra.value))
            if self.aplicado_extra.value else None,
            self.detalles_model.COL_DESCRIPCION_EXTRA: (self.descripcion_extra.value or "").strip() or None,
        }

    def _guardar_borrador(self):
        payload = self._borrador_payload()
        self.detalles_model.upsert_detalles(self.id_pago, payload)

    def _recalcular_y_actualizar_pago(self):
        rs = self.payment_model.get_by_id(self.id_pago) or {}
        data = rs.get("data") or {}
        if not data:
            return

        e = E_PAYMENT
        p = E_PRESTAMOS
        d = E_DISCOUNT

        monto_base = float(data.get(e.MONTO_BASE.value, 0) or 0)
        deposito = float(data.get(e.PAGO_DEPOSITO.value, 0) or 0)
        prestamos_total = float(data.get(p.PRESTAMO_MONTO.value, 0) or 0)

        total_desc = float(self.discount_model.get_total_descuentos_por_pago(self.id_pago) or 0)

        nuevo_total = max(0.0, monto_base - total_desc - prestamos_total)
        nuevo_efectivo = max(0.0, nuevo_total - deposito)

        self.payment_model.update_pago(
            self.id_pago,
            {
                e.MONTO_TOTAL.value: nuevo_total,
                d.MONTO_DESCUENTO.value: total_desc,
                e.PAGO_EFECTIVO.value: nuevo_efectivo,
            },
        )
