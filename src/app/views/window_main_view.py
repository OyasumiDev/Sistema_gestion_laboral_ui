import flet as ft
from typing import Any
from app.core.app_state import AppState
from app.views.login_view import LoginView
from app.views.home_view import HomeView
from app.views.settings_view import SettingsView
from app.helpers.class_singleton import class_singleton

@class_singleton
class WindowMain:
    def __init__(self):
        self._page: ft.Page | None = None
        self.home_view: HomeView | None = None
        self.settings_view: SettingsView | None = None

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

        self._page.window_full_screen = True
        self._page.window_resizable = True

        # Estado global (ahora sí, con page ya definida)
        state = AppState()
        state.set_page(self._page)  # Aquí actualiza dimensiones y modo

        # Instancias únicas de vistas principales
        self.home_view = HomeView()
        self.settings_view = SettingsView(self._page)

        # Asignar handler de rutas
        self._page.on_route_change = self.route_change

        # Iniciar en login
        self._page.go('/login')

        # self._page.go('/home/empleados')
        # self._page.go('/home/asistencias')
        # self._page.go('/home/pagos')
        # self._page.go('/settings')
        # self._page.go('/prestamos')

    def route_change(self, route: ft.RouteChangeEvent):
        """
        Mapeo de rutas de la aplicación con layout persistente en /home
        y sección de configuración en /settings
        """
        path = route.route or '/login'
        if path.endswith('/') and len(path) > 1:
            path = path[:-1]

        if path == '/login':
            self._page.views.clear()
            self._page.views.append(LoginView())

        elif path == '/home' or path.startswith('/home/') or path.lstrip('/') in {
            'usuario', 'empleados', 'asistencias', 'pagos', 'prestamos', 'desempeno', 'reportes', 'config'
        } or path.startswith('/home/prestamos/pagosprestamos'):
            if path == '/home':
                section = 'overview'
            elif path.startswith('/home/'):
                section = path[len('/home/'):]  # Captura sección completa, incl. subrutas como prestamos/pagosprestamos
            else:
                section = path.lstrip('/')
            self.home_view.update_content(section)
            self._page.views.clear()
            self._page.views.append(self.home_view)

        elif path == '/settings' or path.startswith('/settings/'):
            if path == '/settings':
                section = 'settings'
            else:
                section = path.split('/')[-1]
            self.settings_view.update_content(section)
            self._page.views.clear()
            self._page.views.append(self.settings_view)

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
