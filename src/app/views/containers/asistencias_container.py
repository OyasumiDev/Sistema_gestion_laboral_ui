import flet as ft
from datetime import datetime, timedelta, date
from decimal import Decimal
import pandas as pd
from typing import Optional, Callable, Any

from app.models.assistance_model import AssistanceModel
from app.controllers.asistencias_import_controller import AsistenciasImportController
from app.core.app_state import AppState
from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.views.containers.window_snackbar import WindowSnackbar
from app.views.containers.modal_alert import ModalAlert

# ⬇️ Column builder / row helper
from app.helpers.asistencias_column_builder import AsistenciasColumnBuilder
from app.helpers.asistencias_row_helper import AsistenciasRowHelper
from app.helpers.calculo_horas_helper import CalculoHorasHelper
from app.helpers.boton_factory import (
    crear_boton_importar,
    crear_boton_exportar,
    crear_boton_agregar_asistencias,
)

from app.models.employes_model import EmployesModel
from app.helpers.sworting_helper import Sworting


class AsistenciasContainer(ft.Container):
    """
    - DESCANSO default = MD (1) SIEMPRE.
    - El cálculo real de horas/estado lo hace MySQL vía triggers.
    - El container usa CalculoHorasHelper SOLO para validación visual/guardado.
    - En modo vista, el descanso se puede cambiar sin entrar a edición (autosave):
        * Dropdown SN/MD/CMP
        * al cambiar, se guarda automáticamente en DB
        * ✅ re-lee el registro desde DB (ya recalculado por triggers)
        * ✅ refresca UI
    """

    # ---- Config UI / rendimiento ----
    _BASE_MIN_WIDTH = 1200
    _PAGE_MARGIN_W = 80
    _HEADER_ESTIMATE = 180
    _PANEL_MIN_H = 400
    _PANEL_MAX_H = 550
    _TABLE_COL_SPACING = 8

    # Anchos por columna
    _COL_WIDTHS = {
        "numero_nomina": 80,
        "nombre_completo": 205,
        "fecha": 100,
        "hora_entrada": 100,
        "hora_salida": 100,
        "descanso": 108,
        "tiempo_trabajo": 122,
        "estado": 122,
    }

    def __init__(self):
        super().__init__(expand=True, padding=16, alignment=ft.alignment.top_left)

        # Core
        self.page = AppState().page
        self.asistencia_model = AssistanceModel()
        self.calculo_helper = CalculoHorasHelper()
        self.window_snackbar = WindowSnackbar(self.page)
        self.employees_model = EmployesModel()

        # ✅ Para shell persistente: NO pisar on_resize sin encadenar
        self._prev_on_resize = None

        # Estado
        # ✅ editando usa llave estable: (numero_nomina, fecha_iso)
        self.editando: dict[Any, Any] = {}
        self.datos_por_grupo: dict[str, list[dict]] = {}
        self.grupos_expandido: dict[str, bool] = {}

        # Scroll per group
        self._scroll_state: dict[str, dict[str, float]] = {}
        self._vcols_by_group: dict[str, ft.Column] = {}

        # Ordenamiento y filtros
        self._group_sort: dict[str, dict] = {}
        self.sort_id_filter: str | None = None
        self.sort_name_filter: str | None = None

        # alias
        self.activar_edicion = self._activar_edicion

        # tablas por grupo
        self._tablas_por_grupo: dict[str, ft.DataTable] = {}
        # grupos manuales (para permitir agregar cuando no hay importados)
        self._manual_groups: set[str] = set()

        # Helpers
        # ✅ callbacks "a prueba de balas": aceptan distintas firmas desde el RowHelper
        self.row_helper = AsistenciasRowHelper(
            recalcular_callback=self._recalcular_horas_fila_proxy,
            actualizar_callback=self._actualizar_valor_fila_proxy,
            commit_descanso_callback=self._commit_descanso_from_rowhelper,
        )
        # ✅ FIX CRÍTICO: asegurar page REAL en el helper
        self._sync_row_helper_page()

        self.columnas_definidas = [
            ("Nómina", "numero_nomina"),
            ("Nombre", "nombre_completo"),
            ("Fecha", "fecha"),
            ("Hora Entrada", "hora_entrada"),
            ("Hora Salida", "hora_salida"),
            ("Descanso", "descanso"),
            ("Horas Trabajadas", "tiempo_trabajo"),
            ("Estado", "estado"),
        ]
        self._col_index = {f: i for i, (_t, f) in enumerate(self.columnas_definidas)}

        self.column_builder = AsistenciasColumnBuilder(
            on_edit=self.activar_edicion,
            on_delete=lambda reg: self._confirmar_eliminacion(
                reg["numero_nomina"], reg.get("__fecha_iso") or reg["fecha"]
            ),
        )

        # Import / Export
        self.import_controller = AsistenciasImportController(page=self.page, on_success=self._actualizar_tabla)
        self.save_invoker = FileSaveInvoker(
            page=self.page,
            on_save=self._exportar_asistencias,
            save_dialog_title="Exportar asistencias como Excel",
            file_name="asistencias_exportadas.xlsx",
            allowed_extensions=["xlsx"],
        )
        self.import_button = crear_boton_importar(on_click=lambda: self.import_controller.file_invoker.open())
        self.export_button = crear_boton_exportar(on_click=lambda: self.save_invoker.open_save())
        self.add_button = crear_boton_agregar_asistencias(on_click=lambda: self._on_click_agregar_asistencia())

        # Toolbar
        self.sort_id_input = ft.TextField(
            label="Ordenar por ID nómina",
            hint_text="Escribe un ID y presiona Enter",
            width=220,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_submit=self._aplicar_sort_id,
            on_change=self._id_on_change_auto_reset,
        )
        self.sort_id_clear_btn = ft.IconButton(
            icon=ft.icons.CLEAR, tooltip="Limpiar ID", on_click=lambda e: self._limpiar_sort_id()
        )

        self.sort_name_input = ft.TextField(
            label="Buscar por Nombre",
            hint_text="Escribe nombre y presiona Enter",
            width=320,
            on_submit=self._aplicar_sort_nombre,
            on_change=self._nombre_on_change_auto_reset,
        )
        self.sort_name_clear_btn = ft.IconButton(
            icon=ft.icons.CLEAR, tooltip="Limpiar nombre", on_click=lambda e: self._limpiar_sort_nombre()
        )

        self._title_label = None
        # Toolbar Ãºnica: botones + filtros en una sola lÃ­nea
        self._top_row = ft.Row(
            controls=[
                self.add_button,
                self.import_button,
                self.export_button,
                ft.Container(width=12),
                self.sort_id_input,
                self.sort_id_clear_btn,
                self.sort_name_input,
                self.sort_name_clear_btn,
            ],
            spacing=10,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=False,
            scroll=ft.ScrollMode.AUTO,
        )

        # Contenedor principal
        self._root_column = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            spacing=10,
            controls=[self._top_row],
        )
        self.content = ft.Container(expand=True, content=self._root_column)

        # caches
        self._page_w = 0
        self._page_h = 0
        self._panel_scroll_w = self._BASE_MIN_WIDTH
        self._panel_viewport_h = 360

        # Primera carga
        self._recompute_layout_sizes()
        self._construir_paneles_iniciales()
        self._actualizar_tabla()
        self._update_panels_viewport_sizes()
        self._safe_update()

    # --------------------- Ciclo de vida (shell persistente) ---------------------
    def did_mount(self):
        # refresca page real al montar
        self.page = AppState().page or self.page
        self.window_snackbar = WindowSnackbar(self.page)
        self._sync_row_helper_page()

        # encadenar resize sin romper el handler previo
        if self.page:
            self._prev_on_resize = getattr(self.page, "on_resize", None)
            self.page.on_resize = self._on_page_resize_chained

        self._recompute_layout_sizes()
        self._update_panels_viewport_sizes()
        self._safe_update()

    def will_unmount(self):
        # restaurar on_resize previo
        try:
            if self.page and self._prev_on_resize is not None:
                self.page.on_resize = self._prev_on_resize
        except Exception:
            pass

    def _on_page_resize_chained(self, e: ft.ControlEvent | None):
        try:
            if callable(self._prev_on_resize):
                self._prev_on_resize(e)
        except Exception:
            pass
        self._on_page_resize(e)

    # --------------------- Update seguro ---------------------
    def _safe_update(self, control: ft.Control | None = None):
        try:
            if control is not None:
                control.update()
                return
        except Exception:
            pass
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

    def _sync_row_helper_page(self):
        """✅ Mantiene el RowHelper apuntando a la page real."""
        try:
            if getattr(self, "row_helper", None) is None:
                return
            if self.page:
                setattr(self.row_helper, "page", self.page)
        except Exception:
            pass

    # --------------------- Helpers: Fecha / Hora / Decimal ---------------------
    def _parse_fecha_any(self, v) -> date | None:
        """Acepta date/datetime/'DD/MM/YYYY'/'YYYY-MM-DD' y devuelve date."""
        try:
            if v is None:
                return None
            if isinstance(v, datetime):
                return v.date()
            if isinstance(v, date):
                return v
            s = str(v).strip()
            if not s:
                return None
            if "/" in s:
                return datetime.strptime(s, "%d/%m/%Y").date()
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    def _fecha_to_display(self, v) -> str:
        d = self._parse_fecha_any(v)
        return d.strftime("%d/%m/%Y") if d else (str(v) if v is not None else "")

    def _fecha_to_iso(self, v) -> str:
        d = self._parse_fecha_any(v)
        return d.strftime("%Y-%m-%d") if d else (str(v) if v is not None else "")

    def _decimal_horas_a_hhmm(self, v) -> str:
        """
        Convierte 7.5 -> '07:30'
        Si viene 'HH:MM'/'HH:MM:SS' lo regresa normalizado a HH:MM.
        """
        if v is None:
            return ""
        try:
            if isinstance(v, (int, float, Decimal)):
                total_min = int(round(float(v) * 60))
                hh = total_min // 60
                mm = total_min % 60
                return f"{hh:02}:{mm:02}"
            s = str(v).strip()
            if not s:
                return ""
            if ":" in s:
                parts = s.split(":")
                if len(parts) >= 2:
                    return f"{int(parts[0]):02}:{int(parts[1]):02}"
                return s
            f = float(s)
            total_min = int(round(f * 60))
            hh = total_min // 60
            mm = total_min % 60
            return f"{hh:02}:{mm:02}"
        except Exception:
            return str(v)

    def _normalizar_hora_display(self, v) -> str:
        """TIME puede venir como timedelta/time/str. Regresa 'HH:MM' para UI."""
        try:
            if v is None:
                return ""
            if isinstance(v, timedelta):
                t = (datetime.min + v).time()
                return t.strftime("%H:%M")
            if hasattr(v, "strftime"):
                return v.strftime("%H:%M")
            s = str(v).strip()
            if not s:
                return ""
            if s.count(":") >= 1:
                parts = s.split(":")
                return f"{int(parts[0]):02}:{int(parts[1]):02}"
            return s
        except Exception:
            return str(v) if v is not None else ""

    # --------------------- DESCANSO: normalizar / mapear ---------------------
    def _normalizar_descanso(self, v) -> str:
        """
        Acepta:
        - None, "", "NULL" -> MD
        - 0/SN -> SN
        - 1/MD -> MD
        - 2/CMP -> CMP
        """
        if v is None:
            return "MD"
        s = str(v).strip().upper()
        if s in ("", "NONE", "NULL"):
            return "MD"
        if s in ("0", "SN", "SIN"):
            return "SN"
        if s in ("1", "MD", "MEDIO"):
            return "MD"
        if s in ("2", "CMP", "COMIDA", "COMPLETO"):
            return "CMP"
        if s not in ("SN", "MD", "CMP"):
            return "MD"
        return s

    def _descanso_to_int(self, descanso: str) -> int:
        s = self._normalizar_descanso(descanso)
        return {"SN": 0, "MD": 1, "CMP": 2}.get(s, 1)

    def _wrap_descanso_cell_with_label(self, cell_content: ft.Control, descanso: str) -> ft.Control:
        tag = ft.Container(
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=8,
            bgcolor=ft.colors.with_opacity(0.18, ft.colors.WHITE),
            border=ft.border.all(1, ft.colors.with_opacity(0.35, ft.colors.WHITE)),
            content=ft.Text(descanso, size=11, weight="bold"),
        )
        if isinstance(cell_content, ft.Text):
            if str(cell_content.value).strip().upper() in ("SN", "MD", "CMP"):
                return cell_content

        return ft.Row(
            controls=[cell_content, ft.Container(width=8), tag],
            spacing=0,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _estado_color(self, estado: str) -> str:
        e = (estado or "").strip().upper()
        if e == "INCOMPLETO" or e.startswith("HORAS"):
            return ft.colors.RED
        if e == "COMPLETO":
            return ft.colors.GREEN
        if e == "DUPLICADO":
            return ft.colors.RED_600
        if e == "PENDIENTE":
            return ft.colors.GREY
        return ft.colors.GREY

    def _update_view_controls_from_reg(self, reg: dict) -> bool:
        updated = False
        try:
            tiempo_ctrl = reg.get("__tiempo_text")
            if isinstance(tiempo_ctrl, ft.Text):
                raw = reg.get("tiempo_trabajo") or reg.get("tiempo_trabajo_con_descanso") or "00:00:00"
                s = str(raw or "").strip()
                parts = s.split()
                if len(parts) >= 2 and parts[0].upper() in ("SN", "MD", "CMP"):
                    s = parts[1].strip()
                tiempo_ctrl.value = s
                updated = True

            estado_ctrl = reg.get("__estado_text")
            if isinstance(estado_ctrl, ft.Text):
                est = (reg.get("estado") or "PENDIENTE").strip().upper()
                if estado_ctrl.value != "DUPLICADO":
                    estado_ctrl.value = est
                    estado_ctrl.color = self._estado_color(est)
                    updated = True

            self._safe_update()
            return updated
        except Exception:
            return updated

    # --------------------- LLAVE ESTABLE / búsqueda ---------------------
    def _ensure_keys(self, r: dict) -> None:
        """Garantiza llaves internas estables para edición/DB."""
        try:
            if "__fecha_iso" not in r or not str(r.get("__fecha_iso") or "").strip():
                r["__fecha_iso"] = self._fecha_to_iso(r.get("fecha"))
        except Exception:
            r["__fecha_iso"] = self._fecha_to_iso(r.get("fecha"))

    def _find_reg(self, numero: int, fecha_iso: str) -> tuple[str | None, dict | None]:
        """Busca el registro por llave estable (numero, fecha_iso) en todos los grupos."""
        for g, regs in self.datos_por_grupo.items():
            for r in regs:
                self._ensure_keys(r)
                if int(r.get("numero_nomina") or 0) == int(numero) and str(r.get("__fecha_iso")) == str(fecha_iso):
                    return g, r
        return None, None

    def _get_current_edit_key(self) -> tuple[int, str] | None:
        """Devuelve (numero, fecha_iso) que esté en edición (True)."""
        for k, v in self.editando.items():
            if v is True and isinstance(k, tuple) and len(k) == 2:
                try:
                    return int(k[0]), str(k[1])
                except Exception:
                    return None
        return None

    # --------------------- NUEVO: Descanso editable en modo vista (autosave) ---------------------
    def _make_descanso_dropdown(self, grupo: str, reg: dict) -> ft.Dropdown:
        self._ensure_keys(reg)
        actual = self._normalizar_descanso(reg.get("descanso"))
        dd = ft.Dropdown(
            value=actual,
            width=90,
            content_padding=ft.padding.symmetric(horizontal=6, vertical=2),
            text_size=12,
            dense=True,
            options=[ft.dropdown.Option("SN"), ft.dropdown.Option("MD"), ft.dropdown.Option("CMP")],
        )

        def _on_change(e: ft.ControlEvent):
            nuevo = self._normalizar_descanso(e.control.value)
            anterior = self._normalizar_descanso(reg.get("descanso"))
            if nuevo == anterior:
                return
            self._autosave_descanso(grupo=grupo, reg=reg, nuevo_descanso=nuevo)

        dd.on_change = _on_change
        return dd

    def _autosave_descanso(self, grupo: str, reg: dict, nuevo_descanso: str) -> None:
        """
        Guarda descanso sin entrar a modo edición (autosave).
        ✅ Guarda en DB
        ✅ Re-lee el registro (ya recalculado por triggers)
        ✅ Refresca UI
        """
        updated = False
        try:
            self._sync_row_helper_page()
            self._ensure_keys(reg)

            numero = int(reg.get("numero_nomina") or 0)
            if numero <= 0:
                self.window_snackbar.show_error("❌ Nómina inválida. No se pudo guardar el descanso.")
                return

            fecha_iso = str(reg.get("__fecha_iso") or "").strip()
            if not fecha_iso:
                fecha_iso = self._fecha_to_iso(reg.get("fecha"))
            if not fecha_iso:
                self.window_snackbar.show_error("❌ Fecha inválida. No se pudo guardar el descanso.")
                return

            descanso_label = self._normalizar_descanso(nuevo_descanso)
            descanso_int = self._descanso_to_int(descanso_label)

            # -------------------- Recalculo UI inmediato --------------------
            try:
                entrada_local = self.calculo_helper.sanitizar_hora(reg.get("hora_entrada", ""))
                salida_local = self.calculo_helper.sanitizar_hora(reg.get("hora_salida", ""))
                res_local = self.calculo_helper.recalcular_con_estado(entrada_local, salida_local, descanso_label)
                reg["tiempo_trabajo"] = res_local.get("tiempo_trabajo")
                reg["tiempo_trabajo_con_descanso"] = res_local.get("tiempo_trabajo_con_descanso")
                estado_actual = str(reg.get("estado") or "").strip().upper()
                if estado_actual != "DUPLICADO":
                    reg["estado"] = "COMPLETO" if res_local.get("estado") == "ok" else "INCOMPLETO"
                updated = self._update_view_controls_from_reg(reg)
            except Exception:
                pass

            # -------------------- Guardar en DB --------------------
            resultado_db = None
            if hasattr(self.asistencia_model, "update_descanso"):
                resultado_db = self.asistencia_model.update_descanso(
                    numero_nomina=numero,
                    fecha=fecha_iso,
                    descanso=descanso_int,
                )
            elif hasattr(self.asistencia_model, "update_asistencia"):
                resultado_db = self.asistencia_model.update_asistencia(
                    {"numero_nomina": numero, "fecha": fecha_iso, "descanso": descanso_int}
                )
            else:
                self.window_snackbar.show_error("❌ El modelo no expone un método para guardar descanso.")
                return

            if not resultado_db or resultado_db.get("status") != "success":
                msg = (resultado_db or {}).get("message", "Error al guardar descanso.")
                self.window_snackbar.show_error(f"❌ {msg}")
                return

            # -------------------- Releer registro recalculado --------------------
            row_db = None
            try:
                row_db = self.asistencia_model.get_by_empleado_fecha(numero, fecha_iso)
            except Exception:
                row_db = None

            if isinstance(row_db, dict) and row_db:
                reg["__fecha_iso"] = self._fecha_to_iso(row_db.get("fecha")) or fecha_iso
                reg["fecha"] = self._fecha_to_display(row_db.get("fecha"))
                reg["descanso"] = self._normalizar_descanso(row_db.get("descanso"))
                reg["hora_entrada"] = self._normalizar_hora_display(row_db.get("hora_entrada"))
                reg["hora_salida"] = self._normalizar_hora_display(row_db.get("hora_salida"))
                if "tiempo_trabajo" in row_db:
                    reg["tiempo_trabajo"] = self._decimal_horas_a_hhmm(row_db.get("tiempo_trabajo"))
                if "tiempo_trabajo_con_descanso" in row_db:
                    reg["tiempo_trabajo_con_descanso"] = self._decimal_horas_a_hhmm(
                        row_db.get("tiempo_trabajo_con_descanso")
                    )
                estado_db = str(row_db.get("estado") or "").strip().upper()
                reg["estado"] = estado_db if estado_db else "INCOMPLETO"
                updated = self._update_view_controls_from_reg(reg)
            else:
                reg["descanso"] = descanso_label
                updated = self._update_view_controls_from_reg(reg)

            extra_sync = self._formatear_resumen_sync((resultado_db or {}).get("sync"))
            self.window_snackbar.show_success(f"✅ Descanso actualizado a {descanso_label}.{extra_sync}")

            self._emit_pagamentos_delta(
                {"id_empleado": numero, "periodo_ini": fecha_iso, "periodo_fin": fecha_iso},
                message=f"Pagos: descanso actualizado ({descanso_label}) para ID {numero}",
            )

            # refresca sólo el grupo para asegurar UI sincronizada
            self._refrescar_filas_grupo(grupo)
            self._safe_update()

        except Exception as e:
            self.window_snackbar.show_error(f"⚠️ No se pudo guardar descanso: {e}")

    def _commit_descanso_from_rowhelper(self, registro: dict | None = None, payload: dict | None = None, **kwargs):
        """
        Persiste descanso desde fila en edición sin forzar refresh de snapshot DB.
        Evita pisar horas editadas aún no guardadas.
        """
        try:
            reg = registro or payload or {}
            numero = int(reg.get("numero_nomina") or 0)
            if numero <= 0:
                return {"status": "error", "message": "numero_nomina inválido"}

            fecha_iso = str(reg.get("__fecha_iso") or "").strip()
            if not fecha_iso:
                fecha_iso = self._fecha_to_iso(reg.get("fecha"))
            if not fecha_iso:
                return {"status": "error", "message": "fecha inválida"}

            descanso_label = self._normalizar_descanso(reg.get("descanso", "MD"))
            descanso_int = self._descanso_to_int(descanso_label)

            if hasattr(self.asistencia_model, "update_descanso"):
                return self.asistencia_model.update_descanso(
                    numero_nomina=numero,
                    fecha=fecha_iso,
                    descanso=descanso_int,
                    return_row=False,
                )
            if hasattr(self.asistencia_model, "update_asistencia"):
                return self.asistencia_model.update_asistencia(
                    {"numero_nomina": numero, "fecha": fecha_iso, "descanso": descanso_int}
                )
            return {"status": "error", "message": "No hay método para guardar descanso"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # --------------------- PubSub Pagos (UI) ---------------------
    def _emit_pagamentos_delta(self, payload: dict, message: str | None = None) -> None:
        if not payload:
            return
        texto = message or f"Pagos: cambios detectados para ID {payload.get('id_empleado')}"
        try:
            self.window_snackbar.show_success(texto)
        except Exception:
            pass
        pubsub = getattr(self.page, "pubsub", None) if self.page else None
        if not pubsub:
            return
        try:
            if hasattr(pubsub, "publish"):
                pubsub.publish("asistencias:changed", payload)
            elif hasattr(pubsub, "send_all"):
                pubsub.send_all("asistencias:changed", payload)
        except Exception:
            pass

    # --------------------- Interacción de ordenamiento (GLOBAL: filtros) ---------------------
    def _aplicar_sort_id(self, e=None):
        v = (self.sort_id_input.value or "").strip()
        if v and not v.isdigit():
            self.window_snackbar.show_error("❌ ID inválido. Usa solo números.")
            return
        self.sort_id_filter = v if v else None
        self._actualizar_tabla()
        self._safe_update()

    def _limpiar_sort_id(self):
        self.sort_id_input.value = ""
        self.sort_id_filter = None
        self._actualizar_tabla()
        self._safe_update()

    def _id_on_change_auto_reset(self, e: ft.ControlEvent):
        v = (e.control.value or "").strip()
        if v == "" and self.sort_id_filter is not None:
            self.sort_id_filter = None
            self._actualizar_tabla()
            self._safe_update()

    def _aplicar_sort_nombre(self, e=None):
        texto = (self.sort_name_input.value or "").strip()
        if not texto:
            self.sort_name_filter = None
            self._actualizar_tabla()
            self._safe_update()
            return

        res = self.asistencia_model.get_all()
        if res.get("status") == "success":
            data = res.get("data", [])
            needle = Sworting.normalize_text(texto)
            hay = any(needle in Sworting.normalize_text(r.get("nombre_completo", "")) for r in data)
            if not hay:
                self.window_snackbar.show_error("esta busqueda no esta disponible")
                return

        self.sort_name_filter = texto
        self._actualizar_tabla()
        self._safe_update()

    def _limpiar_sort_nombre(self):
        self.sort_name_input.value = ""
        self.sort_name_filter = None
        self._actualizar_tabla()
        self._safe_update()

    def _nombre_on_change_auto_reset(self, e: ft.ControlEvent):
        v = (e.control.value or "").strip()
        if v == "" and self.sort_name_filter is not None:
            self.sort_name_filter = None
            self._actualizar_tabla()
            self._safe_update()

    # --------------------- Agregar asistencia manual ---------------------
    def _on_click_agregar_asistencia(self):
        # Siempre pedir fecha para crear/usar grupo explícito
        self._prompt_fecha_para_grupo()

    def _prompt_fecha_para_grupo(self):
        if not self.page:
            return

        fecha_input = ft.TextField(
            label="Fecha de asistencia (DD/MM/AAAA)",
            hint_text="DD/MM/AAAA",
            width=240,
            autofocus=True,
            value=date.today().strftime("%d/%m/%Y"),
        )

        def _cerrar_dialogo():
            try:
                dlg.open = False
                self._safe_update()
            except Exception:
                pass

        def _crear_grupo(_e=None):
            val = (fecha_input.value or "").strip()
            d = self._parse_fecha_any(val)
            if not d:
                self.window_snackbar.show_error("❌ Fecha inválida. Usa DD/MM/AAAA.")
                return
            if d > date.today():
                self.window_snackbar.show_error("❌ La fecha no puede ser mayor a hoy.")
                return
            grupo = f"GRUPO:{d.strftime('%d/%m/%Y')}"
            if grupo not in self.datos_por_grupo:
                self._manual_groups.add(grupo)
            _cerrar_dialogo()
            self.grupos_expandido[grupo] = True
            self._agregar_fila_en_grupo(grupo)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Nueva asistencia"),
            content=fecha_input,
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: _cerrar_dialogo()),
                ft.ElevatedButton("Crear", on_click=_crear_grupo),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dlg
        dlg.open = True
        self._safe_update()

    def _pick_default_group(self, grupos: list[str]) -> str | None:
        try:
            def _sort_key(g: str):
                registros = self.datos_por_grupo.get(g, [])
                d = self._grupo_date_for_sort(g, registros)
                return -d.toordinal()

            grupos_ordenados = sorted(grupos, key=_sort_key)
            return grupos_ordenados[0] if grupos_ordenados else None
        except Exception:
            return grupos[0] if grupos else None

    # --------------------- Interacción de ordenamiento (POR PANEL) ---------------------
    def _get_group_sort(self, grupo: str) -> dict:
        st = self._group_sort.get(grupo)
        if not st:
            st = {"key": "estado", "asc": True}
            self._group_sort[grupo] = st
        return st

    def _on_header_sort_click(self, grupo: str, field: str):
        st = self._get_group_sort(grupo)
        if st["key"] == field:
            st["asc"] = not st["asc"]
        else:
            st["key"] = field
            st["asc"] = True

        self._actualizar_tabla()
        self._safe_update()

    # --------------------- Layout helpers ---------------------
    def _on_page_resize(self, _e: ft.ControlEvent | None):
        self._recompute_layout_sizes()
        self._update_panels_viewport_sizes()

    def _recompute_layout_sizes(self):
        try:
            self._page_w = int(self.page.width or 0) if self.page else 0
            self._page_h = int(self.page.height or 0) if self.page else 0

            usable_w = max(
                self._BASE_MIN_WIDTH,
                (self._page_w - self._PAGE_MARGIN_W) if self._page_w > 0 else self._BASE_MIN_WIDTH,
            )
            self._panel_scroll_w = usable_w

            usable_h = (self._page_h - self._HEADER_ESTIMATE) if self._page_h > 0 else 480
            usable_h = max(self._PANEL_MIN_H, min(self._PANEL_MAX_H, usable_h))
            self._panel_viewport_h = usable_h
        except Exception:
            pass

    def _update_panels_viewport_sizes(self):
        for ctrl in self._root_column.controls:
            if isinstance(ctrl, ft.ExpansionPanelList):
                for p in ctrl.controls:
                    if isinstance(p, ft.ExpansionPanel) and isinstance(p.content, ft.Column):
                        if len(p.content.controls) >= 2 and isinstance(p.content.controls[1], ft.Container):
                            viewport_h_container: ft.Container = p.content.controls[1]
                            viewport_h_container.height = self._panel_viewport_h
                            if viewport_h_container.content and isinstance(viewport_h_container.content, ft.Row):
                                hrow: ft.Row = viewport_h_container.content
                                if hrow.controls and isinstance(hrow.controls[0], ft.Container):
                                    inner_w_container: ft.Container = hrow.controls[0]
                                    inner_w_container.width = self._get_table_width()
        self._safe_update()

    def _get_table_width(self) -> int:
        try:
            acciones_w = 0
            if getattr(self, "row_helper", None) is not None:
                acciones_w = int(getattr(self.row_helper, "_W", {}).get("acciones", 0) or 0)
            base = sum(int(v) for v in self._COL_WIDTHS.values()) + acciones_w
            n_cols = len(self._COL_WIDTHS) + (1 if acciones_w > 0 else 0)
            spacing = self._TABLE_COL_SPACING * max(0, n_cols - 1)
            return max(300, int(base + spacing + 40))
        except Exception:
            return max(300, int(self._panel_scroll_w))

    # --------------------- Tabla y paneles ---------------------
    def _make_sortable_header(self, titulo: str, campo: str, width: int | None, grupo: str):
        st = self._get_group_sort(grupo)
        arrow = ""
        if st["key"] == campo:
            arrow = " ▲" if st["asc"] else " ▼"
        label = ft.GestureDetector(
            on_tap=lambda e, f=campo, g=grupo: self._on_header_sort_click(g, f),
            mouse_cursor=ft.MouseCursor.CLICK,
            content=ft.Row(
                [ft.Text(f"{titulo}{arrow}", size=11, weight="bold")],
                alignment=ft.MainAxisAlignment.START,
                spacing=4,
            ),
        )
        return ft.Container(label, width=width) if width else label

    def crear_columnas(self, grupo: str):
        cols = self.column_builder.build_columns(self.columnas_definidas)
        campos_sortables = {"numero_nomina", "nombre_completo", "fecha", "hora_entrada", "hora_salida", "estado"}

        for i, c in enumerate(cols):
            if i >= len(self.columnas_definidas):
                continue

            titulo, campo = self.columnas_definidas[i]
            width = self._COL_WIDTHS.get(campo, None)

            if campo in campos_sortables:
                c.label = self._make_sortable_header(titulo, campo, width, grupo)
            else:
                c.label = (
                    ft.Container(ft.Text(titulo, size=11, weight="bold"), width=width)
                    if width
                    else ft.Text(titulo, size=11, weight="bold")
                )

        return cols

    def _to_minutes(self, t) -> int:
        try:
            s = (str(t) or "").strip()
            if not s:
                return 10**9
            fmt = "%H:%M:%S" if s.count(":") == 2 else "%H:%M"
            dt = datetime.strptime(s, fmt)
            return dt.hour * 60 + dt.minute
        except Exception:
            return 10**9

    def _estado_rank(self, r: dict) -> int:
        estado = str(r.get("estado", "")).strip().upper()
        if r.get("__error_horas", False):
            return 0
        return 0 if estado == "INCOMPLETO" else 1

    def _ordenar_lista(self, datos: list[dict], grupo: str) -> list[dict]:
        st = self._get_group_sort(grupo)
        key, asc = st["key"], st["asc"]

        ordered = sorted(datos, key=self._estado_rank)
        ordered = sorted(ordered, key=lambda r: Sworting.to_number(r.get("numero_nomina", 0)))
        ordered = sorted(ordered, key=lambda r: Sworting.to_date(r.get("fecha")))

        if key == "numero_nomina":
            ordered = sorted(ordered, key=lambda r: Sworting.to_number(r.get("numero_nomina", 0)), reverse=not asc)
        elif key == "nombre_completo":
            ordered = sorted(
                ordered, key=lambda r: Sworting.normalize_text(r.get("nombre_completo", "")), reverse=not asc
            )
        elif key == "fecha":
            ordered = sorted(ordered, key=lambda r: Sworting.to_date(r.get("fecha")), reverse=not asc)
        elif key == "hora_entrada":
            ordered = sorted(ordered, key=lambda r: self._to_minutes(r.get("hora_entrada")), reverse=not asc)
        elif key == "hora_salida":
            ordered = sorted(ordered, key=lambda r: self._to_minutes(r.get("hora_salida")), reverse=not asc)
        elif key == "estado":
            ordered = sorted(ordered, key=self._estado_rank, reverse=not asc)

        if self.sort_name_filter:
            needle = Sworting.normalize_text(self.sort_name_filter)
            ordered = sorted(
                ordered,
                key=lambda r: 0 if needle in Sworting.normalize_text(r.get("nombre_completo", "")) else 1,
            )

        if self.sort_id_filter:
            id_str = str(self.sort_id_filter)
            ordered = sorted(ordered, key=lambda r: 0 if str(r.get("numero_nomina")) == id_str else 1)

        return ordered

    # --------------------- Normalización fuerte (UI + llaves) ---------------------
    def _normalize_row_for_ui(self, r: dict) -> None:
        """Normaliza para UI, pero conserva llave estable __fecha_iso."""
        self._ensure_keys(r)
        r["fecha"] = self._fecha_to_display(r.get("fecha"))
        r["descanso"] = self._normalizar_descanso(r.get("descanso"))
        r["hora_entrada"] = self._normalizar_hora_display(r.get("hora_entrada"))
        r["hora_salida"] = self._normalizar_hora_display(r.get("hora_salida"))
        if "tiempo_trabajo" in r:
            r["tiempo_trabajo"] = self._decimal_horas_a_hhmm(r.get("tiempo_trabajo"))
        if "tiempo_trabajo_con_descanso" in r:
            r["tiempo_trabajo_con_descanso"] = self._decimal_horas_a_hhmm(r.get("tiempo_trabajo_con_descanso"))
        if not r.get("estado"):
            r["estado"] = "INCOMPLETO" if Sworting.is_asistencia_incomplete(r) else "COMPLETO"
        else:
            r["estado"] = str(r.get("estado")).strip().upper()

    def _actualizar_tabla(self):
        # ✅ aseguramos helper con page real antes de refrescar (clave para repaint)
        self.page = AppState().page or self.page
        self.window_snackbar = WindowSnackbar(self.page)
        self._sync_row_helper_page()

        res = self.asistencia_model.get_all()
        if res.get("status") != "success":
            self.window_snackbar.show_error("❌ No se pudieron cargar asistencias.")
            return

        datos = res.get("data", [])

        for r in datos:
            self._normalize_row_for_ui(r)

        self.datos_por_grupo = self._agrupar_por_grupo_importacion(datos)
        # incluir grupos manuales (sin registros importados)
        for g in self._manual_groups:
            if g not in self.datos_por_grupo:
                self.datos_por_grupo[g] = []

        def _grupo_tiene_match(item) -> bool:
            _, registros = item
            if self.sort_id_filter:
                id_str = str(self.sort_id_filter)
                if any(str(r.get("numero_nomina")) == id_str for r in registros):
                    return True
            if self.sort_name_filter:
                needle = Sworting.normalize_text(self.sort_name_filter)
                if any(needle in Sworting.normalize_text(r.get("nombre_completo", "")) for r in registros):
                    return True
            return False

        grupos = list(self.datos_por_grupo.items())
        grupos_ordenados = sorted(
            grupos,
            key=lambda item: (
                0 if _grupo_tiene_match(item) else 1,
                -self._grupo_date_for_sort(item[0], item[1]).toordinal(),
            ),
        )

        # Snapshot de expansión
        snapshot_expandido = {}
        epl = next((c for c in self._root_column.controls if isinstance(c, ft.ExpansionPanelList)), None)
        if epl:
            for p in epl.controls:
                try:
                    key = str(p.content.controls[0].key)
                    snapshot_expandido[key] = p.expanded
                except Exception:
                    pass

        for k, v in snapshot_expandido.items():
            self.grupos_expandido[k] = v

        if not self.grupos_expandido:
            self.grupos_expandido = {g: False for g, _ in grupos_ordenados}
            for g, registros in grupos_ordenados:
                if any(Sworting.is_asistencia_incomplete(r) for r in registros):
                    self.grupos_expandido[g] = True
        else:
            for g, _ in grupos_ordenados:
                if g not in self.grupos_expandido:
                    self.grupos_expandido[g] = False

        if not epl:
            epl = ft.ExpansionPanelList(expand=True, controls=[])
            self._root_column.controls.append(epl)

        def _panel_key(p: ft.ExpansionPanel) -> str | None:
            try:
                return str(p.content.controls[0].key)
            except Exception:
                return None

        panels_by_group: dict[str, ft.ExpansionPanel] = {}
        for p in list(epl.controls):
            key = _panel_key(p)
            if key not in self.datos_por_grupo:
                epl.controls.remove(p)
                self._tablas_por_grupo.pop(key, None)
                self._vcols_by_group.pop(key, None)
                self._scroll_state.pop(key, None)
            else:
                panels_by_group[key] = p

        # Crear paneles faltantes
        for grupo, _ in grupos_ordenados:
            if grupo in panels_by_group:
                continue

            cols = self.crear_columnas(grupo)
            tabla = ft.DataTable(
                columns=cols,
                rows=[],
                column_spacing=self._TABLE_COL_SPACING,
                data_row_max_height=44,
                heading_row_height=34,
            )
            self._tablas_por_grupo[grupo] = tabla

            encabezado = ft.Row(
                [
                    ft.Text(f"🗂 {grupo}", expand=True, weight="bold"),
                    ft.IconButton(
                        icon=ft.icons.ADD,
                        tooltip="Agregar asistencia",
                        on_click=lambda e, g=grupo: self._agregar_fila_en_grupo(g),
                    ),
                    ft.IconButton(
                        icon=ft.icons.DELETE_OUTLINE,
                        tooltip="Eliminar grupo",
                        icon_color=ft.colors.RED_600,
                        on_click=lambda e, g=grupo: self._eliminar_grupo(g),
                    ),
                ],
                spacing=6,
            )

            vertical_scroll_column = ft.Column(controls=[tabla], expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
            self._vcols_by_group[grupo] = vertical_scroll_column

            inner_w_container = ft.Container(
                content=vertical_scroll_column, width=self._get_table_width(), alignment=ft.alignment.top_left
            )

            horizontal_row = ft.Row(
                controls=[inner_w_container],
                expand=True,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.START,
                scroll=ft.ScrollMode.AUTO,
            )

            viewport_container = ft.Container(height=self._panel_viewport_h, expand=False, content=horizontal_row)
            panel_content = ft.Column(controls=[ft.Container(key=grupo), viewport_container], spacing=8)

            panel = ft.ExpansionPanel(
                header=encabezado,
                content=panel_content,
                can_tap_header=True,
                expanded=self.grupos_expandido.get(grupo, False),
            )
            panel.on_expansion_changed = lambda e, g=grupo: self._toggle_expansion(g)

            epl.controls.append(panel)
            panels_by_group[grupo] = panel

        # Reordenar paneles
        epl.controls = [panels_by_group[g] for g, _ in grupos_ordenados if g in panels_by_group]

        # Refrescar filas
        for grupo, _ in grupos_ordenados:
            self._refrescar_filas_grupo(grupo)
            p = panels_by_group.get(grupo)
            if p:
                p.expanded = self.grupos_expandido.get(grupo, False)

        self._update_panels_viewport_sizes()
        self._safe_update()

    # --------------------- Estética de filas / celdas ---------------------
    def _estilizar_fila(self, grupo: str, fila: ft.DataRow, editable: bool, incompleto: bool, reg: Optional[dict] = None):
        if not getattr(fila, "cells", None):
            return

        tabla = self._tablas_por_grupo.get(grupo)
        if tabla:
            self._fix_row_cells(fila, len(tabla.columns))

        for idx, cell in enumerate(fila.cells):
            if idx >= len(self.columnas_definidas):
                continue

            _, campo = self.columnas_definidas[idx]
            width = self._COL_WIDTHS.get(campo, None)

            contenido = cell.content

            # ✅ Descanso en modo vista: Dropdown autosave
            if (not editable) and campo == "descanso" and reg is not None:
                try:
                    dd = self._make_descanso_dropdown(grupo=grupo, reg=reg)
                    cell.content = dd
                    contenido = cell.content
                except Exception:
                    pass

            # estética: en edición no se agrega tag extra (evita duplicados visuales)

            if isinstance(contenido, ft.TextField):
                contenido.expand = True
                contenido.text_size = 12
                contenido.content_padding = ft.padding.symmetric(horizontal=6, vertical=4)
                if width:
                    cell.content = ft.Container(contenido, width=width, expand=True)
            else:
                if width:
                    cell.content = ft.Container(contenido, width=width, expand=True)

        try:
            idx_estado = self._col_index.get("estado")
            if idx_estado is not None and idx_estado < len(fila.cells):
                estado_cell = fila.cells[idx_estado]
                if incompleto:
                    txt = ft.Text("INCOMPLETO", color=ft.colors.RED_600, weight="bold", size=12)
                    estado_cell.content = ft.Container(txt, width=self._COL_WIDTHS["estado"], expand=True)
        except Exception:
            pass

    def _fix_row_cells(self, fila: ft.DataRow, n_cols: int) -> None:
        try:
            if not hasattr(fila, "cells") or fila.cells is None:
                return
            cells = list(fila.cells)
            while len(cells) < n_cols:
                cells.append(ft.DataCell(ft.Text("—")))
            if len(cells) > n_cols:
                cells = cells[:n_cols]
            fila.cells = cells
        except Exception:
            pass

    # --------------------- Callbacks proxy (RowHelper) ---------------------
    def _recalcular_horas_fila_proxy(self, *args, **kwargs):
        """
        ✅ NO redibujar tabla aquí.
        Se dispara en cada on_change del RowHelper.
        """
        # si el helper pasa un control, intenta update puntual
        for a in args:
            if isinstance(a, ft.Control):
                self._safe_update(a)
                return
        self._safe_update()

    def _actualizar_valor_fila_proxy(self, *args, **kwargs):
        grupo = kwargs.get("grupo", None)
        campo = kwargs.get("campo", None)
        valor = kwargs.get("valor", None)

        if campo is None and len(args) >= 2:
            if len(args) == 2:
                campo, valor = args[0], args[1]
            elif len(args) >= 3:
                grupo, campo, valor = args[0], args[1], args[2]

        self._actualizar_valor_fila(grupo=grupo, campo=campo, valor=valor)

    # --------------------- Acciones / edición ---------------------
    def _on_click_editar(self, numero_nomina, fecha_any):
        fecha_iso = self._fecha_to_iso(fecha_any)
        self.activar_edicion(int(numero_nomina), fecha_iso)
        self._actualizar_tabla()
        self._safe_update()

    def _actualizar_valor_fila(self, grupo=None, campo=None, valor=None):
        if campo is None:
            return

        # ---- fila nueva ----
        if grupo is not None and ("nuevo", grupo) in self.editando:
            self.editando[("nuevo", grupo)][campo] = valor
            return

        # ---- inferir registro en edición actual ----
        edit_key = self._get_current_edit_key()
        if not edit_key:
            return
        numero_nomina, fecha_iso = edit_key

        # si no llegó grupo, búscalo
        if grupo is None:
            g, r = self._find_reg(numero_nomina, fecha_iso)
            if r is not None:
                r[campo] = valor
            return

        regs = self.datos_por_grupo.get(grupo, [])
        for r in regs:
            self._ensure_keys(r)
            if int(r.get("numero_nomina") or 0) == int(numero_nomina) and str(r.get("__fecha_iso")) == str(fecha_iso):
                r[campo] = valor
                return

        g, r = self._find_reg(numero_nomina, fecha_iso)
        if r is not None:
            r[campo] = valor

    def _formatear_resumen_sync(self, sync_info) -> str:
        if not isinstance(sync_info, dict):
            return ""

        status = sync_info.get("status")
        if status == "success":
            partes: list[str] = []
            pendientes = sync_info.get("pendientes_actualizados")
            pagados = sync_info.get("pagados_ajustados")
            sin_cambios = sync_info.get("sin_cambios")

            if pendientes:
                partes.append(f"pendientes actualizados: {pendientes}")
            if pagados:
                partes.append(f"pagados ajustados: {pagados}")
            if not partes and sin_cambios:
                partes.append("pagos sin cambios")

            errores = sync_info.get("errores") or []
            if errores:
                self.window_snackbar.show_error(f"Pagos: {errores[0]}")
                partes.append("ver avisos de pagos")

            return f" ({', '.join(partes)})" if partes else ""

        if status == "noop":
            return " (sin pagos asociados al cambio)"

        if status == "error":
            mensaje = sync_info.get("message", "No se pudieron sincronizar los pagos.")
            self.window_snackbar.show_error(f"Pagos: {mensaje}")
            return " (pagos no sincronizados)"

        return ""

    def _agregar_fila_en_grupo(self, grupo_importacion):
        hoy = date.today().strftime("%d/%m/%Y")
        self.editando[("nuevo", grupo_importacion)] = {
            "numero_nomina": "",
            "nombre_completo": "",
            "fecha": hoy,
            "hora_entrada": "",
            "hora_salida": "",
            "descanso": "MD",
            "__duplicado": False,
            "__horas_invalidas": True,
        }
        self.grupos_expandido[grupo_importacion] = True
        self._actualizar_tabla()
        self._safe_update()

    def _guardar_fila_nueva(self, grupo: str):
        try:
            fila = self.editando.get(("nuevo", grupo), {})

            if fila.get("__duplicado", False):
                ModalAlert(
                    title_text="No se puede guardar",
                    message="❌ Este número de nómina ya existe para la fecha indicada.",
                ).mostrar()
                return
            if fila.get("__horas_invalidas", True):
                ModalAlert(
                    title_text="No se puede guardar",
                    message="❌ Las horas son inválidas. Verifica formato y que la salida sea mayor a la entrada.",
                ).mostrar()
                return

            numero = str(fila.get("numero_nomina", "")).strip()
            if not numero.isdigit():
                self.window_snackbar.show_error("❌ Número de nómina inválido.")
                return
            numero_int = int(numero)

            fecha_str = str(fila.get("fecha", "")).strip()
            fecha_iso = self._fecha_to_iso(fecha_str)
            if not fecha_iso:
                self.window_snackbar.show_error("❌ Formato de fecha inválido. Usa DD/MM/AAAA.")
                return

            hora_entrada = self.calculo_helper.sanitizar_hora(fila.get("hora_entrada"))
            hora_salida = self.calculo_helper.sanitizar_hora(fila.get("hora_salida"))
            descanso = self._normalizar_descanso(fila.get("descanso", "MD"))

            resultado = self.calculo_helper.recalcular_con_estado(hora_entrada, hora_salida, descanso)
            if resultado.get("estado") != "ok":
                self.window_snackbar.show_error(f"❌ {resultado.get('mensaje', 'Error en tiempo trabajado.')}")
                return

            registros_del_grupo = self.datos_por_grupo.get(grupo, [])
            valido, errores = self.calculo_helper.validar_numero_fecha_en_grupo(
                registros_del_grupo, numero_int, fecha_str, registro_actual=fila
            )
            if not valido:
                ModalAlert(title_text="No se puede guardar", message="❌ " + " ".join(errores)).mostrar()
                return

            resultado_db = self.asistencia_model.add(
                numero_nomina=numero_int,
                fecha=fecha_iso,
                hora_entrada=hora_entrada,
                hora_salida=hora_salida,
                descanso=self._descanso_to_int(descanso),
                grupo_importacion=grupo,
            )
            if not resultado_db or resultado_db.get("status") != "success":
                self.window_snackbar.show_error(
                    (resultado_db or {}).get("message") or "❌ Error al guardar en la base de datos."
                )
                return

            extra_sync = self._formatear_resumen_sync((resultado_db or {}).get("sync"))
            self.window_snackbar.show_success(f"OK. Asistencia guardada correctamente.{extra_sync}")
            self._emit_pagamentos_delta({"id_empleado": numero_int, "periodo_ini": fecha_iso, "periodo_fin": fecha_iso})

            self.editando.pop(("nuevo", grupo), None)
            self._actualizar_tabla()
            self._safe_update()

        except Exception as e:
            self.window_snackbar.show_error(f"⚠️ Error inesperado al guardar: {e}")

    def _cancelar_fila_nueva(self, grupo):
        if ("nuevo", grupo) in self.editando:
            self.editando.pop(("nuevo", grupo))
            self._actualizar_tabla()
            self._safe_update()
            self.window_snackbar.show_success("ℹ️ Registro cancelado.")

    def _toggle_expansion(self, grupo: str):
        self.grupos_expandido[grupo] = not self.grupos_expandido.get(grupo, False)
        self._update_panels_viewport_sizes()
        self._safe_update()

    def _es_editando(self, registro: dict) -> bool:
        self._ensure_keys(registro)
        return self.editando.get((int(registro.get("numero_nomina") or 0), str(registro.get("__fecha_iso"))), False) is True

    def _guardar_edicion(self, numero_nomina, fecha_iso):
        numero_nomina = int(numero_nomina)
        fecha_iso = str(fecha_iso).strip()

        if not fecha_iso:
            self.window_snackbar.show_error("❌ Fecha inválida para guardar.")
            return

        grupo_encontrado, registro_actualizado = self._find_reg(numero_nomina, fecha_iso)
        if not registro_actualizado:
            self.window_snackbar.show_error("❌ No se encontró el registro a actualizar.")
            return

        def convertir_time(t):
            if isinstance(t, timedelta):
                return (datetime.min + t).time().strftime("%H:%M:%S")
            return str(t).strip() if t is not None else ""

        hora_entrada = self.calculo_helper.sanitizar_hora(convertir_time(registro_actualizado.get("hora_entrada")))
        hora_salida = self.calculo_helper.sanitizar_hora(convertir_time(registro_actualizado.get("hora_salida")))
        descanso_label = self._normalizar_descanso(registro_actualizado.get("descanso", "MD"))
        descanso_int = self._descanso_to_int(descanso_label)

        resultado = self.calculo_helper.recalcular_con_estado(hora_entrada, hora_salida, descanso_label)
        if resultado.get("estado") != "ok":
            self.window_snackbar.show_error("❌ " + (resultado.get("mensaje") or "Error al validar horas."))
            return

        tiempo_manual = str(registro_actualizado.get("tiempo_trabajo_manual") or "").strip()
        manual_override = bool(tiempo_manual)

        try:
            if not manual_override:
                if hasattr(self.asistencia_model, "update_asistencia"):
                    resultado_db = self.asistencia_model.update_asistencia(
                        {
                            "numero_nomina": int(numero_nomina),
                            "fecha": fecha_iso,
                            "hora_entrada": hora_entrada,
                            "hora_salida": hora_salida,
                            "descanso": descanso_int,
                        }
                    )
                else:
                    resultado_db = self.asistencia_model.actualizar_asistencia_completa(
                        numero_nomina=int(numero_nomina),
                        fecha=fecha_iso,
                        hora_entrada=hora_entrada,
                        hora_salida=hora_salida,
                        estado="completo",
                        descanso=descanso_int,
                        tiempo_trabajo=None,
                    )
            else:
                resultado_db = self.asistencia_model.actualizar_asistencia_completa(
                    numero_nomina=int(numero_nomina),
                    fecha=fecha_iso,
                    hora_entrada=hora_entrada,
                    hora_salida=hora_salida,
                    estado="completo",
                    descanso=descanso_int,
                    tiempo_trabajo=tiempo_manual,
                )
        except Exception as e:
            self.window_snackbar.show_error(f"❌ Error guardando en DB: {e}")
            return

        if not isinstance(resultado_db, dict) or resultado_db.get("status") != "success":
            self.window_snackbar.show_error(
                f"❌ {((resultado_db or {}).get('message')) or 'Error al actualizar la asistencia.'}"
            )
            return

        try:
            row_db = self.asistencia_model.get_by_empleado_fecha(int(numero_nomina), fecha_iso)
            if isinstance(row_db, dict) and row_db:
                registro_actualizado["__fecha_iso"] = self._fecha_to_iso(row_db.get("fecha")) or fecha_iso
                registro_actualizado["fecha"] = self._fecha_to_display(row_db.get("fecha"))
                registro_actualizado["descanso"] = self._normalizar_descanso(row_db.get("descanso"))
                registro_actualizado["hora_entrada"] = self._normalizar_hora_display(row_db.get("hora_entrada"))
                registro_actualizado["hora_salida"] = self._normalizar_hora_display(row_db.get("hora_salida"))
                if "tiempo_trabajo" in row_db:
                    registro_actualizado["tiempo_trabajo"] = self._decimal_horas_a_hhmm(row_db.get("tiempo_trabajo"))
                if "tiempo_trabajo_con_descanso" in row_db:
                    registro_actualizado["tiempo_trabajo_con_descanso"] = self._decimal_horas_a_hhmm(
                        row_db.get("tiempo_trabajo_con_descanso")
                    )
                est = str(row_db.get("estado") or "").strip().upper()
                registro_actualizado["estado"] = est if est else "INCOMPLETO"
        except Exception:
            pass

        extra_msg = self._formatear_resumen_sync(resultado_db.get("sync"))
        self.window_snackbar.show_success(f"OK. Asistencia actualizada correctamente{extra_msg}")
        self._emit_pagamentos_delta({"id_empleado": int(numero_nomina), "periodo_ini": fecha_iso, "periodo_fin": fecha_iso})

        self.editando.clear()
        if grupo_encontrado:
            self.grupos_expandido[grupo_encontrado] = True

        self._actualizar_tabla()
        self._safe_update()

    def _cancelar_edicion(self, numero_nomina, fecha_iso):
        self.editando.clear()
        self._actualizar_tabla()
        self._safe_update()
        self.window_snackbar.show_success("ℹ️ Edición cancelada.")

    # --------------------- Eliminar ---------------------
    def _eliminar_grupo(self, grupo):
        ModalAlert(
            title_text="¿Eliminar grupo?",
            message=f"¿Deseas eliminar todas las asistencias del grupo '{grupo}'?",
            on_confirm=lambda: self._confirmar_eliminar_grupo(grupo),
            on_cancel=self._actualizar_tabla,
        ).mostrar()

    def _confirmar_eliminar_grupo(self, grupo):
        try:
            registros = self.datos_por_grupo.get(grupo, [])
            avisos: list[dict] = []
            fechas_afectadas = set()

            for reg in registros:
                self._ensure_keys(reg)
                fecha_disp = str(reg.get("fecha"))
                fechas_afectadas.add(fecha_disp)

                fecha_iso = str(reg.get("__fecha_iso") or "") or self._fecha_to_iso(fecha_disp) or fecha_disp
                self.asistencia_model.delete_by_numero_nomina_and_fecha(int(reg["numero_nomina"]), fecha_iso)

                avisos.append(
                    {"id_empleado": int(reg["numero_nomina"]), "periodo_ini": fecha_iso, "periodo_fin": fecha_iso}
                )

            self.window_snackbar.show_success(f"✅ Grupo '{grupo}' eliminado.")
            for f in fechas_afectadas:
                self._notificar_fecha_libre_si_corresponde(f)
            for payload in avisos:
                self._emit_pagamentos_delta(payload)

        except Exception as e:
            self.window_snackbar.show_error(f"❌ Error eliminando grupo: {str(e)}")

        self._actualizar_tabla()
        self._safe_update()

    def _confirmar_eliminacion(self, numero, fecha_any, e=None):
        fecha_disp = self._fecha_to_display(fecha_any)
        ModalAlert(
            title_text="¿Eliminar asistencia?",
            message=f"¿Deseas eliminar el registro del empleado {numero} el día {fecha_disp}?",
            on_confirm=lambda: self._eliminar_asistencia(numero, fecha_any),
            on_cancel=self._actualizar_tabla,
        ).mostrar()

    def _eliminar_asistencia(self, numero, fecha_any):
        try:
            fecha_iso = self._fecha_to_iso(fecha_any) or str(fecha_any)
            resultado = self.asistencia_model.delete_by_numero_nomina_and_fecha(int(numero), fecha_iso)
            if resultado.get("status") == "success":
                self.window_snackbar.show_success("✅ Asistencia eliminada correctamente.")
                self._notificar_fecha_libre_si_corresponde(str(fecha_any))
                self._emit_pagamentos_delta({"id_empleado": int(numero), "periodo_ini": fecha_iso, "periodo_fin": fecha_iso})
            else:
                self.window_snackbar.show_error(f"❌ {resultado.get('message')}")
        except Exception as e:
            self.window_snackbar.show_error(f"⚠️ {str(e)}")

        self._actualizar_tabla()
        self._safe_update()

    def _notificar_fecha_libre_si_corresponde(self, fecha_str: str):
        try:
            target = self._parse_fecha_any(fecha_str)
            if not target:
                return

            res = self.asistencia_model.get_all()
            if res.get("status") == "success":
                quedan = False
                for r in res.get("data", []):
                    d = self._parse_fecha_any(r.get("fecha"))
                    if d and d == target:
                        quedan = True
                        break
                if not quedan and self.page and getattr(self.page, "pubsub", None):
                    try:
                        self.page.pubsub.send("calendario:fecha_libre", target.strftime("%d/%m/%Y"))
                    except Exception:
                        pass
        except Exception:
            pass

    # --------------------- Exportar ---------------------
    def _exportar_asistencias(self, ruta_guardado: str):
        try:
            resultado = self.asistencia_model.get_all()
            if resultado.get("status") != "success":
                self.window_snackbar.show_error("❌ No se pudieron obtener los datos para exportar.")
                return

            df = pd.DataFrame(resultado.get("data", []))
            df.to_excel(ruta_guardado, index=False)
            self.window_snackbar.show_success("✅ Asistencias exportadas correctamente.")
        except Exception as e:
            self.window_snackbar.show_error(f"❌ Error al exportar asistencias: {str(e)}")

    # --------------------- Utilidades ---------------------
    def _agrupar_por_grupo_importacion(self, datos: list) -> dict:
        agrupado = {}
        for reg in datos:
            grupo_fecha = reg.get("grupo_importacion")
            if not grupo_fecha:
                d = self._parse_fecha_any(reg.get("fecha")) or date.today()
                grupo_fecha = f"GRUPO:{d.strftime('%d/%m/%Y')}"
                reg["grupo_importacion"] = grupo_fecha
            agrupado.setdefault(grupo_fecha, []).append(reg)
        return agrupado

    def _extraer_fecha_primer_registro(self, registros: list) -> date:
        try:
            if not registros:
                return date.min
            d = self._parse_fecha_any(registros[0].get("fecha"))
            return d if d else date.min
        except Exception:
            return date.min

    def _grupo_date_for_sort(self, grupo: str, registros: list) -> date:
        if registros:
            return self._extraer_fecha_primer_registro(registros)
        try:
            label = str(grupo or "")
            if "GRUPO:" in label:
                label = label.split("GRUPO:", 1)[-1].strip()
            d = self._parse_fecha_any(label)
            return d if d else date.min
        except Exception:
            return date.min

    # alias real llamado por AsistenciasColumnBuilder
    def _activar_edicion(self, numero_nomina, fecha_any):
        numero_nomina = int(numero_nomina)
        fecha_iso = self._fecha_to_iso(fecha_any)

        self.editando.clear()
        self.editando[(numero_nomina, fecha_iso)] = True

        grupo_encontrado, _ = self._find_reg(numero_nomina, fecha_iso)
        if grupo_encontrado:
            self.grupos_expandido[grupo_encontrado] = True

        self._actualizar_tabla()
        self._safe_update()

    # --------------------- Construcción inicial ---------------------
    def _construir_paneles_iniciales(self):
        res = self.asistencia_model.get_all()
        if res.get("status") != "success":
            self.window_snackbar.show_error("❌ No se pudieron cargar asistencias.")
            return

        datos = res.get("data", [])
        for r in datos:
            self._normalize_row_for_ui(r)

        self.datos_por_grupo = self._agrupar_por_grupo_importacion(datos)
        for g in self._manual_groups:
            if g not in self.datos_por_grupo:
                self.datos_por_grupo[g] = []

        grupos_ordenados = sorted(
            list(self.datos_por_grupo.items()),
            key=lambda item: -self._grupo_date_for_sort(item[0], item[1]).toordinal(),
        )

        paneles = []
        for grupo, _registros in grupos_ordenados:
            self.grupos_expandido.setdefault(grupo, False)

            cols = self.crear_columnas(grupo)
            tabla = ft.DataTable(
                columns=cols,
                rows=[],
                column_spacing=self._TABLE_COL_SPACING,
                data_row_max_height=44,
                heading_row_height=34,
            )
            self._tablas_por_grupo[grupo] = tabla

            encabezado = ft.Row(
                [
                    ft.Text(f"🗂 {grupo}", expand=True, weight="bold"),
                    ft.IconButton(
                        icon=ft.icons.ADD,
                        tooltip="Agregar asistencia",
                        on_click=lambda e, g=grupo: self._agregar_fila_en_grupo(g),
                    ),
                    ft.IconButton(
                        icon=ft.icons.DELETE_OUTLINE,
                        tooltip="Eliminar grupo",
                        icon_color=ft.colors.RED_600,
                        on_click=lambda e, g=grupo: self._eliminar_grupo(g),
                    ),
                ],
                spacing=6,
            )

            vertical_scroll_column = ft.Column(controls=[tabla], expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
            self._vcols_by_group[grupo] = vertical_scroll_column

            inner_w_container = ft.Container(
                content=vertical_scroll_column, width=self._get_table_width(), alignment=ft.alignment.top_left
            )

            horizontal_row = ft.Row(
                controls=[inner_w_container],
                expand=True,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.START,
                scroll=ft.ScrollMode.AUTO,
            )

            viewport_container = ft.Container(height=self._panel_viewport_h, expand=False, content=horizontal_row)
            panel_content = ft.Column(controls=[ft.Container(key=grupo), viewport_container], spacing=8)

            panel = ft.ExpansionPanel(
                header=encabezado,
                content=panel_content,
                can_tap_header=True,
                expanded=self.grupos_expandido[grupo],
            )
            panel.on_expansion_changed = lambda e, g=grupo: self._toggle_expansion(g)

            paneles.append(panel)

        epl = ft.ExpansionPanelList(expand=True, controls=paneles)

        self._root_column.controls = [self._top_row, epl]
        self._update_panels_viewport_sizes()
        self._safe_update()

    # --------------------- Helper: auto-llenar nombre en fila nueva ---------------------
    def _wire_autofill_nombre_en_fila_nueva(self, fila_ui: ft.DataRow, registro: dict, resolver_nombre: Callable[[int], str]):
        try:
            num_cell = fila_ui.cells[0].content
            name_cell = fila_ui.cells[1].content
            if not isinstance(num_cell, ft.Container) or not isinstance(name_cell, ft.Container):
                return
            numero_tf = num_cell.content
            nombre_txt = name_cell.content

            if not isinstance(numero_tf, ft.TextField) or not isinstance(nombre_txt, ft.Text):
                return

            prev_blur = getattr(numero_tf, "on_blur", None)
            prev_change = getattr(numero_tf, "on_change", None)
            last_val = {"v": None}

            def _sync_nombre(value: str):
                try:
                    val = str(value or "").strip()
                    if val == last_val["v"]:
                        return
                    last_val["v"] = val
                    if val.isdigit():
                        nombre = (resolver_nombre(int(val)) or "").strip()
                        registro["nombre_completo"] = nombre
                        nombre_txt.value = nombre if nombre else "?"
                    else:
                        registro["nombre_completo"] = ""
                        nombre_txt.value = "?"
                except Exception:
                    registro["nombre_completo"] = ""
                    nombre_txt.value = "?"
                self._safe_update()

            def _on_blur_compuesto(e):
                try:
                    if callable(prev_blur):
                        prev_blur(e)
                except Exception:
                    pass
                _sync_nombre(numero_tf.value)

            def _on_change_compuesto(e):
                try:
                    if callable(prev_change):
                        prev_change(e)
                except Exception:
                    pass
                _sync_nombre(e.control.value)

            numero_tf.on_blur = _on_blur_compuesto
            numero_tf.on_change = _on_change_compuesto
        except Exception:
            pass

    # --------------------- Refresco de filas por grupo ---------------------
    def _refrescar_filas_grupo(self, grupo: str):
        tabla = self._tablas_por_grupo.get(grupo)
        if not tabla:
            return

        registros = self.datos_por_grupo.get(grupo, [])
        registros_ordenados = self._ordenar_lista(list(registros), grupo)

        filas: list[ft.DataRow] = []

        for reg in registros_ordenados:
            self._normalize_row_for_ui(reg)

            if self._es_editando(reg):
                fila = self.row_helper.build_fila_edicion(
                    registro=reg,
                    on_save=lambda r=reg: self._guardar_edicion(
                        int(r["numero_nomina"]), str(r.get("__fecha_iso") or self._fecha_to_iso(r.get("fecha")))
                    ),
                    on_cancel=lambda r=reg: self._cancelar_edicion(
                        int(r["numero_nomina"]), str(r.get("__fecha_iso") or self._fecha_to_iso(r.get("fecha")))
                    ),
                )
                self._estilizar_fila(
                    grupo=grupo,
                    fila=fila,
                    editable=True,
                    incompleto=(str(reg.get("estado")).upper() == "INCOMPLETO"),
                    reg=reg,
                )
            else:
                fila = self.row_helper.build_fila_vista(
                    registro=reg,
                    on_edit=self._on_click_editar,
                    on_delete=lambda r=reg: self._confirmar_eliminacion(
                        int(r["numero_nomina"]), str(r.get("__fecha_iso") or self._fecha_to_iso(r.get("fecha")))
                    ),
                )
                self._estilizar_fila(
                    grupo=grupo,
                    fila=fila,
                    editable=False,
                    incompleto=(str(reg.get("estado")).upper() == "INCOMPLETO"),
                    reg=reg,
                )

            filas.append(fila)

        # Fila nueva al final
        fila_nueva_data = self.editando.get(("nuevo", grupo))
        hay_fila_nueva = fila_nueva_data is not None
        if hay_fila_nueva:
            fila_nueva_data["descanso"] = self._normalizar_descanso(fila_nueva_data.get("descanso", "MD"))

            def _resolver_nombre_local(numero: int) -> str:
                try:
                    data = self.employees_model.get_by_numero_nomina(numero)
                    if isinstance(data, dict) and data:
                        nombre = data.get("nombre_completo")
                        if not nombre:
                            nombre = f"{(data.get('nombres') or '').strip()} {(data.get('apellidos') or '').strip()}".strip()
                        return nombre or ""
                except Exception:
                    pass
                return ""

            fila_ui = self.row_helper.build_fila_nueva(
                grupo_importacion=grupo,
                registro=fila_nueva_data,
                on_save=lambda g=grupo: self._guardar_fila_nueva(g),
                on_cancel=lambda g=grupo: self._cancelar_fila_nueva(g),
                registros_del_grupo=registros,
            )

            self._wire_autofill_nombre_en_fila_nueva(fila_ui, fila_nueva_data, _resolver_nombre_local)
            self._estilizar_fila(grupo=grupo, fila=fila_ui, editable=True, incompleto=True, reg=fila_nueva_data)
            filas.append(fila_ui)

        # Seguridad: igualar celdas con columnas
        n_cols = len(tabla.columns)
        for f in filas:
            self._fix_row_cells(f, n_cols)

        tabla.rows = filas
        # agrega espacio extra al final para que la nueva fila no quede pegada
        vcol = self._vcols_by_group.get(grupo)
        if vcol is not None:
            if hay_fila_nueva:
                vcol.controls = [tabla, ft.Container(height=95)]
            else:
                vcol.controls = [tabla, ft.Container(height=70)]
        self._safe_update()

        # Auto-scroll si hay fila nueva
        if hay_fila_nueva:
            try:
                if vcol is not None:
                    self._safe_update()
                    vcol.scroll_to(offset=10**9, duration=260)
                    self._safe_update()
                    # doble intento para asegurar que llegue al final tras el render
                    vcol.scroll_to(offset=10**9, duration=260)
                    self._safe_update()
            except Exception:
                pass
