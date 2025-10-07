from __future__ import annotations

from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple
import flet as ft

# Core / Models
from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert
from app.views.containers.modal_descuentos import ModalDescuentos
from app.views.containers.date_modal_selector import DateModalSelector

# Modal de préstamos para NÓMINA (multi-préstamo, auto-save)
from app.views.containers.modal_prestamos_nomina import ModalPrestamosNomina

from app.models.payment_model import PaymentModel
from app.models.discount_model import DiscountModel
from app.models.assistance_model import AssistanceModel
from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.descuento_detalles_model import DescuentoDetallesModel
from app.models.detalles_pagos_prestamo_model import DetallesPagosPrestamoModel

# Helpers
from app.helpers.pagos.payment_view_math import PaymentViewMath
from app.helpers.pagos.pagos_repo import PagosRepo

# Sorting/Filters (si existe)
try:
    from app.helpers.pagos.sorting_filter_payment_helper import SortingFilterPaymentHelper
except Exception:
    SortingFilterPaymentHelper = None  # fallback interno

# Tablas compactas
from app.helpers.pagos.payment_table_builder import PaymentTableBuilder

# Refresher por fila
from app.helpers.pagos.row_refresh import PaymentRowRefresh

# Scroll helper
from app.helpers.pagos.scroll_pagos_helper import PagosScrollHelper

# Botones header (fábrica)
from app.helpers.boton_factory import (
    crear_boton_importar,
    crear_boton_exportar,
    crear_boton_agregar,
)


