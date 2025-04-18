import flet as ft
from app.models.user_model import UserModel
from app.helpers.password_manager import PasswordManager
from app.core.enums.e_user_model import EUserModel
from app.core.app_state import AppState



class LoginContainer(ft.Container):
    def __init__(self):
        super().__init__(
            width=450,
            padding=20,
            border_radius=10,
            bgcolor=ft.colors.BLUE_ACCENT_100,
            alignment=ft.alignment.center,
        )
        self.page = None

        # configuramos las respectivas Models
        self.user_model = UserModel()

        # Campos de texto para usuario y contraseña
        self.user_field = ft.TextField(
            label="Usuario"
        )

        self.password_field = ft.TextField(
            label="Contraseña",
            password=True,
            can_reveal_password=True
        )

        self.login_message = ft.Text(
            color=ft.Colors.BLACK
        )

        self.content = ft.Column(
            [
                # Logo en la parte superior del login
                ft.Image(
                    src='logos/loggin.png',
                    width=300
                ),

                # Campos de texto para usuario y contraseña
                self.user_field,
                self.password_field,

                # Botón de inicio de sesión
                ft.CupertinoButton(
                    "Iniciar sesión",
                    on_click=self.on_login,
                    bgcolor=ft.colors.BLUE_ACCENT_100,
                    color=ft.colors.WHITE
                ),

                # Mensaje de inicio de sesión
                self.login_message
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )

    def on_login(self, e: ft.ControlEvent):
        page: ft.Page = AppState().page

        user_value = self.user_field.value.strip()
        pass_value = self.password_field.value.strip()

        if not user_value or not pass_value:
            self.login_message.value = "Por favor, ingrese usuario y contraseña."
            page.update()
            return

        try:
            user_data = self.user_model.get_by_username(user_value)
            if user_data is None:
                self.login_message.value = "Usuario no encontrado."
            else:
                if pass_value == user_data[EUserModel.PASSWORD.value]:
                    # Convertimos fechas en string para evitar errores de serialización
                    user_data[EUserModel.FECHA_CREACION.value] = str(user_data[EUserModel.FECHA_CREACION.value])
                    user_data[EUserModel.FECHA_MODIFICACION.value] = str(user_data[EUserModel.FECHA_MODIFICACION.value])

                    page.client_storage.set("app.user", user_data)
                    page.go("/dashboard")
                else:
                    self.login_message.value = "Contraseña incorrecta."
        except Exception as ex:
            self.login_message.value = f"Error inesperado: {ex}"
        finally:
            page.update()

