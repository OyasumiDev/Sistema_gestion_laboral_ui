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

    def _sanitizar_hora(self, valor):
        if isinstance(valor, time):
            return valor.strftime("%H:%M:%S")
        elif isinstance(valor, timedelta):
            total_seconds = int(valor.total_seconds())
            horas = total_seconds // 3600
            minutos = (total_seconds % 3600) // 60
            segundos = total_seconds % 60
            return f"{horas:02}:{minutos:02}:{segundos:02}"
        elif isinstance(valor, datetime):
            return valor.time().strftime("%H:%M:%S")
        elif isinstance(valor, str):
            partes = valor.strip().split(":")
            if len(partes) == 2:
                # Si solo viene HH:MM, agregamos los segundos
                return f"{partes[0]:0>2}:{partes[1]:0>2}:00"
            elif len(partes) == 3:
                return f"{partes[0]:0>2}:{partes[1]:0>2}:{partes[2]:0>2}"
            else:
                return ""
        else:
            return ""


    def build_fila_nueva(self, grupo_importacion: str, registro: Dict, on_save: Callable, on_cancel: Callable) -> ft.DataRow:
        if "descanso" not in registro:
            registro["descanso"] = "SN"

        tiempo_trabajo_field = ft.TextField(
            value=registro.get("tiempo_trabajo_con_descanso", "0.00"),
            width=100,
            read_only=True
        )

        entrada_field = ft.TextField(width=100)
        salida_field = ft.TextField(width=100)

        entrada_field.value = self._sanitizar_hora(registro.get("hora_entrada", ""))
        salida_field.value = self._sanitizar_hora(registro.get("hora_salida", ""))

        entrada_field.on_change = lambda e: self._actualizar_tiempo_trabajo(
            entrada_field, salida_field, registro["descanso"],
            tiempo_trabajo_field, registro,
            [entrada_field, salida_field, tiempo_trabajo_field]
        )

        salida_field.on_change = lambda e: self._actualizar_tiempo_trabajo(
            entrada_field, salida_field, registro["descanso"],
            tiempo_trabajo_field, registro,
            [entrada_field, salida_field, tiempo_trabajo_field]
        )

        descanso_widget = self._crear_botones_descanso(
            grupo_importacion,
            registro,
            tiempo_trabajo_field,
            entrada_field,
            salida_field
        )

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(self._crear_textfield(grupo_importacion, "numero_nomina", registro), 100)),
            ft.DataCell(self._wrap_cell(ft.Text("-"), 150)),
            ft.DataCell(self._wrap_cell(self._crear_textfield(grupo_importacion, "fecha", registro), 110)),
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

        tiempo_trabajo_field = ft.TextField(
            value=registro.get("tiempo_trabajo_con_descanso", "0.00"),
            width=100,
            read_only=True
        )

        entrada_field = ft.TextField(width=100)
        salida_field = ft.TextField(width=100)

        entrada_field.value = self._sanitizar_hora(registro.get("hora_entrada", ""))
        salida_field.value = self._sanitizar_hora(registro.get("hora_salida", ""))

        entrada_field.on_change = lambda e: self._actualizar_tiempo_trabajo(
            entrada_field, salida_field, registro["descanso"],
            tiempo_trabajo_field, registro,
            [entrada_field, salida_field, tiempo_trabajo_field]
        )

        salida_field.on_change = lambda e: self._actualizar_tiempo_trabajo(
            entrada_field, salida_field, registro["descanso"],
            tiempo_trabajo_field, registro,
            [entrada_field, salida_field, tiempo_trabajo_field]
        )

        descanso_widget = self._crear_botones_descanso(
            numero_nomina,
            registro,
            tiempo_trabajo_field,
            entrada_field,
            salida_field
        )

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(ft.Text(str(numero_nomina)), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("nombre_completo", "")), 150)),
            ft.DataCell(self._wrap_cell(ft.Text(str(fecha)), 110)),
            ft.DataCell(self._wrap_cell(entrada_field, 100)),
            ft.DataCell(self._wrap_cell(salida_field, 100)),
            ft.DataCell(self._wrap_cell(descanso_widget, 180)),
            ft.DataCell(self._wrap_cell(tiempo_trabajo_field, 100)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("estado", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Row([
                ft.IconButton(icon=ft.icons.SAVE, tooltip="Guardar edición", on_click=lambda e: on_save()),
                ft.IconButton(icon=ft.icons.CANCEL, tooltip="Cancelar", on_click=lambda e: on_cancel())
            ], spacing=5), 100))
        ])




    def build_fila_vista(self, registro: dict, on_edit: Callable, on_delete: Callable = None) -> ft.DataRow:
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
            ft.DataCell(self._wrap_cell(ft.Text(str(numero_nomina)), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("nombre_completo", "")), 150)),
            ft.DataCell(self._wrap_cell(ft.Text(str(fecha)), 110)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("hora_entrada", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("hora_salida", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(descanso_texto), 180)),
            ft.DataCell(self._wrap_cell(ft.Text(str(tiempo_mostrar)), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("estado", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Row(acciones, spacing=5), 100))
        ])


    def _actualizar_tiempo_trabajo(
        self,
        entrada_field: ft.TextField,
        salida_field: ft.TextField,
        descanso_tipo: str,
        tiempo_field: ft.TextField,
        registro: Dict,
        fila_controls: list,
        boton_guardar: ft.IconButton = None  # ✅ botón opcional para desactivar
    ) -> bool:
        entrada = entrada_field.value
        salida = salida_field.value

        resultado = self.calculo_helper.recalcular_con_estado(entrada, salida, descanso_tipo)

        tiempo_field.value = resultado["tiempo_trabajo_con_descanso"]
        tiempo_field.update()

        def marcar_error(field, error: bool):
            field.border_color = ft.colors.RED_400 if error else ft.colors.TRANSPARENT
            field.bgcolor = ft.colors.RED_50 if error else ft.colors.TRANSPARENT
            field.update()

        hay_error = len(resultado["errores"]) > 0

        marcar_error(entrada_field, not entrada or resultado["estado"] == "invalido")
        marcar_error(salida_field, not salida or resultado["estado"] in ["invalido", "negativo"])
        marcar_error(tiempo_field, hay_error)

        registro["hora_entrada"] = entrada
        registro["hora_salida"] = salida
        registro["tiempo_trabajo"] = resultado["tiempo_trabajo"]
        registro["tiempo_trabajo_con_descanso"] = resultado["tiempo_trabajo_con_descanso"]
        registro["errores"] = resultado["errores"]

        # ✅ Desactiva el botón si hay errores
        if boton_guardar:
            boton_guardar.disabled = hay_error
            boton_guardar.icon_color = ft.colors.GREY if hay_error else None
            boton_guardar.tooltip = "Corregir errores para guardar" if hay_error else "Guardar"
            boton_guardar.update()

        return not hay_error



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

            # Si es hora_entrada o hora_salida, recalcular
            if campo in ("hora_entrada", "hora_salida") and tiempo_trabajo_field:
                entrada_valor = entrada_field_ref.value if campo == "hora_salida" else valor
                salida_valor = salida_field_ref.value if campo == "hora_entrada" else valor

                self._actualizar_tiempo_trabajo(
                    grupo,
                    entrada_valor,
                    salida_valor,
                    registro.get("descanso", "SN"),
                    registro,
                    tiempo_trabajo_field,
                    entrada_field_ref,
                    salida_field_ref
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

            # Visual: actualizar colores de botones
            for btn in botones:
                btn.bgcolor = ft.colors.BLUE if btn.data == opcion else ft.colors.WHITE
                btn.update()

            self._on_change(grupo, "descanso", opcion)

            # ✅ Recalcular usando campos actuales en pantalla
            if entrada_field and salida_field and tiempo_trabajo_field:
                self._actualizar_tiempo_trabajo(
                    entrada_field,
                    salida_field,
                    opcion,
                    tiempo_trabajo_field,
                    registro,
                    [entrada_field, salida_field, tiempo_trabajo_field]
                )

        # Inicializar valor por defecto si falta
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
        print(f"📝 _on_change - Grupo: {grupo}, Campo: {campo}, Valor: {valor}")
        self.actualizar_callback(grupo, campo, valor)
        if campo in ("hora_entrada", "hora_salida", "descanso"):
            self.recalcular_callback(grupo)

