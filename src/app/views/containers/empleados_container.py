import flet as ft
import pandas as pd
from app.core.app_state import AppState
from app.controllers.employes_import_controller import EmpleadosImportController
from app.models.employes_model import EmployesModel
from app.views.containers.modal_alert import ModalAlert
from app.core.invokers.file_save_invoker import FileSaveInvoker


class EmpleadosContainer(ft.Container):
    def __init__(self):
        super().__init__()

        self.page = AppState().page
        self.empleado_model = EmployesModel()
        self.fila_editando = None

        self.orden_actual = {
            "numero_nomina": None,
            "estado": None,
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
                alignment=ft.MainAxisAlignment.START,  # Alinea hacia arriba
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,  # Centra horizontalmente
                expand=True
            )
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
                            self._build_add_button()
                        ]
                    ),
                    ft.Divider(height=1),
                    ft.Container(
                        alignment=ft.alignment.top_center,
                        padding=ft.padding.only(top=10),
                        expand=True,
                        content=ft.Column(
                            alignment=ft.MainAxisAlignment.START,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            scroll=ft.ScrollMode.ALWAYS,
                            controls=[self.table_container]
                        )
                    )
                ]
            )
        )




        self._actualizar_tabla("")

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

            estado_cell = (
                ft.Dropdown(value=e["estado"], options=[
                    ft.dropdown.Option("activo"),
                    ft.dropdown.Option("inactivo")
                ]) if en_edicion else ft.Text(e["estado"])
            )

            tipo_cell = (
                ft.Dropdown(value=e["tipo_trabajador"], options=[
                    ft.dropdown.Option("taller"),
                    ft.dropdown.Option("externo"),
                    ft.dropdown.Option("no definido")
                ]) if en_edicion else ft.Text(e["tipo_trabajador"])
            )

            if en_edicion:
                def crear_sueldo_cell(valor_inicial):
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

                sueldo_cell = crear_sueldo_cell(e["sueldo_por_hora"])
            else:
                sueldo_cell = ft.Text(str(e["sueldo_por_hora"]))

            def guardar_cambios(ev, id=numero, estado_cell=estado_cell, tipo_cell=tipo_cell, sueldo_cell=sueldo_cell):
                try:
                    sueldo = float(sueldo_cell.value)
                    if sueldo < 0:
                        raise ValueError
                    sueldo_cell.border_color = None
                    self.page.update()
                except:
                    sueldo_cell.border_color = ft.colors.RED
                    self.page.update()
                    ModalAlert.mostrar_info("Error", "El sueldo debe ser un número positivo.")
                    return

                def confirmar_guardado():
                    resultado = self.empleado_model.update(
                        id,
                        estado=estado_cell.value,
                        tipo_trabajador=tipo_cell.value,
                        sueldo_por_hora=sueldo
                    )
                    if resultado["status"] == "success":
                        ModalAlert.mostrar_info("Éxito", "Cambios guardados correctamente")
                        self._actualizar_tabla()
                    else:
                        ModalAlert.mostrar_info("Error", f"No se pudo guardar: {resultado['message']}")

                self.fila_editando = None
                ModalAlert(
                    title_text="¿Guardar cambios?",
                    message=f"¿Deseas aplicar los cambios al empleado {id}?",
                    on_confirm=confirmar_guardado
                ).mostrar()

            def activar_edicion(ev, id=numero):
                print(f"✏️ Editando fila {id}")
                self._actualizar_tabla(fila_en_edicion=id)

            def confirmar_eliminar(ev, id=numero):
                def on_confirm():
                    resultado = self.empleado_model.delete_by_numero_nomina(id)
                    if resultado["status"] == "success":
                        ModalAlert.mostrar_info("Eliminado", "Empleado eliminado correctamente")
                        self._actualizar_tabla("")
                    else:
                        ModalAlert.mostrar_info("Error", f"No se pudo eliminar: {resultado['message']}")

                ModalAlert(
                    title_text="¿Eliminar empleado?",
                    message=f"Esta acción no se puede deshacer. ID: {id}",
                    on_confirm=on_confirm
                ).mostrar()

            def crear_boton_cancelar(id_cancelar):
                def cancelar(ev):
                    self.fila_editando = None
                    ModalAlert.mostrar_info("Edición cancelada", f"Se canceló la edición del empleado {id_cancelar}")
                    self._actualizar_tabla()
                return ft.IconButton(
                    icon=ft.icons.CLOSE,
                    icon_color=ft.colors.RED_600,
                    tooltip="Cancelar",
                    on_click=cancelar
                )

            if en_edicion:
                acciones = ft.Row([
                    ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, tooltip="Guardar", on_click=guardar_cambios),
                    crear_boton_cancelar(numero)
                ])
            else:
                acciones = ft.Row([
                    ft.IconButton(icon=ft.icons.EDIT, tooltip="Editar", on_click=activar_edicion),
                    ft.IconButton(icon=ft.icons.DELETE_OUTLINE, tooltip="Eliminar", icon_color=ft.colors.RED_600, on_click=confirmar_eliminar)
                ])

            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(numero))),
                ft.DataCell(ft.Text(e["nombre_completo"])),
                ft.DataCell(estado_cell),
                ft.DataCell(tipo_cell),
                ft.DataCell(sueldo_cell),
                ft.DataCell(acciones)
            ]))

        return ft.DataTable(
            expand=True,
            columns=[
                ft.DataColumn(ft.Text(f"Nómina {self._icono_orden('numero_nomina')}"), on_sort=lambda _: self._ordenar_por_columna("numero_nomina")),
                ft.DataColumn(ft.Text("Nombre")),
                ft.DataColumn(ft.Text(f"Estado {self._icono_orden('estado')}"), on_sort=lambda _: self._ordenar_por_columna("estado")),
                ft.DataColumn(ft.Text("Tipo Trabajador")),
                ft.DataColumn(ft.Text(f"Sueldo por Hora {self._icono_orden('sueldo_por_hora')}"), on_sort=lambda _: self._ordenar_por_columna("sueldo_por_hora")),
                ft.DataColumn(ft.Text("Eliminar-Editar"))
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
            on_tap=self._insertar_fila_editable,
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

    def _insertar_fila_editable(self, e=None):
        nombre_input = ft.TextField(hint_text="Nombre completo")
        estado_dropdown = ft.Dropdown(options=[ft.dropdown.Option("activo"), ft.dropdown.Option("inactivo")])
        tipo_dropdown = ft.Dropdown(options=[ft.dropdown.Option("taller"), ft.dropdown.Option("externo"), ft.dropdown.Option("no definido")])
        sueldo_input = ft.TextField(hint_text="Sueldo diario", keyboard_type=ft.KeyboardType.NUMBER)

        nuevo_id = self.empleado_model.get_ultimo_numero_nomina() + 1

        def validar_nombre_input(_):
            valor = nombre_input.value.strip()
            if len(valor) < 3 or not all(char.isalpha() or char.isspace() for char in valor):
                nombre_input.border_color = ft.colors.RED
            else:
                nombre_input.border_color = None
            self.page.update()

        def validar_sueldo_input(_):
            try:
                valor = float(sueldo_input.value)
                if valor < 0:
                    raise ValueError
                sueldo_input.border_color = None
            except:
                sueldo_input.border_color = ft.colors.RED
            self.page.update()

        nombre_input.on_change = validar_nombre_input
        sueldo_input.on_change = validar_sueldo_input

        def on_guardar(_):
            try:
                if not nombre_input.value or not estado_dropdown.value or not tipo_dropdown.value or not sueldo_input.value:
                    raise ValueError("Todos los campos son obligatorios")

                nombre = nombre_input.value.strip()
                if len(nombre) < 3 or not all(char.isalpha() or char.isspace() for char in nombre):
                    nombre_input.border_color = ft.colors.RED
                    self.page.update()
                    raise ValueError("Nombre inválido")

                sueldo = float(sueldo_input.value)
                if sueldo < 0:
                    sueldo_input.border_color = ft.colors.RED
                    self.page.update()
                    raise ValueError("Sueldo negativo")

                resultado = self.empleado_model.add(
                    numero_nomina=nuevo_id,
                    nombre_completo=nombre,
                    estado=estado_dropdown.value,
                    tipo_trabajador=tipo_dropdown.value,
                    sueldo_por_hora=sueldo
                )

                if resultado["status"] == "success":
                    ModalAlert.mostrar_info("Éxito", f"Empleado agregado con ID {nuevo_id}")
                    self._actualizar_tabla("")
                else:
                    ModalAlert.mostrar_info("Error", resultado["message"])

            except Exception as ex:
                ModalAlert.mostrar_info("Error", f"No se pudo agregar el empleado: {ex}")

        def on_cancelar(_):
            self.table.rows.pop()
            self.page.update()

        nueva_fila = ft.DataRow(cells=[
            ft.DataCell(ft.Text(str(nuevo_id))),
            ft.DataCell(nombre_input),
            ft.DataCell(estado_dropdown),
            ft.DataCell(tipo_dropdown),
            ft.DataCell(sueldo_input),
            ft.DataCell(ft.Row([
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, on_click=on_guardar),
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600, on_click=on_cancelar)
            ]))
        ])

        self.table.rows.append(nueva_fila)
        self.page.update()


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
                "estado",
                "tipo_trabajador",
                "sueldo_por_hora"
            ]
            df = df[columnas_ordenadas]
            df.to_excel(path, index=False)

            ModalAlert.mostrar_info("Exportación", f"Archivo guardado en: {path}")
        except Exception as ex:
            ModalAlert.mostrar_info("Error de exportación", f"No se pudo guardar el archivo: {ex}")
