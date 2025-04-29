import flet as ft
from flet import FilePicker, FilePickerResultEvent

class FileSaveInvoker:
    def __init__(
        self,
        page: ft.Page,
        on_save: callable,
        on_import: callable,
        save_dialog_title: str = "Guardar archivo",
        import_dialog_title: str = "Importar archivo",
        file_name: str | None = None,
        initial_directory: str | None = None,
        allowed_extensions: list[str] | None = None,
        import_extensions: list[str] | None = None
    ):
        self.page = page
        self.on_save = on_save
        self.on_import = on_import
        self.save_dialog_title = save_dialog_title
        self.import_dialog_title = import_dialog_title
        self.file_name = file_name or ""
        self.initial_directory = initial_directory or ""
        self.allowed_extensions = allowed_extensions or []
        self.import_extensions = import_extensions or []

        self.save_picker = FilePicker(on_result=self._on_save_result)
        self.import_picker = FilePicker(on_result=self._on_import_result)

        self.page.overlay.append(self.save_picker)
        self.page.overlay.append(self.import_picker)

    def open_save(self) -> None:
        self.save_picker.save_file(
            dialog_title=self.save_dialog_title,
            file_name=self.file_name,
            initial_directory=self.initial_directory,
            allowed_extensions=[ext.lower().lstrip(".") for ext in self.allowed_extensions]
        )
        self.page.update()

    def open_import(self) -> None:
        self.import_picker.pick_files(
            dialog_title=self.import_dialog_title,
            allow_multiple=False,
            allowed_extensions=[ext.lower().lstrip(".") for ext in self.import_extensions]
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
        self.on_import(e.files[0].path)

    def get_import_button(self, text: str = "Importar archivo", icon_path: str = "assets/buttons/import_database-button.png") -> ft.ElevatedButton:
        return ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Image(src=icon_path, width=24, height=24),
                    ft.Text(text),
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER
            ),
            on_click=lambda _: self.open_import()
        )
