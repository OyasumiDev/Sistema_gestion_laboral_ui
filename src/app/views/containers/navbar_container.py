# app/views/containers/navbar_container.py

import flet as ft
from app.core.app_state import AppState
from app.views.containers.theme_controller import ThemeController
from app.views.containers.layout_controller import LayoutController
from app.views.containers.user_icon_area import UserIconArea
from app.views.containers.menu_buttons_area import MenuButtonsArea
from app.views.containers.control_buttons_area import ControlButtonsArea

class NavBarContainer(ft.Container):
    def __init__(self, is_root: bool = False, modo_settings: bool = False):
        super().__init__(padding=10)

        self.page = AppState().page
        self.is_root = is_root
        self.modo_settings = modo_settings

        self.theme_ctrl = ThemeController()
        self.layout_ctrl = LayoutController()

        self._build()

    def _build(self):
        expanded = self.layout_ctrl.expandido
        colors = self.theme_ctrl.get_colors()

        self.width = 250 if expanded else 80

        self.bgcolor = colors["BG_COLOR"]

        avatar_area = UserIconArea(
            is_root=self.is_root,
            accent=colors["AVATAR_ACCENT"],  # Siempre usa el color dinámico
            nav_width=self.width,
            height=64
        )

        if self.modo_settings:
            menu_area = self._build_settings_menu(expanded, colors)
        else:
            menu_area = MenuButtonsArea(
                is_root=self.is_root,
                expanded=expanded,
                fg=colors["FG_COLOR"],
                btn_bg=colors["BTN_BG"]
            )

        control_area = ControlButtonsArea(
            expanded=expanded,
            dark=self.theme_ctrl.tema_oscuro,
            on_toggle_nav=self._on_toggle_nav,
            on_toggle_theme=(self._on_toggle_theme if not self.modo_settings else None),
            on_settings=(lambda e: None) if self.modo_settings else self._on_settings,
            on_exit=lambda e: self.page.window.close(),
            bg=colors["BTN_BG"],
            mostrar_settings=not self.modo_settings,
            mostrar_theme=not self.modo_settings
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

    def _build_settings_menu(self, expanded: bool, colors: dict) -> ft.Column:
        """Menu especial para Settings (usando FG_COLOR igual que Home)."""

        btn_return = ft.GestureDetector(
            on_tap=self._on_return,
            content=ft.Container(
                bgcolor=colors["BTN_BG"],
                padding=6,
                border_radius=6,
                content=ft.Row(
                    controls=[
                        ft.Image(src="assets/buttons/return-button.png", width=24, height=24),
                        ft.Text("Return", size=12, visible=expanded, color=colors["FG_COLOR"])
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                )
            )
        )

        btn_database = ft.GestureDetector(
            on_tap=self._on_database,
            content=ft.Container(
                bgcolor=colors["BTN_BG"],
                padding=6,
                border_radius=6,
                content=ft.Row(
                    controls=[
                        ft.Image(src="assets/buttons/database-button.png", width=24, height=24),
                        ft.Text("Database", size=12, visible=expanded, color=colors["FG_COLOR"])
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                )
            )
        )

        return ft.Column(
            controls=[
                btn_return,
                btn_database
            ],
            spacing=10
        )

    def _on_toggle_nav(self, e):
        self.layout_ctrl.toggle()
        self._build()
        self.page.update()

    def _on_toggle_theme(self, e):
        self.theme_ctrl.toggle()
        self._build()
        self.page.update()

    def _on_settings(self, e):
        self.page.go("/settings")
        self.page.update()

    def _on_return(self, e):
        self.page.go("/home")

    def _on_database(self, e):
        self.page.go("/settings/db")