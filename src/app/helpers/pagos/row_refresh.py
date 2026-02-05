# app/helpers/pagos/row_refresh.py
from __future__ import annotations

from typing import Any, Dict, Optional, Iterable, Tuple
import math
import flet as ft
from datetime import datetime, date


class PaymentRowRefresh:
    """
    Utilidad de refresco granular para filas y grupos de pagos.

    Qué hace:
    - Refresca celdas específicas de una fila (descuentos, préstamos, saldo, efectivo, total).
    - Controla el TextField de depósito (valor y borde de error).
    - Marca estado visual (PENDIENTE / PAGADO) y bloquea depósito si aplica.
    - Inserta / elimina filas de DataTable.
    - Registra grupos (p.ej. '2025-05-09') con su tabla y label de total del día.
    - Recalcula total de un grupo leyendo su propia tabla.
    - Valida traslapes de rangos de fechas.

    NOTA: No toca BD; sólo UI.

    CONTRATOS DE ÍNDICES (fallback si no hay refs registradas):
    - Edición (16 cols):
        7=descuentos, 8=prestamos, 9=saldo, 10=tf_deposito, 11=efectivo, 12=total, 15=estado_chip/texto
    - Lectura/compacto (11 cols):
        4=descuentos, 5=prestamos, 7=saldo, 8=efectivo, 9=total, 10=estado_chip/texto
    """

    # -------------------- Inicialización --------------------
    def __init__(self):
        # cache: id_pago -> referencias a controles de la fila
        self._rows: Dict[int, Dict[str, Any]] = {}
        # cache grupos: key (fecha/token) -> refs
        self._groups: Dict[str, Dict[str, Any]] = {}

        # Flet: no hay un OUTLINE estable en todas las versiones.
        self._default_border = ft.colors.GREY_400

    # ==================== UTIL SEGURO ====================
    @staticmethod
    def _safe_update(ctrl: Optional[ft.Control]) -> None:
        """
        Evita crashes si el control aún no está montado en page, o si update falla.
        """
        try:
            if ctrl is not None and getattr(ctrl, "page", None) is not None:
                ctrl.update()
        except Exception:
            pass

    @staticmethod
    def _safe_setattr(obj: Any, name: str, value: Any) -> None:
        """Setattr defensivo (no rompe si la propiedad no existe)."""
        try:
            setattr(obj, name, value)
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
        table: Optional[ft.DataTable] = None,
    ) -> None:
        """
        Guarda referencias a controles de la fila para refrescos rápidos.

        Recomendación:
        - Si puedes, pasa `table` para que el refresher sepa cuál actualizar.
        """
        pid = self._safe_int(id_pago)
        self._rows[pid] = {
            "row": row,
            "table": table,
            "txt_desc": txt_desc,
            "txt_prest": txt_prest,
            "txt_saldo": txt_saldo,
            "tf_deposito": tf_deposito,
            "txt_efectivo": txt_efectivo,
            "txt_total": txt_total,
            "estado_chip": estado_chip,
        }

        # Preferir row.data (estable) a atributos privados.
        try:
            if row.data is None or not isinstance(row.data, dict):
                row.data = {}
            row.data["id_pago"] = pid
        except Exception:
            pass

    def unregister_row(self, id_pago: int) -> None:
        """Saca una fila del caché (útil tras eliminarla de la tabla)."""
        self._rows.pop(self._safe_int(id_pago), None)

    def get_row(self, datatable: Optional[ft.DataTable], id_pago: int) -> Optional[ft.DataRow]:
        """
        Busca la fila en caché o, como fallback, en la tabla (si se provee).
        Soporta datatable=None (sólo caché).
        """
        pid = self._safe_int(id_pago)
        if pid in self._rows:
            r = self._rows[pid].get("row")
            if isinstance(r, ft.DataRow):
                return r

        if datatable is not None:
            for r in datatable.rows:
                rid = self._try_row_id(r)
                if rid == pid:
                    return r
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
        k = str(key or "").strip()
        if not k:
            return
        self._groups[k] = {
            "table": table,
            "panel": panel,
            "lbl_total": lbl_total,
            "lbl_title": lbl_title,
        }

    def unregister_group(self, key: str) -> None:
        self._groups.pop(str(key or "").strip(), None)

    def get_group_table(self, key: str) -> Optional[ft.DataTable]:
        g = self._groups.get(str(key or "").strip())
        t = g.get("table") if g else None
        return t if isinstance(t, ft.DataTable) else None

    # ==================== SETTERS DE CELDAS ====================

    def set_descuentos(self, row: ft.DataRow, valor: float) -> None:
        txt = self._get_txt_desc(row)
        if isinstance(txt, ft.Text):
            txt.value = self._fmt_money(valor)
            self._safe_update(txt)

    def set_prestamos(self, row: ft.DataRow, valor: float) -> None:
        txt = self._get_txt_prest(row)
        if isinstance(txt, ft.Text):
            txt.value = self._fmt_money(valor)
            self._safe_update(txt)

    def set_saldo(self, row: ft.DataRow, valor: float) -> None:
        txt = self._get_txt_saldo(row)
        if isinstance(txt, ft.Text):
            txt.value = self._fmt_money(valor)
            self._safe_update(txt)

    def set_efectivo(self, row: ft.DataRow, valor: float) -> None:
        txt = self._get_txt_efectivo(row)
        if isinstance(txt, ft.Text):
            txt.value = self._fmt_money(valor)
            self._safe_update(txt)

    def set_total(self, row: ft.DataRow, valor: float) -> None:
        txt = self._get_txt_total(row)
        if isinstance(txt, ft.Text):
            txt.value = self._fmt_money(valor)
            self._safe_update(txt)

    def set_deposito_border_color(self, row: ft.DataRow, color: Optional[str]) -> None:
        """
        Pinta el borde del depósito. Si color es None, restaura el borde por defecto.
        """
        tf = self._get_tf_deposito(row)
        if isinstance(tf, ft.TextField):
            tf.border_color = color or self._default_border
            self._safe_update(tf)

    def set_deposito_value(self, row: ft.DataRow, value: float | str) -> None:
        """
        Setea el TextField de depósito con formateo (dos decimales).
        """
        tf = self._get_tf_deposito(row)
        if isinstance(tf, ft.TextField):
            num = self._safe_float(value, 0.0)
            tf.value = f"{num:.2f}"
            self._safe_update(tf)

    # ==================== ESTADO VISUAL ====================

    def set_estado_pagado(self, row: ft.DataRow) -> None:
        """Marca visual como PAGADO y bloquea el depósito."""
        chip = self._get_estado_chip(row)
        if isinstance(chip, ft.Container) and isinstance(chip.content, ft.Text):
            chip.content.value = "PAGADO"
            chip.bgcolor = ft.colors.GREEN_100
            self._safe_update(chip)

        tf = self._get_tf_deposito(row)
        if isinstance(tf, ft.TextField):
            tf.read_only = True
            tf.disabled = True
            self._safe_update(tf)

        self._force_repaint_row_container(row)

    def set_estado_pendiente(self, row: ft.DataRow) -> None:
        """Marca visual como PENDIENTE y habilita el depósito."""
        chip = self._get_estado_chip(row)
        if isinstance(chip, ft.Container) and isinstance(chip.content, ft.Text):
            chip.content.value = "PENDIENTE"
            chip.bgcolor = ft.colors.GREY_200
            self._safe_update(chip)

        tf = self._get_tf_deposito(row)
        if isinstance(tf, ft.TextField):
            tf.read_only = False
            tf.disabled = False
            self._safe_update(tf)

        self._force_repaint_row_container(row)

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
        force_table_update: bool = True,
    ) -> None:
        """
        Aplica el resultado de PaymentViewMath.recalc_from_pago_row(...) a la fila.

        Regla Flet:
        - Actualizar controles internos (Text/TextField) es lo más estable.
        - Si no se ve reflejado, actualizar la DataTable contenedora.
        """
        self.set_descuentos(row, descuentos)
        self.set_prestamos(row, prestamos)
        self.set_saldo(row, saldo_ajuste)
        self.set_efectivo(row, efectivo)
        self.set_total(row, total_vista)

        if deposito is not None:
            self.set_deposito_value(row, deposito)
            self.set_deposito_border_color(row, ft.colors.RED if deposito_excede_total else None)

        if force_table_update:
            self._force_repaint_row_container(row)

    # ==================== TABLAS / GRUPOS ====================

    def insert_row(self, table: ft.DataTable, row: ft.DataRow, *, index: Optional[int] = None) -> None:
        """Inserta una fila en la tabla (al final por defecto) y actualiza la UI."""
        if not isinstance(table, ft.DataTable) or not isinstance(row, ft.DataRow):
            return

        if index is None or index < 0 or index > len(table.rows):
            table.rows.append(row)
        else:
            table.rows.insert(index, row)

        self._safe_update(table)

    def remove_row_by_id(self, table: ft.DataTable, id_pago: int) -> bool:
        """Elimina la fila con id_pago de una tabla. Devuelve True si se eliminó."""
        if not isinstance(table, ft.DataTable):
            return False

        pid = self._safe_int(id_pago)
        removed = False

        for i, r in enumerate(list(table.rows)):
            rid = self._try_row_id(r)
            if rid == pid:
                try:
                    table.rows.pop(i)
                except Exception:
                    try:
                        table.rows.remove(r)
                    except Exception:
                        pass
                removed = True
                break

        if removed:
            self.unregister_row(pid)
            self._safe_update(table)

        return removed

    def compute_table_total(self, table: ft.DataTable, total_col_index: int) -> float:
        """
        Suma la columna `total_col_index` de una DataTable.
        Soporta celdas con ft.Text, strings, y textos tipo "$9,950.00".
        """
        if not isinstance(table, ft.DataTable):
            return 0.0

        tot = 0.0
        for r in table.rows:
            try:
                if total_col_index < 0 or total_col_index >= len(r.cells):
                    continue
                cell_content = r.cells[total_col_index].content

                if isinstance(cell_content, ft.Text):
                    raw = cell_content.value
                else:
                    raw = getattr(cell_content, "value", cell_content)

                tot += self._parse_money(raw)
            except Exception:
                continue

        return round(tot, 2)

    def update_group_total_label(self, group_key: str, total_value: float) -> None:
        """Actualiza el label de total del grupo (si está registrado)."""
        g = self._groups.get(str(group_key or "").strip())
        if not g:
            return

        lbl = g.get("lbl_total")
        if isinstance(lbl, ft.Text):
            lbl.value = f"Total día: {self._fmt_money(total_value)}"
            self._safe_update(lbl)

    def recalc_and_paint_group_total(self, group_key: str, *, total_col_index: int) -> float:
        """Recalcula el total de un grupo leyendo la tabla y pinta el label."""
        table = self.get_group_table(group_key)
        if not table:
            return 0.0

        total = self.compute_table_total(table, total_col_index)
        self.update_group_total_label(group_key, total)
        return total

    # ==================== VALIDACIONES DE FECHAS ====================

    @staticmethod
    def _parse_ymd(d: str) -> Optional[date]:
        """Parse seguro YYYY-MM-DD (y tolera espacios)."""
        try:
            s = str(d or "").strip()
            if not s:
                return None
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    @staticmethod
    def _normalize_range(a: Optional[date], b: Optional[date]) -> Tuple[Optional[date], Optional[date]]:
        """Si vienen invertidas, las ordena."""
        if a and b and a > b:
            return b, a
        return a, b

    @staticmethod
    def ranges_overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
        """
        Determina si [a_start, a_end] y [b_start, b_end] se traslapan.
        Fechas en formato 'YYYY-MM-DD'. Inclusivo en extremos.

        Blindaje:
        - compara dates reales
        - si no se pueden parsear fechas, asume traslape (bloquea para evitar inconsistencias)
        """
        a_s = PaymentRowRefresh._parse_ymd(a_start)
        a_e = PaymentRowRefresh._parse_ymd(a_end)
        b_s = PaymentRowRefresh._parse_ymd(b_start)
        b_e = PaymentRowRefresh._parse_ymd(b_end)

        a_s, a_e = PaymentRowRefresh._normalize_range(a_s, a_e)
        b_s, b_e = PaymentRowRefresh._normalize_range(b_s, b_e)

        if not all([a_s, a_e, b_s, b_e]):
            return True

        return not (a_e < b_s or b_e < a_s)

    @staticmethod
    def validate_no_overlaps(
        new_range: Tuple[str, str],
        existing: Iterable[Tuple[str, str]],
    ) -> Tuple[bool, Optional[Tuple[str, str]]]:
        """
        Valida que (fi, ff) no se traslape con ningún (fi2, ff2) existente.
        Devuelve:
          - (True, None) si no hay conflicto
          - (False, (fi_conflict, ff_conflict)) si hay traslape
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

    reset = clear
    invalidate = clear

    def clear_rows(self) -> None:
        """Sólo filas."""
        self._rows.clear()

    def clear_groups(self) -> None:
        """Sólo grupos."""
        self._groups.clear()

    # ==================== UTILS INTERNOS (CORE) ====================

    def _find_controls(self, row: ft.DataRow) -> Optional[Dict[str, Any]]:
        """
        Encuentra el dict de referencias de la fila.
        Prioridad:
        1) row.data["id_pago"]
        2) cache por _try_row_id (columna 0)
        """
        pid = None
        try:
            if isinstance(getattr(row, "data", None), dict):
                pid = row.data.get("id_pago")
        except Exception:
            pid = None

        if pid is None:
            pid = self._try_row_id(row)

        try:
            pid_i = self._safe_int(pid)
            return self._rows.get(pid_i)
        except Exception:
            return None

    def _force_repaint_row_container(self, row: ft.DataRow) -> None:
        """
        Fuerza repaint del contenedor visual:
        - si hay table registrada -> update(table)
        - si no, intenta update de los controles internos (ya hecho) y no truena
        """
        c = self._find_controls(row)
        if c:
            tbl = c.get("table")
            self._safe_update(tbl)

    # ==================== FALLBACK POR ÍNDICES ====================

    def _is_edit_row(self, row: ft.DataRow) -> bool:
        """Heurística: si tiene 16 celdas, asumimos edición."""
        try:
            return len(row.cells) >= 16
        except Exception:
            return False

    def _cell_content(self, row: ft.DataRow, idx: int) -> Optional[ft.Control]:
        try:
            if idx < 0 or idx >= len(row.cells):
                return None
            return row.cells[idx].content
        except Exception:
            return None

    def _get_txt_desc(self, row: ft.DataRow) -> Optional[ft.Text]:
        c = self._find_controls(row)
        txt = c.get("txt_desc") if c else None
        if isinstance(txt, ft.Text):
            return txt
        # fallback por índice
        idx = 7 if self._is_edit_row(row) else 4
        cc = self._cell_content(row, idx)
        return cc if isinstance(cc, ft.Text) else None

    def _get_txt_prest(self, row: ft.DataRow) -> Optional[ft.Text]:
        c = self._find_controls(row)
        txt = c.get("txt_prest") if c else None
        if isinstance(txt, ft.Text):
            return txt
        idx = 8 if self._is_edit_row(row) else 5
        cc = self._cell_content(row, idx)
        return cc if isinstance(cc, ft.Text) else None

    def _get_txt_saldo(self, row: ft.DataRow) -> Optional[ft.Text]:
        c = self._find_controls(row)
        txt = c.get("txt_saldo") if c else None
        if isinstance(txt, ft.Text):
            return txt
        idx = 9 if self._is_edit_row(row) else 7
        cc = self._cell_content(row, idx)
        return cc if isinstance(cc, ft.Text) else None

    def _get_tf_deposito(self, row: ft.DataRow) -> Optional[ft.TextField]:
        c = self._find_controls(row)
        tf = c.get("tf_deposito") if c else None
        if isinstance(tf, ft.TextField):
            return tf
        idx = 10 if self._is_edit_row(row) else -1  # lectura no tiene TF
        cc = self._cell_content(row, idx) if idx >= 0 else None
        return cc if isinstance(cc, ft.TextField) else None

    def _get_txt_efectivo(self, row: ft.DataRow) -> Optional[ft.Text]:
        c = self._find_controls(row)
        txt = c.get("txt_efectivo") if c else None
        if isinstance(txt, ft.Text):
            return txt
        idx = 11 if self._is_edit_row(row) else 8
        cc = self._cell_content(row, idx)
        return cc if isinstance(cc, ft.Text) else None

    def _get_txt_total(self, row: ft.DataRow) -> Optional[ft.Text]:
        c = self._find_controls(row)
        txt = c.get("txt_total") if c else None
        if isinstance(txt, ft.Text):
            return txt
        idx = 12 if self._is_edit_row(row) else 9
        cc = self._cell_content(row, idx)
        return cc if isinstance(cc, ft.Text) else None

    def _get_estado_chip(self, row: ft.DataRow) -> Optional[ft.Container]:
        c = self._find_controls(row)
        chip = c.get("estado_chip") if c else None
        if isinstance(chip, ft.Container):
            return chip
        idx = 15 if self._is_edit_row(row) else 10
        cc = self._cell_content(row, idx)
        return cc if isinstance(cc, ft.Container) else None

    # ==================== UTILS INTERNOS (PARSE/FORMAT) ====================

    @staticmethod
    def _try_row_id(row: ft.DataRow) -> Optional[int]:
        """Extrae id_pago desde la primera celda (columna 0)."""
        try:
            c0 = row.cells[0].content
            if isinstance(c0, ft.Text):
                return int(str(c0.value))
            return int(str(getattr(c0, "value", 0)))
        except Exception:
            return None

    @staticmethod
    def _safe_int(v: Any, default: int = 0) -> int:
        try:
            if v is None:
                return default
            s = str(v).strip()
            if not s:
                return default
            return int(float(s))
        except Exception:
            return default

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            if v is None:
                return default
            if isinstance(v, (int, float)):
                f = float(v)
                if math.isnan(f) or math.isinf(f):
                    return default
                return f
            s = str(v).strip().replace(" ", "")
            if not s:
                return default
            s = s.replace("$", "").replace(",", "")
            f = float(s)
            if math.isnan(f) or math.isinf(f):
                return default
            return f
        except Exception:
            return default

    @staticmethod
    def _fmt_money(v: Any) -> str:
        """Formatea dinero siempre seguro."""
        try:
            f = PaymentRowRefresh._safe_float(v, 0.0)
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

            if "," in s and "." in s:
                s = s.replace(",", "")
            else:
                s = s.replace(",", ".")

            f = float(s)
            if math.isnan(f) or math.isinf(f):
                return 0.0
            return f
        except Exception:
            return 0.0
