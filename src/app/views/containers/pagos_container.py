from __future__ import annotations

from datetime import datetime, date
from typing import List, Dict, Any
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

# Tablas compactas y filas (builder de tablas)
from app.helpers.pagos.payment_table_builder import PaymentTableBuilder

# Refresher de filas (no construye filas; solo refresca)
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
    Contenedor de Pagos refactorizado:
    - Tabla compacta de PENDIENTES (edición) al inicio.
    - Expansibles por día (CONFIRMADOS) con tabla compacta y scroll interno.
    - Cálculo visual con PaymentViewMath (descuentos/préstamos de borrador ó confirmados).
    - Refresco granular de celdas con PaymentRowRefresh.
    """

    # --- configuración de columnas compactas (coinciden con índices usados) ---
    COLUMNS_EDICION = [
        "id_pago", "id_empleado", "nombre", "fecha_pago", "horas", "sueldo_hora",
        "monto_base", "descuentos", "prestamos", "saldo", "deposito",
        "efectivo", "total", "ediciones", "acciones", "estado"
    ]

    COLUMNS_COMPACTAS_CONFIRMADO = [
    "id_pago", "id_empleado", "nombre",
    "monto_base", "descuentos", "prestamos",
    "deposito", "saldo", "efectivo", "total", "estado"
    ]


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

        # Helpers de negocio/UI
        self.repo = PagosRepo(payment_model=self.payment_model)
        self.math = PaymentViewMath(
            discount_model=self.discount_model,
            detalles_desc_model=self.detalles_desc_model,
            loan_payment_model=self.loan_payment_model,
            detalles_prestamo_model=self.detalles_prestamo_model,
        )
        self.table_builder = PaymentTableBuilder()  # tablas compactas
        self.row_refresh = PaymentRowRefresh()      # refresco granular
        self.scroll = PagosScrollHelper()          # scaffold con scroll

        # Estado UI para depósito tipeado
        self.depositos_temporales: dict[int, float] = {}
        self._deposito_buffer: dict[int, str] = {}

        # Selector de fechas
        self.selector_fechas = DateModalSelector(on_dates_confirmed=self._generar_por_fechas)

        # Controles UI header
        self.input_id = ft.TextField(
            label="ID Empleado",
            width=150,
            height=34,
            border_color=ft.colors.OUTLINE,
            on_change=self._validar_input_id,
        )

        # Tabla de pendientes (editable) + contenedor de expansibles
        self.tabla_pendientes = self.table_builder.build_table(self.COLUMNS_EDICION, rows=[])
        self.paneles_confirmados = ft.ExpansionPanelList(expand=True, controls=[])

        # Resumen
        self.resumen_pagos = ft.Text(value="", weight=ft.FontWeight.BOLD, size=13)

        self._build()
        self._cargar_pagos()

    # ---------------- UI scaffold ----------------
    def _build(self):
        # Header con acciones
        header_bar = ft.Row(
            controls=[
                crear_boton_importar(lambda: self._no_impl("Importar")),
                crear_boton_exportar(lambda: self._no_impl("Exportar")),
                crear_boton_agregar(self._abrir_modal_fechas_disponibles),
            ],
            spacing=10,
            alignment=ft.MainAxisAlignment.START,
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
            datatable=None,   # ahora usamos layout propio
            header=header,
            footer=footer,
            required_min_width=1700,
            body_override=body,
        )

    def _no_impl(self, what: str):
        ModalAlert.mostrar_info("Próximamente", f"La acción '{what}' se implementará más adelante.")

    # ------------- Carga / Render -------------
    def _cargar_pagos(self):
        try:
            pagos = self.repo.listar_pagos(order_desc=True) or []

            # Limpieza
            self.tabla_pendientes.rows.clear()
            self.paneles_confirmados.controls.clear()

            if not pagos:
                # Vacío: solo pintar fila placeholder en pendientes
                self.tabla_pendientes.rows.append(
                    ft.DataRow(cells=[ft.DataCell(ft.Text("-")) for _ in range(len(self.COLUMNS_EDICION))])
                )
                self.resumen_pagos.value = "Total pagado: $0.00"
                if self.page:
                    self.page.update()
                return

            # Split pendientes / confirmados
            pendientes: List[Dict[str, Any]] = []
            confirmados: List[Dict[str, Any]] = []
            for p in pagos:
                if str(p.get("estado", "")).lower() == "pagado":
                    confirmados.append(p)
                else:
                    pendientes.append(p)

            # ---------------- PENDIENTES (tabla editable) ----------------
            for p in pendientes:
                id_pago = int(p.get("id_pago_nomina") or p.get("id_pago"))
                # depósito visible (buffer -> temporales -> DB)
                if id_pago in self._deposito_buffer:
                    try:
                        deposito_ui = float(self._deposito_buffer[id_pago])
                    except Exception:
                        deposito_ui = float(self.depositos_temporales.get(id_pago, p.get("pago_deposito", 0.0) or 0.0))
                else:
                    deposito_ui = float(self.depositos_temporales.get(id_pago, p.get("pago_deposito", 0.0) or 0.0))

                calc = self.math.recalc_from_pago_row(p, deposito_ui)
                # construir fila compacta editable (índices deben coincidir con COLUMNS_EDICION)
                row = self._build_row_edicion_compacta(
                    p=p,
                    deposito_ui=deposito_ui,
                    calc=calc,
                    tiene_prestamo_activo=bool(self.loan_model.get_prestamo_activo_por_empleado(int(p["numero_nomina"]))),
                )
                self.tabla_pendientes.rows.append(row)

            # ---------------- CONFIRMADOS agrupados por fecha (expansibles) ----------------
            grupos: Dict[str, List[Dict[str, Any]]] = {}
            for p in confirmados:
                fecha = str(p.get("fecha_pago") or "")
                grupos.setdefault(fecha, []).append(p)

            for fecha, pagos_dia in sorted(grupos.items(), reverse=True):
                # armar tabla compacta por día (lectura)
                tabla = self.table_builder.build_table(self.COLUMNS_COMPACTAS_CONFIRMADO, rows=[])
                total_dia = 0.0

                for p in pagos_dia:
                    id_pago = int(p.get("id_pago_nomina") or p.get("id_pago"))
                    deposito_ui = float(p.get("pago_deposito", 0.0) or 0.0)
                    calc = self.math.recalc_from_pago_row(p, deposito_ui)
                    total_dia += float(calc["total_vista"])
                    row = self._build_row_confirmado_compacto(p, calc)
                    tabla.rows.append(row)

                # wrap con scroll interno
                tabla_scroll = self.table_builder.wrap_scroll(tabla, height=220, width=1600)

                # panel expansible
                panel = ft.ExpansionPanel(
                    header=ft.Row(
                        [
                            ft.Text(f"Pagos del {fecha}", weight=ft.FontWeight.BOLD, size=12),
                            ft.Text(f"Total día: ${total_dia:.2f}", italic=True, size=11),
                        ],
                        spacing=20,
                    ),
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


    def _build_row_edicion_compacta(
        self,
        *,
        p: Dict[str, Any],
        deposito_ui: float,
        calc: Dict[str, float],
        tiene_prestamo_activo: bool,
    ) -> ft.DataRow:
        """
        Fila editable compacta que coincide con COLUMNS_EDICION (16 columnas).
        Además registra referencias en PaymentRowRefresh para refresco granular.
        """
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

        # Depósito editable
        tf_deposito = ft.TextField(
            value=f"{float(deposito_ui or 0):.2f}",
            width=90,
            height=28,
            text_align=ft.TextAlign.RIGHT,
            dense=True,
            text_size=font,
            on_change=lambda e, pid=id_pago: self._on_deposito_change(pid, e.control.value),
            on_blur=lambda e, pid=id_pago: self._actualizar_fila_pago(pid),
            on_submit=lambda e, pid=id_pago: self._actualizar_fila_pago(pid),
        )

        txt_efectivo = ft.Text(t_money(calc.get("efectivo", 0.0)), size=font)
        txt_total = ft.Text(t_money(calc.get("total_vista", 0.0)), size=font)

        # Botones edición (descuentos / préstamos)
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

        # Acciones (confirmar / eliminar)
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
                ft.DataCell(txt_id),          # 0 id_pago
                ft.DataCell(txt_num),         # 1 id_empleado
                ft.DataCell(txt_nombre),      # 2 nombre
                ft.DataCell(txt_fecha),       # 3 fecha_pago
                ft.DataCell(txt_horas),       # 4 horas
                ft.DataCell(txt_sueldo),      # 5 sueldo_hora
                ft.DataCell(txt_monto_base),  # 6 monto_base
                ft.DataCell(txt_desc),        # 7 descuentos
                ft.DataCell(txt_prest),       # 8 prestamos
                ft.DataCell(txt_saldo),       # 9 saldo ajustado
                ft.DataCell(tf_deposito),     # 10 depósito
                ft.DataCell(txt_efectivo),    # 11 efectivo
                ft.DataCell(txt_total),       # 12 total
                ft.DataCell(ediciones_cell),  # 13 ediciones
                ft.DataCell(acciones_cell),   # 14 acciones
                ft.DataCell(estado_chip),     # 15 estado
            ]
        )
        # registrar referencias para refresco ágil
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
        row._id_pago = id_pago  # hint
        return row


    def _build_row_confirmado_compacto(self, p: Dict[str, Any], calc: Dict[str, float]) -> ft.DataRow:
        """
        Fila de lectura compacta para confirmados.
        Muestra monto base, descuentos, préstamos, depósito confirmado, saldo, efectivo, total y estado.
        """
        font = 11
        id_pago = int(p.get("id_pago_nomina") or p.get("id_pago"))
        num = int(p.get("numero_nomina") or 0)
        nombre = str(p.get("nombre_completo") or p.get("nombre_empleado") or "")
        monto_base = float(p.get("monto_base") or 0.0)

        # Depósito realmente pagado desde la DB
        deposito_real = float(p.get("pago_deposito", 0.0) or 0.0)

        # Recalcular usando el depósito real
        calc_conf = self.math.recalc_from_pago_row(p, deposito_real)

        def tx(v: float) -> str:
            return f"${float(v):,.2f}"

        estado_chip = ft.Container(
            content=ft.Text("PAGADO", size=10),
            bgcolor=ft.colors.GREEN_100,
            padding=ft.padding.symmetric(4, 6),
            border_radius=6,
        )

        return ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(str(id_pago), size=font)),                         # ID Pago
                ft.DataCell(ft.Text(str(num), size=font)),                             # ID Empleado
                ft.DataCell(ft.Text(nombre, size=font)),                               # Nombre
                ft.DataCell(ft.Text(tx(monto_base), size=font)),                       # Monto Base
                ft.DataCell(ft.Text(tx(calc_conf.get("descuentos_view", 0.0)), size=font)),  # Descuentos
                ft.DataCell(ft.Text(tx(calc_conf.get("prestamos_view", 0.0)), size=font)),   # Préstamos
                ft.DataCell(ft.Text(tx(deposito_real), size=font)),                    # Depósito confirmado
                ft.DataCell(ft.Text(tx(calc_conf.get("saldo_ajuste", 0.0)), size=font)),     # Saldo ajustado
                ft.DataCell(ft.Text(tx(calc_conf.get("efectivo", 0.0)), size=font)),        # Efectivo
                ft.DataCell(ft.Text(tx(calc_conf.get("total_vista", 0.0)), size=font)),     # Total
                ft.DataCell(estado_chip),                                              # Estado
            ]
        )


    # ------------- Eventos Depósito -------------
    def _on_deposito_change(self, id_pago: int, value: str):
        self._deposito_buffer[id_pago] = value or ""

    # ------------- Recalculo por fila -------------
    def _actualizar_fila_pago(self, id_pago_nomina: int):
        try:
            row = self.row_refresh.get_row(self.tabla_pendientes, id_pago_nomina)
            if not row:
                return

            p_db = self.repo.obtener_pago(id_pago_nomina)
            if not p_db:
                return

            buf = self._deposito_buffer.get(id_pago_nomina, None)
            if buf is not None:
                try:
                    deposito_ui = float(buf)
                except Exception:
                    deposito_ui = 0.0
            else:
                deposito_ui = float(self.depositos_temporales.get(id_pago_nomina, p_db.get("pago_deposito", 0.0) or 0.0))

            calc = self.math.recalc_from_pago_row(p_db, deposito_ui)

            # Actualiza celdas (sin reconstruir la fila)
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
        except Exception as ex:
            print(f"❌ Error al actualizar fila: {ex}")

    # ------------- Acciones -------------
    def _guardar_pago_confirmado(self, id_pago_nomina: int):
        try:
            res = self.repo.confirmar_pago(id_pago_nomina)
            # fallback legacy si tu entorno usa update_pago_completo
            if res.get("status") != "success" and hasattr(self.payment_model, "update_pago_completo"):
                detalles_desc = self.detalles_desc_model.obtener_por_id_pago(id_pago_nomina) or {}
                res = self.payment_model.update_pago_completo(
                    id_pago=id_pago_nomina, descuentos=detalles_desc, estado="pagado"
                )

            if res.get("status") == "success":
                # mover refresco simple; al recargar se reubica en confirmados/expansibles
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
                    self.depositos_temporales.pop(id_pago_nomina, None)
                    self._deposito_buffer.pop(id_pago_nomina, None)
                    self._cargar_pagos()
                else:
                    ModalAlert.mostrar_info("Error", res.get("message", "No se pudo eliminar."))
            except Exception as ex:
                ModalAlert.mostrar_info("Error al eliminar", str(ex))

        ModalAlert(
            title_text="Eliminar Pago",
            message=f"¿Eliminar el pago #{id_pago_nomina}?",
            on_confirm=eliminar,
        ).mostrar()

    # ------------- Modales -------------
    def _abrir_modal_descuentos(self, pago_row: Dict[str, Any]):
        p = {
            "id_pago": int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago")),
            "numero_nomina": int(pago_row["numero_nomina"]),
            "estado": pago_row.get("estado"),
        }

        def on_ok(_):
            self._actualizar_fila_pago(p["id_pago"])

        ModalDescuentos(pago_data=p, on_confirmar=on_ok).mostrar()

    def _abrir_modal_prestamos(self, pago_row: Dict[str, Any]):
        """
        Abre el modal de PRÉSTAMOS para NÓMINA (multi-préstamo, auto-save),
        sincronizado con el módulo de Préstamos.
        """
        num = int(pago_row["numero_nomina"])
        pago_id = int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago"))

        # Verificación en caliente
        prestamo_activo = self.loan_model.get_prestamo_activo_por_empleado(num)
        if not prestamo_activo:
            ModalAlert.mostrar_info("Sin préstamo", f"El empleado {num} no tiene préstamos activos.")
            return

        p = {"id_pago": pago_id, "numero_nomina": num, "estado": pago_row.get("estado")}

        def on_ok(_):
            # refresca SOLO esta fila (suma de detalles de préstamos)
            self._actualizar_fila_pago(pago_id)

        ModalPrestamosNomina(pago_data=p, on_confirmar=on_ok).mostrar()

    # ------------- Fechas disponibles -------------
    def _get_fechas_disponibles_para_pago(self) -> List[date]:
        """
        Devuelve la lista de fechas disponibles para generar pagos,
        considerando las asistencias completas y no utilizadas.
        """
        try:
            if hasattr(self.assistance_model, "get_fechas_disponibles_para_pago"):
                return self.assistance_model.get_fechas_disponibles_para_pago() or []

            # Fallback desde min/max
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
            # 1) Fechas ya utilizadas (bloqueadas)
            bloqueadas = self.payment_model.get_fechas_utilizadas() or []
            bloqueadas = [
                datetime.strptime(f, "%Y-%m-%d").date() if isinstance(f, str) else f
                for f in bloqueadas
            ]
            self.selector_fechas.set_fechas_bloqueadas(bloqueadas)

            # 2) Fechas disponibles normales
            disponibles = self._get_fechas_disponibles_para_pago()
            disponibles = [d for d in disponibles if d not in bloqueadas]

            # 3) Fechas totalmente vacías (sin asistencias registradas)
            fi = self.assistance_model.get_fecha_minima_asistencia()
            ff = self.assistance_model.get_fecha_maxima_asistencia()
            if fi and ff:
                vacias = self.assistance_model.get_fechas_vacias(fi, ff)
                disponibles.extend(vacias)

            # 4) Únicas + ordenadas
            disponibles = sorted(set(disponibles))

            # 5) Enviar al selector
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
        texto = self.input_id.value.strip()
        self.input_id.border_color = ft.colors.OUTLINE if not texto or texto.isdigit() else ft.colors.RED_400
        if self.page:
            self.page.update()
