import flet as ft


class MenuButton(ft.Container):
    def __init__(self, texto: str, icono: str, ruta: str, nav_bar):
        self.nav_bar = nav_bar
        self.expandido = nav_bar.expandido

        self.texto = ft.Text(
            value=texto,
            visible=self.expandido,
            size=12,
            color=ft.colors.WHITE if nav_bar.tema_oscuro else ft.colors.BLACK
        )

        self.icono_container = ft.Container(
            bgcolor=ft.colors.WHITE if nav_bar.tema_oscuro else ft.colors.BLACK,
            border_radius=6,
            padding=6,
            content=ft.Image(src=icono, width=20, height=20)
        )

        fila = ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[self.icono_container, self.texto]
        )

        super().__init__(
            bgcolor=ft.colors.GREY_800 if nav_bar.tema_oscuro else ft.colors.GREY_300,
            border_radius=8,
            padding=10,
            content=fila,
            on_click=lambda _: nav_bar.navegar(ruta)
        )

    def update(self):
        self.expandido = self.nav_bar.expandido
        self.texto.visible = self.expandido
        self.texto.color = ft.colors.WHITE if self.nav_bar.tema_oscuro else ft.colors.BLACK
        self.bgcolor = ft.colors.GREY_800 if self.nav_bar.tema_oscuro else ft.colors.GREY_300
        self.icono_container.bgcolor = ft.colors.WHITE if self.nav_bar.tema_oscuro else ft.colors.BLACK
