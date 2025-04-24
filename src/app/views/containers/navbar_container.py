import flet as ft
from app.core.app_state import AppState

class NavBarContainer(ft.Container):
    """
    Barra de navegación con iconos uniformes y contraste para modo oscuro/claro.
    """
    def __init__(self, is_root: bool = False):
        # Estado global
        self.page = AppState().page
        self.is_root = is_root
        self.expandido = False
        # Tema guardado o por defecto
        stored_tema = self.page.client_storage.get("tema_oscuro")
        self.tema_oscuro = stored_tema if stored_tema is not None else True

        # Colores base según tema
        bg = ft.colors.BLACK if self.tema_oscuro else ft.colors.WHITE
        fg = ft.colors.WHITE if self.tema_oscuro else ft.colors.BLACK

        super().__init__(
            width=80,
            bgcolor=bg,
            padding=10,
            alignment=ft.alignment.top_left
        )

        # Auxiliar para iconos con fondo de contraste
        def make_icon(file_name: str):
            return ft.Container(
                bgcolor=fg,
                padding=6,
                border_radius=6,
                content=ft.Image(
                    src=f"assets/buttons/{file_name}",
                    width=24, height=24,
                    fit=ft.ImageFit.CONTAIN
                )
            )

        # Avatar de usuario
        avatar_src = "assets/logos/root.png" if is_root else "assets/logos/user.png"
        self.avatar = ft.Container(
            bgcolor=fg,
            padding=8,
            border_radius=10,
            alignment=ft.alignment.center,
            content=ft.Image(
                src=avatar_src,
                width=40, height=40,
                border_radius=20,
                fit=ft.ImageFit.COVER
            )
        )

        # Botón expandir/colapsar layout (imagen sin fondo)
        self.layout_icon = ft.Image(
            src="assets/buttons/layout_open-button.png",
            width=24, height=24,
            fit=ft.ImageFit.CONTAIN
        )
        self.layout_label = ft.Text("", visible=False, size=12, color=fg)
        self.btn_layout = ft.GestureDetector(
            on_tap=self.toggle_nav,
            content=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[self.layout_icon, self.layout_label]
            )
        )

        # Menú de navegación
        raw_menu = [
            ("Usuario",    "user-manager-area-button.png",    "usuario"),
            ("Empleados",  "employees-button.png",            "empleados"),
            ("Asistencias","attendance-area-button.png",    "asistencias"),
            ("Pagos",      "payment-area-button.png",        "pagos"),
            ("Préstamos",  "nomina-area-button.png",         "prestamos"),
            ("Desempeño",  "performance-area-button.png",    "desempeno"),
            ("Reportes",   "reports-area-button.png",        "reportes")
        ]
        if self.is_root:
            raw_menu.append(("Gestión de Usuarios", "user-manager-area-button.png", "usuarios"))

        self.menu_buttons = []
        for text, icon_file, ruta in raw_menu:
            icon = make_icon(icon_file)
            label = ft.Text(text, visible=False, size=12, color=fg)
            btn = ft.GestureDetector(
                on_tap=lambda e, r=ruta: self.page.go(f"/home/{r}"),
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[icon, label]
                )
            )
            self.menu_buttons.append((btn, icon, label))

        # Botón cambiar tema (imagen sin fondo)
        self.theme_icon = ft.Image(
            src=("assets/buttons/light-color-button.png" if self.tema_oscuro else "assets/buttons/dark-color-button.png"),
            width=24, height=24,
            fit=ft.ImageFit.CONTAIN
        )
        self.theme_label = ft.Text("Cambiar tema", visible=False, size=12, color=fg)
        self.btn_theme = ft.GestureDetector(
            on_tap=self.toggle_tema,
            content=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[self.theme_icon, self.theme_label]
            )
        )

        # Botón salir (imagen sin fondo)
        self.exit_icon = ft.Image(
            src="assets/buttons/exit-button.png",
            width=24, height=24,
            fit=ft.ImageFit.CONTAIN
        )
        self.exit_label = ft.Text("Salir", visible=False, size=12, color=fg)
        self.btn_exit = ft.GestureDetector(
            on_tap=self.exit_app,
            content=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[self.exit_icon, self.exit_label]
            )
        )

        # Montaje final
        self.content = ft.Column(
            spacing=16,
            controls=[
                self.avatar,
                self.btn_layout,
                *[btn for btn, _, _ in self.menu_buttons],
                ft.Container(expand=True),
                self.btn_theme,
                self.btn_exit
            ]
        )

    def _refresh_all(self):
        """Actualiza labels e iconos según estado."""
        fg = ft.colors.WHITE if self.tema_oscuro else ft.colors.BLACK

        # Layout icon swap
        icon_file = "layout_close-button.png" if self.expandido else "layout_open-button.png"
        self.layout_icon.src = f"assets/buttons/{icon_file}"
        self.layout_label.value = "Comprimir layout" if self.expandido else ""
        self.layout_label.visible = self.expandido

        # Menú labels
        for btn, icon, label in self.menu_buttons:
            label.visible = self.expandido
            label.color = fg

        # Tema icon swap
        theme_file = "light-color-button.png" if self.tema_oscuro else "dark-color-button.png"
        self.theme_icon.src = f"assets/buttons/{theme_file}"
        self.theme_label.visible = self.expandido
        self.theme_label.color = fg

        # Exit label only
        self.exit_label.visible = self.expandido
        self.exit_label.color = fg

        # Fondo principal
        self.bgcolor = ft.colors.BLACK if self.tema_oscuro else ft.colors.WHITE
        try:
            self.update()
        except:
            pass

    def toggle_nav(self, e=None):
        self.expandido = not self.expandido
        self.width = 250 if self.expandido else 80
        self._refresh_all()

    def toggle_tema(self, e=None):
        self.tema_oscuro = not self.tema_oscuro
        self.page.client_storage.set("tema_oscuro", self.tema_oscuro)
        self._refresh_all()

    def exit_app(self, e=None):
        self.page.window.close()
