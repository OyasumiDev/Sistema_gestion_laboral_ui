import flet as ft
from app.core.app_state import AppState
from app.models.employes_model import EmployesModel
from app.views.containers.modal_alert import ModalAlert
from app.views.containers.window_snackbar import WindowSnackbar
from app.core.invokers.safe_scroll_invoker import SafeScrollInvoker
from app.controllers.employes_import_controller import EmpleadosImportController


class EmpleadosContainer(ft.Container):
    def __init__(self):
        super().__init__()

        # Core
        self.page = AppState().page
        self.window_snackbar = WindowSnackbar(self.page)
        self.empleado_model = EmployesModel()

        # Estado
        self.fila_editando = None
        self.fila_nueva_en_proceso = False
        self.sort_id_filter: str | None = None
        self.sort_name_filter: str | None = None
        self.orden_actual = {"numero_nomina": None, "sueldo_por_hora": None}

        # Tabla y scroll
        self.table = None
        self.table_container = ft.Container(
            expand=True,
            alignment=ft.alignment.top_center,
            content=ft.Column(
                controls=[],
                alignment=ft.MainAxisAlignment.START,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            ),
        )

        self.scroll_column_ref = ft.Ref[ft.Column]()
        self.scroll_anchor = ft.Container(height=1, key="bottom-anchor")
        self.scroll_column = ft.Column(
            ref=self.scroll_column_ref,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.ALWAYS,
            expand=True,
            controls=[self.table_container, self.scroll_anchor],
        )

        # ---- Import / Export (controlador dedicado) ----
        self.emp_import_ctrl = EmpleadosImportController(
            page=self.page,
            on_success=self._actualizar_tabla,
            on_export=lambda ruta: self.window_snackbar.show_success(f"✅ Exportado: {ruta}")
        )

        # Botón Importar
        self.import_button = ft.GestureDetector(
            on_tap=lambda e: self.emp_import_ctrl.file_invoker.open(),
            content=ft.Container(
                padding=10,
                border_radius=20,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=ft.Row(
                    [
                        ft.Icon(name=ft.icons.FILE_DOWNLOAD_OUTLINED, size=18),
                        ft.Text("Importar", size=12, weight="bold"),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=6,
                ),
            ),
        )

        # Botón Exportar (usa el save_invoker para abrir ventana Guardar como…)
        self.export_button = ft.GestureDetector(
            on_tap=lambda e: self.emp_import_ctrl.save_invoker.open_save(),
            content=ft.Container(
                padding=10,
                border_radius=20,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=ft.Row(
                    [
                        ft.Icon(name=ft.icons.FILE_UPLOAD_OUTLINED, size=18),
                        ft.Text("Exportar", size=12, weight="bold"),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=6,
                ),
            ),
        )

        # Botón Agregar
        self.add_button = ft.GestureDetector(
            on_tap=lambda e: self._insertar_fila_editable(),
            content=ft.Container(
                padding=10,
                border_radius=20,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=ft.Row(
                    [
                        ft.Icon(name=ft.icons.ADD, size=18),
                        ft.Text("Agregar", size=12, weight="bold"),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=6,
                ),
            ),
        )


        # ---- Toolbar (filtros) ----
        self.sort_id_input = ft.TextField(
            label="Ordenar por ID",
            hint_text="Escribe un ID y presiona Enter",
            width=180,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_submit=self._aplicar_sort_id,
            on_change=self._id_on_change_auto_reset,
        )
        self.sort_id_clear_btn = ft.IconButton(
            icon=ft.icons.CLEAR,
            tooltip="Limpiar ID",
            on_click=lambda e: self._limpiar_sort_id(),
        )

        self.sort_name_input = ft.TextField(
            label="Buscar por Nombre",
            hint_text="Escribe nombre y presiona Enter",
            width=260,
            on_submit=self._aplicar_sort_nombre,
            on_change=self._nombre_on_change_auto_reset,
        )
        self.sort_name_clear_btn = ft.IconButton(
            icon=ft.icons.CLEAR,
            tooltip="Limpiar nombre",
            on_click=lambda e: self._limpiar_sort_nombre(),
        )

        # Content
        self.content = ft.Container(
            expand=True,
            padding=20,
            content=ft.Column(
                expand=True,
                alignment=ft.MainAxisAlignment.START,
                spacing=10,
                controls=[
                    ft.Row(
                        spacing=10,
                        alignment=ft.MainAxisAlignment.START,
                        controls=[self.add_button, self.import_button, self.export_button],
                    ),
                    ft.Row(
                        spacing=10,
                        alignment=ft.MainAxisAlignment.START,
                        controls=[
                            self.sort_id_input,
                            self.sort_id_clear_btn,
                            self.sort_name_input,
                            self.sort_name_clear_btn,
                        ],
                    ),
                    ft.Divider(height=1),
                    ft.Container(
                        alignment=ft.alignment.top_center,
                        padding=ft.padding.only(top=10),
                        expand=True,
                        content=self.scroll_column,
                    ),
                ],
            ),
        )

        self._actualizar_tabla()

    # -----------------------------------------------------------------
    # Filtros globales
    # -----------------------------------------------------------------
    def _aplicar_sort_id(self, e=None):
        v = (self.sort_id_input.value or "").strip()
        if v and not v.isdigit():
            self.window_snackbar.show_error("❌ ID inválido. Usa solo números.")
            return
        self.sort_id_filter = v if v else None
        self._actualizar_tabla()

    def _limpiar_sort_id(self):
        self.sort_id_input.value = ""
        self.sort_id_filter = None
        self._actualizar_tabla()

    def _id_on_change_auto_reset(self, e: ft.ControlEvent):
        if (e.control.value or "").strip() == "" and self.sort_id_filter is not None:
            self.sort_id_filter = None
            self._actualizar_tabla()

    def _aplicar_sort_nombre(self, e=None):
        texto = (self.sort_name_input.value or "").strip()
        if not texto:
            self.sort_name_filter = None
            self._actualizar_tabla()
            return

        res = self.empleado_model.get_all()
        data = res.get("data", [])
        hay = any(texto.lower() in (r.get("nombre_completo", "").lower()) for r in data)
        if not hay:
            self.window_snackbar.show_error("esta busqueda no esta disponible")
            return

        self.sort_name_filter = texto
        self._actualizar_tabla()

    def _limpiar_sort_nombre(self):
        self.sort_name_input.value = ""
        self.sort_name_filter = None
        self._actualizar_tabla()

    def _nombre_on_change_auto_reset(self, e: ft.ControlEvent):
        if (e.control.value or "").strip() == "" and self.sort_name_filter is not None:
            self.sort_name_filter = None
            self._actualizar_tabla()

    # -----------------------------------------------------------------
    # Ordenamiento por columnas
    # -----------------------------------------------------------------
    def _icono_orden(self, columna):
        if self.orden_actual.get(columna) == "asc":
            return "▲"
        elif self.orden_actual.get(columna) == "desc":
            return "▼"
        else:
            return "⇅"

    def _ordenar_por_columna(self, columna: str):
        ascendente = self.orden_actual.get(columna) != "asc"
        self.orden_actual = {k: None for k in self.orden_actual}
        self.orden_actual[columna] = "asc" if ascendente else "desc"

        empleados_result = self.empleado_model.get_all()
        empleados = empleados_result.get("data", [])
        empleados = self._ordenar_lista(empleados, columna, ascendente)
        self._refrescar_tabla(empleados)

    def _ordenar_lista(self, datos: list, columna=None, asc=True) -> list:
        ordered = list(datos)

        # Prioridad por ID (si coincide exacto va primero)
        if self.sort_id_filter:
            id_str = str(self.sort_id_filter)
            ordered = sorted(
                ordered,
                key=lambda r: 0 if str(r.get("numero_nomina")) == id_str else 1
            )

        # Prioridad por nombre (si contiene el texto va primero)
        if self.sort_name_filter:
            texto = self.sort_name_filter.lower()
            ordered = sorted(
                ordered,
                key=lambda r: 0 if texto in r.get("nombre_completo", "").lower() else 1
            )

        # Orden por columna
        if columna:
            if columna in ("numero_nomina", "sueldo_por_hora"):
                ordered.sort(key=lambda x: float(x[columna]), reverse=not asc)
            else:
                ordered.sort(key=lambda x: x[columna], reverse=not asc)

        return ordered

    # -----------------------------------------------------------------
    # Tabla y datos
    # -----------------------------------------------------------------
    def _refrescar_tabla(self, empleados: list):
        self.table = self._build_table(empleados)
        self.table_container.content.controls.clear()
        self.table_container.content.controls.append(self.table)
        if self.page:
            self.page.update()

    def _actualizar_tabla(self, fila_en_edicion=None):
        empleados_result = self.empleado_model.get_all()
        empleados = empleados_result.get("data", [])
        self.fila_editando = fila_en_edicion
        empleados = self._ordenar_lista(empleados)
        self._refrescar_tabla(empleados)

    def _build_table(self, empleados):
        rows = []
        for e in empleados:
            numero = e["numero_nomina"]
            en_edicion = self.fila_editando == numero

            # Celda de NOMBRE
            nombre_cell = (
                ft.DataCell(
                    ft.Container(
                        self._crear_textfield_nombre(e["nombre_completo"]),
                        width=300,
                        expand=True
                    )
                )
                if en_edicion else
                ft.DataCell(
                    ft.Container(
                        ft.Text(e["nombre_completo"]),
                        width=300,
                        expand=True
                    )
                )
            )

            # Celda de SUELDO
            sueldo_cell = (
                ft.DataCell(
                    ft.Container(
                        self._crear_textfield_sueldo(e["sueldo_por_hora"]),
                        width=150,
                        expand=True
                    )
                )
                if en_edicion else
                ft.DataCell(
                    ft.Container(
                        ft.Text(str(e["sueldo_por_hora"])),
                        width=150,
                        expand=True
                    )
                )
            )

            def guardar_cambios(ev, id=numero,
                                nombre_cell=nombre_cell.content.content,
                                sueldo_cell=sueldo_cell.content.content):
                errores = []

                nombre_val = nombre_cell.value.strip()
                if len(nombre_val) < 3 or not all(c.isalpha() or c.isspace() for c in nombre_val):
                    nombre_cell.border_color = ft.colors.RED
                    errores.append("Nombre inválido")
                else:
                    nombre_cell.border_color = None

                try:
                    sueldo_val = float(sueldo_cell.value)
                    if sueldo_val < 0:
                        raise ValueError
                    sueldo_cell.border_color = None
                except Exception:
                    sueldo_cell.border_color = ft.colors.RED
                    errores.append("Sueldo inválido")

                self.page.update()

                if errores:
                    self.window_snackbar.show_error("❌ " + " / ".join(errores))
                    return

                resultado = self.empleado_model.update(
                    numero_nomina=id,
                    nombre_completo=nombre_val,
                    sueldo_por_hora=sueldo_val
                )

                self.fila_editando = None

                if resultado["status"] == "success":
                    self._actualizar_tabla()
                    self.window_snackbar.show_success("✅ Cambios guardados correctamente.")
                else:
                    self.window_snackbar.show_error(f"❌ No se pudo guardar: {resultado['message']}")

            def activar_edicion(ev, id=numero):
                self._actualizar_tabla(fila_en_edicion=id)

            def confirmar_eliminar(ev, id=numero):
                def on_confirm():
                    resultado = self.empleado_model.delete_by_numero_nomina(id)
                    if resultado["status"] == "success":
                        self._actualizar_tabla()
                        self.window_snackbar.show_success("✅ Empleado eliminado correctamente.")
                    else:
                        self.window_snackbar.show_error(f"❌ No se pudo eliminar: {resultado['message']}")

                ModalAlert(
                    title_text="¿Eliminar empleado?",
                    message=f"Esta acción no se puede deshacer. ID: {id}",
                    on_confirm=on_confirm
                ).mostrar()

            def crear_boton_cancelar(id_cancelar):
                def cancelar(ev):
                    self.fila_editando = None
                    self.window_snackbar.show_success(f"ℹ️ Se canceló la edición del empleado {id_cancelar}")
                    self._actualizar_tabla()
                return ft.IconButton(
                    icon=ft.icons.CLOSE,
                    icon_color=ft.colors.RED_600,
                    tooltip="Cancelar",
                    on_click=cancelar
                )

            acciones = ft.Row([
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600,
                              tooltip="Guardar", on_click=guardar_cambios),
                crear_boton_cancelar(numero)
            ]) if en_edicion else ft.Row([
                ft.IconButton(icon=ft.icons.EDIT, tooltip="Editar", on_click=activar_edicion),
                ft.IconButton(icon=ft.icons.DELETE_OUTLINE, tooltip="Eliminar",
                              icon_color=ft.colors.RED_600, on_click=confirmar_eliminar)
            ])

            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(numero))),
                nombre_cell,
                sueldo_cell,
                ft.DataCell(acciones)
            ]))

        return ft.DataTable(
            expand=True,
            columns=[
                ft.DataColumn(
                    ft.Container(
                        ft.Text(f"Nómina {self._icono_orden('numero_nomina')}", size=12, weight="bold"),
                        width=100,
                        alignment=ft.alignment.center
                    ),
                    on_sort=lambda _: self._ordenar_por_columna("numero_nomina")
                ),
                ft.DataColumn(
                    ft.Container(
                        ft.Text("Nombre", size=12, weight="bold"),
                        width=300
                    )
                ),
                ft.DataColumn(
                    ft.Container(
                        ft.Text(f"Sueldo por Hora {self._icono_orden('sueldo_por_hora')}", size=12, weight="bold"),
                        width=150
                    ),
                    on_sort=lambda _: self._ordenar_por_columna("sueldo_por_hora")
                ),
                ft.DataColumn(
                    ft.Container(
                        ft.Text("Editar - Eliminar", size=12, weight="bold"),
                        width=160
                    )
                )
            ],
            rows=rows
        )

    def _crear_textfield_sueldo(self, valor_inicial):
        sueldo = ft.TextField(
            value=str(valor_inicial),
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
            text_size=12,
            content_padding=ft.padding.symmetric(horizontal=8, vertical=6)
        )

        def validar(_):
            try:
                v = float(sueldo.value)
                if v < 0:
                    raise ValueError
                sueldo.border_color = None
            except Exception:
                sueldo.border_color = ft.colors.RED
            self.page.update()

        sueldo.on_change = validar
        return sueldo

    def _crear_textfield_nombre(self, valor_inicial):
        nombre = ft.TextField(
            value=valor_inicial,
            expand=True,
            text_size=12,
            content_padding=ft.padding.symmetric(horizontal=8, vertical=6)
        )

        def validar(_):
            if len(nombre.value.strip()) >= 3 and all(c.isalpha() or c.isspace() for c in nombre.value.strip()):
                nombre.border_color = None
            else:
                nombre.border_color = ft.colors.RED
            self.page.update()

        nombre.on_change = validar
        return nombre

    def _insertar_fila_editable(self, e=None):
        if self.fila_nueva_en_proceso:
            ModalAlert.mostrar_info("Atención", "Ya hay un registro nuevo en proceso.")
            return

        self.fila_nueva_en_proceso = True

        nombre_input = ft.TextField(hint_text="Nombre completo", expand=True)
        sueldo_input = ft.TextField(hint_text="Sueldo por hora", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        nuevo_id = self.empleado_model.get_ultimo_numero_nomina() + 1

        def validar_nombre_input(_):
            valor = nombre_input.value.strip()
            nombre_input.border_color = None if len(valor) >= 3 and all(char.isalpha() or char.isspace() for char in valor) else ft.colors.RED
            self.page.update()

        def validar_sueldo_input(_):
            try:
                valor = float(sueldo_input.value)
                sueldo_input.border_color = None if valor >= 0 else ft.colors.RED
            except Exception:
                sueldo_input.border_color = ft.colors.RED
            self.page.update()

        nombre_input.on_change = validar_nombre_input
        sueldo_input.on_change = validar_sueldo_input

        def on_guardar(_):
            errores = []

            if not nombre_input.value or len(nombre_input.value.strip()) < 3 or not all(char.isalpha() or char.isspace() for char in nombre_input.value.strip()):
                nombre_input.border_color = ft.colors.RED
                errores.append("Nombre inválido (mínimo 3 letras)")
            try:
                sueldo = float(sueldo_input.value)
                if sueldo < 0:
                    raise ValueError
            except Exception:
                sueldo_input.border_color = ft.colors.RED
                errores.append("Sueldo inválido (número positivo)")

            self.page.update()

            if errores:
                self.window_snackbar.show_error("❌ " + " / ".join(errores))
                return

            resultado = self.empleado_model.add(
                numero_nomina=nuevo_id,
                nombre_completo=nombre_input.value.strip(),
                sueldo_por_hora=sueldo
            )

            self.fila_nueva_en_proceso = False

            if resultado["status"] == "success":
                self.window_snackbar.show_success(f"✅ Empleado agregado con ID {nuevo_id}")
                self._actualizar_tabla()
            else:
                self.window_snackbar.show_error(f"❌ {resultado['message']}")

        def on_cancelar(_):
            self.fila_nueva_en_proceso = False
            self.table.rows.pop()
            self.page.update()

        nueva_fila = ft.DataRow(cells=[
            ft.DataCell(ft.Text(str(nuevo_id))),
            ft.DataCell(ft.Container(nombre_input, width=300, expand=True)),
            ft.DataCell(ft.Container(sueldo_input, width=150, expand=True)),
            ft.DataCell(ft.Row([
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, on_click=on_guardar),
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600, on_click=on_cancelar)
            ]))
        ])

        self.table.rows.append(nueva_fila)
        self.page.update()

        SafeScrollInvoker.scroll_to_bottom(self.page)
        nombre_input.focus()
