# app/views/containers/modal_prestamos_nomina.py
from __future__ import annotations
import flet as ft
from datetime import datetime
from decimal import Decimal
from typing import Optional, Callable, Dict, Any

from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert

from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.detalles_pagos_prestamo_model import DetallesPagosPrestamoModel
from app.models.employes_model import EmployesModel
from app.core.enums.e_pagos_prestamos import E_PAGOS_PRESTAMO as E  # ajusta si tu import real difiere


class ModalPrestamosNomina:
    """
    Modal para detallar pagos de PRESTAMOS ligados a un pago de nómina (id_pago).
    - Auto-guardado al escribir y al cambiar de préstamo.
    - No bloquea edición salvo que el pago de nómina ya esté 'pagado' o el préstamo haya sido eliminado.
    - Tras cada guardado notifica al contenedor (para recálculo en vivo).
    """

    def __init__(self, pago_data: Dict[str, Any], on_confirmar: Callable[[Any], None]):
        """
        pago_data:
          - id_pago (int)
          - numero_nomina (int)
          - estado (str) -> 'pendiente' / 'pagado'
        """
        self.page = AppState().page
        self.pago_data = (pago_data or {}).copy()
        self.on_confirmar = on_confirmar

        # ---- Datos base
        self.id_pago: int = int(self.pago_data["id_pago"])
        self.numero_nomina: int = int(self.pago_data["numero_nomina"])
        self.estado_pago: str = str(self.pago_data.get("estado", "pendiente")).lower()

        # ---- Modelos
        self.loan_model = LoanModel()
        self.loan_payment_model = LoanPaymentModel()
        self.detalles_model = DetallesPagosPrestamoModel()
        self.emp_model = EmployesModel()

        # ---- Empleado
        emp = self.emp_model.get_by_numero_nomina(self.numero_nomina) or {}
        self.nombre_empleado = emp.get("nombre_completo", "Desconocido")

        # ---- Prestamos del empleado (lo más amplio posible)
        self.prestamos: list[dict] = self.loan_model.get_prestamos_por_empleado(self.numero_nomina) or []
        self.prestamos_map = {int(p["id_prestamo"]): p for p in self.prestamos if "id_prestamo" in p}

        # ---- Buffers (edición por préstamo) y último snapshot guardado
        self.buffers: dict[int, dict] = {}
        self.ultimos_guardados: dict[int, tuple[float, int, str]] = {}
        self._cargar_detalles_guardados_en_buffers()

        # ---- UI
        self.dialog = ft.AlertDialog(modal=True)
        self.dropdown: Optional[ft.Dropdown] = None
        self.monto_input: Optional[ft.TextField] = None
        self.interes_input: Optional[ft.TextField] = None
        self.obs_input: Optional[ft.TextField] = None
        self.lbl_preview = ft.Text("-", weight=ft.FontWeight.BOLD)
        self.resumen_text = ft.Text("", color=ft.colors.BLUE_GREY)
        self.historial_table: Optional[ft.DataTable] = None

        self.current_prestamo_id: Optional[int] = None
        self._construir_modal()

    # ---------------- API ----------------
    def mostrar(self):
        # Usar page.dialog es más estable que overlays para diálogos modales
        if self.page:
            self.page.dialog = self.dialog
            self.dialog.open = True
            self.page.update()

    # ---------------- Internos ----------------
    def _cargar_detalles_guardados_en_buffers(self):
        for p in self.prestamos:
            pid = int(p["id_prestamo"])
            det = self.detalles_model.get_detalle(self.id_pago, pid)
            if det:
                monto = str(det.get(self.detalles_model.E.MONTO_GUARDADO.value, "") or "")
                interes = str(det.get(self.detalles_model.E.INTERES_GUARDADO.value, "") or "0")
                obs = det.get(self.detalles_model.E.OBSERVACIONES.value, "") or ""
                self.buffers[pid] = {"monto": monto, "interes": interes, "obs": obs}
                try:
                    self.ultimos_guardados[pid] = (
                        float(str(monto).replace(",", ".")),
                        int(round(float(interes or "0"))),
                        obs,
                    )
                except Exception:
                    pass

    def _solo_lectura_global(self) -> bool:
        return self.estado_pago == "pagado"

    def _prestamo_eliminado(self, pid: int) -> bool:
        return pid not in self.prestamos_map

    # Nota: no bloqueamos por “terminado”; damos feedback, pero permitimos ajustar detalle
    def _prestamo_terminado(self, pid: int) -> bool:
        p = self.prestamos_map.get(pid)
        return bool(p and str(p.get("estado", "")).lower() == "terminado")

    def _construir_modal(self):
        # Sin préstamos
        if not self.prestamos:
            self.dialog.content = ft.Container(
                padding=20,
                width=760,
                content=ft.Column(
                    [
                        ft.Text(
                            f"Préstamos • {self.nombre_empleado} (No. {self.numero_nomina})",
                            style=ft.TextThemeStyle.TITLE_MEDIUM,
                        ),
                        ft.Divider(),
                        ft.Text(
                            "Este empleado no tiene préstamos disponibles para detallar.",
                            color=ft.colors.GREY_700,
                        ),
                        ft.Row(
                            [ft.TextButton("Cerrar", on_click=lambda _: self._cerrar(True))],
                            alignment=ft.MainAxisAlignment.END,
                        ),
                    ],
                    spacing=12,
                ),
            )
            return

        # Dropdown
        self.dropdown = ft.Dropdown(
            label="Préstamo",
            value=None,
            options=[
                ft.dropdown.Option(
                    str(int(p["id_prestamo"])),
                    f"ID {p['id_prestamo']} • Saldo: ${float(p.get('saldo_prestamo',0) or 0):.2f} • {p.get('estado','')}",
                )
                for p in self.prestamos
            ],
            on_change=self._on_change_prestamo,
            width=520,
        )

        # Inputs
        self.monto_input = ft.TextField(
            label="Monto a detallar",
            width=220,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=self._on_change_inputs,
        )
        self.interes_input = ft.TextField(
            label="Interés (%)",
            width=140,
            keyboard_type=ft.KeyboardType.NUMBER,
            value="0",
            on_change=self._on_change_inputs,
        )
        self.obs_input = ft.TextField(
            label="Observaciones",
            hint_text="Descripción adicional (opcional)",
            multiline=True,
            min_lines=2,
            max_lines=3,
            on_change=self._on_change_inputs,
        )

        # Historial
        self.historial_table = ft.DataTable(
            columns=[
                ft.DataColumn(label=ft.Text("Fecha")),
                ft.DataColumn(label=ft.Text("Monto")),
                ft.DataColumn(label=ft.Text("Interés")),
                ft.DataColumn(label=ft.Text("Aplicado")),
                ft.DataColumn(label=ft.Text("Saldo")),
            ],
            rows=[],
            column_spacing=18,
            data_row_max_height=36,
        )

        # Layout
        self.dialog.content = ft.Container(
            padding=20,
            width=860,
            content=ft.Column(
                [
                    ft.Text(
                        f"Detalle de préstamos (Nómina) • {self.nombre_empleado} (No. {self.numero_nomina})",
                        style=ft.TextThemeStyle.TITLE_MEDIUM,
                    ),
                    self.dropdown,
                    ft.Divider(),
                    ft.Text("Historial reciente", weight=ft.FontWeight.BOLD),
                    self.historial_table,
                    ft.Divider(),
                    ft.Text("Detalle a registrar para este préstamo", weight=ft.FontWeight.BOLD),
                    ft.Row([self.monto_input, self.interes_input], spacing=16),
                    self.lbl_preview,
                    self.obs_input,
                    self.resumen_text,
                    ft.Row(
                        [
                            ft.TextButton("Cerrar", on_click=lambda _: self._cerrar(True)),
                        ],
                        alignment=ft.MainAxisAlignment.END,
                        spacing=12,
                    ),
                ],
                spacing=12,
            ),
        )

        # Selección inicial
        try:
            if self.prestamos:
                first_id = int(self.prestamos[0]["id_prestamo"])
                self.dropdown.value = str(first_id)
                self._on_change_prestamo(None, initial=True)
        except Exception:
            pass

        # Solo lectura global (si nómina ya está pagada)
        if self._solo_lectura_global():
            self._set_inputs_enabled(False)

    def _cerrar(self, notify: bool = False):
        # Auto-guardar lo que esté seleccionado y notificar para recálculo
        if self.current_prestamo_id is not None:
            self._auto_upsert(self.current_prestamo_id)
        if notify:
            self._notify_parent_refresh()

        self.dialog.open = False
        if self.page:
            self.page.update()

    def _set_inputs_enabled(self, enabled: bool):
        for ctrl in (self.monto_input, self.interes_input, self.obs_input):
            if ctrl:
                ctrl.disabled = not enabled

    def _on_change_prestamo(self, e, initial: bool = False):
        # Auto-save del anterior
        if (not initial) and (self.current_prestamo_id is not None):
            self._auto_upsert(self.current_prestamo_id)

        # Nuevo seleccionado
        try:
            pid = int(self.dropdown.value)
        except Exception:
            pid = None
        self.current_prestamo_id = pid

        # Cargar valores guardados/buffer
        self._cargar_inputs_desde_buffer(pid)

        # Historial + preview
        self._refrescar_historial(pid)
        self._recalcular_preview(pid)

        # Reglas de edición: SOLO se bloquea si nómina ya pagada o préstamo eliminado
        editable = (not self._solo_lectura_global()) and (pid is not None) and (not self._prestamo_eliminado(pid))
        self._set_inputs_enabled(editable)

        # Feedback si “terminado”
        if pid is not None and self._prestamo_terminado(pid):
            self.resumen_text.value = "ℹ️ Préstamo marcado como terminado; aún puedes ajustar el detalle antes de confirmar nómina."

        if self.page:
            self.page.update()

    def _cargar_inputs_desde_buffer(self, pid: Optional[int]):
        buf = self.buffers.get(pid, {})
        self.monto_input.value = buf.get("monto", "")
        self.interes_input.value = buf.get("interes", "0")
        self.obs_input.value = buf.get("obs", "")

    def _guardar_buffer_local(self, pid: int):
        self.buffers[pid] = {
            "monto": self.monto_input.value or "",
            "interes": self.interes_input.value or "0",
            "obs": self.obs_input.value or "",
        }

    def _refrescar_historial(self, pid: Optional[int]):
        rows = []
        if pid is not None and not self._prestamo_eliminado(pid):
            pagos_res = self.loan_payment_model.get_by_prestamo(pid) or {}
            pagos = pagos_res.get("data", []) if isinstance(pagos_res, dict) else []
            for p in pagos[-5:]:
                try:
                    fecha = p.get(E.PAGO_FECHA_PAGO.value)
                    monto = float(p.get(E.PAGO_MONTO_PAGADO.value, 0) or 0)
                    interes_pct = p.get(E.PAGO_INTERES_PORCENTAJE.value)
                    interes_apl = float(p.get(E.PAGO_INTERES_APLICADO.value, 0) or 0)
                    saldo = float(p.get(E.PAGO_SALDO_RESTANTE.value, 0) or 0)
                except Exception:
                    continue
                rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(str(fecha))),
                            ft.DataCell(ft.Text(f"${monto:.2f}")),
                            ft.DataCell(ft.Text(f"{interes_pct}%")),
                            ft.DataCell(ft.Text(f"${interes_apl:.2f}")),
                            ft.DataCell(ft.Text(f"${saldo:.2f}")),
                        ]
                    )
                )
        self.historial_table.rows = rows
        if getattr(self.historial_table, "page", None):
            self.historial_table.update()

    def _on_change_inputs(self, _):
        pid = self.current_prestamo_id
        self._recalcular_preview(pid)
        if pid is not None:
            self._auto_upsert(pid)

    def _calc_preview(self, pid: int, monto: float, interes_pct: float) -> dict:
        saldo_actual = 0.0
        try:
            mx = self.loan_payment_model.get_saldo_y_monto_prestamo(pid) or {}
            saldo_actual = float(mx.get("saldo_prestamo", 0.0))
        except Exception:
            p = self.prestamos_map.get(pid, {})
            try:
                saldo_actual = float(p.get("saldo_prestamo", 0) or 0)
            except Exception:
                saldo_actual = 0.0

        interes_aplicado = round(saldo_actual * (interes_pct / 100.0), 2) if interes_pct > 0 else 0.0
        saldo_con_interes = round(saldo_actual + interes_aplicado, 2)
        pago_efectivo = min(max(monto, 0.0), saldo_con_interes)
        nuevo_saldo = round(saldo_con_interes - pago_efectivo, 2)

        return dict(
            saldo_actual=saldo_actual,
            interes_aplicado=interes_aplicado,
            saldo_con_interes=saldo_con_interes,
            nuevo_saldo=nuevo_saldo,
        )

    def _recalcular_preview(self, pid: Optional[int]):
        if pid is None:
            return
        try:
            interes = float((self.interes_input.value or "0").replace(",", "."))
        except Exception:
            interes = 0.0
        try:
            monto = float((self.monto_input.value or "0").replace(",", "."))
        except Exception:
            monto = 0.0

        prev = self._calc_preview(pid, monto, interes)
        self.lbl_preview.value = (
            f"Saldo: ${prev['saldo_actual']:.2f} + interés ${prev['interes_aplicado']:.2f} "
            f"= ${prev['saldo_con_interes']:.2f} | Pago: ${monto:.2f} → saldo quedaría ${prev['nuevo_saldo']:.2f}"
        )

        monto_valido = (
            (not self._solo_lectura_global())
            and (monto > 0)
            and (monto <= prev["saldo_con_interes"])
            and (not self._prestamo_eliminado(pid))
        )
        self.monto_input.border_color = ft.colors.GREEN if monto_valido else ft.colors.RED

        try:
            m = Decimal(str(monto or 0))
            restante = Decimal(str(prev["saldo_con_interes"])) - m
            self.resumen_text.value = f"💸 Este detalle: ${m:.2f} | 🔚 Restante con interés: ${restante:.2f}"
        except Exception:
            self.resumen_text.value = f"💸 Este detalle: — | 🔚 Restante: —"

        if self.page:
            self.page.update()

    # ---------------- AUTO-GUARDADO ----------------
    def _auto_upsert(self, pid: int):
        if self._solo_lectura_global() or self._prestamo_eliminado(pid):
            return

        # Parseo
        try:
            interes = float((self.interes_input.value or "0").replace(",", "."))
        except Exception:
            return
        try:
            monto = float((self.monto_input.value or "0").replace(",", "."))
        except Exception:
            return

        obs = (self.obs_input.value or "").strip()

        # Validación
        prev = self._calc_preview(pid, monto, interes)
        if (monto <= 0) or (monto > prev["saldo_con_interes"]):
            return

        # Evitar upsert redundante
        snapshot = (round(monto, 2), int(round(interes)), obs)
        if self.ultimos_guardados.get(pid) == snapshot:
            self._guardar_buffer_local(pid)
            return

        # Guardar
        res = self.detalles_model.upsert_detalle(
            id_pago=self.id_pago,
            id_prestamo=pid,
            monto=round(monto, 2),
            interes=int(round(interes)),
            observaciones=obs,
        )
        if res.get("status") == "success":
            self._guardar_buffer_local(pid)
            self.ultimos_guardados[pid] = snapshot

            try:
                m = Decimal(str(monto))
                restante = Decimal(str(prev["saldo_con_interes"])) - m
                self.resumen_text.value = f"✓ guardado • 💸 ${m:.2f} | 🔚 Restante con interés: ${restante:.2f}"
            except Exception:
                self.resumen_text.value = "✓ guardado"

            # Notificar contenedor para recálculo inmediato
            self._notify_parent_refresh()

            if self.page:
                self.page.update()
        else:
            # Feedback mínimo en caso de fallo
            ModalAlert.mostrar_info("Detalle de préstamo", res.get("message", "No se pudo guardar el detalle."))

    # ---------------- Notificación al contenedor ----------------
    def _notify_parent_refresh(self):
        """Invoca el callback del contenedor para que recalcule la fila (pendiente o pagado)."""
        try:
            if callable(self.on_confirmar):
                # Enviamos un payload por si el caller quisiera distinguir el evento
                self.on_confirmar({"source": "modal_prestamos", "id_pago": self.id_pago})
        except Exception:
            pass
