# 🌟 Mejoras aplicadas a SettingsNavBarContainer (y plan para NavBarContainer)

import flet as ft
from app.core.app_state import AppState
from app.views.containers.theme_controller import ThemeController
from app.views.containers.layout_controller import LayoutController
from app.views.containers.user_icon_area import UserIconArea
from app.views.containers.menu_buttons_area import MenuButtonsArea  # Home usa esto, Settings no
from app.views.containers.control_buttons_area import ControlButtonsArea

class SettingsNavBarContainer(ft.Container):
    def __init__(self):
        super().__init__(padding=10)

        # Singletons
        self.page = AppState().page
        self.theme_ctrl = ThemeController()
        self.layout_ctrl = LayoutController()

        # Inicializar construccion
        self.build()

    def build(self):
        colors = self.theme_ctrl.get_colors()
        expanded = self.layout_ctrl.expandido

        self.bgcolor = colors["BG_COLOR"]
        self.width = 250 if expanded else 80

        # Avatar
        avatar_area = UserIconArea(
            is_root=True,
            accent=colors["AVATAR_ACCENT"],
            nav_width=self.width,
            height=64
        )

        # Botones menu SOLO para settings (Return y Database)
        btn_return = ft.GestureDetector(
            on_tap=self._on_return,
            content=ft.Container(
                bgcolor=colors["BTN_BG"],
                padding=6,
                border_radius=6,
                content=ft.Image(src="assets/buttons/return-button.png", width=24, height=24)
            )
        )

        btn_database = ft.GestureDetector(
            on_tap=self._on_database,
            content=ft.Container(
                bgcolor=colors["BTN_BG"],
                padding=6,
                border_radius=6,
                content=ft.Image(src="assets/buttons/database-button.png", width=24, height=24)
            )
        )

        menu_area = ft.Column(
            controls=[
                btn_return,
                ft.Text("Return", size=12, visible=expanded, color=colors["FG_COLOR"]),
                ft.Divider(thickness=1, color=colors["DIVIDER_COLOR"]),
                btn_database,
                ft.Text("Database", size=12, visible=expanded, color=colors["FG_COLOR"])
            ],
            spacing=16,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )

        # Control buttons abajo (sin Settings)
        control_area = ControlButtonsArea(
            expanded=expanded,
            dark=self.theme_ctrl.tema_oscuro,
            on_toggle_nav=self._on_toggle_nav,
            on_toggle_theme=self._on_toggle_theme,
            on_settings=lambda e: None,  # Settings oculto
            on_exit=lambda e: self.page.window.close(),
            bg=colors["BTN_BG"],
            mostrar_settings=False  # 🔍 Aqui FORZAMOS que NO aparezca el boton Settings
        )

        self.content = ft.Column(
            controls=[
                avatar_area,
                ft.Divider(thickness=1, color=colors["DIVIDER_COLOR"]),
                menu_area,
                ft.Container(expand=True),
                control_area
            ],
            spacing=16
        )

    def _on_return(self, e):
        self.page.go("/home")

    def _on_database(self, e):
        self.page.go("/settings/db")

    def _on_toggle_nav(self, e):
        self.layout_ctrl.toggle()
        self.build()
        self.page.update()

    def _on_toggle_theme(self, e):
        self.theme_ctrl.toggle()
        self.build()
        self.page.update()
