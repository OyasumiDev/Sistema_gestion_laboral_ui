import flet as ft



class ThemeToggleButton(ft.GestureDetector):
    def __init__(self, nav_bar):
        self.nav_bar = nav_bar
        self.expandido = nav_bar.expandido
        self.tema_oscuro = nav_bar.tema_oscuro

        icono = "light-color-button.png" if self.tema_oscuro else "dark-color-button.png"
        etiqueta = "Cambiar tema" if self.expandido else ""

        self.label = ft.Text(
            value=etiqueta,
            visible=self.expandido,
            size=12,
            color=ft.colors.WHITE if self.tema_oscuro else ft.colors.BLACK
        )

        self.icono_container = ft.Container(
            bgcolor=ft.colors.WHITE if self.tema_oscuro else ft.colors.BLACK,
            border_radius=6,
            padding=6,
            content=ft.Image(
                src=f"button's/{icono}", width=20, height=20
            )
        )

        content = ft.Container(
            bgcolor=ft.colors.GREY_800 if self.tema_oscuro else ft.colors.GREY_300,
            padding=10,
            border_radius=8,
            content=ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[self.icono_container, self.label]
            )
        )

        super().__init__(
            on_tap=self.toggle_tema,
            content=content
        )

    def toggle_tema(self, e):
        self.nav_bar.toggle_tema()

    def update(self):
        self.expandido = self.nav_bar.expandido
        self.tema_oscuro = self.nav_bar.tema_oscuro

        icono = "light-color-button.png" if self.tema_oscuro else "dark-color-button.png"
        self.label.value = "Cambiar tema" if self.expandido else ""
        self.label.visible = self.expandido
        self.label.color = ft.colors.WHITE if self.tema_oscuro else ft.colors.BLACK
        self.icono_container.content.src = f"button's/{icono}"
        self.icono_container.bgcolor = ft.colors.WHITE if self.tema_oscuro else ft.colors.BLACK
        self.content.bgcolor = ft.colors.GREY_800 if self.tema_oscuro else ft.colors.GREY_300
