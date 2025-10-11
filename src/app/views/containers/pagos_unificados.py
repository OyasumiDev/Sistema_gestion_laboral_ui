# app/views/containers/pagos_unificados.py
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import re
import datetime as dt
import flet as ft

# Helpers / servicios (los que ya definiste)
from app.helpers.pagos.payment_table_builder import PaymentTableBuilder
from app.helpers.pagos.payment_row_builder import PaymentRowBuilder
from app.helpers.pagos.row_refresh import PaymentRowRefresh
from app.helpers.pagos.sorting_filter_payment_helper import PaymentSortFilterHelper
from app.helpers.pagos.pagos_repo import PagosRepo
from app.helpers.pagos.payment_view_math import PaymentViewMath


def _money(v: Any) -> str:
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return "$0.00"


def _to_iso_from_ddmmyyyy(txt: str) -> Optional[str]:
    """
    Convierte 'dd/mm/yyyy' -> 'yyyy-mm-dd'. Devuelve None si no matchea.
    """
    s = (txt or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    if not m:
        return None
    d, mth, y = m.group(1), m.group(2), m.group(3)
    try:
        dt.date(int(y), int(mth), int(d))  # valida fecha
        return f"{y}-{mth}-{d}"
    except Exception:
        return None


class PagosUnificados(ft.UserControl):
    """
    Contenedor unificado de pagos:
    - Panel A: Pendientes (edición).
    - Panel B: Pagados (expansible por fecha).
    Filtros y sort centralizados. Refresh sin cerrar toggles de expansibles.
    """

    # Índices columna para DataTable de PENDIENTES (con PaymentRowBuilder.build_row_edicion)
    # ["id_pago"(0), "id_empleado"(1), "nombre"(2), "fecha_pago"(3), "horas"(4),
    #  "sueldo_hora"(5), "monto_base"(6), "descuentos"(7), "prestamos"(8),
    #  "saldo"(9), "deposito"(10), "efectivo"(11), "total"(12), "ediciones"(13),
    #  "acciones"(14), "estado"(15)]
    PEND_ID_PAGO_IDX = 0
    PEND_ID_EMP_IDX = 1
    PEND_FECHA_IDX = 3
    PEND_MONTO_BASE_IDX = 6
    PEND_TOTAL_IDX = 12

    # Índices columna para DataTable de PAGADOS (compacto/lectura)
    # ["id_pago"(0), "id_empleado"(1), "nombre"(2), "monto_base"(3), "descuentos"(4),
    #  "prestamos"(5), "deposito"(6), "saldo"(7), "efectivo"(8), "total"(9), "estado"(10)]
    PAID_ID_PAGO_IDX = 0
    PAID_ID_EMP_IDX = 1
    PAID_MONTO_BASE_IDX = 3
    PAID_TOTAL_IDX = 9

    def __init__(
        self,
        *,
        repo: Optional[PagosRepo] = None,
        math: Optional[PaymentViewMath] = None,
        table_builder: Optional[PaymentTableBuilder] = None,
        row_builder: Optional[PaymentRowBuilder] = None,
        row_refresh: Optional[PaymentRowRefresh] = None,
        sort_filter: Optional[PaymentSortFilterHelper] = None,
        # Callbacks externos (modales / navegación) — opcionales
        on_editar_descuentos: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_editar_prestamos: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_pago_confirmado: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_pago_eliminado: Optional[Callable[[int], None]] = None,
    ):
        super().__init__()

        # Inyección / defaults
        self.repo = repo or PagosRepo()
        self.math = math or PaymentViewMath(
            discount_model=self.repo.payment_model.discount_model,
            detalles_desc_model=self.repo.payment_model.detalles_desc_model,
            loan_payment_model=self.repo.payment_model.loan_payment_model,
            detalles_prestamo_model=self.repo.payment_model.loan_payment_model,  # si tienes otro, inyéctalo
        )
        self.table_builder = table_builder or PaymentTableBuilder()
        self.row_builder = row_builder or PaymentRowBuilder()
        self.row_refresh = row_refresh or PaymentRowRefresh()
        self.sort_filter = sort_filter or PaymentSortFilterHelper()

        # Callbacks UI externas
        self.on_editar_descuentos = on_editar_descuentos
        self.on_editar_prestamos = on_editar_prestamos
        self.on_pago_confirmado = on_pago_confirmado
        self.on_pago_eliminado = on_pago_eliminado

        # Estado interno
        self._expanded_state: Dict[str, bool] = {}      # fecha -> expanded?
        self._group_rows: Dict[str, ft.DataTable] = {}  # fecha -> tabla
        self._group_total_labels: Dict[str, ft.Text] = {}  # fecha -> label total
        self._paid_panels: Dict[str, ft.ExpansionPanel] = {}

        # Controles UI principales
        self._tf_id_pago: Optional[ft.TextField] = None
        self._tf_id_emp: Optional[ft.TextField] = None
        self._tf_fecha: Optional[ft.TextField] = None  # dd/mm/yyyy
        self._btn_clear: Optional[ft.IconButton] = None

        self._pending_table: Optional[ft.DataTable] = None
        self._paid_panel_list: Optional[ft.ExpansionPanelList] = None

        # Data en memoria (para re-build sin re-consultar si no quieres)
        self._rows_pending: List[Dict[str, Any]] = []
        self._rows_paid: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Flet lifecycle
    # ------------------------------------------------------------------
    def build(self) -> ft.Control:
        # Filtros arriba
        filters_bar = self._build_filters_bar()

        # Panel pendientes
        pending_card = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("Pagos pendientes", weight=ft.FontWeight.BOLD, size=14),
                        self._build_pending_table(),
                    ],
                    spacing=8,
                ),
                padding=10,
            ),
            elevation=2,
        )

        # Panel pagados (expansibles por fecha)
        paid_card = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("Pagos pagados por fecha", weight=ft.FontWeight.BOLD, size=14),
                        self._build_paid_panels(),
                    ],
                    spacing=8,
                ),
                padding=10,
            ),
            elevation=2,
        )

        return ft.Column(
            controls=[
                filters_bar,
                pending_card,
                paid_card,
            ],
            spacing=12,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    def did_mount(self):
        # Cargar data inicial y pintar
        self.refresh_all()

    # ------------------------------------------------------------------
    # UI — Filtros
    # ------------------------------------------------------------------
    def _build_filters_bar(self) -> ft.Container:
        self._tf_id_pago = ft.TextField(
            label="ID pago (prefijo o lista)",
            hint_text="Ej: 12 ó 1,2,5-8",
            dense=True,
            height=36,
            width=220,
            on_change=lambda e: self.apply_filters(),
        )
        self._tf_id_emp = ft.TextField(
            label="ID empleado (prefijo)",
            hint_text="Ej: 10",
            dense=True,
            height=36,
            width=200,
            on_change=lambda e: self.apply_filters(),
        )
        self._tf_fecha = ft.TextField(
            label="Fecha (dd/mm/yyyy)",
            hint_text="dd/mm/yyyy",
            dense=True,
            height=36,
            width=180,
            on_change=lambda e: self.apply_filters(),
        )
        self._btn_clear = ft.IconButton(
            icon=ft.icons.CLEAR_ALL,
            tooltip="Limpiar filtros",
            on_click=lambda e: self._clear_filters(),
        )

        return ft.Container(
            content=ft.Row(
                controls=[self._tf_id_pago, self._tf_id_emp, self._tf_fecha, self._btn_clear],
                spacing=8,
                wrap=True,
            ),
            padding=5,
        )

    def _clear_filters(self):
        if self._tf_id_pago:
            self._tf_id_pago.value = ""
        if self._tf_id_emp:
            self._tf_id_emp.value = ""
        if self._tf_fecha:
            self._tf_fecha.value = ""
        self.apply_filters()

    # ------------------------------------------------------------------
    # Pending table
    # ------------------------------------------------------------------
    def _build_pending_table(self) -> ft.Container:
        # Columnas (clave->texto) para header con PaymentTableBuilder
        columns = [
            "id_pago", "id_empleado", "nombre", "fecha_pago", "horas", "sueldo_hora", "monto_base",
            "descuentos", "prestamos", "saldo", "deposito", "efectivo", "total", "ediciones", "acciones", "estado",
        ]
        # Tabla vacía de inicio; rows se cargan en refresh_all()
        self._pending_table = self.table_builder.build_table(
            columns=columns,
            rows=[],
            sortable_cols=columns,
        )
        # sorters estándar
        self.sort_filter.bind_standard_sorters_to_pendientes(
            self._pending_table,
            on_after_sort=None,
            id_pago_idx=self.PEND_ID_PAGO_IDX,
            monto_base_idx=self.PEND_MONTO_BASE_IDX,
            total_idx=self.PEND_TOTAL_IDX,
        )
        return self.table_builder.wrap_scroll(self._pending_table, height=280, width=1600)

    # ------------------------------------------------------------------
    # Paid panels (grouped by fecha_pago)
    # ------------------------------------------------------------------
    def _build_paid_panels(self) -> ft.Container:
        self._paid_panel_list = ft.ExpansionPanelList(
            expand_icon=ft.icons.KEYBOARD_ARROW_DOWN,
            elevation=1,
            divider_color=ft.colors.GREY_300,
            controls=[],
        )
        return ft.Container(
            content=self._paid_panel_list,
            padding=ft.padding.only(top=2),
            width=1600,
        )

    # ------------------------------------------------------------------
    # Data loading / refresh
    # ------------------------------------------------------------------
    def refresh_all(self) -> None:
        """
        Vuelve a leer ambos listados y repinta. Mantiene estado expandido de grupos.
        """
        # Guarda expansión actual
        self._snapshot_expand_state()

        # 1) Leer lista plana (tu get_all_pagos) y partir por estado
        flat_rows = self.repo.listar_pagos(order_desc=True) or []
        self._rows_pending = [r for r in flat_rows if str(r.get("estado", "")).lower() != "pagado"]
        self._rows_paid = [r for r in flat_rows if str(r.get("estado", "")).lower() == "pagado"]

        # 2) Pintar pendientes
        self._paint_pending_rows(self._rows_pending)

        # 3) Pintar pagados por fecha
        self._paint_paid_groups(self._rows_paid)

        # 4) Aplicar filtros actuales (si los hay)
        self.apply_filters()

    # ------------------------- pendientes -------------------------
    def _paint_pending_rows(self, items: List[Dict[str, Any]]) -> None:
        if not self._pending_table:
            return

        self.row_refresh.clear_rows()
        rows: List[ft.DataRow] = []
        for pago in items:
            # Calculadora de vista
            calc = self.math.recalc_from_pago_row(pago, deposito_ui=float(pago.get("deposito", 0.0) or 0.0))

            row = self.row_builder.build_row_edicion(
                pago,
                calc,
                on_editar_descuentos=self.on_editar_descuentos,
                on_editar_prestamos=self.on_editar_prestamos,
                on_confirmar=lambda p=pago: self._confirmar_pago(p),
                on_eliminar=lambda p=pago: self._eliminar_pago(p),
                on_deposito_change=lambda pid, v: self._on_deposito_change(pid, v),
                on_deposito_blur=lambda pid: self._on_deposito_blur(pid),
                on_deposito_submit=lambda pid: self._on_deposito_blur(pid),
            )
            # Registrar refs para refrescos rápidos
            # Mapeo de controles en la fila:
            refs = self._extract_refs_from_pending_row(row)
            self.row_refresh.register_row(
                int(pago.get("id_pago_nomina") or pago.get("id_pago") or 0),
                row,
                **refs,
            )
            rows.append(row)

        self._pending_table.rows = rows
        self.sort_filter.refresh_snapshot(self._pending_table)
        self._pending_table.update()

    def _extract_refs_from_pending_row(self, row: ft.DataRow) -> Dict[str, Any]:
        """
        Extrae referencias de celdas por índice para el refresher:
        indices: 7(desc), 8(prest), 9(saldo), 10(tf depósito), 11(efe), 12(total)
        """
        def _text(idx): 
            try: return row.cells[idx].content if isinstance(row.cells[idx].content, ft.Text) else None
            except Exception: return None

        def _textfield(idx):
            try: return row.cells[idx].content if isinstance(row.cells[idx].content, ft.TextField) else None
            except Exception: return None

        return {
            "txt_desc": _text(7),
            "txt_prest": _text(8),
            "txt_saldo": _text(9),
            "tf_deposito": _textfield(10),
            "txt_efectivo": _text(11),
            "txt_total": _text(12),
            "estado_chip": None,  # si usas chip/Container de estado, inyéctalo aquí
        }

    # -------------------------- pagados ---------------------------
    def _paint_paid_groups(self, items: List[Dict[str, Any]]) -> None:
        if not self._paid_panel_list:
            return

        # agrupar por fecha_pago
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in items:
            f = str(r.get("fecha_pago") or "")
            groups.setdefault(f, []).append(r)

        # limpia registros previos
        self._group_rows.clear()
        self._group_total_labels.clear()
        self._paid_panels.clear()

        panels: List[ft.ExpansionPanel] = []
        for fecha, rows in sorted(groups.items(), key=lambda kv: kv[0], reverse=True):
            # tabla del grupo
            dt_group = self._build_paid_group_table(fecha, rows)
            # header con suma del día
            total_day = self._compute_total_from_table(dt_group, self.PAID_TOTAL_IDX)
            lbl_total = ft.Text(f"Total día: {_money(total_day)}", weight=ft.FontWeight.BOLD, size=12)

            header = ft.Row(
                controls=[
                    ft.Text(fecha, weight=ft.FontWeight.BOLD, size=13),
                    ft.Container(expand=True),
                    lbl_total,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            panel = ft.ExpansionPanel(
                header=header,
                content=ft.Container(content=dt_group, padding=ft.padding.only(top=6, bottom=6)),
                expanded=self._expanded_state.get(fecha, False),
                can_tap_header=True,
            )
            panels.append(panel)

            # registrar para refrescos granulares
            self._group_rows[fecha] = dt_group
            self._group_total_labels[fecha] = lbl_total
            self._paid_panels[fecha] = panel

        self._paid_panel_list.controls = panels
        self._paid_panel_list.update()

        # registra grupos en refresher (para totales live)
        for fecha, table in self._group_rows.items():
            self.row_refresh.register_group(
                fecha,
                table=table,
                panel=self._paid_panels.get(fecha),
                lbl_total=self._group_total_labels.get(fecha),
                lbl_title=None,
            )

    def _build_paid_group_table(self, fecha: str, items: List[Dict[str, Any]]) -> ft.DataTable:
        columns = [
            "id_pago", "id_empleado", "nombre",
            "monto_base", "descuentos", "prestamos",
            "deposito", "saldo", "efectivo", "total", "estado",
        ]
        rows: List[ft.DataRow] = []

        for pago in items:
            calc = self.math.recalc_from_pago_row(pago, deposito_ui=float(pago.get("deposito", 0.0) or 0.0))
            row = self.row_builder.build_row_compacto(pago, calc)
            # registra para refresco granular
            refs = self._extract_refs_from_paid_row(row)
            self.row_refresh.register_row(
                int(pago.get("id_pago_nomina") or pago.get("id_pago") or 0),
                row,
                **refs,
            )
            rows.append(row)

        table = self.table_builder.build_table(
            columns=columns,
            rows=rows,
            sortable_cols=columns,
        )
        # sorters
        self.sort_filter.bind_standard_sorters_to_confirmado(
            table,
            id_pago_idx=self.PAID_ID_PAGO_IDX,
            monto_base_idx=self.PAID_MONTO_BASE_IDX,
            total_idx=self.PAID_TOTAL_IDX,
        )
        return table

    def _extract_refs_from_paid_row(self, row: ft.DataRow) -> Dict[str, Any]:
        # índices: 4(desc), 5(prest), 7(saldo), 8(efectivo), 9(total)
        def _text(idx): 
            try: return row.cells[idx].content if isinstance(row.cells[idx].content, ft.Text) else None
            except Exception: return None

        return {
            "txt_desc": _text(4),
            "txt_prest": _text(5),
            "txt_saldo": _text(7),
            "tf_deposito": None,   # en pagado no hay TF editable
            "txt_efectivo": _text(8),
            "txt_total": _text(9),
            "estado_chip": None,
        }

    # ------------------------------------------------------------------
    # Filtros combinados (ID pago, ID empleado, fecha dd/mm/yyyy)
    # ------------------------------------------------------------------
    def apply_filters(self) -> None:
        id_pago_q = (self._tf_id_pago.value if self._tf_id_pago else "") or ""
        id_emp_q = (self._tf_id_emp.value if self._tf_id_emp else "") or ""
        fecha_q = (self._tf_fecha.value if self._tf_fecha else "") or ""

        # ---- pendientes (tabla única) ----
        if self._pending_table:
            # Resetea snapshot si cambiaste el contenido
            self.sort_filter.refresh_snapshot(self._pending_table)

            # 1) priorizar por prefijos de IDs
            self.sort_filter.apply_standard_filters_to_pendientes_table(
                self._pending_table,
                id_empleado_prefix=id_emp_q,
                id_pago_prefix=id_pago_q,
                match_mode="or",
                mode="prioritize",
                id_empleado_idx=self.PEND_ID_EMP_IDX,
                id_pago_idx=self.PEND_ID_PAGO_IDX,
            )
            # 2) filtrar por fecha dd/mm/yyyy (si aplica)
            if fecha_q.strip():
                iso = _to_iso_from_ddmmyyyy(fecha_q.strip())
                if iso:
                    self._filter_table_by_date_iso(self._pending_table, self.PEND_FECHA_IDX, iso)

        # ---- pagados (expansibles por fecha) ----
        if self._paid_panel_list:
            # filtrar por fecha: si hay fecha, muestra sólo ese panel; si no, todos
            target_iso = _to_iso_from_ddmmyyyy(fecha_q.strip()) if fecha_q.strip() else None
            for fecha, panel in self._paid_panels.items():
                panel.visible = (fecha == target_iso) if target_iso else True

            # dentro de cada tabla del grupo, prioriza por prefijos de IDs
            for fecha, table in self._group_rows.items():
                self.sort_filter.refresh_snapshot(table)
                self.sort_filter.apply_standard_filters_to_confirmado_table(
                    table,
                    id_empleado_prefix=id_emp_q,
                    id_pago_prefix=id_pago_q,
                    match_mode="or",
                    mode="prioritize",
                    id_empleado_idx=self.PAID_ID_EMP_IDX,
                    id_pago_idx=self.PAID_ID_PAGO_IDX,
                )
                table.update()

            self._paid_panel_list.update()

    def _filter_table_by_date_iso(self, datatable: ft.DataTable, fecha_col_index: int, fecha_iso: str) -> None:
        """
        Reduce filas de una tabla por match exacto en columna fecha (yyyy-mm-dd).
        Usa el snapshot para no acumular filtros.
        """
        tid = id(datatable)
        self.sort_filter._ensure_snapshot(datatable)
        base_rows = list(self.sort_filter._snapshots[tid])

        filtered: List[ft.DataRow] = []
        for r in base_rows:
            try:
                txt = str(self.sort_filter._get_cell_content(r, fecha_col_index))
                if txt == fecha_iso:
                    filtered.append(r)
            except Exception:
                continue

        datatable.rows = filtered
        datatable.update()

    # ------------------------------------------------------------------
    # Eventos de edición (depósito), confirmar, eliminar
    # ------------------------------------------------------------------
    def _on_deposito_change(self, id_pago: int, value: str) -> None:
        """
        Recalcula en vivo (UI only). No persiste.
        """
        # buscamos el dict base de la fila (en pendientes)
        p = next((x for x in self._rows_pending if int(x.get("id_pago_nomina") or x.get("id_pago") or 0) == id_pago), None)
        if not p:
            return
        try:
            dep = float(value.replace(",", "."))
        except Exception:
            dep = 0.0

        # recalcular y pintar
        self.row_refresh.recalc_and_paint_row(
            id_pago=id_pago,
            pago_row_dict=p,
            view_math=self.math,
            deposito_ui=dep,
        )

    def _on_deposito_blur(self, id_pago: int) -> None:
        """
        Persistencia opcional del depósito al salir del campo.
        Si prefieres sólo confirmar al final, comenta esta parte.
        """
        p = next((x for x in self._rows_pending if int(x.get("id_pago_nomina") or x.get("id_pago") or 0) == id_pago), None)
        if not p:
            return

        # lee el valor que quedó en el TF
        row = self.row_refresh.get_row(self._pending_table, id_pago)
        dep = self.row_refresh._read_current_deposito(row) if row else 0.0

        # persistir contra PaymentModel.update_pago (vía repo.payment_model)
        try:
            E = self.repo.payment_model.E
            ok = self.repo.payment_model.update_pago(id_pago, {E.PAGO_DEPOSITO.value: dep})
            if not ok:
                # marca borde rojo si no guardó
                self.row_refresh.set_deposito_border_color(row, ft.colors.RED_400)
            else:
                self.row_refresh.set_deposito_border_color(row, None)
        except Exception:
            self.row_refresh.set_deposito_border_color(row, ft.colors.RED_400)

    def _confirmar_pago(self, pago_dict: Dict[str, Any]) -> None:
        """
        Confirma en backend y mueve fila de pendientes -> grupo pagado en vivo,
        preservando el estado del panel de destino.
        """
        id_pago = int(pago_dict.get("id_pago_nomina") or pago_dict.get("id_pago") or 0)
        if id_pago <= 0:
            return

        rs = self.repo.confirmar_pago(id_pago)
        if not isinstance(rs, dict) or rs.get("status") != "success":
            # puedes mostrar un snackbar, etc.
            return

        # Traer registro fresco
        fresh = self.repo.obtener_pago(id_pago) or {}
        if not fresh:
            return

        # Asegurar que quede marcado como pagado
        fresh["estado"] = "pagado"

        # Fecha destino (grupo)
        dest_fecha = str(fresh.get("fecha_pago") or "")

        # Garantiza que el panel/tabla existan; si no, los creamos sin perder estado ajeno
        if dest_fecha not in self._group_rows:
            # crea panel "vacío"
            self._expanded_state.setdefault(dest_fecha, True)  # lo nuevo, abierto por UX
            self._paint_paid_groups(self._rows_paid + [fresh])  # re-pinta con el nuevo también
        else:
            # inserción granular sin re-construir todo
            table = self._group_rows[dest_fecha]
            calc = self.math.recalc_from_pago_row(fresh, deposito_ui=float(fresh.get("deposito", 0.0) or 0.0))
            new_row = self.row_builder.build_row_compacto(fresh, calc)
            refs = self._extract_refs_from_paid_row(new_row)
            self.row_refresh.register_row(id_pago, new_row, **refs)
            self.row_refresh.insert_row(table, new_row)
            # total del grupo
            self.row_refresh.recalc_and_paint_group_total(dest_fecha, total_col_index=self.PAID_TOTAL_IDX)

        # sacar de pendientes
        if self._pending_table:
            self.row_refresh.remove_row_by_id(self._pending_table, id_pago)
            # quítalo también de la lista en memoria
            self._rows_pending = [r for r in self._rows_pending if int(r.get("id_pago_nomina") or r.get("id_pago") or 0) != id_pago]

        # add a paid memory copy si no existía
        if not any(int(r.get("id_pago_nomina") or r.get("id_pago") or 0) == id_pago for r in self._rows_paid):
            self._rows_paid.append(fresh)

        # notificar afuera si lo requieren
        if self.on_pago_confirmado:
            self.on_pago_confirmado(fresh)

        # mantener filtros aplicados
        self.apply_filters()

    def _eliminar_pago(self, pago_dict: Dict[str, Any]) -> None:
        id_pago = int(pago_dict.get("id_pago_nomina") or pago_dict.get("id_pago") or 0)
        if id_pago <= 0:
            return

        rs = self.repo.eliminar_pago(id_pago)
        if not isinstance(rs, dict) or rs.get("status") != "success":
            return

        # elimina de la tabla pendientes
        if self._pending_table:
            self.row_refresh.remove_row_by_id(self._pending_table, id_pago)
        self._rows_pending = [r for r in self._rows_pending if int(r.get("id_pago_nomina") or r.get("id_pago") or 0) != id_pago]

        if self.on_pago_eliminado:
            self.on_pago_eliminado(id_pago)

    # ------------------------------------------------------------------
    # Utilidades privadas
    # ------------------------------------------------------------------
    def _snapshot_expand_state(self) -> None:
        """
        Guarda estado expandido de los paneles antes de refrescar.
        """
        if not self._paid_panels:
            return
        for fecha, panel in self._paid_panels.items():
            try:
                self._expanded_state[fecha] = bool(panel.expanded)
            except Exception:
                pass

    def _compute_total_from_table(self, table: ft.DataTable, total_col_idx: int) -> float:
        return self.row_refresh.compute_table_total(table, total_col_idx)
