import flet as ft
from typing import Any
from app.core.app_state import AppState
from app.views.login_view import LoginView
from app.views.home_view import HomeView
from app.helpers.class_singleton import class_singleton

@class_singleton
class WindowMain:
    def __init__(self):
        self._page: ft.Page | None = None
        self.home_view: HomeView | None = None

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
        
        self._page.window_full_screen = True
        self._page.window_resizable = True

        # Instancia única de HomeView para layout persistente
        self.home_view = HomeView()

        # Asignar handler de rutas
        self._page.on_route_change = self.route_change
        # Iniciar en login
        self._page.go('/login')
        # self._page.go('/home')
    def route_change(self, route: ft.RouteChangeEvent):
        """
        Mapeo de rutas de la aplicación con layout persistente en /home
        """
        # Normalize path
        path = route.route or '/login'
        if path.endswith('/') and len(path) > 1:
            path = path[:-1]

        # Ruta de login
        if path == '/login':
            self._page.views.clear()
            self._page.views.append(LoginView())

        # Rutas /home y alias que deben usar layout persistente
        elif path == '/home' or path.startswith('/home/') or path.lstrip('/') in {
            'usuario','empleados','asistencias','pagos','prestamos','desempeno','reportes'}:
            # Determinar sección
            if path == '/home':
                section = 'overview'
            elif path.startswith('/home/'):
                section = path.split('/')[-1]
            else:
                section = path.lstrip('/')
            # Actualizar contenido en HomeView
            self.home_view.update_content(section)
            # Mostrar layout persistente
            self._page.views.clear()
            self._page.views.append(self.home_view)

        # Cualquier otra ruta: volver a login
        else:
            self._page.views.clear()
            self._page.views.append(LoginView())

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
