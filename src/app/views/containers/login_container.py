import flet as ft
from app.models.user_model import UserModel
from app.helpers.password_manager import PasswordManager
from app.core.enums.e_user_model import EUserModel

class LoginContainer(ft.Container):
    def __init__(self):
        super().__init__(
            width=450,
            padding=20,
            border_radius=10,
            bgcolor=ft.colors.BLUE_ACCENT_100,
            alignment=ft.alignment.center,
        )

        # configuramos las respectivas Models
        self.user_modal = UserModel()

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
                    src='logos/icon.png',
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

    def on_login(self, e):
        user_value = self.user_field.value.strip()
        pass_value = self.password_field.value.strip()
        print("on_click -> Usuario:", user_value)  # Depuración

        try:
            # Validaciones
            if user_value == '' or pass_value == '':
                self.login_message.value = "Por favor, ingrese un usuario y una contraseña."
                return

            user_data = self.user_modal.get_by_username(user_value)
            print(f'user_data: {user_data}')

            if user_data is None:

                self.login_message.value = "Usuario no encontrado."
            else:

                # Generar el hash de la contraseña ingresada (en minúsculas)
                entered_hash = PasswordManager().encrypt_password(pass_value)
                if entered_hash == user_data[EUserModel.PASSWORD]:

                    self.login_message.value = f"Bienvenido {user_value} (rol: {user_data[EUserModel.ROLE]})"
                    self.page.client_storage.set('app.user', user_data)
                    e.page.go('/dashboard')
                else:

                    self.login_message.value = "Contraseña incorrecta."

        except Exception as ex:
            self.login_message.value = str(ex)

        finally:
            e.page.update()