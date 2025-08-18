import flet as ft
from datetime import datetime, timedelta, date
import pandas as pd

from app.models.assistance_model import AssistanceModel
from app.controllers.asistencias_import_controller import AsistenciasImportController
from app.core.app_state import AppState
from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.views.containers.theme_controller import ThemeController
from app.views.containers.window_snackbar import WindowSnackbar
from app.views.containers.modal_alert import ModalAlert

from app.helpers.sort_helpers import SortHelper
from app.helpers.table_column_builder import TableColumnBuilder
from app.helpers.asistencias_scroll_helper import AsistenciasScrollHelper
from app.helpers.asistencias_row_helper import AsistenciasRowHelper
from app.helpers.calculo_horas_helper import CalculoHorasHelper
from app.helpers.boton_factory import crear_boton_importar, crear_boton_exportar


class AsistenciasContainer(ft.Container):
    """
    - Scroll H/V por PANEL (grupo) con barras siempre visibles.
    - Conserva la posición del scroll al editar/guardar/refrescar.
    - Compacto y con menos updates para más fluidez.
    """

    # ---- Config UI / rendimiento ----
    _BASE_MIN_WIDTH = 1280   # ancho lógico para provocar H-scroll
    _PAGE_MARGIN_W = 80      # margen lateral aproximado
    _HEADER_ESTIMATE = 160   # alto estimado de encabezados/botones
    _PANEL_MIN_H = 300       # alto mínimo del viewport de panel
    _PANEL_MAX_H = 520       # alto máximo del viewport

    def __init__(self):
        super().__init__(expand=True, padding=16, alignment=ft.alignment.top_center)

        # Core
        self.page = AppState().page
        self.asistencia_model = AssistanceModel()
        self.theme_ctrl = ThemeController()
        self.sort_helper = SortHelper(default_key="numero_nomina")
        self.calculo_helper = CalculoHorasHelper()
        self.window_snackbar = WindowSnackbar(self.page)

        # Estado
        self.editando: dict = {}
        self.datos_por_grupo: dict = {}
        self.grupos_expandido: dict = {}

        # ⛳ Estado de scroll por grupo: {grupo: {"v": float, "h": float}}
        self._scroll_state: dict[str, dict[str, float]] = {}

        # alias para evitar AttributeError en TableColumnBuilder
        self.activar_edicion = self._activar_edicion

        # Helpers de UI
        self.row_helper = AsistenciasRowHelper(
            recalcular_callback=self._recalcular_horas_fila,
            actualizar_callback=self._actualizar_valor_fila
        )

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

        self.column_builder = TableColumnBuilder(
            sort_helper=self.sort_helper,
            on_edit=self.activar_edicion,
            on_delete=lambda reg: self._confirmar_eliminacion(reg["numero_nomina"], reg["fecha"])
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

        # Contenedor principal (el trabajo de scroll lo hacen los paneles)
        self._root_column = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14,
            controls=[
                ft.Text("Registro de Asistencias", size=22, weight="bold"),
                ft.Row([self.import_button, self.export_button],
                       spacing=10, alignment=ft.MainAxisAlignment.START),
                # aquí inyectamos los paneles
            ],
        )
        self.content = ft.Container(expand=True, content=self._root_column)

        # caches de ancho/alto calculados
        self._page_w = 0
        self._page_h = 0
        self._panel_scroll_w = self._BASE_MIN_WIDTH
        self._panel_viewport_h = 360

        if self.page:
            self.page.on_resize = self._on_page_resize

        # cargar y pintar
        self._actualizar_tabla()
        self._recompute_layout_sizes()
        if self.page:
            self.page.update()

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
        """Actualiza ancho/alto del viewport de cada panel sin reconstruir todo."""
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
                                    inner_w_container.width = self._panel_scroll_w
        if self.page:
            self.page.update()

    # --------------------- Tabla y paneles ---------------------
    def crear_columnas(self):
        return self.column_builder.build_columns(self.columnas_definidas)

    def _actualizar_tabla(self):
        res = self.asistencia_model.get_all()
        if res["status"] != "success":
            self.window_snackbar.show_error("❌ No se pudieron cargar asistencias.")
            return

        datos = res["data"]
        self.datos_por_grupo = self._agrupar_por_grupo_importacion(datos)

        # Reemplaza solo la lista de paneles (deja título/botones)
        new_panel_list = self._construir_paneles()
        self._root_column.controls = self._root_column.controls[:2] + [new_panel_list]

    def _construir_paneles(self) -> ft.ExpansionPanelList:
        if not self.datos_por_grupo:
            return ft.ExpansionPanelList(
                expand=True,
                controls=[ft.ExpansionPanel(
                    header=ft.Text("Sin datos"),
                    content=ft.Text("No hay asistencias registradas.")
                )]
            )

        paneles = []
        grupos_ordenados = sorted(
            self.datos_por_grupo.items(),
            key=lambda item: self._extraer_fecha_primer_registro(item[1]),
            reverse=True,
        )

        # expandir último grupo por defecto
        if not self.grupos_expandido and grupos_ordenados:
            self.grupos_expandido = {g: False for g, _ in grupos_ordenados}
            self.grupos_expandido[grupos_ordenados[0][0]] = True

        cols = self.crear_columnas()

        for grupo, registros in grupos_ordenados:
            expandido = self.grupos_expandido.get(grupo, False)

            # filas (vista/edición)
            filas = []
            for reg in registros:
                if reg.get("__error_horas", False):
                    reg["estado"] = "ERROR"

                if self._es_editando(reg):
                    filas.append(
                        self.row_helper.build_fila_edicion(
                            registro=reg,
                            on_save=lambda g=grupo, r=reg: self._guardar_edicion(r["numero_nomina"], r["fecha"]),
                            on_cancel=lambda g=grupo, r=reg: self._cancelar_edicion(r["numero_nomina"], r["fecha"]),
                        )
                    )
                else:
                    filas.append(
                        self.row_helper.build_fila_vista(
                            registro=reg,
                            on_edit=self._on_click_editar,
                            on_delete=lambda r=reg: self._confirmar_eliminacion(r["numero_nomina"], r["fecha"]),
                        )
                    )

            # fila nueva (si aplica)
            if ("nuevo", grupo) in self.editando:
                nueva_fila = self.row_helper.build_fila_nueva(
                    grupo_importacion=grupo,
                    registro=self.editando[("nuevo", grupo)],
                    on_save=lambda g=grupo: self._guardar_fila_nueva(g),
                    on_cancel=lambda g=grupo: self._cancelar_fila_nueva(g),
                    registros_del_grupo=registros,
                )
                if getattr(nueva_fila, "cells", None) and nueva_fila.cells and nueva_fila.cells[0].content:
                    nueva_fila.cells[0].content.key = f"nuevo-{grupo}"
                filas.append(nueva_fila)

            # DataTable compacta para mejorar fluidez
            tabla = ft.DataTable(
                columns=cols,
                rows=filas,
                column_spacing=10,
                data_row_max_height=36,
                heading_row_height=38,
            )

            # Header del panel
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

            # -------- Viewport por PANEL con scrolls SIEMPRE visibles --------
            # vertical: tabla (si muchas filas)
            vertical_scroll_column = ft.Column(
                controls=[tabla],
                expand=True,
                scroll=ft.ScrollMode.ALWAYS,         # barra vertical del panel
                spacing=0,
            )
            # guarda pos. vertical en tiempo real
            self._bind_vertical_scroll_memory(vertical_scroll_column, grupo)

            # inner ancho (provoca scroll H local)
            inner_w_container = ft.Container(
                content=vertical_scroll_column,
                width=self._panel_scroll_w,          # recalculado on_resize
                alignment=ft.alignment.top_left,
            )

            # fila que activa scroll H local (barra SIEMPRE visible)
            horizontal_row = ft.Row(
                controls=[inner_w_container],
                expand=True,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.START,
                scroll=ft.ScrollMode.ALWAYS,         # barra horizontal del panel
            )
            # guarda pos. horizontal en tiempo real
            self._bind_horizontal_scroll_memory(horizontal_row, grupo)

            # viewport que mantiene visible la barra horizontal
            viewport_container = ft.Container(
                height=self._panel_viewport_h,       # recalculado on_resize
                expand=False,
                content=horizontal_row,
            )

            panel_content = ft.Column(
                controls=[
                    ft.Container(key=grupo),          # ancla por si quieres saltar al grupo
                    viewport_container,               # <<< barras H/V SIEMPRE visibles aquí
                ],
                spacing=8,
            )

            panel = ft.ExpansionPanel(
                header=encabezado,
                content=panel_content,
                can_tap_header=True,
                expanded=expandido,
            )
            panel.on_expansion_changed = lambda e, g=grupo: self._toggle_expansion(g)

            paneles.append(panel)

        epl = ft.ExpansionPanelList(expand=True, controls=paneles)

        # 🔁 Tras construir paneles, restaurar scrolls previamente guardados
        self._restore_all_scroll_positions(epl)

        return epl

    # --------------------- Memoria/restauración de scroll ---------------------
    def _event_px(self, e, axis: str) -> float | None:
        """
        Intenta extraer el pixel offset del evento de scroll.
        'axis' = 'v' o 'h'
        """
        try:
            # flet suele exponer .pixels; en algunos casos .pixels_y / .pixels_x
            if hasattr(e, "pixels"):
                return float(e.pixels)
            if axis == "v":
                for attr in ("pixels_y", "offset_y", "dy"):
                    if hasattr(e, attr):
                        return float(getattr(e, attr))
            else:
                for attr in ("pixels_x", "offset_x", "dx"):
                    if hasattr(e, attr):
                        return float(getattr(e, attr))
        except Exception:
            pass
        return None

    def _bind_vertical_scroll_memory(self, col: ft.Column, grupo: str):
        def _on_scroll(e):
            px = self._event_px(e, "v")
            if px is None:
                return
            st = self._scroll_state.setdefault(grupo, {})
            st["v"] = px
        # si la versión soporta on_scroll
        try:
            col.on_scroll = _on_scroll
            col.on_scroll_interval = 40
        except Exception:
            pass

    def _bind_horizontal_scroll_memory(self, row: ft.Row, grupo: str):
        def _on_scroll(e):
            px = self._event_px(e, "h")
            if px is None:
                return
            st = self._scroll_state.setdefault(grupo, {})
            st["h"] = px
        try:
            row.on_scroll = _on_scroll
            row.on_scroll_interval = 40
        except Exception:
            pass

    def _restore_all_scroll_positions(self, epl: ft.ExpansionPanelList):
        """Restaura los offsets H/V por grupo tras reconstruir paneles."""
        for p in epl.controls:
            if not isinstance(p, ft.ExpansionPanel) or not isinstance(p.content, ft.Column):
                continue
            # content.controls = [anchor, viewport_container]
            if len(p.content.controls) < 2:
                continue
            viewport_container: ft.Container = p.content.controls[1]
            if not isinstance(viewport_container, ft.Container):
                continue
            if not isinstance(viewport_container.content, ft.Row):
                continue
            hrow: ft.Row = viewport_container.content
            if not hrow.controls or not isinstance(hrow.controls[0], ft.Container):
                continue
            inner_w_container: ft.Container = hrow.controls[0]
            if not isinstance(inner_w_container.content, ft.Column):
                continue
            vcol: ft.Column = inner_w_container.content

            grupo = None
            # el anchor está en content.controls[0]
            anchor = p.content.controls[0]
            if isinstance(anchor, ft.Container) and anchor.key:
                grupo = str(anchor.key)
            if not grupo:
                continue

            st = self._scroll_state.get(grupo, {})
            v = st.get("v", None)
            h = st.get("h", None)

            # restaurar vertical
            try:
                if v is not None:
                    # si la API soporta offset:
                    vcol.scroll_to(offset=v, duration=1)
            except Exception:
                pass

            # restaurar horizontal
            try:
                if h is not None:
                    hrow.scroll_to(offset=h, duration=1)
            except Exception:
                pass

    # --------------------- Acciones / edición ---------------------
    def _recalcular_horas_fila(self, grupo):
        if ("nuevo", grupo) in self.editando:
            self._actualizar_tabla()
            if self.page:
                self.page.update()
            return
        for (numero_nomina, fecha), edit_flag in self.editando.items():
            if edit_flag is True:
                for registros in self.datos_por_grupo.get(grupo, []):
                    if registros["numero_nomina"] == numero_nomina and str(registros["fecha"]) == str(fecha):
                        self._actualizar_tabla()
                        if self.page:
                            self.page.update()
                        return

    def _on_click_editar(self, numero_nomina, fecha):
        self.activar_edicion(numero_nomina, fecha)
        # 🔇 no desplazamos el scroll: se conservará al reconstruir
        self._actualizar_tabla()
        if self.page:
            self.page.update()

    def _actualizar_valor_fila(self, grupo, campo, valor):
        if ("nuevo", grupo) in self.editando:
            self.editando[("nuevo", grupo)][campo] = valor
            return
        for (numero_nomina, fecha), edit_flag in self.editando.items():
            if edit_flag is True:
                for registros in self.datos_por_grupo.get(grupo, []):
                    if registros["numero_nomina"] == numero_nomina and str(registros["fecha"]) == str(fecha):
                        registros[campo] = valor
                        return

    def _agregar_fila_en_grupo(self, grupo_importacion):
        self.editando[("nuevo", grupo_importacion)] = {
            "numero_nomina": "",
            "fecha": "",
            "hora_entrada": "",
            "hora_salida": "",
            "descanso": "SN",
            "tiempo_trabajo": "0.00",
            "estado": "PENDIENTE",
        }
        self.grupos_expandido = {k: False for k in self.datos_por_grupo.keys()}
        self.grupos_expandido[grupo_importacion] = True
        self._actualizar_tabla()
        if self.page:
            self.page.update()

    def _guardar_fila_nueva(self, grupo: str):
        try:
            fila = self.editando.get(("nuevo", grupo), {})
            numero = str(fila.get("numero_nomina", "")).strip()
            if not numero.isdigit():
                self.window_snackbar.show_error("❌ Número de nómina inválido.")
                return
            numero = int(numero)

            fecha_str = str(fila.get("fecha", "")).strip()
            try:
                fecha_dt = datetime.strptime(fecha_str, "%d/%m/%Y")
                fecha_iso = fecha_dt.strftime("%Y-%m-%d")
            except Exception:
                self.window_snackbar.show_error("❌ Formato de fecha inválido. Usa DD/MM/AAAA.")
                return

            hora_entrada = self.calculo_helper.sanitizar_hora(fila.get("hora_entrada"))
            hora_salida = self.calculo_helper.sanitizar_hora(fila.get("hora_salida"))
            descanso = fila.get("descanso", "SN")

            resultado = self.calculo_helper.recalcular_con_estado(hora_entrada, hora_salida, descanso)
            if resultado["estado"] != "ok":
                self.window_snackbar.show_error(f"❌ {resultado.get('mensaje', 'Error en tiempo trabajado.')}")
                return

            registros_del_grupo = self.datos_por_grupo.get(grupo, [])
            valido, errores = self.calculo_helper.validar_numero_fecha_en_grupo(
                registros_del_grupo, numero, fecha_str, registro_actual=fila
            )
            if not valido:
                self.window_snackbar.show_error("❌ " + " ".join(errores))
                return

            resultado_db = self.asistencia_model.add(
                numero_nomina=numero,
                fecha=fecha_iso,
                hora_entrada=hora_entrada,
                hora_salida=hora_salida,
                descanso={"SN": 0, "MD": 1, "CMP": 2}.get(descanso, 0),
                grupo_importacion=grupo,
            )
            if not resultado_db or resultado_db.get("status") != "success":
                self.window_snackbar.show_error("❌ Error al guardar en la base de datos.")
                return

            self.window_snackbar.show_success("✅ Asistencia guardada correctamente.")
            self.editando.pop(("nuevo", grupo), None)
            self._actualizar_tabla()
            if self.page:
                self.page.update()

        except Exception:
            self.window_snackbar.show_error("⚠️ Error inesperado al guardar.")

    def _cancelar_fila_nueva(self, grupo):
        if ("nuevo", grupo) in self.editando:
            self.editando.pop(("nuevo", grupo))
            self._actualizar_tabla()
            if self.page:
                self.page.update()
            self.window_snackbar.show_success("ℹ️ Registro cancelado.")

    def _toggle_expansion(self, grupo):
        self.grupos_expandido = {k: False for k in self.datos_por_grupo.keys()}
        self.grupos_expandido[grupo] = True
        # 🔇 No hacemos scroll-to-top del grupo; conservamos offset almacenado
        self._actualizar_tabla()
        if self.page:
            self.page.update()

    def _es_editando(self, registro):
        return self.editando.get((registro["numero_nomina"], str(registro["fecha"])), False)

    def _guardar_edicion(self, numero_nomina, fecha):
        registro_actualizado = None
        for _grupo, registros in self.datos_por_grupo.items():
            for reg in registros:
                if reg["numero_nomina"] == numero_nomina and str(reg["fecha"]) == str(fecha):
                    registro_actualizado = reg
                    break
            if registro_actualizado:
                break

        if not registro_actualizado:
            self.window_snackbar.show_error("❌ No se encontró el registro a actualizar.")
            return

        fecha_valor = str(registro_actualizado.get("fecha", "")).strip()
        try:
            fecha_obj = (
                datetime.strptime(fecha_valor, "%d/%m/%Y")
                if "/" in fecha_valor
                else datetime.strptime(fecha_valor, "%Y-%m-%d")
            )
            registro_actualizado["fecha"] = fecha_obj.strftime("%Y-%m-%d")
        except Exception:
            self.window_snackbar.show_error("⚠️ Fecha inválida. Usa el formato YYYY-MM-DD.")
            return

        def convertir(t):
            if isinstance(t, timedelta):
                return (datetime.min + t).time().strftime("%H:%M:%S")
            return str(t).strip()

        registro_actualizado["hora_entrada"] = convertir(registro_actualizado.get("hora_entrada"))
        registro_actualizado["hora_salida"] = convertir(registro_actualizado.get("hora_salida"))

        resultado = self.row_helper.calculo_helper.recalcular_con_estado(
            registro_actualizado["hora_entrada"],
            registro_actualizado["hora_salida"],
            registro_actualizado.get("descanso", "SN"),
        )
        if resultado["estado"] != "ok":
            self.window_snackbar.show_error("❌ " + (resultado["mensaje"] or "Error al calcular tiempo trabajado."))
            return

        registro_actualizado["tiempo_trabajo"] = resultado["tiempo_trabajo"]
        registro_actualizado["tiempo_trabajo_con_descanso"] = resultado["tiempo_trabajo_con_descanso"]

        resultado_db = self.asistencia_model.update_asistencia(registro_actualizado)
        if resultado_db["status"] == "success":
            self.window_snackbar.show_success("✅ Asistencia actualizada correctamente.")
        else:
            self.window_snackbar.show_error(f"❌ {resultado_db.get('message', 'Error al actualizar la asistencia.')}")

        self.editando.clear()
        self._actualizar_tabla()
        if self.page:
            self.page.update()

    def _cancelar_edicion(self, numero_nomina, fecha):
        self.editando.clear()
        self._actualizar_tabla()
        if self.page:
            self.page.update()
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
            for reg in registros:
                self.asistencia_model.delete_by_numero_nomina_and_fecha(reg["numero_nomina"], reg["fecha"])
            self.window_snackbar.show_success(f"✅ Grupo '{grupo}' eliminado.")
        except Exception as e:
            self.window_snackbar.show_error(f"❌ Error eliminando grupo: {str(e)}")
        self._actualizar_tabla()
        if self.page:
            self.page.update()

    def _confirmar_eliminacion(self, numero, fecha, e=None):
        ModalAlert(
            title_text="¿Eliminar asistencia?",
            message=f"¿Deseas eliminar el registro del empleado {numero} el día {fecha}?",
            on_confirm=lambda: self._eliminar_asistencia(numero, fecha),
            on_cancel=self._actualizar_tabla,
        ).mostrar()

    def _eliminar_asistencia(self, numero, fecha):
        try:
            resultado = self.asistencia_model.delete_by_numero_nomina_and_fecha(numero, fecha)
            if resultado["status"] == "success":
                self.window_snackbar.show_success("✅ Asistencia eliminada correctamente.")
            else:
                self.window_snackbar.show_error(f"❌ {resultado['message']}")
        except Exception as e:
            self.window_snackbar.show_error(f"⚠️ {str(e)}")

        self._actualizar_tabla()
        if self.page:
            self.page.update()

    def _exportar_asistencias(self, ruta_guardado: str):
        try:
            resultado = self.asistencia_model.get_all()
            if resultado["status"] != "success":
                self.window_snackbar.show_error("❌ No se pudieron obtener los datos para exportar.")
                return

            df = pd.DataFrame(resultado["data"])
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
                fecha_registro = reg.get("fecha")
                if isinstance(fecha_registro, str):
                    try:
                        fecha_registro = datetime.strptime(fecha_registro, "%Y-%m-%d").date()
                    except:
                        fecha_registro = date.today()
                grupo_fecha = f"GRUPO:{fecha_registro.strftime('%d/%m/%Y')}"
                reg["grupo_importacion"] = grupo_fecha

            if grupo_fecha not in agrupado:
                agrupado[grupo_fecha] = []
            agrupado[grupo_fecha].append(reg)
        return agrupado

    def _extraer_fecha_primer_registro(self, registros: list):
        try:
            primer_registro = registros[0]
            fecha_str = primer_registro.get("fecha", "")
            return datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except:
            return date.min

    # alias real llamado por TableColumnBuilder
    def _activar_edicion(self, numero_nomina, fecha):
        self.editando.clear()
        self.editando[(numero_nomina, str(fecha))] = True

        grupo_encontrado = None
        for grupo, registros in self.datos_por_grupo.items():
            if any(reg["numero_nomina"] == numero_nomina and str(reg["fecha"]) == str(fecha) for reg in registros):
                grupo_encontrado = grupo
                break

        if grupo_encontrado:
            self.grupos_expandido = {k: False for k in self.datos_por_grupo.keys()}
            self.grupos_expandido[grupo_encontrado] = True
            # 🔇 No hacemos scroll-to-top ni a ancla; se conservará offset
            self._actualizar_tabla()
            if self.page:
                self.page.update()
        else:
            self._actualizar_tabla()
            if self.page:
                self.page.update()
