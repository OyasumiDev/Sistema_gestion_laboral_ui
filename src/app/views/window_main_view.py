import flet as ft
from typing import Any
from app.core.app_state import AppState
from app.views.login_view import LoginView
from app.views.home_view import HomeView
from app.views.usuario_view import UsuarioView
from app.views.empleados_view import EmpleadosView
from app.views.asistencias_view import AsistenciasView
from app.views.pagos_view import PagosView
from app.views.prestamos_view import PrestamosView
from app.views.desempeno_view import DesempenoView
from app.views.reportes_view import ReportesView
from app.helpers.class_singleton import class_singleton

@class_singleton
class WindowMain:
    def __init__(self):
        self._page: ft.Page | None = None

    def __call__(self, flet_page: ft.Page) -> Any:
        self._page = flet_page
        self._page.title = "Sistema de gestión"
        self._page.window.icon = "logos/icon.ico"
        self._page.window.center()
        self._page.padding = 0
        self._page.theme_mode = ft.ThemeMode.LIGHT
        self._page.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE_ACCENT_100)
        self._page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self._page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

        # Estado global
        state = AppState()
        state.page = self._page

        # Asignar handler de rutas
        self._page.on_route_change = self.route_change
        # Iniciar en login
        self._page.go('/login')

    def route_change(self, route: ft.RouteChangeEvent):
        """
        Mapeo de rutas de la aplicación con normalización de path.
        """
        # Normalize path to avoid trailing slash issues
        path = route.route or '/login'
        if path.endswith('/') and len(path) > 1:
            path = path[:-1]

        views = {
            # Rutas públicas
            '/login': LoginView(),
            # Home
            '/home': HomeView(),
            # Sub-áreas
            '/home/usuario': UsuarioView(),
            '/home/empleados': EmpleadosView(),
            '/home/asistencias': AsistenciasView(),
            '/home/pagos': PagosView(),
            '/home/prestamos': PrestamosView(),
            '/home/desempeno': DesempenoView(),
            '/home/reportes': ReportesView(),
            # Atajos directos
            '/usuarios': UsuarioView(),
            '/empleados': EmpleadosView(),
            '/asistencias': AsistenciasView(),
            '/pagos': PagosView(),
            '/prestamos': PrestamosView(),
            '/desempeno': DesempenoView(),
            '/reportes': ReportesView(),
        }

        # Render selected view or fallback to login
        self._page.views.clear()
        selected_view = views.get(path, LoginView())
        self._page.views.append(selected_view)
        self._page.update()

    def page_update(self):
        """
        Refresca la UI si es necesario.
        """
        try:
            self._page.update()
        except Exception:
            pass

# Instanciación singleton
window_main = WindowMain()
