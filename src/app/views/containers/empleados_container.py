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

        self.orden_actual = {
            "numero_nomina": None,
            "estado": None,
            "sueldo_diario": None
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

        self.table = self._build_table()

        self.expand = True

        self.content = ft.Column(
            expand=True,
            alignment=ft.MainAxisAlignment.START,
            scroll="auto",
            controls=[
                ft.Text("Empleados registrados", size=24, weight="bold"),
                ft.Divider(height=10),
                ft.Row(
                    spacing=10,
                    controls=[
                        self._build_import_button(),
                        self._build_export_button(),
                        self._build_add_button()
                    ]
                ),
                ft.Divider(height=10),
                ft.Container(
                    expand=True,
                    alignment=ft.alignment.top_center,
                    content=ft.Row(
                        controls=[self.table],
                        expand=True,
                        alignment=ft.MainAxisAlignment.CENTER
                    )
                )
            ]
        )

    def _build_table(self):
        empleados_result = self.empleado_model.get_all()
        empleados = empleados_result.get("data", [])

        icono_orden = lambda col: (
            ft.icons.ARROW_DROP_UP if self.orden_actual.get(col) == "asc"
            else ft.icons.ARROW_DROP_DOWN if self.orden_actual.get(col) == "desc"
            else ft.icons.UNFOLD_MORE
        )

        return ft.DataTable(
            expand=True,
            columns=[
                ft.DataColumn(
                    ft.TextButton(
                        text="Nómina",
                        icon=icono_orden("numero_nomina"),
                        on_click=lambda _: self._ordenar_por_columna("numero_nomina")
                    )
                ),
                ft.DataColumn(ft.Text("Nombre")),
                ft.DataColumn(
                    ft.TextButton(
                        text="Estado",
                        icon=icono_orden("estado"),
                        on_click=lambda _: self._ordenar_por_columna("estado")
                    )
                ),
                ft.DataColumn(ft.Text("Tipo Trabajador")),
                ft.DataColumn(
                    ft.TextButton(
                        text="Sueldo Diario",
                        icon=icono_orden("sueldo_diario"),
                        on_click=lambda _: self._ordenar_por_columna("sueldo_diario")
                    )
                ),
                ft.DataColumn(ft.Text("Eliminar"))
            ],
            rows=[
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(e["numero_nomina"]))),
                    ft.DataCell(ft.Text(e["nombre_completo"])),
                    ft.DataCell(ft.Text(e["estado"])),
                    ft.DataCell(ft.Text(e["tipo_trabajador"])),
                    ft.DataCell(ft.Text(str(e["sueldo_diario"]))),
                    ft.DataCell(ft.IconButton(
                        icon=ft.icons.DELETE_OUTLINE,
                        tooltip="Eliminar empleado",
                        icon_color=ft.colors.RED_600,
                        on_click=lambda _, id=e["numero_nomina"]: self._confirmar_eliminacion_empleado(id)
                    ))
                ])
                for e in empleados
            ]
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

        def on_guardar(_):
            try:
                if not nombre_input.value or not estado_dropdown.value or not tipo_dropdown.value or not sueldo_input.value:
                    raise ValueError("Todos los campos son obligatorios")

                sueldo = float(sueldo_input.value)

                resultado = self.empleado_model.add(
                    numero_nomina=nuevo_id,
                    nombre_completo=nombre_input.value.strip(),
                    estado=estado_dropdown.value,
                    tipo_trabajador=tipo_dropdown.value,
                    sueldo_diario=sueldo
                )

                if resultado["status"] == "success":
                    print(f"✅ Nuevo empleado agregado con ID {nuevo_id}")
                    self._actualizar_tabla("")
                else:
                    print("❌", resultado["message"])
            except Exception as ex:
                print(f"⚠️ Error al agregar empleado: {ex}")

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

        
    def _ordenar_por_columna(self, columna: str):
        ascendente = self.orden_actual.get(columna) != "asc"
        self.orden_actual = {k: None for k in self.orden_actual}
        self.orden_actual[columna] = "asc" if ascendente else "desc"

        empleados_result = self.empleado_model.get_all()
        empleados = empleados_result.get("data", [])

        if columna in ("numero_nomina", "sueldo_diario"):
            empleados.sort(key=lambda x: float(x[columna]), reverse=not ascendente)
        else:
            empleados.sort(key=lambda x: x[columna], reverse=not ascendente)

        self._refrescar_tabla(empleados)

    def _refrescar_tabla(self, empleados: list):
        self.table.rows.clear()
        for e in empleados:
            self.table.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(e["numero_nomina"]))),
                ft.DataCell(ft.Text(e["nombre_completo"])),
                ft.DataCell(ft.Text(e["estado"])),
                ft.DataCell(ft.Text(e["tipo_trabajador"])),
                ft.DataCell(ft.Text(str(e["sueldo_diario"]))),
                ft.DataCell(ft.IconButton(
                    icon=ft.icons.DELETE_OUTLINE,
                    tooltip="Eliminar empleado",
                    icon_color=ft.colors.RED_600,
                    on_click=lambda _, id=e["numero_nomina"]: self._confirmar_eliminacion_empleado(id)
                ))
            ]))
        self.page.update()

    def _actualizar_tabla(self, path: str):
        empleados_result = self.empleado_model.get_all()
        empleados = empleados_result.get("data", [])
        self._refrescar_tabla(empleados)

    def _confirmar_eliminacion_empleado(self, numero_nomina: int):
        def on_confirm():
            resultado = self.empleado_model.delete_by_numero_nomina(numero_nomina)
            if resultado["status"] == "success":
                print("🗑️ Empleado eliminado correctamente")
                self._actualizar_tabla("")
            else:
                print("❌ Error al eliminar:", resultado["message"])

        alerta = ModalAlert(
            title_text="Confirmar eliminación",
            message=f"¿Estás seguro de que deseas eliminar al empleado {numero_nomina}?",
            on_confirm=on_confirm
        )
        alerta.mostrar()

    def _guardar_empleados_en_excel(self, path: str):
        try:
            empleados_result = self.empleado_model.get_all()
            empleados = empleados_result.get("data", [])

            if not empleados:
                print("⚠️ No hay empleados para exportar.")
                return

            df = pd.DataFrame(empleados)
            columnas_ordenadas = [
                "numero_nomina",
                "nombre_completo",
                "estado",
                "tipo_trabajador",
                "sueldo_diario"
            ]
            df = df[columnas_ordenadas]
            df.to_excel(path, index=False)

            print(f"📄 Empleados exportados correctamente a: {path}")
        except Exception as ex:
            print(f"❌ Error al exportar empleados: {ex}")

    def _mostrar_dialogo_agregar(self, e=None):
        print("🟡 Se abrió el diálogo para agregar empleado")

        nombre_input = ft.TextField(label="Nombre completo", width=400)
        estado_dropdown = ft.Dropdown(
            label="Estado",
            options=[ft.dropdown.Option("activo"), ft.dropdown.Option("inactivo")],
            width=200
        )
        tipo_dropdown = ft.Dropdown(
            label="Tipo de trabajador",
            options=[
                ft.dropdown.Option("taller"),
                ft.dropdown.Option("externo"),
                ft.dropdown.Option("no definido")
            ],
            width=200
        )
        sueldo_input = ft.TextField(label="Sueldo diario", width=200, keyboard_type=ft.KeyboardType.NUMBER)

        def on_agregar(e=None):
            print("🟢 Botón 'Agregar' presionado")
            self._agregar_empleado(
                dialog,
                nombre_input.value,
                estado_dropdown.value,
                tipo_dropdown.value,
                sueldo_input.value
            )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Agregar nuevo empleado", weight="bold"),
            content=ft.Column(controls=[
                nombre_input,
                ft.Row([estado_dropdown, tipo_dropdown]),
                sueldo_input
            ], tight=True),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self._cerrar_dialogo(dialog)),
                ft.ElevatedButton("Agregar", on_click=on_agregar)
            ]
        )

        dialog.open = True
        self.page.dialog = dialog
        self.page.update()

    def _cerrar_dialogo(self, dialog):
        dialog.open = False
        self.page.update()

    def _agregar_empleado(self, dialog, nombre, estado, tipo, sueldo):
        try:
            if not nombre or not estado or not tipo or not sueldo:
                raise ValueError("Todos los campos son obligatorios")

            sueldo = float(sueldo)
            ultimo_id = self.empleado_model.get_ultimo_numero_nomina()
            nuevo_id = ultimo_id + 1

            resultado = self.empleado_model.add(
                numero_nomina=nuevo_id,
                nombre_completo=nombre.strip(),
                estado=estado,
                tipo_trabajador=tipo,
                sueldo_diario=sueldo
            )

            if resultado["status"] == "success":
                print(f"✅ Nuevo empleado agregado con ID {nuevo_id}")
                self._actualizar_tabla("")
            else:
                print("❌", resultado["message"])

        except Exception as ex:
            print(f"⚠️ Error al agregar empleado: {ex}")
        finally:
            dialog.open = False
            self.page.update()
