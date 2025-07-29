import flet as ft
import pandas as pd
from app.core.app_state import AppState
from app.controllers.employes_import_controller import EmpleadosImportController
from app.models.employes_model import EmployesModel
from app.views.containers.modal_alert import ModalAlert
from app.core.invokers.file_save_invoker import FileSaveInvoker
from threading import Timer
from app.core.invokers.safe_scroll_invoker import SafeScrollInvoker
from app.views.containers.window_snackbar import WindowSnackbar


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

        self.controller = EmpleadosImportController(
            page=self.page,
            on_success=self._actualizar_tabla
        )

        self.save_invoker = FileSaveInvoker(
            page=self.page,
            file_name="empleados.xlsx",
            allowed_extensions=["xlsx"],
            on_save=self._guardar_empleados_en_excel
        )

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
                            self._build_import_button(),
                            self._build_export_button(),
                            self._build_add_button()  # ← ya está vinculado
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


    def _esta_cerca_del_final(self):
        try:
            scroll_col = self.scroll_column_ref.current
            if not scroll_col:
                return False
            return scroll_col.offset >= (scroll_col.scroll_height - scroll_col.height - 100)
        except:
            return False
        
        
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


    def _actualizar_tabla(self, path: str = "", fila_en_edicion=None):
        empleados_result = self.empleado_model.get_all()
        empleados = empleados_result.get("data", [])
        self.fila_editando = fila_en_edicion
        self._refrescar_tabla(empleados)

    def _build_table(self, empleados):
        rows = []
        for e in empleados:
            numero = e["numero_nomina"]
            en_edicion = self.fila_editando == numero

            sueldo_cell = (
                self._crear_textfield_sueldo(e["sueldo_por_hora"])
                if en_edicion else
                ft.Text(str(e["sueldo_por_hora"]))
            )

            def guardar_cambios(ev, id=numero, sueldo_cell=sueldo_cell):
                try:
                    sueldo = float(sueldo_cell.value)
                    if sueldo < 0:
                        raise ValueError
                    sueldo_cell.border_color = None
                    self.page.update()
                except:
                    sueldo_cell.border_color = ft.colors.RED
                    self.page.update()
                    self.window_snackbar.show_error("❌ El sueldo debe ser un número positivo.")
                    return

                def confirmar_guardado():
                    resultado = self.empleado_model.update(
                        numero_nomina=id,
                        sueldo_por_hora=sueldo
                    )
                    if resultado["status"] == "success":
                        self._actualizar_tabla()
                        self.window_snackbar.show_success("✅ Cambios guardados correctamente.")
                    else:
                        self.window_snackbar.show_error(f"❌ No se pudo guardar: {resultado['message']}")

                self.fila_editando = None
                ModalAlert(
                    title_text="¿Guardar cambios?",
                    message=f"¿Deseas aplicar los cambios al empleado {id}?",
                    on_confirm=confirmar_guardado
                ).mostrar()

            def activar_edicion(ev, id=numero):
                self._actualizar_tabla(fila_en_edicion=id)

            def confirmar_eliminar(ev, id=numero):
                def on_confirm():
                    resultado = self.empleado_model.delete_by_numero_nomina(id)
                    if resultado["status"] == "success":
                        self._actualizar_tabla("")
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
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, tooltip="Guardar", on_click=guardar_cambios),
                crear_boton_cancelar(numero)
            ]) if en_edicion else ft.Row([
                ft.IconButton(icon=ft.icons.EDIT, tooltip="Editar", on_click=activar_edicion),
                ft.IconButton(icon=ft.icons.DELETE_OUTLINE, tooltip="Eliminar", icon_color=ft.colors.RED_600, on_click=confirmar_eliminar)
            ])

            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(numero))),
                ft.DataCell(ft.Text(e["nombre_completo"])),
                ft.DataCell(sueldo_cell),
                ft.DataCell(acciones)
            ]))

        return ft.DataTable(
            expand=True,
            columns=[
                ft.DataColumn(ft.Text(f"Nómina {self._icono_orden('numero_nomina')}"), on_sort=lambda _: self._ordenar_por_columna("numero_nomina")),
                ft.DataColumn(ft.Text("Nombre")),
                ft.DataColumn(ft.Text(f"Sueldo por Hora {self._icono_orden('sueldo_por_hora')}"), on_sort=lambda _: self._ordenar_por_columna("sueldo_por_hora")),
                ft.DataColumn(ft.Text("Editar - Eliminar"))
            ],
            rows=rows
        )



    def _build_import_button(self):
        return ft.GestureDetector(
            on_tap=lambda _: self.controller.file_invoker.open(),
            content=ft.Container(
                padding=8,
                border_radius=12,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=ft.Row([
                    ft.Image(src="assets/buttons/import-button.png", width=20, height=20),
                    ft.Text("Importar", size=11, weight="bold")
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=5)
            )
        )

    def _build_export_button(self):
        return ft.GestureDetector(
            on_tap=lambda _: self.save_invoker.open_save(),
            content=ft.Container(
                padding=8,
                border_radius=12,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=ft.Row([
                    ft.Image(src="assets/buttons/export-button.png", width=20, height=20),
                    ft.Text("Exportar", size=11, weight="bold")
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=5)
            )
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
        sueldo = ft.TextField(value=str(valor_inicial), keyboard_type=ft.KeyboardType.NUMBER)

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


    def _insertar_fila_editable(self, e=None):
        if self.fila_nueva_en_proceso:
            ModalAlert.mostrar_info("Atención", "Ya hay un registro nuevo en proceso.")
            return

        self.fila_nueva_en_proceso = True

        nombre_input = ft.TextField(hint_text="Nombre completo")
        sueldo_input = ft.TextField(hint_text="Sueldo por hora", keyboard_type=ft.KeyboardType.NUMBER)
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
            ft.DataCell(nombre_input),
            ft.DataCell(sueldo_input),
            ft.DataCell(ft.Row([
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, on_click=on_guardar),
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600, on_click=on_cancelar)
            ]))
        ])

        self.table.rows.append(nueva_fila)
        self.page.update()

        SafeScrollInvoker.scroll_to_bottom(self.page)
        nombre_input.focus()


    def _guardar_empleados_en_excel(self, path: str):
        try:
            empleados_result = self.empleado_model.get_all()
            empleados = empleados_result.get("data", [])

            if not empleados:
                ModalAlert.mostrar_info("Atención", "No hay empleados para exportar.")
                return

            df = pd.DataFrame(empleados)
            columnas_ordenadas = [
                "numero_nomina",
                "nombre_completo",
                "sueldo_por_hora"
            ]
            df = df[columnas_ordenadas]
            df.to_excel(path, index=False)

            ModalAlert.mostrar_info("Exportación", f"Archivo guardado en: {path}")
        except Exception as ex:
            ModalAlert.mostrar_info("Error de exportación", f"No se pudo guardar el archivo: {ex}")

