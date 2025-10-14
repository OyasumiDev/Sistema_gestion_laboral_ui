from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
import flet as ft
from decimal import Decimal

from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert
from app.views.containers.modal_descuentos import ModalDescuentos
from app.views.containers.modal_prestamos_nomina import ModalPrestamosNomina

from app.helpers.pagos.payment_table_builder import PaymentTableBuilder
from app.helpers.pagos.row_refresh import PaymentRowRefresh
from app.helpers.pagos.pagos_repo import PagosRepo
from app.helpers.pagos.payment_view_math import PaymentViewMath

# Modelos
from app.models.payment_model import PaymentModel
from app.models.loan_model import LoanModel
from app.models.descuento_detalles_model import DescuentoDetallesModel


class PagosPendientesEditables(ft.UserControl):
    """
    Reglas clave:
      - saldo: neto a pagar (monto_base - descuentos - préstamos) ANTES de dividir en depósito/efectivo.
      - pago_efectivo: parte en cash = max(total_vista - pago_deposito, 0).
      - Se persisten por separado: pago_deposito, pago_efectivo y saldo.
    """
    COL_KEYS = [
        "id_pago", "id_empleado", "nombre", "fecha_pago", "horas", "sueldo_hora",
        "monto_base", "descuentos", "prestamos", "saldo", "deposito",
        "efectivo", "total", "ediciones", "acciones", "estado",
    ]

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

        # Tabla base
        self.table: ft.DataTable = self.table_builder.build_table(self.COL_KEYS, rows=[])

    # ---------------- Ciclo de vida ----------------
    def did_mount(self):
        try:
            self.reload()
        except Exception:
            pass

    def get_control(self) -> ft.Control:
        return self.table

    def set_filters(self, *, id_empleado: str = "", id_pago: str = "") -> None:
        self.filters["id_empleado"] = (id_empleado or "").strip()
        self.filters["id_pago"] = (id_pago or "").strip()
        self.reload()

    def apply_filters(self, **kwargs): return self.set_filters(**kwargs)
    def filtrar(self, **kwargs): return self.set_filters(**kwargs)
    def refresh(self, **_): return self.reload()
    def load(self, **_): return self.reload()
    def render(self, **_): return self.reload()

    # ---------------- Render/recarga ----------------
    def reload(self) -> None:
        try:
            pagos = self.repo.listar_pagos(order_desc=True) or []
            pendientes = [p for p in pagos if str(p.get("estado", "")).lower() != "pagado"]
            pendientes = self._priorizar_por_filtros(pendientes, self.filters)

            self.table.rows.clear()
            if not pendientes:
                self.table.rows.append(
                    ft.DataRow(cells=[ft.DataCell(ft.Text("-")) for _ in range(len(self.COL_KEYS))])
                )
            else:
                for p in pendientes:
                    id_pago = int(p.get("id_pago_nomina") or p.get("id_pago"))
                    num_nomina = int(p.get("numero_nomina") or 0)
                    tiene_prestamo = bool(self.loan_model.get_prestamo_activo_por_empleado(num_nomina))

                    raw_dep = self._deposito_buffer.get(id_pago, p.get("pago_deposito", 0))
                    deposito_ui = self._sanitize_float(raw_dep)

                    calc = self.math.recalc_from_pago_row(p, deposito_ui)

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

    def build(self) -> ft.Control:
        return self.table

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
        id_pago = int(p.get("id_pago_nomina") or p.get("id_pago"))
        num = int(p.get("numero_nomina") or 0)
        nombre = str(p.get("nombre_completo") or p.get("nombre_empleado") or "")
        fecha_pago = str(p.get("fecha_pago") or "")
        horas = float(p.get("horas") or 0.0)
        sueldo_h = float(p.get("sueldo_por_hora") or 0.0)
        monto_base = float(p.get("monto_base") or 0.0)

        def money(v: float) -> str:
            return f"${float(v):,.2f}"

        # UI texts a partir de calc (sin mezclar efectivo con saldo)
        txts = {
            "id": ft.Text(str(id_pago), size=font),
            "num": ft.Text(str(num), size=font),
            "nombre": ft.Text(nombre, size=font),
            "fecha": ft.Text(fecha_pago, size=font),
            "horas": ft.Text(f"{horas:.2f}", size=font),
            "sueldo": ft.Text(money(sueldo_h), size=font),
            "base": ft.Text(money(monto_base), size=font),
            "desc": ft.Text(money(calc.get("descuentos_view", 0.0)), size=font),
            "prest": ft.Text(money(calc.get("prestamos_view", 0.0)), size=font),
            "saldo": ft.Text(money(calc.get("saldo_ajuste", 0.0)), size=font),  # neto a pagar
            "efectivo": ft.Text(money(calc.get("efectivo", 0.0)), size=font),   # cash (total - depósito)
            "total": ft.Text(money(calc.get("total_vista", 0.0)), size=font),   # total a pagar
        }

        tf_deposito = ft.TextField(
            value=f"{float(deposito_ui or 0):.2f}",
            width=90, height=28, text_align=ft.TextAlign.RIGHT, dense=True, text_size=font,
            on_change=lambda e, pid=id_pago: self._on_deposito_change_pend(pid, e.control.value),
            on_blur=lambda e, pid=id_pago: self._guardar_deposito_desde_ui_pend(pid),
            on_submit=lambda e, pid=id_pago: self._guardar_deposito_desde_ui_pend(pid),
        )

        # Botones de edición
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

        # Acciones
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
        row._id_pago = id_pago

        # Validación visual de depósito > total
        self.row_refresh.set_deposito_border_color(
            row, ft.colors.RED if deposito_ui > float(calc.get("total_vista", 0.0)) + 1e-9 else None
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

            p_db = self.repo.obtener_pago(id_pago_nomina)
            if not p_db:
                return

            # Valor de depósito desde buffer o DB
            raw = self._deposito_buffer.get(id_pago_nomina, None)
            deposito_ui = (
                self._sanitize_float(raw)
                if raw is not None
                else self._sanitize_float(p_db.get("pago_deposito", 0.0))
            )
            # Nunca negativo
            if deposito_ui < 0:
                deposito_ui = 0.0

            # Recalcular vista con datos actuales
            calc = self.math.recalc_from_pago_row(p_db, deposito_ui)

            # Derivar montos claros
            total_vista = float(calc.get("total_vista", 0.0))
            saldo_val = float(calc.get("saldo_ajuste", 0.0))   # neto a pagar
            efectivo_val = float(calc.get("efectivo", 0.0))    # cash
            # Clamp por seguridad si depósito > total
            if deposito_ui > total_vista + 1e-9:
                efectivo_val = 0.0

            # Refrescar UI (NO mezclar efectivo con saldo)
            self.row_refresh.set_descuentos(row, calc["descuentos_view"])
            self.row_refresh.set_prestamos(row, calc["prestamos_view"])
            self.row_refresh.set_saldo(row, saldo_val)
            self.row_refresh.set_efectivo(row, efectivo_val)
            self.row_refresh.set_total(row, total_vista)
            self.row_refresh.set_deposito_border_color(
                row, ft.colors.RED if deposito_ui > total_vista + 1e-9 else None
            )
            if getattr(row, "page", None):
                row.update()

            if not persist:
                return

            # Persistencia: depósito, efectivo y saldo por separado
            payload = {
                "pago_deposito": float(deposito_ui),
                "pago_efectivo": float(efectivo_val),
                "saldo": float(saldo_val),
            }

            ok = False
            try:
                if hasattr(self.repo, "actualizar_montos_ui"):
                    r = self.repo.actualizar_montos_ui(id_pago_nomina, payload)
                    ok = (r or {}).get("status") == "success"
                else:
                    ok = bool(self.payment_model.update_pago(id_pago_nomina, payload))
            except Exception as ex2:
                print(f"⚠️ Persistencia fallback: {ex2}")
                ok = False

            if not ok:
                ModalAlert.mostrar_info(
                    "Atención",
                    "No se pudo guardar depósito/efectivo/saldo en DB. Revisa PaymentModel/Repo."
                )
                return

            # Limpiar buffer y releer para reflejar desde DB
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

    # ---------------- util ----------------
    def _invalidate_caches(self):
        """
        Limpia caches de todos los modelos que participan en el recálculo de la fila:
        repo / payment / loans / borradores de descuento y los modelos internos de math.
        """
        objs = [self.repo, self.payment_model, self.loan_model, self.detalles_desc_model]
        # Intenta incluir submodelos inyectados en PaymentViewMath
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
        """Refresca de forma segura: sólo si la tabla ya está montada."""
        if getattr(self.table, "page", None):
            self.table.update()
        elif getattr(self, "page", None):
            try:
                self.page.update()
            except Exception:
                pass

    # ---------------- Acciones ----------------
    def _guardar_pago_confirmado(self, id_pago_nomina: int):
        try:
            res = self.repo.confirmar_pago(id_pago_nomina)
            if res.get("status") != "success" and hasattr(self.payment_model, "confirmar_pago"):
                res = self.payment_model.confirmar_pago(id_pago_nomina)

            if res.get("status") == "success":
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

                ModalAlert.mostrar_info("Éxito", res.get("message", "Pago confirmado."))

                self._invalidate_caches()
                if callable(self.on_data_changed):
                    try:
                        self.on_data_changed()
                    except Exception:
                        pass
            else:
                ModalAlert.mostrar_info("Error", res.get("message", "No fue posible confirmar el pago."))
        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo confirmar el pago: {str(ex)}")

    def _eliminar_pago(self, id_pago_nomina: int):
        def eliminar():
            try:
                res = self.repo.eliminar_pago(id_pago_nomina)
                if res.get("status") == "success":
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
                        self.on_data_changed()
                else:
                    ModalAlert.mostrar_info("Error", res.get("message", "No se pudo eliminar."))
            except Exception as ex:
                ModalAlert.mostrar_info("Error al eliminar", str(ex))

        ModalAlert(
            title_text="Eliminar Pago",
            message=f"¿Eliminar el pago #{id_pago_nomina} (pendiente)?",
            on_confirm=eliminar,
        ).mostrar()

    # ---------------- Modales ----------------
    def _abrir_modal_descuentos(self, pago_row: Dict[str, Any]):
        p = {
            "id_pago": int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago")),
            "numero_nomina": int(pago_row["numero_nomina"]),
            "estado": pago_row.get("estado"),
        }

        def on_ok(_):
            # Relee totales de descuentos/prestamos y refresca solo la fila
            self._refrescar_descuentos_y_totales(p["id_pago"])

        ModalDescuentos(pago_data=p, on_confirmar=on_ok).mostrar()

    def _abrir_modal_prestamos(self, pago_row: Dict[str, Any]):
        num = int(pago_row["numero_nomina"])
        pago_id = int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago"))

        prestamo_activo = self.loan_model.get_prestamo_activo_por_empleado(num)
        if not prestamo_activo:
            ModalAlert.mostrar_info("Sin préstamo", f"El empleado {num} no tiene préstamos activos.")
            return

        p = {"id_pago": pago_id, "numero_nomina": num, "estado": pago_row.get("estado")}

        def on_ok(_):
            # Recalcula usando DB fresca; refleja cambios en la fila
            self._refrescar_descuentos_y_totales(pago_id)

        ModalPrestamosNomina(pago_data=p, on_confirmar=on_ok).mostrar()

    # ---------------- Utils ----------------
    @staticmethod
    def _sanitize_float(v: Any) -> float:
        # Acepta Decimal, int, float o str; devuelve siempre float
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
                ok = ok and str(x.get("id_pago_nomina") or x.get("id_pago")).startswith(idp)
            return ok

        matching = [x for x in items if match(x)]
        non_matching = [x for x in items if not match(x)]
        return matching + non_matching

    def _refrescar_descuentos_y_totales(self, id_pago_nomina: int):
        try:
            self._invalidate_caches()
            p_db = self.repo.obtener_pago(id_pago_nomina) or {}
            if not p_db:
                r = getattr(self.payment_model, "get_by_id", lambda *_: {}) (id_pago_nomina) or {}
                p_db = r.get("data", {}) if isinstance(r, dict) else {}
            if not p_db:
                return

            raw = self._deposito_buffer.get(id_pago_nomina, None)
            deposito_ui = (
                self._sanitize_float(raw)
                if raw is not None
                else self._sanitize_float(p_db.get("pago_deposito", 0.0))
            )
            calc = self.math.recalc_from_pago_row(p_db, deposito_ui)

            row = self.row_refresh.get_row(self.table, id_pago_nomina)
            if not row:
                for r in self.table.rows:
                    if getattr(r, "_id_pago", None) == id_pago_nomina:
                        row = r
                        break
            if not row:
                return

            total_vista = float(calc.get("total_vista", 0.0))
            saldo_val = float(calc.get("saldo_ajuste", 0.0))
            efectivo_val = float(calc.get("efectivo", 0.0))
            if deposito_ui > total_vista + 1e-9:
                efectivo_val = 0.0

            self.row_refresh.set_descuentos(row, calc["descuentos_view"])
            self.row_refresh.set_prestamos(row, calc["prestamos_view"])
            self.row_refresh.set_saldo(row, saldo_val)
            self.row_refresh.set_efectivo(row, efectivo_val)
            self.row_refresh.set_total(row, total_vista)
            self.row_refresh.set_deposito_border_color(
                row, ft.colors.RED if deposito_ui > total_vista + 1e-9 else None
            )

            if getattr(row, "page", None):
                row.update()
            self._refresh_table()
        except Exception as ex:
            print(f"⚠️ refrescar descuentos/total (pend): {ex}")
