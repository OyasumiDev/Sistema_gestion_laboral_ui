# app/views/containers/modal_prestamos_nomina.py
import flet as ft
from datetime import datetime
from decimal import Decimal
from typing import Optional, Callable

from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert

from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.detalles_pagos_prestamo_model import DetallesPagosPrestamoModel
from app.models.employes_model import EmployesModel
from app.core.enums.e_pagos_prestamos import E_PAGOS_PRESTAMO as E  # ajusta si tu import real difiere


class ModalPrestamosNomina:
    """
    Modal para PAGOS DE PRÉSTAMOS en el contexto de NÓMINA (detalles por id_pago).
    - Permite registrar montos a MÚLTIPLES préstamos para un mismo id_pago.
    - AUTO-GUARDA al escribir y al cambiar de préstamo.
    - Respeta reglas:
        * estado_pago == 'pagado' -> solo lectura (no guarda).
        * préstamo eliminado -> no editable.
        * préstamo terminado -> solo lectura de ese préstamo.
    - Historial siempre fresco vía LoanPaymentModel.get_by_prestamo(id_prestamo).
    """

    def __init__(self, pago_data: dict, on_confirmar: Callable):
        """
        pago_data requerido:
          - id_pago (int)
          - numero_nomina (int)
          - estado (str)   -> 'pendiente' / 'pagado'
        """
        self.page = AppState().page
        self.pago_data = (pago_data or {}).copy()
        self.on_confirmar = on_confirmar

        # --- Datos base del pago de nómina
        self.id_pago: int = int(self.pago_data["id_pago"])
        self.numero_nomina: int = int(self.pago_data["numero_nomina"])
        self.estado_pago: str = str(self.pago_data.get("estado", "pendiente")).lower()

        # --- Modelos
        self.loan_model = LoanModel()
        self.loan_payment_model = LoanPaymentModel()
        self.detalles_model = DetallesPagosPrestamoModel()
        self.emp_model = EmployesModel()

        # --- Empleado (nombre)
        emp = self.emp_model.get_by_numero_nomina(self.numero_nomina) or {}
        self.nombre_empleado = emp.get("nombre_completo", "Desconocido")

        # --- Prestamos del empleado (activos y no activos)
        self.prestamos: list[dict] = self.loan_model.get_prestamos_por_empleado(self.numero_nomina) or []
        self.prestamos_map = {int(p["id_prestamo"]): p for p in self.prestamos if "id_prestamo" in p}

        # --- Buffers por préstamo (edición en curso) y últimos valores guardados
        # Estructura buffers: { id_prestamo: {"monto": str, "interes": str, "obs": str} }
        self.buffers: dict[int, dict] = {}
        # Último payload persistido para evitar upserts redundantes
        self.ultimos_guardados: dict[int, tuple[float, int, str]] = {}

        self._cargar_detalles_guardados_en_buffers()

        # UI state
        self.dialog = ft.AlertDialog(modal=True)
        self.dropdown: Optional[ft.Dropdown] = None
        self.monto_input: Optional[ft.TextField] = None
        self.interes_input: Optional[ft.TextField] = None
        self.obs_input: Optional[ft.TextField] = None
        self.lbl_preview = ft.Text("-", weight=ft.FontWeight.BOLD)
        self.resumen_text = ft.Text("", color=ft.colors.BLUE_GREY)
        self.historial_table: Optional[ft.DataTable] = None

        # id_prestamo seleccionado actualmente
        self.current_prestamo_id: Optional[int] = None

        # Construcción
        self._construir_modal()

    # ---------------- API ----------------
    def mostrar(self):
        if self.page and self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    # ---------------- Internos ----------------
    def _cargar_detalles_guardados_en_buffers(self):
        # Pre-cargar detalle guardado por cada préstamo de este empleado (si existe)
        for p in self.prestamos:
            pid = int(p["id_prestamo"])
            det = self.detalles_model.get_detalle(self.id_pago, pid)
            if det:
                monto = str(det.get(self.detalles_model.E.MONTO_GUARDADO.value, ""))
                interes = str(det.get(self.detalles_model.E.INTERES_GUARDADO.value, ""))
                obs = det.get(self.detalles_model.E.OBSERVACIONES.value, "") or ""
                self.buffers[pid] = {"monto": monto, "interes": interes, "obs": obs}
                # guarda snapshot numérico para evitar re-upsert innecesario
                try:
                    self.ultimos_guardados[pid] = (float(str(monto).replace(",", ".")), int(round(float(interes or "0"))), obs)
                except Exception:
                    pass

    def _solo_lectura_global(self) -> bool:
        return self.estado_pago == "pagado"

    def _prestamo_eliminado(self, pid: int) -> bool:
        return pid not in self.prestamos_map

    def _prestamo_terminado(self, pid: int) -> bool:
        p = self.prestamos_map.get(pid)
        return (not p) or (str(p.get("estado", "")).lower() == "terminado")

    def _construir_modal(self):
        # Si no hay préstamos, solo mostrar mensaje y bloquear
        if not self.prestamos:
            self.dialog.content = ft.Container(
                padding=20,
                width=760,
                content=ft.Column([
                    ft.Text(f"Préstamos • {self.nombre_empleado} (No. {self.numero_nomina})",
                            style=ft.TextThemeStyle.TITLE_MEDIUM),
                    ft.Divider(),
                    ft.Text("Este empleado no tiene préstamos activos o disponibles para detalle.", color=ft.colors.GREY_700),
                    ft.Row([ft.TextButton("Cerrar", on_click=lambda _: self._cerrar())],
                           alignment=ft.MainAxisAlignment.END)
                ], spacing=12)
            )
            return

        # Dropdown de préstamos (siempre visible en nómina)
        self.dropdown = ft.Dropdown(
            label="Préstamo",
            value=None,
            options=[
                ft.dropdown.Option(
                    str(int(p["id_prestamo"])),
                    f"ID {p['id_prestamo']} • Saldo: ${float(p.get('saldo_prestamo',0) or 0):.2f} • {p.get('estado','')}"
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
            on_change=self._on_change_inputs
        )
        self.interes_input = ft.TextField(
            label="Interés (%)",
            width=140,
            keyboard_type=ft.KeyboardType.NUMBER,
            value="10",
            on_change=self._on_change_inputs
        )
        self.obs_input = ft.TextField(
            label="Observaciones",
            hint_text="Descripción adicional (opcional)",
            multiline=True, min_lines=2, max_lines=3,
            on_change=self._on_change_inputs
        )

        # Historial placeholder
        self.historial_table = ft.DataTable(
            columns=[
                ft.DataColumn(label=ft.Text("Fecha")),
                ft.DataColumn(label=ft.Text("Monto")),
                ft.DataColumn(label=ft.Text("Interés")),
                ft.DataColumn(label=ft.Text("Aplicado")),
                ft.DataColumn(label=ft.Text("Saldo")),
            ],
            rows=[],
            column_spacing=18, data_row_max_height=36
        )

        # Layout (sin botones de guardar: auto-save)
        self.dialog.content = ft.Container(
            padding=20, width=860,
            content=ft.Column([
                ft.Text(f"Detalle de préstamos (Nómina) • {self.nombre_empleado} (No. {self.numero_nomina})",
                        style=ft.TextThemeStyle.TITLE_MEDIUM),
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
                ft.Row([ft.TextButton("Cerrar", on_click=lambda _: self._cerrar())],
                       alignment=ft.MainAxisAlignment.END, spacing=12)
            ], spacing=12)
        )

        # Seleccionar el primer préstamo por defecto
        try:
            if self.prestamos:
                first_id = int(self.prestamos[0]["id_prestamo"])
                self.dropdown.value = str(first_id)
                self._on_change_prestamo(None, initial=True)
        except Exception:
            pass

        # Solo lectura global si el pago ya está pagado
        if self._solo_lectura_global():
            self._set_inputs_enabled(False)

    def _cerrar(self):
        self.dialog.open = False
        if self.page:
            self.page.update()

    def _set_inputs_enabled(self, enabled: bool):
        for ctrl in (self.monto_input, self.interes_input, self.obs_input):
            if ctrl:
                ctrl.disabled = not enabled

    def _on_change_prestamo(self, e, initial: bool = False):
        # Antes de cambiar, intenta auto-guardar el préstamo previo
        if (not initial) and (self.current_prestamo_id is not None):
            self._auto_upsert(self.current_prestamo_id)

        # Cargar el seleccionado
        try:
            pid = int(self.dropdown.value)
        except Exception:
            pid = None
        self.current_prestamo_id = pid

        # Cargar inputs desde buffer o detalle guardado
        self._cargar_inputs_desde_buffer(pid)

        # Actualizar historial y preview
        self._refrescar_historial(pid)
        self._recalcular_preview(pid)

        # Habilitar/Deshabilitar por reglas
        editable = (not self._solo_lectura_global()) and (pid is not None) and (not self._prestamo_eliminado(pid)) and (not self._prestamo_terminado(pid))
        self._set_inputs_enabled(editable)
        if not editable:
            self.monto_input.border_color = None

        if self.page:
            self.page.update()

    def _cargar_inputs_desde_buffer(self, pid: Optional[int]):
        buf = self.buffers.get(pid, {})
        self.monto_input.value = buf.get("monto", "")
        self.interes_input.value = buf.get("interes", "10")
        self.obs_input.value = buf.get("obs", "")

    def _guardar_buffer_local(self, pid: int):
        self.buffers[pid] = {
            "monto": self.monto_input.value or "",
            "interes": self.interes_input.value or "0",
            "obs": self.obs_input.value or "",
        }

    def _refrescar_historial(self, pid: Optional[int]):
        # Siempre fresco (si eliminaron un pago en Prestamos, aquí desaparece)
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
                rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(fecha))),
                    ft.DataCell(ft.Text(f"${monto:.2f}")),
                    ft.DataCell(ft.Text(f"{interes_pct}%")),
                    ft.DataCell(ft.Text(f"${interes_apl:.2f}")),
                    ft.DataCell(ft.Text(f"${saldo:.2f}")),
                ]))
        self.historial_table.rows = rows

    def _on_change_inputs(self, _):
        pid = self.current_prestamo_id
        self._recalcular_preview(pid)
        # Auto-guardar si es válido y editable
        if pid is not None:
            self._auto_upsert(pid)

    def _calc_preview(self, pid: int, monto: float, interes_pct: float) -> dict:
        # saldo actual desde DB con fallback al prestamo listado
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
            f"Saldo: ${prev['saldo_actual']:.2f} + interés ${prev['interes_aplicado']:.2f} = ${prev['saldo_con_interes']:.2f} | "
            f"Pago: ${monto:.2f} → saldo quedaría ${prev['nuevo_saldo']:.2f}"
        )

        # borde verde/rojo
        monto_valido = (not self._solo_lectura_global()) and (monto > 0) and (monto <= prev["saldo_con_interes"]) and (not self._prestamo_terminado(pid)) and (not self._prestamo_eliminado(pid))
        self.monto_input.border_color = ft.colors.GREEN if monto_valido else ft.colors.RED

        # resumen con feedback
        try:
            m = Decimal(str(monto or 0))
            restante = Decimal(str(prev["saldo_con_interes"])) - m
            # no marcamos "guardado" aquí; se marca al confirmar el upsert
            self.resumen_text.value = f"💸 Este detalle: ${m:.2f} | 🔚 Restante con interés: ${restante:.2f}"
        except Exception:
            self.resumen_text.value = f"💸 Este detalle: — | 🔚 Restante: —"

        if self.page:
            self.page.update()

    # ---------------- AUTO-GUARDADO ----------------
    def _auto_upsert(self, pid: int):
        """
        Guarda automáticamente el detalle del préstamo seleccionado si:
        - No es solo lectura global
        - El préstamo existe y no está terminado
        - Los datos son válidos y cambian respecto al último guardado
        """
        if self._solo_lectura_global() or self._prestamo_eliminado(pid) or self._prestamo_terminado(pid):
            return

        # Parseo
        try:
            interes = float((self.interes_input.value or "0").replace(",", "."))
        except Exception:
            return  # no guardar con interés inválido
        try:
            monto = float((self.monto_input.value or "0").replace(",", "."))
        except Exception:
            return  # no guardar con monto inválido

        obs = (self.obs_input.value or "").strip()

        # Validación contra preview
        prev = self._calc_preview(pid, monto, interes)
        if (monto <= 0) or (monto > prev["saldo_con_interes"]):
            return  # inválido -> no guardar

        # Evitar upsert redundante
        snapshot = (round(monto, 2), int(round(interes)), obs)
        if self.ultimos_guardados.get(pid) == snapshot:
            # ya está guardado con estos valores
            self._guardar_buffer_local(pid)
            return

        # Guardar
        res = self.detalles_model.upsert_detalle(
            id_pago=self.id_pago,
            id_prestamo=pid,
            monto=round(monto, 2),
            interes=int(round(interes)),
            observaciones=obs
        )
        if res.get("status") == "success":
            # Actualiza memoria local
            self._guardar_buffer_local(pid)
            self.ultimos_guardados[pid] = snapshot
            # Feedback sutil
            try:
                m = Decimal(str(monto))
                restante = Decimal(str(prev["saldo_con_interes"])) - m
                self.resumen_text.value = f"✓ guardado • 💸 ${m:.2f} | 🔚 Restante con interés: ${restante:.2f}"
            except Exception:
                self.resumen_text.value = "✓ guardado"
            # Notifica al contenedor para recálculo de fila
            try:
                self.on_confirmar(None)
            finally:
                if self.page:
                    self.page.update()
        else:
            # no bloquear; solo feedback mínimo
            pass
