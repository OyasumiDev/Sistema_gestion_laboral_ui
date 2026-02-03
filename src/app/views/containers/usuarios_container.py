import flet as ft
from datetime import datetime

from app.core.app_state import AppState
from app.models.user_model import UserModel
from app.views.containers.modal_alert import ModalAlert


class UsuariosContainer(ft.Container):
    """
    FINAL estable:
    - Anchos reales con Container(width=...) en headers y celdas
    - Modo compacto en edición/creación: sin Creado/Modificado
    - Root auth antes de editar usuario root (si verify_user_password existe)
    - Contraseña en edición/creación con reveal
    - ✅ Host de tabla: Row(scroll="auto") (estable en layout) + sin expand dentro de DataCell
    - ✅ Hitbox de acciones grande y dentro de la celda
    - No se queda bloqueado tras agregar/editar/cancelar/error
    """

    # 🔥 Ajusta aquí. Esto SÍ se refleja.
    W_ID = 50
    W_AVATAR = 50
    W_USERNAME = 150
    W_ROLE = 100
    W_PASSWORD = 200
    W_ACTIONS = 100

    # (solo modo normal)
    W_CREATED = 170
    W_MODIFIED = 170

    def __init__(self):
        super().__init__()
        self.expand = True
        self.page = AppState().page
        self.user_model = UserModel()

        user_data = self.page.client_storage.get("app.user") if self.page else None
        if not user_data or user_data.get("role") != "root":
            self.content = ft.Text(
                "❌ Acceso denegado. Solo el usuario root puede ver esta sección.",
                color=ft.colors.RED,
            )
            return

        # Estado UI
        self._active_mode: str | None = None  # None | "auth" | "edit" | "new"
        self._active_user_id: int | None = None

        # botones por fila (para lock)
        self._row_action_buttons: dict[int, dict[str, ft.IconButton]] = {}

        # UI superior persistente
        self.title = ft.Text("Usuarios registrados", size=24, weight="bold")

        self.btn_add = ft.ElevatedButton(
            content=ft.Row(
                [
                    ft.Icon(name=ft.icons.PERSON_ADD, size=18),
                    ft.Text("Agregar Usuario", size=12, weight="bold"),
                ],
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            on_click=self._agregar_usuario,
        )

        # Stats persistentes
        self.txt_total = ft.Text("-", size=16)
        self.txt_roots = ft.Text("-", size=16)
        self.txt_last_mod = ft.Text("-", size=14)

        self.stats_row = ft.Row(
            [
                ft.Card(
                    content=ft.Container(
                        padding=10,
                        content=ft.Column(
                            [
                                ft.Text("Total de usuarios", weight="bold", size=13),
                                self.txt_total,
                            ]
                        ),
                    )
                ),
                ft.Card(
                    content=ft.Container(
                        padding=10,
                        content=ft.Column(
                            [
                                ft.Text("Usuarios root", weight="bold", size=13),
                                self.txt_roots,
                            ]
                        ),
                    )
                ),
                ft.Card(
                    content=ft.Container(
                        padding=10,
                        content=ft.Column(
                            [
                                ft.Text("Última modificación", weight="bold", size=13),
                                self.txt_last_mod,
                            ]
                        ),
                    )
                ),
            ],
            spacing=20,
        )

        # DataTable persistente
        self.data_table = ft.DataTable(
            columns=[],
            rows=[],
            column_spacing=14,
            horizontal_margin=10,
            data_row_min_height=54,
        )

        # ✅ Host estable + scroll horizontal REAL
        # (Row scroll no buguea la tabla como ListView horizontal)
        self.table_host = ft.Container(
            expand=True,
            padding=10,
            alignment=ft.alignment.top_left,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Row(
                controls=[self.data_table],
                scroll=ft.ScrollMode.AUTO,
                wrap=False,
                spacing=0,
            ),
        )

        self.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                self.title,
                ft.Row([self.btn_add], spacing=20),
                ft.Divider(),
                self.stats_row,
                ft.Divider(height=10),
                self.table_host,
            ],
        )

        # Carga inicial
        self._refresh_all(normal_mode=True)

    # -------------------------------------------------------------------------
    # Helpers ancho real (headers + celdas)
    # -------------------------------------------------------------------------
    def _h(self, text: str, width: int) -> ft.Control:
        return ft.Container(
            width=width,
            alignment=ft.alignment.center_left,
            content=ft.Text(text, size=14, weight="bold"),
        )

    def _c(self, control: ft.Control, width: int) -> ft.Control:
        return ft.Container(
            width=width,
            alignment=ft.alignment.center_left,
            padding=ft.padding.symmetric(horizontal=4),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=control,
        )

    def _apply_table_width(self, normal_mode: bool) -> None:
        if normal_mode:
            total = (
                self.W_ID
                + self.W_AVATAR
                + self.W_USERNAME
                + self.W_ROLE
                + self.W_PASSWORD
                + self.W_CREATED
                + self.W_MODIFIED
                + self.W_ACTIONS
            )
        else:
            total = (
                self.W_ID
                + self.W_AVATAR
                + self.W_USERNAME
                + self.W_ROLE
                + self.W_PASSWORD
                + self.W_ACTIONS
            )

        # margen extra para spacing y márgenes internos de DataTable
        self.data_table.width = total + 80

    # -------------------------------------------------------------------------
    # Data / Stats
    # -------------------------------------------------------------------------
    def _fetch_users(self) -> list[dict]:
        resp = self.user_model.get_users()
        if isinstance(resp, dict) and resp.get("status") == "success":
            return resp.get("data", []) or []
        return []

    def _update_stats(self, usuarios: list[dict]) -> None:
        total = len(usuarios)
        roots = sum(1 for u in usuarios if u.get("role") == "root")

        last_mod = "N/A"
        if usuarios:
            fechas = [u.get("fecha_modificacion") for u in usuarios if u.get("fecha_modificacion")]
            if fechas:
                last_mod = str(max(fechas))

        self.txt_total.value = str(total)
        self.txt_roots.value = str(roots)
        self.txt_last_mod.value = str(last_mod)

    # -------------------------------------------------------------------------
    # Columns
    # -------------------------------------------------------------------------
    def _columns_normal(self) -> list[ft.DataColumn]:
        return [
            ft.DataColumn(label=self._h("ID", self.W_ID)),
            ft.DataColumn(label=self._h("Avatar", self.W_AVATAR)),
            ft.DataColumn(label=self._h("Nombre de Usuario", self.W_USERNAME)),
            ft.DataColumn(label=self._h("Rol", self.W_ROLE)),
            ft.DataColumn(label=self._h("Contraseña", self.W_PASSWORD)),
            ft.DataColumn(label=self._h("Creado", self.W_CREATED)),
            ft.DataColumn(label=self._h("Modificado", self.W_MODIFIED)),
            ft.DataColumn(label=self._h("Acciones", self.W_ACTIONS)),
        ]

    def _columns_compact(self) -> list[ft.DataColumn]:
        return [
            ft.DataColumn(label=self._h("ID", self.W_ID)),
            ft.DataColumn(label=self._h("Avatar", self.W_AVATAR)),
            ft.DataColumn(label=self._h("Nombre de Usuario", self.W_USERNAME)),
            ft.DataColumn(label=self._h("Rol", self.W_ROLE)),
            ft.DataColumn(label=self._h("Contraseña", self.W_PASSWORD)),
            ft.DataColumn(label=self._h("Acciones", self.W_ACTIONS)),
        ]

    # -------------------------------------------------------------------------
    # Rows - view
    # -------------------------------------------------------------------------
    def _build_row_view_normal(self, u: dict) -> ft.DataRow:
        user_id = int(u.get("id", 0) or 0)
        username = u.get("username", "") or ""
        role = u.get("role", "user") or "user"
        creado = str(u.get("fecha_creacion", "-"))
        modificado = str(u.get("fecha_modificacion", "-"))

        avatar = ft.CircleAvatar(
            content=ft.Text(username[:1].upper() if username else "?", size=14, weight="bold"),
            bgcolor=ft.colors.BLUE_GREY,
        )

        pw_text = ft.Text("●●●●●●●●", italic=True, color=ft.colors.SECONDARY, size=14)

        btn_del = ft.IconButton(
            icon=ft.icons.DELETE_FOREVER,
            icon_color=ft.colors.RED,
            tooltip="Eliminar usuario",
            on_click=lambda e, uid=user_id: self._confirmar_eliminar(uid),
            disabled=(self._active_mode is not None),
        )
        btn_edit = ft.IconButton(
            icon=ft.icons.EDIT,
            icon_color=ft.colors.BLUE,
            tooltip="Editar usuario",
            on_click=lambda e, user=u: self._entrar_edicion(user),
            disabled=(self._active_mode is not None),
        )

        self._row_action_buttons[user_id] = {"edit": btn_edit, "del": btn_del}

        # ✅ Acciones con hitbox grande y SIN expand (expand rompe hit-test en DataTable)
        half = max(44, int((self.W_ACTIONS - 8) / 2))

        acciones = ft.Row(
            spacing=0,
            controls=[
                ft.Container(width=half, height=44, alignment=ft.alignment.center, content=btn_del),
                ft.Container(width=half, height=44, alignment=ft.alignment.center, content=btn_edit),
            ],
        )

        return ft.DataRow(
            cells=[
                ft.DataCell(self._c(ft.Text(str(user_id)), self.W_ID)),
                ft.DataCell(self._c(avatar, self.W_AVATAR)),
                ft.DataCell(self._c(ft.Text(username), self.W_USERNAME)),
                ft.DataCell(self._c(ft.Text(role), self.W_ROLE)),
                ft.DataCell(self._c(pw_text, self.W_PASSWORD)),
                ft.DataCell(self._c(ft.Text(creado), self.W_CREATED)),
                ft.DataCell(self._c(ft.Text(modificado), self.W_MODIFIED)),
                ft.DataCell(self._c(acciones, self.W_ACTIONS)),
            ]
        )

    def _build_row_view_compact(self, u: dict) -> ft.DataRow:
        user_id = int(u.get("id", 0) or 0)
        username = u.get("username", "") or ""
        role = u.get("role", "user") or "user"

        avatar = ft.CircleAvatar(
            content=ft.Text(username[:1].upper() if username else "?", size=14, weight="bold"),
            bgcolor=ft.colors.BLUE_GREY,
        )
        pw_text = ft.Text("●●●●●●●●", italic=True, color=ft.colors.SECONDARY, size=14)

        return ft.DataRow(
            cells=[
                ft.DataCell(self._c(ft.Text(str(user_id)), self.W_ID)),
                ft.DataCell(self._c(avatar, self.W_AVATAR)),
                ft.DataCell(self._c(ft.Text(username), self.W_USERNAME)),
                ft.DataCell(self._c(ft.Text(role), self.W_ROLE)),
                ft.DataCell(self._c(pw_text, self.W_PASSWORD)),
                ft.DataCell(self._c(ft.Text(""), self.W_ACTIONS)),
            ]
        )

    # -------------------------------------------------------------------------
    # Refresh
    # -------------------------------------------------------------------------
    def _refresh_all(self, *, normal_mode: bool) -> None:
        usuarios = self._fetch_users()
        self._update_stats(usuarios)
        self._row_action_buttons.clear()

        if normal_mode:
            self.data_table.columns = self._columns_normal()
            self.data_table.rows = (
                [self._build_row_view_normal(u) for u in usuarios]
                if usuarios
                else [self._empty_row_normal()]
            )
        else:
            self.data_table.columns = self._columns_compact()
            self.data_table.rows = (
                [self._build_row_view_compact(u) for u in usuarios]
                if usuarios
                else [self._empty_row_compact()]
            )

        self._apply_table_width(normal_mode)
        self._apply_mode_to_top_controls()
        self._safe_update(self.data_table)
        self._safe_update(self)

    def _empty_row_normal(self) -> ft.DataRow:
        return ft.DataRow(
            cells=[
                ft.DataCell(self._c(ft.Text("Sin registros", size=14), self.W_ID)),
                ft.DataCell(self._c(ft.Text(""), self.W_AVATAR)),
                ft.DataCell(self._c(ft.Text(""), self.W_USERNAME)),
                ft.DataCell(self._c(ft.Text(""), self.W_ROLE)),
                ft.DataCell(self._c(ft.Text(""), self.W_PASSWORD)),
                ft.DataCell(self._c(ft.Text(""), self.W_CREATED)),
                ft.DataCell(self._c(ft.Text(""), self.W_MODIFIED)),
                ft.DataCell(self._c(ft.Text(""), self.W_ACTIONS)),
            ]
        )

    def _empty_row_compact(self) -> ft.DataRow:
        return ft.DataRow(
            cells=[
                ft.DataCell(self._c(ft.Text("Sin registros", size=14), self.W_ID)),
                ft.DataCell(self._c(ft.Text(""), self.W_AVATAR)),
                ft.DataCell(self._c(ft.Text(""), self.W_USERNAME)),
                ft.DataCell(self._c(ft.Text(""), self.W_ROLE)),
                ft.DataCell(self._c(ft.Text(""), self.W_PASSWORD)),
                ft.DataCell(self._c(ft.Text(""), self.W_ACTIONS)),
            ]
        )

    def _apply_mode_to_top_controls(self) -> None:
        self.btn_add.disabled = (self._active_mode is not None)
        self._safe_update(self.btn_add)

    def _safe_update(self, control: ft.Control | None) -> None:
        if not control:
            return
        try:
            control.update()
        except Exception:
            try:
                if self.page:
                    self.page.update()
            except Exception:
                pass

    def _lock_row_actions(self, locked: bool, *, except_user_id: int | None = None) -> None:
        for uid, btns in self._row_action_buttons.items():
            if except_user_id is not None and uid == except_user_id:
                continue
            btns["edit"].disabled = locked
            btns["del"].disabled = locked
        self._safe_update(self.data_table)

    # -------------------------------------------------------------------------
    # Root auth
    # -------------------------------------------------------------------------
    def _request_root_password(self, user: dict, on_success) -> None:
        uid = int(user.get("id", 0) or 0)
        username = user.get("username", "root") or "root"

        tf_pwd = ft.TextField(
            label="Contraseña actual",
            password=True,
            can_reveal_password=True,
            autofocus=True,
            width=320,
        )

        def close_dialog():
            dlg.open = False
            self._safe_update(self.page)

        def cancelar(_):
            close_dialog()
            self._exit_active_mode_and_refresh()

        def continuar(_):
            typed = (tf_pwd.value or "").strip()
            if not typed:
                ModalAlert.mostrar_info("Validación", "Escribe la contraseña actual para continuar.")
                return

            if not hasattr(self.user_model, "verify_user_password"):
                close_dialog()
                ModalAlert.mostrar_info(
                    "Pendiente",
                    "Tu UserModel no tiene verify_user_password().\n"
                    "Luego lo conectamos; por ahora no puedo validar la contraseña.",
                )
                self._exit_active_mode_and_refresh()
                return

            resp = self.user_model.verify_user_password(uid, typed)
            if not isinstance(resp, dict) or resp.get("status") != "success":
                close_dialog()
                ModalAlert.mostrar_info("Acceso denegado", resp.get("message", "Contraseña incorrecta."))
                self._exit_active_mode_and_refresh()
                return

            close_dialog()
            on_success()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Confirmación para editar '{username}'"),
            content=ft.Column(
                tight=True,
                controls=[
                    ft.Text("Para editar un usuario root, confirma la contraseña actual."),
                    tf_pwd,
                ],
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=cancelar),
                ft.ElevatedButton("Continuar", on_click=continuar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.dialog = dlg
        dlg.open = True
        self._safe_update(self.page)

    # -------------------------------------------------------------------------
    # Edit
    # -------------------------------------------------------------------------
    def _entrar_edicion(self, user: dict) -> None:
        if self._active_mode is not None:
            return

        uid = int(user.get("id", 0) or 0)
        role = user.get("role", "user") or "user"

        self._active_mode = "edit"
        self._active_user_id = uid

        self._refresh_all(normal_mode=False)
        self._lock_row_actions(True, except_user_id=uid)

        if role == "root":
            self._active_mode = "auth"
            self._active_user_id = uid

            def proceed():
                self._active_mode = "edit"
                self._active_user_id = uid
                self._enter_edit_row(user)

            self._request_root_password(user, proceed)
            return

        self._enter_edit_row(user)

    def _find_row_index_compact_by_user_id(self, user_id: int) -> int | None:
        for i, r in enumerate(self.data_table.rows):
            try:
                c0 = r.cells[0].content
                if isinstance(c0, ft.Container) and isinstance(c0.content, ft.Text) and str(c0.content.value) == str(user_id):
                    return i
            except Exception:
                continue
        return None

    def _enter_edit_row(self, user: dict) -> None:
        uid = int(user.get("id", 0) or 0)
        actual_username = user.get("username", "") or ""
        actual_role = user.get("role", "user") or "user"

        username_input = ft.TextField(
            value=actual_username,
            dense=True,
            content_padding=10,
            width=self.W_USERNAME - 16,
        )
        role_input = ft.Dropdown(
            value=actual_role,
            options=[ft.dropdown.Option("user"), ft.dropdown.Option("root")],
            dense=True,
            width=self.W_ROLE - 16,
        )
        password_input = ft.TextField(
            hint_text="Nueva contraseña (opcional)",
            password=True,
            can_reveal_password=True,
            dense=True,
            content_padding=10,
            width=self.W_PASSWORD - 16,
        )

        def contar_roots_db() -> int:
            users = self._fetch_users()
            return sum(1 for x in users if x.get("role") == "root")

        def confirmar(_):
            nuevo_username = (username_input.value or "").strip()
            nueva_password = (password_input.value or "").strip()
            nuevo_rol = role_input.value

            if not nuevo_username:
                ModalAlert.mostrar_info("Validación", "El nombre de usuario no puede estar vacío.")
                return

            if actual_role == "root" and nuevo_rol != "root" and contar_roots_db() == 1:
                ModalAlert.mostrar_info("Restricción", "Debe existir al menos un usuario root.")
                return

            campos = {"username": nuevo_username, "role": nuevo_rol}
            if nueva_password:
                campos["password"] = nueva_password

            resultado = self.user_model.update(uid, campos)
            if isinstance(resultado, dict) and resultado.get("status") == "success":
                ModalAlert.mostrar_info("Éxito", f"Usuario {uid} actualizado.")
                self._exit_active_mode_and_refresh()
            else:
                ModalAlert.mostrar_info("Error", resultado.get("message", "Error desconocido"))

        def cancelar(_):
            self._exit_active_mode_and_refresh()

        acciones = ft.Row(
            [
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN, on_click=confirmar),
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED, on_click=cancelar),
            ],
            spacing=6,
        )

        avatar = ft.CircleAvatar(
            content=ft.Text((actual_username[:1].upper() if actual_username else "?"), size=14, weight="bold"),
            bgcolor=ft.colors.BLUE_GREY,
        )

        row_edit = ft.DataRow(
            cells=[
                ft.DataCell(self._c(ft.Text(str(uid)), self.W_ID)),
                ft.DataCell(self._c(avatar, self.W_AVATAR)),
                ft.DataCell(self._c(username_input, self.W_USERNAME)),
                ft.DataCell(self._c(role_input, self.W_ROLE)),
                ft.DataCell(self._c(password_input, self.W_PASSWORD)),
                ft.DataCell(self._c(acciones, self.W_ACTIONS)),
            ]
        )

        idx = self._find_row_index_compact_by_user_id(uid)
        if idx is not None:
            self.data_table.rows[idx] = row_edit
            self._safe_update(self.data_table)

    # -------------------------------------------------------------------------
    # Delete
    # -------------------------------------------------------------------------
    def _confirmar_eliminar(self, user_id: int):
        if self._active_mode is not None:
            ModalAlert.mostrar_info("Acción bloqueada", "Termina o cancela la edición antes de eliminar.")
            return

        alerta = ModalAlert(
            title_text="Eliminar usuario",
            message=f"¿Estás seguro de que deseas eliminar el usuario con ID {user_id}?",
            on_confirm=lambda: self._eliminar_usuario(user_id),
        )
        alerta.mostrar()

    def _eliminar_usuario(self, user_id: int):
        resultado = self.user_model.delete_by_id(user_id)
        if isinstance(resultado, dict) and resultado.get("status") == "success":
            ModalAlert.mostrar_info("Éxito", f"Usuario con ID {user_id} eliminado.")
        else:
            ModalAlert.mostrar_info("Error", resultado.get("message", "No se pudo eliminar"))
        self._exit_active_mode_and_refresh()

    # -------------------------------------------------------------------------
    # Add
    # -------------------------------------------------------------------------
    def _agregar_usuario(self, e):
        if self._active_mode is not None:
            return

        self._active_mode = "new"
        self._active_user_id = None

        self._refresh_all(normal_mode=False)
        self._lock_row_actions(True)

        id_nuevo = self.user_model.get_last_id() + 1

        username_field = ft.TextField(
            hint_text="Usuario",
            dense=True,
            content_padding=10,
            width=self.W_USERNAME - 16,
        )
        role_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option("user"), ft.dropdown.Option("root")],
            dense=True,
            width=self.W_ROLE - 16,
        )
        password_field = ft.TextField(
            hint_text="Contraseña",
            password=True,
            can_reveal_password=True,
            dense=True,
            content_padding=10,
            width=self.W_PASSWORD - 16,
        )

        def confirmar(_: ft.ControlEvent):
            username = (username_field.value or "").strip()
            password = (password_field.value or "").strip()
            role = role_dropdown.value

            if not username or not password or not role:
                ModalAlert.mostrar_info("Validación", "Todos los campos son obligatorios.")
                return

            resp = self.user_model.add(username, password, role)
            if isinstance(resp, dict) and resp.get("status") == "success":
                ModalAlert.mostrar_info("Éxito", f"Usuario '{username}' agregado correctamente.")
                self._exit_active_mode_and_refresh()
            else:
                ModalAlert.mostrar_info("Error", resp.get("message", "No se pudo agregar"))

        def cancelar(_):
            self._exit_active_mode_and_refresh()

        acciones = ft.Row(
            [
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN, on_click=confirmar),
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED, on_click=cancelar),
            ],
            spacing=6,
        )

        avatar = ft.CircleAvatar(content=ft.Text("?", size=14, weight="bold"), bgcolor=ft.colors.BLUE_GREY)

        row_new = ft.DataRow(
            cells=[
                ft.DataCell(self._c(ft.Text(str(id_nuevo)), self.W_ID)),
                ft.DataCell(self._c(avatar, self.W_AVATAR)),
                ft.DataCell(self._c(username_field, self.W_USERNAME)),
                ft.DataCell(self._c(role_dropdown, self.W_ROLE)),
                ft.DataCell(self._c(password_field, self.W_PASSWORD)),
                ft.DataCell(self._c(acciones, self.W_ACTIONS)),
            ]
        )

        self.data_table.rows.append(row_new)
        self._safe_update(self.data_table)

    # -------------------------------------------------------------------------
    # Exit active mode
    # -------------------------------------------------------------------------
    def _exit_active_mode_and_refresh(self):
        self._active_mode = None
        self._active_user_id = None
        self._refresh_all(normal_mode=True)
        self._lock_row_actions(False)
        self._apply_mode_to_top_controls()
        self._safe_update(self)
