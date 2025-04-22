import flet as ft
from app.core.app_state import AppState
from app.views.containers.navbar_container import DashboardNavBar

class DashboardView(ft.View):
    def __init__(self, tab: str = "usuario"):
        super().__init__(
            route="/dashboard",
            controls=[]
        )

        self.page = AppState().page
        self.tab = tab

        # Obtenemos el usuario y su rol desde el almacenamiento
        user_data = self.page.client_storage.get("app.user")
        self.is_root = user_data and user_data.get("role") == "root"

        # Creamos barra lateral modular
        self.nav_bar = DashboardNavBar(is_root=self.is_root)

        # Contenedor dinámico de contenido
        self.content_area = ft.Container(expand=True)

        # Layout principal: barra lateral + contenido
        layout = ft.Row(
            expand=True,
            controls=[
                self.nav_bar,
                self.content_area
            ]
        )

        self.controls.append(layout)
        self.update_content(self.tab)

    def update_content(self, section: str):
        if section == "usuario":
            self.content_area.content = ft.Text("Sección: Usuario")
        elif section == "nomina":
            self.content_area.content = ft.Text("Sección: Nómina")
        elif section == "config":
            self.content_area.content = ft.Text("Configuración del sistema")
        elif section == "usuarios" and self.is_root:
            self.content_area.content = ft.Text("Gestor de usuarios (Root)")
        else:
            self.content_area.content = ft.Text("Vista no encontrada o sin acceso")

        self.page.update()

    def set_tema(self, oscuro: bool):
        self.bgcolor = ft.colors.BLACK if oscuro else ft.colors.WHITE
        self.content_area.bgcolor = ft.colors.BLACK if oscuro else ft.colors.WHITE
        self.page.update()


# import flet as ft

# class LayoutMain(ft.GridView):
#     def __init__(self):
#         super().__init__()

# class DashboardView(ft.View):

#     def __init__(self):
#         """
#         Vista de login
#         """
#         self.controls_dashboard = []
        
#         super().__init__(
#             route = '/dashboard',
#             controls = self.controls_dashboard
#         )


#         self.controls_dashboard.append(
#             ft.Text(value = 'dashboard')
#         )