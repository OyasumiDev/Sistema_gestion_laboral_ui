import flet as ft

def create_confirm_exit_dialog(on_confirm, on_cancel):
    return ft.AlertDialog(
        modal=True,
        title=ft.Text("¿Deseas salir de la aplicación?"),
        actions=[
            ft.TextButton("Sí", on_click=on_confirm),
            ft.TextButton("No", on_click=on_cancel)
        ],
        actions_alignment=ft.MainAxisAlignment.CENTER
    )
