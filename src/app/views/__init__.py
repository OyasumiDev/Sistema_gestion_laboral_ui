import flet as ft
from datetime import date
from decimal import Decimal
from typing import Callable, Optional

from app.core.app_state import AppState
from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.detalles_pagos_prestamo_model import DetallesPagosPrestamoModel
from app.models.employes_model import EmployesModel
from app.views.containers.modal_alert import ModalAlert


class ModalPagoPrestamo:
    """
    Modal reutilizable para registrar pagos de préstamos.

    Modos de uso:
    - modo = "prestamos": se crea un pago real en LoanPaymentModel.
        Requiere: numero_nomina (int), id_prestamo (opcional si hay 1), on_ok (callback)
    - modo = "nomina": se guarda/actualiza el detalle ligado a un pago de nómina.
        Requiere: numero_nomina (int), id_pago_nomina (int), estado_pago (str), on_ok (callback)
    """

    def __init__(
        self,
        *,
        numero_nomina: int,
        id_prestamo: Optional[int] = None,
        id_pago_nomina: Optional[int] = None,
        estado_pago: Optional[str] = None,
        on_ok: Optional[Callable] = None,
        interes_opciones: tuple[int, ...] = (5, 10, 15),
    ) -> None:
        self.page = AppState().page
        self.numero_nomina = int(numero_nomina)
        self.id_prestamo = id_prestamo  # puede venir preseleccionado
        self.id_pago_nomina = id_pago_nomina
        self.estado_pago = (estado_pago or "").lower() if estado_pago else None
        self.on_ok = on_ok
        self.interes_opciones = interes_opciones

        # Modo
        self.modo = "nomina" if self.id_pago_nomina is not None else "prestamos"

        # Modelos
        self.loan_model = LoanModel()
        self.pago_model = LoanPaymentModel()
        self.detalles_model = DetallesPagosPrestamoModel()
        self.empleado_model = EmployesModel()

        # Estado / datos
        self.nombre_empleado = ""
        self.prestamos_disponibles: list[dict] = []
        self.pagos_ultimos: list[dict] = []
        self.saldo_restante = Decimal("0.00")
        self.total_pagado = Decimal("0.00")
        self.detalle_guardado = None
        self.puede_editar = True  # se ajusta luego

        # UI
        self.dialog = ft.AlertDialog(modal=True)
        self.dd_prestamo: Optional[ft.Dropdown] = None
        self.dd_interes: Optional[ft.Dropdown] = None
        self.tf_monto: Optional[ft.TextField] = None
        self.tf_fecha_prog: Optional[ft.TextField] = None
        self.tf_fecha_real: Optional[ft.TextField] = None
        self.tf_obs: Optional[ft.TextField] = None
        self.txt_saldo_int: Optional[ft.Text] = None
        self.txt_resumen: Optional[ft.Text] = None
        self.btn_guardar: Optional[ft.ElevatedButton] = None

        # Cargar y construir
        self._cargar_base()
        self._construir_modal()

    # ---------- API ----------
    def mostrar(self) -> None:
        if self.page and self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    # ---------- Carga de datos ----------
    def _cargar_base(self) -> None:
        # Empleado
        try:
            emp = self.empleado_model.get_by_numero_nomina(self.numero_nomina) or {}
            self.nombre_empleado = emp.get("nombre_completo", f"No. {self.numero_nomina}")
        except Exception:
            self.nombre_empleado = f"No. {self.numero_nomina}"

        # Préstamos del empleado
        try:
            self.prestamos_disponibles = self.loan_model.get_prestamos_por_empleado(self.numero_nomina) or []
        except Exception:
            self.prestamos_disponibles = []

        if not self.prestamos_disponibles:
            ModalAlert.mostrar_info("Sin préstamo", f"No hay préstamos para el empleado {self.numero_nomina}.")
            self.puede_editar = False
            return

        # Selección de préstamo
        if self.id_prestamo is None:
            # toma el primero
            self.id_prestamo = int(self.prestamos_disponibles[0]["id_prestamo"])

        self._refrescar_info_prestamo()

        # Reglas de edición (en modo nómina)
        if self.modo == "nomina":
            # Si ya está pagado o existe detalle pendiente, bloquear
            existe = False
            try:
                existe = self.pago_model.existe_pago_pendiente_para_pago_nomina(
                    id_pago_nomina=self.id_pago_nomina,
                    id_prestamo=self.id_prestamo,
                )
            except Exception:
                existe = False

            self.puede_editar = (self.estado_pago != "pagado") and (self.saldo_restante > 0) and (not existe)

            # Cargar detalle guardado (si existe)
            try:
                self.detalle_guardado = self.detalles_model.get_detalle(self.id_pago_nomina, self.id_prestamo)
            except Exception:
                self.detalle_guardado = None

    def _refrescar_info_prestamo(self) -> None:
        """ Actualiza saldo, pagos y totales según préstamo seleccionado. """
        p = next((x for x in self.prestamos_disponibles if int(x["id_prestamo"]) == int(self.id_prestamo)), None)
        if not p:
            return

        try:
            self.saldo_restante = Decimal(str(p.get("saldo_prestamo", "0")))
        except Exception:
            self.saldo_restante = Decimal("0.00")

        # Últimos pagos
        try:
            res = self.pago_model.get_by_id_prestamo(self.id_prestamo)
            data = (res or {}).get("data", []) if isinstance(res, dict) else (res or [])
            self.pagos_ultimos = data[-5:] if len(data) > 5 else data
            self.total_pagado = sum(Decimal(str(pp.get("monto_pagado", 0))) for pp in data)
        except Exception:
            self.pagos_ultimos = []
            self.total_pagado = Decimal("0.00")

    # ---------- UI ----------
    def _construir_modal(self) -> None:
        hoy_ui = date.today().strftime("%d/%m/%Y")

        # Dropdown de préstamos
        self.dd_prestamo = ft.Dropdown(
            label="Seleccionar préstamo",
            value=str(self.id_prestamo) if self.id_prestamo is not None else None,
            options=[
                ft.dropdown.Option(str(p["id_prestamo"]), f"ID {p['id_prestamo']} — Saldo: ${float(p['saldo_prestamo']):.2f}")
                for p in self.prestamos_disponibles
            ],
            width=360,
            disabled=not self.puede_editar,
            on_change=(lambda e: self._on_cambio_prestamo(int(e.control.value))) if self.puede_editar else None,
        )

        # Campos
        self.tf_monto = ft.TextField(label="Monto a pagar", width=180, keyboard_type=ft.KeyboardType.NUMBER, autofocus=True,
                                     on_change=self._recalcular_montos, disabled=not self.puede_editar)
        self.dd_interes = ft.Dropdown(
            label="Interés (%)", width=120,
            value=str(self.interes_opciones[1]) if self.interes_opciones else "0",
            options=[ft.dropdown.Option(str(x)) for x in self.interes_opciones],
            on_change=self._recalcular_montos if self.puede_editar else None,
            disabled=not self.puede_editar,
        )
        self.tf_fecha_prog = ft.TextField(label="Fecha programada (DD/MM/YYYY)", value=hoy_ui, width=220, disabled=not self.puede_editar)
        self.tf_fecha_real = ft.TextField(label="Fecha real (DD/MM/YYYY)", value=hoy_ui, width=220, disabled=not self.puede_editar)
        self.tf_obs = ft.TextField(label="Observaciones", multiline=True, min_lines=2, max_lines=3, width=560, disabled=not self.puede_editar)

        # Rótulos
        self.txt_saldo_int = ft.Text("Saldo + interés: -", weight=ft.FontWeight.BOLD)
        self.txt_resumen = ft.Text("", size=12)

        # Historial (últimos 5)
        tabla_historial = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Fecha")),
                ft.DataColumn(ft.Text("Monto")),
                ft.DataColumn(ft.Text("Interés (%)")),
                ft.DataColumn(ft.Text("Interés $")),
                ft.DataColumn(ft.Text("Saldo")),
            ],
            rows=[
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(p.get("fecha_pago") or p.get("fecha_real") or "-"))),
                    ft.DataCell(ft.Text(f"${float(p.get('monto_pagado', 0)):.2f}")),
                    ft.DataCell(ft.Text(str(p.get('interes_porcentaje', 0)))),
                    ft.DataCell(ft.Text(f"${float(p.get('interes_aplicado', 0)):.2f}")),
                    ft.DataCell(ft.Text(f"${float(p.get('saldo_restante', 0)):.2f}")),
                ]) for p in self.pagos_ultimos
            ],
            column_spacing=16,
            data_row_max_height=36,
        )

        # Prefill en modo nómina si había detalle guardado
        if self.modo == "nomina" and self.detalle_guardado:
            self.tf_monto.value = str(self.detalle_guardado.get("monto_guardado", ""))
            self.dd_interes.value = str(self.detalle_guardado.get("interes_guardado", ""))
            self.tf_obs.value = self.detalle_guardado.get("observaciones", "") or ""

        # Acciones
        self.btn_guardar = ft.ElevatedButton("Guardar", icon=ft.icons.SAVE, on_click=self._guardar, disabled=not self.puede_editar)
        acciones = ft.Row(
            controls=[*( [self.btn_guardar] if self.puede_editar else [] ), ft.TextButton("Cancelar", on_click=lambda _: self._cerrar())],
            alignment=ft.MainAxisAlignment.END,
        )

        # Armado del diálogo
        self.dialog.title = ft.Text(
            f"{'Detalle de pago (nómina)' if self.modo=='nomina' else 'Agregar pago'} — "
            f"{self.nombre_empleado} (No. {self.numero_nomina})",
            style=ft.TextThemeStyle.TITLE_MEDIUM
        )
        self.dialog.content = ft.Container(
            padding=18, width=720,
            content=ft.Column(
                spacing=12,
                controls=[
                    self.dd_prestamo,
                    ft.Divider(),
                    ft.Text("Últimos pagos", weight=ft.FontWeight.BOLD),
                    tabla_historial,
                    ft.Divider(),
                    ft.Text("Registrar pago", weight=ft.FontWeight.BOLD),
                    ft.Row([self.tf_monto, self.dd_interes, self.txt_saldo_int], spacing=16),
                    ft.Row([self.tf_fecha_prog, self.tf_fecha_real], spacing=16) if self.modo == "prestamos" else ft.Container(),
                    self.tf_obs,
                    self.txt_resumen,
                    acciones,
                ],
            ),
        )

        # Calcular valores iniciales
        self._recalcular_montos()

    def _on_cambio_prestamo(self, nuevo_id: int) -> None:
        self.id_prestamo = nuevo_id
        self._refrescar_info_prestamo()
        # Si hay detalle guardado para el nuevo préstamo (modo nómina), re-cargar
        if self.modo == "nomina":
            try:
                self.detalle_guardado = self.detalles_model.get_detalle(self.id_pago_nomina, self.id_prestamo)
            except Exception:
                self.detalle_guardado = None

            if self.detalle_guardado:
                self.tf_monto.value = str(self.detalle_guardado.get("monto_guardado", ""))
                self.dd_interes.value = str(self.detalle_guardado.get("interes_guardado", self.dd_interes.value))
                self.tf_obs.value = self.detalle_guardado.get("observaciones", "") or ""
            else:
                self.tf_monto.value = ""
                self.tf_obs.value = ""

        self._recalcular_montos()

    # ---------- Lógica de cálculo ----------
    def _recalcular_montos(self, _=None) -> None:
        try:
            interes = Decimal(str(self.dd_interes.value or "0"))
            saldo = self.saldo_restante.quantize(Decimal("0.01"))
            interes_aplicado = (saldo * interes / 100).quantize(Decimal("0.01"))
            saldo_total = (saldo + interes_aplicado).quantize(Decimal("0.01"))
            self.txt_saldo_int.value = f"Saldo + interés: ${saldo_total:.2f}"

            # Validar monto
            monto_ok = False
            try:
                monto = Decimal(str(self.tf_monto.value or "0")).quantize(Decimal("0.01"))
                restante = (saldo_total - monto).quantize(Decimal("0.01"))
                if monto > 0 and monto <= saldo_total and restante >= 0:
                    self.tf_monto.border_color = ft.colors.GREEN
                    monto_ok = True
                else:
                    self.tf_monto.border_color = ft.colors.RED
            except Exception:
                self.tf_monto.border_color = ft.colors.RED

            if self.btn_guardar:
                self.btn_guardar.disabled = not (self.puede_editar and monto_ok)

            # Resumen
            self.txt_resumen.value = (
                f"💰 Total pagado histórico: ${self.total_pagado:.2f} — "
                f"💸 Total por pagar tras este pago: ${(saldo_total - Decimal(str(self.tf_monto.value or 0))):.2f}"
                if (self.tf_monto.value or "").strip() else
                f"💰 Total pagado histórico: ${self.total_pagado:.2f}"
            )
        finally:
            self.page.update()

    # ---------- Guardar ----------
    def _guardar(self, _):
        if not self.puede_editar:
            return

        # Validaciones básicas
        try:
            monto = Decimal(str(self.tf_monto.value or "0")).quantize(Decimal("0.01"))
        except Exception:
            ModalAlert.mostrar_info("Error", "Monto inválido.")
            return
        if monto <= 0:
            ModalAlert.mostrar_info("Error", "El monto debe ser mayor a 0.")
            return

        interes_pct = int(self.dd_interes.value or "0")
        obs = (self.tf_obs.value or "").strip()

        if self.modo == "prestamos":
            # Fechas (obligatorias aquí)
            try:
                fecha_prog_sql = self._to_mysql(self.tf_fecha_prog.value)
                fecha_real_sql = self._to_mysql(self.tf_fecha_real.value)
            except Exception:
                ModalAlert.mostrar_info("Error", "Fecha inválida. Usa DD/MM/YYYY.")
                return

            payload = {
                "id_prestamo": int(self.id_prestamo),
                "monto_pagado": float(monto),
                "fecha_programada": fecha_prog_sql,
                "fecha_real": fecha_real_sql,
                "interes_porcentaje": interes_pct,
                "observaciones": obs,
            }
            res = self._insertar_pago_real(payload)
        else:
            # Modo nómina → upsert detalle
            payload = {
                "id_pago": int(self.id_pago_nomina),
                "id_prestamo": int(self.id_prestamo),
                "monto": float(monto),
                "interes": interes_pct,
                "observaciones": obs,
            }
            res = self._upsert_detalle_nomina(payload)

        if res.get("status") == "success":
            self.dialog.open = False
            self.page.update()
            ModalAlert.mostrar_info("Éxito", "Información guardada correctamente.")
            if callable(self.on_ok):
                try:
                    self.on_ok(None)
                except Exception:
                    pass
        else:
            ModalAlert.mostrar_info("Error", res.get("message", "No se pudo guardar."))

    # ---------- Helpers ----------
    def _cerrar(self) -> None:
        self.dialog.open = False
        self.page.update()

    @staticmethod
    def _to_mysql(ddmmyyyy: str) -> str:
        # Acepta "DD/MM/YYYY" o ya "YYYY-MM-DD"
        s = (ddmmyyyy or "").strip()
        if "-" in s and len(s) == 10:
            return s
        d, m, y = s.split("/")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    # Adaptadores a modelos -----------------------
    def _insertar_pago_real(self, datos: dict) -> dict:
        """
        Intenta distintos nombres en LoanPaymentModel.
        """
        candidates = ["add", "insert", "create", "add_payment", "save"]
        for name in candidates:
            fn = getattr(self.pago_model, name, None)
            if callable(fn):
                try:
                    out = fn(datos)
                except TypeError:
                    out = fn(**datos)
                if out is None:
                    return {"status": "error", "message": f"LoanPaymentModel.{name} devolvió None"}
                if isinstance(out, dict) and "status" in out:
                    return out
                return {"status": "success", "data": out}
        return {"status": "error", "message": "No existe método de inserción de pagos compatible en LoanPaymentModel."}

    def _upsert_detalle_nomina(self, datos: dict) -> dict:
        """
        Usa DetallesPagosPrestamoModel.upsert_detalle(id_pago, id_prestamo, monto, interes, observaciones)
        """
        try:
            fn = getattr(self.detalles_model, "upsert_detalle", None)
            if callable(fn):
                out = fn(**datos)
                if isinstance(out, dict) and "status" in out:
                    return out
                return {"status": "success", "data": out}
            return {"status": "error", "message": "No se encontró upsert_detalle en DetallesPagosPrestamoModel."}
        except Exception as ex:
            return {"status": "error", "message": f"Error al guardar detalle: {ex}"}
