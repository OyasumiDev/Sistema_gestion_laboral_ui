import flet as ft
from typing import List, Tuple, Callable, Optional
from app.helpers.boton_factory import (
    crear_boton_editar,
    crear_boton_eliminar,
    crear_boton_guardar,
    crear_boton_cancelar,
)


class AsistenciasColumnBuilder:
    """
    Column builder especializado para el módulo de asistencias.

    - Acepta callbacks de edición y eliminación (solo para decidir si agrega la
      columna 'Acciones'; los botones reales los crea el RowHelper).
    - No aplica sort aquí: el sort per-panel se maneja en AsistenciasContainer.crear_columnas(),
      que sustituye los labels por encabezados clicables.
    """

    def __init__(
        self,
        on_edit: Optional[Callable[[object], None]] = None,
        on_delete: Optional[Callable[[object], None]] = None,
    ):
        self.on_edit = on_edit
        self.on_delete = on_delete

    def build_columns(self, columnas_definidas: List[Tuple[str, str]]) -> List[ft.DataColumn]:
        """
        Crea DataColumns a partir de (titulo, clave). Si hay callbacks de edición/elim,
        agrega una última columna 'Acciones'.
        """
        cols: List[ft.DataColumn] = []

        for titulo, _clave in columnas_definidas:
            # El contenedor luego reemplaza el label por uno "clickable" si es sortable
            cols.append(
                ft.DataColumn(
                    label=ft.Text(titulo, size=12, weight="bold")
                )
            )

        if self.on_edit or self.on_delete:
            cols.append(ft.DataColumn(label=ft.Text("Acciones", size=12, weight="bold")))

        return cols

    # Opcional: útil si en algún punto quieres que el builder te fabrique los botones de acción.
    # El contenedor/row helper ya gestionan esto, pero lo dejamos disponible por compatibilidad.
    def build_action_buttons(
        self,
        is_editing: bool,
        registro: Optional[dict] = None,
        on_save: Optional[Callable[[], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
    ) -> ft.Row:
        botones = []

        if is_editing:
            if on_save:
                botones.append(crear_boton_guardar(on_save))
            if on_cancel:
                botones.append(crear_boton_cancelar(on_cancel))
        else:
            if self.on_edit and registro is not None:
                botones.append(crear_boton_editar(lambda e: self.on_edit(registro)))
            if self.on_delete and registro is not None:
                botones.append(crear_boton_eliminar(lambda e: self.on_delete(registro)))

        return ft.Row(controls=botones, spacing=5)
