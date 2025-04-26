# app/views/home_view.py

import flet as ft
from app.core.app_state import AppState
from app.views.nvar_view import NavBarView  # Import correcto
from app.views.containers.theme_controller import ThemeController  # Theme singleton

class HomeView(ft.View):
    def __init__(self):
        super().__init__(route="/home", controls=[])

        # Página actual desde el estado global
        self.page = AppState().page

        # Instancia singleton de ThemeController
        self.theme_ctrl = ThemeController()

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

        # Contenido inicial por defecto
        self.update_content("overview")

    def update_content(self, section: str):
        """
        Actualiza el contenido según la sección seleccionada.
        """
        if self.page is None:
            return  # Seguridad: no intentar actualizar si page es None

        # Reconstruir navbar si tiene método build()
        if hasattr(self.nav_bar, "build"):
            self.nav_bar.build()

        # Mapeo de secciones
        section_map = {
            "overview": "Bienvenido al Home",
            "usuario": "Sección: Usuario",
            "empleados": "Sección: Empleados",
            "asistencias": "Sección: Asistencias",
            "pagos": "Sección: Pagos",
            "prestamos": "Sección: Préstamos",
            "desempeno": "Sección: Desempeño",
            "reportes": "Sección: Reportes",
            "config": "Configuración del sistema",
            "usuarios": "Gestor de usuarios (Root)"
        }

        # Determinar texto
        content_text = section_map.get(section, "Vista no encontrada o sin acceso")
        if section == "usuarios" and not self.is_root:
            content_text = "Vista no encontrada o sin acceso"

        # Obtener color desde el theme controller
        fg_color = self.theme_ctrl.get_fg_color()

        # Asignar el contenido
        self.content_area.content = ft.Container(
            expand=True,
            padding=20,
            bgcolor=None,
            content=ft.Text(content_text, color=fg_color, size=16)
        )

        # Refrescar UI
        self.page.update()
