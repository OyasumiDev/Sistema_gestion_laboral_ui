import flet as ft

class WindowSnackbar:
    def __init__(self, page: ft.Page):
        self.page = page
        self.snackbar = ft.SnackBar(
            content=ft.Text(""),
            bgcolor=ft.colors.GREEN_200,
            behavior=ft.SnackBarBehavior.FLOATING,
            duration=3000
        )
        self.page.snack_bar = self.snackbar

    def show_success(self, message: str):
        self.snackbar.content = ft.Text(message)
        self.snackbar.bgcolor = ft.colors.GREEN_200
        self.snackbar.open = True
        self.page.update()

    def show_error(self, message: str):
        self.snackbar.content = ft.Text(message)
        self.snackbar.bgcolor = ft.colors.RED_400
        self.snackbar.open = True
        self.page.update()
