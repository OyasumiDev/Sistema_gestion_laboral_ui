import flet as ft
from app.core.app_state import AppState

class ModalAlert:
    def __init__(
        self,
        title_text: str,
        message: str,
        on_confirm: callable = None,
        on_cancel: callable = None,
    ):
        self.page = AppState().page
        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(title_text, weight="bold"),
            content=ft.Text(message),
            actions_alignment=ft.MainAxisAlignment.END,
            actions=[
                ft.TextButton("Cancelar", on_click=self._cancelar),
                ft.ElevatedButton("Aceptar", on_click=self._aceptar)
            ],
            on_dismiss=lambda _: self.page.update()
        )
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

    def mostrar(self):
        print("📢 ModalAlert: mostrando alerta en la página")
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()


    def _aceptar(self, e):
        self.dialog.open = False
        self.page.update()
        if self.on_confirm:
            print("✅ Acción confirmada desde ModalAlert")
            self.on_confirm()

    def _cancelar(self, e):
        self.dialog.open = False
        self.page.update()
        if self.on_cancel:
            print("❌ Acción cancelada desde ModalAlert")
            self.on_cancel()
