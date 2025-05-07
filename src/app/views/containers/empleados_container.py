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
        self.table = self._build_table()

        self.orden_actual = {
            "numero_nomina": None,
            "estado": None,
            "sueldo_diario": None
        }

        self.controller = EmpleadosImportController(
            page=self.page,
            on_success=self._actualizar_tabla
        )

        self.expand = True

        self.content = ft.Column(
            expand=True,
            alignment=ft.MainAxisAlignment.START,
            scroll="auto",
            controls=[
                ft.Text("Empleados registrados", size=24, weight="bold"),
                ft.Divider(height=10),
                ft.Row(
                    controls=[
                        self.controller.get_import_button(),
                        ft.IconButton(
                            icon=ft.icons.FILE_DOWNLOAD,
                            tooltip="Exportar empleados a Excel",
                            on_click=self._exportar_empleados
                        )
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

    def _build_table(self) -> ft.DataTable:
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
        print(f"📄 Actualizando tabla con datos de: {path}")
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

    def _exportar_empleados(self, e):
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

        invoker = FileSaveInvoker()
        ruta_guardado = invoker.save_file("empleados.xlsx", file_type="excel")

        if ruta_guardado:
            df.to_excel(ruta_guardado, index=False)
            print(f"📤 Archivo exportado correctamente a: {ruta_guardado}")
        else:
            print("❌ Exportación cancelada por el usuario.")
