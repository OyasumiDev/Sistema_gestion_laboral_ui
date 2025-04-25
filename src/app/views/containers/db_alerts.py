import flet as ft
from app.core.app_state import AppState
from app.core.interfaces.database_mysql import DatabaseMysql

class DBAlerts:
    """Alertas iniciales de configuración de BD en el login."""
    def __init__(self):
        self.page = AppState().page
        self.db = DatabaseMysql()
        self.file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.page.overlay.append(self.file_picker)

    def show(self):
        mensaje = (
            "Usted no cuenta con datos, ¿desea importar una base de datos?"
            if self.db.is_empty()
            else
            "Usted ya cuenta con una configuración de base de datos; "
            "si importa otra, será reemplazada. ¿Desea continuar?"
        )
        dialog = ft.AlertDialog(
            title=ft.Text("Configuración BD"),
            content=ft.Text(mensaje),
            actions=[
                ft.TextButton(text="Sí", on_click=self._on_yes),
                ft.TextButton(text="No", on_click=self._on_no)
            ]
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _on_yes(self, e: ft.ControlEvent):
        self.page.dialog.open = False
        self.page.update()
        self.file_picker.pick_files(allow_multiple=False)

    def _on_no(self, e: ft.ControlEvent):
        # Cierra la ventana principal
        self.page.window.close()

    def _on_file_picked(self, e: ft.FilePickerResultEvent):
        try:
            sql_file = e.files[0].path
            self.db.import_db(sql_file)
            self.page.snack_bar = ft.SnackBar(ft.Text("Base de datos importada correctamente."))
            self.page.snack_bar.open = True
            self.page.update()
            # Cierre para reiniciar con nueva configuración
            self.page.window.close()
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"Error al importar: {ex}"))
            self.page.snack_bar.open = True
            self.page.update()