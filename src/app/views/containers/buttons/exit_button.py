import flet as ft


def ExitButton(expandido: bool, salir_fn) -> ft.GestureDetector:
    """Botón para salir de la aplicación."""
    etiqueta = "Salir" if expandido else ""
    label = ft.Text(etiqueta, visible=expandido, size=12, color=ft.colors.WHITE)

    return ft.GestureDetector(
        on_tap=salir_fn,
        content=ft.Container(
            bgcolor=ft.colors.GREY_800,
            padding=10,
            border_radius=8,
            content=ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        bgcolor=ft.colors.WHITE,
                        border_radius=6,
                        padding=6,
                        content=ft.Image(
                            src="button's/exit-button.png", width=20, height=20
                        )
                    ),
                    label
                ]
            )
        )
    )