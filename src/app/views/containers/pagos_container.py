from __future__ import annotations

from datetime import datetime, date
from typing import List, Dict, Any
import inspect
import flet as ft

# Core / Models
from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert
from app.views.containers.date_modal_selector import DateModalSelector

# Modelos / helpers negocio
from app.models.payment_model import PaymentModel
from app.models.discount_model import DiscountModel
from app.models.assistance_model import AssistanceModel
from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.descuento_detalles_model import DescuentoDetallesModel
from app.models.detalles_pagos_prestamo_model import DetallesPagosPrestamoModel

from app.helpers.pagos.payment_view_math import PaymentViewMath
from app.helpers.pagos.pagos_repo import PagosRepo
from app.helpers.pagos.payment_table_builder import PaymentTableBuilder
from app.helpers.pagos.row_refresh import PaymentRowRefresh
from app.helpers.pagos.scroll_pagos_helper import PagosScrollHelper

# --------- Módulos nuevos (con fallback) ----------
try:
    from app.views.containers.modal_fecha_grupo_pagado import ModalFechaGrupoPagado
except Exception:
    ModalFechaGrupoPagado = None  # type: ignore

try:
    from app.views.containers.pagos_pendientes_editables import PagosPendientesEditables
except Exception:
    PagosPendientesEditables = None  # type: ignore

try:
    from app.views.containers.pagos_pagados_expansibles import PagosPagadosExpansibles
except Exception:
    PagosPagadosExpansibles = None  # type: ignore

# Botones header (fábrica)
from app.helpers.boton_factory import (
    crear_boton_importar,
    crear_boton_exportar,
    crear_boton_agregar,
    crear_boton_agregar_fechas_pagadas,   # <-- nuevo
)


