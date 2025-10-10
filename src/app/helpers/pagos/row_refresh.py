from __future__ import annotations

from typing import Any, Dict, Optional, Iterable, Tuple
import math
import flet as ft


class PaymentRowRefresh:
    """
    Utilidad de refresco granular para filas y grupos de pagos.

    - Refresca celdas de una fila (descuentos, préstamos, saldo, efectivo, total).
    - Controla el TextField de depósito (valor y borde de error).
    - Marca estado visual (PENDIENTE / PAGADO) y bloquea depósito si aplica.
    - Inserta / elimina filas de DataTable y recalcula totales visibles.
    - Registra grupos (p. ej. '2025-05-09') con su tabla y label de total del día.
    - Recalcula el total de un grupo desde la propia tabla.
    - Valida traslapes de rangos de fechas.

    NOTA: No toca la BD; sólo UI.
    """

    # -------------------- Inicialización --------------------
    def __init__(self):
        # cache: id_pago -> referencias a controles de la fila
        self._rows: Dict[int, Dict[str, Any]] = {}
        # cache grupos: key (fecha/token) -> refs
        self._groups: Dict[str, Dict[str, Any]] = {}
        self._default_border = ft.colors.OUTLINE

    # ==================== UTIL SEGURO ====================
    @staticmethod
    def _safe_update(ctrl: Optional[ft.Control]) -> None:
        """Evita AssertionError si el control aún no está en la page."""
        try:
            if ctrl is not None and getattr(ctrl, "page", None) is not None:
                ctrl.update()
        except Exception:
            pass

    # ==================== REGISTROS ====================

    # ---- Filas ----
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
    ) -> None:
        """Guarda referencias a controles de la fila para refrescos rápidos."""
        self._rows[id_pago] = {
            "row": row,
            "txt_desc": txt_desc,
            "txt_prest": txt_prest,
            "txt_saldo": txt_saldo,
            "tf_deposito": tf_deposito,
            "txt_efectivo": txt_efectivo,
            "txt_total": txt_total,
            "estado_chip": estado_chip,
        }
        row._id_pago = id_pago  # type: ignore[attr-defined]

    def unregister_row(self, id_pago: int) -> None:
        """Saca una fila del caché (útil tras eliminarla de la tabla)."""
        self._rows.pop(id_pago, None)

    def get_row(self, datatable: Optional[ft.DataTable], id_pago: int) -> Optional[ft.DataRow]:
        """
        Busca la fila en caché o, como fallback, en la tabla (si se provee).
        Soporta datatable=None (sólo caché).
        """
        if id_pago in self._rows:
            return self._rows[id_pago].get("row")

        if datatable is not None:
            for r in datatable.rows:
                try:
                    rid = int(str(r.cells[0].content.value))
                    if rid == id_pago:
                        return r
                except Exception:
                    continue
        return None

    # ---- Grupos ----
    def register_group(
        self,
        key: str,
        *,
        table: ft.DataTable,
        panel: Optional[ft.ExpansionPanel] = None,
        lbl_total: Optional[ft.Text] = None,
        lbl_title: Optional[ft.Text] = None,
    ) -> None:
        """
        Registra referencias de un grupo (por fecha o token).
        - table: tabla del grupo (confirmados).
        - lbl_total: label que muestra “Total día: $…”.
        - lbl_title: label con el título del grupo (opcional).
        """
        self._groups[key] = {
            "table": table,
            "panel": panel,
            "lbl_total": lbl_total,
            "lbl_title": lbl_title,
        }

    def unregister_group(self, key: str) -> None:
        self._groups.pop(key, None)

    def get_group_table(self, key: str) -> Optional[ft.DataTable]:
        g = self._groups.get(key)
        return g["table"] if g else None

    # ==================== SETTERS DE CELDAS ====================

    def set_descuentos(self, row: ft.DataRow, valor: float) -> None:
        c = self._find_controls(row)
        if c and c["txt_desc"]:
            c["txt_desc"].value = self._fmt_money(valor)

    def set_prestamos(self, row: ft.DataRow, valor: float) -> None:
        c = self._find_controls(row)
        if c and c["txt_prest"]:
            c["txt_prest"].value = self._fmt_money(valor)

    def set_saldo(self, row: ft.DataRow, valor: float) -> None:
        c = self._find_controls(row)
        if c and c["txt_saldo"]:
            c["txt_saldo"].value = self._fmt_money(valor)

    def set_efectivo(self, row: ft.DataRow, valor: float) -> None:
        c = self._find_controls(row)
        if c and c["txt_efectivo"]:
            c["txt_efectivo"].value = self._fmt_money(valor)

    def set_total(self, row: ft.DataRow, valor: float) -> None:
        c = self._find_controls(row)
        if c and c["txt_total"]:
            c["txt_total"].value = self._fmt_money(valor)

    def set_deposito_border_color(self, row: ft.DataRow, color: Optional[str]) -> None:
        """
        Pinta el borde del depósito. Si color es None, restaura el borde por defecto.
        """
        c = self._find_controls(row)
        if c and c["tf_deposito"]:
            c["tf_deposito"].border_color = color or self._default_border

    def set_deposito_value(self, row: ft.DataRow, value: float | str) -> None:
        """
        Setea el TextField de depósito con formateo (dos decimales).
        Útil cuando el backend valida/ajusta y queremos reflejarlo tal cual.
        """
        c = self._find_controls(row)
        if c and c["tf_deposito"]:
            try:
                num = float(value) if value not in (None, "") else 0.0
            except Exception:
                num = 0.0
            c["tf_deposito"].value = f"{num:.2f}"

    # ==================== ESTADO VISUAL ====================

    def set_estado_pagado(self, row: ft.DataRow) -> None:
        """Marca visual como PAGADO y bloquea el depósito."""
        c = self._find_controls(row)
        if not c:
            return
        chip: ft.Container = c.get("estado_chip")
        if chip and isinstance(chip.content, ft.Text):
            chip.content.value = "PAGADO"
            chip.bgcolor = ft.colors.GREEN_100
            self._safe_update(chip)
        tf: ft.TextField = c.get("tf_deposito")
        if tf:
            tf.read_only = True
            # no forzamos update del TextField: Flet exige que esté en page

    def set_estado_pendiente(self, row: ft.DataRow) -> None:
        """Marca visual como PENDIENTE y habilita el depósito."""
        c = self._find_controls(row)
        if not c:
            return
        chip: ft.Container = c.get("estado_chip")
        if chip and isinstance(chip.content, ft.Text):
            chip.content.value = "PENDIENTE"
            chip.bgcolor = ft.colors.GREY_200
            self._safe_update(chip)
        tf: ft.TextField = c.get("tf_deposito")
        if tf:
            tf.read_only = False

    # ==================== APLICADORES ====================

    def apply_calc(
        self,
        row: ft.DataRow,
        *,
        descuentos: float,
        prestamos: float,
        saldo_ajuste: float,
        efectivo: float,
        total_vista: float,
        deposito: Optional[float] = None,
        deposito_excede_total: bool = False,
    ) -> None:
        """
        Aplica el resultado de PaymentViewMath.recalc_from_pago_row(...) a la fila.
        Si `deposito` viene, también setea el TextField y pinta borde rojo si excede.
        """
        self.set_descuentos(row, descuentos)
        self.set_prestamos(row, prestamos)
        self.set_saldo(row, saldo_ajuste)
        self.set_efectivo(row, efectivo)
        self.set_total(row, total_vista)

        if deposito is not None:
            self.set_deposito_value(row, deposito)
            self.set_deposito_border_color(row, ft.colors.RED if deposito_excede_total else None)

        self._safe_update(row)

    # ==================== TABLAS / GRUPOS ====================

    def insert_row(self, table: ft.DataTable, row: ft.DataRow, *, index: Optional[int] = None) -> None:
        """
        Inserta una fila en la tabla (al final por defecto) y actualiza la UI.
        """
        if index is None or index < 0 or index > len(table.rows):
            table.rows.append(row)
        else:
            table.rows.insert(index, row)
        self._safe_update(table)

    def remove_row_by_id(self, table: ft.DataTable, id_pago: int) -> bool:
        """
        Elimina la fila con id_pago de una tabla. Devuelve True si se eliminó.
        """
        removed = False
        for i, r in enumerate(list(table.rows)):
            rid = self._try_row_id(r)
            if rid == id_pago:
                table.rows.pop(i)
                removed = True
                break
        if removed:
            self.unregister_row(id_pago)
            self._safe_update(table)
        return removed

    def compute_table_total(self, table: ft.DataTable, total_col_index: int) -> float:
        """
        Suma la columna `total_col_index` de una DataTable con textos tipo "$9,950.00".
        """
        tot = 0.0
        for r in table.rows:
            try:
                cell = r.cells[total_col_index].content
                val = self._parse_money(getattr(cell, "value", "0"))
                tot += val
            except Exception:
                continue
        return round(tot, 2)

    def update_group_total_label(self, group_key: str, total_value: float) -> None:
        """
        Actualiza el label de total del grupo (si está registrado).
        """
        g = self._groups.get(group_key)
        if not g:
            return
        lbl: ft.Text = g.get("lbl_total")
        if lbl:
            # Convención usada en tu UI: "Total día: $X"
            lbl.value = f"Total día: {self._fmt_money(total_value)}"
            self._safe_update(lbl)

    def recalc_and_paint_group_total(self, group_key: str, *, total_col_index: int) -> float:
        """
        Recalcula el total de un grupo leyendo la tabla y pinta el label.
        """
        table = self.get_group_table(group_key)
        if not table:
            return 0.0
        total = self.compute_table_total(table, total_col_index)
        self.update_group_total_label(group_key, total)
        return total

    # ==================== VALIDACIONES DE FECHAS ====================

    @staticmethod
    def ranges_overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
        """
        Determina si [a_start, a_end] y [b_start, b_end] se traslapan.
        Fechas en formato 'YYYY-MM-DD'. Inclusivo en extremos.
        """
        return not (a_end < b_start or b_end < a_start)

    @staticmethod
    def validate_no_overlaps(
        new_range: Tuple[str, str],
        existing: Iterable[Tuple[str, str]],
    ) -> Tuple[bool, Optional[Tuple[str, str]]]:
        """
        Valida que (fi, ff) no se traslape con ningún (fi2, ff2) existente.
        Devuelve (True, None) si no hay conflicto;
        (False, (fi_conflict, ff_conflict)) si hay traslape.
        """
        fi, ff = new_range
        for (ei, ef) in existing:
            if PaymentRowRefresh.ranges_overlap(fi, ff, ei, ef):
                return False, (ei, ef)
        return True, None

    # ==================== LIMPIEZA DE CACHÉ ====================

    def clear(self) -> None:
        """Limpia filas y grupos (alias de reset/invalidate)."""
        self._rows.clear()
        self._groups.clear()

    # Aliases cómodos (para usar desde el container sin importar el nombre)
    reset = clear
    invalidate = clear

    def clear_rows(self) -> None:
        """Sólo filas."""
        self._rows.clear()

    def clear_groups(self) -> None:
        """Sólo grupos."""
        self._groups.clear()

    # ==================== UTILS INTERNOS ====================

    def _find_controls(self, row: ft.DataRow) -> Optional[Dict[str, Any]]:
        id_pago = getattr(row, "_id_pago", None)
        if id_pago is None:
            id_pago = self._try_row_id(row)
        try:
            return self._rows.get(int(id_pago)) if id_pago is not None else None
        except Exception:
            return None

    @staticmethod
    def _try_row_id(row: ft.DataRow) -> Optional[int]:
        try:
            return int(str(row.cells[0].content.value))
        except Exception:
            return None

    @staticmethod
    def _fmt_money(v: Any) -> str:
        try:
            if v is None:
                return "$0.00"
            f = float(v)
            if math.isnan(f) or math.isinf(f):
                return "$0.00"
            return f"${f:,.2f}"
        except Exception:
            return "$0.00"

    @staticmethod
    def _parse_money(txt: Any) -> float:
        """
        Convierte textos como "$9,950.00", "9.950,00", " 9 950.00 " a float seguro.
        """
        try:
            s = str(txt).strip().replace(" ", "")
            if not s:
                return 0.0
            s = s.replace("$", "")
            # Normaliza miles/comas comunes
            if "," in s and "." in s:
                # heurística: si hay ambos, asume coma como miles y punto como decimal
                s = s.replace(",", "")
            else:
                # si solo hay coma, trátala como decimal
                s = s.replace(",", ".")
            return float(s)
        except Exception:
            return 0.0
