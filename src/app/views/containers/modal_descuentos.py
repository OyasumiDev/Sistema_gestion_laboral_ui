from __future__ import annotations

from typing import Any, Callable, Dict, Optional

import flet as ft

from app.core.app_state import AppState
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
        on_confirmar: Optional[Callable[[Dict[str, Any]], None]] = None,
        initial_state: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()

        self.pago: Dict[str, Any] = pago_data or {}
        self.on_confirmar = on_confirmar
        self.initial_state = initial_state or {}

        self.page: Optional[ft.Page] = None  # se setea en mostrar()
        self.detalles_model = DescuentoDetallesModel()

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
        self._guardar_borrador()

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
