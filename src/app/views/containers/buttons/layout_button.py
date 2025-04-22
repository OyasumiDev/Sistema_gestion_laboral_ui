import flet as ft

def LayoutToggleButton(expandido: bool, toggle_fn) -> ft.GestureDetector:
    """Botón para expandir o comprimir el layout."""
    icono = "layout_close-button.png" if expandido else "layout_open-button.png"
    etiqueta = "Comprimir layout" if expandido else ""

    label = ft.Text(etiqueta, visible=expandido, size=12, color=ft.colors.WHITE)

    return ft.GestureDetector(
        on_tap=toggle_fn,
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
                            src=f"button's/{icono}", width=20, height=20
                        )
                    ),
                    label
                ]
            )
        )
    )