class PagosContainer(ft.Container):
    """
    Pagos:
    - Pendientes (edición) con recálculo en vivo y guardado exacto.
    - Confirmados por fecha (expansibles) con CRUD de grupos y filas.
    - Filtros que priorizan coincidencias sin ocultar el resto.
    - Sorting solo en CONFIRMADOS al clickear encabezados (id_pago, monto_base, total).
    - Registros PAGADOS editables (depósito).
    """

    # --- columnas ---
    COLUMNS_EDICION = [
        "id_pago", "id_empleado", "nombre", "fecha_pago", "horas", "sueldo_hora",
        "monto_base", "descuentos", "prestamos", "saldo", "deposito",
        "efectivo", "total", "ediciones", "acciones", "estado"
    ]

    # En confirmados construimos columnas manualmente para añadir sort en encabezados
    COLS_CONF_CLICK_SORT = ("id_pago", "monto_base", "total")

    def __init__(self):
        super().__init__(expand=True, padding=0, alignment=ft.alignment.top_center)
        self.page = AppState().page

        # Modelos
        self.payment_model = PaymentModel()
        self.payment_model.crear_sp_horas_trabajadas_para_pagos()
        self.discount_model = DiscountModel()
        self.assistance_model = AssistanceModel()
        self.loan_model = LoanModel()
        self.loan_payment_model = LoanPaymentModel()
        self.detalles_desc_model = DescuentoDetallesModel()
        self.detalles_prestamo_model = DetallesPagosPrestamoModel()

        # Helpers
        self.repo = PagosRepo(payment_model=self.payment_model)
        self.math = PaymentViewMath(
            discount_model=self.discount_model,
            detalles_desc_model=self.detalles_desc_model,
            loan_payment_model=self.loan_payment_model,
            detalles_prestamo_model=self.detalles_prestamo_model,
        )
        self.table_builder = PaymentTableBuilder()
        self.row_refresh = PaymentRowRefresh()
        self.scroll = PagosScrollHelper()
        self.sf = SortingFilterPaymentHelper() if SortingFilterPaymentHelper else None

        # Filtros (prioritarios, no excluyentes)
        self.filters_pend = {"id_empleado": "", "id_pago": ""}
        self.filters_conf = {"id_empleado": "", "id_pago": ""}

        # Estado de sorting SOLO para confirmados (encabezados clicables)
        self.sort_conf_key, self.sort_conf_asc = "id_pago", True

        # Estado UI depósito tipeado
        self._deposito_buffer: dict[int, str] = {}
        self._saving_rows: set[int] = set()

        # Selector de fechas (generación y grupos pagados)
        self.selector_fechas = DateModalSelector(on_dates_confirmed=self._generar_por_fechas)

        # Controles UI header (solo filtros y acciones)
        self.input_id = ft.TextField(
            label="ID Empleado",
            width=150,
            height=34,
            border_color=ft.colors.OUTLINE,
            on_change=self._validar_input_id,
        )
        self.input_id_pago_pend = ft.TextField(
            label="ID Pago (pend.)",
            width=140,
            height=34,
            border_color=ft.colors.OUTLINE,
            on_change=lambda e: self._on_filter_change(scope="pend", key="id_pago", value=e.control.value),
        )
        self.input_id_pago_conf = ft.TextField(
            label="ID Pago (conf.)",
            width=140,
            height=34,
            border_color=ft.colors.OUTLINE,
            on_change=lambda e: self._on_filter_change(scope="conf", key="id_pago", value=e.control.value),
        )

        # Tabla de pendientes + expansibles confirmados
        self.tabla_pendientes = self.table_builder.build_table(self.COLUMNS_EDICION, rows=[])
        self.paneles_confirmados = ft.ExpansionPanelList(expand=True, controls=[])

        # Resumen
        self.resumen_pagos = ft.Text(value="", weight=ft.FontWeight.BOLD, size=13)

        self._build()
        self._cargar_pagos()

    # ---------------- UI scaffold ----------------
    def _build(self):
        # Acciones + filtros (sin controles de sort)
        header_bar = ft.Row(
            controls=[
                crear_boton_importar(lambda: self._no_impl("Importar")),
                crear_boton_exportar(lambda: self._no_impl("Exportar")),
                crear_boton_agregar(self._abrir_modal_fechas_disponibles),
                ft.ElevatedButton(
                    "Agregar grupo pagado",
                    icon=ft.icons.ADD,
                    on_click=lambda e: self._abrir_modal_agregar_grupo_pagado(),
                ),
                ft.Container(width=20),
                ft.Text("Filtros (prioritarios):", size=12, italic=True),
                self.input_id,
                self.input_id_pago_pend,
                self.input_id_pago_conf,
            ],
            spacing=10,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        header = ft.Column(
            spacing=8,
            controls=[
                ft.Text("ÁREA DE PAGOS", style=ft.TextThemeStyle.TITLE_MEDIUM),
                header_bar,
            ],
        )

        # Secciones
        titulo_pend = ft.Text("Pendientes (edición)", weight=ft.FontWeight.BOLD, size=12)
        tabla_pend_scroll = self.table_builder.wrap_scroll(self.tabla_pendientes, height=260, width=1600)

        titulo_conf = ft.Text("Confirmados por fecha", weight=ft.FontWeight.BOLD, size=12)
        paneles_conf_scroll = ft.Container(self.paneles_confirmados, expand=False, width=1600)

        body = ft.Column(
            spacing=10,
            controls=[
                titulo_pend,
                tabla_pend_scroll,
                ft.Divider(),
                titulo_conf,
                paneles_conf_scroll,
            ],
        )

        footer = ft.Container(self.resumen_pagos, padding=10, alignment=ft.alignment.center)

        # Scaffold con scroll ALWAYS
        self.content = self.scroll.build_scaffold(
            page=self.page,
            datatable=None,   # layout personalizado
            header=header,
            footer=footer,
            required_min_width=1700,
            body_override=body,
        )

    def _no_impl(self, what: str):
        ModalAlert.mostrar_info("Próximamente", f"La acción '{what}' se implementará más adelante.")

    # -------------------- Filtros (prioritarios) --------------------
    def _on_filter_change(self, *, scope: str, key: str, value: str):
        value = (value or "").strip()
        if scope == "pend":
            self.filters_pend[key] = value
        else:
            self.filters_conf[key] = value
        self._cargar_pagos()

    # ---------------- Carga / Render ----------------
    def _cargar_pagos(self):
        try:
            pagos = self.repo.listar_pagos(order_desc=True) or []

            # Limpieza
            self.tabla_pendientes.rows.clear()
            self.paneles_confirmados.controls.clear()

            if not pagos:
                self.tabla_pendientes.rows.append(
                    ft.DataRow(cells=[ft.DataCell(ft.Text("-")) for _ in range(len(self.COLUMNS_EDICION))])
                )
                self.resumen_pagos.value = "Total pagado: $0.00"
                if self.page:
                    self.page.update()
                return

            # Split
            pendientes: List[Dict[str, Any]] = []
            confirmados: List[Dict[str, Any]] = []
            for p in pagos:
                if str(p.get("estado", "")).lower() == "pagado":
                    confirmados.append(p)
                else:
                    pendientes.append(p)

            # --- Filtros PRIORITARIOS (no excluyentes) ---
            pendientes = self._priorizar_por_filtros(pendientes, self.filters_pend)
            confirmados = self._priorizar_por_filtros(confirmados, self.filters_conf)

            # ---------------- PENDIENTES (editable) ----------------
            for p in pendientes:
                id_pago = int(p.get("id_pago_nomina") or p.get("id_pago"))
                # depósito visible en UI (buffer -> DB)
                if id_pago in self._deposito_buffer:
                    try:
                        deposito_ui = float(self._sanitize_float(self._deposito_buffer[id_pago]))
                    except Exception:
                        deposito_ui = float(p.get("pago_deposito", 0.0) or 0.0)
                else:
                    deposito_ui = float(p.get("pago_deposito", 0.0) or 0.0)

                calc = self.math.recalc_from_pago_row(p, deposito_ui)

                row = self._build_row_edicion_compacta(
                    p=p,
                    deposito_ui=deposito_ui,
                    calc=calc,
                    tiene_prestamo_activo=bool(self.loan_model.get_prestamo_activo_por_empleado(int(p["numero_nomina"]))),
                )
                self.tabla_pendientes.rows.append(row)

            # ---------------- CONFIRMADOS agrupados por fecha ----------------
            grupos: Dict[str, List[Dict[str, Any]]] = {}
            for p in confirmados:
                fecha = str(p.get("fecha_pago") or "")
                grupos.setdefault(fecha, []).append(p)

            for fecha, pagos_dia in sorted(grupos.items(), reverse=True):
                # Ordenar dentro del grupo según sort_conf_key/asc
                pagos_dia = self._aplicar_sort_confirmados(pagos_dia)

                # tabla con encabezados clicables para sort
                tabla = self._build_confirmados_table_with_click_sort(fecha)
                total_dia = 0.0

                for p in pagos_dia:
                    deposito_real = float(p.get("pago_deposito", 0.0) or 0.0)
                    calc = self.math.recalc_from_pago_row(p, deposito_real)
                    total_dia += float(calc["total_vista"])
                    row = self._build_row_confirmado_editable(p, calc, fecha_grupo=fecha)
                    tabla.rows.append(row)

                tabla_scroll = self.table_builder.wrap_scroll(tabla, height=220, width=1600)

                # Header del panel con acciones de grupo
                panel_header = ft.Row(
                    [
                        ft.Text(f"Pagos del {fecha}", weight=ft.FontWeight.BOLD, size=12),
                        ft.Text(f"Total día: ${total_dia:.2f}", italic=True, size=11),
                        ft.Container(width=16),
                        ft.IconButton(
                            icon=ft.icons.ADD,
                            tooltip="Agregar pago a este grupo",
                            on_click=lambda e, f=fecha: self._agregar_pago_a_grupo(f),
                        ),
                        ft.IconButton(
                            icon=ft.icons.EDIT_CALENDAR,
                            tooltip="Mover grupo a otra fecha",
                            on_click=lambda e, f=fecha: self._editar_grupo_fecha(f),
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

                panel = ft.ExpansionPanel(
                    header=panel_header,
                    content=tabla_scroll,
                    expanded=False,
                )
                self.paneles_confirmados.controls.append(panel)

            # Resumen global
            total_pagado = self.repo.total_pagado_confirmado()
            self.resumen_pagos.value = f"Total pagado (confirmado): ${float(total_pagado):.2f}"

            if self.page:
                self.page.update()

        except Exception as ex:
            ModalAlert.mostrar_info("Error al cargar pagos", str(ex))

    # -------------------- Fila editable (pendientes) --------------------
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

        def t_money(v: float) -> str:
            return f"${float(v):,.2f}"

        # celdas
        txt_id = ft.Text(str(id_pago), size=font)
        txt_num = ft.Text(str(num), size=font)
        txt_nombre = ft.Text(nombre, size=font)
        txt_fecha = ft.Text(fecha_pago, size=font)
        txt_horas = ft.Text(f"{horas:.2f}", size=font)
        txt_sueldo = ft.Text(t_money(sueldo_h), size=font)
        txt_monto_base = ft.Text(t_money(monto_base), size=font)
        txt_desc = ft.Text(t_money(calc.get("descuentos_view", 0.0)), size=font)
        txt_prest = ft.Text(t_money(calc.get("prestamos_view", 0.0)), size=font)
        txt_saldo = ft.Text(t_money(calc.get("saldo_ajuste", 0.0)), size=font)

        # Depósito editable (recalcula UI; guarda en DB en blur/submit)
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

        txt_efectivo = ft.Text(t_money(calc.get("efectivo", 0.0)), size=font)
        txt_total = ft.Text(t_money(calc.get("total_vista", 0.0)), size=font)

        btn_desc = ft.IconButton(
            icon=ft.icons.REMOVE_CIRCLE_OUTLINE,
            tooltip="Editar descuentos",
            icon_color=ft.colors.AMBER_700,
            on_click=lambda e, pago_row=p: self._abrir_modal_descuentos(pago_row),
        )
        btn_prest = ft.IconButton(
            icon=ft.icons.ACCOUNT_BALANCE_WALLET,
            tooltip="Editar préstamos",
            icon_color=ft.colors.BLUE_600,
            disabled=(not tiene_prestamo_activo),
            on_click=lambda e, pago_row=p: self._abrir_modal_prestamos(pago_row),
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
                ft.DataCell(txt_id),
                ft.DataCell(txt_num),
                ft.DataCell(txt_nombre),
                ft.DataCell(txt_fecha),
                ft.DataCell(txt_horas),
                ft.DataCell(txt_sueldo),
                ft.DataCell(txt_monto_base),
                ft.DataCell(txt_desc),
                ft.DataCell(txt_prest),
                ft.DataCell(txt_saldo),
                ft.DataCell(tf_deposito),
                ft.DataCell(txt_efectivo),
                ft.DataCell(txt_total),
                ft.DataCell(ediciones_cell),
                ft.DataCell(acciones_cell),
                ft.DataCell(estado_chip),
            ]
        )
        # registrar referencias
        self.row_refresh.register_row(
            id_pago,
            row,
            txt_desc=txt_desc,
            txt_prest=txt_prest,
            txt_saldo=txt_saldo,
            tf_deposito=tf_deposito,
            txt_efectivo=txt_efectivo,
            txt_total=txt_total,
            estado_chip=estado_chip,
        )
        row._id_pago = id_pago
        # feedback visual si depósito excede total
        self.row_refresh.set_deposito_border_color(
            row, ft.colors.RED if deposito_ui > float(calc.get("total_vista", 0.0)) + 1e-9 else None
        )
        return row

    # -------------------- Confirmados: tabla con encabezados clicables --------------------
    def _build_confirmados_table_with_click_sort(self, fecha_grupo: str) -> ft.DataTable:
        """
        DataTable para confirmados con encabezados clicables de sort (id_pago, monto_base, total).
        El estado de sort es global para confirmados.
        """
        # Columnas en el orden final
        col_keys = [
            "id_pago", "id_empleado", "nombre",
            "monto_base", "descuentos", "prestamos",
            "deposito", "saldo", "efectivo", "total", "estado", "acciones"
        ]

        cols: List[ft.DataColumn] = []
        for key in col_keys:
            label_ctrl = self._make_header_label(key)
            cols.append(
                ft.DataColumn(
                    label=ft.Container(
                        label_ctrl,
                        width=self.table_builder.DEFAULT_WIDTHS.get(key, 90),
                    )
                )
            )

        return ft.DataTable(
            columns=cols,
            rows=[],
            heading_row_height=self.table_builder.heading_row_height,
            data_row_min_height=self.table_builder.data_row_min_height,
            data_row_max_height=self.table_builder.data_row_max_height,
            column_spacing=self.table_builder.column_spacing,
        )

    def _make_header_label(self, key: str) -> ft.Control:
        """
        Construye la etiqueta de encabezado.
        - Si es un campo sortable, muestra botón que alterna asc/desc.
        - En otros, solo texto.
        """
        title = key.replace("_", " ").title()
        is_sortable = key in self.COLS_CONF_CLICK_SORT

        if not is_sortable:
            return ft.Text(title, size=self.table_builder.font_size, weight=ft.FontWeight.BOLD)

        # Icono segun estado actual
        active = (self.sort_conf_key == key)
        icon = None
        if active:
            icon = ft.icons.ARROW_UPWARD if self.sort_conf_asc else ft.icons.ARROW_DOWNWARD

        def do_click(_):
            if self.sort_conf_key == key:
                self.sort_conf_asc = not self.sort_conf_asc
            else:
                self.sort_conf_key, self.sort_conf_asc = key, True
            if self.page:
                self.page.update()
            self._cargar_pagos()

        btn = ft.TextButton(
            content=ft.Row(
                [
                    ft.Text(title, size=self.table_builder.font_size, weight=ft.FontWeight.BOLD),
                    ft.Icon(icon) if icon else ft.Container(width=0, height=0),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=do_click,
        )
        return btn

    def _aplicar_sort_confirmados(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        key, asc = self.sort_conf_key, self.sort_conf_asc

        def k(row: Dict[str, Any]):
            if key == "id_pago":
                return int(row.get("id_pago_nomina") or row.get("id_pago") or 0)
            if key == "monto_base":
                return float(row.get("monto_base") or 0.0)
            if key == "total":
                deposito = float(row.get("pago_deposito", 0.0) or 0.0)
                calc = self.math.recalc_from_pago_row(row, deposito)
                return float(calc.get("total_vista", 0.0))
            return 0

        return sorted(items, key=k, reverse=not asc)

    # -------------------- Fila lectura/edición (confirmados) --------------------
    def _build_row_confirmado_editable(self, p: Dict[str, Any], calc: Dict[str, float], *, fecha_grupo: str) -> ft.DataRow:
        """
        Confirmados: igual que lectura, pero con depósito editable y acciones de eliminación.
        """
        font = 11
        id_pago = int(p.get("id_pago_nomina") or p.get("id_pago"))
        num = int(p.get("numero_nomina") or 0)
        nombre = str(p.get("nombre_completo") or p.get("nombre_empleado") or "")
        monto_base = float(p.get("monto_base") or 0.0)
        deposito_real = float(p.get("pago_deposito", 0.0) or 0.0)

        def tx(v: float) -> str:
            return f"${float(v):,.2f}"

        estado_chip = ft.Container(
            content=ft.Text("PAGADO", size=10),
            bgcolor=ft.colors.GREEN_100,
            padding=ft.padding.symmetric(4, 6),
            border_radius=6,
        )

        # Depósito editable en confirmados
        tf_deposito = ft.TextField(
            value=f"{float(deposito_real or 0):.2f}",
            width=90,
            height=28,
            text_align=ft.TextAlign.RIGHT,
            dense=True,
            text_size=font,
            on_change=lambda e, pid=id_pago: self._on_deposito_change_pagado(pid, e.control.value),
            on_blur=lambda e, pid=id_pago: self._guardar_deposito_desde_ui_pagado(pid),
            on_submit=lambda e, pid=id_pago: self._guardar_deposito_desde_ui_pagado(pid),
        )

        txt_desc = ft.Text(tx(calc.get("descuentos_view", 0.0)), size=font)
        txt_prest = ft.Text(tx(calc.get("prestamos_view", 0.0)), size=font)
        txt_saldo = ft.Text(tx(calc.get("saldo_ajuste", 0.0)), size=font)
        txt_efectivo = ft.Text(tx(calc.get("efectivo", 0.0)), size=font)
        txt_total = ft.Text(tx(calc.get("total_vista", 0.0)), size=font)

        acciones = ft.Row(
            [
                ft.IconButton(
                    icon=ft.icons.DELETE_OUTLINE,
                    icon_color=ft.colors.RED_500,
                    tooltip="Eliminar pago (confirmado)",
                    on_click=lambda e, pid=id_pago: self._eliminar_pago_pagado(pid),
                ),
            ],
            spacing=4,
        )

        row = ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(str(id_pago), size=font)),      # ID Pago
                ft.DataCell(ft.Text(str(num), size=font)),          # ID Empleado
                ft.DataCell(ft.Text(nombre, size=font)),            # Nombre
                ft.DataCell(ft.Text(tx(monto_base), size=font)),    # Monto Base
                ft.DataCell(txt_desc),                              # Descuentos
                ft.DataCell(txt_prest),                             # Préstamos
                ft.DataCell(tf_deposito),                           # Depósito (editable)
                ft.DataCell(txt_saldo),                             # Saldo
                ft.DataCell(txt_efectivo),                          # Efectivo
                ft.DataCell(txt_total),                             # Total
                ft.DataCell(estado_chip),                           # Estado
                ft.DataCell(acciones),                              # Acciones
            ]
        )

        # registrar en refresher
        self.row_refresh.register_row(
            id_pago,
            row,
            txt_desc=txt_desc,
            txt_prest=txt_prest,
            txt_saldo=txt_saldo,
            tf_deposito=tf_deposito,
            txt_efectivo=txt_efectivo,
            txt_total=txt_total,
            estado_chip=estado_chip,
        )
        row._id_pago = id_pago

        # borde rojo si depósito excede total
        self.row_refresh.set_deposito_border_color(
            row, ft.colors.RED if deposito_real > float(calc.get("total_vista", 0.0)) + 1e-9 else None
        )

        return row

    # ---------------- Eventos Depósito (UI) ----------------
    def _on_deposito_change_pend(self, id_pago: int, value: str):
        self._deposito_buffer[id_pago] = value or ""
        try:
            self._actualizar_fila(id_pago, persist=False)
        except Exception as ex:
            print(f"⚠️ recalculo UI (pend): {ex}")

    def _on_deposito_change_pagado(self, id_pago: int, value: str):
        self._deposito_buffer[id_pago] = value or ""
        try:
            self._actualizar_fila(id_pago, persist=False)
        except Exception as ex:
            print(f"⚠️ recalculo UI (pagado): {ex}")

    # ---------------- Recalculo + Persistencia (común) ----------------
    def _actualizar_fila(self, id_pago_nomina: int, *, persist: bool):
        """
        Recalcula una fila (pendiente o pagada) desde DB + buffer.
        Si persist=True, guarda en DB lo que quedó en UI.
        """
        try:
            # El row lo obtenemos del cache del refresher
            row = self.row_refresh.get_row(self.tabla_pendientes, id_pago_nomina)
            if not row:
                return

            p_db = self.repo.obtener_pago(id_pago_nomina)
            if not p_db:
                return

            buf = self._deposito_buffer.get(id_pago_nomina, None)
            if buf is not None:
                deposito_ui = float(self._sanitize_float(buf))
            else:
                deposito_ui = float(p_db.get("pago_deposito", 0.0) or 0.0)

            calc = self.math.recalc_from_pago_row(p_db, deposito_ui)

            # Actualiza celdas
            self.row_refresh.set_descuentos(row, calc["descuentos_view"])
            self.row_refresh.set_prestamos(row, calc["prestamos_view"])
            self.row_refresh.set_saldo(row, calc["saldo_ajuste"])
            self.row_refresh.set_efectivo(row, calc["efectivo"])
            self.row_refresh.set_total(row, calc["total_vista"])

            # feedback visual si depósito excede total_vista
            self.row_refresh.set_deposito_border_color(
                row, ft.colors.RED if deposito_ui > calc["total_vista"] + 1e-9 else None
            )
            row.update()

            if not persist:
                return

            # Persistir EXACTAMENTE lo visible
            payload = {
                "pago_deposito": deposito_ui,
                "pago_efectivo": float(calc["efectivo"]),
                "saldo": float(calc["saldo_ajuste"]),
                "monto_total": float(calc["total_vista"]),
            }

            ok = False
            try:
                if hasattr(self.repo, "actualizar_montos_ui"):
                    r = self.repo.actualizar_montos_ui(id_pago_nomina, payload)
                    ok = (r or {}).get("status") == "success"
                elif hasattr(self.payment_model, "update_montos_ui"):
                    r = self.payment_model.update_montos_ui(id_pago_nomina, payload)
                    ok = (r or {}).get("status") == "success"
                elif hasattr(self.payment_model, "update_pago_campos"):
                    r = self.payment_model.update_pago_campos(id_pago_nomina, payload)
                    ok = (r or {}).get("status") == "success"
                else:
                    if hasattr(self.payment_model, "update_pago_deposito_y_totales"):
                        r = self.payment_model.update_pago_deposito_y_totales(
                            id_pago=id_pago_nomina,
                            pago_deposito=payload["pago_deposito"],
                            pago_efectivo=payload["pago_efectivo"],
                            saldo=payload["saldo"],
                            monto_total=payload["monto_total"],
                        )
                        ok = (r or {}).get("status") == "success"
            except Exception as ex2:
                print(f"⚠️ Persistencia fallback: {ex2}")
                ok = False

            if not ok:
                ModalAlert.mostrar_info("Atención", "No se pudo guardar los montos en DB. Revisa PaymentModel/Repo.")

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

    def _guardar_deposito_desde_ui_pagado(self, id_pago_nomina: int):
        if id_pago_nomina in self._saving_rows:
            return
        self._saving_rows.add(id_pago_nomina)
        try:
            self._actualizar_fila(id_pago_nomina, persist=True)
        finally:
            self._saving_rows.discard(id_pago_nomina)

    # ---------------- Acciones ----------------
    def _guardar_pago_confirmado(self, id_pago_nomina: int):
        try:
            res = self.repo.confirmar_pago(id_pago_nomina)
            # fallback legacy
            if res.get("status") != "success" and hasattr(self.payment_model, "update_pago_completo"):
                detalles_desc = self.detalles_desc_model.obtener_por_id_pago(id_pago_nomina) or {}
                res = self.payment_model.update_pago_completo(
                    id_pago=id_pago_nomina, descuentos=detalles_desc, estado="pagado"
                )

            if res.get("status") == "success":
                ModalAlert.mostrar_info("Éxito", res.get("message", "Pago confirmado."))
                self._cargar_pagos()
            else:
                ModalAlert.mostrar_info("Error", res.get("message", "No fue posible confirmar el pago."))
        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo confirmar el pago: {str(ex)}")

    def _eliminar_pago(self, id_pago_nomina: int):
        def eliminar():
            try:
                res = self.repo.eliminar_pago(id_pago_nomina)
                if res.get("status") == "success":
                    self._deposito_buffer.pop(id_pago_nomina, None)
                    self._cargar_pagos()
                else:
                    ModalAlert.mostrar_info("Error", res.get("message", "No se pudo eliminar."))
            except Exception as ex:
                ModalAlert.mostrar_info("Error al eliminar", str(ex))
        ModalAlert(
            title_text="Eliminar Pago",
            message=f"¿Eliminar el pago #{id_pago_nomina} (pendiente)?",
            on_confirm=eliminar,
        ).mostrar()

    def _eliminar_pago_pagado(self, id_pago_nomina: int):
        def eliminar():
            try:
                ok = False
                if hasattr(self.repo, "eliminar_pago"):
                    r = self.repo.eliminar_pago(id_pago_nomina, force=True)
                    ok = (r or {}).get("status") == "success"
                if not ok and hasattr(self.payment_model, "eliminar_pago"):
                    r = self.payment_model.eliminar_pago(id_pago_nomina, force=True)
                    ok = (r or {}).get("status") == "success"
                if ok:
                    self._cargar_pagos()
                else:
                    ModalAlert.mostrar_info("Error", "Backend no soporta eliminar pagos pagados (force=True).")
            except Exception as ex:
                ModalAlert.mostrar_info("Error", str(ex))
        ModalAlert(
            title_text="Eliminar Pago (Confirmado)",
            message=f"¿Eliminar el pago # {id_pago_nomina}? Esta acción es permanente.",
            on_confirm=eliminar,
        ).mostrar()

    # ---------------- CRUD Grupos Confirmados ----------------
    def _eliminar_grupo_fecha(self, fecha: str):
        def eliminar():
            try:
                ok = False
                if hasattr(self.repo, "eliminar_grupo_por_fecha"):
                    r = self.repo.eliminar_grupo_por_fecha(fecha, force=True)
                    ok = (r or {}).get("status") == "success"
                if not ok and hasattr(self.payment_model, "eliminar_pagos_por_fecha"):
                    r = self.payment_model.eliminar_pagos_por_fecha(fecha, force=True)
                    ok = (r or {}).get("status") == "success"
                if ok:
                    self._cargar_pagos()
                else:
                    ModalAlert.mostrar_info("Error", "No existe método backend para eliminar el grupo por fecha.")
            except Exception as ex:
                ModalAlert.mostrar_info("Error", str(ex))
        ModalAlert(
            title_text="Eliminar Grupo",
            message=f"¿Eliminar TODOS los pagos del {fecha}? Esta acción no se puede deshacer.",
            on_confirm=eliminar,
        ).mostrar()

    def _editar_grupo_fecha(self, fecha_actual: str):
        """Mover todos los pagos de una fecha a otra (valida solapamientos)."""
        dp = ft.DatePicker(on_change=lambda e: None, on_dismiss=lambda e: None)
        self.page.overlay.append(dp)
        self.page.update()

        def do_move(new_date: date):
            if not new_date:
                return
            nueva = new_date.strftime("%Y-%m-%d")
            try:
                ok = False
                if hasattr(self.repo, "mover_grupo_fecha"):
                    r = self.repo.mover_grupo_fecha(fecha_actual, nueva)
                    ok = (r or {}).get("status") == "success"
                elif hasattr(self.payment_model, "mover_grupo_fecha"):
                    r = self.payment_model.mover_grupo_fecha(fecha_actual, nueva)
                    ok = (r or {}).get("status") == "success"
                if ok:
                    self._cargar_pagos()
                else:
                    ModalAlert.mostrar_info("Error", "Backend no soporta mover grupos de fecha.")
            except Exception as ex:
                ModalAlert.mostrar_info("Error", str(ex))

        dp.on_change = lambda e: do_move(e.control.value)
        dp.pick_date()

    def _abrir_modal_agregar_grupo_pagado(self):
        """
        Agrega un grupo 'pagado' vacío para una fecha elegida y, al terminar,
        abre el modal para agregar pagos a ese grupo.
        Evita fechas duplicadas (no puede haber una fecha dentro de otra).
        """
        # Reutilizamos DateModalSelector para elegir UNA fecha
        def on_dates_ok(fechas: List[date]):
            if not fechas:
                ModalAlert.mostrar_info("Fecha requerida", "Selecciona una fecha para el grupo pagado.")
                return
            f = min(fechas)  # si seleccionan varias, tomamos la mínima
            fecha = f.strftime("%Y-%m-%d")

            # Validar no duplicado
            usadas = self.payment_model.get_fechas_utilizadas() or []
            usadas = [str(u) for u in usadas]
            if fecha in usadas:
                ModalAlert.mostrar_info("Fecha ocupada", f"Ya existe un grupo para {fecha}.")
                return

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

                # Cargar y abrir el modal para agregar pagos a ese grupo
                self._cargar_pagos()
                self._agregar_pago_a_grupo(fecha)

            except Exception as ex:
                ModalAlert.mostrar_info("Error", f"No se pudo crear el grupo: {str(ex)}")

        # Configurar el selector para una elección rápida
        try:
            bloqueadas = self.payment_model.get_fechas_utilizadas() or []
            bloqueadas = [
                datetime.strptime(f, "%Y-%m-%d").date() if isinstance(f, str) else f
                for f in bloqueadas
            ]
            # No bloqueamos aquí, solo informamos al usuario al confirmar si repite
            self.selector_fechas.set_fechas_bloqueadas(bloqueadas)
        except Exception:
            pass

        # Usamos el mismo modal de fechas pero con el callback anterior
        self.selector_fechas.on_dates_confirmed = on_dates_ok
        self.selector_fechas.abrir_dialogo(reset_selection=True)

    def _agregar_pago_a_grupo(self, fecha: str):
        """Agregar un pago manual al grupo (si backend lo permite)."""
        numero_field = ft.TextField(label="Número de nómina", width=180)
        deposito_field = ft.TextField(label="Depósito (opcional)", width=180)

        def confirm(_):
            try:
                num = int(numero_field.value.strip())
                dep = float(self._sanitize_float(deposito_field.value)) if deposito_field.value.strip() else 0.0
            except Exception:
                ModalAlert.mostrar_info("Datos inválidos", "Verifica número y depósito.")
                return
            try:
                ok = False
                if hasattr(self.repo, "agregar_pago_manual_a_fecha"):
                    r = self.repo.agregar_pago_manual_a_fecha(num, fecha, dep)
                    ok = (r or {}).get("status") == "success"
                elif hasattr(self.payment_model, "agregar_pago_manual_a_fecha"):
                    r = self.payment_model.agregar_pago_manual_a_fecha(num, fecha, dep)
                    ok = (r or {}).get("status") == "success"
                if ok:
                    dlg.open = False
                    self.page.update()
                    self._cargar_pagos()
                else:
                    ModalAlert.mostrar_info("No disponible", "Tu backend aún no soporta alta manual en confirmados.")
            except Exception as ex:
                ModalAlert.mostrar_info("Error", str(ex))

        dlg = ft.AlertDialog(
            title=ft.Text(f"Agregar pago a grupo ({fecha})"),
            content=ft.Column([numero_field, deposito_field], tight=True, spacing=8),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: self._close_dialog(e, dlg)),
                ft.ElevatedButton("Agregar", on_click=confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def _close_dialog(self, e, dlg: ft.AlertDialog):
        dlg.open = False
        self.page.update()

    # ------------- Fechas disponibles -------------
    def _get_fechas_disponibles_para_pago(self) -> List[date]:
        try:
            if hasattr(self.assistance_model, "get_fechas_disponibles_para_pago"):
                return self.assistance_model.get_fechas_disponibles_para_pago() or []

            fi = self.assistance_model.get_fecha_minima_asistencia()
            ff = self.assistance_model.get_fecha_maxima_asistencia()
            if not fi or not ff:
                return []

            cur, out = fi, []
            while cur <= ff:
                out.append(cur)
                cur = date.fromordinal(cur.toordinal() + 1)
            return out

        except Exception as ex:
            print(f"❌ Error al obtener fechas disponibles para pago: {ex}")
            return []

    # ------------- Calendario -------------
    def _abrir_modal_fechas_disponibles(self):
        try:
            bloqueadas = self.payment_model.get_fechas_utilizadas() or []
            bloqueadas = [
                datetime.strptime(f, "%Y-%m-%d").date() if isinstance(f, str) else f
                for f in bloqueadas
            ]
            self.selector_fechas.set_fechas_bloqueadas(bloqueadas)

            disponibles = self._get_fechas_disponibles_para_pago()
            disponibles = [d for d in disponibles if d not in bloqueadas]

            fi = self.assistance_model.get_fecha_minima_asistencia()
            ff = self.assistance_model.get_fecha_maxima_asistencia()
            if fi and ff:
                vacias = self.assistance_model.get_fechas_vacias(fi, ff)
                disponibles.extend(vacias)

            disponibles = sorted(set(disponibles))

            if hasattr(self.assistance_model, "get_fechas_estado"):
                fechas_estado = self.assistance_model.get_fechas_estado(fi, ff)
                self.selector_fechas.set_asistencias(fechas_estado)

            self.selector_fechas.set_fechas_disponibles(disponibles)
            self.selector_fechas.abrir_dialogo(reset_selection=True)

        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo abrir el calendario: {str(ex)}")

    # ------------- Generación por fechas -------------
    def _generar_por_fechas(self, fechas: List[date]):
        if not fechas:
            ModalAlert.mostrar_info("Fechas", "Selecciona al menos una fecha.")
            return

        fi = min(fechas)
        ff = max(fechas)
        fi_s = fi.strftime("%Y-%m-%d")
        ff_s = ff.strftime("%Y-%m-%d")

        try:
            if hasattr(self.assistance_model, "get_fechas_estado"):
                estados = self.assistance_model.get_fechas_estado(fi, ff)
                incompletas = [f for f, st in estados.items() if st == "incompleto"]

                if incompletas:
                    if len(incompletas) == 1:
                        msg = (f"No se puede generar la nómina porque la fecha "
                               f"{incompletas[0].strftime('%d/%m/%Y')} tiene asistencias incompletas.")
                    else:
                        fechas_txt = ", ".join(d.strftime("%d/%m/%Y") for d in incompletas)
                        msg = ("No se puede generar la nómina en un rango de fechas donde existan "
                               f"asistencias incompletas.\n\n🔴 Fechas con problemas: {fechas_txt}")
                    ModalAlert.mostrar_info("Rango inválido para generar nómina", msg)
                    return

            res = self.payment_model.generar_pagos_por_rango(fecha_inicio=fi_s, fecha_fin=ff_s)

            try:
                self.assistance_model.marcar_asistencias_como_generadas(fecha_inicio=fi_s, fecha_fin=ff_s)
            except Exception:
                pass

            if res.get("status") == "success":
                ModalAlert.mostrar_info("Nómina por rango", res.get("message", "Pagos generados."))
            else:
                ModalAlert.mostrar_info("Nómina por rango", res.get("message", "Ocurrió un problema."))

        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo generar la nómina: {str(ex)}")

        self._cargar_pagos()

    # ------------- Utils -------------
    def _validar_input_id(self, _):
        texto = (self.input_id.value or "").strip()
        self.input_id.border_color = ft.colors.OUTLINE if not texto or texto.isdigit() else ft.colors.RED_400
        self.filters_pend["id_empleado"] = texto if texto.isdigit() else ""
        self.filters_conf["id_empleado"] = texto if texto.isdigit() else ""
        if self.page:
            self.page.update()
        self._cargar_pagos()

    def _sanitize_float(self, s: str) -> float:
        s = (s or "").strip().replace(",", "")
        if s in ("", ".", "-", "-.", "+", "+."):
            return 0.0
        try:
            return float(s)
        except Exception:
            return 0.0

    def _priorizar_por_filtros(self, items: List[Dict[str, Any]], filtros: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        No excluye. Empuja ARRIBA los items que coinciden con filtros.
        """
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

    # ------------- Modales (descuentos / préstamos) -------------
    def _abrir_modal_descuentos(self, pago_row: Dict[str, Any]):
        p = {
            "id_pago": int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago")),
            "numero_nomina": int(pago_row["numero_nomina"]),
            "estado": pago_row.get("estado"),
        }

        def on_ok(_):
            self._actualizar_fila(p["id_pago"], persist=False)

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
            self._actualizar_fila(pago_id, persist=False)

        ModalPrestamosNomina(pago_data=p, on_confirmar=on_ok).mostrar()
