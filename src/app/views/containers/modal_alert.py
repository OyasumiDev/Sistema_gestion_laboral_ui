import flet as ft
from app.core.app_state import AppState

class ModalAlert:
    def __init__(
        self,
        title_text: str,
        message: str,
        on_confirm: callable = None,
        on_cancel: callable = None,
        only_info: bool = False
    ):
        self.page = AppState().page
        self.only_info = only_info
        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(title_text, weight="bold"),
            content=ft.Text(message),
            actions_alignment=ft.MainAxisAlignment.END,
            actions=self._build_actions(),
            on_dismiss=lambda _: self.page.update()
        )
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

    def _build_actions(self):
        if self.only_info:
            return [
                ft.ElevatedButton("Cerrar", on_click=self._cerrar_info)
            ]
        else:
            return [
                ft.TextButton("Cancelar", on_click=self._cancelar),
                ft.ElevatedButton("Aceptar", on_click=self._aceptar)
            ]

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

    def _cerrar_info(self, e):
        self.dialog.open = False
        self.page.update()
        print("ℹ️ Modal informativo cerrado")

    @staticmethod
    def mostrar_info(titulo: str, mensaje: str):
        modal = ModalAlert(title_text=titulo, message=mensaje, only_info=True)
        modal.mostrar()

    @staticmethod
    def confirm_async(title: str, message: str, *, on_confirm=None, on_cancel=None):
        # CHANGE: helper compacto para reutilizar confirmaciones en flujo Pagos
        modal = ModalAlert(
            title_text=title,
            message=message,
            on_confirm=on_confirm,
            on_cancel=on_cancel,
            only_info=False,
        )
        modal.mostrar()
        return modal
