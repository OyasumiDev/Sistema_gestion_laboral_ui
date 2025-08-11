from __future__ import annotations
import flet as ft
from typing import Dict, Any, Callable, Optional


class RowRefresh:
    """
    Construye y actualiza filas de pagos evitando índices mágicos.
    Las keys viven en los CONTROLES internos, no en DataCell (Flet 0.24).
    """

    # keys internas (children)
    K_ID = "p-id"
    K_DESC = "p-descuentos"
    K_PREST = "p-prestamos"
    K_SALDO = "p-saldo"
    K_DEP_INPUT = "p-deposito-input"
    K_DEP_CONTAINER = "p-deposito-container"
    K_EFECTIVO = "p-efectivo"
    K_TOTAL = "p-total"
    K_ESTADO = "p-estado-label"

    def build_row(
        self,
        pago_row: Dict[str, Any],
        *,
        descuentos_value: float,
        prestamos_value: float,
        saldo_value: float,
        deposito_value: float,
        efectivo_value: float,
        total_value: float,
        esta_pagado: bool,
        on_confirmar: Callable[[int], None],
        on_eliminar: Callable[[int], None],
        on_editar_descuentos: Callable[[Dict[str, Any]], None],
        on_editar_prestamos: Callable[[Dict[str, Any]], None],
        on_deposito_change: Callable[[str], None],
        on_deposito_blur: Optional[Callable[[], None]] = None,
        on_deposito_submit: Optional[Callable[[], None]] = None,
        tiene_prestamo_activo: bool = True,
    ) -> ft.DataRow:

        # acepta id_pago_nomina o id_pago (fallback)
        id_pago_nomina = int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago"))
        numero_nomina = int(pago_row["numero_nomina"])
        nombre = str(pago_row.get("nombre_completo") or pago_row.get("empleado") or "")
        fecha_pago = str(pago_row.get("fecha_pago"))
        horas = str(pago_row.get("total_horas_trabajadas"))
        sueldo_hora = float(pago_row.get("sueldo_por_hora", 0.0))
        monto_base = float(pago_row.get("monto_base", 0.0))
        estado_txt = "Pagado" if esta_pagado else "Pendiente"

        # ---------- celdas estáticas ----------
        c_id = ft.DataCell(ft.Text(str(id_pago_nomina), key=self.K_ID))
        c_nomina = ft.DataCell(ft.Text(str(numero_nomina)))
        c_nombre = ft.DataCell(ft.Text(nombre))
        c_fecha = ft.DataCell(ft.Text(fecha_pago))
        c_horas = ft.DataCell(ft.Text(horas))
        c_sueldo = ft.DataCell(ft.Text(f"${sueldo_hora:.2f}"))
        c_base = ft.DataCell(ft.Text(f"${monto_base:.2f}"))

        # ---------- Descuentos ----------
        desc_text = ft.Text(f"${float(descuentos_value):.2f}", key=self.K_DESC)
        btn_desc = ft.IconButton(
            icon=ft.icons.EDIT_NOTE,
            tooltip="Editar descuentos",
            on_click=lambda e, r=pago_row: on_editar_descuentos(r),
            disabled=esta_pagado,
        )
        c_desc = ft.DataCell(ft.Row([desc_text, btn_desc]))

        # ---------- Préstamos ----------
        prest_text = ft.Text(f"${float(prestamos_value):.2f}", key=self.K_PREST)
        btn_prest = ft.IconButton(
            icon=ft.icons.EDIT_NOTE,
            tooltip=("Editar préstamos" if tiene_prestamo_activo else "Sin préstamo activo"),
            on_click=(lambda e, r=pago_row: on_editar_prestamos(r)) if tiene_prestamo_activo else None,
            disabled=esta_pagado or (not tiene_prestamo_activo),
            icon_color=ft.colors.BLUE if (not esta_pagado and tiene_prestamo_activo) else None,
        )
        c_prest = ft.DataCell(ft.Row([prest_text, btn_prest]))

        # ---------- Saldo (ajuste) ----------
        c_saldo = ft.DataCell(ft.Text(f"${float(saldo_value):.2f}", key=self.K_SALDO))

        # ---------- Depósito ----------
        if esta_pagado:
            dep_content = ft.Text(f"${float(deposito_value):.2f}")
        else:
            dep_field = ft.TextField(
                key=self.K_DEP_INPUT,
                value="0.0" if float(deposito_value) == 0 else str(deposito_value),
                hint_text="0.0",
                height=36,
                width=120,
                text_align=ft.TextAlign.RIGHT,
                border_color=ft.colors.BLUE,
                keyboard_type=ft.KeyboardType.NUMBER,
                input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9\.\-]"),
                # on_focus=lambda e: setattr(e.control, "value", ""),  # ❌ quítalo
                on_change=lambda e: on_deposito_change(e.control.value),
                on_blur=lambda e: on_deposito_blur() if on_deposito_blur else None,
                on_submit=lambda e: on_deposito_submit() if on_deposito_submit else None,
            )

            dep_content = ft.Container(
                key=self.K_DEP_CONTAINER,
                width=120,
                content=dep_field,
            )
        c_dep = ft.DataCell(dep_content)

        # ---------- Efectivo / Total ----------
        c_efectivo = ft.DataCell(ft.Text(f"${float(efectivo_value):.2f}", key=self.K_EFECTIVO))
        c_total = ft.DataCell(ft.Text(f"${float(total_value):.2f}", key=self.K_TOTAL))

        # ---------- Acciones / Estado ----------
        if esta_pagado:
            acciones_ctrl = ft.Text("✔️")
        else:
            acciones_ctrl = ft.Row(
                [
                    ft.IconButton(
                        icon=ft.icons.CHECK,
                        tooltip="Confirmar pago",
                        on_click=lambda e, pid=id_pago_nomina: on_confirmar(pid),
                    ),
                    ft.IconButton(
                        icon=ft.icons.CANCEL,
                        tooltip="Eliminar pago",
                        on_click=lambda e, pid=id_pago_nomina: on_eliminar(pid),
                    ),
                ]
            )
        c_acciones = ft.DataCell(acciones_ctrl)

        c_estado = ft.DataCell(ft.Text(estado_txt, key=self.K_ESTADO))

        return ft.DataRow(
            cells=[
                c_id, c_nomina, c_nombre, c_fecha, c_horas, c_sueldo,
                c_base, c_desc, c_prest, c_saldo, c_dep, c_efectivo,
                c_total, c_acciones, c_estado
            ]
        )


    # --------------- helpers de actualización ---------------

    def get_row(self, table: ft.DataTable, id_pago_nomina: int) -> Optional[ft.DataRow]:
        for row in table.rows:
            try:
                txt: ft.Text = row.cells[0].content  # Text con key p-id
                if txt.value and int(txt.value) == int(id_pago_nomina):
                    return row
            except Exception:
                continue
        return None

    def _get_text_by_key(self, row: ft.DataRow, key: str) -> Optional[ft.Text]:
        for cell in row.cells:
            ctrl = cell.content
            if isinstance(ctrl, ft.Text) and ctrl.key == key:
                return ctrl
            if isinstance(ctrl, ft.Row):
                for ch in ctrl.controls:
                    if isinstance(ch, ft.Text) and ch.key == key:
                        return ch
            if isinstance(ctrl, ft.Container):
                if isinstance(ctrl.content, ft.Text) and ctrl.content.key == key:
                    return ctrl.content
                if isinstance(ctrl.content, ft.Row):
                    for ch in ctrl.content.controls:
                        if isinstance(ch, ft.Text) and ch.key == key:
                            return ch
        return None

    def set_descuentos(self, row: ft.DataRow, value: float):
        t = self._get_text_by_key(row, self.K_DESC)
        if t:
            t.value = f"${float(value):.2f}"

    def set_prestamos(self, row: ft.DataRow, value: float):
        t = self._get_text_by_key(row, self.K_PREST)
        if t:
            t.value = f"${float(value):.2f}"

    def set_saldo(self, row: ft.DataRow, value: float):
        t = self._get_text_by_key(row, self.K_SALDO)
        if t:
            t.value = f"${float(value):.2f}"

    def set_efectivo(self, row: ft.DataRow, value: float):
        t = self._get_text_by_key(row, self.K_EFECTIVO)
        if t:
            t.value = f"${float(value):.2f}"

    def set_total(self, row: ft.DataRow, value: float):
        t = self._get_text_by_key(row, self.K_TOTAL)
        if t:
            t.value = f"${float(value):.2f}"

    def set_deposito_border_color(self, row: ft.DataRow, color: str):
        # busca el Container del depósito y su TextField
        for cell in row.cells:
            ctrl = cell.content
            if isinstance(ctrl, ft.Container) and ctrl.key == self.K_DEP_CONTAINER:
                tf = ctrl.content
                if isinstance(tf, ft.TextField):
                    tf.border_color = color
                return

    def set_estado_pagado(self, row: ft.DataRow):
        # reemplaza acciones por check y estado a "Pagado"
        estado = self._get_text_by_key(row, self.K_ESTADO)
        if estado:
            estado.value = "Pagado"
        # celda de acciones es la penúltima
        acciones_cell = row.cells[-2]
        acciones_cell.content = ft.Text("✔️")
