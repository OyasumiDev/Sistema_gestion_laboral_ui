# app/views/containers/pagos_pagados_expansibles.py
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import flet as ft

from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert
from app.views.containers.modal_descuentos import ModalDescuentos
from app.views.containers.modal_prestamos_nomina import ModalPrestamosNomina
from app.views.containers.modal_fecha_grupo_pagado import ModalFechaGrupoPagado

from app.models.payment_model import PaymentModel
from app.models.discount_model import DiscountModel
from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.descuento_detalles_model import DescuentoDetallesModel
from app.models.detalles_pagos_prestamo_model import DetallesPagosPrestamoModel

from app.helpers.pagos.payment_view_math import PaymentViewMath
from app.helpers.pagos.payment_table_builder import PaymentTableBuilder
from app.helpers.pagos.row_refresh import PaymentRowRefresh
from app.helpers.pagos.scroll_pagos_helper import PagosScrollHelper
from app.helpers.pagos.sorting_filter_payment_helper import PaymentSortFilterHelper


class PagosPagadosExpansibles(ft.UserControl):
    """
    Paneles expansibles por FECHA para gestionar pagos CONFIRMADOS (pagados).
    """

    COLUMNS = [
        "id_pago", "id_empleado", "nombre",
        "horas", "sueldo_hora", "monto_base",
        "descuentos", "prestamos",
        "deposito", "saldo", "efectivo", "total",
        "acciones", "estado"
    ]
    # columnas con ordenamiento por click en header
    CLICK_SORT = ("id_pago", "id_empleado", "monto_base", "total")
    # índice rápido por nombre de columna
    IDX: Dict[str, int] = {k: i for i, k in enumerate(COLUMNS)}

    def __init__(
        self,
        *,
        payment_model: Optional[PaymentModel] = None,
        discount_model: Optional[DiscountModel] = None,
        loan_model: Optional[LoanModel] = None,
        loan_payment_model: Optional[LoanPaymentModel] = None,
        detalles_desc_model: Optional[DescuentoDetallesModel] = None,
        detalles_prestamo_model: Optional[DetallesPagosPrestamoModel] = None,
        math: Optional[PaymentViewMath] = None,
        repo: Optional[Any] = None,
        table_builder: Optional[PaymentTableBuilder] = None,
        row_refresh: Optional[PaymentRowRefresh] = None,
    ):
        super().__init__()
        self.page = AppState().page

        # modelos / helpers
        self.payment_model = payment_model or PaymentModel()
        self.discount_model = discount_model or DiscountModel()
        self.loan_model = loan_model or LoanModel()
        self.loan_payment_model = loan_payment_model or LoanPaymentModel()
        self.detalles_desc_model = detalles_desc_model or DescuentoDetallesModel()
        self.detalles_prestamo_model = detalles_prestamo_model or DetallesPagosPrestamoModel()

        self.math = math or PaymentViewMath(
            discount_model=self.discount_model,
            detalles_desc_model=self.detalles_desc_model,
            loan_payment_model=self.loan_payment_model,
            detalles_prestamo_model=self.detalles_prestamo_model,
        )
        self.repo = repo

        self.table_builder = table_builder or PaymentTableBuilder()
        self.row_refresh = row_refresh or PaymentRowRefresh()
        self.scroll = PagosScrollHelper()
        self.sort_helper = PaymentSortFilterHelper()

        # estado
        self.sort_key, self.sort_asc = "id_pago", True
        # añade id_pago_conf como alias de filtro para confirmados
        self.filters = {"id_empleado": "", "id_pago": "", "id_pago_conf": ""}

        # edición por fila
        self._edit_rows: set[int] = set()
        self._edit_buffer: dict[int, Dict[str, float]] = {}

        # mapeos por fecha / fila
        self._panel_by_date: Dict[str, ft.ExpansionPanel] = {}
        self._table_by_date: Dict[str, ft.DataTable] = {}
        self._total_lbl_by_date: Dict[str, ft.Text] = {}
        self._ids_by_date: Dict[str, set[int]] = {}
        self._row_total: Dict[int, float] = {}      # total_vista por fila
        self._fecha_by_id: Dict[int, str] = {}      # fecha_pago por id

        # raíz UI
        self.view = ft.ExpansionPanelList(expand=True, controls=[])

        # modal crear grupo pagado
        self.modal_grupo = ModalFechaGrupoPagado(on_date_confirmed=self._crear_grupo_pagado)

    # ---------- Integración pública ----------
    def get_control(self) -> ft.Control:
        return self.view

    def set_filters(
        self,
        *,
        id_empleado: str = "",
        id_pago: str = "",
        id_pago_conf: str = "",
        preserve_expansion: bool = True
    ):
        # si nos pasan id_pago_conf, úsalo como preferente para confirmados
        id_pago = (id_pago_conf or id_pago or "").strip()
        self.filters["id_empleado"] = (id_empleado or "").strip()
        self.filters["id_pago"] = id_pago
        self.filters["id_pago_conf"] = (id_pago_conf or "").strip()
        self.reload(preserve_expansion=preserve_expansion)

    def reload(self, *, preserve_expansion: bool = True):
        self._cargar_paneles(preserve_expansion=preserve_expansion)

    # wrapper tolerante; tu contenedor puede llamarlo
    def add_or_update_pagado(self, pago_row: Dict[str, Any], keep_expanded: bool = True):
        self.push_pago_pagado(pago_row, keep_expanded=keep_expanded)

    def open_group(self, fecha: str):
        p = self._panel_by_date.get(fecha)
        if p:
            p.expanded = True
            if self.page:
                self.page.update()

    # === Push incremental desde "Pendientes" ===
    def push_pago_pagado(self, pago_row: Dict[str, Any], *, keep_expanded: bool = True):
        """
        Inserta/actualiza una fila 'pagada' en su panel de fecha SIN recargar todo.
        Mantiene abierta la expansión del grupo afectado.
        """
        try:
            if not pago_row:
                return
            id_pago = int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago") or 0)
            fecha = str(pago_row.get("fecha_pago") or "")
            if id_pago <= 0 or not fecha:
                return

            # Asegurar panel/tabla para la fecha
            self._ensure_panel_for_date(fecha, expand=True)

            # Si ya existía esa fila, primero la quitamos para hacer "upsert"
            self._remove_row_if_exists(id_pago)

            # Calculo con depósito actual (si viene como 'deposito' o 'pago_deposito')
            deposito = float(pago_row.get("deposito") or pago_row.get("pago_deposito") or 0.0)
            calc = self.math.recalc_from_pago_row(pago_row, deposito)
            row = self._build_row_pagado(pago=pago_row, calc=calc)

            tabla = self._table_by_date[fecha]
            tabla.rows.append(row)
            self._refresh_table_snapshot(fecha)  # snapshot listo

            # Registros del grupo / totales
            total_vista = float(calc.get("total_vista", 0.0))
            self._row_total[id_pago] = total_vista
            self._fecha_by_id[id_pago] = fecha
            self._ids_by_date.setdefault(fecha, set()).add(id_pago)
            self._update_total_label_for(fecha)

            if keep_expanded:
                self.open_group(fecha)
            if self.page:
                self.page.update()
        except Exception as ex:
            ModalAlert.mostrar_info("Push pagado", f"No se pudo insertar la fila: {ex}")

    # ---------- Ciclo Flet ----------
    def build(self):
        return self.view

    # ---------- Carga ----------
    def _cargar_paneles(self, *, preserve_expansion: bool):
        try:
            # guardar expansiones
            expanded_dates = set()
            if preserve_expansion:
                for p in self.view.controls:
                    try:
                        if p.expanded:
                            t = p.header.controls[0]
                            if isinstance(t, ft.Text):
                                expanded_dates.add(t.value.split()[-1])
                    except Exception:
                        pass

            # limpiar estado
            self.view.controls.clear()
            self._panel_by_date.clear()
            self._table_by_date.clear()
            self._total_lbl_by_date.clear()
            self._ids_by_date.clear()
            self._row_total.clear()
            self._fecha_by_id.clear()

            rs = self.payment_model.get_all_pagos() or {}
            todos: List[Dict[str, Any]] = rs.get("data") or []

            # SOLO pagados
            pagos = [p for p in todos if str(p.get("estado", "")).lower() == "pagado"]

            # agrupar por fecha_pago
            grupos: Dict[str, List[Dict[str, Any]]] = {}
            for p in pagos:
                f = str(p.get("fecha_pago") or "")
                if not f:
                    continue
                grupos.setdefault(f, []).append(p)

            for fecha, items in sorted(grupos.items(), reverse=True):
                items = self._filtros_y_sort(items)

                tabla = self._build_table_with_click_sort()
                total_dia = 0.0

                for p in items:
                    deposito = float(p.get("deposito") or p.get("pago_deposito") or 0.0)
                    calc = self.math.recalc_from_pago_row(p, deposito)
                    total_vista = float(calc.get("total_vista", 0.0))
                    total_dia += total_vista
                    row = self._build_row_pagado(pago=p, calc=calc)
                    tabla.rows.append(row)

                    # mapas para totales rápidos
                    pid = int(p.get("id_pago_nomina") or p.get("id_pago") or 0)
                    self._row_total[pid] = total_vista
                    self._fecha_by_id[pid] = fecha
                    self._ids_by_date.setdefault(fecha, set()).add(pid)

                # snapshot del grupo ya con todas las filas
                self._refresh_table_snapshot(fecha)

                tabla_scroll = self.table_builder.wrap_scroll(tabla, height=240, width=1600)

                total_lbl = ft.Text(f"Total día: ${total_dia:,.2f}", italic=True, size=11)
                header = ft.Row(
                    [
                        ft.Text(f"Pagos del {fecha}", weight=ft.FontWeight.BOLD, size=12),
                        total_lbl,
                        ft.Container(width=16),
                        ft.IconButton(
                            icon=ft.icons.ADD,
                            tooltip="Agregar pago pagado al grupo",
                            on_click=lambda e, f=fecha: self._abrir_dialogo_alta_pago_pagado(f),
                        ),
                        ft.IconButton(
                            icon=ft.icons.DELETE_FOREVER,
                            icon_color=ft.colors.RED_500,
                            tooltip="Eliminar grupo",
                            on_click=lambda e, f=fecha: self._eliminar_grupo_fecha(f),
                        ),
                    ],
                    spacing=14,
                )

                panel = ft.ExpansionPanel(header=header, content=tabla_scroll, expanded=(fecha in expanded_dates))
                self.view.controls.append(panel)

                # guardar referencias
                self._panel_by_date[fecha] = panel
                self._table_by_date[fecha] = tabla
                self._total_lbl_by_date[fecha] = total_lbl

            if self.page:
                self.page.update()
        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No fue posible cargar los grupos: {ex}")

    # ✅ reemplaza COMPLETO este método
    def _build_table_with_click_sort(self) -> ft.DataTable:
        """
        Construye DataTable con encabezados clickeables.
        - Si la versión de Flet soporta DataColumn.on_sort, usa e.ascending.
        - Si no, hace fallback a GestureDetector (toggle manual).
        - Además, setea sort_column_index / sort_ascending para mostrar la flecha.
        """
        cols: List[ft.DataColumn] = []

        def _make_sort_handler(col_key: str):
            # handler compatible con ambas rutas (on_sort y on_tap)
            def _handler(e=None, k=col_key):
                asc = getattr(e, "ascending", None) if e is not None else None
                self._on_header_sort(k, ascending=asc)
            return _handler

        for key in self.COLUMNS:
            w = self.table_builder.DEFAULT_WIDTHS.get(key, 90)
            title = key.replace("_", " ").title()
            text = ft.Text(title, size=self.table_builder.font_size, weight=ft.FontWeight.BOLD)

            if key in self.CLICK_SORT:
                # Intento usar on_sort (si la versión lo soporta)
                try:
                    cols.append(
                        ft.DataColumn(
                            label=ft.Container(text, width=w),
                            on_sort=_make_sort_handler(key),
                        )
                    )
                except TypeError:
                    # Fallback: label clickeable (toggle manual)
                    cols.append(
                        ft.DataColumn(
                            label=ft.Container(
                                ft.GestureDetector(on_tap=_make_sort_handler(key), content=text),
                                width=w,
                            )
                        )
                    )
            else:
                cols.append(ft.DataColumn(label=ft.Container(text, width=w)))

        table = ft.DataTable(
            columns=cols,
            rows=[],
            heading_row_height=self.table_builder.heading_row_height,
            data_row_min_height=self.table_builder.data_row_min_height,
            data_row_max_height=self.table_builder.data_row_max_height,
            column_spacing=self.table_builder.column_spacing,
        )

        # Mostrar flecha de orden activo
        if self.sort_key in self.IDX:
            table.sort_column_index = self.IDX[self.sort_key]
            table.sort_ascending = self.sort_asc

        return table

    # ✅ reemplaza COMPLETO este método
    def _on_header_sort(self, key: str, *, ascending: Optional[bool] = None):
        """
        Si viene desde DataColumn.on_sort, 'ascending' trae la dirección pedida por Flet.
        Si viene del fallback (tap), alternamos manualmente.
        """
        if ascending is None:
            # toggle manual
            if self.sort_key == key:
                self.sort_asc = not self.sort_asc
            else:
                self.sort_key, self.sort_asc = key, True
        else:
            # respeta la dirección que envía Flet
            self.sort_key, self.sort_asc = key, bool(ascending)

        self.reload(preserve_expansion=True)

    # ---------- Filtros + Sort (estable, con prioridad) ----------
    def _filtros_y_sort(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ide = (self.filters.get("id_empleado") or "").strip()
        idp = (self.filters.get("id_pago_conf") or self.filters.get("id_pago") or "").strip()

        # 1) Orden base por sort_key usando el helper (con compute_total real)
        def compute_total(row: Dict[str, Any]) -> float:
            deposito = float(row.get("deposito") or row.get("pago_deposito") or 0.0)
            calc = self.math.recalc_from_pago_row(row, deposito)
            return float(calc.get("total_vista", 0.0))

        ordered = self.sort_helper.sort_records(
            items,
            key=self.sort_key,
            asc=self.sort_asc,
            compute_total=compute_total,
        )

        # 2) Prioridad estable por filtros (OR)
        prioritized = self.sort_helper.prioritize_records_by_filters(
            ordered,
            id_empleado_prefix=ide,
            id_pago_prefix=idp,
            match_mode="or",
        )
        return prioritized

    # ---------- Fila pagado con edición controlada ----------
    def _build_row_pagado(self, *, pago: Dict[str, Any], calc: Dict[str, float]) -> ft.DataRow:
        font = 11
        id_pago = int(pago.get("id_pago_nomina") or pago.get("id_pago"))
        num = int(pago.get("numero_nomina") or 0)
        nombre = str(pago.get("nombre_completo") or pago.get("nombre_empleado") or "")
        horas = float(pago.get("horas") or 0.0)
        sueldo_h = float(pago.get("sueldo_por_hora") or 0.0)
        monto_base = float(pago.get("monto_base") or 0.0)

        # ✅ corrección: usar 'pago' (no 'p')
        deposito_actual = float(pago.get("deposito") or pago.get("pago_deposito") or 0.0)
        efectivo_actual = float(pago.get("efectivo") or pago.get("pago_efectivo") or 0.0)
        total_vista = float(calc.get("total_vista", 0.0))

        # modo edición?
        en_edicion = id_pago in self._edit_rows
        buf = self._edit_buffer.get(id_pago, {"deposito": deposito_actual, "efectivo": efectivo_actual})
        dep_ui = float(buf.get("deposito", deposito_actual) or 0.0)
        efe_ui = float(buf.get("efectivo", efectivo_actual) or 0.0)

        # saldo desde UI
        saldo_ui = round(max(0.0, total_vista - (dep_ui + efe_ui)), 2)

        def money(v: float) -> str:
            return f"${float(v):,.2f}"

        # controles texto
        txt_id = ft.Text(str(id_pago), size=font)
        txt_num = ft.Text(str(num), size=font)
        txt_nombre = ft.Text(nombre, size=font)
        txt_horas = ft.Text(f"{horas:.2f}", size=font)
        txt_sueldo = ft.Text(money(sueldo_h), size=font)
        txt_base = ft.Text(money(monto_base), size=font)

        txt_desc = ft.Text(money(calc.get("descuentos_view", 0.0)), size=font)
        txt_prest = ft.Text(money(calc.get("prestamos_view", 0.0)), size=font)

        # EDITABLES: se habilitan solo cuando está en edición
        tf_deposito = ft.TextField(
            value=f"{dep_ui:.2f}",
            width=90, height=28, text_align=ft.TextAlign.RIGHT, dense=True, text_size=font,
            read_only=False,
            disabled=not en_edicion,
            on_change=lambda e, pid=id_pago: self._on_edit_change(pid, "deposito", e.control.value),
        )
        tf_efectivo = ft.TextField(
            value=f"{efe_ui:.2f}",
            width=90, height=28, text_align=ft.TextAlign.RIGHT, dense=True, text_size=font,
            read_only=False,
            disabled=not en_edicion,
            on_change=lambda e, pid=id_pago: self._on_edit_change(pid, "efectivo", e.control.value),
        )

        # saldo/total reflejan UI
        txt_saldo = ft.Text(money(saldo_ui), size=font)
        txt_total = ft.Text(money(total_vista), size=font)

        # acciones
        acciones = ft.Row(spacing=4)
        acciones.controls.append(
            ft.IconButton(
                icon=ft.icons.REMOVE_CIRCLE_OUTLINE,
                tooltip="Editar descuentos",
                icon_color=ft.colors.AMBER_700,
                on_click=lambda e, pr=pago: self._abrir_modal_descuentos(pr),
            )
        )

        # botón préstamos: solo AZUL si este registro tiene préstamo (prestamos_view > 0)
        has_prestamo_en_registro = float(calc.get("prestamos_view", 0.0) or 0.0) > 1e-9
        acciones.controls.append(
            ft.IconButton(
                icon=ft.icons.ACCOUNT_BALANCE_WALLET,
                tooltip="Ver préstamos" if has_prestamo_en_registro else "Sin préstamos para este registro",
                icon_color=ft.colors.BLUE_600 if has_prestamo_en_registro else ft.colors.GREY_400,
                disabled=not has_prestamo_en_registro,
                on_click=(lambda e, pr=pago: self._abrir_modal_prestamos(pr)) if has_prestamo_en_registro else None,
            )
        )

        if en_edicion:
            acciones.controls.append(
                ft.IconButton(
                    icon=ft.icons.CHECK,
                    icon_color=ft.colors.GREEN_600,
                    tooltip="Guardar",
                    on_click=lambda e, pid=id_pago: self._guardar_edicion_pagado(pid),
                )
            )
            acciones.controls.append(
                ft.IconButton(
                    icon=ft.icons.CLOSE,
                    icon_color=ft.colors.GREY_700,
                    tooltip="Cancelar",
                    on_click=lambda e, pid=id_pago: self._cancelar_edicion(pid),
                )
            )
        else:
            acciones.controls.append(
                ft.IconButton(
                    icon=ft.icons.EDIT,
                    tooltip="Editar depósito/efectivo",
                    on_click=lambda e, pid=id_pago: self._activar_edicion(pid),
                )
            )
        acciones.controls.append(
            ft.IconButton(
                icon=ft.icons.DELETE_OUTLINE,
                icon_color=ft.colors.RED_500,
                tooltip="Eliminar pago",
                on_click=lambda e, pid=id_pago: self._eliminar_pago_pagado(pid),
            )
        )

        estado_chip = ft.Container(
            content=ft.Text("PAGADO", size=10),
            bgcolor=ft.colors.GREEN_100,
            padding=ft.padding.symmetric(4, 6),
            border_radius=6,
        )

        row = ft.DataRow(
            cells=[
                ft.DataCell(txt_id),
                ft.DataCell(txt_num),
                ft.DataCell(txt_nombre),
                ft.DataCell(txt_horas),
                ft.DataCell(txt_sueldo),
                ft.DataCell(txt_base),
                ft.DataCell(txt_desc),
                ft.DataCell(txt_prest),
                ft.DataCell(tf_deposito),
                ft.DataCell(txt_saldo),
                ft.DataCell(tf_efectivo),
                ft.DataCell(txt_total),
                ft.DataCell(acciones),
                ft.DataCell(estado_chip),
            ]
        )

        # registrar para refrescos
        self.row_refresh.register_row(
            id_pago,
            row,
            txt_desc=txt_desc, txt_prest=txt_prest,
            tf_deposito=tf_deposito, txt_saldo=txt_saldo, txt_total=txt_total,
        )
        row._id_pago = id_pago

        # feedback si dep+efe > total
        over = (dep_ui + efe_ui) > (total_vista + 1e-9)
        self.row_refresh.set_deposito_border_color(row, ft.colors.RED if over else None)

        return row

    # ---------- Edición controlada ----------
    def _activar_edicion(self, id_pago: int):
        self._edit_rows.add(id_pago)
        # carga buffer inicial desde DB
        try:
            r = self.payment_model.get_by_id(id_pago)
            if r.get("status") == "success":
                p = r["data"]
                self._edit_buffer[id_pago] = {
                    "deposito": float(p.get(self.payment_model.E.PAGO_DEPOSITO.value) or 0.0),
                    "efectivo": float(p.get(self.payment_model.E.PAGO_EFECTIVO.value) or 0.0),
                }
        except Exception:
            self._edit_buffer.setdefault(id_pago, {"deposito": 0.0, "efectivo": 0.0})

        # cambia la fila a modo edición inline (sin recargar todo)
        self._toggle_inline_edit(id_pago, True)

    def _cancelar_edicion(self, id_pago: int):
        self._edit_rows.discard(id_pago)
        self._edit_buffer.pop(id_pago, None)
        self._toggle_inline_edit(id_pago, False)

    def _toggle_inline_edit(self, id_pago: int, editing: bool):
        """Activa/Desactiva edición en la fila SIN recargar toda la tabla."""
        row = self.row_refresh.get_row(None, id_pago)
        if not row:
            self.reload(preserve_expansion=True)
            return

        # 1) Toggle de los TextField (NO llamar tf.update() aquí)
        dep_cell = row.cells[self.IDX["deposito"]].content
        efe_cell = row.cells[self.IDX["efectivo"]].content
        for tf in (dep_cell, efe_cell):
            if isinstance(tf, ft.TextField):
                tf.disabled = not editing
                tf.read_only = False

        # 2) Reemplazo de botones de acciones
        acciones: ft.Row = row.cells[self.IDX["acciones"]].content
        if isinstance(acciones, ft.Row):
            base_btns, delete_btn = [], None
            for c in acciones.controls:
                if isinstance(c, ft.IconButton) and c.icon == ft.icons.DELETE_OUTLINE:
                    delete_btn = c
                elif isinstance(c, ft.IconButton) and c.icon in (
                    ft.icons.REMOVE_CIRCLE_OUTLINE, ft.icons.ACCOUNT_BALANCE_WALLET
                ):
                    base_btns.append(c)

            acciones.controls.clear()
            acciones.controls.extend(base_btns)

            if editing:
                acciones.controls.append(
                    ft.IconButton(
                        icon=ft.icons.CHECK,
                        icon_color=ft.colors.GREEN_600,
                        tooltip="Guardar",
                        on_click=lambda e, pid=id_pago: self._guardar_edicion_pagado(pid),
                    )
                )
                acciones.controls.append(
                    ft.IconButton(
                        icon=ft.icons.CLOSE,
                        icon_color=ft.colors.GREY_700,
                        tooltip="Cancelar",
                        on_click=lambda e, pid=id_pago: self._cancelar_edicion(pid),
                    )
                )
            else:
                acciones.controls.append(
                    ft.IconButton(
                        icon=ft.icons.EDIT,
                        tooltip="Editar depósito/efectivo",
                        on_click=lambda e, pid=id_pago: self._activar_edicion(pid),
                    )
                )
            if delete_btn:
                acciones.controls.append(delete_btn)

        # 3) Actualiza SOLO la fila / tabla (no el TextField individual)
        row.update()
        if self.page:
            self.page.update()

        # 4) Foco "seguro" al entrar a edición (solo si ya está en la página)
        if editing and isinstance(dep_cell, ft.TextField) and getattr(dep_cell, "page", None):
            try:
                dep_cell.focus()
            except Exception:
                pass

    def _on_edit_change(self, id_pago: int, campo: str, value: str):
        # si por alguna razón llega un change sin estar en edición, lo activamos
        if id_pago not in self._edit_rows:
            self._activar_edicion(id_pago)

        try:
            v = float((value or "0").replace(",", ""))
        except Exception:
            v = 0.0
        buf = self._edit_buffer.setdefault(id_pago, {"deposito": 0.0, "efectivo": 0.0})
        buf[campo] = v
        # preview UI
        try:
            r = self.payment_model.get_by_id(id_pago)
            if r.get("status") == "success":
                p_db = r["data"]
                calc = self.math.recalc_from_pago_row(p_db, buf.get("deposito", 0.0))
                total_vista = float(calc.get("total_vista", 0.0))
                saldo = max(0.0, round(total_vista - (buf.get("deposito", 0.0) + buf.get("efectivo", 0.0)), 2))
                row = self.row_refresh.get_row(None, id_pago)
                if row:
                    self.row_refresh.set_descuentos(row, calc["descuentos_view"])
                    self.row_refresh.set_prestamos(row, calc["prestamos_view"])
                    self.row_refresh.set_total(row, total_vista)
                    self.row_refresh.set_saldo(row, saldo)
                    self.row_refresh.set_deposito_border_color(
                        row,
                        ft.colors.RED if (buf.get("deposito", 0.0) + buf.get("efectivo", 0.0)) > total_vista + 1e-9 else None
                    )
                    row.update()
        except Exception:
            pass

    def _guardar_edicion_pagado(self, id_pago: int):
        try:
            buf = self._edit_buffer.get(id_pago, {"deposito": 0.0, "efectivo": 0.0})
            r = self.payment_model.get_by_id(id_pago)
            if r.get("status") != "success":
                return
            p_db = r["data"]
            calc = self.math.recalc_from_pago_row(p_db, buf.get("deposito", 0.0))
            total_vista = float(calc.get("total_vista", 0.0))
            deposito = float(buf.get("deposito", 0.0))
            efectivo = float(buf.get("efectivo", 0.0))
            if deposito + efectivo > total_vista + 1e-9:
                ModalAlert.mostrar_info("Montos inválidos", "Depósito + Efectivo no puede superar el total.")
                return
            saldo = max(0.0, round(total_vista - (deposito + efectivo), 2))

            payload = {
                self.payment_model.E.PAGO_DEPOSITO.value: deposito,
                self.payment_model.E.PAGO_EFECTIVO.value: efectivo,
                self.payment_model.E.SALDO.value: saldo,
                self.payment_model.E.MONTO_TOTAL.value: total_vista,
            }
            self.payment_model.update_pago(id_pago, payload)

            # actualizar solo la fila y total del día
            self._edit_rows.discard(id_pago)
            self._edit_buffer.pop(id_pago, None)
            self._refrescar_fila(id_pago)  # también ajusta total del día
            self.open_group(self._fecha_by_id.get(id_pago, ""))  # mantener expandido

            # volver a modo vista sin recargar todo
            self._toggle_inline_edit(id_pago, False)
        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo guardar la edición: {ex}")

    # ---------- Eliminar ----------
    def _eliminar_pago_pagado(self, id_pago: int):
        def ok():
            try:
                okflag = False
                if hasattr(self.repo, "eliminar_pago"):
                    r = self.repo.eliminar_pago(id_pago, force=True)
                    okflag = (r or {}).get("status") == "success"
                if not okflag and hasattr(self.payment_model, "eliminar_pago"):
                    r = self.payment_model.eliminar_pago(id_pago)
                    okflag = (r or {}).get("status") == "success"
                if okflag:
                    self._remove_row_if_exists(id_pago)
                    fecha = self._fecha_by_id.pop(id_pago, "")
                    if fecha:
                        self._ids_by_date.get(fecha, set()).discard(id_pago)
                        self._row_total.pop(id_pago, None)
                        self._update_total_label_for(fecha)
                    if self.page:
                        self.page.update()
                else:
                    ModalAlert.mostrar_info("Error", "Backend no permite eliminar el pago.")
            except Exception as ex:
                ModalAlert.mostrar_info("Error", str(ex))
        ModalAlert(
            title_text="Eliminar Pago (Confirmado)",
            message=f"¿Eliminar el pago #{id_pago}? Esta acción es permanente.",
            on_confirm=ok
        ).mostrar()

    # ---------- Modales ----------
    def _abrir_modal_descuentos(self, pago_row: Dict[str, Any]):
        p = {
            "id_pago": int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago")),
            "numero_nomina": int(pago_row.get("numero_nomina") or 0),
            "estado": pago_row.get("estado"),
        }
        def on_ok(_):
            self._refrescar_descuentos_y_totales(p["id_pago"])
        ModalDescuentos(pago_data=p, on_confirmar=on_ok).mostrar()

    def _abrir_modal_prestamos(self, pago_row: Dict[str, Any]):
        num = int(pago_row.get("numero_nomina") or 0)
        pago_id = int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago"))
        p = {"id_pago": pago_id, "numero_nomina": num, "estado": pago_row.get("estado")}
        def on_ok(_):
            self._refrescar_fila(pago_id)
        ModalPrestamosNomina(pago_data=p, on_confirmar=on_ok).mostrar()

    def _refrescar_fila(self, id_pago: int):
        """Recalcula la fila y ajusta el 'Total día' sin recargar todo."""
        try:
            r = self.payment_model.get_by_id(id_pago)
            if r.get("status") == "success":
                p_db = r["data"]
                fecha = str(p_db.get(self.payment_model.E.FECHA_PAGO.value) or "")
                self._fecha_by_id[id_pago] = fecha
                deposito = float(p_db.get(self.payment_model.E.PAGO_DEPOSITO.value) or 0.0)
                efectivo = float(p_db.get(self.payment_model.E.PAGO_EFECTIVO.value) or 0.0)
                calc = self.math.recalc_from_pago_row(p_db, deposito)
                total_vista = float(calc.get("total_vista", 0.0))
                saldo = max(0.0, round(total_vista - (deposito + efectivo), 2))

                row = self.row_refresh.get_row(None, id_pago)
                if row:
                    self.row_refresh.set_descuentos(row, calc["descuentos_view"])
                    self.row_refresh.set_prestamos(row, calc["prestamos_view"])
                    self.row_refresh.set_total(row, total_vista)
                    self.row_refresh.set_saldo(row, saldo)
                    row.update()

                # actualizar total del día con mapas
                self._row_total[id_pago] = total_vista
                self._ids_by_date.setdefault(fecha, set()).add(id_pago)
                self._update_total_label_for(fecha)
                if self.page:
                    self.page.update()
        except Exception:
            pass

    # ---------- CRUD grupos ----------
    def _crear_grupo_pagado(self, f: date):
        fecha = f.strftime("%Y-%m-%d")
        try:
            ok = False
            if hasattr(self.repo, "crear_grupo_pagado"):
                r = self.repo.crear_grupo_pagado(fecha)
                ok = (r or {}).get("status") == "success"
            elif hasattr(self.payment_model, "crear_grupo_pagado"):
                r = self.payment_model.crear_grupo_pagado(fecha)
                ok = (r or {}).get("status") == "success"
            elif hasattr(self.payment_model, "crear_grupo_por_fecha"):
                r = self.payment_model.crear_grupo_por_fecha(fecha, estado="pagado")
                ok = (r or {}).get("status") == "success"
            if not ok:
                ModalAlert.mostrar_info("No disponible", "Backend no soporta crear grupos pagados.")
                return
            self._ensure_panel_for_date(fecha, expand=True)
            self._abrir_dialogo_alta_pago_pagado(fecha)
        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo crear el grupo: {ex}")

    def _eliminar_grupo_fecha(self, fecha: str):
        def ok():
            try:
                okflag = False
                if hasattr(self.repo, "eliminar_grupo_por_fecha"):
                    r = self.repo.eliminar_grupo_por_fecha(fecha, force=True)
                    okflag = (r or {}).get("status") == "success"
                if not okflag and hasattr(self.payment_model, "eliminar_pagos_por_fecha"):
                    r = self.payment_model.eliminar_pagos_por_fecha(fecha, force=True)
                    okflag = (r or {}).get("status") == "success"
                if okflag:
                    # quitar panel y mapas
                    self._remove_panel(fecha)
                    if self.page:
                        self.page.update()
                else:
                    ModalAlert.mostrar_info("Error", "No existe método backend para eliminar el grupo por fecha.")
            except Exception as ex:
                ModalAlert.mostrar_info("Error", str(ex))
        ModalAlert(
            title_text="Eliminar Grupo",
            message=f"¿Eliminar TODOS los pagos del {fecha}? Esta acción no se puede deshacer.",
            on_confirm=ok
        ).mostrar()

    # ---------- Alta manual de pago pagado ----------
    def _abrir_dialogo_alta_pago_pagado(self, fecha: str):
        numero_field = ft.TextField(label="Número de nómina", width=180)
        horas_field = ft.TextField(label="Horas trabajadas", width=180)
        deposito_field = ft.TextField(label="Depósito", width=180, value="0.00")
        efectivo_field = ft.TextField(label="Efectivo", width=180, value="0.00")

        nombre_lbl = ft.Text("", size=12, italic=True)
        sueldo_lbl = ft.Text("", size=12)

        def on_num_changed(e):
            try:
                num = int((numero_field.value or "").strip())
                emp = self.payment_model.employee_model.get_by_numero_nomina(num) or {}
                nombre_lbl.value = emp.get("nombre_completo", "")
                sh = float(emp.get("sueldo_por_hora", 0) or 0.0)
                if sh <= 0:
                    sd = float(emp.get("sueldo_diario", 0) or 0.0)
                    sh = round(sd / 8.0, 2) if sd > 0 else 0.0
                sueldo_lbl.value = f"Sueldo/Hora: ${sh:,.2f}"
            except Exception:
                nombre_lbl.value = ""
                sueldo_lbl.value = ""
            self.page.update()

        numero_field.on_change = on_num_changed

        def confirm(_):
            try:
                num = int((numero_field.value or "").strip())
                horas = float((horas_field.value or "0").replace(",", ""))
                dep = float((deposito_field.value or "0").replace(",", ""))
                efe = float((efectivo_field.value or "0").replace(",", ""))
            except Exception:
                ModalAlert.mostrar_info("Datos inválidos", "Verifica número, horas, depósito y efectivo.")
                return
            self._crear_pago_pagado_en_grupo(fecha, num, horas, dep, efe)

            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(f"Agregar pago pagado ({fecha})"),
            content=ft.Column(
                [numero_field, horas_field, deposito_field, efectivo_field, nombre_lbl, sueldo_lbl],
                tight=True, spacing=8
            ),
            actions=[ft.TextButton("Cancelar", on_click=lambda e: self._close_dialog(dlg)),
                     ft.ElevatedButton("Agregar", on_click=confirm)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def _close_dialog(self, dlg: ft.AlertDialog):
        dlg.open = False
        self.page.update()

    def _crear_pago_pagado_en_grupo(self, fecha: str, numero_nomina: int, horas: float, deposito: float, efectivo: float):
        """Crea un PAGO PAGADO para 'fecha' validando duplicados y lo inserta en UI."""
        try:
            if numero_nomina <= 0 or horas <= 0:
                ModalAlert.mostrar_info("Datos inválidos", "Número y horas deben ser > 0.")
                return

            if self.payment_model.existe_pago_para_fecha(numero_nomina, fecha, incluir_pendientes=True):
                ModalAlert.mostrar_info("Duplicado", "Ese empleado ya tiene un pago en este grupo (fecha).")
                return

            emp = self.payment_model.employee_model.get_by_numero_nomina(numero_nomina) or {}
            sh = float(emp.get("sueldo_por_hora", 0) or 0.0)
            if sh <= 0:
                sd = float(emp.get("sueldo_diario", 0) or 0.0)
                sh = round(sd / 8.0, 2) if sd > 0 else 0.0
            if sh <= 0:
                ModalAlert.mostrar_info("Empleado sin sueldo", "No se pudo determinar sueldo por hora.")
                return

            monto_base = round(sh * horas, 2)
            fi = ff = fecha
            grupo_token = self.payment_model._build_grupo_token(fi, ff)

            ins_q = f"""
                INSERT INTO {self.payment_model.E.TABLE.value} (
                    {self.payment_model.E.NUMERO_NOMINA.value},
                    {self.payment_model.E.GRUPO_PAGO.value}, {self.payment_model.E.FECHA_INICIO.value},
                    {self.payment_model.E.FECHA_FIN.value}, {self.payment_model.E.ESTADO_GRUPO.value},
                    {self.payment_model.E.FECHA_PAGO.value},
                    {self.payment_model.E.TOTAL_HORAS_TRABAJADAS.value},
                    {self.payment_model.E.MONTO_BASE.value},
                    {self.payment_model.E.MONTO_TOTAL.value},
                    {self.payment_model.D.MONTO_DESCUENTO.value},
                    {self.payment_model.P.PRESTAMO_MONTO.value},
                    {self.payment_model.E.SALDO.value},
                    {self.payment_model.E.PAGO_DEPOSITO.value},
                    {self.payment_model.E.PAGO_EFECTIVO.value},
                    {self.payment_model.E.ESTADO.value}
                ) VALUES (%s,%s,%s,%s,'abierto',%s,%s,%s,%s,0,0,%s,0,%s,'pendiente')
            """
            self.payment_model.db.run_query(
                ins_q,
                (numero_nomina, grupo_token, fi, ff, fecha, horas, monto_base, monto_base, monto_base, monto_base)
            )
            new_id = int(self.payment_model.db.get_last_insert_id())

            try:
                self.payment_model._prefill_borrador_descuentos(new_id, numero_nomina)
            except Exception:
                pass

            self.payment_model.confirmar_pago(new_id)

            r = self.payment_model.get_by_id(new_id)
            if r.get("status") == "success":
                p_db = r["data"]
                calc = self.math.recalc_from_pago_row(p_db, deposito)
                total_vista = float(calc.get("total_vista", 0.0))
                if deposito + efectivo > total_vista + 1e-9:
                    ModalAlert.mostrar_info("Montos inválidos", "Depósito + Efectivo no puede superar el total.")
                    return
                saldo = max(0.0, round(total_vista - (deposito + efectivo), 2))
                self.payment_model.update_pago(new_id, {
                    self.payment_model.E.PAGO_DEPOSITO.value: deposito,
                    self.payment_model.E.PAGO_EFECTIVO.value: efectivo,
                    self.payment_model.E.SALDO.value: saldo,
                    self.payment_model.E.MONTO_TOTAL.value: total_vista,
                })

                # push visual inmediato
                p_db["deposito"] = deposito
                p_db["efectivo"] = efectivo
                self.push_pago_pagado(p_db)
                self.open_group(fecha)
        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo crear el pago: {ex}")

    # ---------- Helpers internos ----------
    def _ensure_panel_for_date(self, fecha: str, *, expand: bool = False):
        """Crea panel vacío si no existe."""
        if fecha in self._panel_by_date:
            if expand:
                self._panel_by_date[fecha].expanded = True
            return

        tabla = self._build_table_with_click_sort()
        tabla_scroll = self.table_builder.wrap_scroll(tabla, height=240, width=1600)

        total_lbl = ft.Text("Total día: $0.00", italic=True, size=11)
        header = ft.Row(
            [
                ft.Text(f"Pagos del {fecha}", weight=ft.FontWeight.BOLD, size=12),
                total_lbl,
                ft.Container(width=16),
                ft.IconButton(
                    icon=ft.icons.ADD,
                    tooltip="Agregar pago pagado al grupo",
                    on_click=lambda e, f=fecha: self._abrir_dialogo_alta_pago_pagado(f),
                ),
                ft.IconButton(
                    icon=ft.icons.DELETE_FOREVER,
                    icon_color=ft.colors.RED_500,
                    tooltip="Eliminar grupo",
                    on_click=lambda e, f=fecha: self._eliminar_grupo_fecha(f),
                ),
            ],
            spacing=14,
        )

        panel = ft.ExpansionPanel(header=header, content=tabla_scroll, expanded=expand)

        # Insertar en orden (lista descendente por fecha)
        inserted = False
        for i, p in enumerate(self.view.controls):
            try:
                t = p.header.controls[0]
                existing = (t.value or "").split()[-1]
                if fecha > existing:  # string YYYY-MM-DD compara bien
                    self.view.controls.insert(i, panel)
                    inserted = True
                    break
            except Exception:
                continue
        if not inserted:
            self.view.controls.append(panel)

        # guardar refs
        self._panel_by_date[fecha] = panel
        self._table_by_date[fecha] = tabla
        self._total_lbl_by_date[fecha] = total_lbl
        self._ids_by_date.setdefault(fecha, set())

    def _remove_panel(self, fecha: str):
        p = self._panel_by_date.pop(fecha, None)
        if p and p in self.view.controls:
            self.view.controls.remove(p)
        self._table_by_date.pop(fecha, None)
        self._total_lbl_by_date.pop(fecha, None)
        # limpiar ids relacionados
        ids = self._ids_by_date.pop(fecha, set())
        for pid in list(ids):
            self._row_total.pop(pid, None)
            self._fecha_by_id.pop(pid, None)

    def _remove_row_if_exists(self, id_pago: int):
        """Intenta quitar una fila por id en su tabla, si existía (para hacer upsert o tras eliminar)."""
        fecha = self._fecha_by_id.get(id_pago, "")
        tabla = self._table_by_date.get(fecha)
        if not tabla:
            # buscar en todas (por si no sabíamos la fecha)
            for f, t in self._table_by_date.items():
                row = self.row_refresh.get_row(None, id_pago)
                if row and row in t.rows:
                    t.rows.remove(row)
                    break
        else:
            row = self.row_refresh.get_row(None, id_pago)
            if row and row in tabla.rows:
                tabla.rows.remove(row)
        if fecha:
            self._refresh_table_snapshot(fecha)
        else:
            self._refresh_table_snapshot()  # refresca todas por seguridad

    def _update_total_label_for(self, fecha: str):
        ids = self._ids_by_date.get(fecha, set())
        total = sum(self._row_total.get(i, 0.0) for i in ids)
        lbl = self._total_lbl_by_date.get(fecha)
        if lbl:
            lbl.value = f"Total día: ${total:,.2f}"

    # Caches
    def _invalidate_caches(self):
        for obj in (self.payment_model, self.discount_model, self.detalles_desc_model):
            for nm in ("invalidate_cache", "clear_cache", "reset_cache", "refresh_cache"):
                fn = getattr(obj, nm, None)
                if callable(fn):
                    try:
                        fn()
                    except:
                        pass

    def _refrescar_descuentos_y_totales(self, id_pago: int):
        """Vuelve a leer descuentos confirmados y refresca la fila + total del día."""
        try:
            # Evita lecturas viejas de helpers/modelos
            self._invalidate_caches()

            r = self.payment_model.get_by_id(id_pago)
            if r.get("status") != "success":
                return
            p_db = r["data"]
            fecha = str(p_db.get(self.payment_model.E.FECHA_PAGO.value) or "")
            self._fecha_by_id[id_pago] = fecha

            # Lee el total de descuentos ya confirmados
            total_desc = float(self.discount_model.get_total_descuentos_por_pago(id_pago) or 0.0)

            # Recalcula totales visibles con depósito actual
            deposito = float(p_db.get(self.payment_model.E.PAGO_DEPOSITO.value) or 0.0)
            efectivo = float(p_db.get(self.payment_model.E.PAGO_EFECTIVO.value) or 0.0)
            calc = self.math.recalc_from_pago_row(p_db, deposito)

            total_vista = float(calc.get("total_vista", 0.0))
            saldo = max(0.0, round(total_vista - (deposito + efectivo), 2))

            # Actualiza celdas de la fila
            row = self.row_refresh.get_row(None, id_pago)
            if row:
                self.row_refresh.set_descuentos(row, total_desc)               # fuerza el nuevo total de descuentos
                self.row_refresh.set_prestamos(row, calc["prestamos_view"])
                self.row_refresh.set_total(row, total_vista)
                self.row_refresh.set_saldo(row, saldo)
                row.update()

            # Ajusta el total del día
            if fecha:
                self._row_total[id_pago] = total_vista
                self._ids_by_date.setdefault(fecha, set()).add(id_pago)
                self._update_total_label_for(fecha)

            if self.page:
                self.page.update()
        except Exception as ex:
            ModalAlert.mostrar_info("Descuentos", f"No se pudo actualizar: {ex}")

    def _refresh_table_snapshot(self, fecha: Optional[str] = None) -> None:
        """
        Mantiene sincronizado el snapshot interno de PaymentSortFilterHelper
        con las filas actualmente visibles en la DataTable.

        Úsalo SIEMPRE que agregues, quites o reemplaces filas en una tabla.
        - Si pasas `fecha`, refresca solo la tabla de ese grupo.
        - Si lo llamas sin argumentos, refresca todas las tablas cargadas.
        """
        try:
            if fecha is None:
                for t in self._table_by_date.values():
                    try:
                        self.sort_helper.refresh_snapshot(t)
                    except Exception:
                        pass
            else:
                t = self._table_by_date.get(fecha)
                if t:
                    self.sort_helper.refresh_snapshot(t)
        except Exception:
            # no romper el flujo de UI por un snapshot fallido
            pass
