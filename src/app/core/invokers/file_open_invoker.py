import flet as ft
from flet import FilePicker, FilePickerResultEvent

class FileOpenInvoker:
    """
    Módulo genérico para seleccionar un archivo desde diálogo nativo.
    - `on_select`: callback que recibe la ruta seleccionada.
    - `allowed_extensions`: lista de extensiones permitidas (sin punto).
    """
    def __init__(
        self,
        page: ft.Page,
        on_select: callable,
        dialog_title: str = "Selecciona un archivo",
        allowed_extensions: list[str] | None = None,
    ):
        self.page = page
        self.on_select = on_select
        self.dialog_title = dialog_title
        self.allowed_extensions = allowed_extensions or []

        self.picker = FilePicker(on_result=self._on_result)

        if self.picker not in self.page.overlay:
            self.page.overlay.append(self.picker)

    def open(self) -> None:
        """Abre el diálogo para seleccionar un archivo."""
        if self.picker not in self.page.overlay:
            self.page.overlay.append(self.picker)
            self.page.update()

        self.picker.pick_files(
            dialog_title=self.dialog_title,
            allow_multiple=False,
            allowed_extensions=[
                ext.lower().lstrip(".") for ext in self.allowed_extensions
            ]
        )

    def _on_result(self, e: FilePickerResultEvent) -> None:
        if not e.files:
            return

        selected = e.files[0].path
        self.on_select(selected)

    def get_open_button(
        self,
        text: str = "Abrir archivo",
        icon_path: str = "assets/buttons/open_file-button.png"
    ) -> ft.ElevatedButton:
        return ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Image(src=icon_path, width=24, height=24),
                    ft.Text(text),
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER
            ),
            on_click=lambda _: self.open()
        )
