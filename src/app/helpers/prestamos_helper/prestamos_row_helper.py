import flet as ft
from typing import Callable, Dict, Optional
from datetime import date

from app.helpers.prestamos_helper.prestamos_validation_helper import PrestamosValidationHelper
from app.models.employes_model import EmployesModel
from app.helpers.boton_factory import (
    crear_boton_editar,
    crear_boton_eliminar,
    crear_boton_guardar,
    crear_boton_cancelar,
)


class PrestamosRowHelper:
    """
    Helper de filas para el módulo de préstamos (SIN DataRow).
    - Devuelve `ft.Container` / `ft.Row` para insertarlos directo en ExpansionTile.
    - `build_fila_nueva()` expone `campos_ref` para que el contenedor lea los valores.
    - `on_save()` y `on_cancel()` no reciben argumentos; el contenedor usa `campos_ref`.
    - Fecha editable en modo "nuevo" y autollenado si está vacía.
    """

    def __init__(self, actualizar_callback: Optional[Callable] = None):
        self.actualizar_callback = actualizar_callback
        self.validador = PrestamosValidationHelper()
        self.empleado_model = EmployesModel()

        # Anchos aproximados para la fila
        self.W_ID = 110
        self.W_NOMBRE = 220
        self.W_MONTO = 120
        self.W_FECHA = 140
        self.W_GRUPO = 160

    # -------------------- API pública --------------------

    def build_fila_nueva(
        self,
        registro: Dict,
        on_save: Callable,
        on_cancel: Callable,
        page: ft.Page,
        scroll_key: str,
        campos_ref: Optional[Dict[str, ft.TextField]] = None,
        grupo_empleado: Optional[str] = None,  # <-- se ignora visualmente (calculado en el container)
    ) -> ft.Control:
        """
        Crea una fila editable para ALTA de préstamo. Devuelve un Container listo para insertar.
        """
        return self._build_fila_editable(
            registro=registro,
            on_save=on_save,
            on_cancel=on_cancel,
            page=page,
            scroll_key=scroll_key,
            campos_ref=campos_ref,
            editable=True,
            modo="nuevo",
            grupo_empleado=grupo_empleado,  # se conserva por compatibilidad, pero no se pinta
        )


    def build_fila_lectura(
        self,
        registro: Dict,
        on_edit: Optional[Callable] = None,
        on_delete: Optional[Callable] = None,
        on_pagos: Optional[Callable] = None,
    ) -> ft.Control:
        """
        Fila en modo lectura con acciones opcionales. Devuelve un Container listo para insertar.
        (Sin mostrar "Grupo empleado")
        """
        numero = registro.get("numero_nomina", "")
        nombre = registro.get("nombre_empleado", "")
        monto = registro.get("monto", "")
        saldo = registro.get("saldo", "0.00")
        pagado = registro.get("pagado", "0.00")
        estado = registro.get("estado", "")
        fecha = registro.get("fecha_solicitud", "")

        chips = ft.Row(
            [
                ft.Chip(label=ft.Text(f"Saldo: {saldo}")),
                ft.Chip(label=ft.Text(f"Pagado: {pagado}")),
                ft.Chip(label=ft.Text(f"Estado: {estado}")),
            ],
            spacing=6,
            wrap=True,
        )

        acciones: list[ft.Control] = []
        if on_pagos:
            acciones.append(
                ft.IconButton(icon=ft.icons.RECEIPT_LONG, tooltip="Ver pagos", on_click=lambda e: on_pagos())
            )
        if on_edit and str(estado).lower() != "cerrado":
            acciones.append(crear_boton_editar(lambda e: on_edit()))
        if on_delete:
            acciones.append(crear_boton_eliminar(lambda e: on_delete()))

        fila = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(f"No. {numero}", width=self.W_ID),
                    ft.Text(nombre, width=self.W_NOMBRE),
                    ft.Text(f"Monto: {monto}", width=self.W_MONTO),
                    ft.Text(f"Fecha: {fecha}", width=self.W_FECHA),
                    ft.Container(chips, expand=True),
                    ft.Container(
                        content=ft.Row(acciones, spacing=8),
                        margin=ft.margin.only(right=15),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=10,
            border=ft.border.all(1, ft.colors.GREY_300),
            border_radius=12,
        )
        return fila

    # -------------------- Internos --------------------

    def _build_fila_editable(
        self,
        registro: Dict,
        on_save: Callable,
        on_cancel: Callable,
        page: ft.Page,
        scroll_key: str,
        campos_ref: Optional[Dict[str, ft.TextField]],
        editable: bool,
        modo: str,  # "nuevo" | "edicion"
        grupo_empleado: Optional[str],
    ) -> ft.Control:
        campos_ref = campos_ref if campos_ref is not None else {}
        hoy = date.today().strftime("%d/%m/%Y")
        es_cerrado = str(registro.get("estado", "")).lower() == "cerrado"
        editable = editable and not es_cerrado

        # Numero de nómina
        numero_val = str(registro.get("numero_nomina", "")).strip()
        numero_input = ft.TextField(
            value=numero_val,
            width=self.W_ID,
            dense=True,
            label="No. nómina",
            keyboard_type=ft.KeyboardType.NUMBER,
            read_only=not editable if not (grupo_empleado and numero_val) else True,
        )

        # Nombre (solo display)
        nombre_lbl = ft.Text(str(registro.get("nombre_empleado", "")), width=self.W_NOMBRE)

        # Monto
        monto_input = ft.TextField(
            value=str(registro.get("monto", "")),
            width=self.W_MONTO,
            dense=True,
            label="Monto",
            keyboard_type=ft.KeyboardType.NUMBER,
            read_only=not editable,
        )

        # Fecha (editable en nuevo) -> usa HOY si viene vacío o None
        fecha_val = registro.get("fecha_solicitud") or hoy
        fecha_input = ft.TextField(
            value=str(fecha_val),
            width=self.W_FECHA,
            dense=True,
            label="Fecha (DD/MM/YYYY)",
            read_only=not editable,
        )

        # Exponer refs a contenedor (SIN grupo_empleado)
        campos_ref["numero_nomina"] = numero_input
        campos_ref["monto"] = monto_input
        campos_ref["fecha"] = fecha_input

        # ---- validaciones on_change ----
        def _on_change_numero(e):
            numero = e.control.value.strip()
            if not numero.isdigit():
                e.control.border_color = self.validador.COLOR_ERROR
                nombre_lbl.value = ""
            else:
                try:
                    emp = self.empleado_model.get_by_numero_nomina(int(numero))
                except Exception:
                    emp = None
                if emp:
                    nombre_lbl.value = emp.get("nombre_completo", "")
                    e.control.border_color = self.validador.COLOR_OK
                else:
                    nombre_lbl.value = ""
                    e.control.border_color = self.validador.COLOR_ERROR
            e.control.update()
            nombre_lbl.update()

        def _on_change_monto(e):
            self.validador.validar_monto(monto_input, limite=10000.0)

        def _on_change_fecha(e):
            self.validador.validar_fecha(fecha_input)

        numero_input.on_change = _on_change_numero
        monto_input.on_change = _on_change_monto
        fecha_input.on_change = _on_change_fecha

        # ---- acciones ----
        def on_guardar_click(e):
            if es_cerrado:
                if page:
                    page.show_snack_bar(ft.SnackBar(ft.Text("No se puede editar un préstamo cerrado.")))
                return

            # Completar fecha si está vacía
            self.validador.establecer_fecha_actual_si_vacia(fecha_input)

            ok_numero = self.validador.validar_numero_nomina(numero_input)
            ok_monto = self.validador.validar_monto(monto_input, limite=10000.0)
            ok_fecha = self.validador.validar_fecha(fecha_input)

            ok_campos = all([
                bool((numero_input.value or "").strip()),
                bool((monto_input.value or "").strip()),
                bool((fecha_input.value or "").strip()),
            ])

            if not (ok_campos and ok_numero and ok_monto and ok_fecha):
                if page:
                    page.show_snack_bar(ft.SnackBar(ft.Text("Corrige los campos marcados en rojo.")))
                return

            on_save()

        def on_cancelar_click(e):
            on_cancel()

        acciones = ft.Row(
            controls=[crear_boton_guardar(on_guardar_click), crear_boton_cancelar(on_cancelar_click)],
            spacing=8,
        )

        fila = ft.Container(
            key=scroll_key,
            content=ft.Row(
                controls=[
                    numero_input,
                    nombre_lbl,
                    monto_input,
                    fecha_input,
                    ft.Container(expand=True),
                    acciones,
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=False,
            ),
            padding=10,
            border=ft.border.all(1, ft.colors.GREY_300),
            border_radius=12,
        )

        # El scroll se hace desde el contenedor tras _actualizar_vista()
        return fila
