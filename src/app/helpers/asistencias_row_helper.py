import flet as ft
from typing import Callable, Dict
from datetime import datetime, date
from app.helpers.calculo_horas_helper import CalculoHorasHelper


class AsistenciasRowHelper:
    def __init__(self, recalcular_callback: Callable, actualizar_callback: Callable):
        self.recalcular_callback = recalcular_callback
        self.actualizar_callback = actualizar_callback
        self.calculo_helper = CalculoHorasHelper()

    def build_fila_nueva(self, grupo_importacion: str, registro: Dict, on_save: Callable, on_cancel: Callable) -> ft.DataRow:
        print(f"✅ build_fila_nueva - Grupo: {grupo_importacion}, Registro: {registro}")
        descanso_widget = self._crear_botones_descanso(grupo_importacion, registro)

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(self._crear_textfield(grupo_importacion, "numero_nomina", registro), 100)),
            ft.DataCell(self._wrap_cell(ft.Text("-"), 150)),
            ft.DataCell(self._wrap_cell(self._crear_textfield(grupo_importacion, "fecha", registro), 110)),
            ft.DataCell(self._wrap_cell(self._crear_textfield(grupo_importacion, "hora_entrada", registro), 100)),
            ft.DataCell(self._wrap_cell(self._crear_textfield(grupo_importacion, "hora_salida", registro), 100)),
            ft.DataCell(self._wrap_cell(descanso_widget, 180)),
            ft.DataCell(self._wrap_cell(ft.TextField(value=registro.get("tiempo_trabajo", "0.00"), width=80, read_only=True), 90)),
            ft.DataCell(self._wrap_cell(ft.Text("PENDIENTE"), 100)),
            ft.DataCell(self._wrap_cell(ft.Row([
                ft.IconButton(icon=ft.icons.SAVE, tooltip="Guardar", on_click=lambda e: on_save()),
                ft.IconButton(icon=ft.icons.CANCEL, tooltip="Cancelar", on_click=lambda e: on_cancel())
            ], spacing=5), 100))
        ])

    def build_fila_edicion(self, registro: Dict, on_save: Callable, on_cancel: Callable) -> ft.DataRow:
        numero_nomina = registro["numero_nomina"]
        fecha = registro["fecha"]
        print(f"✅ build_fila_edicion - Nomina: {numero_nomina}, Fecha: {fecha}, Registro: {registro}")

        descanso_widget = self._crear_botones_descanso(numero_nomina, registro)

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(ft.Text(str(numero_nomina)), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("nombre_completo", "")), 150)),
            ft.DataCell(self._wrap_cell(ft.Text(str(fecha)), 110)),
            ft.DataCell(self._wrap_cell(self._crear_textfield(numero_nomina, "hora_entrada", registro), 100)),
            ft.DataCell(self._wrap_cell(self._crear_textfield(numero_nomina, "hora_salida", registro), 100)),
            ft.DataCell(self._wrap_cell(descanso_widget, 180)),
            ft.DataCell(self._wrap_cell(ft.TextField(value=registro.get("tiempo_trabajo", "0.00"), width=80, read_only=True), 90)),
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
        print(f"✅ build_fila_vista - Nomina: {numero_nomina}, Fecha: {fecha}, Descanso: {descanso}")
        descanso_texto = f"{descanso}: {self.calculo_helper.obtener_minutos_descanso(descanso)} min"

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(ft.Text(str(numero_nomina)), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("nombre_completo", "")), 150)),
            ft.DataCell(self._wrap_cell(ft.Text(str(fecha)), 110)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("hora_entrada", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("hora_salida", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(descanso_texto), 180)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("tiempo_trabajo", "0.00")), 90)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("estado", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Row([
                ft.IconButton(
                    icon=ft.icons.EDIT,
                    tooltip="Editar",
                    on_click=lambda e: on_edit(numero_nomina, fecha)
                )
            ]), 100))
        ])

    def _crear_textfield(self, grupo: str, campo: str, registro: Dict) -> ft.TextField:
        return ft.TextField(
            value=registro.get(campo, ""),
            width=100,
            on_change=lambda e: self._on_change(grupo, campo, e.control.value)
        )

    def _crear_botones_descanso(self, grupo: str, registro: Dict) -> ft.Container:
        botones = []
        for tipo in ["SN", "MD", "CMP"]:
            botones.append(
                ft.FilledButton(
                    tipo,
                    style=ft.ButtonStyle(padding=ft.Padding(5, 0, 5, 0)),
                    on_click=lambda e, t=tipo: self._on_change(grupo, "descanso", t)
                )
            )
        return ft.Container(
            content=ft.Row(
                controls=botones,
                spacing=3,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
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
            entrada_time = datetime.strptime(entrada, "%H:%M").time()
            salida_time = datetime.strptime(salida, "%H:%M").time()
            total = (datetime.combine(date.min, salida_time) - datetime.combine(date.min, entrada_time)).total_seconds() / 3600
            total -= self.calculo_helper.obtener_minutos_descanso(descanso) / 60
            return f"{max(total, 0):.2f}"
        except Exception as e:
            print(f"❗ Error recalculando horas: {e}")
            return "0.00"

    def _wrap_cell(self, control, width: int) -> ft.Container:
        return ft.Container(content=control, width=width)
