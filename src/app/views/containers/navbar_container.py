# app/views/containers/navbar_container.py
import flet as ft
from app.core.app_state import AppState

class NavBarContainer(ft.Container):
    """
    Barra de navegación que integra todos los botones y su lógica internamente.
    """
    def __init__(self, is_root: bool = False):
        super().__init__(
            width=80,
            bgcolor=ft.colors.BLACK,
            padding=10,
            alignment=ft.alignment.top_left
        )

        # Estado global
        self.page = AppState().page
        self.is_root = is_root
        self.expandido = False
        # ClientStorage.get only accepts one parameter: the key.
        stored_tema = self.page.client_storage.get("tema_oscuro")
        self.tema_oscuro = stored_tema if stored_tema is not None else True

        # Avatar de usuario
        avatar_img = ft.Image(
            src="logos/root.png" if is_root else "logos/user.png",
            width=40, height=40,
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

        # Botón de layout integrado
        self.layout_icon = ft.Container(
            bgcolor=ft.colors.WHITE,
            border_radius=6,
            padding=6,
            content=ft.Image(src="button's/layout_open-button.png", width=20, height=20)
        )
        self.layout_label = ft.Text(
            value="",
            visible=False,
            size=12,
            color=ft.colors.WHITE
        )
        self.btn_layout = ft.GestureDetector(
            on_tap=self.toggle_nav,
            content=ft.Container(
                bgcolor=ft.colors.GREY_800,
                padding=10,
                border_radius=8,
                content=ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[self.layout_icon, self.layout_label]
                )
            )
        )

        # Botones de menú
        raw_menu = [
            ("Usuario", "button's/attendance-area-button.png", "usuario"),
            ("Empleados", "button's/empleados-area-button.png", "empleados"),
            ("Asistencias", "button's/attendance-area-button.png", "asistencias"),
            ("Pagos", "button's/pagos-area-button.png", "pagos"),
            ("Préstamos", "button's/prestamos-area-button.png", "prestamos"),
            ("Desempeño", "button's/desempeno-area-button.png", "desempeno"),
            ("Reportes", "button's/reportes-area-button.png", "reportes")
        ]
        if self.is_root:
            raw_menu.append(
                ("Gestión de Usuarios", "button's/user-manager-area-button.png", "usuarios")
            )
        self.menu_buttons = []
        for text, icon_path, ruta in raw_menu:
            icon = ft.Container(
                bgcolor=ft.colors.WHITE if self.tema_oscuro else ft.colors.BLACK,
                border_radius=6,
                padding=6,
                content=ft.Image(src=icon_path, width=20, height=20)
            )
            label = ft.Text(
                value=text,
                visible=False,
                size=12,
                color=ft.colors.WHITE if self.tema_oscuro else ft.colors.BLACK
            )
            btn = ft.GestureDetector(
                on_tap=lambda e, r=ruta: self.page.go(f"/home/{r}"),
                content=ft.Container(
                    bgcolor=ft.colors.GREY_800 if self.tema_oscuro else ft.colors.GREY_300,
                    padding=10,
                    border_radius=8,
                    content=ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[icon, label]
                    )
                )
            )
            self.menu_buttons.append((btn, icon, label))

        # Botón de tema integrado
        self.theme_icon = ft.Container(border_radius=6, padding=6)
        self.theme_label = ft.Text(value="", visible=False, size=12)
        self.btn_theme = ft.GestureDetector(
            on_tap=self.toggle_tema,
            content=ft.Container(
                bgcolor=ft.colors.GREY_800,
                padding=10,
                border_radius=8,
                content=ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[self.theme_icon, self.theme_label]
                )
            )
        )

        # Botón de salir integrado
        self.exit_icon = ft.Container(border_radius=6, padding=6)
        self.exit_label = ft.Text(value="", visible=False, size=12)
        self.btn_exit = ft.GestureDetector(
            on_tap=self.exit_app,
            content=ft.Container(
                bgcolor=ft.colors.GREY_800,
                padding=10,
                border_radius=8,
                content=ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[self.exit_icon, self.exit_label]
                )
            )
        )

        # Montaje final
        self.content = ft.Column(
            spacing=10,
            controls=[
                self.avatar,
                self.btn_layout,
                *[btn for btn, _, _ in self.menu_buttons],
                ft.Container(expand=True),
                self.btn_theme,
                self.btn_exit
            ]
        )
        # Inicializamos iconos y etiquetas
        self._refresh_all()

    def _refresh_all(self):
        # Actualiza estado visual de todos los botones
        # Layout
        icon_file = "layout_close-button.png" if self.expandido else "layout_open-button.png"
        self.layout_icon.content.src = f"button's/{icon_file}"
        self.layout_label.value = "Comprimir layout" if self.expandido else ""
        self.layout_label.visible = self.expandido

        # Menú
        for btn, icon, label in self.menu_buttons:
            label.visible = self.expandido
            label.color = ft.colors.WHITE if self.tema_oscuro else ft.colors.BLACK
            icon.bgcolor = ft.colors.WHITE if self.tema_oscuro else ft.colors.BLACK
            btn.content.bgcolor = ft.colors.GREY_800 if self.tema_oscuro else ft.colors.GREY_300

        # Tema
        dark = self.tema_oscuro
        self.theme_icon.content = ft.Image(
            src=("light-color-button.png" if dark else "dark-color-button.png"),
            width=20, height=20
        )
        self.theme_icon.bgcolor = ft.colors.WHITE if dark else ft.colors.BLACK
        self.theme_label.value = "Cambiar tema"
        self.theme_label.visible = self.expandido
        self.theme_label.color = ft.colors.WHITE if dark else ft.colors.BLACK
        self.btn_theme.content.bgcolor = ft.colors.GREY_800 if dark else ft.colors.GREY_300

        # Salir
        self.exit_icon.content = ft.Image(src="button's/exit-button.png", width=20, height=20)
        self.exit_icon.bgcolor = ft.colors.WHITE if self.tema_oscuro else ft.colors.BLACK
        self.exit_label.value = "Salir"
        self.exit_label.visible = self.expandido
        self.exit_label.color = ft.colors.WHITE
        self.btn_exit.content.bgcolor = ft.colors.GREY_800 if self.tema_oscuro else ft.colors.GREY_300

        # Refrescar UI
        self.page.update()

    def toggle_nav(self, e=None):
        """Expande o contrae la barra lateral"""
        self.expandido = not self.expandido
        self.width = 250 if self.expandido else 80
        self._refresh_all()

    def toggle_tema(self, e=None):
        """Alterna tema oscuro/claro"""
        self.tema_oscuro = not self.tema_oscuro
        self.page.client_storage.set("tema_oscuro", self.tema_oscuro)
        self._refresh_all()

    def exit_app(self, e=None):
        """Cierra la aplicación"""
        self.page.window_close()

    # Navegación delegada a WindowMain.route_change vía page.go()
    # No se necesita método interno de navegar aquí
