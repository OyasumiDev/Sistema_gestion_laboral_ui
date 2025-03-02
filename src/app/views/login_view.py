import flet as ft
from helpers.convert_image import convert_image_to_base64
import mysql.connector
import hashlib

# Vista Login
class LoginView(ft.Container):

    def __init__(self):
        '''
        Vista de login
        '''
        super().__init__(
            content=ft.Text("Inicio de sesión"),
            alignment=ft.alignment.center
        )

login_view = LoginView()

def hash_password(password: str) -> str:
    """
    Genera el hash SHA-256 en formato hexadecimal (en minúsculas)
    para que coincida con el valor almacenado en la base de datos.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def main(page: ft.Page):
    # Configuración de tema y centrado
    # page.theme_mode = ft.ThemeMode.LIGHT
    # page.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE_ACCENT_100)
    # page.vertical_alignment = ft.MainAxisAlignment.CENTER
    # page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    # Barra superior
    page.appbar = ft.AppBar(
        title=ft.Text("Inicio de sesión"),
        bgcolor=ft.Colors.ON_SURFACE_VARIANT
    )

    # Convertir imagen a base64
    image_path = r"C:\Users\fatra\OneDrive - Universidad Autonoma de Nuevo León\Trabajo\FRONT\app_loggin\src\assets\icon.png"
    base64_image = convert_image_to_base64(image_path)
    
    # Campos de texto para usuario y contraseña
    user_field = ft.TextField(label="Usuario", width=150)
    password_field = ft.TextField(label="Contraseña", password=True, width=150)
    login_message = ft.Text("", color=ft.Colors.GREEN)

    # Función para obtener los datos del usuario de la base de datos

    # Función que maneja el inicio de sesión
    def on_login(e):
        user_value = user_field.value.strip()
        pass_value = password_field.value.strip()
        print("on_login llamado -> Usuario:", user_value)  # Depuración

        try:
            user_data = get_user_data(user_value)
            if user_data is None:
                login_message.value = "Usuario no encontrado."
            else:
                # Generar el hash de la contraseña ingresada (en minúsculas)
                entered_hash = hash_password(pass_value)
                if entered_hash == user_data["password_hash"]:
                    login_message.value = f"Bienvenido {user_value} (rol: {user_data['role']})"
                else:
                    login_message.value = "Contraseña incorrecta."
        except Exception as ex:
            login_message.value = str(ex)

        page.update()

    # Permitir iniciar sesión presionando Enter en el campo de contraseña
    password_field.on_submit = on_login

    # Contenedor principal
    container = ft.Container(
        width=450,
        padding=20,
        border_radius=10,
        bgcolor=ft.Colors.BLUE_ACCENT_100,
        alignment=ft.alignment.center,
        content=ft.Column(
            spacing=20,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                # Logo centrado
                ft.Image(src_base64=base64_image, width=300),
                # Fila para Usuario y Contraseña
                ft.Row(
                    controls=[user_field, password_field],
                    alignment=ft.MainAxisAlignment.CENTER
                ),
                # Botón de "Iniciar sesión"
                ft.ElevatedButton(text="Iniciar sesión", on_click=on_login),
                # Mensaje de resultado del login
                login_message
            ]
        )
    )

    # Columna principal que centra el contenedor
    main_column = ft.Column(
        expand=True,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[container]
    )

    page.add(main_column)
    page.update()
    