import flet as ft
from flet import FilePicker, FilePickerResultEvent

class FileOpenInvoker:
    """
    Módulo genérico para seleccionar un archivo via diálogo nativo.
    - on_select: callback que recibe la ruta seleccionada.
    - allowed_extensions: lista de extensiones permitidas (sin punto).
    """
    def __init__(self,
                page: ft.Page,
                on_select: callable,
                dialog_title: str = "Selecciona un archivo",
                allowed_extensions: list[str] | None = None):
        self.page = page
        self.on_select = on_select
        # Configurar FilePicker
        self.picker = FilePicker(
            on_result=self._on_result,
            dialog_title=dialog_title,
            allowed_extensions=allowed_extensions or []
        )
        # Agregar al overlay para no afectar layout
        self.page.overlay.append(self.picker)

    def open(self) -> None:
        """Muestra el diálogo de selección de archivo."""
        self.picker.pick_files(allow_multiple=False)
        self.page.update()

    def _on_result(self, e: FilePickerResultEvent) -> None:
        # Remover picker del overlay
        try:
            self.page.overlay.remove(self.picker)
        except ValueError:
            pass
        self.page.update()
        # Si canceló, nada
        if not e.files:
            return
        # Llamar callback con la ruta del primer archivo
        selected = e.files[0].path
        self.on_select(selected)