import flet as ft
from app.core.app_state import AppState
from app.views.nvar_view import NavBarView
from app.views.containers.theme_controller import ThemeController
from app.views.containers.asistencias_container import AsistenciasContainer
from app.views.empleados_view import EmpleadosView
from app.views.containers.usuarios_container import UsuariosContainer
from app.views.containers.pagos_container import PagosContainer
from app.views.containers.prestamos_container import PrestamosContainer
from app.views.containers.pagos_prestamo_container import PagosPrestamoContainer


class HomeView(ft.View):
    def __init__(self):
        super().__init__(route="/home", controls=[])

        self.page = AppState().page
        self.theme_ctrl = ThemeController()

        user_data = self.page.client_storage.get("app.user")
        self.is_root = user_data and user_data.get("role") == "root"

        self.nav_bar = NavBarView(is_root=self.is_root)
        self.content_area = ft.Container(expand=True)

        layout = ft.Row(
            expand=True,
            controls=[self.nav_bar, self.content_area]
        )
        self.controls.append(layout)

        self.update_content("overview")

    def update_content(self, section: str):
        if self.page is None:
            return

        if hasattr(self.nav_bar, "build"):
            self.nav_bar.build()

        section_map = {
            "overview": "Bienvenido al Home",
            "empleados": "Sección: Empleados",
            "asistencias": "Sección: Asistencias",
            "pagos": "Sección: Pagos",
            "prestamos": "Sección: Préstamos",
            "prestamos/pagosprestamos": "Pagos del préstamo",
            "desempeno": "Sección: Desempeño",
            "reportes": "Sección: Reportes",
            "config": "Configuración del sistema",
            "usuarios": "Gestor de usuarios (Root)"
        }

        content_text = section_map.get(section, "Vista no encontrada o sin acceso")
        if section == "usuarios" and not self.is_root:
            content_text = "Vista no encontrada o sin acceso"

        fg_color = self.theme_ctrl.get_fg_color()

        if section == "empleados":
            from app.views.containers.empleados_container import EmpleadosContainer
            self.content_area.content = ft.Column(
                expand=True,
                controls=[
                    ft.Text("AREA DE EMPLEADOS", size=20, weight="bold", color=fg_color),
                    EmpleadosContainer()
                ]
            )

        elif section == "asistencias":
            self.content_area.content = ft.Column(
                expand=True,
                controls=[
                    ft.Text("AREA DE ASISTENCIAS", size=20, weight="bold", color=fg_color),
                    AsistenciasContainer()
                ]
            )

        elif section == "pagos":
            self.content_area.content = ft.Column(
                expand=True,
                controls=[
                    ft.Text("AREA DE PAGOS", size=20, weight="bold", color=fg_color),
                    PagosContainer()
                ]
            )

        elif section == "prestamos":
            self.content_area.content = ft.Column(
                expand=True,
                controls=[
                    ft.Text("ÁREA DE PRÉSTAMOS", size=20, weight="bold", color=fg_color),
                    PrestamosContainer()
                ]
            )

        elif section.startswith("prestamos/pagosprestamos"):
            self.content_area.content = ft.Column(
                expand=True,
                controls=[
                    ft.Text("PAGOS DEL PRÉSTAMO", size=20, weight="bold", color=fg_color),
                    PagosPrestamoContainer()
                ]
            )

        elif section == "usuarios" and self.is_root:
            self.content_area.content = ft.Column(
                expand=True,
                controls=[
                    UsuariosContainer()
                ]
            )

        else:
            self.content_area.content = ft.Column(
                expand=True,
                controls=[
                    ft.Text(f"Área actual: {content_text}", size=20, weight="bold", color=fg_color),
                    ft.Container(
                        expand=True,
                        padding=20,
                        bgcolor=None,
                        content=ft.Text(content_text, color=fg_color, size=16)
                    )
                ]
            )

        self.page.update()
