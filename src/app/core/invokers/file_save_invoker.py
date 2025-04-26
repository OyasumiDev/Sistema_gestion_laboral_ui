import flet as ft
from flet import FilePicker, FilePickerResultEvent

class FileSaveInvoker:
    """
    Módulo genérico para guardar un archivo via diálogo nativo.
    - on_save: callback que recibe la ruta destino.
    - file_name: nombre por defecto para el archivo.
    - allowed_extensions: lista de extensiones permitidas (sin punto).
    """
    def __init__(self,
                page: ft.Page,
                on_save: callable,
                dialog_title: str = "Guardar archivo",
                file_name: str | None = None,
                initial_directory: str | None = None,
                allowed_extensions: list[str] | None = None):
        self.page = page
        self.on_save = on_save
        # Configurar FilePicker en modo "save"
        self.picker = FilePicker(
            on_result=self._on_result,
            dialog_title=dialog_title,
            file_name=file_name or "",
            initial_directory=initial_directory or "",
            allowed_extensions=allowed_extensions or []
        )
        self.page.overlay.append(self.picker)

    def open(self) -> None:
        """Muestra el diálogo para guardar archivo."""
        self.picker.save_file()
        self.page.update()

    def _on_result(self, e: FilePickerResultEvent) -> None:
        # Remover picker
        try:
            self.page.overlay.remove(self.picker)
        except ValueError:
            pass
        self.page.update()
        # Si canceló, nothing
        if not e.path:
            return
        # callback con ruta destino
        self.on_save(e.path)
