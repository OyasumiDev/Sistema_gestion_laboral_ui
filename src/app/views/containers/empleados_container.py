import flet as ft
from app.core.app_state import AppState
from app.models.employes_model import EmployesModel
from app.views.containers.modal_alert import ModalAlert
from app.views.containers.window_snackbar import WindowSnackbar
from app.core.invokers.safe_scroll_invoker import SafeScrollInvoker


class EmpleadosContainer(ft.Container):
    def __init__(self):
        super().__init__()

        self.page = AppState().page
        self.window_snackbar = WindowSnackbar(self.page)
        self.empleado_model = EmployesModel()
        self.fila_editando = None
        self.fila_nueva_en_proceso = False

        self.orden_actual = {
            "numero_nomina": None,
            "sueldo_por_hora": None
        }

        self.table = None
        self.expand = True

        self.table_container = ft.Container(
            expand=True,
            alignment=ft.alignment.top_center,
            content=ft.Column(
                controls=[],
                alignment=ft.MainAxisAlignment.START,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True
            )
        )

        self.scroll_column_ref = ft.Ref[ft.Column]()
        self.scroll_anchor = ft.Container(height=1, key="bottom-anchor")

        self.scroll_column = ft.Column(
            ref=self.scroll_column_ref,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.ALWAYS,
            expand=True,
            controls=[
                self.table_container,
                self.scroll_anchor
            ]
        )

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
                        controls=[
                            self._build_add_button()
                        ]
                    ),
                    ft.Divider(height=1),
                    ft.Container(
                        alignment=ft.alignment.top_center,
                        padding=ft.padding.only(top=10),
                        expand=True,
                        content=self.scroll_column
                    )
                ]
            )
        )

        self._actualizar_tabla()

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

        if columna in ("numero_nomina", "sueldo_por_hora"):
            empleados.sort(key=lambda x: float(x[columna]), reverse=not ascendente)
        else:
            empleados.sort(key=lambda x: x[columna], reverse=not ascendente)

        self._refrescar_tabla(empleados)

    def _refrescar_tabla(self, empleados: list):
        self.table = self._build_table(empleados)
        self.table_container.content.controls.clear()
        self.table_container.content.controls.append(self.table)
        self.page.update()

    def _actualizar_tabla(self, fila_en_edicion=None):
        empleados_result = self.empleado_model.get_all()
        empleados = empleados_result.get("data", [])
        self.fila_editando = fila_en_edicion
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
                except:
                    sueldo_cell.border_color = ft.colors.RED
                    errores.append("Sueldo inválido")

                self.page.update()

                if errores:
                    self.window_snackbar.show_error("❌ " + " / ".join(errores))
                    return

                # 🚀 Guardar directo sin confirmación modal
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

    def _build_add_button(self):
        return ft.GestureDetector(
            on_tap=lambda _: self._insertar_fila_editable(),
            content=ft.Container(
                padding=8,
                border_radius=12,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=ft.Row([
                    ft.Icon(name=ft.icons.PERSON_ADD_ALT_1_OUTLINED, size=20),
                    ft.Text("Agregar", size=11, weight="bold")
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=5)
            )
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
            except:
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
            except:
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
            except:
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
