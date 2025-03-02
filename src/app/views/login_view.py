import flet as ft
from app.core.app_state import state
from app.core.database_manager import DatabaseManager
from app.helpers.password_manager import PasswordManager

# Vista Login
class LoginView(ft.View):

    def __init__(self):
        '''
        Vista de login
        '''
        super().__init__(
            route = '/login',
            appbar=ft.AppBar(
                title=ft.Text("Inicio de sesión"),
                bgcolor=ft.Colors.ON_SURFACE_VARIANT
            ),
            vertical_alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
        # Accedemos a la base de datos
        self.db_manager = DatabaseManager()



        # Accedemos a page main
        self._page_main = state.page

        # Campos de texto para usuario y contraseña
        self.user_field = ft.TextField(label="Usuario", width=150)
        self.password_field = ft.TextField(label="Contraseña", password=True, width=150)
        self.login_message = ft.Text(color=ft.Colors.BLACK)

        self.container = ft.Container(
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
                    ft.Image(src = 'logos/icon.png', width=300),
                    # Fila para Usuario y Contraseña
                    ft.Row(
                        controls=[self.user_field, self.password_field],
                        alignment=ft.MainAxisAlignment.CENTER
                    ),
                    # Botón de "Iniciar sesión"
                    ft.ElevatedButton(text="Iniciar sesión", on_click=self.on_login),
                    # Mensaje de resultado del login
                    self.login_message
                ]
            )
        )

        self.controls.append(self.container)
        
    
    def callback_go_dashboard(self, event):
        event.page.go('/dashboard')
    

    def on_login(self, e):
        user_value = self.user_field.value.strip()
        pass_value = self.password_field.value.strip()
        print("on_login llamado -> Usuario:", user_value)  # Depuración

        try:
            user_data = self.db_manager.get_user_data(user_value)

            if user_data is None:

                self.login_message.value = "Usuario no encontrado."
            else:

                # Generar el hash de la contraseña ingresada (en minúsculas)
                entered_hash = PasswordManager().encrypt_password(pass_value)
                if entered_hash == user_data['password_hash']:
                    
                    self.login_message.value = f"Bienvenido {user_value} (rol: {user_data['role']})"
                    e.page.go('/dashboard')
                else:
                    
                    self.login_message.value = "Contraseña incorrecta."
            
            # Actualizar vista
            e.page.update()

        except Exception as ex:
            self.login_message.value = str(ex)






