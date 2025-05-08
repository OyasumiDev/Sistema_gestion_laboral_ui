import flet as ft
from flet import FilePicker, FilePickerResultEvent
from app.core.interfaces.database_mysql import DatabaseMysql


class FileSaveInvoker:
    def __init__(
        self,
        page: ft.Page,
        on_save: callable = None,
        on_import: callable = None,
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
        self.file_name = file_name or "backup.sql"
        self.initial_directory = initial_directory or ""
        self.allowed_extensions = allowed_extensions or []
        self.import_extensions = import_extensions or []

        self.db = DatabaseMysql()

        self.save_picker = FilePicker(on_result=self._on_save_result)
        self.import_picker = FilePicker(on_result=self._on_import_result)

        self._safe_append_overlay(self.save_picker)
        self._safe_append_overlay(self.import_picker)

    def _safe_append_overlay(self, picker: FilePicker):
        if self.page and hasattr(self.page, "overlay"):
            if picker not in self.page.overlay:
                self.page.overlay.append(picker)

    def open_save(self) -> None:
        self._safe_append_overlay(self.save_picker)
        self.page.update()
        self.save_picker.save_file(
            dialog_title=self.save_dialog_title,
            file_name=self.file_name,
            initial_directory=self.initial_directory,
            allowed_extensions=[ext.lower().lstrip(".") for ext in self.allowed_extensions]
        )

    def open_import(self) -> None:
        self._safe_append_overlay(self.import_picker)
        self.page.update()
        self.import_picker.pick_files(
            dialog_title=self.import_dialog_title,
            allow_multiple=False,
            allowed_extensions=[ext.lower().lstrip(".") for ext in self.import_extensions]
        )

    def _on_save_result(self, e: FilePickerResultEvent) -> None:
        if e.path:
            success = self.db.exportar_base_datos(e.path)
            msg = (
                "✅ Base de datos exportada exitosamente."
                if success else
                "⚠️ No se pudo exportar la base de datos."
            )
            self.page.snack_bar = ft.SnackBar(ft.Text(msg))
            self.page.snack_bar.open = True
            self.page.update()

            if self.on_save:
                self.on_save(e.path)

    def _on_import_result(self, e: FilePickerResultEvent) -> None:
        if e.files and e.files[0].path:
            path = e.files[0].path
            success = self.db.importar_base_datos(path)
            msg = (
                f"✅ Base de datos importada correctamente desde: {path}"
                if success else
                f"❌ No se pudo importar la base de datos desde: {path}"
            )
            print(msg)
            self.page.snack_bar = ft.SnackBar(ft.Text(msg))
            self.page.snack_bar.open = True
            self.page.update()

            if self.on_import:
                self.on_import(path)

    def get_import_button(self, text="Importar archivo", icon_path="assets/buttons/import_database-button.png") -> ft.ElevatedButton:
        return ft.ElevatedButton(
            content=ft.Row(
                controls=[ft.Image(src=icon_path, width=24, height=24), ft.Text(text)],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            on_click=lambda _: self.open_import()
        )

    def get_save_button(self, text="Guardar archivo", icon_path="assets/buttons/save-database-button.png") -> ft.OutlinedButton:
        return ft.OutlinedButton(
            content=ft.Row(
                controls=[ft.Image(src=icon_path, width=24, height=24), ft.Text(text)],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            on_click=lambda _: self.open_save()
        )
