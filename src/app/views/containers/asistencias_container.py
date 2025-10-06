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

# ⬇️ usamos el column builder especializado para asistencias
from app.helpers.asistencias_column_builder import AsistenciasColumnBuilder
from app.helpers.asistencias_row_helper import AsistenciasRowHelper
from app.helpers.calculo_horas_helper import CalculoHorasHelper
from app.helpers.boton_factory import crear_boton_importar, crear_boton_exportar

# ✅ Helper global de ordenamientos / normalizaciones
from app.helpers.sworting_helper import Sworting


class AsistenciasContainer(ft.Container):
    """
    - Scroll H/V por PANEL (grupo) con barras siempre visibles.
    - Conserva la posición del scroll al editar/guardar/refrescar.
    - Celdas optimizadas (sin recortes) tanto en vista como en edición.
    - Ley: INCOMPLETOS arriba.
    - Sort por encabezado POR PANEL: Nómina, Nombre, Fecha, Hora Entrada, Hora Salida, Estado.
    - Caja "Ordenar por ID nómina": Enter prioriza ese ID. Borrar → orden normal.
    - Caja "Buscar por Nombre": Enter prioriza coincidencias (sin acentos / casefold).
      Si no hay coincidencias, muestra "esta busqueda no esta disponible".
    """

    # ---- Config UI / rendimiento ----
    _BASE_MIN_WIDTH = 1280
    _PAGE_MARGIN_W = 80
    _HEADER_ESTIMATE = 180
    _PANEL_MIN_H = 300
    _PANEL_MAX_H = 520

    # Anchos por columna para evitar recortes (coherentes con encabezados)
    _COL_WIDTHS = {
        "numero_nomina": 100,
        "nombre_completo": 260,
        "fecha": 120,
        "hora_entrada": 120,
        "hora_salida": 120,
        "descanso": 140,
        "tiempo_trabajo": 160,
        "estado": 160,   # 🔥 antes 120 → ahora más ancho
    }


    def __init__(self):
        super().__init__(expand=True, padding=16, alignment=ft.alignment.top_center)

        # Core
        self.page = AppState().page
        self.asistencia_model = AssistanceModel()
        self.theme_ctrl = ThemeController()
        self.calculo_helper = CalculoHorasHelper()
        self.window_snackbar = WindowSnackbar(self.page)

        # Estado
        self.editando: dict = {}
        self.datos_por_grupo: dict = {}
        self.grupos_expandido: dict = {}

        # ⛳ Estado de scroll por grupo: {grupo: {"v": float, "h": float}}
        self._scroll_state: dict[str, dict[str, float]] = {}

        # 🔀 Estado de ordenamiento por GRUPO
        self._group_sort: dict[str, dict] = {}

        # 🎯 Filtros globales (priorización transversal)
        self.sort_id_filter: str | None = None
        self.sort_name_filter: str | None = None

        # alias para evitar AttributeError si algún helper intenta llamar activar_edicion
        self.activar_edicion = self._activar_edicion

        # ⛳ Estado de tablas por grupo para refrescar solo filas
        self._tablas_por_grupo: dict[str, ft.DataTable] = {}

        # Helpers
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
        self._col_index = {f: i for i, (_t, f) in enumerate(self.columnas_definidas)}

        self.column_builder = AsistenciasColumnBuilder(
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

        # ---- Toolbar ----
        self.sort_id_input = ft.TextField(
            label="Ordenar por ID nómina",
            hint_text="Escribe un ID y presiona Enter",
            width=220,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_submit=self._aplicar_sort_id,
            on_change=self._id_on_change_auto_reset,
        )
        self.sort_id_clear_btn = ft.IconButton(icon=ft.icons.CLEAR, tooltip="Limpiar ID", on_click=lambda e: self._limpiar_sort_id())

        self.sort_name_input = ft.TextField(
            label="Buscar por Nombre",
            hint_text="Escribe nombre y presiona Enter",
            width=320,
            on_submit=self._aplicar_sort_nombre,
            on_change=self._nombre_on_change_auto_reset,
        )
        self.sort_name_clear_btn = ft.IconButton(icon=ft.icons.CLEAR, tooltip="Limpiar nombre", on_click=lambda e: self._limpiar_sort_nombre())

        self._title_label = ft.Text("Registro de Asistencias", size=22, weight="bold")
        self._import_export_row = ft.Row([self.import_button, self.export_button], spacing=10, alignment=ft.MainAxisAlignment.START)
        self._toolbar_row = ft.Row(controls=[self.sort_id_input, self.sort_id_clear_btn, self.sort_name_input, self.sort_name_clear_btn], spacing=10, alignment=ft.MainAxisAlignment.START)

        # Contenedor principal
        self._root_column = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14,
            controls=[
                self._title_label,
                self._import_export_row,
                self._toolbar_row,
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

        # 🔥 Primera carga
        self._recompute_layout_sizes()
        self._construir_paneles_iniciales()   # ✅ construye los paneles una sola vez
        self._actualizar_tabla()              # ✅ refresca filas según datos
        self._update_panels_viewport_sizes()
        if self.page:
            self.page.update()


    # --------------------- Interacción de ordenamiento (GLOBAL: filtros) ---------------------
    def _aplicar_sort_id(self, e=None):
        v = (self.sort_id_input.value or "").strip()
        if v and not v.isdigit():
            self.window_snackbar.show_error("❌ ID inválido. Usa solo números.")
            return
        self.sort_id_filter = v if v else None
        self._actualizar_tabla()
        if self.page:
            self.page.update()

    def _limpiar_sort_id(self):
        self.sort_id_input.value = ""
        self.sort_id_filter = None
        self._actualizar_tabla()
        if self.page:
            self.page.update()

    def _id_on_change_auto_reset(self, e: ft.ControlEvent):
        # Si el usuario borra el campo → volver a orden normal sin Enter
        v = (e.control.value or "").strip()
        if v == "" and self.sort_id_filter is not None:
            self.sort_id_filter = None
            self._actualizar_tabla()
            if self.page:
                self.page.update()

    # 🔎 Buscar por Nombre (similar a ID, pero por texto y con aviso si no hay resultados)
    def _aplicar_sort_nombre(self, e=None):
        texto = (self.sort_name_input.value or "").strip()
        if not texto:
            self.sort_name_filter = None
            self._actualizar_tabla()
            if self.page:
                self.page.update()
            return

        # Verificar si hay coincidencias antes de aplicar
        res = self.asistencia_model.get_all()
        if res.get("status") == "success":
            data = res.get("data", [])
            needle = Sworting.normalize_text(texto)
            hay = any(needle in Sworting.normalize_text(r.get("nombre_completo", "")) for r in data)
            if not hay:
                # Mensaje literal solicitado
                self.window_snackbar.show_error("esta busqueda no esta disponible")
                return

        self.sort_name_filter = texto
        self._actualizar_tabla()
        if self.page:
            self.page.update()

    def _limpiar_sort_nombre(self):
        self.sort_name_input.value = ""
        self.sort_name_filter = None
        self._actualizar_tabla()
        if self.page:
            self.page.update()

    def _nombre_on_change_auto_reset(self, e: ft.ControlEvent):
        v = (e.control.value or "").strip()
        if v == "" and self.sort_name_filter is not None:
            self.sort_name_filter = None
            self._actualizar_tabla()
            if self.page:
                self.page.update()

    # --------------------- Interacción de ordenamiento (POR PANEL) ---------------------
    def _get_group_sort(self, grupo: str) -> dict:
        st = self._group_sort.get(grupo)
        if not st:
            # valor por defecto: por estado asc (INCOMPLETO/ERROR primero)
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

        # refrescar solo el contenido sin resetear expansiones
        self._actualizar_tabla()
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
    def _make_sortable_header(self, titulo: str, campo: str, width: int | None, grupo: str):
        st = self._get_group_sort(grupo)
        arrow = ""
        if st["key"] == campo:
            arrow = " ▲" if st["asc"] else " ▼"
        label = ft.GestureDetector(
            on_tap=lambda e, f=campo, g=grupo: self._on_header_sort_click(g, f),
            mouse_cursor=ft.MouseCursor.CLICK,
            content=ft.Row(
                [ft.Text(f"{titulo}{arrow}", size=12, weight="bold")],
                alignment=ft.MainAxisAlignment.START,
                spacing=4
            ),
        )
        return ft.Container(label, width=width) if width else label

    def crear_columnas(self, grupo: str):
        cols = self.column_builder.build_columns(self.columnas_definidas)

        # Aplicar anchos fijos y hacer "clickable" los encabezados sortables POR PANEL
        campos_sortables = {"numero_nomina", "nombre_completo", "fecha", "hora_entrada", "hora_salida", "estado"}

        for i, c in enumerate(cols):
            # No tocar la columna "Acciones" que el builder agrega al final
            if i >= len(self.columnas_definidas):
                continue

            titulo, campo = self.columnas_definidas[i]
            width = self._COL_WIDTHS.get(campo, None)

            if campo in campos_sortables:
                c.label = self._make_sortable_header(titulo, campo, width, grupo)
            else:
                # encabezado no sortable, pero con ancho fijo
                if isinstance(c.label, ft.Text):
                    txt = c.label.value
                elif isinstance(c.label, ft.Container) and isinstance(c.label.content, ft.Text):
                    txt = c.label.content.value
                else:
                    txt = titulo
                c.label = ft.Container(ft.Text(txt, size=12, weight="bold"), width=width) if width else ft.Text(txt, size=12, weight="bold")

        return cols

    def _to_minutes(self, t) -> int:
        """
        Convierte 'HH:MM' o 'HH:MM:SS' a minutos.
        Si vacío/None → valor alto (para quedar al final cuando asc), los incompletos ya se priorizan por otra capa.
        """
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
        """
        Ranking fijo:
        - 0 → Incompleto (o error de horas)
        - 1 → Completo/otros
        """
        estado = str(r.get("estado", "")).strip().upper()
        if r.get("__error_horas", False):
            return 0
        return 0 if estado == "INCOMPLETO" else 1

    def _ordenar_lista(self, datos: list[dict], grupo: str) -> list[dict]:
        """
        Orden estable dentro del grupo:
        1) INCOMPLETOS siempre arriba
        2) Tie-breakers → numero_nomina, fecha
        3) Campo principal del grupo (click en encabezado)
        4) Filtros globales: nombre / ID
        """
        st = self._get_group_sort(grupo)
        key, asc = st["key"], st["asc"]

        ordered = sorted(datos, key=self._estado_rank)  # incompletos arriba
        ordered = sorted(ordered, key=lambda r: Sworting.to_number(r.get("numero_nomina", 0)))
        ordered = sorted(ordered, key=lambda r: Sworting.to_date(r.get("fecha")))

        if key == "numero_nomina":
            ordered = sorted(
                ordered,
                key=lambda r: Sworting.to_number(r.get("numero_nomina", 0)),
                reverse=not asc,
            )
        elif key == "nombre_completo":
            ordered = sorted(
                ordered,
                key=lambda r: Sworting.normalize_text(r.get("nombre_completo", "")),
                reverse=not asc,
            )
        elif key == "fecha":
            ordered = sorted(
                ordered,
                key=lambda r: Sworting.to_date(r.get("fecha")),
                reverse=not asc,
            )
        elif key == "hora_entrada":
            ordered = sorted(
                ordered,
                key=lambda r: self._to_minutes(r.get("hora_entrada")),
                reverse=not asc,
            )
        elif key == "hora_salida":
            ordered = sorted(
                ordered,
                key=lambda r: self._to_minutes(r.get("hora_salida")),
                reverse=not asc,
            )
        elif key == "estado":
            ordered = sorted(ordered, key=self._estado_rank, reverse=not asc)

        # Priorizar coincidencia por nombre (si hay filtro global)
        if self.sort_name_filter:
            needle = Sworting.normalize_text(self.sort_name_filter)
            ordered = sorted(
                ordered,
                key=lambda r: 0
                if needle in Sworting.normalize_text(r.get("nombre_completo", ""))
                else 1,
            )

        # Priorizar coincidencia exacta por ID (si hay filtro global)
        if self.sort_id_filter:
            id_str = str(self.sort_id_filter)
            ordered = sorted(
                ordered,
                key=lambda r: 0 if str(r.get("numero_nomina")) == id_str else 1,
            )

        return ordered


    def _actualizar_tabla(self):
        """Refresca datos, crea paneles que falten y conserva expansión/scroll incluso al filtrar."""
        res = self.asistencia_model.get_all()
        if res["status"] != "success":
            self.window_snackbar.show_error("❌ No se pudieron cargar asistencias.")
            return

        datos = res["data"]

        # 🔹 Reagrupar registros
        self.datos_por_grupo = self._agrupar_por_grupo_importacion(datos)

        # 🔹 Ordenar grupos
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
                -self._extraer_fecha_primer_registro(item[1]).toordinal(),
            ),
        )

        # 🔹 Snapshot del estado actual de expansión en UI (antes de refrescar)
        snapshot_expandido = {}
        epl = next((c for c in self._root_column.controls if isinstance(c, ft.ExpansionPanelList)), None)
        if epl:
            for p in epl.controls:
                try:
                    key = str(p.content.controls[0].key)
                    snapshot_expandido[key] = p.expanded
                except Exception:
                    pass

        # 🔹 Merge snapshot con self.grupos_expandido (snapshot tiene prioridad)
        for k, v in snapshot_expandido.items():
            self.grupos_expandido[k] = v

        # 🔹 Inicializar estado expandido si es la primera vez
        if not self.grupos_expandido:
            self.grupos_expandido = {g: False for g, _ in grupos_ordenados}
            for g, registros in grupos_ordenados:
                if any(Sworting.is_asistencia_incomplete(r) for r in registros):
                    self.grupos_expandido[g] = True
        else:
            for g, _ in grupos_ordenados:
                if g not in self.grupos_expandido:
                    self.grupos_expandido[g] = False

        # 🔹 Crear o limpiar paneles (misma lógica de antes)
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
            else:
                panels_by_group[key] = p

        # 🔹 Crear paneles que falten
        for grupo, _ in grupos_ordenados:
            if grupo in panels_by_group:
                continue

            cols = self.crear_columnas(grupo)
            tabla = ft.DataTable(columns=cols, rows=[], column_spacing=12,
                                data_row_max_height=38, heading_row_height=40)
            self._tablas_por_grupo[grupo] = tabla

            encabezado = ft.Row([
                ft.Text(f"🗂 {grupo}", expand=True, weight="bold"),
                ft.IconButton(icon=ft.icons.ADD, tooltip="Agregar asistencia",
                            on_click=lambda e, g=grupo: self._agregar_fila_en_grupo(g)),
                ft.IconButton(icon=ft.icons.DELETE_OUTLINE, tooltip="Eliminar grupo",
                            icon_color=ft.colors.RED_600,
                            on_click=lambda e, g=grupo: self._eliminar_grupo(g)),
            ], spacing=6)

            vertical_scroll_column = ft.Column(controls=[tabla], expand=True,
                                            scroll=ft.ScrollMode.ALWAYS, spacing=0)
            self._bind_vertical_scroll_memory(vertical_scroll_column, grupo)

            inner_w_container = ft.Container(content=vertical_scroll_column,
                                            width=self._panel_scroll_w,
                                            alignment=ft.alignment.top_left)

            horizontal_row = ft.Row(controls=[inner_w_container], expand=True,
                                    alignment=ft.MainAxisAlignment.START,
                                    vertical_alignment=ft.CrossAxisAlignment.START,
                                    scroll=ft.ScrollMode.ALWAYS)
            self._bind_horizontal_scroll_memory(horizontal_row, grupo)

            viewport_container = ft.Container(height=self._panel_viewport_h,
                                            expand=False, content=horizontal_row)

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

        # 🔹 Reordenar paneles
        epl.controls = [panels_by_group[g] for g, _ in grupos_ordenados if g in panels_by_group]

        # 🔹 Refrescar filas y reaplicar expansión desde self.grupos_expandido
        for grupo, _ in grupos_ordenados:
            self._refrescar_filas_grupo(grupo)
            p = panels_by_group.get(grupo)
            if p:
                p.expanded = self.grupos_expandido.get(grupo, False)

        # 🔹 Ajustes visuales
        self._update_panels_viewport_sizes()
        self._restore_all_scroll_positions(epl)

        if self.page:
            self.page.update()


    # --------------------- Estética de filas / celdas ---------------------
    def _estilizar_fila(self, fila: ft.DataRow, editable: bool, incompleto: bool):
        """
        Evita recortes en celdas y estiliza estado/incompleto.
        - Envuelve contenido en Container(width=col_width, expand=True)
        - Si es editable, TextField.expand=True + padding compacto.
        - Marca 'estado' en rojo si está incompleto.
        """
        if not getattr(fila, "cells", None):
            return

        for idx, cell in enumerate(fila.cells):
            if idx >= len(self.columnas_definidas):
                continue

            _, campo = self.columnas_definidas[idx]
            width = self._COL_WIDTHS.get(campo, None)

            contenido = cell.content
            if isinstance(contenido, ft.TextField):
                contenido.expand = True
                contenido.text_size = 12
                contenido.content_padding = ft.padding.symmetric(
                    horizontal=6, vertical=4
                )
                if width:
                    cell.content = ft.Container(contenido, width=width, expand=True)
            else:
                if width:
                    cell.content = ft.Container(contenido, width=width, expand=True)

        # Pintar "Estado" si está incompleto
        try:
            idx_estado = self._col_index.get("estado")
            if idx_estado is not None and idx_estado < len(fila.cells):
                estado_cell = fila.cells[idx_estado]
                if incompleto:
                    txt = ft.Text(
                        "INCOMPLETO",
                        color=ft.colors.RED_600,
                        weight="bold",
                        size=12,
                    )
                    estado_cell.content = ft.Container(
                        txt, width=self._COL_WIDTHS["estado"], expand=True
                    )
                else:
                    contenido = estado_cell.content
                    if isinstance(contenido, ft.Text):
                        txt = ft.Text(contenido.value, size=12)
                        estado_cell.content = ft.Container(
                            txt, width=self._COL_WIDTHS["estado"], expand=True
                        )
        except Exception:
            pass

    # --------------------- Memoria/restauración de scroll ---------------------
    def _event_px(self, e, axis: str) -> float | None:
        try:
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
        for p in epl.controls:
            if not isinstance(p, ft.ExpansionPanel) or not isinstance(p.content, ft.Column):
                continue
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

            # Recuperar key del grupo
            grupo = None
            anchor = p.content.controls[0]
            if isinstance(anchor, ft.Container) and anchor.key:
                grupo = str(anchor.key)
            if not grupo:
                continue

            st = self._scroll_state.get(grupo, {})
            v = st.get("v", None)
            h = st.get("h", None)

            try:
                if v is not None:
                    vcol.scroll_to(offset=v, duration=1)
            except Exception:
                pass
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
                    if (
                        registros["numero_nomina"] == numero_nomina
                        and str(registros["fecha"]) == str(fecha)
                    ):
                        self._actualizar_tabla()
                        if self.page:
                            self.page.update()
                        return

    def _on_click_editar(self, numero_nomina, fecha):
        self.activar_edicion(numero_nomina, fecha)
        self._actualizar_tabla()
        if self.page:
            self.page.update()

    def _actualizar_valor_fila(self, grupo=None, campo=None, valor=None):
        """
        Actualiza el valor de una fila en edición o nueva.
        - grupo, campo y valor vienen del RowHelper.
        - Si se invoca sin argumentos, no hace nada (para callbacks simplificados).
        """
        if grupo is None or campo is None:
            return  # 🔧 evita el TypeError cuando se llama sin args

        # Caso: fila nueva en grupo
        if ("nuevo", grupo) in self.editando:
            self.editando[("nuevo", grupo)][campo] = valor
            return

        # Caso: edición de fila existente
        for (numero_nomina, fecha), edit_flag in self.editando.items():
            if edit_flag is True:
                for registros in self.datos_por_grupo.get(grupo, []):
                    if (
                        registros["numero_nomina"] == numero_nomina
                        and str(registros["fecha"]) == str(fecha)
                    ):
                        registros[campo] = valor
                        return


    def _agregar_fila_en_grupo(self, grupo_importacion):
        # Descanso por defecto = "MD"
        self.editando[("nuevo", grupo_importacion)] = {
            "numero_nomina": "",
            "fecha": "",
            "hora_entrada": "",
            "hora_salida": "",
            "descanso": "MD",
            "tiempo_trabajo": "0.00",
            "estado": "PENDIENTE",
        }
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
                self.window_snackbar.show_error(
                    "❌ Formato de fecha inválido. Usa DD/MM/AAAA."
                )
                return

            hora_entrada = self.calculo_helper.sanitizar_hora(fila.get("hora_entrada"))
            hora_salida = self.calculo_helper.sanitizar_hora(fila.get("hora_salida"))
            descanso = fila.get("descanso", "MD")

            resultado = self.calculo_helper.recalcular_con_estado(
                hora_entrada, hora_salida, descanso
            )
            if resultado["estado"] != "ok":
                self.window_snackbar.show_error(
                    f"❌ {resultado.get('mensaje', 'Error en tiempo trabajado.')}"
                )
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
                descanso={"SN": 0, "MD": 1, "CMP": 2}.get(descanso, 1),
                grupo_importacion=grupo,
            )
            if not resultado_db or resultado_db.get("status") != "success":
                self.window_snackbar.show_error(
                    "❌ Error al guardar en la base de datos."
                )
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

    def _toggle_expansion(self, grupo: str):
        """
        Alterna la expansión de un grupo sin reconstruir paneles completos.
        Solo cambia el estado y deja que la UI lo refleje.
        """
        estado_actual = self.grupos_expandido.get(grupo, False)
        self.grupos_expandido[grupo] = not estado_actual

        # 🔹 Ya no llamamos a _actualizar_tabla porque eso regeneraba filas de todos.
        # Aquí solo refrescamos tamaños del panel afectado.
        self._update_panels_viewport_sizes()

        if self.page:
            self.page.update()


    def _es_editando(self, registro):
        return self.editando.get(
            (registro["numero_nomina"], str(registro["fecha"])), False
        )

    def _guardar_edicion(self, numero_nomina, fecha):
        registro_actualizado = None
        for _grupo, registros in self.datos_por_grupo.items():
            for reg in registros:
                if reg["numero_nomina"] == numero_nomina and str(reg["fecha"]) == str(
                    fecha
                ):
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

        registro_actualizado["hora_entrada"] = convertir(
            registro_actualizado.get("hora_entrada")
        )
        registro_actualizado["hora_salida"] = convertir(
            registro_actualizado.get("hora_salida")
        )

        resultado = self.row_helper.calculo_helper.recalcular_con_estado(
            registro_actualizado["hora_entrada"],
            registro_actualizado["hora_salida"],
            registro_actualizado.get("descanso", "MD"),
        )
        if resultado["estado"] != "ok":
            self.window_snackbar.show_error(
                "❌ " + (resultado["mensaje"] or "Error al calcular tiempo trabajado.")
            )
            return

        registro_actualizado["tiempo_trabajo"] = resultado["tiempo_trabajo"]
        registro_actualizado["tiempo_trabajo_con_descanso"] = resultado[
            "tiempo_trabajo_con_descanso"
        ]

        # Solo forzamos INCOMPLETO si aplica
        if Sworting.is_asistencia_incomplete(registro_actualizado):
            registro_actualizado["estado"] = "INCOMPLETO"

        resultado_db = self.asistencia_model.update_asistencia(registro_actualizado)
        if resultado_db["status"] == "success":
            self.window_snackbar.show_success("✅ Asistencia actualizada correctamente.")
        else:
            self.window_snackbar.show_error(
                f"❌ {resultado_db.get('message', 'Error al actualizar la asistencia.')}"
            )

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
            fechas_afectadas = set()
            for reg in registros:
                fechas_afectadas.add(str(reg["fecha"]))
                self.asistencia_model.delete_by_numero_nomina_and_fecha(
                    reg["numero_nomina"], reg["fecha"]
                )
            self.window_snackbar.show_success(f"✅ Grupo '{grupo}' eliminado.")
            # Notificar calendario por cada fecha ahora libre
            for f in fechas_afectadas:
                self._notificar_fecha_libre_si_corresponde(f)
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
            resultado = self.asistencia_model.delete_by_numero_nomina_and_fecha(
                numero, fecha
            )
            if resultado["status"] == "success":
                self.window_snackbar.show_success("✅ Asistencia eliminada correctamente.")
                self._notificar_fecha_libre_si_corresponde(str(fecha))
            else:
                self.window_snackbar.show_error(f"❌ {resultado['message']}")
        except Exception as e:
            self.window_snackbar.show_error(f"⚠️ {str(e)}")

        self._actualizar_tabla()
        if self.page:
            self.page.update()

    def _notificar_fecha_libre_si_corresponde(self, fecha_str: str):
        """
        Revisa si ya no existen registros para la fecha dada.
        Si está vacía, notifica a calendario para 'reabrir' esa fecha.
        """
        try:
            res = self.asistencia_model.get_all()
            if res.get("status") == "success":
                quedan = any(
                    str(r.get("fecha")) == fecha_str for r in res.get("data", [])
                )
                if not quedan and self.page:
                    self.page.pubsub.send("calendario:fecha_libre", fecha_str)
        except Exception:
            pass

    def _exportar_asistencias(self, ruta_guardado: str):
        try:
            resultado = self.asistencia_model.get_all()
            if resultado["status"] != "success":
                self.window_snackbar.show_error(
                    "❌ No se pudieron obtener los datos para exportar."
                )
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
                        fecha_registro = datetime.strptime(
                            fecha_registro, "%Y-%m-%d"
                        ).date()
                    except Exception:
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
        except Exception:
            return date.min

    # alias real llamado por AsistenciasColumnBuilder
    def _activar_edicion(self, numero_nomina, fecha):
        """
        Activa el modo edición para el registro (numero_nomina, fecha),
        expande el panel correspondiente y re-renderiza manteniendo los scrolls.
        """
        # Limpiar cualquier edición previa y marcar el registro actual como 'en edición'
        self.editando.clear()
        self.editando[(numero_nomina, str(fecha))] = True

        # Buscar el grupo que contiene el registro para expandirlo
        grupo_encontrado = None
        for grupo, registros in self.datos_por_grupo.items():
            if any(
                r.get("numero_nomina") == numero_nomina and str(r.get("fecha")) == str(fecha)
                for r in registros
            ):
                grupo_encontrado = grupo
                break

        if grupo_encontrado:
            # Aseguramos que el grupo quede expandido (no tocamos el resto)
            self.grupos_expandido[grupo_encontrado] = True

        # Re-pintar manteniendo memorias de scroll
        self._actualizar_tabla()
        if self.page:
            self.page.update()


    def _construir_paneles_iniciales(self):
        """Construye los paneles una sola vez y guarda referencias a las tablas."""
        res = self.asistencia_model.get_all()
        if res["status"] != "success":
            self.window_snackbar.show_error("❌ No se pudieron cargar asistencias.")
            return

        datos = res["data"]
        self.datos_por_grupo = self._agrupar_por_grupo_importacion(datos)

        paneles = []
        for grupo, registros in self.datos_por_grupo.items():
            self.grupos_expandido.setdefault(grupo, False)

            cols = self.crear_columnas(grupo)
            filas = []  # vacío por ahora, las cargaremos en `_refrescar_filas_grupo`

            tabla = ft.DataTable(
                columns=cols,
                rows=filas,
                column_spacing=12,
                data_row_max_height=38,
                heading_row_height=40,
            )
            self._tablas_por_grupo[grupo] = tabla

            encabezado = ft.Row(
                [
                    ft.Text(f"🗂 {grupo}", expand=True, weight="bold"),
                    ft.IconButton(icon=ft.icons.ADD, tooltip="Agregar asistencia",
                                on_click=lambda e, g=grupo: self._agregar_fila_en_grupo(g)),
                    ft.IconButton(icon=ft.icons.DELETE_OUTLINE, tooltip="Eliminar grupo",
                                icon_color=ft.colors.RED_600,
                                on_click=lambda e, g=grupo: self._eliminar_grupo(g)),
                ],
                spacing=6,
            )

            vertical_scroll_column = ft.Column(controls=[tabla], expand=True,
                                            scroll=ft.ScrollMode.ALWAYS, spacing=0)
            self._bind_vertical_scroll_memory(vertical_scroll_column, grupo)

            inner_w_container = ft.Container(
                content=vertical_scroll_column,
                width=self._panel_scroll_w,
                alignment=ft.alignment.top_left,
            )

            horizontal_row = ft.Row(
                controls=[inner_w_container],
                expand=True,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.START,
                scroll=ft.ScrollMode.ALWAYS,
            )
            self._bind_horizontal_scroll_memory(horizontal_row, grupo)

            viewport_container = ft.Container(
                height=self._panel_viewport_h,
                expand=False,
                content=horizontal_row,
            )

            panel_content = ft.Column(controls=[ft.Container(key=grupo), viewport_container],
                                    spacing=8)

            panel = ft.ExpansionPanel(
                header=encabezado,
                content=panel_content,
                can_tap_header=True,
                expanded=self.grupos_expandido[grupo],
            )
            panel.on_expansion_changed = lambda e, g=grupo: self._toggle_expansion(g)

            paneles.append(panel)

        epl = ft.ExpansionPanelList(expand=True, controls=paneles)

        self._root_column.controls = [
            self._title_label,
            self._import_export_row,
            self._toolbar_row,
            epl,
        ]
        self._update_panels_viewport_sizes()
        if self.page:
            self.page.update()


    def _refrescar_filas_grupo(self, grupo: str):
        """Actualiza las filas de la tabla de un grupo sin reconstruir paneles."""
        tabla = self._tablas_por_grupo.get(grupo)
        if not tabla:
            return

        registros = self.datos_por_grupo.get(grupo, [])
        registros_ordenados = self._ordenar_lista(list(registros), grupo)

        filas = []
        for reg in registros_ordenados:
            # 🔹 Descanso por defecto = "MD"
            if not reg.get("descanso") or reg.get("descanso") in (0, "0", "SN", "", None):
                reg["descanso"] = "MD"

            # 🔹 Recalcular horas
            hora_entrada = self.calculo_helper.sanitizar_hora(reg.get("hora_entrada"))
            hora_salida = self.calculo_helper.sanitizar_hora(reg.get("hora_salida"))
            resultado = self.calculo_helper.recalcular_con_estado(
                hora_entrada,
                hora_salida,
                reg.get("descanso", "MD")
            )

            if resultado["estado"] == "ok":
                reg["tiempo_trabajo"] = resultado["tiempo_trabajo"]
                reg["tiempo_trabajo_con_descanso"] = resultado["tiempo_trabajo_con_descanso"]
                reg["estado"] = "COMPLETO"
                reg["__error_horas"] = False
            else:
                reg["__error_horas"] = True
                reg["estado"] = "INCOMPLETO"

            # 🔹 Estado inicial si aún no hay
            if not reg.get("estado"):
                reg["estado"] = "INCOMPLETO" if Sworting.is_asistencia_incomplete(reg) else "COMPLETO"

            # 🔹 Texto del estado con color y centrado
            estado_text = ft.Text(
                reg.get("estado", "").upper(),
                text_align=ft.TextAlign.CENTER,
                color=ft.colors.RED if reg["estado"] == "INCOMPLETO"
                    else ft.colors.GREEN if reg["estado"] == "COMPLETO"
                    else ft.colors.GREY
            )
            reg["__estado_text_widget"] = estado_text  # opcional, por si necesitas reusar

            # 🔹 Construcción de filas
            if self._es_editando(reg):
                fila = self.row_helper.build_fila_edicion(
                    registro=reg,
                    on_save=lambda r=reg: self._guardar_edicion(r["numero_nomina"], r["fecha"]),
                    on_cancel=lambda r=reg: self._cancelar_edicion(r["numero_nomina"], r["fecha"]),
                )
                self._estilizar_fila(fila, editable=True, incompleto=(reg["estado"] == "INCOMPLETO"))
            else:
                fila = self.row_helper.build_fila_vista(
                    registro=reg,
                    on_edit=self._on_click_editar,
                    on_delete=lambda r=reg: self._confirmar_eliminacion(r["numero_nomina"], r["fecha"]),
                )
                self._estilizar_fila(fila, editable=False, incompleto=(reg["estado"] == "INCOMPLETO"))

            filas.append(fila)

        tabla.rows = filas
        if self.page:
            self.page.update()
