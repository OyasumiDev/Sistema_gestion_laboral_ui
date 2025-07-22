import flet as ft
from typing import Callable, Dict
from datetime import datetime, date, time, timedelta
from app.helpers.calculo_horas_helper import CalculoHorasHelper


class AsistenciasRowHelper:
    def __init__(self, recalcular_callback: Callable, actualizar_callback: Callable):
        self.recalcular_callback = recalcular_callback
        self.actualizar_callback = actualizar_callback
        self.calculo_helper = CalculoHorasHelper()

    def build_fila_nueva(self, grupo_importacion: str, registro: Dict, on_save: Callable, on_cancel: Callable) -> ft.DataRow:
        # print(f"✅ build_fila_nueva - Grupo: {grupo_importacion}, Registro: {registro}")
        if "descanso" not in registro:
            registro["descanso"] = "SN"
        tiempo_trabajo_field = ft.TextField(value=registro.get("tiempo_trabajo_con_descanso", "00:00:00"), width=80, read_only=True)
        descanso_widget = self._crear_botones_descanso(grupo_importacion, registro, tiempo_trabajo_field)
        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(self._crear_textfield(grupo_importacion, "numero_nomina", registro), 100)),
            ft.DataCell(self._wrap_cell(ft.Text("-"), 150)),
            ft.DataCell(self._wrap_cell(self._crear_textfield(grupo_importacion, "fecha", registro), 110)),
            ft.DataCell(self._wrap_cell(self._crear_textfield(grupo_importacion, "hora_entrada", registro, tiempo_trabajo_field), 100)),
            ft.DataCell(self._wrap_cell(self._crear_textfield(grupo_importacion, "hora_salida", registro, tiempo_trabajo_field), 100)),
            ft.DataCell(self._wrap_cell(descanso_widget, 180)),
            ft.DataCell(self._wrap_cell(tiempo_trabajo_field, 90)),
            ft.DataCell(self._wrap_cell(ft.Text("PENDIENTE"), 100)),
            ft.DataCell(self._wrap_cell(ft.Row([
                ft.IconButton(icon=ft.icons.SAVE, tooltip="Guardar", on_click=lambda e: on_save()),
                ft.IconButton(icon=ft.icons.CANCEL, tooltip="Cancelar", on_click=lambda e: on_cancel())
            ], spacing=5), 100))
        ])

    def build_fila_edicion(self, registro: Dict, on_save: Callable, on_cancel: Callable) -> ft.DataRow:
        numero_nomina = registro["numero_nomina"]
        fecha = registro["fecha"]
        # print(f"✅ build_fila_edicion - Nomina: {numero_nomina}, Fecha: {fecha}, Registro: {registro}")
        if "descanso" not in registro:
            registro["descanso"] = "SN"
        tiempo_trabajo_field = ft.TextField(value=registro.get("tiempo_trabajo_con_descanso", "00:00:00"), width=80, read_only=True)
        descanso_widget = self._crear_botones_descanso(numero_nomina, registro, tiempo_trabajo_field)
        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(ft.Text(str(numero_nomina)), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("nombre_completo", "")), 150)),
            ft.DataCell(self._wrap_cell(ft.Text(str(fecha)), 110)),
            ft.DataCell(self._wrap_cell(self._crear_textfield(numero_nomina, "hora_entrada", registro, tiempo_trabajo_field), 100)),
            ft.DataCell(self._wrap_cell(self._crear_textfield(numero_nomina, "hora_salida", registro, tiempo_trabajo_field), 100)),
            ft.DataCell(self._wrap_cell(descanso_widget, 180)),
            ft.DataCell(self._wrap_cell(tiempo_trabajo_field, 90)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("estado", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Row([
                ft.IconButton(icon=ft.icons.SAVE, tooltip="Guardar edición", on_click=lambda e: on_save()),
                ft.IconButton(icon=ft.icons.CANCEL, tooltip="Cancelar", on_click=lambda e: on_cancel())
            ], spacing=5), 100))
        ])

    def build_fila_vista(self, registro: dict, on_edit: Callable) -> ft.DataRow:
        numero_nomina = registro["numero_nomina"]
        fecha = registro["fecha"]
        descanso = registro.get("descanso", "SN")
        # print(f"✅ build_fila_vista - Nomina: {numero_nomina}, Fecha: {fecha}, Descanso: {descanso}")
        descanso_texto = f"{descanso}: {self.calculo_helper.obtener_minutos_descanso(descanso)} min"
        tiempo_mostrar = registro.get("tiempo_trabajo_con_descanso", "00:00:00")
        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(ft.Text(str(numero_nomina)), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("nombre_completo", "")), 150)),
            ft.DataCell(self._wrap_cell(ft.Text(str(fecha)), 110)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("hora_entrada", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("hora_salida", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(descanso_texto), 180)),
            ft.DataCell(self._wrap_cell(ft.Text(str(tiempo_mostrar)), 90)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("estado", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Row([
                ft.IconButton(icon=ft.icons.EDIT, tooltip="Editar", on_click=lambda e: on_edit(numero_nomina, fecha))
            ]), 100))
        ])

    def _actualizar_tiempo_trabajo(self, grupo: str, registro: Dict, tiempo_trabajo_field: ft.TextField):
        entrada = registro.get("hora_entrada", "")
        salida = registro.get("hora_salida", "")
        descanso = registro.get("descanso", "SN")
        nuevo_valor = self.recalcular_horas(entrada, salida, descanso)
        registro["tiempo_trabajo_con_descanso"] = nuevo_valor
        if tiempo_trabajo_field:
            tiempo_trabajo_field.value = nuevo_valor
            tiempo_trabajo_field.update()

    def _crear_textfield(self, grupo: str, campo: str, registro: Dict, tiempo_trabajo_field: ft.TextField = None) -> ft.TextField:
        return ft.TextField(
            value=registro.get(campo, ""),
            width=100,
            on_change=lambda e: (
                self._on_change(grupo, campo, e.control.value),
                self._actualizar_tiempo_trabajo(grupo, registro, tiempo_trabajo_field)
            )
        )

    def _crear_botones_descanso(self, grupo: str, registro: Dict, tiempo_trabajo_field: ft.TextField = None) -> ft.Container:
        opciones = ["SN", "MD", "CMP"]
        botones = []

        def seleccionar(opcion):
            registro["descanso"] = opcion
            for btn in botones:
                btn.bgcolor = ft.colors.BLUE if btn.data == opcion else ft.colors.WHITE
                btn.update()
            self._on_change(grupo, "descanso", opcion)
            if tiempo_trabajo_field:
                self._actualizar_tiempo_trabajo(grupo, registro, tiempo_trabajo_field)

        if "descanso" not in registro:
            registro["descanso"] = "SN"

        for tipo in opciones:
            btn = ft.Container(
                content=ft.Text(tipo, size=12, color=ft.colors.BLACK),
                bgcolor=ft.colors.BLUE if registro.get("descanso", "SN") == tipo else ft.colors.WHITE,
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

    def recalcular_horas(self, entrada: str, salida: str, descanso: str) -> str:
        try:
            def parse_hora(valor):
                if isinstance(valor, time):
                    return valor
                if isinstance(valor, timedelta):
                    return (datetime.min + valor).time()
                valor = str(valor).strip()
                for fmt in ("%H:%M:%S", "%H:%M"):
                    try:
                        return datetime.strptime(valor, fmt).time()
                    except:
                        continue
                raise ValueError(f"Formato inválido de hora: {valor}")

            entrada_time = parse_hora(entrada)
            salida_time = parse_hora(salida)
            dt_entrada = datetime.combine(date.min, entrada_time)
            dt_salida = datetime.combine(date.min, salida_time)
            if dt_salida <= dt_entrada:
                dt_salida += timedelta(days=1)

            total_segundos = (dt_salida - dt_entrada).total_seconds()
            total_segundos -= self.calculo_helper.obtener_minutos_descanso(descanso) * 60
            total_segundos = max(total_segundos, 0)

            horas = int(total_segundos) // 3600
            minutos = (int(total_segundos) % 3600) // 60
            segundos = int(total_segundos) % 60

            return f"{horas:02}:{minutos:02}:{segundos:02}"

        except Exception as e:
            print(f"❗ Error recalculando horas: {e}")
            return "00:00:00"

    def _wrap_cell(self, control, width: int) -> ft.Container:
        return ft.Container(content=control, width=width)
