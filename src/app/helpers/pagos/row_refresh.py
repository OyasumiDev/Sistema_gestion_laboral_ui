# app/helpers/pagos/row_refresh.py
from __future__ import annotations

from typing import Any, Dict, Optional, Callable
import flet as ft


class PaymentRowRefresh:
    """
    Construye y refresca una fila de pago en DataTable.
    - Provee TextField de Depósito con on_change/blur/submit (buffer externo).
    - Botones de edición (descuentos, préstamos); estado.
    - Métodos set_* para refrescar SIN romper la expansión ni el foco.
    - Mantiene referencias a controles clave para actualizaciones rápidas.

    Columnas esperadas por tu DataTable (índices):
    0 ID Pago | 1 ID Emp | 2 Nombre | 3 Fecha | 4 Horas | 5 Sueldo/H |
    6 Monto Base | 7 Descuentos | 8 Préstamos | 9 Saldo | 10 Depósito |
    11 Efectivo | 12 Total | 13 Ediciones | 14 Acciones (reemplaza container) | 15 Estado
    """

    def __init__(self):
        # cache: id_pago -> dict(controles)
        self._cache: Dict[int, Dict[str, Any]] = {}

    # -------------------- Construcción --------------------
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
        on_editar_descuentos: Callable[[Dict[str, Any]], None],
        on_editar_prestamos: Callable[[Dict[str, Any]], None],
        tiene_prestamo_activo: bool,
        on_confirmar: Callable[[int], None],
        on_eliminar: Callable[[int], None],
        on_deposito_change: Callable[[str], None],
        on_deposito_blur: Callable[[], None],
        on_deposito_submit: Callable[[], None],
    ) -> ft.DataRow:

        id_pago = int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago"))
        num = int(pago_row.get("numero_nomina") or 0)
        nombre = str(pago_row.get("nombre_completo") or "")
        fecha_pago = str(pago_row.get("fecha_pago") or "")
        horas = float(pago_row.get("horas") or 0.0)
        sueldo_h = float(pago_row.get("sueldo_por_hora") or 0.0)
        monto_base = float(pago_row.get("monto_base") or 0.0)
        estado = str(pago_row.get("estado") or "").lower()

        # ------------- celdas presentacionales -------------
        def _txt_money(v: float) -> ft.Text:
            return ft.Text(f"${float(v):,.2f}")

        def _txt_small(s: str) -> ft.Text:
            return ft.Text(s, size=12)

        txt_id = ft.Text(str(id_pago))
        txt_num = ft.Text(str(num))
        txt_nombre = ft.Text(nombre)
        txt_fecha = ft.Text(fecha_pago)
        txt_horas = ft.Text(f"{horas:.2f}")
        txt_sueldo = _txt_money(sueldo_h)
        txt_monto_base = _txt_money(monto_base)
        txt_desc = _txt_money(descuentos_value)
        txt_prest = _txt_money(prestamos_value)
        txt_saldo = _txt_money(saldo_value)
        txt_efectivo = _txt_money(efectivo_value)
        txt_total = _txt_money(total_value)

        # ------------- TextField de Depósito -------------
        tf_deposito = ft.TextField(
            value=f"{float(deposito_value or 0):.2f}",
            width=110,
            height=34,
            text_align=ft.TextAlign.RIGHT,
            dense=True,
            read_only=esta_pagado,
            on_change=lambda e: on_deposito_change(e.control.value),
            on_blur=lambda e: on_deposito_blur(),
            on_submit=lambda e: on_deposito_submit(),
        )

        # ------------- Botones edición (col 13) -------------
        btn_desc = ft.IconButton(
            icon=ft.icons.REMOVE_CIRCLE_OUTLINE,
            tooltip="Editar descuentos",
            on_click=lambda e: on_editar_descuentos(pago_row),
            icon_color=ft.colors.AMBER_700,
            disabled=esta_pagado,
        )
        btn_prest = ft.IconButton(
            icon=ft.icons.ACCOUNT_BALANCE_WALLET,
            tooltip="Editar préstamos",
            on_click=lambda e: on_editar_prestamos(pago_row),
            icon_color=ft.colors.BLUE_600,
            disabled=(not tiene_prestamo_activo) or esta_pagado,
        )
        ediciones_cell = ft.Row([btn_desc, btn_prest], spacing=6)

        # ------------- Estado (col 15) -------------
        estado_chip = ft.Container(
            content=_txt_small("PAGADO" if estado == "pagado" else "PENDIENTE"),
            bgcolor=ft.colors.GREEN_100 if estado == "pagado" else ft.colors.GREY_200,
            padding=ft.padding.symmetric(4, 6),
            border_radius=6,
        )

        # ------------- Placeholder Acciones (col 14) -------------
        acciones_placeholder = ft.Text("-")  # lo reemplaza el container

        # ------------- DataRow -------------
        row = ft.DataRow(
            cells=[
                ft.DataCell(txt_id),            # 0
                ft.DataCell(txt_num),           # 1
                ft.DataCell(txt_nombre),        # 2
                ft.DataCell(txt_fecha),         # 3
                ft.DataCell(txt_horas),         # 4
                ft.DataCell(txt_sueldo),        # 5
                ft.DataCell(txt_monto_base),    # 6
                ft.DataCell(txt_desc),          # 7
                ft.DataCell(txt_prest),         # 8
                ft.DataCell(txt_saldo),         # 9
                ft.DataCell(tf_deposito),       # 10
                ft.DataCell(txt_efectivo),      # 11
                ft.DataCell(txt_total),         # 12
                ft.DataCell(ediciones_cell),    # 13
                ft.DataCell(acciones_placeholder),  # 14 (reemplazado fuera)
                ft.DataCell(estado_chip),       # 15
            ],
        )
        # Guarda referencias para refrescos sin re-expansión
        self._cache[id_pago] = {
            "row": row,
            "txt_desc": txt_desc,
            "txt_prest": txt_prest,
            "txt_saldo": txt_saldo,
            "tf_deposito": tf_deposito,
            "txt_efectivo": txt_efectivo,
            "txt_total": txt_total,
            "estado_chip": estado_chip,
        }
        # atributo auxiliar por si quieres ubicar rápido
        row._id_pago = id_pago  # tipo: ignore
        return row

    # -------------------- Búsqueda fila --------------------
    def get_row(self, datatable: ft.DataTable, id_pago: int) -> Optional[ft.DataRow]:
        if id_pago in self._cache:
            return self._cache[id_pago].get("row")
        # búsqueda defensiva
        for r in datatable.rows:
            try:
                rid = int(str(r.cells[0].content.value))
                if rid == id_pago:
                    return r
            except Exception:
                continue
        return None

    # -------------------- Setters rápidos --------------------
    def set_descuentos(self, row: ft.DataRow, valor: float):
        c = self._find_controls(row)
        if c and c["txt_desc"]:
            c["txt_desc"].value = f"${float(valor):,.2f}"

    def set_prestamos(self, row: ft.DataRow, valor: float):
        c = self._find_controls(row)
        if c and c["txt_prest"]:
            c["txt_prest"].value = f"${float(valor):,.2f}"

    def set_saldo(self, row: ft.DataRow, valor: float):
        c = self._find_controls(row)
        if c and c["txt_saldo"]:
            c["txt_saldo"].value = f"${float(valor):,.2f}"

    def set_efectivo(self, row: ft.DataRow, valor: float):
        c = self._find_controls(row)
        if c and c["txt_efectivo"]:
            c["txt_efectivo"].value = f"${float(valor):,.2f}"

    def set_total(self, row: ft.DataRow, valor: float):
        c = self._find_controls(row)
        if c and c["txt_total"]:
            c["txt_total"].value = f"${float(valor):,.2f}"

    def set_deposito_border_color(self, row: ft.DataRow, color: Optional[str]):
        c = self._find_controls(row)
        if c and c["tf_deposito"]:
            c["tf_deposito"].border_color = color

    def set_estado_pagado(self, row: ft.DataRow):
        c = self._find_controls(row)
        if not c:
            return
        chip: ft.Container = c["estado_chip"]
        chip.content.value = "PAGADO"
        chip.bgcolor = ft.colors.GREEN_100
        # Bloquea depósito
        tf: ft.TextField = c["tf_deposito"]
        tf.read_only = True

    # -------------------- Util interno --------------------
    def _find_controls(self, row: ft.DataRow) -> Optional[Dict[str, Any]]:
        id_pago = getattr(row, "_id_pago", None)
        if id_pago is None:
            # intenta leer del texto en celda 0
            try:
                id_pago = int(str(row.cells[0].content.value))
            except Exception:
                return None
        return self._cache.get(int(id_pago))
