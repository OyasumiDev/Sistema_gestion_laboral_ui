# app/views/containers/navbar_container.py

import flet as ft
from app.core.app_state import AppState
from app.views.containers.theme_controller import ThemeController
from app.views.containers.layout_controller import LayoutController

from app.views.containers.user_icon_area import UserIconArea
from app.views.containers.menu_buttons_area import MenuButtonsArea
from app.views.containers.control_buttons_area import ControlButtonsArea

class NavBarContainer(ft.Container):
    def __init__(self, is_root: bool = False):
        self.page = AppState().page
        self.is_root = is_root

        # Singletons
        self.theme_ctrl = ThemeController()
        self.layout_ctrl = LayoutController()

        super().__init__(padding=10)
        self._build()

    def _build(self):
        expanded = self.layout_ctrl.expandido

        # Obtener colores actualizados según tema
        colors = self.theme_ctrl.get_colors()
        BG_COLOR       = colors["BG_COLOR"]
        FG_COLOR       = colors["FG_COLOR"]
        AVATAR_ACCENT  = colors["AVATAR_ACCENT"]
        DIVIDER_COLOR  = colors["DIVIDER_COLOR"]
        BTN_BG         = colors["BTN_BG"]

        self.width = 250 if expanded else 80
        self.bgcolor = BG_COLOR

        # Áreas de la NavBar
        avatar_area = UserIconArea(
            is_root=self.is_root,
            accent=AVATAR_ACCENT,
            nav_width=self.width,
            height=64
        )

        menu_area = MenuButtonsArea(
            is_root=self.is_root,
            expanded=expanded,
            fg=FG_COLOR,
            btn_bg=BTN_BG
        )

        control_area = ControlButtonsArea(
            expanded=expanded,
            dark=self.theme_ctrl.tema_oscuro,
            on_toggle_nav=self._on_toggle_nav,
            on_toggle_theme=self._on_toggle_theme,
            on_settings=self._on_settings,   # <== este nuevo parámetro!
            on_exit=lambda e: self.page.window.close(),
            bg=BTN_BG
        )


        self.content = ft.Column(
            controls=[
                avatar_area,
                ft.Divider(thickness=1, color=DIVIDER_COLOR),
                menu_area,
                ft.Container(expand=True),
                control_area
            ],
            spacing=16
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
