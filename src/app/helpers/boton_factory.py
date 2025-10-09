import flet as ft
from typing import Callable


class BotonFactory:
    """
    Fábrica de botones:
    - Acciones de fila (editar, eliminar, guardar, cancelar) -> IconButton
    - Botones de header (importar, exportar, agregar, agregar fechas pagadas) -> 'pill buttons'
    """

    def __init__(self):
        pass

    # ------------------------
    #  Internos reutilizables
    # ------------------------
    def _pill_button(
        self,
        text: str,
        on_tap: Callable,
        *,
        img_src: str | None = None,
        icon_name: str | None = None,
    ) -> ft.GestureDetector:
        """
        Crea un botón tipo 'pastilla' consistente con EmpleadosContainer.
        Usa imagen si se provee; si no, usa un icono Flet.
        """
        content_row: list[ft.Control] = []
        if img_src:
            content_row.append(ft.Image(src=img_src, width=20, height=20))
        elif icon_name:
            content_row.append(ft.Icon(name=icon_name, size=20))

        content_row.append(ft.Text(text, size=11, weight="bold"))

        return ft.GestureDetector(
            on_tap=lambda _: on_tap(),
            content=ft.Container(
                padding=8,
                border_radius=12,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=ft.Row(
                    content_row,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=5,
                ),
            ),
        )

    def crear_boton_accion(self, icon_name: str, tooltip: str, color: str, on_click: Callable) -> ft.IconButton:
        return ft.IconButton(
            icon=icon_name,
            icon_size=20,
            icon_color=color,
            tooltip=tooltip,
            on_click=on_click,
        )

    # ------------------------
    #  Acciones de fila
    # ------------------------
    def crear_boton_editar(self, on_click: Callable) -> ft.IconButton:
        return self.crear_boton_accion(ft.icons.EDIT, "Editar registro", ft.colors.BLUE_600, on_click)

    def crear_boton_eliminar(self, on_click: Callable) -> ft.IconButton:
        return self.crear_boton_accion(ft.icons.DELETE_OUTLINE, "Eliminar registro", ft.colors.RED_600, on_click)

    def crear_boton_guardar(self, on_click: Callable) -> ft.IconButton:
        return self.crear_boton_accion(ft.icons.SAVE, "Guardar cambios", ft.colors.GREEN_600, on_click)

    def crear_boton_cancelar(self, on_click: Callable) -> ft.IconButton:
        return self.crear_boton_accion(ft.icons.CANCEL, "Cancelar acción", ft.colors.GREY_700, on_click)

    # ------------------------
    #  Botones de header (pill)
    # ------------------------
    def crear_boton_importar(self, on_click: Callable) -> ft.GestureDetector:
        return self._pill_button(
            "Importar",
            on_click,
            img_src="assets/buttons/import-button.png",
        )

    def crear_boton_exportar(self, on_click: Callable) -> ft.GestureDetector:
        return self._pill_button(
            "Exportar",
            on_click,
            img_src="assets/buttons/export-button.png",
        )

    def crear_boton_agregar(self, on_click: Callable) -> ft.GestureDetector:
        return self._pill_button(
            "Agregar",
            on_click,
            icon_name=ft.icons.ADD,
        )

    def crear_boton_agregar_fechas_pagadas(self, on_click: Callable) -> ft.GestureDetector:
        """
        Nuevo botón 'pill' para abrir el modal de 'Agregar fechas pagadas'.
        Coincide visualmente con Importar/Exportar/Agregar.
        """
        return self._pill_button(
            "Agregar fechas pagadas",
            on_click,
            icon_name=ft.icons.CALENDAR_MONTH,  # calendario para distinguirlo del resto
        )


# Instancia única de la fábrica para helpers
_factory = BotonFactory()

def crear_boton_editar(on_click: Callable):
    return _factory.crear_boton_editar(on_click)

def crear_boton_eliminar(on_click: Callable):
    return _factory.crear_boton_eliminar(on_click)

def crear_boton_guardar(on_click: Callable):
    return _factory.crear_boton_guardar(on_click)

def crear_boton_cancelar(on_click: Callable):
    return _factory.crear_boton_cancelar(on_click)

def crear_boton_importar(on_click: Callable):
    return _factory.crear_boton_importar(on_click)

def crear_boton_exportar(on_click: Callable):
    return _factory.crear_boton_exportar(on_click)

def crear_boton_agregar(on_click: Callable):
    return _factory.crear_boton_agregar(on_click)

def crear_boton_agregar_fechas_pagadas(on_click: Callable):
    return _factory.crear_boton_agregar_fechas_pagadas(on_click)
