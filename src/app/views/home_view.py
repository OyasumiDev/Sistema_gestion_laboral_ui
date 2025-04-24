import flet as ft
from app.core.app_state import AppState
from app.views.nvar_view import NavBarView  # <-- Import correcto

class HomeView(ft.View):
    def __init__(self):
        super().__init__(
            route="/home",
            controls=[]
        )

        # Página actual desde el estado global
        self.page = AppState().page

        # Obtenemos el usuario y su rol desde el almacenamiento local
        user_data = self.page.client_storage.get("app.user")
        self.is_root = user_data and user_data.get("role") == "root"

        # Creamos la vista de la barra lateral modular
        self.nav_bar = NavBarView(is_root=self.is_root)

        # Contenedor dinámico de contenido
        self.content_area = ft.Container(expand=True)

        # Layout principal: barra lateral + área de contenido
        layout = ft.Row(
            expand=True,
            controls=[
                self.nav_bar,
                self.content_area
            ]
        )
        self.controls.append(layout)

        # Contenido inicial por defecto (overview)
        self.update_content("overview")

    def update_content(self, section: str):
        """
        Actualiza el contenido según la sección seleccionada.
        """
        if section == "overview":
            self.content_area.content = ft.Text("Bienvenido al Home")
        elif section == "usuario":
            self.content_area.content = ft.Text("Sección: Usuario")
        elif section == "empleados":
            self.content_area.content = ft.Text("Sección: Empleados")
        elif section == "asistencias":
            self.content_area.content = ft.Text("Sección: Asistencias")
        elif section == "pagos":
            self.content_area.content = ft.Text("Sección: Pagos")
        elif section == "prestamos":
            self.content_area.content = ft.Text("Sección: Préstamos")
        elif section == "desempeno":
            self.content_area.content = ft.Text("Sección: Desempeño")
        elif section == "reportes":
            self.content_area.content = ft.Text("Sección: Reportes")
        elif section == "config":
            self.content_area.content = ft.Text("Configuración del sistema")
        elif section == "usuarios" and self.is_root:
            self.content_area.content = ft.Text("Gestor de usuarios (Root)")
        else:
            self.content_area.content = ft.Text("Vista no encontrada o sin acceso")

        # Refrescamos la UI
        self.page.update()
