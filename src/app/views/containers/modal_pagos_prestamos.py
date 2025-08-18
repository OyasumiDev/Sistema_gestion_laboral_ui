# app/views/containers/modal_pagos_prestamos.py
import flet as ft
from datetime import datetime
from decimal import Decimal
from typing import Optional, Callable

from app.core.app_state import AppState
from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.employes_model import EmployesModel
from app.views.containers.modal_alert import ModalAlert
from app.core.enums.e_pagos_prestamos import E_PAGOS_PRESTAMO as E


class ModalPrestamos:
    """
    Modal EXCLUSIVO para el módulo de Préstamos.
    - Aplica pagos REALES a un préstamo.
    - NO maneja detalles de nómina ni dropdown para cambiar de préstamo.
    - Mantiene la firma (pago_data, on_confirmar) para no romper invocaciones previas.
    
    pago_data esperado (mínimo):
    - numero_nomina (int | str)
    - id_prestamo (int)  -> recomendado pasarlo desde la fila seleccionada
    - fecha_generacion (YYYY-MM-DD) opcional (default hoy)
    - fecha_pago (YYYY-MM-DD) opcional (default = fecha_generacion)
    """

    def __init__(self, pago_data: dict, on_confirmar: Callable):
        self.page = AppState().page
        self.on_confirmar = on_confirmar
        self.pago_data = (pago_data or {}).copy()

        # ── Datos base
        self.numero_nomina = int(self.pago_data["numero_nomina"])
        hoy = datetime.today().strftime("%Y-%m-%d")
        self.fecha_generacion = self.pago_data.get("fecha_generacion") or hoy
        self.fecha_pago_base = self.pago_data.get("fecha_pago") or self.fecha_generacion

        # Modelos
        self.loan_model = LoanModel()
        self.pago_model = LoanPaymentModel()
        self.empleado_model = EmployesModel()
        self.E = E

        # Empleado
        emp = self.empleado_model.get_by_numero_nomina(self.numero_nomina) or {}
        self.nombre_empleado = emp.get("nombre_completo", "Desconocido")

        # Estado de préstamo
        self.id_prestamo: Optional[int] = None
        self.prestamos_disponibles: list[dict] = []
        self.pagos: list[dict] = []
        self.total_pagado = 0.0
        self.saldo_restante = 0.0
        self.puede_editar = False  # se define al setear préstamo

        # UI
        self.dialog = ft.AlertDialog(modal=True)
        self.monto_input: Optional[ft.TextField] = None
        self.interes_input: Optional[ft.TextField] = None
        self.observaciones_input: Optional[ft.TextField] = None
        self.lbl_preview = ft.Text("-", weight=ft.FontWeight.BOLD)
        self.resumen_text = ft.Text("")
        self.boton_guardar: Optional[ft.Control] = None

        self._cargar_datos()

    # ---------------- API ----------------
    def mostrar(self):
        if self.page and self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    # ------------- Internos --------------
    def _cerrar(self, _=None):
        self.dialog.open = False
        self.page.update()

    def _cargar_datos(self):
        # Obtener préstamos del empleado
        self.prestamos_disponibles = self.loan_model.get_prestamos_por_empleado(self.numero_nomina) or []
        if not self.prestamos_disponibles:
            ModalAlert.mostrar_info("Sin préstamo", f"No hay préstamos para {self.numero_nomina}")
            return

        # Determinar id_prestamo (preferentemente viene de la fila)
        pid = self.pago_data.get("id_prestamo")
        if pid:
            self.id_prestamo = int(pid)
        else:
            # fallback: primero disponible
            self.id_prestamo = int(self.prestamos_disponibles[0]["id_prestamo"])

        self._set_prestamo(self.id_prestamo)

    def _set_prestamo(self, id_prestamo: int):
        self.id_prestamo = id_prestamo
        prestamo = next((p for p in self.prestamos_disponibles if p["id_prestamo"] == id_prestamo), None)
        if not prestamo:
            ModalAlert.mostrar_info("Error", "Préstamo no encontrado.")
            return

        self.saldo_restante = float(prestamo["saldo_prestamo"])
        pagos_res = self.pago_model.get_by_prestamo(self.id_prestamo) or {}
        self.pagos = pagos_res.get("data", []) if isinstance(pagos_res, dict) else []
        self.total_pagado = sum(float(p.get(self.E.PAGO_MONTO_PAGADO.value, 0) or 0) for p in self.pagos)

        estado_prest = str(prestamo.get("estado", "")).lower()
        # Editable si queda saldo y no está terminado
        self.puede_editar = (self.saldo_restante > 0) and (estado_prest != "terminado")

        self._construir_modal()
        self._recalcular_montos()
        self.page.update()

    def _construir_modal(self):
        # Historial (últimos 5)
        rows = []
        for p in self.pagos[-5:]:
            try:
                fecha = p.get(self.E.PAGO_FECHA_PAGO.value)
                monto = float(p.get(self.E.PAGO_MONTO_PAGADO.value, 0) or 0)
                interes_pct = p.get(self.E.PAGO_INTERES_PORCENTAJE.value)
                interes_apl = float(p.get(self.E.PAGO_INTERES_APLICADO.value, 0) or 0)
                saldo = float(p.get(self.E.PAGO_SALDO_RESTANTE.value, 0) or 0)
            except Exception:
                continue
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(fecha))),
                ft.DataCell(ft.Text(f"${monto:.2f}")),
                ft.DataCell(ft.Text(f"{interes_pct}%")),
                ft.DataCell(ft.Text(f"${interes_apl:.2f}")),
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
            column_spacing=18,
            data_row_max_height=36,
        )

        # Inputs
        self.interes_input = ft.TextField(
            label="Interés (%)",
            width=120,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=self._recalcular_montos if self.puede_editar else None,
            disabled=not self.puede_editar,
            value="10",
        )
        self.monto_input = ft.TextField(
            label="Monto a pagar",
            width=200,
            on_change=self._recalcular_montos if self.puede_editar else None,
            keyboard_type=ft.KeyboardType.NUMBER,
            disabled=not self.puede_editar,
            autofocus=self.puede_editar,
        )
        self.observaciones_input = ft.TextField(
            label="Observaciones",
            hint_text="Descripción adicional (opcional)",
            multiline=True,
            min_lines=2,
            max_lines=3,
            disabled=not self.puede_editar,
        )

        # Acción guardar (solo si editable)
        def _chip(label: str, icon, on_tap):
            return ft.GestureDetector(
                on_tap=lambda _: on_tap(),
                content=ft.Container(
                    padding=10,
                    border_radius=12,
                    bgcolor=ft.colors.SURFACE_VARIANT,
                    content=ft.Row(
                        [ft.Icon(icon, size=18), ft.Text(label, size=12, weight="bold")],
                        spacing=6, alignment=ft.MainAxisAlignment.CENTER
                    )
                )
            )

        self.boton_guardar = _chip("Guardar pago", ft.icons.SAVE, lambda: self._guardar()) if self.puede_editar else ft.Container()
        boton_cancelar = ft.TextButton("Cancelar", on_click=self._cerrar)

        # Layout
        self.dialog.content = ft.Container(
            padding=20,
            width=760,
            content=ft.Column(
                controls=[
                    ft.Text(f"Pago de préstamo • {self.nombre_empleado} (No. {self.numero_nomina})",
                            style=ft.TextThemeStyle.TITLE_MEDIUM),

                    ft.Divider(),
                    ft.Text("Historial reciente", weight=ft.FontWeight.BOLD),
                    tabla_historial,

                    ft.Divider(),
                    ft.Text("Aplicar pago", weight=ft.FontWeight.BOLD),
                    ft.Row([self.monto_input, self.interes_input], spacing=16),
                    self.lbl_preview,
                    self.observaciones_input,
                    self._info_resumen(),

                    ft.Row([self.boton_guardar, boton_cancelar],
                           alignment=ft.MainAxisAlignment.END, spacing=16),
                ],
                spacing=14,
            ),
        )

    def _info_resumen(self) -> ft.Text:
        self.resumen_text = ft.Text("", color=ft.colors.BLUE_GREY)
        return self.resumen_text

    # --------- Cálculo inline (preview) ----------
    def _calc_preview(self, monto: float, interes_pct: float) -> dict:
        # saldo actual desde DB (por si cambió) con fallback
        try:
            mx = self.pago_model.get_saldo_y_monto_prestamo(self.id_prestamo) or {}
            saldo_actual = float(mx.get("saldo_prestamo", self.saldo_restante))
        except Exception:
            saldo_actual = float(self.saldo_restante)

        interes_aplicado = round(saldo_actual * (interes_pct / 100.0), 2) if interes_pct > 0 else 0.0
        saldo_con_interes = round(saldo_actual + interes_aplicado, 2)
        pago_efectivo = min(max(monto, 0.0), saldo_con_interes)
        nuevo_saldo = round(saldo_con_interes - pago_efectivo, 2)

        # días de retraso: fecha_generacion → fecha_pago
        try:
            f_gen = datetime.strptime(self.fecha_generacion, "%Y-%m-%d")
            f_pag = datetime.strptime(self.fecha_pago_base, "%Y-%m-%d")
            dias_retraso = max((f_pag - f_gen).days, 0)
        except Exception:
            dias_retraso = 0

        return dict(
            saldo_actual=saldo_actual,
            interes_aplicado=interes_aplicado,
            saldo_con_interes=saldo_con_interes,
            nuevo_saldo=nuevo_saldo,
            dias_retraso=dias_retraso,
        )

    def _recalcular_montos(self, _=None):
        try:
            interes = float((self.interes_input.value or "0").replace(",", "."))
        except Exception:
            interes = 0.0
        try:
            monto = float((self.monto_input.value or "0").replace(",", "."))
        except Exception:
            monto = 0.0

        prev = self._calc_preview(monto=monto, interes_pct=interes)

        self.lbl_preview.value = (
            f"Saldo: ${prev['saldo_actual']:.2f} + interés ${prev['interes_aplicado']:.2f} = ${prev['saldo_con_interes']:.2f} | "
            f"Pago: ${monto:.2f} → saldo quedaría ${prev['nuevo_saldo']:.2f} (retraso: {prev['dias_retraso']} días)"
        )

        monto_valido = self.puede_editar and (monto > 0) and (monto <= prev["saldo_con_interes"])
        if self.puede_editar:
            self.monto_input.border_color = ft.colors.GREEN if monto_valido else ft.colors.RED

        try:
            total_hist = Decimal(str(self.total_pagado or 0))
            m = Decimal(str(monto or 0))
            restante = Decimal(str(prev["saldo_con_interes"])) - m
            self.resumen_text.value = f"💰 Total pagado: ${total_hist:.2f} | 💸 Este pago: ${m:.2f} | 🔚 Restante con interés: ${restante:.2f}"
        except Exception:
            self.resumen_text.value = f"💰 Total pagado: ${self.total_pagado:.2f} | 💸 Este pago: — | 🔚 Restante: —"

        self.page.update()

    # --------------- Guardado ----------------
    def _guardar(self):
        # Validar inputs
        try:
            interes = float((self.interes_input.value or "0").replace(",", "."))
        except Exception:
            ModalAlert.mostrar_info("Error", "Interés inválido.")
            return
        try:
            monto = float((self.monto_input.value or "0").replace(",", "."))
        except Exception:
            ModalAlert.mostrar_info("Error", "Monto inválido.")
            return

        prev = self._calc_preview(monto=monto, interes_pct=interes)
        saldo_con_interes = prev["saldo_con_interes"]
        if monto <= 0 or monto > saldo_con_interes:
            ModalAlert.mostrar_info("Error", "Monto fuera de rango.")
            return

        obs = (self.observaciones_input.value or "").strip()

        # Asegurar id_pago de nómina para registrar el pago real
        id_pago = self.pago_model.ensure_id_pago_nomina(self.numero_nomina, self.fecha_pago_base)
        if not id_pago:
            ModalAlert.mostrar_info("Error", "No se pudo crear/obtener el id_pago para registrar el pago.")
            return

        res = self.pago_model.add_payment(
            id_prestamo=self.id_prestamo,
            id_pago_nomina=id_pago,
            monto_pagado=round(monto, 2),
            fecha_pago=self.fecha_pago_base,
            fecha_generacion=self.fecha_generacion,
            interes_porcentaje=int(round(interes)),
            aplicado=True,
            fecha_real_pago=self.fecha_pago_base,
            observaciones=obs
        )

        if res.get("status") == "success":
            ModalAlert.mostrar_info("Éxito", res.get("message", "Pago aplicado correctamente."))
            self.dialog.open = False
            try:
                self.on_confirmar(None)
            finally:
                self.page.update()
        else:
            ModalAlert.mostrar_info("Error", res.get("message", "No se pudo aplicar el pago."))
            self.page.update()
