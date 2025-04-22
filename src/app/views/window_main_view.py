import flet as ft
from typing import Any
from app.core.app_state import AppState
from app.views.login_view import LoginView
from app.views.dashboard_view import DashboardView
from app.views.containers.navbar_container import DashboardNavBar
# from app.views.
# from app.views.
# from app.views.
# from app.views.
# from app.views.
# from app.views.
from app.helpers.class_singleton import class_singleton

@class_singleton
class WindowMain:
    def __init__(self):
        self._page = None

    def __call__(self, flet_page: ft.Page) -> Any:
        self._page = flet_page
        self._page.title = "Sistema de gestion"
        self._page.window.icon = "logos/icon.ico" 
        self._page.window.center()
        self._page.padding = 0
        self._page.theme_mode = ft.ThemeMode.LIGHT
        self._page.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE_ACCENT_100)
        self._page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self._page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        


        # Seteamos nuestra pagina o windows main en page
        state = AppState()
        state.page = self._page

        self._page.on_route_change = self.route_change
        # Pruebas a partir de login
        self._page.go('/login')
        # Pruebas a partir de dshboard
        # self._page.go('/dashboard')
    def route_change(self, route: ft.RouteChangeEvent):

        # "/login","/usuarios","/empleados","/asistencias","/pagos""/prestamos","/desempeno","/reportes"
        
        views = {
        "/login": LoginView(),
        "/dashboard": DashboardView(),
        "/dashboard/usuario": DashboardView(tab="usuario"),
        "/dashboard/nomina": DashboardView(tab="nomina"),
        "/dashboard/config": DashboardView(tab="config")
                }
            # "/dashboard": nomina()
            # Area encargada de cargar los datos de la nomina y asistencias en forma tabular una vez cargados los datos
            # "/dashboard": asistenc()
            # "/dashboard": DashboardView()
            # "/dashboard": DashboardView()
        


        self._page.views.clear()
        self._page.views.append(views.get(route.route, LoginView()))
        self._page.update()

    def page_update(self):
        """
        Actualiza la información dentro de la ui
        """
        try:
            self._page.update()
        except Exception as e:
            pass


window_main = WindowMain()