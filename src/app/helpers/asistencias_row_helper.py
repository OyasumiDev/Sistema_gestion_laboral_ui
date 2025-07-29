import flet as ft
from typing import Callable, Dict, Tuple
from datetime import datetime, date, time, timedelta
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

        tiempo_trabajo_field = ft.TextField(
            value=registro.get("tiempo_trabajo_con_descanso", "0.00"),
            width=100,
            read_only=True
        )

        entrada_field = ft.TextField(width=100)
        salida_field = ft.TextField(width=100)

        entrada_field.value = self.calculo_helper.sanitizar_hora(registro.get("hora_entrada", ""))
        salida_field.value = self.calculo_helper.sanitizar_hora(registro.get("hora_salida", ""))

        entrada_field.on_change = lambda e: self.calculo_helper._actualizar_tiempo_trabajo(
            entrada_field, salida_field, registro["descanso"], tiempo_trabajo_field, registro
        )
        salida_field.on_change = lambda e: self.calculo_helper._actualizar_tiempo_trabajo(
            entrada_field, salida_field, registro["descanso"], tiempo_trabajo_field, registro
        )

        def on_numero_change(e):
            registro["numero_nomina"] = e.control.value
            self.calculo_helper.validar_fecha_y_numero(registro, registros_del_grupo, numero_field, fecha_field)

        def on_fecha_change(e):
            registro["fecha"] = e.control.value
            self.calculo_helper.validar_fecha_y_numero(registro, registros_del_grupo, numero_field, fecha_field)

        numero_field = ft.TextField(
            width=60,
            value=str(registro.get("numero_nomina", "")),
            on_change=on_numero_change,
            autofocus=True
        )

        fecha_field = ft.TextField(
            width=150,
            value=str(registro.get("fecha", "")),
            on_change=on_fecha_change
        )

        descanso_widget = self._crear_botones_descanso(
            grupo_importacion,
            registro,
            tiempo_trabajo_field,
            entrada_field,
            salida_field
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


    def build_fila_edicion(self, registro: Dict, on_save: Callable, on_cancel: Callable) -> ft.DataRow:
        numero_nomina = registro["numero_nomina"]
        fecha = registro["fecha"]

        if "descanso" not in registro:
            registro["descanso"] = "SN"

        tiempo_field = ft.TextField(value=registro.get("tiempo_trabajo_con_descanso", "00:00:00"), width=100, read_only=True)

        entrada_field = ft.TextField(value=self.calculo_helper.sanitizar_hora(registro.get("hora_entrada", "")), width=100)
        salida_field = ft.TextField(value=self.calculo_helper.sanitizar_hora(registro.get("hora_salida", "")), width=100)

        entrada_field.on_change = lambda e: self.calculo_helper._actualizar_tiempo_trabajo(
            entrada_field, salida_field, registro["descanso"], tiempo_field, registro, [entrada_field, salida_field, tiempo_field]
        )
        salida_field.on_change = lambda e: self.calculo_helper._actualizar_tiempo_trabajo(
            entrada_field, salida_field, registro["descanso"], tiempo_field, registro, [entrada_field, salida_field, tiempo_field]
        )

        descanso_widget = self._crear_botones_descanso(numero_nomina, registro, tiempo_field, entrada_field, salida_field)

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(ft.Text(str(numero_nomina)), 60)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("nombre_completo", ""), overflow=ft.TextOverflow.ELLIPSIS, max_lines=1, text_align=ft.TextAlign.LEFT), 250)),
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



    def build_fila_vista(
        self,
        registro: dict,
        on_edit: Callable,
        on_delete: Callable = None
    ) -> ft.DataRow:
        numero_nomina = registro["numero_nomina"]
        fecha = registro["fecha"]
        descanso = registro.get("descanso", "SN")
        descanso_texto = f"{descanso}: {self.calculo_helper.obtener_minutos_descanso(descanso)} min"
        tiempo_mostrar = registro.get("tiempo_trabajo_con_descanso", "00:00:00")

        acciones = [
            ft.IconButton(
                icon=ft.icons.EDIT,
                tooltip="Editar",
                on_click=lambda e: on_edit(numero_nomina, fecha)
            )
        ]

        if on_delete:
            acciones.append(
                ft.IconButton(
                    icon=ft.icons.DELETE_OUTLINE,
                    tooltip="Eliminar",
                    icon_color=ft.colors.RED_600,
                    on_click=lambda e: on_delete(registro)
                )
            )

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(ft.Text(str(numero_nomina)), 60)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("nombre_completo", ""), overflow=ft.TextOverflow.ELLIPSIS, max_lines=1,text_align=ft.TextAlign.LEFT  # o START si usas idiomas LTR/RTL
), 250)),
            ft.DataCell(self._wrap_cell(ft.Text(str(fecha)), 135)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("hora_entrada", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("hora_salida", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(descanso_texto), 180)),
            ft.DataCell(self._wrap_cell(ft.Text(str(tiempo_mostrar)), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("estado", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Row(acciones, spacing=5), 100))
        ])


    def _crear_textfield(
        self,
        grupo: str,
        campo: str,
        registro: Dict,
        tiempo_trabajo_field: ft.TextField = None,
        entrada_field_ref: ft.TextField = None,
        salida_field_ref: ft.TextField = None
    ) -> ft.TextField:
        field = ft.TextField(
            value=registro.get(campo, ""),
            width=100,
            border_color=ft.colors.GREY,
            bgcolor=ft.colors.TRANSPARENT
        )

        def on_change(e):
            valor = e.control.value
            self._on_change(grupo, campo, valor)

            # Recalcular tiempo trabajado si cambian entrada/salida
            if campo in ("hora_entrada", "hora_salida") and tiempo_trabajo_field:
                entrada_valor = entrada_field_ref.value if campo == "hora_salida" else valor
                salida_valor = salida_field_ref.value if campo == "hora_entrada" else valor

                self.calculo_helper._actualizar_tiempo_trabajo(
                    entrada_field=entrada_field_ref,
                    salida_field=salida_field_ref,
                    descanso_tipo=registro.get("descanso", "SN"),
                    tiempo_field=tiempo_trabajo_field,
                    registro=registro,
                    fila_controls=[entrada_field_ref, salida_field_ref, tiempo_trabajo_field]
                )

        field.on_change = on_change
        return field


    def _crear_botones_descanso(
        self,
        grupo: str,
        registro: Dict,
        tiempo_trabajo_field: ft.TextField,
        entrada_field: ft.TextField = None,
        salida_field: ft.TextField = None
    ) -> ft.Container:
        opciones = ["SN", "MD", "CMP"]
        botones = []

        def seleccionar(opcion):
            registro["descanso"] = opcion
            self._on_change(grupo, "descanso", opcion)

            # Actualizar visual de botones
            for btn in botones:
                btn.bgcolor = ft.colors.BLUE if btn.data == opcion else ft.colors.WHITE
                try:
                    if btn.page:
                        btn.update()
                except Exception as e:
                    print(f"⚠️ Error actualizando botón de descanso: {e}")

            # Recalcular tiempo trabajado si campos están presentes
            if entrada_field and salida_field and tiempo_trabajo_field:
                self.calculo_helper._actualizar_tiempo_trabajo(
                    entrada_field=entrada_field,
                    salida_field=salida_field,
                    descanso_tipo=opcion,
                    tiempo_field=tiempo_trabajo_field,
                    registro=registro,
                    fila_controls=[entrada_field, salida_field, tiempo_trabajo_field]
                )

        # Valor por defecto
        if "descanso" not in registro:
            registro["descanso"] = "SN"

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
            content=ft.Row(
                controls=botones,
                spacing=3,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True
            ),
            alignment=ft.alignment.center,
            width=180
        )


    def _on_change(self, grupo: str, campo: str, valor: str):
        try:
            # Validación rápida
            if not grupo or not campo:
                print("❗ _on_change cancelado: grupo o campo vacío")
                return

            # Actualiza el valor en el registro sin bloquear
            if callable(self.actualizar_callback):
                self.actualizar_callback(grupo, campo, valor)

            # Evitar recálculos innecesarios en cada pulsación
            if campo in ("hora_entrada", "hora_salida", "descanso"):
                # Usa una tarea diferida o mínima para evitar saturación
                ft.app(target=lambda: self.recalcular_callback(grupo))

        except Exception as e:
            print(f"❌ Excepción en _on_change - Grupo: {grupo}, Campo: {campo}, Error: {e}")
