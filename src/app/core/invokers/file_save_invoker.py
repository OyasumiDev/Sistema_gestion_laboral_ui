import flet as ft
from flet import FilePicker, FilePickerResultEvent
from app.helpers.class_singleton import class_singleton

@class_singleton
class FileSaveInvoker:
    def __init__(
        self,
        page: ft.Page,
        on_save: callable,
        on_import: callable,
        dialog_title: str = "Guardar archivo",
        file_name: str | None = None,
        initial_directory: str | None = None,
        allowed_extensions: list[str] | None = None,
        import_extensions: list[str] | None = None
    ):
        self.page = page
        self.on_save = on_save
        self.on_import = on_import
        self.dialog_title = dialog_title
        self.file_name = file_name or ""
        self.initial_directory = initial_directory or ""
        self.allowed_extensions = allowed_extensions or []
        self.import_extensions = import_extensions or ["sql", "db", "bak"]

        # Picker para guardar archivo
        self.save_picker = FilePicker(on_result=self._on_save_result)

        # Picker para importar archivo
        self.import_picker = FilePicker(on_result=self._on_import_result)

        self.page.overlay.append(self.save_picker)
        self.page.overlay.append(self.import_picker)

    def open_save(self) -> None:
        """Muestra el diálogo para guardar archivo."""
        self.save_picker.save_file(
            dialog_title=self.dialog_title,
            file_name=self.file_name,
            initial_directory=self.initial_directory,
            allowed_extensions=self.allowed_extensions
        )
        self.page.update()

    def open_import(self) -> None:
        """Muestra el diálogo para importar archivo."""
        self.import_picker.pick_files(
            dialog_title="Importar Base de Datos",
            allow_multiple=False,
            allowed_extensions=self.import_extensions
        )
        self.page.update()

    def _on_save_result(self, e: FilePickerResultEvent) -> None:
        try:
            self.page.overlay.remove(self.save_picker)
        except ValueError:
            pass
        self.page.update()
        if not e.path:
            return
        self.on_save(e.path)

    def _on_import_result(self, e: FilePickerResultEvent) -> None:
        try:
            self.page.overlay.remove(self.import_picker)
        except ValueError:
            pass
        self.page.update()
        if not e.files:
            return
        # archivo seleccionado
        self.on_import(e.files[0].path)

    def get_import_button(self) -> ft.ElevatedButton:
        """Devuelve un botón que abre el diálogo de importar archivo."""
        return ft.ElevatedButton(
            text="Importar Base de Datos",
            icon=ft.icons.UPLOAD_FILE,
            on_click=lambda _: self.open_import()
        )
