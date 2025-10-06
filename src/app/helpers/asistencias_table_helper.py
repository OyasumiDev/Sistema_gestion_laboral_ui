import flet as ft
from datetime import datetime, date


class AsistenciasTableHelper:
    def __init__(self, on_guardar_fila, on_cancelar_fila, on_editar, on_guardar_edicion, on_cancelar_edicion, on_eliminar=None):
        self.on_guardar_fila = on_guardar_fila
        self.on_cancelar_fila = on_cancelar_fila
        self.on_editar = on_editar
        self.on_guardar_edicion = on_guardar_edicion
        self.on_cancelar_edicion = on_cancelar_edicion
        self.on_eliminar = on_eliminar

    # -------------------- Filas --------------------
    def crear_fila_nueva(self, registro: dict, grupo_importacion: str, on_update_valor):
        return ft.DataRow(cells=[
            ft.DataCell(self._crear_textfield(registro.get("numero_nomina", ""), 100,
                lambda e: on_update_valor(grupo_importacion, "numero_nomina", e.control.value, "nuevo"))),
            ft.DataCell(ft.Text("-")),
            ft.DataCell(self._crear_textfield(registro.get("fecha", ""), 120,
                lambda e: on_update_valor(grupo_importacion, "fecha", e.control.value, "nuevo"))),
            ft.DataCell(self._crear_textfield(registro.get("hora_entrada", ""), 120,
                lambda e: on_update_valor(grupo_importacion, "hora_entrada", e.control.value, "nuevo"))),
            ft.DataCell(self._crear_textfield(registro.get("hora_salida", ""), 120,
                lambda e: on_update_valor(grupo_importacion, "hora_salida", e.control.value, "nuevo"))),
            ft.DataCell(self._crear_botones_descanso(on_update_valor, grupo_importacion=grupo_importacion, tipo_edicion="nuevo")),
            ft.DataCell(self._crear_textfield(registro.get("tiempo_trabajo", "0.00"), 120, read_only=True)),
            ft.DataCell(ft.Text("PENDIENTE")),
            ft.DataCell(ft.Row([
                ft.IconButton(icon=ft.icons.SAVE, tooltip="Guardar", on_click=lambda e: self.on_guardar_fila(grupo_importacion)),
                ft.IconButton(icon=ft.icons.CANCEL, tooltip="Cancelar", on_click=lambda e: self.on_cancelar_fila(grupo_importacion))
            ], spacing=4))
        ])

    def crear_fila_edicion(self, registro: dict, on_update_valor):
        numero_nomina, fecha = registro["numero_nomina"], registro["fecha"]
        return ft.DataRow(cells=[
            ft.DataCell(ft.Text(str(numero_nomina))),
            ft.DataCell(ft.Text(registro.get("nombre_completo", ""))),
            ft.DataCell(ft.Text(str(fecha))),
            ft.DataCell(self._crear_textfield(registro.get("hora_entrada", ""), 120,
                lambda e: on_update_valor(numero_nomina, fecha, "hora_entrada", e.control.value, "edicion"))),
            ft.DataCell(self._crear_textfield(registro.get("hora_salida", ""), 120,
                lambda e: on_update_valor(numero_nomina, fecha, "hora_salida", e.control.value, "edicion"))),
            ft.DataCell(self._crear_botones_descanso(on_update_valor, numero_nomina=numero_nomina, fecha=fecha, tipo_edicion="edicion")),
            ft.DataCell(self._crear_textfield(registro.get("tiempo_trabajo", "0.00"), 120, read_only=True)),
            ft.DataCell(ft.Text(registro.get("estado", ""))),
            ft.DataCell(ft.Row([
                ft.IconButton(icon=ft.icons.SAVE, tooltip="Guardar edición", on_click=lambda e: self.on_guardar_edicion(numero_nomina, fecha)),
                ft.IconButton(icon=ft.icons.CANCEL, tooltip="Cancelar", on_click=lambda e: self.on_cancelar_edicion(numero_nomina, fecha))
            ], spacing=4))
        ])

    def crear_fila_lectura(self, registro: dict):
        numero_nomina, fecha = registro["numero_nomina"], registro["fecha"]
        descanso_valor = registro.get("descanso", "SN")
        descanso_texto = f"{descanso_valor}: {self._descanso_a_minutos(descanso_valor)} min"

        acciones = [
            ft.IconButton(icon=ft.icons.EDIT, tooltip="Editar", on_click=lambda e: self.on_editar(numero_nomina, fecha))
        ]
        if self.on_eliminar:
            acciones.append(ft.IconButton(icon=ft.icons.DELETE_OUTLINE, tooltip="Eliminar", icon_color=ft.colors.RED_600,
                                          on_click=lambda e: self.on_eliminar(numero_nomina, fecha)))

        return ft.DataRow(cells=[
            ft.DataCell(ft.Text(str(numero_nomina))),
            ft.DataCell(ft.Text(registro.get("nombre_completo", ""))),
            ft.DataCell(ft.Text(str(fecha))),
            ft.DataCell(ft.Text(registro.get("hora_entrada", ""))),
            ft.DataCell(ft.Text(registro.get("hora_salida", ""))),
            ft.DataCell(ft.Text(descanso_texto)),
            ft.DataCell(ft.Text(registro.get("tiempo_trabajo", "0.00"))),
            ft.DataCell(ft.Text(registro.get("estado", ""))),
            ft.DataCell(ft.Row(acciones, spacing=4))
        ])

    # -------------------- Helpers --------------------
    def _crear_textfield(self, valor, ancho, on_change=None, read_only=False):
        return ft.TextField(
            value=valor, width=ancho, read_only=read_only, on_change=on_change,
            text_size=12, content_padding=ft.padding.symmetric(horizontal=4, vertical=2)
        )

    def _crear_botones_descanso(self, on_update_valor, **kwargs):
        botones, tipos = [], ["SN", "MD", "CMP"]
        tipo_edicion = kwargs["tipo_edicion"]

        if tipo_edicion == "nuevo":
            grupo_importacion = kwargs["grupo_importacion"]
            for tipo in tipos:
                botones.append(ft.FilledButton(text=tipo, style=ft.ButtonStyle(padding=ft.padding.all(2)),
                    on_click=lambda e, t=tipo: on_update_valor(grupo_importacion, "descanso", t, "nuevo")))
        elif tipo_edicion == "edicion":
            numero_nomina, fecha = kwargs["numero_nomina"], kwargs["fecha"]
            for tipo in tipos:
                botones.append(ft.FilledButton(text=tipo, style=ft.ButtonStyle(padding=ft.padding.all(2)),
                    on_click=lambda e, t=tipo: on_update_valor(numero_nomina, fecha, "descanso", t, "edicion")))

        return ft.Row(botones, spacing=3)

    def _descanso_a_minutos(self, tipo):
        return {"MD": 30, "CMP": 60, "SN": 0}.get(tipo, 0)

    def recalcular_horas(self, entrada: str, salida: str, descanso: str) -> str:
        try:
            entrada_time = datetime.strptime(entrada, "%H:%M").time()
            salida_time = datetime.strptime(salida, "%H:%M").time()
            total = (datetime.combine(date.min, salida_time) - datetime.combine(date.min, entrada_time)).total_seconds() / 3600
            total -= self._descanso_a_minutos(descanso) / 60
            return f"{max(total, 0):.2f}"
        except Exception:
            return "0.00"
