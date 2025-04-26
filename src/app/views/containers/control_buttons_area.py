# app/views/containers/control_buttons_area.py

import flet as ft

class ControlButtonsArea(ft.Column):
    def __init__(
        self,
        expanded: bool,
        dark: bool,
        on_toggle_nav,
        on_toggle_theme,
        on_settings,
        on_exit,
        bg: str,
        mostrar_settings: bool = True,
        mostrar_theme: bool = True
    ):
        super().__init__(spacing=10)

        self.expanded = expanded
        self.dark = dark
        self.on_toggle_nav = on_toggle_nav
        self.on_toggle_theme = on_toggle_theme
        self.on_settings = on_settings
        self.on_exit = on_exit
        self.bg = bg
        self.mostrar_settings = mostrar_settings
        self.mostrar_theme = mostrar_theme

        self._build()

    def _build(self):
        # Decidir qué imagen mostrar para expandir/contraer
        expand_icon = "assets/buttons/layout_close-button.png" if self.expanded else "assets/buttons/layout_open-button.png"
        
        btn_expand = ft.GestureDetector(
            on_tap=self.on_toggle_nav,
            content=ft.Container(
                bgcolor=self.bg,
                padding=6,
                border_radius=6,
                content=ft.Image(
                    src=expand_icon,
                    width=24,
                    height=24
                )
            )
        )

        # Botón cambiar tema
        theme_icon = "assets/buttons/light-color-button.png" if self.dark else "assets/buttons/dark-color-button.png"
        
        btn_theme = ft.GestureDetector(
            on_tap=self.on_toggle_theme,
            content=ft.Container(
                bgcolor=self.bg,
                padding=6,
                border_radius=6,
                content=ft.Image(
                    src=theme_icon,
                    width=24,
                    height=24
                )
            )
        ) if self.mostrar_theme else None

        # Botón settings
        btn_settings = ft.GestureDetector(
            on_tap=self.on_settings,
            content=ft.Container(
                bgcolor=self.bg,
                padding=6,
                border_radius=6,
                content=ft.Image(
                    src="assets/buttons/settings-button.png",
                    width=24,
                    height=24
                )
            )
        ) if self.mostrar_settings else None

        # Botón salir
        btn_exit = ft.GestureDetector(
            on_tap=self.on_exit,
            content=ft.Container(
                bgcolor=self.bg,
                padding=6,
                border_radius=6,
                content=ft.Image(
                    src="assets/buttons/exit-button.png",
                    width=24,
                    height=24
                )
            )
        )

        controls = [btn_expand]
        if btn_theme:
            controls.append(btn_theme)
        if btn_settings:
            controls.append(btn_settings)
        controls.append(btn_exit)

        self.controls = controls
