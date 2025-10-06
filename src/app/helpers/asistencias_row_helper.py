import flet as ft
from typing import Callable, Dict
from app.helpers.calculo_horas_helper import CalculoHorasHelper
from app.core.app_state import AppState


class AsistenciasRowHelper:
    def __init__(self, recalcular_callback: Callable, actualizar_callback: Callable):
        self.recalcular_callback = recalcular_callback
        self.actualizar_callback = actualizar_callback
        self.calculo_helper = CalculoHorasHelper()
        self.page = AppState().page

    # ---------- util ----------
    def _wrap_cell(self, control, width: int) -> ft.Container:
        return ft.Container(
            content=control,
            width=width,
            alignment=ft.alignment.center,
            padding=ft.padding.symmetric(horizontal=2)
        )

    def _soft_update(self):
        if self.page:
            self.page.update()

    # ========== FILA NUEVA ==========
    def build_fila_nueva(
        self,
        grupo_importacion: str,
        registro: Dict,
        on_save: Callable,
        on_cancel: Callable,
        registros_del_grupo: list
    ) -> ft.DataRow:
        if not registro.get("descanso"):
            registro["descanso"] = "MD"
        if not registro.get("estado"):
            registro["estado"] = "PENDIENTE"

        # Widgets
        estado_text = ft.Text(
            registro.get("estado", "PENDIENTE").upper(),
            size=12,
            text_align=ft.TextAlign.CENTER,
            color=ft.colors.GREY
        )
        tiempo_field = ft.TextField(
            value=registro.get("tiempo_trabajo_con_descanso", "00:00:00"),
            width=100,
            read_only=True,
            text_align=ft.TextAlign.CENTER
        )

        entrada_field = ft.TextField(
            width=100,
            value=self.calculo_helper.sanitizar_hora(registro.get("hora_entrada", "")),
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.DATETIME,
            on_change=lambda e: self._on_change_hora(
                grupo_importacion, registro, "hora_entrada",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
            on_blur=lambda e: self._on_blur_hora(
                grupo_importacion, registro, "hora_entrada",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
        )
        salida_field = ft.TextField(
            width=100,
            value=self.calculo_helper.sanitizar_hora(registro.get("hora_salida", "")),
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.DATETIME,
            on_change=lambda e: self._on_change_hora(
                grupo_importacion, registro, "hora_salida",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
            on_blur=lambda e: self._on_blur_hora(
                grupo_importacion, registro, "hora_salida",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
        )

        # Validaciones extra
        def on_numero_blur(e):
            registro["numero_nomina"] = e.control.value
            self.actualizar_callback(grupo_importacion, "numero_nomina", e.control.value)
            self.calculo_helper.validar_fecha_y_numero(registro, registros_del_grupo, numero_field, fecha_field)
            self._soft_update()

        def on_fecha_blur(e):
            registro["fecha"] = e.control.value
            self.actualizar_callback(grupo_importacion, "fecha", e.control.value)
            self.calculo_helper.validar_fecha_y_numero(registro, registros_del_grupo, numero_field, fecha_field)
            self._soft_update()

        numero_field = ft.TextField(
            width=60,
            value=str(registro.get("numero_nomina", "")),
            on_blur=on_numero_blur,
            autofocus=True,
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        fecha_field = ft.TextField(
            width=150,
            value=str(registro.get("fecha", "")),
            on_blur=on_fecha_blur,
            text_align=ft.TextAlign.CENTER
        )

        descanso_widget = self._crear_botones_descanso(
            grupo_importacion, registro, tiempo_field, estado_text, entrada_field, salida_field
        )

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(numero_field, 60)),
            ft.DataCell(self._wrap_cell(ft.Text("-", overflow=ft.TextOverflow.ELLIPSIS, max_lines=1), 250)),
            ft.DataCell(self._wrap_cell(fecha_field, 150)),
            ft.DataCell(self._wrap_cell(entrada_field, 100)),
            ft.DataCell(self._wrap_cell(salida_field, 100)),
            ft.DataCell(self._wrap_cell(descanso_widget, 180)),
            ft.DataCell(self._wrap_cell(tiempo_field, 100)),
            ft.DataCell(self._wrap_cell(estado_text, 100)),
            ft.DataCell(self._wrap_cell(ft.Row([
                ft.IconButton(icon=ft.icons.SAVE, tooltip="Guardar", on_click=lambda e: on_save()),
                ft.IconButton(icon=ft.icons.CANCEL, tooltip="Cancelar", on_click=lambda e: on_cancel())
            ], spacing=5), 100))
        ])

    # ========== FILA EDICIÓN ==========
    def build_fila_edicion(self, registro: Dict, on_save: Callable, on_cancel: Callable) -> ft.DataRow:
        numero_nomina = registro["numero_nomina"]
        fecha = registro["fecha"]
        grupo = registro.get("grupo_importacion", "")

        if not registro.get("descanso"):
            registro["descanso"] = "MD"

        estado_text = ft.Text(
            registro.get("estado", "").upper(),
            size=12,
            text_align=ft.TextAlign.CENTER,
            color=ft.colors.RED if registro.get("estado") == "INCOMPLETO" else ft.colors.GREEN
        )
        tiempo_field = ft.TextField(
            value=registro.get("tiempo_trabajo_con_descanso", "00:00:00"),
            width=100,
            read_only=True,
            text_align=ft.TextAlign.CENTER
        )

        entrada_field = ft.TextField(
            value=self.calculo_helper.sanitizar_hora(registro.get("hora_entrada", "")),
            width=100,
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.DATETIME,
            on_change=lambda e: self._on_change_hora(
                grupo, registro, "hora_entrada",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
            on_blur=lambda e: self._on_blur_hora(
                grupo, registro, "hora_entrada",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
        )
        salida_field = ft.TextField(
            value=self.calculo_helper.sanitizar_hora(registro.get("hora_salida", "")),
            width=100,
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.DATETIME,
            on_change=lambda e: self._on_change_hora(
                grupo, registro, "hora_salida",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
            on_blur=lambda e: self._on_blur_hora(
                grupo, registro, "hora_salida",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
        )

        descanso_widget = self._crear_botones_descanso(
            grupo, registro, tiempo_field, estado_text, entrada_field, salida_field
        )

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(ft.Text(str(numero_nomina)), 60)),
            ft.DataCell(self._wrap_cell(ft.Text(
                registro.get("nombre_completo", ""),
                overflow=ft.TextOverflow.ELLIPSIS, max_lines=1, text_align=ft.TextAlign.LEFT
            ), 250)),
            ft.DataCell(self._wrap_cell(ft.Text(str(fecha)), 135)),
            ft.DataCell(self._wrap_cell(entrada_field, 100)),
            ft.DataCell(self._wrap_cell(salida_field, 100)),
            ft.DataCell(self._wrap_cell(descanso_widget, 180)),
            ft.DataCell(self._wrap_cell(tiempo_field, 100)),
            ft.DataCell(self._wrap_cell(estado_text, 100)),
            ft.DataCell(self._wrap_cell(ft.Row([
                ft.IconButton(icon=ft.icons.SAVE, tooltip="Guardar edición", on_click=lambda e: on_save()),
                ft.IconButton(icon=ft.icons.CANCEL, tooltip="Cancelar", on_click=lambda e: on_cancel())
            ], spacing=5), 100))
        ])

    # ========== FILA VISTA ==========
    def build_fila_vista(self, registro: dict, on_edit: Callable, on_delete: Callable = None) -> ft.DataRow:
        numero_nomina = registro["numero_nomina"]
        fecha = registro["fecha"]
        descanso = registro.get("descanso", "MD")
        descanso_texto = f"{descanso}: {self.calculo_helper.obtener_minutos_descanso(descanso)} min"
        tiempo_mostrar = registro.get("tiempo_trabajo_con_descanso", "00:00:00")

        estado_text = ft.Text(
            registro.get("estado", "").upper(),
            text_align=ft.TextAlign.CENTER,
            color=ft.colors.RED if registro.get("estado") == "INCOMPLETO" else ft.colors.GREEN
        )

        acciones = [ft.IconButton(icon=ft.icons.EDIT, tooltip="Editar", on_click=lambda e: on_edit(numero_nomina, fecha))]
        if on_delete:
            acciones.append(
                ft.IconButton(icon=ft.icons.DELETE_OUTLINE, tooltip="Eliminar", icon_color=ft.colors.RED_600,
                              on_click=lambda e: on_delete(registro))
            )

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(ft.Text(str(numero_nomina)), 60)),
            ft.DataCell(self._wrap_cell(ft.Text(
                registro.get("nombre_completo", ""),
                overflow=ft.TextOverflow.ELLIPSIS, max_lines=1, text_align=ft.TextAlign.LEFT
            ), 250)),
            ft.DataCell(self._wrap_cell(ft.Text(str(fecha)), 135)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("hora_entrada", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("hora_salida", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(descanso_texto), 180)),
            ft.DataCell(self._wrap_cell(ft.Text(str(tiempo_mostrar)), 100)),
            ft.DataCell(self._wrap_cell(estado_text, 100)),
            ft.DataCell(self._wrap_cell(ft.Row(acciones, spacing=5), 100))
        ])

    # ========== HANDLERS ==========
    def _on_change_hora(self, grupo, registro, campo, entrada_field, salida_field, tiempo_field, estado_text):
        valor = entrada_field.value if campo == "hora_entrada" else salida_field.value
        registro[campo] = valor
        self.actualizar_callback(grupo, campo, valor)

        res = self.calculo_helper.recalcular_con_estado(
            entrada_field.value, salida_field.value, registro.get("descanso", "MD")
        )
        tiempo_field.value = res.get("tiempo_trabajo_con_descanso", "00:00:00")
        registro["tiempo_trabajo"] = res.get("tiempo_trabajo", "00:00:00")
        registro["tiempo_trabajo_con_descanso"] = tiempo_field.value

        nuevo_estado = "COMPLETO" if res.get("estado") == "ok" else "INCOMPLETO"
        registro["estado"] = nuevo_estado
        estado_text.value = nuevo_estado
        estado_text.color = ft.colors.GREEN if nuevo_estado == "COMPLETO" else ft.colors.RED

        self._soft_update()

    def _on_blur_hora(self, grupo, registro, campo, entrada_field, salida_field, tiempo_field, estado_text):
        valor = entrada_field.value if campo == "hora_entrada" else salida_field.value
        registro[campo] = valor
        self.actualizar_callback(grupo, campo, valor)
        self._soft_update()

    def _crear_botones_descanso(self, grupo, registro, tiempo_field, estado_text, entrada_field=None, salida_field=None):
        opciones = ["SN", "MD", "CMP"]
        botones = []

        def seleccionar(opcion):
            registro["descanso"] = opcion
            self.actualizar_callback(grupo, "descanso", opcion)

            res = self.calculo_helper.recalcular_con_estado(
                entrada_field.value if entrada_field else registro.get("hora_entrada", ""),
                salida_field.value if salida_field else registro.get("hora_salida", ""),
                opcion
            )
            tiempo_field.value = res.get("tiempo_trabajo_con_descanso", "00:00:00")
            registro["tiempo_trabajo"] = res.get("tiempo_trabajo", "00:00:00")
            registro["tiempo_trabajo_con_descanso"] = tiempo_field.value

            nuevo_estado = "COMPLETO" if res.get("estado") == "ok" else "INCOMPLETO"
            registro["estado"] = nuevo_estado
            estado_text.value = nuevo_estado
            estado_text.color = ft.colors.GREEN if nuevo_estado == "COMPLETO" else ft.colors.RED

            for btn in botones:
                is_on = btn.data == opcion
                btn.bgcolor = ft.colors.BLUE if is_on else ft.colors.WHITE
                btn.content.color = ft.colors.WHITE if is_on else ft.colors.BLACK

            self._soft_update()

        for tipo in opciones:
            is_on = registro.get("descanso") == tipo
            btn = ft.Container(
                content=ft.Text(tipo, size=12, color=ft.colors.WHITE if is_on else ft.colors.BLACK),
                bgcolor=ft.colors.BLUE if is_on else ft.colors.WHITE,
                border=ft.border.all(1, ft.colors.GREY_400),
                border_radius=5,
                alignment=ft.alignment.center,
                height=30,
                expand=True,
                data=tipo,
                on_click=lambda e, t=tipo: seleccionar(t)
            )
            botones.append(btn)

        return ft.Container(
            content=ft.Row(controls=botones, spacing=3, alignment=ft.MainAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            width=180
        )
