import flet as ft

class ControlButtonsArea(ft.Column):
    def __init__(
        self,
        expanded: bool,
        dark: bool,
        on_toggle_nav,
        on_toggle_theme,
        on_exit,
        bg: str
    ):
        # Toggle layout
        layout_file = "layout_close-button.png" if expanded else "layout_open-button.png"
        btn_layout = ft.GestureDetector(
            on_tap=on_toggle_nav,
            content=ft.Container(
                bgcolor=bg,
                padding=6,
                border_radius=6,
                content=ft.Image(
                    src=f"assets/buttons/{layout_file}",
                    width=24,
                    height=24
                )
            )
        )

        # Toggle tema
        theme_file = "light-color-button.png" if dark else "dark-color-button.png"
        btn_theme = ft.GestureDetector(
            on_tap=on_toggle_theme,
            content=ft.Container(
                bgcolor=bg,
                padding=6,
                border_radius=6,
                content=ft.Image(
                    src=f"assets/buttons/{theme_file}",
                    width=24,
                    height=24
                )
            )
        )

        # Salir
        btn_exit = ft.GestureDetector(
            on_tap=on_exit,
            content=ft.Container(
                bgcolor=bg,
                padding=6,
                border_radius=6,
                content=ft.Image(
                    src="assets/buttons/exit-button.png",
                    width=24,
                    height=24
                )
            )
        )

        super().__init__(
            spacing=16,
            controls=[btn_layout, btn_theme, btn_exit]
        )
