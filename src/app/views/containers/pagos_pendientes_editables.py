from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from decimal import Decimal
import flet as ft

from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert
from app.views.containers.modal_descuentos import ModalDescuentos
from app.views.containers.modal_prestamos_nomina import ModalPrestamosNomina

from app.helpers.pagos.payment_table_builder import PaymentTableBuilder
from app.helpers.pagos.payment_row_builder import PaymentRowBuilder
from app.helpers.pagos.row_refresh import PaymentRowRefresh
from app.helpers.pagos.pagos_repo import PagosRepo
from app.helpers.pagos.payment_view_math import PaymentViewMath

# Modelos
from app.models.payment_model import PaymentModel
from app.models.loan_model import LoanModel
from app.models.descuento_detalles_model import DescuentoDetallesModel


class PagosPendientesEditables(ft.UserControl):
    """
    Reglas clave (alineadas con tu arquitectura):

    ✅ Descuentos (nuevo descuento_detalles):
      - El borrador vive en `descuento_detalles`.
      - El container NO aplica borrador a confirmados.
      - Solo el ModalDescuentos confirma (tabla `descuentos`) cuando el usuario lo decide.
      - La vista (DataTable) se recalcula con PaymentViewMath (que debe considerar borrador/confirmados).

    ✅ Confirmar pago (blindado):
      - Si existe borrador con descuentos aplicados y aún NO hay confirmados:
          -> BLOQUEA y obliga a abrir ModalDescuentos para confirmar.
      - Si no hay borrador aplicado (o ya hay confirmados):
          -> permite confirmar pago.

    ✅ Depósito/efectivo/saldo:
      - UI recalcula con PaymentViewMath.
      - Persistencia SOLO de: pago_deposito, pago_efectivo, saldo (regla $50) vía repo.actualizar_montos_ui().
      - Nunca tocar pagos pagados desde este módulo.
    """

    COL_KEYS = [
        "id_pago", "id_empleado", "nombre", "fecha_pago", "horas", "sueldo_hora",
        "monto_base", "descuentos", "prestamos", "saldo", "deposito",
        "efectivo", "total", "ediciones", "acciones", "estado",
    ]

    # ---------------- Init ----------------
    def __init__(
        self,
        *,
        repo: PagosRepo,
        payment_model: PaymentModel,
        math: PaymentViewMath,
        loan_model: LoanModel,
        detalles_desc_model: DescuentoDetallesModel,
        table_builder: PaymentTableBuilder,
        row_refresh: PaymentRowRefresh,
        on_data_changed: Optional[Callable[[], None]] = None,
        on_pago_confirmado: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_pago_eliminado: Optional[Callable[[int], None]] = None,
    ):
        super().__init__()

        # OJO: igual guardo referencia, pero el modal se abrirá con self.page real cuando exista.
        self.page = AppState().page

        # Inyección
        self.repo = repo
        self.payment_model = payment_model
        self.math = math
        self.loan_model = loan_model
        self.detalles_desc_model = detalles_desc_model
        self.table_builder = table_builder
        self.row_refresh = row_refresh

        # Callbacks
        self.on_data_changed = on_data_changed
        self.on_pago_confirmado = on_pago_confirmado
        self.on_pago_eliminado = on_pago_eliminado

        # Estado
        self.filters: Dict[str, str] = {"id_empleado": "", "id_pago": ""}
        self._deposito_buffer: Dict[int, Any] = {}
        self._saving_rows: set[int] = set()

        sort_state = AppState().get("pagos.sort.pend", {"key": "id_pago", "asc": False})
        self.sort_key: str = str(sort_state.get("key") or "id_pago")
        self.sort_asc: bool = bool(sort_state.get("asc", False))

        # Tabla base
        self.table: ft.DataTable = self.table_builder.build_table(
            self.COL_KEYS,
            rows=[],
            on_sort=self._handle_sort_event,
            sort_key=self.sort_key,
            sort_ascending=self.sort_asc,
        )

    # ---------------- Ciclo de vida ----------------
    def did_mount(self):
        # Asegura page real del control (Flet suele setearla ya montado)
        try:
            if getattr(self, "page", None) is None:
                self.page = AppState().page
        except Exception:
            pass

        try:
            self.reload()
        except Exception:
            pass

    def get_control(self) -> ft.Control:
        return self.table

    def build(self) -> ft.Control:
        return self.table

    # ---------------- Filtros / Orden ----------------
    def set_filters(self, *, id_empleado: str = "", id_pago: str = "") -> None:
        self.filters["id_empleado"] = (id_empleado or "").strip()
        self.filters["id_pago"] = (id_pago or "").strip()
        self.reload()

    def apply_filters(self, **kwargs): return self.set_filters(**kwargs)
    def filtrar(self, **kwargs): return self.set_filters(**kwargs)
    def refresh(self, **_): return self.reload()
    def load(self, **_): return self.reload()
    def render(self, **_): return self.reload()

    def _handle_sort_event(self, column_key: str, ascending: bool) -> None:
        self.set_sort_state(column_key, ascending)
        self.reload()

    def get_sort_state(self) -> Dict[str, Any]:
        return {"key": self.sort_key, "asc": self.sort_asc}

    def set_sort_state(self, key: str, asc: bool) -> None:
        allowed = {"id_pago", "id_empleado", "fecha_pago", "horas", "monto_base", "total"}
        self.sort_key = key if key in allowed else "id_pago"
        self.sort_asc = bool(asc)
        AppState().set("pagos.sort.pend", self.get_sort_state())
        root_state = dict(AppState().get("pagos.sort", {}))
        root_state["pend"] = self.get_sort_state()
        AppState().set("pagos.sort", root_state)

    # ---------------- Helpers estado ----------------
    @staticmethod
    def _is_pagado_like(estado: str) -> bool:
        st = str(estado or "").strip().lower()
        return st in ("pagado", "cerrado", "cancelado")

    # ---------------- Render/recarga ----------------
    def reload(self) -> None:
        try:
            pagos = self.repo.listar_pagos(
                order_desc=True,
                sort_key=self.sort_key,
                sort_asc=self.sort_asc,
                filtros=self.filters,
                compute_total=lambda r: float(self._compute_total_vista_for_sort(r)),
            ) or []

            pendientes = [p for p in pagos if not self._is_pagado_like(str(p.get("estado", "")))]
            pendientes = self._priorizar_por_filtros(pendientes, self.filters)

            self.table.rows.clear()

            if not pendientes:
                self.table.rows.append(
                    ft.DataRow(cells=[ft.DataCell(ft.Text("-")) for _ in range(len(self.COL_KEYS))])
                )
                self._refresh_table()
                return

            for p in pendientes:
                id_pago = int(p.get("id_pago_nomina") or p.get("id_pago") or 0)
                num_nomina = int(p.get("numero_nomina") or 0)

                # UX: asegurar borrador si usas esa experiencia (no aplica confirmados)
                try:
                    self.repo.ensure_borrador_descuentos(id_pago)
                except Exception:
                    pass

                try:
                    tiene_prestamo = bool(self.loan_model.get_prestamo_activo_por_empleado(num_nomina))
                except Exception:
                    tiene_prestamo = False

                raw_dep = self._deposito_buffer.get(id_pago, p.get("pago_deposito", 0))
                deposito_ui = self._sanitize_float(raw_dep)

                calc = self._recalc_row(p, deposito_ui)

                row = self._build_row_edicion_compacta(
                    p=p,
                    deposito_ui=deposito_ui,
                    calc=calc,
                    tiene_prestamo_activo=tiene_prestamo,
                )
                self.table.rows.append(row)

            self._refresh_table()

        except Exception as ex:
            ModalAlert.mostrar_info("Error al cargar pendientes", str(ex))

    def _compute_total_vista_for_sort(self, p_row: Dict[str, Any]) -> float:
        try:
            dep = self._sanitize_float(p_row.get("pago_deposito", 0.0))
            calc = self._recalc_row(p_row, dep)
            return float(calc.get("total_vista", 0.0))
        except Exception:
            return 0.0

    # -------------------- Fila editable --------------------
    def _build_row_edicion_compacta(
        self,
        *,
        p: Dict[str, Any],
        deposito_ui: float,
        calc: Dict[str, float],
        tiene_prestamo_activo: bool,
    ) -> ft.DataRow:
        font = 11
        id_pago = int(p.get("id_pago_nomina") or p.get("id_pago") or 0)
        num = int(p.get("numero_nomina") or 0)
        nombre = str(p.get("nombre_completo") or p.get("nombre_empleado") or "")
        fecha_pago = str(p.get("fecha_pago") or "")
        horas = float(p.get("horas") or 0.0)
        sueldo_h = float(p.get("sueldo_por_hora") or 0.0)
        monto_base = float(p.get("monto_base") or 0.0)

        def money(v: float) -> str:
            return f"${float(v):,.2f}"

        txts = {
            "id": ft.Text(str(id_pago), size=font),
            "num": ft.Text(str(num), size=font),
            "nombre": ft.Text(nombre, size=font),
            "fecha": ft.Text(fecha_pago, size=font),
            "horas": ft.Text(PaymentRowBuilder.format_horas(horas), size=font, tooltip=f"{horas:.4f}"),
            "sueldo": ft.Text(money(sueldo_h), size=font),
            "base": ft.Text(money(monto_base), size=font),

            "desc": ft.Text(money(calc.get("descuentos_view", 0.0)), size=font),
            "prest": ft.Text(money(calc.get("prestamos_view", 0.0)), size=font),
            "saldo": ft.Text(money(calc.get("saldo_ajuste", 0.0)), size=font),
            "efectivo": ft.Text(money(calc.get("efectivo", 0.0)), size=font),
            "total": ft.Text(money(calc.get("total_vista", 0.0)), size=font),
        }

        tf_deposito = ft.TextField(
            value=f"{float(deposito_ui or 0):.2f}",
            width=90,
            height=28,
            text_align=ft.TextAlign.RIGHT,
            dense=True,
            text_size=font,
            on_change=lambda e, pid=id_pago: self._on_deposito_change_pend(pid, e.control.value),
            on_blur=lambda e, pid=id_pago: self._guardar_deposito_desde_ui_pend(pid),
            on_submit=lambda e, pid=id_pago: self._guardar_deposito_desde_ui_pend(pid),
        )

        btn_desc = ft.IconButton(
            icon=ft.icons.REMOVE_CIRCLE_OUTLINE,
            tooltip="Editar descuentos",
            icon_color=ft.colors.AMBER_700,
            on_click=lambda e, pago_row=p: self._abrir_modal_descuentos(pago_row),
        )

        btn_prest = ft.IconButton(
            icon=ft.icons.ACCOUNT_BALANCE_WALLET,
            tooltip="Editar préstamos" if tiene_prestamo_activo else "Sin préstamo activo",
            icon_color=ft.colors.BLUE_600 if tiene_prestamo_activo else ft.colors.GREY_400,
            disabled=not tiene_prestamo_activo,
            on_click=(lambda e, pago_row=p: self._abrir_modal_prestamos(pago_row)) if tiene_prestamo_activo else None,
        )

        ediciones_cell = ft.Row([btn_desc, btn_prest], spacing=4)

        btn_confirmar = ft.IconButton(
            icon=ft.icons.CHECK,
            icon_color=ft.colors.GREEN_600,
            tooltip="Confirmar pago",
            on_click=lambda e, pid=id_pago: self._guardar_pago_confirmado(pid),
        )
        btn_eliminar = ft.IconButton(
            icon=ft.icons.DELETE_OUTLINE,
            icon_color=ft.colors.RED_500,
            tooltip="Eliminar pago",
            on_click=lambda e, pid=id_pago: self._eliminar_pago(pid),
        )

        acciones_cell = ft.Row([btn_confirmar, btn_eliminar], spacing=4)

        estado_chip = ft.Container(
            content=ft.Text("PENDIENTE", size=10),
            bgcolor=ft.colors.GREY_200,
            padding=ft.padding.symmetric(4, 6),
            border_radius=6,
        )

        row = ft.DataRow(
            cells=[
                ft.DataCell(txts["id"]),
                ft.DataCell(txts["num"]),
                ft.DataCell(txts["nombre"]),
                ft.DataCell(txts["fecha"]),
                ft.DataCell(txts["horas"]),
                ft.DataCell(txts["sueldo"]),
                ft.DataCell(txts["base"]),
                ft.DataCell(txts["desc"]),
                ft.DataCell(txts["prest"]),
                ft.DataCell(txts["saldo"]),
                ft.DataCell(tf_deposito),
                ft.DataCell(txts["efectivo"]),
                ft.DataCell(txts["total"]),
                ft.DataCell(ediciones_cell),
                ft.DataCell(acciones_cell),
                ft.DataCell(estado_chip),
            ]
        )

        self.row_refresh.register_row(
            id_pago,
            row,
            txt_desc=txts["desc"],
            txt_prest=txts["prest"],
            txt_saldo=txts["saldo"],
            tf_deposito=tf_deposito,
            txt_efectivo=txts["efectivo"],
            txt_total=txts["total"],
            estado_chip=estado_chip,
        )
        row._id_pago = id_pago  # type: ignore[attr-defined]

        self.row_refresh.set_deposito_border_color(
            row, ft.colors.RED if bool(calc.get("deposito_excede_total", False)) else None
        )
        return row

    # ---------------- Depósito (UI) ----------------
    def _on_deposito_change_pend(self, id_pago: int, value: str):
        self._deposito_buffer[id_pago] = value or ""
        try:
            self._actualizar_fila(id_pago, persist=False)
        except Exception as ex:
            print(f"⚠️ recalculo UI (pend): {ex}")

    def _actualizar_fila(self, id_pago_nomina: int, *, persist: bool):
        try:
            row = self.row_refresh.get_row(self.table, id_pago_nomina)
            if not row:
                for r in self.table.rows:
                    if getattr(r, "_id_pago", None) == id_pago_nomina:
                        row = r
                        break
            if not row:
                return

            p_db = self.repo.obtener_pago(id_pago_nomina) or {}
            if not p_db:
                return

            st = str(p_db.get("estado") or "").strip().lower()
            if self._is_pagado_like(st):
                return

            raw = self._deposito_buffer.get(id_pago_nomina, None)
            deposito_ui = (
                self._sanitize_float(raw)
                if raw is not None
                else self._sanitize_float(p_db.get("pago_deposito", 0.0))
            )
            if deposito_ui < 0:
                deposito_ui = 0.0

            calc = self._recalc_row(p_db, deposito_ui)

            self.row_refresh.set_descuentos(row, float(calc.get("descuentos_view", 0.0)))
            self.row_refresh.set_prestamos(row, float(calc.get("prestamos_view", 0.0)))
            self.row_refresh.set_saldo(row, float(calc.get("saldo_ajuste", 0.0)))
            self.row_refresh.set_efectivo(row, float(calc.get("efectivo", 0.0)))
            self.row_refresh.set_total(row, float(calc.get("total_vista", 0.0)))

            self.row_refresh.set_deposito_border_color(
                row, ft.colors.RED if bool(calc.get("deposito_excede_total", False)) else None
            )

            if getattr(row, "page", None):
                row.update()

            if not persist:
                return

            if bool(calc.get("deposito_excede_total", False)):
                ModalAlert.mostrar_info(
                    "Depósito inválido",
                    "El depósito excede el total neto a pagar. Corrige el depósito para poder guardar.",
                )
                return

            payload = {
                "pago_deposito": float(calc.get("deposito", deposito_ui) or 0.0),
                "pago_efectivo": float(calc.get("efectivo", 0.0) or 0.0),
                "saldo": float(calc.get("saldo_ajuste", 0.0) or 0.0),
            }

            r = self.repo.actualizar_montos_ui(id_pago_nomina, payload)
            ok = (r or {}).get("status") == "success"

            if not ok:
                ModalAlert.mostrar_info(
                    "Atención",
                    "No se pudo guardar depósito/efectivo/saldo en DB. Revisa PaymentModel/Repo.",
                )
                return

            self._deposito_buffer.pop(id_pago_nomina, None)
            self._actualizar_fila(id_pago_nomina, persist=False)

        except Exception as ex:
            print(f"❌ Error al actualizar fila: {ex}")

    def _guardar_deposito_desde_ui_pend(self, id_pago_nomina: int):
        if id_pago_nomina in self._saving_rows:
            return
        self._saving_rows.add(id_pago_nomina)
        try:
            self._actualizar_fila(id_pago_nomina, persist=True)
        finally:
            self._saving_rows.discard(id_pago_nomina)

    # ---------------- Confirmar pago (blindado) ----------------
    def _guardar_pago_confirmado(self, id_pago_nomina: int):
        try:
            p_db = self.repo.obtener_pago(id_pago_nomina) or {}
            if not p_db:
                ModalAlert.mostrar_info("Error", "No se encontró el pago.")
                return

            st = str(p_db.get("estado") or "").strip().lower()
            if self._is_pagado_like(st):
                ModalAlert.mostrar_info("Atención", "El pago ya está cerrado/pagado.")
                return

            raw = self._deposito_buffer.get(id_pago_nomina, None)
            deposito_ui = self._sanitize_float(raw) if raw is not None else self._sanitize_float(p_db.get("pago_deposito", 0.0))
            calc = self._recalc_row(p_db, deposito_ui)
            if bool(calc.get("deposito_excede_total", False)):
                ModalAlert.mostrar_info("Depósito inválido", "Corrige el depósito (no puede exceder el total neto).")
                return

            if self._requiere_confirmar_descuentos_en_modal(id_pago_nomina):
                ModalAlert.mostrar_info(
                    "Falta confirmar descuentos",
                    "Hay descuentos en borrador. Abre el modal de descuentos y confirma antes de confirmar el pago.",
                )
                self._abrir_modal_descuentos(p_db)
                return

            res = self.repo.confirmar_pago(id_pago_nomina)
            if (res or {}).get("status") != "success" and hasattr(self.payment_model, "confirmar_pago"):
                res = self.payment_model.confirmar_pago(id_pago_nomina)

            if (res or {}).get("status") == "success":
                self._invalidate_caches()

                pago_ok = self.repo.obtener_pago(id_pago_nomina) or {}
                if callable(self.on_pago_confirmado):
                    try:
                        self.on_pago_confirmado(pago_ok)
                    except Exception as ex_push:
                        print(f"⚠️ push pagado -> expansible: {ex_push}")

                self._deposito_buffer.pop(id_pago_nomina, None)

                row = self.row_refresh.get_row(self.table, id_pago_nomina)
                if not row:
                    for r in list(self.table.rows):
                        if getattr(r, "_id_pago", None) == id_pago_nomina:
                            row = r
                            break
                if row and row in self.table.rows:
                    self.table.rows.remove(row)

                if not self.table.rows:
                    self.table.rows.append(
                        ft.DataRow(cells=[ft.DataCell(ft.Text("-")) for _ in range(len(self.COL_KEYS))])
                    )

                self._refresh_table()
                ModalAlert.mostrar_info("Éxito", (res or {}).get("message", "Pago confirmado."))

                if callable(self.on_data_changed):
                    try:
                        self.on_data_changed()
                    except Exception:
                        pass
            else:
                ModalAlert.mostrar_info("Error", (res or {}).get("message", "No fue posible confirmar el pago."))

        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo confirmar el pago: {str(ex)}")

    def _requiere_confirmar_descuentos_en_modal(self, id_pago: int) -> bool:
        """
        True si:
          - NO hay confirmados (si PaymentViewMath lo detecta)
          - existe borrador con al menos un descuento aplicado (imss/transporte/extra)
        """
        try:
            has_conf = getattr(self.math, "_has_descuentos_confirmados", None)
            if callable(has_conf):
                try:
                    if bool(has_conf(int(id_pago))):
                        return False
                except Exception:
                    pass

            det = self.detalles_desc_model.obtener_por_id_pago(int(id_pago)) or {}
            if not det:
                return False

            flags = [
                bool(det.get(self.detalles_desc_model.COL_APLICADO_IMSS, False)),
                bool(det.get(self.detalles_desc_model.COL_APLICADO_TRANSPORTE, False)),
                bool(det.get(self.detalles_desc_model.COL_APLICADO_EXTRA, False)),
            ]
            return any(flags)
        except Exception:
            return False

    # ---------------- Eliminar ----------------
    def _eliminar_pago(self, id_pago_nomina: int):
        def eliminar():
            try:
                res = self.repo.eliminar_pago(id_pago_nomina)
                if (res or {}).get("status") == "success":
                    self._invalidate_caches()

                    self._deposito_buffer.pop(id_pago_nomina, None)
                    row = self.row_refresh.get_row(self.table, id_pago_nomina)
                    if not row:
                        for r in list(self.table.rows):
                            if getattr(r, "_id_pago", None) == id_pago_nomina:
                                row = r
                                break
                    if row and row in self.table.rows:
                        self.table.rows.remove(row)

                    if not self.table.rows:
                        self.table.rows.append(
                            ft.DataRow(cells=[ft.DataCell(ft.Text("-")) for _ in range(len(self.COL_KEYS))])
                        )

                    self._refresh_table()

                    if callable(self.on_pago_eliminado):
                        try:
                            self.on_pago_eliminado(id_pago_nomina)
                        except Exception:
                            pass

                    if callable(self.on_data_changed):
                        try:
                            self.on_data_changed()
                        except Exception:
                            pass
                else:
                    ModalAlert.mostrar_info("Error", (res or {}).get("message", "No se pudo eliminar."))
            except Exception as ex:
                ModalAlert.mostrar_info("Error al eliminar", str(ex))

        ModalAlert(
            title_text="Eliminar Pago",
            message=f"¿Eliminar el pago #{id_pago_nomina} (pendiente)?",
            on_confirm=eliminar,
        ).mostrar()

    # ---------------- Modales ----------------
    def _abrir_modal_descuentos(self, pago_row: Dict[str, Any]):
        id_pago = int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago") or 0)
        if id_pago <= 0:
            return

        # Payload canónico (sin comida)
        p = {
            "id_pago_nomina": id_pago,
            "id_pago": id_pago,  # compat
            "numero_nomina": int(pago_row.get("numero_nomina") or 0),
            "estado": str(pago_row.get("estado") or ""),
            "nombre_empleado": pago_row.get("nombre_empleado") or pago_row.get("nombre") or "",
            "monto_base": pago_row.get("monto_base") or pago_row.get("monto_bruto") or pago_row.get("monto") or 0,
            "monto_prestamo": pago_row.get("monto_prestamo") or pago_row.get("prestamo") or 0,
        }

        # UX: asegurar borrador
        try:
            self.repo.ensure_borrador_descuentos(id_pago)
        except Exception:
            pass

        # initial_state SOLO UX
        try:
            initial_state = self._build_descuentos_initial_state(id_pago) or {}
        except Exception:
            initial_state = {}

        def on_ok(payload: Optional[Dict[str, Any]] = None):
            payload = payload or {}

            # UX inmediato (si el modal envía totales)
            try:
                if int(payload.get("id_pago") or payload.get("id_pago_nomina") or 0) == id_pago:
                    if "monto_descuento" in payload:
                        pago_row["monto_descuento"] = float(payload.get("monto_descuento") or 0.0)
                    if "monto_total" in payload:
                        pago_row["monto_total"] = float(payload.get("monto_total") or 0.0)
            except Exception:
                pass

            # Fuente de verdad: refrescar con DB + caches
            self._refrescar_fila_post_modal(id_pago)

        dlg = ModalDescuentos(pago_data=p, on_confirmar=on_ok, initial_state=initial_state)

        # Abrir con page real
        try:
            dlg.mostrar(self.page)
        except TypeError:
            dlg.mostrar()

    def _abrir_modal_prestamos(self, pago_row: Dict[str, Any]):
        num = int(pago_row.get("numero_nomina") or 0)
        pago_id = int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago") or 0)

        prestamo_activo = self.loan_model.get_prestamo_activo_por_empleado(num)
        if not prestamo_activo:
            ModalAlert.mostrar_info("Sin préstamo", f"El empleado {num} no tiene préstamos activos.")
            return

        p = {"id_pago_nomina": pago_id, "id_pago": pago_id, "numero_nomina": num, "estado": pago_row.get("estado")}

        def on_ok(_payload=None):
            self._refrescar_fila_post_modal(pago_id)

        dlg = ModalPrestamosNomina(pago_data=p, on_confirmar=on_ok)
        try:
            dlg.mostrar(self.page)
        except TypeError:
            dlg.mostrar()

    # ---------------- Recalc consistente ----------------
    def _recalc_row(self, p_row: Dict[str, Any], deposito_ui: float) -> Dict[str, float]:
        """
        Fuente única de cálculo de vista: PaymentViewMath.
        (Debe contemplar confirmados o borrador según tu lógica interna.)
        """
        try:
            calc = self.math.recalc_from_pago_row(p_row, float(deposito_ui or 0.0)) or {}
        except Exception:
            calc = {}

        return {
            "descuentos_view": float(calc.get("descuentos_view", 0.0) or 0.0),
            "prestamos_view": float(calc.get("prestamos_view", 0.0) or 0.0),
            "total_vista": float(calc.get("total_vista", 0.0) or 0.0),
            "deposito": float(calc.get("deposito", float(deposito_ui or 0.0)) or 0.0),
            "efectivo": float(calc.get("efectivo", 0.0) or 0.0),
            "saldo_ajuste": float(calc.get("saldo_ajuste", 0.0) or 0.0),
            "deposito_excede_total": bool(calc.get("deposito_excede_total", False)),
        }

    def _refrescar_fila_post_modal(self, id_pago_nomina: int):
        """
        Se llama al cerrar modal de descuentos / préstamos.
        Refresca la fila usando DB (sin recargar toda la tabla).
        """
        try:
            self._invalidate_caches()

            p_db = self.repo.obtener_pago(id_pago_nomina) or {}
            if not p_db:
                r = getattr(self.payment_model, "get_by_id", lambda *_: {})(id_pago_nomina) or {}
                p_db = r.get("data", {}) if isinstance(r, dict) else {}

            if not p_db:
                return

            raw = self._deposito_buffer.get(id_pago_nomina, None)
            deposito_ui = (
                self._sanitize_float(raw)
                if raw is not None
                else self._sanitize_float(p_db.get("pago_deposito", 0.0))
            )
            calc = self._recalc_row(p_db, deposito_ui)

            row = self.row_refresh.get_row(self.table, id_pago_nomina)
            if not row:
                for rr in self.table.rows:
                    if getattr(rr, "_id_pago", None) == id_pago_nomina:
                        row = rr
                        break
            if not row:
                return

            self.row_refresh.set_descuentos(row, float(calc.get("descuentos_view", 0.0)))
            self.row_refresh.set_prestamos(row, float(calc.get("prestamos_view", 0.0)))
            self.row_refresh.set_saldo(row, float(calc.get("saldo_ajuste", 0.0)))
            self.row_refresh.set_efectivo(row, float(calc.get("efectivo", 0.0)))
            self.row_refresh.set_total(row, float(calc.get("total_vista", 0.0)))
            self.row_refresh.set_deposito_border_color(
                row, ft.colors.RED if bool(calc.get("deposito_excede_total", False)) else None
            )

            if getattr(row, "page", None):
                row.update()
            self._refresh_table()

        except Exception as ex:
            print(f"⚠️ refrescar fila post modal (pend): {ex}")

    # ---------------- initial_state (solo UX) ----------------
    def _build_descuentos_initial_state(self, id_pago_nomina: int) -> Dict[str, Any]:
        """
        Estado inicial SOLO para prellenar UI.
        Respeta el schema REAL de descuento_detalles:
          - aplicado_imss / monto_imss
          - aplicado_transporte / monto_transporte
          - aplicado_extra / descripcion_extra / monto_extra
        """
        try:
            det = self.detalles_desc_model.obtener_por_id_pago(int(id_pago_nomina))
            if det:
                return {
                    "aplicado_imss": bool(det.get(self.detalles_desc_model.COL_APLICADO_IMSS, False)),
                    "monto_imss": det.get(self.detalles_desc_model.COL_MONTO_IMSS),

                    "aplicado_transporte": bool(det.get(self.detalles_desc_model.COL_APLICADO_TRANSPORTE, False)),
                    "monto_transporte": det.get(self.detalles_desc_model.COL_MONTO_TRANSPORTE),

                    "aplicado_extra": bool(det.get(self.detalles_desc_model.COL_APLICADO_EXTRA, False)),
                    "monto_extra": det.get(self.detalles_desc_model.COL_MONTO_EXTRA),
                    "descripcion_extra": det.get(self.detalles_desc_model.COL_DESCRIPCION_EXTRA),
                }
        except Exception:
            pass

        # Defaults SOLO UX (si no existe borrador)
        default_imss = float(getattr(self.detalles_desc_model, "DEFAULT_IMSS", 0.0))
        default_trans = float(getattr(self.detalles_desc_model, "DEFAULT_TRANSPORTE", 0.0))

        return {
            "aplicado_imss": bool(default_imss > 0),
            "monto_imss": default_imss if default_imss > 0 else None,

            "aplicado_transporte": bool(default_trans > 0),
            "monto_transporte": default_trans if default_trans > 0 else None,

            "aplicado_extra": False,
            "monto_extra": None,
            "descripcion_extra": None,
        }

    # ---------------- util ----------------
    def _invalidate_caches(self):
        objs = [self.repo, self.payment_model, self.loan_model, self.detalles_desc_model]
        for attr in ("discount_model", "detalles_desc_model", "loan_payment_model", "detalles_prestamo_model"):
            m = getattr(self.math, attr, None)
            if m:
                objs.append(m)

        for obj in objs:
            for name in ("invalidate_cache", "clear_cache", "reset_cache", "refresh_cache"):
                fn = getattr(obj, name, None)
                if callable(fn):
                    try:
                        fn()
                    except Exception:
                        pass

    def _refresh_table(self):
        if getattr(self.table, "page", None):
            self.table.update()
        elif getattr(self, "page", None):
            try:
                self.page.update()
            except Exception:
                pass

    # ---------------- Utils ----------------
    @staticmethod
    def _sanitize_float(v: Any) -> float:
        if v is None:
            return 0.0
        if isinstance(v, (int, float, Decimal)):
            return float(v)
        s = str(v)
        try:
            s = s.strip().replace(",", "")
        except Exception:
            pass
        if s in ("", ".", "-", "-.", "+", "+."):
            return 0.0
        try:
            return float(s)
        except Exception:
            return 0.0

    @staticmethod
    def _priorizar_por_filtros(items: List[Dict[str, Any]], filtros: Dict[str, str]) -> List[Dict[str, Any]]:
        ide = (filtros.get("id_empleado") or "").strip()
        idp = (filtros.get("id_pago") or "").strip()

        def match(x: Dict[str, Any]) -> bool:
            ok = True
            if ide:
                ok = ok and str(x.get("numero_nomina", "")).startswith(ide)
            if idp:
                ok = ok and str(x.get("id_pago_nomina") or x.get("id_pago") or "").startswith(idp)
            return ok

        matching = [x for x in items if match(x)]
        non_matching = [x for x in items if not match(x)]
        return matching + non_matching
