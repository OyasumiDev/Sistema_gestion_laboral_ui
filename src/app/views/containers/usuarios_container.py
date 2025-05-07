import flet as ft
import pandas as pd
from datetime import datetime
from app.core.app_state import AppState
from app.models.user_model import UserModel
from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.core.invokers.file_open_invoker import FileOpenInvoker
from app.views.containers.messages import mostrar_mensaje
from app.views.containers.modal_alert import ModalAlert

class UsuariosContainer(ft.Container):
    def __init__(self):
        super().__init__()

        self.expand = True
        self.page = AppState().page
        self.user_model = UserModel()

        user_data = self.page.client_storage.get("app.user")
        if not user_data or user_data.get("role") != "root":
            self.content = ft.Text("❌ Acceso denegado. Solo el usuario root puede ver esta sección.", color=ft.colors.RED)
            return

        self.save_invoker = FileSaveInvoker(
            page=self.page,
            on_save=self._exportar_usuarios,
            save_dialog_title="Exportar usuarios",
            file_name="usuarios_exportados.xlsx",
            allowed_extensions=["xlsx"]
        )

        self.file_invoker = FileOpenInvoker(
            page=self.page,
            on_select=self._importar_usuarios,
            dialog_title="Importar usuarios",
            allowed_extensions=["xlsx"]
        )

        self.table = self._build_table()
        self.content = self._build_content()
        self.controls = [self.content]

    def _build_content(self) -> ft.Column:
        return ft.Column(
            expand=True,
            scroll="auto",
            controls=[
                ft.Text("Usuarios registrados", size=24, weight="bold"),
                ft.Row([
                    ft.ElevatedButton("Agregar Usuario", on_click=self._agregar_usuario),
                    ft.ElevatedButton("Exportar", on_click=lambda _: self.save_invoker.open_save()),
                    ft.ElevatedButton("Importar", on_click=lambda _: self.file_invoker.open())
                ], spacing=10),
                ft.Divider(height=10),
                self.table
            ]
        )

    def _build_table(self) -> ft.DataTable:
        usuarios_result = self.user_model.get_users()
        usuarios = usuarios_result.get("data", [])

        rows = []
        if usuarios:
            for u in usuarios:
                try:
                    user_id = u["id"]
                    username = u["username"]
                    role = u["role"]
                    creado = u.get("fecha_creacion", "-")
                    modificado = u.get("fecha_modificacion", "-")

                    pw_text = ft.Text("●●●●●●●●", italic=True, color=ft.colors.SECONDARY)
                    toggle_btn = ft.IconButton(
                        icon=ft.icons.REMOVE_RED_EYE,
                        tooltip="Ver contraseña",
                        on_click=lambda e, uid=user_id, label=pw_text: self._toggle_password(uid, label, e.control)
                    )


                    pw_field = ft.Row([pw_text, toggle_btn])

                    rows.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(str(user_id))),
                            ft.DataCell(ft.Text(username)),
                            ft.DataCell(ft.Text(role)),
                            ft.DataCell(pw_field),
                            ft.DataCell(ft.Text(str(creado))),
                            ft.DataCell(ft.Text(str(modificado))),
                            ft.DataCell(ft.IconButton(
                                icon=ft.icons.DELETE_FOREVER,
                                icon_color=ft.colors.RED,
                                on_click=lambda e, uid=user_id: self._confirmar_eliminar(uid)
                            ))
                        ])
                    )
                except KeyError as e:
                    print(f"❌ Error al construir fila de usuario: clave faltante {e}")
        else:
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text("Sin registros"))
            ] + [ft.DataCell(ft.Text("-")) for _ in range(6)]))

        return ft.DataTable(
            expand=True,
            columns=[
                ft.DataColumn(label=ft.Text("ID")),
                ft.DataColumn(label=ft.Text("Nombre de Usuario")),
                ft.DataColumn(label=ft.Text("Rol")),
                ft.DataColumn(label=ft.Text("Contraseña")),
                ft.DataColumn(label=ft.Text("Creado")),
                ft.DataColumn(label=ft.Text("Modificado")),
                ft.DataColumn(label=ft.Text("Eliminar"))
            ],
            rows=rows
        )

    def _toggle_password(self, user_id, label: ft.Text, button: ft.IconButton):
        result = self.user_model.get_password(user_id)
        if result["status"] == "success":
            if label.value == "●●●●●●●●":
                label.value = result["data"]
                button.icon = ft.icons.HIDE_SOURCE
                button.tooltip = "Ocultar contraseña"
            else:
                label.value = "●●●●●●●●"
                button.icon = ft.icons.REMOVE_RED_EYE
                button.tooltip = "Ver contraseña"
            self.page.update()
        else:
            mostrar_mensaje(self.page, "Error", result["message"])

    def _confirmar_eliminar(self, user_id: int):
        alerta = ModalAlert(
            title_text="Eliminar usuario",
            message=f"¿Estás seguro de que deseas eliminar el usuario con ID {user_id}?",
            on_confirm=lambda: self._eliminar_usuario(user_id)
        )
        alerta.mostrar()

    def _eliminar_usuario(self, user_id: int):
        print(f"🗑️ Usuario a eliminar: {user_id}")
        resultado = self.user_model.delete_by_id(user_id)
        if resultado["status"] == "success":
            self.page.snack_bar = ft.SnackBar(ft.Text(f"✅ Usuario con ID {user_id} eliminado."))
        else:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"❌ {resultado['message']}"))
        self.page.snack_bar.open = True
        self.page.update()
        self._recargar_tabla()

    def _recargar_tabla(self):
        self.table.rows.clear()
        self.table.rows.extend(self._build_table().rows)
        self.table.update()

    def _agregar_usuario(self, e):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        id_nuevo = self.user_model.get_last_id() + 1
        username_field = ft.TextField(hint_text="Usuario")
        password_field = ft.TextField(hint_text="Contraseña", password=True)
        role_dropdown = ft.Dropdown(options=[ft.dropdown.Option("user"), ft.dropdown.Option("root")])

        def confirmar(_: ft.ControlEvent):
            username = username_field.value.strip()
            password = password_field.value.strip()
            role = role_dropdown.value
            if username and password:
                self.user_model.add(username, password, role)
                self._recargar_tabla()
            else:
                print("❌ Campos incompletos")

        row = ft.DataRow(cells=[
            ft.DataCell(ft.Text(str(id_nuevo))),
            ft.DataCell(username_field),
            ft.DataCell(role_dropdown),
            ft.DataCell(password_field),
            ft.DataCell(ft.Text(now)),
            ft.DataCell(ft.Text(now)),
            ft.DataCell(ft.Row([
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN, on_click=confirmar),
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED, on_click=lambda _: self._cancelar_agregado(row))
            ]))
        ])
        self.table.rows.append(row)
        self.table.update()

    def _cancelar_agregado(self, row):
        if row in self.table.rows:
            self.table.rows.remove(row)
            self.table.update()

    def _exportar_usuarios(self, path: str):
        try:
            result = self.user_model.get_users()
            data = result.get("data", [])
            df = pd.DataFrame(data, columns=["id", "username", "role", "fecha_creacion", "fecha_modificacion"])
            df.to_excel(path, index=False)
            print(f"✅ Usuarios exportados a: {path}")
        except Exception as e:
            print(f"❌ Error al exportar usuarios: {e}")

    def _importar_usuarios(self, path: str):
        try:
            df = pd.read_excel(path)
            print(f"📥 Usuarios importados desde: {path}\n{df}")
            for _, row in df.iterrows():
                username = row.get("username")
                role = row.get("role")
                password = row.get("password", "123456")
                if username:
                    self.user_model.add(username, password, role)
            self._recargar_tabla()
        except Exception as e:
            print(f"❌ Error al importar usuarios: {e}")
