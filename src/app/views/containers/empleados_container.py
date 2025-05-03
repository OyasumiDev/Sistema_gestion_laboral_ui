import flet as ft
from app.core.app_state import AppState
from app.controllers.employes_import_controller import EmpleadosImportController
from app.models.employes_model import EmployesModel

class EmpleadosContainer(ft.Container):
    def __init__(self):
        super().__init__()

        self.page = AppState().page
        self.empleado_model = EmployesModel()
        self.table = self._build_table()

        self.controller = EmpleadosImportController(
            page=self.page,
            on_success=self._actualizar_tabla
        )

        self.expand = True  # que use todo el ancho del contenedor principal

        self.content = ft.Column(
            expand=True,
            alignment=ft.MainAxisAlignment.START,
            scroll="auto",
            controls=[
                ft.Text("Empleados registrados", size=24, weight="bold"),
                ft.Divider(height=10),
                self.controller.get_import_button(),
                ft.Divider(height=10),
                ft.Container(
                    expand=True,
                    alignment=ft.alignment.top_center,
                    content=ft.Row(
                        controls=[
                            self.table
                        ],
                        expand=True,
                        alignment=ft.MainAxisAlignment.CENTER
                    )
                )
            ]
        )

    def _build_table(self) -> ft.DataTable:
        empleados_result = self.empleado_model.get_all()
        empleados = empleados_result.get("data", [])

        return ft.DataTable(
            expand=True,
            columns=[
                ft.DataColumn(ft.Text("Nómina")),
                ft.DataColumn(ft.Text("Nombre")),
                ft.DataColumn(ft.Text("Estado")),
                ft.DataColumn(ft.Text("Tipo Trabajador")),
                ft.DataColumn(ft.Text("Sueldo Diario"))
            ],
            rows=[
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(e["numero_nomina"]))),
                    ft.DataCell(ft.Text(e["nombre_completo"])),
                    ft.DataCell(ft.Text(e["estado"])),
                    ft.DataCell(ft.Text(e["tipo_trabajador"])),
                    ft.DataCell(ft.Text(str(e["sueldo_diario"])))
                ])
                for e in empleados
            ]
        )

    def _actualizar_tabla(self, path: str):
        print(f"📄 Actualizando tabla con datos de: {path}")
        empleados_result = self.empleado_model.get_all()
        empleados = empleados_result.get("data", [])

        self.table.rows.clear()
        for e in empleados:
            self.table.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(e["numero_nomina"]))),
                ft.DataCell(ft.Text(e["nombre_completo"])),
                ft.DataCell(ft.Text(e["estado"])),
                ft.DataCell(ft.Text(e["tipo_trabajador"])),
                ft.DataCell(ft.Text(str(e["sueldo_diario"])))
            ]))
        self.page.update()
