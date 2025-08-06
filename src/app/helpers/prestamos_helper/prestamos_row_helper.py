import flet as ft
from typing import Callable, Dict
from app.helpers.prestamos_helper.prestamos_scroll_helper import PrestamosScrollHelper
from app.helpers.prestamos_helper.prestamos_validation_helper import PrestamosValidationHelper
from app.models.employes_model import EmployesModel
from datetime import date
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
        self.empleado_model = EmployesModel()

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
        modo: str = "nuevo",
        campos_ref: Dict = None
    ) -> ft.DataRow:
        hoy = date.today().strftime("%d/%m/%Y")
        es_cerrado = registro.get("estado", "").lower() == "cerrado"
        editable = not es_cerrado

        numero_input = ft.TextField(
            value=str(registro.get("numero_nomina", "")),
            width=80,
            border_color=ft.colors.GREY,
            autofocus=True,
            read_only=not editable,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        empleado_text = ft.Text(registro.get("nombre_empleado", ""), width=200)

        monto_input = ft.TextField(
            value=str(registro.get("monto", "")),
            width=100,
            border_color=ft.colors.GREY,
            read_only=not editable,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        grupo_empleado_input = ft.TextField(
            value=str(registro.get("grupo_empleado", "")),
            width=140,
            border_color=ft.colors.GREY,
            read_only=not editable
        )

        fecha_input = ft.TextField(
            value=str(registro.get("fecha_solicitud", hoy)),
            width=120,
            border_color=ft.colors.GREY,
            read_only=modo == "nuevo" or not editable
        )

        saldo_text = ft.Text(str(registro.get("saldo", "0.00")), width=80)
        pagado_text = ft.Text(str(registro.get("pagado", "0.00")), width=80)
        estado_text = ft.Text(registro.get("estado", "pendiente"), width=80)

        def on_change_numero(e):
            numero = e.control.value.strip()
            if not numero.isdigit():
                e.control.border_color = self.validador.COLOR_ERROR
                empleado_text.value = ""
            else:
                empleado = self.empleado_model.get_by_numero_nomina(int(numero))
                if empleado:
                    empleado_text.value = empleado["nombre_completo"]
                    e.control.border_color = self.validador.COLOR_OK
                else:
                    empleado_text.value = ""
                    e.control.border_color = self.validador.COLOR_ERROR
            e.control.update()
            empleado_text.update()

        def on_change_monto(e):
            texto = e.control.value.strip().replace(",", ".")
            if texto and texto.replace('.', '', 1).isdigit():
                try:
                    monto = float(texto)
                    registro["monto"] = f"{monto:.2f}"
                except:
                    registro["monto"] = texto
            else:
                registro["monto"] = texto
            self.validador.validar_monto(monto_input, limite=10000)

        def on_change_grupo(e):
            texto = e.control.value.strip()
            registro["grupo_empleado"] = texto
            if texto:
                e.control.border_color = self.validador.COLOR_OK
            else:
                e.control.border_color = self.validador.COLOR_ERROR
            e.control.update()

        numero_input.on_change = on_change_numero
        monto_input.on_change = on_change_monto
        grupo_empleado_input.on_change = on_change_grupo

        def on_guardar(e):
            if es_cerrado:
                print("⚠️ No se puede editar un préstamo cerrado.")
                return

            numero = numero_input.value.strip()
            monto_texto = monto_input.value.strip().replace(",", ".")
            fecha_texto = fecha_input.value.strip()

            if not (
                self.validador.validar_campos_completos(numero_input, monto_input, fecha_input, grupo_empleado_input)
                and numero.isdigit()
                and self.empleado_model.get_by_numero_nomina(int(numero))
            ):
                print("❌ Validación fallida. Corrige los campos marcados en rojo.")
                return

            try:
                monto_float = float(monto_texto)
                monto_input.value = f"{monto_float:.2f}"
                monto_input.update()
            except:
                pass

            fecha_convertida = self.validador.convertir_fecha_mysql(fecha_texto)
            registro["fecha_solicitud"] = fecha_convertida
            fecha_input.value = fecha_convertida
            fecha_input.update()

            on_save()

        acciones = ft.Row([
            crear_boton_guardar(on_guardar),
            crear_boton_cancelar(lambda e: on_cancel())
        ], spacing=5)

        if campos_ref is not None:
            campos_ref["numero_nomina"] = numero_input
            campos_ref["monto"] = monto_input
            campos_ref["fecha"] = fecha_input
            campos_ref["grupo_empleado"] = grupo_empleado_input

        PrestamosScrollHelper.scroll_to_group_after_build(page, scroll_key)

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(numero_input, 80)),
            ft.DataCell(self._wrap_cell(empleado_text, 200)),
            ft.DataCell(self._wrap_cell(monto_input, 100)),
            ft.DataCell(self._wrap_cell(saldo_text, 80)),
            ft.DataCell(self._wrap_cell(pagado_text, 80)),
            ft.DataCell(self._wrap_cell(estado_text, 80)),
            ft.DataCell(self._wrap_cell(grupo_empleado_input, 140)),
            ft.DataCell(self._wrap_cell(fecha_input, 120)),
            ft.DataCell(self._wrap_cell(acciones, 110)),
        ])

    def build_fila_nueva(
        self,
        registro: Dict,
        on_save: Callable,
        on_cancel: Callable,
        page: ft.Page,
        scroll_key: str,
        campos_ref: Dict = None,
        grupo_empleado: str = None
    ) -> ft.DataRow:
        if grupo_empleado:
            registro["grupo_empleado"] = grupo_empleado

        return self._build_fila_editable(
            registro, on_save, on_cancel, page, scroll_key,
            modo="nuevo", campos_ref=campos_ref
        )

    def build_fila_edicion(
        self,
        registro: Dict,
        on_save: Callable,
        on_cancel: Callable,
        page: ft.Page,
        scroll_key: str,
        campos_ref: Dict = None
    ) -> ft.DataRow:
        return self._build_fila_editable(
            registro=registro,
            on_save=on_save,
            on_cancel=on_cancel,
            page=page,
            scroll_key=scroll_key,
            modo="edicion",
            campos_ref=campos_ref
        )

    def build_fila_lectura(
        self,
        registro: Dict,
        on_edit: Callable,
        on_delete: Callable = None,
        on_pagos: Callable = None
    ) -> ft.DataRow:
        acciones = []

        if registro.get("estado", "").lower() != "cerrado":
            acciones.append(crear_boton_editar(lambda e: on_edit(registro)))

        if on_pagos:
            acciones.append(
                ft.IconButton(
                    icon=ft.icons.PAID,
                    tooltip="Ver pagos",
                    on_click=lambda e: on_pagos(registro),
                )
            )

        if on_delete:
            acciones.append(crear_boton_eliminar(lambda e: on_delete(registro)))

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(ft.Text(str(registro.get("numero_nomina", ""))), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(str(registro.get("nombre_empleado", ""))), 200)),
            ft.DataCell(self._wrap_cell(ft.Text(str(registro.get("monto", ""))), 120)),
            ft.DataCell(self._wrap_cell(ft.Text(str(registro.get("saldo", "0.00"))), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(str(registro.get("pagado", "0.00"))), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(str(registro.get("estado", ""))), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(str(registro.get("grupo_empleado", ""))), 140)),
            ft.DataCell(self._wrap_cell(ft.Text(str(registro.get("fecha_solicitud", ""))), 120)),
            ft.DataCell(self._wrap_cell(ft.Row(acciones, spacing=5), 120)),
        ])