from __future__ import annotations

from typing import Any, Callable, Dict, Optional

import flet as ft

from app.core.app_state import AppState
from app.models.discount_model import DiscountModel
from app.models.payment_model import PaymentModel
from app.models.descuento_detalles_model import DescuentoDetallesModel


class ModalDescuentos(ft.AlertDialog):
    """
    Modal para editar descuentos (IMSS / Transporte / Extra).

    Regla de oro:
    - Este modal SOLO guarda BORRADOR en `descuento_detalles`.
    - NO aplica descuentos definitivos en tabla `descuentos`.
    - NO depende de PaymentModel para recalcular (tu PaymentModel no tiene esos métodos).
    - El container es quien reconstruye la fila/tabla (leyendo descuento_detalles).

    Compatibilidad:
    - Tu container llama: ModalDescuentos(...).mostrar()
      => este módulo expone .mostrar() sin args y también .mostrar(page).
    """

    def __init__(
        self,
        pago_data: Dict[str, Any],
        *,
        modo: str = "pendiente",
        on_confirmar: Optional[Callable[[Dict[str, Any]], None]] = None,
        initial_state: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()

        self.pago: Dict[str, Any] = pago_data or {}
        self.modo = str(modo or "pendiente").strip().lower()
        self.on_confirmar = on_confirmar
        self.initial_state = initial_state or {}

        self.page: Optional[ft.Page] = None  # se setea en mostrar()
        self.detalles_model = DescuentoDetallesModel()
        self.discount_model = DiscountModel()
        self.payment_model = PaymentModel()

        self._editable = self._is_editable()

        # --------- Controles UI ----------
        self._chk_imss = ft.Checkbox(label="IMSS", value=False, disabled=not self._editable)
        self._tf_imss = ft.TextField(
            label="Monto IMSS",
            width=170,
            disabled=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        self._chk_transporte = ft.Checkbox(label="Transporte", value=False, disabled=not self._editable)
        self._tf_transporte = ft.TextField(
            label="Monto Transporte",
            width=170,
            disabled=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        self._chk_extra = ft.Checkbox(label="Extra", value=False, disabled=not self._editable)
        self._tf_extra_desc = ft.TextField(
            label="Descripción extra",
            width=270,
            disabled=True,
        )
        self._tf_extra_monto = ft.TextField(
            label="Monto extra",
            width=170,
            disabled=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        self._txt_resumen = ft.Text("", selectable=False)

        # Dialog base
        self.modal = True
        self.open = False
        self.title = ft.Text("Descuentos")
        self.content = self._build_content()
        self.actions = self._build_actions()

        # Cargar estado inicial
        self._cargar_estado_inicial()

        # wire + resumen
        self._wire_events()
        self._sync_enabled_fields()
        self._refresh_resumen()

    # ----------------------------
    # Public API
    # ----------------------------
    def mostrar(self, page: Optional[ft.Page] = None) -> None:
        """Abre el modal. Si no pasas page, usa AppState().page."""
        self.page = page or getattr(AppState(), "page", None)
        if not self.page:
            return
        self.page.dialog = self
        self.open = True
        self._safe_update()

    def cerrar(self) -> None:
        self.open = False
        self._safe_update()

    # ----------------------------
    # Helpers
    # ----------------------------
    def _is_editable(self) -> bool:
        if self.modo == "confirmado":
            return True
        est = str(self.pago.get("estado") or "").strip().lower()
        return est != "pagado"

    def _safe_update(self) -> None:
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

    def _snack(self, msg: str) -> None:
        try:
            if self.page:
                self.page.snack_bar = ft.SnackBar(ft.Text(msg))
                self.page.snack_bar.open = True
                self.page.update()
        except Exception:
            pass

    def _parse_money(self, v: Any) -> float:
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if not s:
            return 0.0
        s = s.replace("$", "").replace(",", "")
        try:
            return float(s)
        except Exception:
            return 0.0

    # ----------------------------
    # UI build
    # ----------------------------
    def _build_content(self) -> ft.Control:
        pid = int(self.pago.get("id_pago_nomina") or self.pago.get("id_pago") or 0)
        nom = str(self.pago.get("nombre_empleado") or self.pago.get("nombre") or "")
        num = str(self.pago.get("numero_nomina") or "")
        est = str(self.pago.get("estado") or "")

        header = ft.Column(
            [
                ft.Text(f"Pago: #{pid}  |  Nómina: {num}  |  {nom}", size=12),
                ft.Text(f"Estado: {est}", size=12),
                ft.Divider(),
            ],
            spacing=6,
        )

        grid = ft.Column(
            [
                ft.Row([self._chk_imss, self._tf_imss], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([self._chk_transporte, self._tf_transporte], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row(
                    [self._chk_extra, self._tf_extra_desc, self._tf_extra_monto],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Divider(),
                self._txt_resumen,
            ],
            spacing=10,
        )

        return ft.Container(
            content=ft.Column([header, grid], spacing=10),
            width=620,
            padding=10,
        )

    def _build_actions(self):
        btn_cancel = ft.TextButton("Cerrar", on_click=lambda _e: self.cerrar())
        if not self._editable:
            return [btn_cancel]
        btn_guardar = ft.ElevatedButton("Guardar", on_click=self._on_guardar)
        return [btn_cancel, btn_guardar]

    def _wire_events(self) -> None:
        def on_any_change(_e=None):
            self._sync_enabled_fields()
            self._refresh_resumen()

        self._chk_imss.on_change = on_any_change
        self._chk_transporte.on_change = on_any_change
        self._chk_extra.on_change = on_any_change

        self._tf_imss.on_change = on_any_change
        self._tf_transporte.on_change = on_any_change
        self._tf_extra_desc.on_change = on_any_change
        self._tf_extra_monto.on_change = on_any_change

    def _sync_enabled_fields(self) -> None:
        if not self._editable:
            self._tf_imss.disabled = True
            self._tf_transporte.disabled = True
            self._tf_extra_desc.disabled = True
            self._tf_extra_monto.disabled = True
            self._safe_update()
            return

        self._tf_imss.disabled = not bool(self._chk_imss.value)
        self._tf_transporte.disabled = not bool(self._chk_transporte.value)

        extra_on = bool(self._chk_extra.value)
        self._tf_extra_desc.disabled = not extra_on
        self._tf_extra_monto.disabled = not extra_on

        self._safe_update()

    # ----------------------------
    # Carga inicial
    # ----------------------------
    def _cargar_estado_inicial(self) -> None:
        pid = int(self.pago.get("id_pago_nomina") or self.pago.get("id_pago") or 0)
        if pid <= 0:
            return

        if self.initial_state:
            self._set_state_from_detalle(self.initial_state)
            return

        if self.modo == "confirmado":
            try:
                ds = self.discount_model.get_descuentos_por_pago(pid) or []
                if ds:
                    self._set_state_from_confirmados(ds)
                    return
            except Exception:
                pass

        try:
            det = self.detalles_model.obtener_por_id_pago(pid) or {}
            if det:
                self._set_state_from_detalle(det)
        except Exception:
            pass

    def _set_state_from_detalle(self, det: Dict[str, Any]) -> None:
        self._chk_imss.value = bool(int(det.get("aplicado_imss") or 0))
        self._tf_imss.value = str(det.get("monto_imss") or "")

        self._chk_transporte.value = bool(int(det.get("aplicado_transporte") or 0))
        self._tf_transporte.value = str(det.get("monto_transporte") or "")

        self._chk_extra.value = bool(int(det.get("aplicado_extra") or 0))
        self._tf_extra_desc.value = str(det.get("descripcion_extra") or "")
        self._tf_extra_monto.value = str(det.get("monto_extra") or "")

    def _set_state_from_confirmados(self, descuentos: list[Dict[str, Any]]) -> None:
        self._chk_imss.value = False
        self._tf_imss.value = ""
        self._chk_transporte.value = False
        self._tf_transporte.value = ""
        self._chk_extra.value = False
        self._tf_extra_desc.value = ""
        self._tf_extra_monto.value = ""

        for d in descuentos:
            tipo = str(d.get("tipo") or "").strip().lower()
            monto = self._parse_money(d.get("monto"))
            desc = str(d.get("descripcion") or "").strip()
            if tipo == "retenciones_imss":
                self._chk_imss.value = True
                self._tf_imss.value = f"{monto:.2f}"
            elif tipo == "transporte":
                self._chk_transporte.value = True
                self._tf_transporte.value = f"{monto:.2f}"
            elif tipo == "descuento_extra":
                self._chk_extra.value = True
                self._tf_extra_desc.value = desc
                self._tf_extra_monto.value = f"{monto:.2f}"

    # ----------------------------
    # Payload / Resumen
    # ----------------------------
    def _borrador_payload(self) -> Dict[str, Any]:
        imss_on = 1 if self._chk_imss.value else 0
        trans_on = 1 if self._chk_transporte.value else 0
        extra_on = 1 if self._chk_extra.value else 0

        return {
            "aplicado_imss": imss_on,
            "monto_imss": self._parse_money(self._tf_imss.value) if imss_on else 0.0,
            "aplicado_transporte": trans_on,
            "monto_transporte": self._parse_money(self._tf_transporte.value) if trans_on else 0.0,
            "aplicado_extra": extra_on,
            "descripcion_extra": (str(self._tf_extra_desc.value or "").strip() if extra_on else ""),
            "monto_extra": self._parse_money(self._tf_extra_monto.value) if extra_on else 0.0,
        }

    def _calc_total_descuentos_desde_payload(self, p: Dict[str, Any]) -> float:
        return float(
            float(p.get("monto_imss") or 0.0)
            + float(p.get("monto_transporte") or 0.0)
            + float(p.get("monto_extra") or 0.0)
        )

    def _refresh_resumen(self) -> None:
        payload = self._borrador_payload()
        total_desc = self._calc_total_descuentos_desde_payload(payload)

        monto_base = self._parse_money(
            self.pago.get("monto_base")
            or self.pago.get("monto_bruto")
            or self.pago.get("monto")
            or self.pago.get("monto_sin_descuentos")
            or 0
        )
        monto_prestamo = self._parse_money(self.pago.get("monto_prestamo") or self.pago.get("prestamo") or 0)
        nuevo_total = max(0.0, float(monto_base) - float(monto_prestamo) - float(total_desc))

        self._txt_resumen.value = (
            f"Total descuentos (borrador): ${total_desc:,.2f}\n"
            f"Monto base: ${monto_base:,.2f}\n"
            f"Préstamo: ${monto_prestamo:,.2f}\n"
            f"Nuevo total (estimado): ${nuevo_total:,.2f}"
        )
        self._safe_update()

    # ----------------------------
    # Guardado / Notify
    # ----------------------------
    def _notify(self, payload: Dict[str, Any]) -> None:
        if callable(self.on_confirmar):
            try:
                self.on_confirmar(payload)
            except TypeError:
                self.on_confirmar()  # type: ignore

    def _on_guardar(self, _e=None) -> None:
        if self.modo == "confirmado":
            self._guardar_confirmado()
        else:
            self._guardar_borrador()

    def _guardar_confirmado(self) -> None:
        pid = int(self.pago.get("id_pago_nomina") or self.pago.get("id_pago") or 0)
        numero_nomina = int(self.pago.get("numero_nomina") or 0)

        if pid <= 0 or numero_nomina <= 0:
            self._snack("Datos incompletos: id de pago o número de nómina inválido.")
            return

        payload = self._borrador_payload()
        try:
            res = self.discount_model.guardar_descuentos_confirmados(
                id_pago=pid,
                numero_nomina=numero_nomina,
                aplicar_imss=bool(payload.get("aplicado_imss")),
                monto_imss=float(payload.get("monto_imss") or 0.0),
                aplicar_transporte=bool(payload.get("aplicado_transporte")),
                monto_transporte=float(payload.get("monto_transporte") or 0.0),
                aplicar_extra=bool(payload.get("aplicado_extra")),
                monto_extra=float(payload.get("monto_extra") or 0.0),
                descripcion_extra=str(payload.get("descripcion_extra") or ""),
            )
            if (res or {}).get("status") not in ("success", "info"):
                self._snack((res or {}).get("message") or "No se pudieron guardar descuentos confirmados.")
                return
        except Exception as ex:
            self._snack(f"No se pudieron guardar descuentos confirmados: {ex}")
            return

        try:
            pago_rs = self.payment_model.get_by_id(pid)
            if pago_rs.get("status") == "success":
                p = pago_rs.get("data") or {}
                total_desc = float(self.discount_model.get_total_descuentos_por_pago(pid) or 0.0)
                monto_base = self._parse_money(p.get(self.payment_model.E.MONTO_BASE.value))
                monto_prestamo = self._parse_money(p.get(self.payment_model.P.PRESTAMO_MONTO.value))
                deposito = self._parse_money(p.get(self.payment_model.E.PAGO_DEPOSITO.value))
                efectivo = self._parse_money(p.get(self.payment_model.E.PAGO_EFECTIVO.value))
                total_nuevo = max(0.0, round(monto_base - total_desc - monto_prestamo, 2))
                saldo_nuevo = round(total_nuevo - deposito - efectivo, 2)

                self.payment_model.update_pago(
                    pid,
                    {
                        self.payment_model.D.MONTO_DESCUENTO.value: total_desc,
                        self.payment_model.E.MONTO_TOTAL.value: total_nuevo,
                        self.payment_model.E.SALDO.value: saldo_nuevo,
                    },
                    force=True,
                )
        except Exception:
            pass

        self._notify(
            {
                "id_pago": pid,
                "accion": "confirmado_guardado",
                "detalle": payload,
            }
        )
        self.open = False
        self._safe_update()

    def _guardar_borrador(self) -> None:
        if not self._editable:
            self._snack("No se puede editar: el pago ya está pagado.")
            return

        pid = int(self.pago.get("id_pago_nomina") or self.pago.get("id_pago") or 0)
        if pid <= 0:
            self._snack("ID de pago inválido. No se pudo guardar.")
            return

        payload = self._borrador_payload()

        # Persistir borrador
        try:
            res = self.detalles_model.upsert_detalles(pid, payload)
            if not isinstance(res, dict) or res.get("status") != "success":
                self._snack((res or {}).get("message") or "No se pudo guardar borrador de descuentos.")
                return
        except Exception as e:
            self._snack(f"No se pudo guardar borrador de descuentos: {e}")
            return

        # Ayuda para el container (sin depender de PaymentModel)
        total_desc = self._calc_total_descuentos_desde_payload(payload)

        monto_base = self._parse_money(
            self.pago.get("monto_base")
            or self.pago.get("monto_bruto")
            or self.pago.get("monto")
            or self.pago.get("monto_sin_descuentos")
            or 0
        )
        monto_prestamo = self._parse_money(self.pago.get("monto_prestamo") or self.pago.get("prestamo") or 0)
        nuevo_total = max(0.0, float(monto_base) - float(monto_prestamo) - float(total_desc))

        self._notify(
            {
                "id_pago": pid,
                "accion": "borrador_guardado",
                "monto_descuento": float(total_desc),
                "monto_total": float(nuevo_total),
                "detalle": payload,  # opcional: evita query inmediata si quieres
            }
        )

        self.open = False
        self._safe_update()
