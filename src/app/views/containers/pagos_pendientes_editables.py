# UI: columna "Ediciones" removida, Acciones unificado (Descuentos, Préstamos, Confirmar, Borrar)
# Mantiene recálculos sin cambios: NO se toca math/repo/DB/refresh; solo reubicación UI y estructura de tabla.
# Fix Flet 0.24: hit-test robusto para IconButtons en filas compactas (Container 28x28 + padding 0).
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Union
from decimal import Decimal
import inspect
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
from app.helpers.pagos.sorting_filter_payment_helper import PaymentSortFilterHelper

from app.models.payment_model import PaymentModel
from app.models.loan_model import LoanModel
from app.models.descuento_detalles_model import DescuentoDetallesModel


Number = Union[int, float]


class PagosPendientesEditables(ft.UserControl):
    """
    Tabla de pagos PENDIENTES / EDITABLES (depósito recalcula efectivo/saldo/total).

    Objetivo UI (refactor quirúrgico):
    - Eliminar columna "ediciones".
    - Mover TODOS los botones a una sola columna "acciones":
        [Descuentos, Préstamos, Confirmar, Borrar]
    - Mantener look & feel alineado a Pagos Pagados:
        * widths desde PaymentTableBuilder.DEFAULT_WIDTHS
        * wrap_cell() como fuente de verdad para tamaño/consistencia
        * DataTable configurada por PaymentTableBuilder.build_table()
    - NO tocar lógica esencial de recálculos / repo / DB / refresh.
    """

    # ✅ IMPORTANTE: orden alineado a "Pagos Pagados" en la parte final:
    # deposito, saldo, efectivo, total, acciones, estado
    COL_KEYS = [
        "id_pago", "id_empleado", "nombre", "fecha_pago", "horas", "sueldo_hora",
        "monto_base", "descuentos", "prestamos",
        "deposito", "saldo", "efectivo", "total",
        "acciones", "estado",
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
        # (Se permiten por compat, pero ya NO son la fuente de verdad)
        col_widths: Optional[Dict[str, Number]] = None,
        col_min_widths: Optional[Dict[str, Number]] = None,
        table_min_width: Number = 0,
        table_padding: int = 0,
    ):
        super().__init__()

        self.page = AppState().page

        self.repo = repo
        self.payment_model = payment_model
        self.math = math
        self.loan_model = loan_model
        self.detalles_desc_model = detalles_desc_model
        self.table_builder = table_builder
        self.row_refresh = row_refresh
        self.sort_helper = PaymentSortFilterHelper()

        self.on_data_changed = on_data_changed
        self.on_pago_confirmado = on_pago_confirmado
        self.on_pago_eliminado = on_pago_eliminado

        self.filters: Dict[str, str] = {"id_empleado": "", "id_pago": ""}
        self._deposito_buffer: Dict[int, Any] = {}
        self._saving_rows: set[int] = set()

        sort_state = AppState().get("pagos.sort.pend", {"key": "id_pago", "asc": False})
        self.sort_key: str = str(sort_state.get("key") or "id_pago")
        self.sort_asc: bool = bool(sort_state.get("asc", False))

        self._table_padding: int = int(table_padding)

        # ✅ Tabla base (columnas + spacing controlado por builder)
        self.table: ft.DataTable = self.table_builder.build_table(
            self.COL_KEYS,
            rows=[],
            sortable_cols=(
                "id_pago", "id_empleado", "nombre", "fecha_pago", "horas", "sueldo_hora",
                "monto_base", "descuentos", "prestamos", "saldo", "deposito", "efectivo", "total",
            ),
            on_sort=self._handle_sort_event,
            sort_key=self.sort_key,
            sort_ascending=self.sort_asc,
            show_sort_indicator=False,
        )
        # Centrar header "Acciones" de forma explícita (por estilo)
        try:
            idx_acc = self.COL_KEYS.index("acciones")
            w = int(getattr(self.table_builder, "_col_width")("acciones"))  # type: ignore[misc]
            label = ft.Container(
                content=ft.Row(
                    [ft.Text("Acciones", size=self.table_builder.font_size, weight=ft.FontWeight.BOLD)],
                    alignment=ft.MainAxisAlignment.CENTER,
                    expand=True,
                ),
                width=w,
                alignment=ft.alignment.center,
            )
            self.table.columns[idx_acc].label = label
        except Exception:
            pass

        # ✅ UI wrappers
        self._root: Optional[ft.Control] = None
        self._table_container: Optional[ft.Container] = None

    def did_mount(self):
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
        return self.build()

    # ---------------- UI (SIN SCROLL HORIZONTAL INTERNO) ----------------
    def build(self) -> ft.Control:
        """
        ✅ Nota:
        - NO poner Row(scroll=ALWAYS) aquí si ya hay scroll horizontal externo (PagosScrollHelper).
        - Scrolls horizontales anidados suelen capturar drag y romper on_click de IconButtons.
        """
        if self._root is not None:
            return self._root

        self._table_container = ft.Container(
            content=self.table,
            width=self._compute_table_width(),
            padding=self._table_padding,
        )

        self._root = ft.Container(
            content=self._table_container,
            expand=False,
        )
        return self._root

    def _compute_table_width(self) -> float:
        """
        Fuente de verdad: PaymentTableBuilder.DEFAULT_WIDTHS
        """
        try:
            base = float(self.table_builder.get_table_width(self.COL_KEYS, buffer=0, include_horizontal_margin=True))
            overlap = float(max(0, int(getattr(self.table_builder, "_estado_pull_left", 0))))
            return max(300.0, base + overlap)
        except Exception:
            return 300.0

    # ✅ Unifica ancho/altura de contenido con header vía wrap_cell()
    def _wrap_cell(self, key: str, control: ft.Control) -> ft.DataCell:
        return self.table_builder.wrap_cell(key, control)

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
        # Tri-estado en tabla (none -> desc -> asc -> none)
        key = str(column_key or "")
        if key in ("acciones", "estado"):
            return

        idx_map = {k: i for i, k in enumerate(self.COL_KEYS)}
        col_idx = idx_map.get(key, None)
        if col_idx is None:
            return

        # tipo por columna
        value_type = {
            "id_pago": "int",
            "id_empleado": "int",
            "nombre": "text",
            "fecha_pago": "date",
            "horas": "float",
            "sueldo_hora": "money",
            "monto_base": "money",
            "descuentos": "money",
            "prestamos": "money",
            "saldo": "money",
            "deposito": "money",
            "efectivo": "money",
            "total": "money",
        }.get(key, "text")

        self.sort_helper.toggle_sort_tristate_table(
            self.table,
            column_index=col_idx,
            value_type=value_type,
        )

    def get_sort_state(self) -> Dict[str, Any]:
        return {"key": self.sort_key, "asc": self.sort_asc}

    def set_sort_state(self, key: str, asc: bool) -> None:
        # ✅ solo llaves presentes en esta tabla
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

                # ✅ no tocar lógica: solo asegurar borrador como ya hacías
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

            # snapshot base para tri-estado (NONE)
            self.sort_helper.refresh_snapshot(self.table)

            # ✅ Mantén ancho real por si cambiaste DEFAULT_WIDTHS
            if self._table_container is not None:
                self._table_container.width = self._compute_table_width()

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

        # --- FIX (E): hit-test robusto para IconButton en filas ultra-compactas ---
        def _compact_icon_btn(
            *,
            icon: str,
            tooltip: str,
            icon_color: Optional[str] = None,
            disabled: bool = False,
            on_click: Optional[Callable] = None,
        ) -> ft.Control:
            btn = ft.IconButton(
                icon=icon,
                tooltip=tooltip,
                icon_color=icon_color,
                disabled=disabled,
                on_click=on_click,
                icon_size=18,
                style=ft.ButtonStyle(padding=ft.padding.all(0)),
            )
            # Container define hitbox estable (Flet 0.24)
            return ft.Container(
                content=btn,
                height=28,
                width=28,
                alignment=ft.alignment.center,
                padding=0,
            )

        txts = {
            "id_pago": ft.Text(str(id_pago), size=font),
            "id_empleado": ft.Text(str(num), size=font),
            "nombre": ft.Text(nombre, size=font, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
            "fecha_pago": ft.Text(fecha_pago, size=font),
            "horas": ft.Text(PaymentRowBuilder.format_horas(horas), size=font, tooltip=f"{horas:.4f}"),
            "sueldo_hora": ft.Text(money(sueldo_h), size=font),
            "monto_base": ft.Text(money(monto_base), size=font),
            "descuentos": ft.Text(money(calc.get("descuentos_view", 0.0)), size=font),
            "prestamos": ft.Text(money(calc.get("prestamos_view", 0.0)), size=font),
            "saldo": ft.Text(money(calc.get("saldo_ajuste", 0.0)), size=font),
            "efectivo": ft.Text(money(calc.get("efectivo", 0.0)), size=font),
            "total": ft.Text(money(calc.get("total_vista", 0.0)), size=font),
        }

        tf_deposito = ft.TextField(
            value=f"{float(deposito_ui or 0):.2f}",
            height=28,
            text_align=ft.TextAlign.RIGHT,
            dense=True,
            text_size=font,
            on_change=lambda e, pid=id_pago: self._on_deposito_change_pend(pid, e.control.value),
            on_blur=lambda e, pid=id_pago: self._guardar_deposito_desde_ui_pend(pid),
            on_submit=lambda e, pid=id_pago: self._guardar_deposito_desde_ui_pend(pid),
        )

        # ✅ Botones que antes vivían en "Ediciones"
        btn_desc = _compact_icon_btn(
            icon=ft.icons.REMOVE_CIRCLE_OUTLINE,
            tooltip="Editar descuentos",
            icon_color=ft.colors.AMBER_700,
            on_click=lambda e, pago_row=p: self._abrir_modal_descuentos(pago_row),
        )

        btn_prest = _compact_icon_btn(
            icon=ft.icons.ACCOUNT_BALANCE_WALLET,
            tooltip="Editar préstamos" if tiene_prestamo_activo else "Sin préstamo activo",
            icon_color=ft.colors.BLUE_600 if tiene_prestamo_activo else ft.colors.GREY_400,
            disabled=not tiene_prestamo_activo,
            on_click=(lambda e, pago_row=p: self._abrir_modal_prestamos(pago_row)) if tiene_prestamo_activo else None,
        )

        # ✅ Botones que ya vivían en "Acciones"
        btn_confirmar = _compact_icon_btn(
            icon=ft.icons.CHECK,
            tooltip="Confirmar pago",
            icon_color=ft.colors.GREEN_600,
            on_click=lambda e, pid=id_pago: self._guardar_pago_confirmado(pid),
        )

        btn_eliminar = _compact_icon_btn(
            icon=ft.icons.DELETE_OUTLINE,
            tooltip="Eliminar pago",
            icon_color=ft.colors.RED_500,
            on_click=lambda e, pid=id_pago: self._eliminar_pago(pid),
        )

        # ✅ ÚNICA columna "acciones" (4 botones)
        acciones_cell = ft.Row([btn_desc, btn_prest, btn_confirmar, btn_eliminar], spacing=4)

        estado_chip = ft.Container(
            content=ft.Text("PENDIENTE", size=10),
            bgcolor=ft.colors.GREY_200,
            padding=ft.padding.symmetric(4, 6),
            border_radius=6,
        )

        # ✅ Celdas SIN "ediciones"
        cells = [
            self._wrap_cell("id_pago", txts["id_pago"]),
            self._wrap_cell("id_empleado", txts["id_empleado"]),
            self._wrap_cell("nombre", txts["nombre"]),
            self._wrap_cell("fecha_pago", txts["fecha_pago"]),
            self._wrap_cell("horas", txts["horas"]),
            self._wrap_cell("sueldo_hora", txts["sueldo_hora"]),
            self._wrap_cell("monto_base", txts["monto_base"]),
            self._wrap_cell("descuentos", txts["descuentos"]),
            self._wrap_cell("prestamos", txts["prestamos"]),
            self._wrap_cell("deposito", tf_deposito),
            self._wrap_cell("saldo", txts["saldo"]),
            self._wrap_cell("efectivo", txts["efectivo"]),
            self._wrap_cell("total", txts["total"]),
            self._wrap_cell("acciones", acciones_cell),
            self._wrap_cell("estado", estado_chip),
        ]

        row = ft.DataRow(cells=cells)

        # ✅ registro para refrescos (sin tocar lógica de recálculo)
        self.row_refresh.register_row(
            id_pago,
            row,
            txt_desc=txts["descuentos"],
            txt_prest=txts["prestamos"],
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

    # ---------------- Acciones / Modales (UI-only) ----------------
    @staticmethod
    def _call_first_callable(target: Any, names: List[str], *args, **kwargs) -> bool:
        """
        Llama al primer método existente y callable dentro de `names`.
        No rompe si el método no existe o falla; retorna True si pudo llamar.
        """
        for n in names:
            fn = getattr(target, n, None)
            if callable(fn):
                try:
                    fn(*args, **kwargs)
                    return True
                except Exception:
                    return False
        return False

    def _abrir_modal_descuentos(self, pago_row: Dict[str, Any]) -> None:
        """
        ✅ Contrato real (ModalDescuentos actual):
            ModalDescuentos(pago_data=payload, on_confirmar=cb).mostrar(page?)
        Sin tocar lógica de recálculos: solo orquesta apertura UI y callback de refresh.
        """
        try:
            page = self.page or AppState().page
            if not page:
                return

            pid = int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago") or 0)
            if pid <= 0:
                return

            # Estado: para pendientes debe ser editable (≠ "pagado")
            estado = str(pago_row.get("estado") or "pendiente").strip().lower()
            if estado == "pagado":
                estado = "pendiente"

            payload = {
                "id_pago": pid,
                "id_pago_nomina": pid,
                "numero_nomina": int(pago_row.get("numero_nomina") or 0),
                "nombre_empleado": pago_row.get("nombre_completo") or pago_row.get("nombre_empleado") or pago_row.get("nombre") or "",
                "estado": estado,
                # opcionales para resumen correcto
                "monto_base": pago_row.get("monto_base") or 0,
                "monto_prestamo": pago_row.get("monto_prestamo") or pago_row.get("prestamo") or 0,
            }

            def _on_confirm(_payload: Dict[str, Any]):
                # UI-only: invalidar caches (si aplica) y refrescar fila
                try:
                    self._invalidate_caches()
                except Exception:
                    pass
                try:
                    self._actualizar_fila(pid, persist=False)
                except Exception:
                    pass
                try:
                    if callable(self.on_data_changed):
                        self.on_data_changed()
                except Exception:
                    pass

            ModalDescuentos(pago_data=payload, on_confirmar=_on_confirm).mostrar(page)

        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo abrir Descuentos: {ex}")

    def _abrir_modal_prestamos(self, pago_row: Dict[str, Any]) -> None:
        """
        Mantiene compat: apertura flexible por si ModalPrestamosNomina cambió en tu proyecto.
        (No sabemos su firma exacta en este turno, así que conservamos robustez.)
        """
        try:
            page = self.page or AppState().page
            if not page:
                return

            # primer intento: helpers estáticos comunes
            if self._call_first_callable(ModalPrestamosNomina, ["mostrar", "abrir", "open"], page, pago_row):
                return

            # fallback por signature introspection
            try:
                sig = inspect.signature(ModalPrestamosNomina)  # type: ignore[arg-type]
                params = {p.name for p in sig.parameters.values()}
            except Exception:
                params = set()

            kwargs: Dict[str, Any] = {}
            if "page" in params:
                kwargs["page"] = page
            if "pago_data" in params:
                kwargs["pago_data"] = pago_row
            elif "pago_row" in params:
                kwargs["pago_row"] = pago_row
            elif "pago" in params:
                kwargs["pago"] = pago_row

            if "loan_model" in params:
                kwargs["loan_model"] = self.loan_model
            if "payment_model" in params:
                kwargs["payment_model"] = self.payment_model
            if "repo" in params:
                kwargs["repo"] = self.repo

            modal = ModalPrestamosNomina(**kwargs) if kwargs else ModalPrestamosNomina()  # type: ignore[call-arg]
            if not self._call_first_callable(modal, ["mostrar", "abrir", "open"], pago_row):
                page.dialog = modal  # type: ignore[assignment]
                try:
                    modal.open = True  # type: ignore[attr-defined]
                except Exception:
                    pass
                page.update()

        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo abrir Préstamos: {ex}")

    def _guardar_pago_confirmado(self, id_pago_nomina: int) -> None:
        """
        Confirma pago:
        - Si hay callback externo, se usa (no toca lógica esencial).
        - Si el repo expone un método estándar, se intenta.
        """
        try:
            # 1) Preferencia: callback externo (contenedor superior)
            if callable(self.on_pago_confirmado):
                p = self.repo.obtener_pago(int(id_pago_nomina)) or {"id_pago_nomina": int(id_pago_nomina)}
                self.on_pago_confirmado(p)
                if callable(self.on_data_changed):
                    self.on_data_changed()
                return

            # 2) Fallback: repositorio (nombres comunes)
            if self._call_first_callable(self.repo, ["confirmar_pago", "marcar_pagado", "set_pagado"], int(id_pago_nomina)):
                if callable(self.on_data_changed):
                    self.on_data_changed()
                self.reload()
                return

            ModalAlert.mostrar_info(
                "Atención",
                "No hay handler de confirmación configurado (on_pago_confirmado) "
                "y el repo no expone confirmar_pago/marcar_pagado.",
            )
        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo confirmar el pago: {ex}")

    def _eliminar_pago(self, id_pago_nomina: int) -> None:
        """
        Elimina pago:
        - Si hay callback externo, se usa.
        - Si el repo expone un método estándar, se intenta.
        """
        try:
            # 1) Preferencia: callback externo
            if callable(self.on_pago_eliminado):
                self.on_pago_eliminado(int(id_pago_nomina))
                if callable(self.on_data_changed):
                    self.on_data_changed()
                return

            # 2) Fallback: repositorio (nombres comunes)
            if self._call_first_callable(self.repo, ["eliminar_pago", "delete_pago", "borrar_pago"], int(id_pago_nomina)):
                if callable(self.on_data_changed):
                    self.on_data_changed()
                self.reload()
                return

            ModalAlert.mostrar_info(
                "Atención",
                "No hay handler de eliminación configurado (on_pago_eliminado) "
                "y el repo no expone eliminar_pago/delete_pago/borrar_pago.",
            )
        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo eliminar el pago: {ex}")

    # ---------------- Cálculo / UI refresh ----------------
    def _recalc_row(self, p_row: Dict[str, Any], deposito_ui: float) -> Dict[str, float]:
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
        try:
            if getattr(self.table, "page", None):
                self.table.update()
            elif getattr(self, "page", None):
                self.page.update()
        except Exception:
            pass

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
