from __future__ import annotations

from typing import Any, Dict, Optional
import flet as ft


class PaymentRowRefresh:
    """
    Refresca una fila ya construida por PaymentRowBuilder.
    - Actualiza valores de texto/numéricos sin reconstruir la fila.
    - Mantiene referencias a controles clave para refrescos rápidos.
    - Útil para recalcular en caliente después de cambiar depósito o confirmar pago.
    """

    def __init__(self):
        # cache: id_pago -> dict(controles)
        self._cache: Dict[int, Dict[str, Any]] = {}

    # -------------------- Registro de fila --------------------
    def register_row(
        self,
        id_pago: int,
        row: ft.DataRow,
        *,
        txt_desc: Optional[ft.Text] = None,
        txt_prest: Optional[ft.Text] = None,
        txt_saldo: Optional[ft.Text] = None,
        tf_deposito: Optional[ft.TextField] = None,
        txt_efectivo: Optional[ft.Text] = None,
        txt_total: Optional[ft.Text] = None,
        estado_chip: Optional[ft.Container] = None,
    ):
        """Guardar referencias a controles de la fila para refrescar más tarde."""
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
        row._id_pago = id_pago  # tipo: ignore

    def get_row(self, datatable: ft.DataTable, id_pago: int) -> Optional[ft.DataRow]:
        """Buscar fila en cache o en la tabla directamente."""
        if id_pago in self._cache:
            return self._cache[id_pago].get("row")
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
        """Marcar la fila como pagada y bloquear depósito."""
        c = self._find_controls(row)
        if not c:
            return
        chip: ft.Container = c["estado_chip"]
        chip.content.value = "PAGADO"
        chip.bgcolor = ft.colors.GREEN_100
        # Bloquea depósito
        tf: ft.TextField = c["tf_deposito"]
        if tf:
            tf.read_only = True

    # -------------------- Util interno --------------------
    def _find_controls(self, row: ft.DataRow) -> Optional[Dict[str, Any]]:
        id_pago = getattr(row, "_id_pago", None)
        if id_pago is None:
            try:
                id_pago = int(str(row.cells[0].content.value))
            except Exception:
                return None
        return self._cache.get(int(id_pago))
