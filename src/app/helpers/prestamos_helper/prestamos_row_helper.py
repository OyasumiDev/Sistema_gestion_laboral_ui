import flet as ft
from typing import Callable, Dict
from app.helpers.prestamos_helper.prestamos_scroll_helper import PrestamosScrollHelper
from app.helpers.prestamos_helper.prestamos_validation_helper import PrestamosValidationHelper
from app.helpers.boton_factory import (
    crear_boton_editar,
    crear_boton_eliminar,
    crear_boton_guardar,
    crear_boton_cancelar,
)


class PrestamosRowHelper:
    def __init__(self, actualizar_callback: Callable):
        self.actualizar_callback = actualizar_callback
        self.validador = PrestamosValidationHelper()

    def _wrap_cell(self, control, width: int) -> ft.Container:
        return ft.Container(
            content=control,
            width=width,
            alignment=ft.alignment.center,
            padding=ft.padding.symmetric(horizontal=2)
        )

    def _build_fila_editable(
        self,
        registro: Dict,
        on_save: Callable,
        on_cancel: Callable,
        page: ft.Page,
        scroll_key: str,
        modo: str = "nuevo"
    ) -> ft.DataRow:
        es_cerrado = registro.get("estado", "").lower() == "cerrado"
        editable = not es_cerrado

        numero_input = ft.TextField(
            value=str(registro.get("numero_nomina", "")),
            width=100,
            border_color=ft.colors.GREY,
            autofocus=True,
            read_only=not editable
        )

        monto_input = ft.TextField(
            value=str(registro.get("monto", "")),
            width=120,
            border_color=ft.colors.GREY,
            read_only=not editable
        )

        fecha_input = ft.TextField(
            value=str(registro.get("fecha_solicitud", "")),
            width=120,
            border_color=ft.colors.GREY,
            read_only=modo == "nuevo" or not editable
        )

        saldo_text = ft.Text(str(registro.get("saldo", "0.00")), width=100)
        pagado_text = ft.Text(str(registro.get("pagado", "0.00")), width=100)
        estado_text = ft.Text(registro.get("estado", "pendiente"), width=100)

        def on_change_numero(e):
            registro["numero_nomina"] = e.control.value
            self.validador.validar_numero_nomina(numero_input)

        def on_change_monto(e):
            registro["monto"] = e.control.value
            self.validador.validar_monto(monto_input)

        numero_input.on_change = on_change_numero
        monto_input.on_change = on_change_monto

        def on_guardar(e):
            if es_cerrado:
                print("⚠️ No se puede editar un préstamo cerrado.")
                return
            valido_numero = self.validador.validar_numero_nomina(numero_input)
            valido_monto = self.validador.validar_monto(monto_input)
            valido_fecha = self.validador.validar_fecha(fecha_input)
            if valido_numero and valido_monto and valido_fecha:
                on_save()
            else:
                print("❌ Validación fallida en préstamo")

        acciones = ft.Row([
            crear_boton_guardar(on_guardar),
            crear_boton_cancelar(lambda e: on_cancel())
        ], spacing=5)

        PrestamosScrollHelper.scroll_to_group_after_build(page, scroll_key)

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(numero_input, 100)),
            ft.DataCell(self._wrap_cell(monto_input, 120)),
            ft.DataCell(self._wrap_cell(fecha_input, 120)),
            ft.DataCell(self._wrap_cell(saldo_text, 100)),
            ft.DataCell(self._wrap_cell(pagado_text, 100)),
            ft.DataCell(self._wrap_cell(estado_text, 100)),
            ft.DataCell(self._wrap_cell(acciones, 110)),
        ])

    def build_fila_nueva(
        self,
        registro: Dict,
        on_save: Callable,
        on_cancel: Callable,
        page: ft.Page,
        scroll_key: str
    ) -> ft.DataRow:
        return self._build_fila_editable(registro, on_save, on_cancel, page, scroll_key, modo="nuevo")

    def build_fila_edicion(
        self,
        registro: Dict,
        on_save: Callable,
        on_cancel: Callable,
        page: ft.Page,
        scroll_key: str
    ) -> ft.DataRow:
        return self._build_fila_editable(registro, on_save, on_cancel, page, scroll_key, modo="edicion")

    def build_fila_lectura(self, registro: Dict, on_edit: Callable, on_delete: Callable = None) -> ft.DataRow:
        acciones = []

        if registro.get("estado", "").lower() != "cerrado":
            acciones.append(crear_boton_editar(lambda e: on_edit(registro)))

        if on_delete:
            acciones.append(crear_boton_eliminar(lambda e: on_delete(registro)))

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(ft.Text(str(registro.get("numero_nomina", ""))), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(str(registro.get("monto", ""))), 120)),
            ft.DataCell(self._wrap_cell(ft.Text(str(registro.get("fecha_solicitud", ""))), 120)),
            ft.DataCell(self._wrap_cell(ft.Text(str(registro.get("saldo", "0.00"))), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(str(registro.get("pagado", "0.00"))), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(str(registro.get("estado", ""))), 100)),
            ft.DataCell(self._wrap_cell(ft.Row(acciones, spacing=5), 110))
        ])
