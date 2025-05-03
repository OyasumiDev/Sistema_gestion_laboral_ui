import flet as ft
from app.core.app_state import AppState
from app.models.user_model import UserModel

class UsuariosContainer(ft.Container):
    def __init__(self):
        super().__init__()
        print("✅ UsuariosContainer inicializado")  # Depuración

        self.expand = True
        self.page = AppState().page
        self.user_model = UserModel()

        self.table = self._build_table()
        self.content = self._build_content()

        self.controls = [self.content]

    def _build_content(self) -> ft.Column:
        return ft.Column(
            expand=True,
            scroll="auto",
            controls=[
                ft.Text("Usuarios registrados", size=24, weight="bold"),
                ft.Divider(height=10),
                self.table
            ]
        )

    def _build_table(self) -> ft.DataTable:
        print("🧪 Ejecutando _build_table()")  # Depuración
        usuarios_result = self.user_model.get_users()
        usuarios = usuarios_result.get("data", [])

        rows = []
        if usuarios:
            for u in usuarios:
                print(f"📄 Usuario: {u}")  # Depuración
                rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(u["id"]))),
                        ft.DataCell(ft.Text(u["username"])),
                        ft.DataCell(ft.Text(u["role"])),
                        ft.DataCell(ft.Text(str(u["fecha_creacion"]))),
                        ft.DataCell(ft.Text(str(u["fecha_modificacion"])))
                    ])
                )
        else:
            print("⚠️ No hay usuarios registrados")

        return ft.DataTable(
            expand=True,
            columns=[
                ft.DataColumn(label=ft.Text("ID")),
                ft.DataColumn(label=ft.Text("Nombre de Usuario")),
                ft.DataColumn(label=ft.Text("Rol")),
                ft.DataColumn(label=ft.Text("Creado")),
                ft.DataColumn(label=ft.Text("Modificado"))
            ],
            rows=rows
        )
