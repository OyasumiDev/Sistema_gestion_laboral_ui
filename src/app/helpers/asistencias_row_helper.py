import flet as ft
from typing import Callable, Dict
from app.helpers.calculo_horas_helper import CalculoHorasHelper


class AsistenciasRowHelper:
    def __init__(self, recalcular_callback: Callable, actualizar_callback: Callable):
        self.recalcular_callback = recalcular_callback
        self.actualizar_callback = actualizar_callback
        self.calculo_helper = CalculoHorasHelper()

    def _wrap_cell(self, control, width: int) -> ft.Container:
        return ft.Container(
            content=control,
            width=width,
            alignment=ft.alignment.center,
            padding=ft.padding.symmetric(horizontal=2)
        )

    # ---------------- FILA NUEVA ----------------
    def build_fila_nueva(
        self,
        grupo_importacion: str,
        registro: Dict,
        on_save: Callable,
        on_cancel: Callable,
        registros_del_grupo: list
    ) -> ft.DataRow:
        if "descanso" not in registro:
            registro["descanso"] = "SN"

        # Campo tiempo trabajado solo lectura
        tiempo_trabajo_field = ft.TextField(
            value=registro.get("tiempo_trabajo_con_descanso", "0.00"),
            width=100,
            read_only=True
        )

        # Entrada / salida
        entrada_field = ft.TextField(width=100)
        salida_field = ft.TextField(width=100)
        entrada_field.value = self.calculo_helper.sanitizar_hora(registro.get("hora_entrada", ""))
        salida_field.value = self.calculo_helper.sanitizar_hora(registro.get("hora_salida", ""))

        entrada_field.on_blur = lambda e: self._recalcular_fila(entrada_field, salida_field, registro, tiempo_trabajo_field)
        salida_field.on_blur = lambda e: self._recalcular_fila(entrada_field, salida_field, registro, tiempo_trabajo_field)

        # Validaciones ID / fecha solo en blur
        def on_numero_blur(e):
            registro["numero_nomina"] = e.control.value
            self.calculo_helper.validar_fecha_y_numero(
                registro, registros_del_grupo, numero_field, fecha_field
            )

        def on_fecha_blur(e):
            registro["fecha"] = e.control.value
            self.calculo_helper.validar_fecha_y_numero(
                registro, registros_del_grupo, numero_field, fecha_field
            )

        numero_field = ft.TextField(
            width=60,
            value=str(registro.get("numero_nomina", "")),
            on_blur=on_numero_blur,
            autofocus=True
        )
        fecha_field = ft.TextField(
            width=150,
            value=str(registro.get("fecha", "")),
            on_blur=on_fecha_blur
        )

        # Descanso
        descanso_widget = self._crear_botones_descanso(
            grupo_importacion, registro, tiempo_trabajo_field, entrada_field, salida_field
        )

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(numero_field, 60)),
            ft.DataCell(self._wrap_cell(ft.Text("-", overflow=ft.TextOverflow.ELLIPSIS, max_lines=1), 250)),
            ft.DataCell(self._wrap_cell(fecha_field, 150)),
            ft.DataCell(self._wrap_cell(entrada_field, 100)),
            ft.DataCell(self._wrap_cell(salida_field, 100)),
            ft.DataCell(self._wrap_cell(descanso_widget, 180)),
            ft.DataCell(self._wrap_cell(tiempo_trabajo_field, 100)),
            ft.DataCell(self._wrap_cell(ft.Text("PENDIENTE"), 100)),
            ft.DataCell(self._wrap_cell(ft.Row([
                ft.IconButton(icon=ft.icons.SAVE, tooltip="Guardar", on_click=lambda e: on_save()),
                ft.IconButton(icon=ft.icons.CANCEL, tooltip="Cancelar", on_click=lambda e: on_cancel())
            ], spacing=5), 100))
        ])

    # ---------------- FILA EDICIÓN ----------------
    def build_fila_edicion(self, registro: Dict, on_save: Callable, on_cancel: Callable) -> ft.DataRow:
        numero_nomina = registro["numero_nomina"]
        fecha = registro["fecha"]

        if "descanso" not in registro:
            registro["descanso"] = "SN"

        tiempo_field = ft.TextField(
            value=registro.get("tiempo_trabajo_con_descanso", "00:00:00"),
            width=100,
            read_only=True
        )

        entrada_field = ft.TextField(value=self.calculo_helper.sanitizar_hora(registro.get("hora_entrada", "")), width=100)
        salida_field = ft.TextField(value=self.calculo_helper.sanitizar_hora(registro.get("hora_salida", "")), width=100)

        entrada_field.on_blur = lambda e: self._recalcular_fila(entrada_field, salida_field, registro, tiempo_field)
        salida_field.on_blur = lambda e: self._recalcular_fila(entrada_field, salida_field, registro, tiempo_field)

        descanso_widget = self._crear_botones_descanso(
            numero_nomina, registro, tiempo_field, entrada_field, salida_field
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
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("estado", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Row([
                ft.IconButton(icon=ft.icons.SAVE, tooltip="Guardar edición", on_click=lambda e: on_save()),
                ft.IconButton(icon=ft.icons.CANCEL, tooltip="Cancelar", on_click=lambda e: on_cancel())
            ], spacing=5), 100))
        ])

    # ---------------- FILA VISTA ----------------
    def build_fila_vista(self, registro: dict, on_edit: Callable, on_delete: Callable = None) -> ft.DataRow:
        numero_nomina = registro["numero_nomina"]
        fecha = registro["fecha"]
        descanso = registro.get("descanso", "SN")
        descanso_texto = f"{descanso}: {self.calculo_helper.obtener_minutos_descanso(descanso)} min"
        tiempo_mostrar = registro.get("tiempo_trabajo_con_descanso", "00:00:00")

        acciones = [
            ft.IconButton(icon=ft.icons.EDIT, tooltip="Editar", on_click=lambda e: on_edit(numero_nomina, fecha))
        ]
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
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("estado", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Row(acciones, spacing=5), 100))
        ])

    # ---------------- HELPERS ----------------
    def _recalcular_fila(self, entrada_field, salida_field, registro, tiempo_field):
        resultado = self.calculo_helper.recalcular_con_estado(
            entrada_field.value, salida_field.value, registro.get("descanso", "SN")
        )
        tiempo_field.value = resultado["tiempo_trabajo_con_descanso"]
        registro["tiempo_trabajo"] = resultado["tiempo_trabajo"]
        registro["tiempo_trabajo_con_descanso"] = resultado["tiempo_trabajo_con_descanso"]
        if callable(self.recalcular_callback):
            self.recalcular_callback(registro.get("grupo_importacion"))

    def _crear_botones_descanso(self, grupo: str, registro: Dict, tiempo_field: ft.TextField,
                                entrada_field: ft.TextField = None, salida_field: ft.TextField = None) -> ft.Container:
        opciones = ["SN", "MD", "CMP"]
        botones = []

        def seleccionar(opcion):
            registro["descanso"] = opcion
            # Recalcular inmediatamente
            self._recalcular_fila(entrada_field, salida_field, registro, tiempo_field)
            # Refrescar botones
            for btn in botones:
                btn.bgcolor = ft.colors.BLUE if btn.data == opcion else ft.colors.WHITE
            if botones and botones[0].page:
                botones[0].page.update()

        for tipo in opciones:
            btn = ft.Container(
                content=ft.Text(tipo, size=12, color=ft.colors.BLACK),
                bgcolor=ft.colors.BLUE if registro.get("descanso") == tipo else ft.colors.WHITE,
                border=ft.border.all(1, ft.colors.GREY),
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