class PagosContainer(ft.Container):
    """
    Orquestador del área de pagos.
    - Mantiene ambos módulos sincronizados (pendientes/confirmados).
    - Reacciona a eventos (confirmación, eliminación, creación de grupos).
    """

    def __init__(self):
        super().__init__(expand=True, padding=0, alignment=ft.alignment.top_center)
        self.page = AppState().page

        # --------- Modelos / repos / helpers compartidos ----------
        self.payment_model = PaymentModel()
        self.payment_model.crear_sp_horas_trabajadas_para_pagos()

        self.discount_model = DiscountModel()
        self.assistance_model = AssistanceModel()
        self.loan_model = LoanModel()
        self.loan_payment_model = LoanPaymentModel()
        self.detalles_desc_model = DescuentoDetallesModel()
        self.detalles_prestamo_model = DetallesPagosPrestamoModel()

        self.repo = PagosRepo(payment_model=self.payment_model)
        self.math = PaymentViewMath(
            discount_model=self.discount_model,
            detalles_desc_model=self.detalles_desc_model,
            loan_payment_model=self.loan_payment_model,
            detalles_prestamo_model=self.detalles_prestamo_model,
        )
        self.table_builder = PaymentTableBuilder()
        # Refrescos separados para evitar colisiones entre tablas
        self.row_refresh_pend = PaymentRowRefresh()
        self.row_refresh_conf = PaymentRowRefresh()
        self.scroll = PagosScrollHelper()

        # --------- Módulos UI ----------
        if not PagosPendientesEditables or not PagosPagadosExpansibles:
            raise RuntimeError("Faltan módulos requeridos: PagosPendientesEditables o PagosPagadosExpansibles.")

        # Helper: inyección segura (filtra kwargs no soportados por la firma)
        def _safe_new(_cls, **kwargs):
            try:
                sig = inspect.signature(_cls)
                allowed = {k: v for k, v in kwargs.items() if k in sig.parameters}
                return _cls(**allowed)
            except Exception:
                return _cls(**kwargs)

        # Pendientes -> incluye callback fino cuando se CONFIRMA un pago
        self.pendientes_ui = _safe_new(
            PagosPendientesEditables,
            repo=self.repo,
            payment_model=self.payment_model,
            discount_model=self.discount_model,
            assistance_model=self.assistance_model,
            loan_model=self.loan_model,
            loan_payment_model=self.loan_payment_model,
            detalles_desc_model=self.detalles_desc_model,
            detalles_prestamo_model=self.detalles_prestamo_model,
            math=self.math,
            table_builder=self.table_builder,
            row_refresh=self.row_refresh_pend,
            on_data_changed=self._on_data_changed,
            # estos dos nombres son tolerantes: el módulo puede implementar uno o ignorarlos
            on_pago_confirmado=self._on_pago_confirmado_desde_pendientes,
            on_pago_eliminado=lambda *_: self._on_data_changed(),
        )

        # Confirmados (expansibles)
        self.confirmados_ui = _safe_new(
            PagosPagadosExpansibles,
            repo=self.repo,
            payment_model=self.payment_model,
            discount_model=self.discount_model,
            loan_model=self.loan_model,
            loan_payment_model=self.loan_payment_model,
            detalles_desc_model=self.detalles_desc_model,
            detalles_prestamo_model=self.detalles_prestamo_model,
            math=self.math,
            table_builder=self.table_builder,
            row_refresh=self.row_refresh_conf,
            on_data_changed=self._on_data_changed,  # si su módulo emite cambios globales
        )

        # --------- Estado de filtros ----------
        self.filters_pend = {"id_empleado": "", "id_pago": ""}
        # IMPORTANTE: confirmados usan id_pago_conf como clave principal
        self.filters_conf = {"id_empleado": "", "id_pago_conf": ""}

        # --------- Selectores / modales ----------
        self.selector_rango = DateModalSelector(on_dates_confirmed=self._generar_por_fechas)
        self.modal_fecha_grupo = (
            ModalFechaGrupoPagado(on_date_confirmed=self._crear_grupo_pagado) if ModalFechaGrupoPagado else None
        )

        # --------- Header ----------
        self._build_header()

        # --------- Secciones ----------
        self.resumen_pagos = ft.Text(value="", weight=ft.FontWeight.BOLD, size=13)

        section_pend = ft.Column(
            spacing=6,
            controls=[
                ft.Text("Pendientes (edición)", weight=ft.FontWeight.BOLD, size=12),
                self.table_builder.wrap_scroll(self._as_control(self.pendientes_ui), height=260, width=1600),
            ],
        )
        section_conf = ft.Column(
            spacing=6,
            controls=[
                ft.Text("Confirmados por fecha", weight=ft.FontWeight.BOLD, size=12),
                ft.Container(self._as_control(self.confirmados_ui), expand=False, width=1600),
            ],
        )

        body = ft.Column(spacing=10, controls=[section_pend, ft.Divider(), section_conf])
        footer = ft.Container(self.resumen_pagos, padding=10, alignment=ft.alignment.center)

        self.content = self.scroll.build_scaffold(
            page=self.page,
            datatable=None,
            header=self.header,
            footer=footer,
            required_min_width=1700,
            body_override=body,
        )

        # Primera carga
        self._recargar_todo(preserve_expansion=False)

    # ---------------- util: obtener control raíz del módulo ----------------
    @staticmethod
    def _as_control(module_obj) -> ft.Control:
        if isinstance(module_obj, ft.Control):
            return module_obj
        for name in ("get_control", "control", "view", "root", "as_control", "render", "build", "get_view"):
            attr = getattr(module_obj, name, None)
            if callable(attr):
                try:
                    ctrl = attr()
                    if isinstance(ctrl, ft.Control):
                        return ctrl
                except Exception:
                    continue
            elif isinstance(attr, ft.Control):
                return attr
        raise RuntimeError("El módulo no expone un control raíz ni es un Control.")

    # ---------------- util: llamar a métodos tolerando nombres/firmas ------
    @staticmethod
    def _call(obj, names: list[str], *args, **kwargs):
        for nm in names:
            fn = getattr(obj, nm, None)
            if callable(fn):
                try:
                    sig = inspect.signature(fn)
                    fkwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
                    return fn(*args, **fkwargs)
                except Exception:
                    continue
        return None

    # ---------------- util: refresco/caché ----------------
    def _invalidate_caches(self):
        for obj in (self.repo, self.payment_model, self.assistance_model):
            for name in ("invalidate_cache", "clear_cache", "reset_cache", "refresh_cache"):
                fn = getattr(obj, name, None)
                if callable(fn):
                    try:
                        fn()
                    except Exception:
                        pass

    # ------------------------------------------------------------
    # Header / Filtros / Acciones
    # ------------------------------------------------------------
    def _build_header(self):
        BtnCls = getattr(ft, "FilledTonalButton", ft.ElevatedButton)

        self.input_id = ft.TextField(
            label="ID Empleado",
            width=180,
            height=36,
            dense=True,
            content_padding=ft.padding.only(left=10, right=10),
            border_color=ft.colors.OUTLINE,
            on_change=self._on_id_empleado_change,
        )
        self.input_id_pago_pend = ft.TextField(
            label="ID Pago (pend.)",
            width=180,
            height=36,
            dense=True,
            content_padding=ft.padding.only(left=10, right=10),
            border_color=ft.colors.OUTLINE,
            on_change=lambda e: self._on_filter_change(scope="pend", key="id_pago", value=e.control.value),
        )
        self.input_id_pago_conf = ft.TextField(
            label="ID Pago (conf.)",
            width=180,
            height=36,
            dense=True,
            content_padding=ft.padding.only(left=10, right=10),
            border_color=ft.colors.OUTLINE,
            # 🔧 ahora escribe en id_pago_conf
            on_change=lambda e: self._on_filter_change(scope="conf", key="id_pago_conf", value=e.control.value),
        )

        header_bar = ft.Row(
            controls=[
                crear_boton_importar(lambda: self._no_impl("Importar")),
                crear_boton_exportar(lambda: self._no_impl("Exportar")),
                crear_boton_agregar(self._abrir_modal_rango),
                crear_boton_agregar_fechas_pagadas(self._abrir_modal_grupo_pagado),
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
        self.header = ft.Column(
            spacing=8,
            controls=[ft.Text("ÁREA DE PAGOS", style=ft.TextThemeStyle.TITLE_MEDIUM), header_bar],
        )

    def _no_impl(self, what: str):
        ModalAlert.mostrar_info("Próximamente", f"La acción '{what}' se implementará más adelante.")

    # ---------------- Filtros ----------------
    def _on_id_empleado_change(self, _):
        texto = (self.input_id.value or "").strip()
        self.input_id.border_color = ft.colors.OUTLINE if not texto or texto.isdigit() else ft.colors.RED_400
        self.filters_pend["id_empleado"] = texto if texto.isdigit() else ""
        self.filters_conf["id_empleado"] = texto if texto.isdigit() else ""
        if self.page:
            self.page.update()
        self._aplicar_filtros()

    def _on_filter_change(self, *, scope: str, key: str, value: str):
        value = (value or "").strip()
        if scope == "pend":
            self.filters_pend[key] = value
        else:
            self.filters_conf[key] = value
        self._aplicar_filtros()

    def _aplicar_filtros(self):
        # Pendientes
        self._call(
            self.pendientes_ui,
            ["set_filters", "apply_filters", "filtrar"],
            id_empleado=self.filters_pend.get("id_empleado", ""),
            id_pago=self.filters_pend.get("id_pago", ""),
        )
        # Confirmados (sin perder expansión)
        self._call(
            self.confirmados_ui,
            ["set_filters", "apply_filters", "filtrar"],
            id_empleado=self.filters_conf.get("id_empleado", ""),
            # 🔧 clave correcta para confirmados:
            id_pago_conf=self.filters_conf.get("id_pago_conf", ""),
            # compat: algunos módulos aceptan id_pago como alias
            id_pago=self.filters_conf.get("id_pago_conf", ""),
            preserve_expansion=True,
        )
        self._actualizar_resumen()
        if self.page:
            self.page.update()

    # ---------------- Carga/recarga y resumen ----------------
    def _recargar_todo(self, *, preserve_expansion: bool = True):
        self._call(
            self.pendientes_ui,
            ["reload", "refresh", "load", "render"],
            id_empleado=self.filters_pend.get("id_empleado", ""),
            id_pago=self.filters_pend.get("id_pago", ""),
        )
        self._call(
            self.confirmados_ui,
            ["reload", "refresh", "load", "render"],
            id_empleado=self.filters_conf.get("id_empleado", ""),
            id_pago_conf=self.filters_conf.get("id_pago_conf", ""),
            id_pago=self.filters_conf.get("id_pago_conf", ""),
            preserve_expansion=preserve_expansion,
        )
        self._actualizar_resumen()
        if self.page:
            self.page.update()

    def _on_data_changed(self):
        """
        Cambios globales (generación por rango, creación/eliminación de grupos, etc.).
        Aquí sí recargamos ambas tablas, preservando expansiones.
        """
        self._recargar_todo(preserve_expansion=True)

    def _actualizar_resumen(self):
        try:
            total_pagado = self.repo.total_pagado_confirmado()
            self.resumen_pagos.value = f"Total pagado (confirmado): ${float(total_pagado):.2f}"
        except Exception:
            pass

    # ---------------- Helpers fechas pagadas ----------------
    def _parse_fechas(self, items):
        out = []
        for f in (items or []):
            if isinstance(f, date):
                out.append(f)
            elif isinstance(f, str):
                try:
                    out.append(datetime.strptime(f, "%Y-%m-%d").date())
                except Exception:
                    pass
        return out

    def _fechas_grupos_pagados(self) -> list[date]:
        candidatos = [
            ("get_fechas_utilizadas_pagadas", self.payment_model, ()),
            ("get_fechas_grupos_pagados", self.payment_model, ()),
            ("get_fechas_grupos_pagados", self.repo, ()),
            ("get_fechas_pagadas", self.payment_model, ()),
        ]
        for nombre, obj, args in candidatos:
            fn = getattr(obj, nombre, None)
            if callable(fn):
                try:
                    return self._parse_fechas(fn(*args))
                except Exception:
                    pass

        candidatos_grupos = [
            ("get_grupos_por_estado", self.payment_model, ("pagado",)),
            ("listar_grupos", self.payment_model, ()),
            ("get_grupos", self.payment_model, ()),
        ]
        for nombre, obj, args in candidatos_grupos:
            fn = getattr(obj, nombre, None)
            if callable(fn):
                try:
                    grupos = fn(*args) or []
                    fechas = []
                    for g in grupos:
                        estado = (g.get("estado") or g.get("status") or "").lower()
                        if estado == "pagado":
                            f = g.get("fecha") or g.get("fecha_pago") or g.get("date")
                            if f:
                                fechas.append(f)
                    if fechas:
                        return self._parse_fechas(fechas)
                except Exception:
                    pass
        return []

    # ---------------- Generación por rango ----------------
    def _abrir_modal_rango(self):
        try:
            bloqueadas = self._fechas_grupos_pagados()
            self.selector_rango.set_fechas_bloqueadas(bloqueadas)

            fi = self.assistance_model.get_fecha_minima_asistencia()
            ff = self.assistance_model.get_fecha_maxima_asistencia()
            if not fi or not ff:
                ModalAlert.mostrar_info("Sin asistencias", "No hay registros de asistencias disponibles.")
                return

            if hasattr(self.assistance_model, "get_fechas_estado_completo_y_incompleto"):
                fechas_estado = self.assistance_model.get_fechas_estado_completo_y_incompleto(fi, ff)
            else:
                fechas_estado = self.assistance_model.get_fechas_estado(fi, ff)
            self.selector_rango.set_asistencias(fechas_estado)

            disponibles = self.assistance_model.get_fechas_disponibles_para_pago() or []
            disponibles = [d for d in disponibles if d not in set(bloqueadas)]

            if hasattr(self.assistance_model, "get_fechas_vacias"):
                disponibles.extend(self.assistance_model.get_fechas_vacias(fi, ff))

            self.selector_rango.set_fechas_disponibles(sorted(set(disponibles)))

            self.selector_rango.abrir_dialogo(reset_selection=True)

        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo abrir el calendario: {str(ex)}")

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
        except Exception:
            return []

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
                estados = self.assistance_model.get_fechas_estado(fi, ff)  # type: ignore[arg-type]
                incompletas = [f for f, st in estados.items() if (st or "").lower() == "incompleto"]
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
                if hasattr(self.assistance_model, "marcar_asistencias_como_generadas"):
                    self.assistance_model.marcar_asistencias_como_generadas(fecha_inicio=fi_s, fecha_fin=ff_s)
            except Exception:
                pass

            if res.get("status") == "success":
                ModalAlert.mostrar_info("Nómina por rango", res.get("message", "Pagos generados."))
            else:
                ModalAlert.mostrar_info("Nómina por rango", res.get("message", "Ocurrió un problema."))
        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo generar la nómina: {str(ex)}")

        self._invalidate_caches()
        self._recargar_todo(preserve_expansion=True)

    # ---------------- Grupos 'pagados' ----------------
    def _abrir_modal_grupo_pagado(self):
        if not self.modal_fecha_grupo:
            ModalAlert.mostrar_info("No disponible", "No está cargado ModalFechaGrupoPagado.")
            return
        try:
            if hasattr(self.modal_fecha_grupo, "cargar_desde_payment_model"):
                self.modal_fecha_grupo.cargar_desde_payment_model(self.payment_model)
        except Exception:
            pass
        self.modal_fecha_grupo.abrir_dialogo(reset_selection=True)

    def _crear_grupo_pagado(self, f: date):
        fecha = f.strftime("%Y-%m-%d")
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

            self._invalidate_caches()
            self._recargar_todo(preserve_expansion=True)
            self._call(self.confirmados_ui, ["open_group", "expand_group"], fecha)
        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo crear el grupo: {str(ex)}")

    # ---------------- Eventos desde PagosPendientesEditables ----------------
    def _on_pago_confirmado_desde_pendientes(self, pago_ok: Dict[str, Any] | None = None):
        try:
            # 0) invalidación SIEMPRE
            self._invalidate_caches()

            # 1) si vino vacío o sin estado, reconsulta
            p = dict(pago_ok or {})
            if not p or str(p.get("estado", "")).lower() != "pagado":
                pid = int(p.get("id_pago_nomina") or p.get("id_pago") or 0)
                if pid > 0 and hasattr(self.repo, "obtener_pago"):
                    p = self.repo.obtener_pago(pid) or p

            if p:
                # preferido: push incremental (pago_row=...)
                self._call(self.confirmados_ui, ["push_pago_pagado"], pago_row=p, keep_expanded=True)

                # fallback: add_or_update_pagado espera 'pago', no 'pago_row'
                self._call(self.confirmados_ui, ["add_or_update_pagado"], pago=p, keep_expanded=True)

                # último recurso: recarga con expansión
                self._call(self.confirmados_ui, ["reload"], preserve_expansion=True)

                fecha = str(p.get("fecha_pago") or "")
                if fecha:
                    self._call(self.confirmados_ui, ["open_group", "expand_group"], fecha)

            self._actualizar_resumen()
            if self.page:
                self.page.update()
        except Exception as ex:
            ModalAlert.mostrar_info("Actualización", f"No se pudo reflejar el pago confirmado en la vista: {ex}")
