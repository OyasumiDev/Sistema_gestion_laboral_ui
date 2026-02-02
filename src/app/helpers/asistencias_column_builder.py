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
    Column builder robusto para el módulo de asistencias.

    FIXES IMPORTANTES:
    - Evita duplicar "Horas Trabajadas" cuando el container use:
        * tiempo_trabajo  ó
        * tiempo_trabajo_con_descanso
      (ambas se mapean a UNA sola columna canónica)
    - NO agrega columnas extra automáticamente (eso rompe el orden y desplaza acciones).
    - La columna "Acciones" siempre existe y siempre es la ÚLTIMA.
    - Se ignora cualquier columna 'acciones' que el container pase por error.
    """

    # Orden canónico (debe coincidir con AsistenciasRowHelper)
    _CANON = [
        ("ID Nómina", "numero_nomina"),
        ("Nombre", "nombre_completo"),
        ("Fecha", "fecha"),
        ("Hora Entrada", "hora_entrada"),
        ("Hora Salida", "hora_salida"),
        ("Descanso", "descanso"),
        # CANÓNICO: usamos UNA sola clave lógica para horas
        ("Horas Trabajadas", "tiempo_trabajo"),
        ("Estado", "estado"),
        # Acciones NO va aquí: se agrega siempre al final
    ]

    # Aliases -> clave canónica
    _ALIASES = {
        "tiempo_trabajo_con_descanso": "tiempo_trabajo",
        "horas_trabajadas": "tiempo_trabajo",
        "acciones": "__acciones__",  # se ignora (si viene del container)
        "accion": "__acciones__",
    }

    def __init__(
        self,
        on_edit: Optional[Callable[[object], None]] = None,
        on_delete: Optional[Callable[[object], None]] = None,
        force_actions_column: bool = True,
        actions_width: int = 100,
        actions_header_mode: str = "icon",  # "icon" | "blank" | "text"
    ):
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.force_actions_column = force_actions_column
        self.actions_width = actions_width
        self.actions_header_mode = actions_header_mode

    # -------------------------
    # Construcción de columnas
    # -------------------------
    def build_columns(self, columnas_definidas: List[Tuple[str, str]]) -> List[ft.DataColumn]:
        """
        Entrada esperada: lista de (titulo, clave).

        Regla de oro:
        - Este builder SOLO construye columnas del orden canónico + Acciones al final.
        - Si el container pasa llaves extra, se ignoran para no desfasar la tabla.
        """
        # Normaliza input -> mapa clave_canónica -> título
        input_map: dict[str, str] = {}

        for titulo, clave in (columnas_definidas or []):
            if not clave:
                continue
            raw_key = str(clave).strip()
            key = self._normalize_key(raw_key)

            # Si es acciones (o alias), se ignora: Acciones se agrega al final siempre
            if key == "__acciones__":
                continue

            # Si cae vacío, ignora
            if not key:
                continue

            title = str(titulo).strip() if titulo else ""
            if title:
                input_map[key] = title

        cols: List[ft.DataColumn] = []

        # 1) Columnas canónicas
        for default_title, key in self._CANON:
            title = input_map.get(key, default_title)
            cols.append(self._col(title))

        # 2) Acciones SIEMPRE al final
        if self.force_actions_column or self.on_edit or self.on_delete:
            cols.append(self._actions_col())

        return cols

    # -------------------------
    # Helpers internos
    # -------------------------
    def _normalize_key(self, key: str) -> str:
        k = (key or "").strip()
        if not k:
            return ""
        k = self._ALIASES.get(k, k)
        return k

    def _col(self, title: str) -> ft.DataColumn:
        return ft.DataColumn(
            label=ft.Text(title, size=12, weight=ft.FontWeight.BOLD, no_wrap=True)
        )

    def _actions_col(self) -> ft.DataColumn:
        return ft.DataColumn(
            label=ft.Container(
                content=ft.Text("Acciones", size=12, weight=ft.FontWeight.BOLD, no_wrap=True),
                width=self.actions_width,
                alignment=ft.alignment.center,
            )
        )


        return ft.DataColumn(
            label=ft.Container(
                content=head,
                width=self.actions_width,
                alignment=ft.alignment.center,
            )
        )

    # -------------------------
    # Opcional: builder de botones
    # -------------------------
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
