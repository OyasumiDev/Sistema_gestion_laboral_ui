import flet as ft
from app.core.app_state import AppState
from app.views.dashboard_view import DashboardView
from app.views.containers.buttons.thene_button import ThemeToggleButton
from app.views.containers.buttons.exit_button import ExitButton
from app.views.containers.buttons.layout_button import LayoutToggleButton
from app.views.containers.buttons.menu_button import MenuButton

class DashboardNavBar(ft.Container):
    def __init__(self, is_root: bool = False):
        super().__init__(
            width=80,
            bgcolor=ft.colors.BLACK,
            padding=10,
            alignment=ft.alignment.top_left
        )

        self.page = AppState().page
        self.is_root = is_root
        self.expandido = False
        self.dashboard_view = None

        # Recuperar tema
        self.tema_oscuro = self.page.client_storage.get("tema_oscuro")
        if self.tema_oscuro is None:
            self.tema_oscuro = True

        # Avatar
        avatar_img = ft.Image(
            src="logos/root.png" if is_root else "logos/user.png",
            width=40,
            height=40,
            border_radius=20,
            fit=ft.ImageFit.COVER,
            tooltip="Usuario"
        )
        self.avatar = ft.Container(
            bgcolor=ft.colors.GREY_800,
            padding=8,
            border_radius=10,
            alignment=ft.alignment.center,
            content=avatar_img
        )

        # Botones del layout
        self.boton_layout = LayoutToggleButton(self)

        # Botones de menú
        self.menu_items = [
            MenuButton("Área de Asistencia", "button's/attendance-area-button.png", "usuario", self),
            MenuButton("Nómina", "button's/nomina-area-button.png", "nomina", self),
            MenuButton("Reportes", "button's/reports-area-button.png", "reportes", self),
        ]
        if is_root:
            self.menu_items.append(MenuButton("Gestión de Usuarios", "button's/user-manager-area-button.png", "usuarios", self))

        # Botón de tema
        self.boton_tema = ThemeToggleButton(self)

        # Botón de salir
        self.boton_salir = ExitButton(self)

        # Layout final
        self.column = ft.Column(
            spacing=10,
            controls=[self.avatar, self.boton_layout] +
                    self.menu_items +
                    [ft.Container(expand=True), self.boton_tema, self.boton_salir]
        )
        self.content = self.column

    def toggle_nav(self, e=None):
        self.expandido = not self.expandido
        self.width = 250 if self.expandido else 80

        self.boton_layout.update()
        self.boton_tema.update()
        self.boton_salir.update()
        for btn in self.menu_items:
            btn.update()

        self.page.update()

    def toggle_tema(self):
        self.tema_oscuro = not self.tema_oscuro
        self.page.client_storage.set("tema_oscuro", self.tema_oscuro)

        # También actualiza el dashboard si está disponible
        if self.dashboard_view:
            self.dashboard_view.set_tema(self.tema_oscuro)

        self.toggle_nav()

    def navegar(self, destino: str):
        from app.views.dashboard_view import DashboardView  # ✅ Import local para evitar circularidad
        vista_actual = next((v for v in self.page.views if isinstance(v, DashboardView)), None)
        if vista_actual:
            self.dashboard_view = vista_actual
            vista_actual.update_content(destino)

