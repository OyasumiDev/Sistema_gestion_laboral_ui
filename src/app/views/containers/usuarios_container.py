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

        self.data_table = None  # se asignará dentro de _build_table()
        self.table = self._build_table()  # Container con la tabla centrada
        self.content = self._build_content()
        self.controls = [self.content]


    def _build_content(self) -> ft.Column:
        usuarios = self.user_model.get_users()["data"]

        estadisticas = ft.Row([
            ft.Card(
                content=ft.Container(
                    padding=10,
                    content=ft.Column([
                        ft.Text("Total de usuarios", weight="bold", size=13),
                        ft.Text(str(len(usuarios)), size=16)
                    ])
                )
            ),
            ft.Card(
                content=ft.Container(
                    padding=10,
                    content=ft.Column([
                        ft.Text("Usuarios root", weight="bold", size=13),
                        ft.Text(str(sum(1 for u in usuarios if u["role"] == "root")), size=16)
                    ])
                )
            ),
            ft.Card(
                content=ft.Container(
                    padding=10,
                    content=ft.Column([
                        ft.Text("Última modificación", weight="bold", size=13),
                        ft.Text(
                            max([u.get("fecha_modificacion", "N/A") for u in usuarios]),
                            size=14
                        )
                    ])
                )
            )
        ], spacing=20)

        return ft.Column(
            expand=True,
            scroll="auto",
            controls=[
                ft.Text("Usuarios registrados", size=24, weight="bold"),
                ft.Row([
                    ft.ElevatedButton(
                        content=ft.Row([
                            ft.Icon(name=ft.icons.PERSON_ADD, size=18),
                            ft.Text("Agregar Usuario", size=12, weight="bold")
                        ], spacing=5, alignment=ft.MainAxisAlignment.CENTER),
                        on_click=self._agregar_usuario
                    ),
                    ft.ElevatedButton(
                        content=ft.Row([
                            ft.Icon(name=ft.icons.FILE_DOWNLOAD, size=18),
                            ft.Text("Exportar", size=12, weight="bold")
                        ], spacing=5, alignment=ft.MainAxisAlignment.CENTER),
                        on_click=lambda _: self.save_invoker.open_save()
                    ),
                    ft.ElevatedButton(
                        content=ft.Row([
                            ft.Icon(name=ft.icons.FILE_UPLOAD, size=18),
                            ft.Text("Importar", size=12, weight="bold")
                        ], spacing=5, alignment=ft.MainAxisAlignment.CENTER),
                        on_click=lambda _: self.file_invoker.open()
                    )
                ], spacing=20),
                ft.Divider(),
                estadisticas,
                ft.Divider(height=10),
                self.table
            ]
        )

    def _build_table(self) -> ft.Container:
        usuarios_result = self.user_model.get_users()
        usuarios = usuarios_result.get("data", [])

        rows = []

        def contar_roots():
            return sum(1 for u in usuarios if u["role"] == "root")

        if usuarios:
            for u in usuarios:
                try:
                    user_id = u["id"]
                    username = u["username"]
                    role = u["role"]
                    creado = u.get("fecha_creacion", "-")
                    modificado = u.get("fecha_modificacion", "-")

                    avatar = ft.CircleAvatar(
                        content=ft.Text(username[0].upper(), size=14, weight="bold"),
                        bgcolor=ft.colors.BLUE_GREY
                    )

                    pw_text = ft.Text("●●●●●●●●", italic=True, color=ft.colors.SECONDARY, size=14)
                    toggle_btn = ft.IconButton(
                        icon=ft.icons.REMOVE_RED_EYE,
                        tooltip="Ver contraseña",
                        on_click=lambda e, uid=user_id, label=pw_text: self._toggle_password(uid, label, e.control)
                    )

                    pw_field = ft.Row([pw_text, toggle_btn], vertical_alignment=ft.CrossAxisAlignment.CENTER)

                    def editar_usuario(index, uid, actual_username, actual_role, creado, modificado):
                        username_input = ft.TextField(value=actual_username)
                        password_input = ft.TextField(hint_text="Nueva contraseña (opcional)", password=True)
                        role_input = ft.Dropdown(value=actual_role, options=[
                            ft.dropdown.Option("user"), ft.dropdown.Option("root")
                        ])

                        def confirmar(_):
                            nuevo_username = username_input.value.strip()
                            nueva_password = password_input.value.strip()
                            nuevo_rol = role_input.value

                            if not nuevo_username:
                                ModalAlert.mostrar_info("Validación", "El nombre de usuario no puede estar vacío.")
                                return

                            if actual_role == "root" and nuevo_rol != "root" and contar_roots() == 1:
                                ModalAlert.mostrar_info("Restricción", "Debe existir al menos un usuario root.")
                                return

                            campos = {"username": nuevo_username, "role": nuevo_rol}
                            if nueva_password:
                                campos["password"] = nueva_password

                            resultado = self.user_model.update(uid, campos)
                            if resultado["status"] == "success":
                                ModalAlert.mostrar_info("Éxito", f"Usuario {uid} actualizado.")
                                self._recargar_tabla()
                            else:
                                ModalAlert.mostrar_info("Error", resultado["message"])

                        def cancelar(_):
                            self._recargar_tabla()

                        fila_edicion = ft.DataRow(cells=[
                            ft.DataCell(ft.Text(str(uid))),
                            ft.DataCell(ft.CircleAvatar(content=ft.Text(username_input.value[:1].upper() if username_input.value else "?"))),
                            ft.DataCell(username_input),
                            ft.DataCell(role_input),
                            ft.DataCell(password_input),
                            ft.DataCell(ft.Text(creado)),
                            ft.DataCell(ft.Text(modificado)),
                            ft.DataCell(ft.Text("-")),
                            ft.DataCell(ft.Row([
                                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN, on_click=confirmar),
                                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED, on_click=cancelar)
                            ]))
                        ])

                        self.data_table.rows[index] = fila_edicion
                        self.data_table.update()

                    # Captura del índice actual de la fila
                    index_actual = len(rows)

                    rows.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(str(user_id))),
                            ft.DataCell(avatar),
                            ft.DataCell(ft.Text(username)),
                            ft.DataCell(ft.Text(role)),
                            ft.DataCell(pw_field),
                            ft.DataCell(ft.Text(str(creado))),
                            ft.DataCell(ft.Text(str(modificado))),
                            ft.DataCell(ft.IconButton(
                                icon=ft.icons.DELETE_FOREVER,
                                icon_color=ft.colors.RED,
                                tooltip="Eliminar usuario",
                                on_click=lambda e, uid=user_id: self._confirmar_eliminar(uid)
                            )),
                            ft.DataCell(ft.IconButton(
                                icon=ft.icons.EDIT,
                                tooltip="Editar usuario",
                                icon_color=ft.colors.BLUE,
                                on_click=lambda e, idx=index_actual, uid=user_id, uname=username, rol=role, cre=creado, mod=modificado:
                                    editar_usuario(idx, uid, uname, rol, cre, mod)
                            ))
                        ])
                    )
                except KeyError as e:
                    print(f"❌ Error al construir fila de usuario: clave faltante {e}")
        else:
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text("Sin registros", size=14))
            ] + [ft.DataCell(ft.Text("-", size=14)) for _ in range(8)]))

        self.data_table = ft.DataTable(
            expand=True,
            columns=[
                ft.DataColumn(label=ft.Text("ID", size=14, weight="bold")),
                ft.DataColumn(label=ft.Text("Avatar")),
                ft.DataColumn(label=ft.Text("Nombre de Usuario", size=14, weight="bold")),
                ft.DataColumn(label=ft.Text("Rol", size=14, weight="bold")),
                ft.DataColumn(label=ft.Text("Contraseña", size=14, weight="bold")),
                ft.DataColumn(label=ft.Text("Creado", size=14, weight="bold")),
                ft.DataColumn(label=ft.Text("Modificado", size=14, weight="bold")),
                ft.DataColumn(label=ft.Text("Eliminar", size=14, weight="bold")),
                ft.DataColumn(label=ft.Text("Editar", size=14, weight="bold")),
            ],
            rows=rows
        )

        return ft.Container(
            alignment=ft.alignment.center,
            content=self.data_table,
            expand=True,
            padding=10
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
            ModalAlert.mostrar_info("Éxito", f"Usuario con ID {user_id} eliminado.")
        else:
            ModalAlert.mostrar_info("Error", resultado["message"])
        self._recargar_tabla()


    def _recargar_tabla(self):
        nueva_tabla = self._build_table()
        self.table.content = nueva_tabla.content  # reemplaza el contenido interno
        self.data_table = nueva_tabla.content     # actualiza la referencia
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

            if not username or not password or not role:
                ModalAlert.mostrar_info("Validación", "Todos los campos son obligatorios.")
                return

            self.user_model.add(username, password, role)
            ModalAlert.mostrar_info("Éxito", f"Usuario '{username}' agregado correctamente.")
            self._recargar_tabla()

        def cancelar(_):
            self._recargar_tabla()

        row = ft.DataRow(cells=[
            ft.DataCell(ft.Text(str(id_nuevo))),
            ft.DataCell(ft.CircleAvatar(content=ft.Text("?", size=14))),
            ft.DataCell(username_field),
            ft.DataCell(role_dropdown),
            ft.DataCell(password_field),
            ft.DataCell(ft.Text(now)),
            ft.DataCell(ft.Text(now)),
            ft.DataCell(ft.Row([
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN, on_click=confirmar),
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED, on_click=cancelar)
            ])),
            ft.DataCell(ft.Text("Agregando..."))
        ])

        self.data_table.rows.append(row)
        self.data_table.update()


    def _exportar_usuarios(self, path: str):
        try:
            result = self.user_model.get_users()
            data = result.get("data", [])
            df = pd.DataFrame(data, columns=["id", "username", "role", "fecha_creacion", "fecha_modificacion"])
            df.to_excel(path, index=False)
            ModalAlert.mostrar_info("Éxito", f"Usuarios exportados a:\n{path}")
        except Exception as e:
            ModalAlert.mostrar_info("Error", f"No se pudo exportar:\n{e}")


    def _importar_usuarios(self, path: str):
        try:
            df = pd.read_excel(path)
            for _, row in df.iterrows():
                username = row.get("username")
                role = row.get("role")
                password = row.get("password", "123456")
                if username:
                    self.user_model.add(username, password, role)
            ModalAlert.mostrar_info("Éxito", f"{len(df)} usuarios importados correctamente.")
            self._recargar_tabla()
        except Exception as e:
            ModalAlert.mostrar_info("Error", f"No se pudo importar:\n{e}")
