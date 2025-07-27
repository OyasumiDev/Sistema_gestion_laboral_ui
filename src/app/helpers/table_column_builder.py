import flet as ft
from typing import List, Tuple, Callable, Optional
from app.helpers.boton_factory import (
    crear_boton_editar,
    crear_boton_eliminar,
    crear_boton_guardar,
    crear_boton_cancelar
)


class TableColumnBuilder:
    def __init__(
        self,
        sort_helper: Optional[object] = None,
        on_edit: Optional[Callable[[object], None]] = None,
        on_delete: Optional[Callable[[object], None]] = None
    ):
        self.sort_helper = sort_helper
        self.on_edit = on_edit
        self.on_delete = on_delete

    def build_columns(self, columnas_definidas: List[Tuple[str, str]]) -> List[ft.DataColumn]:
        columnas = []

        for titulo, clave in columnas_definidas:
            if self.sort_helper:
                icon = self.sort_helper.get_icon(clave)
                col = ft.DataColumn(
                    label=ft.Row(
                        controls=[
                            ft.Text(titulo),
                            ft.Icon(name=icon, size=14)
                        ],
                        spacing=5
                    ),
                    on_sort=lambda e, k=clave: self.sort_helper.toggle_sort(k)
                )
            else:
                col = ft.DataColumn(label=ft.Text(titulo))

            columnas.append(col)

        if self.on_edit or self.on_delete:
            columnas.append(ft.DataColumn(label=ft.Text("Acciones")))

        return columnas



    def build_action_buttons(
        self,
        is_editing: bool,
        registro: Optional[dict] = None,  # ✅ Recibe el registro para pasarlo al callback
        on_save: Optional[Callable[[], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None
    ) -> ft.Row:
        botones = []

        if is_editing:
            if on_save:
                botones.append(crear_boton_guardar(on_save))
            if on_cancel:
                botones.append(crear_boton_cancelar(on_cancel))
        else:
            if self.on_edit and registro:
                botones.append(crear_boton_editar(lambda e: self.on_edit(registro)))
            if self.on_delete and registro:
                botones.append(crear_boton_eliminar(lambda e: self.on_delete(registro)))

        return ft.Row(controls=botones, spacing=5)

    def build_group_panel(
        self,
        grupo_nombre: str,
        tabla: ft.DataTable,
        on_add: Callable[[], None],
        expanded: bool = False,
        on_toggle: Optional[Callable[[], None]] = None
    ) -> ft.ExpansionPanel:
        encabezado = ft.Row(controls=[
            ft.Text(f"🗂 {grupo_nombre}", expand=True),
            ft.IconButton(
                icon=ft.icons.ADD,
                tooltip="Agregar nuevo registro",
                on_click=lambda e: on_add()
            )
        ])

        panel = ft.ExpansionPanel(
            header=encabezado,
            content=tabla,
            can_tap_header=True,
            expanded=expanded
        )

        if on_toggle:
            panel.on_expansion_changed = lambda e: on_toggle()

        return panel

