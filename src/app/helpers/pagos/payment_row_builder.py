# app/helpers/pagos/payment_row_builder.py
from __future__ import annotations

import flet as ft
from typing import Dict, Any, Callable, Optional
from decimal import Decimal, InvalidOperation


# Opcional (no rompe si no existe / evita circular imports)
try:
    from app.helpers.pagos.row_refresh import PaymentRowRefresh
except Exception:  # pragma: no cover
    PaymentRowRefresh = None  # type: ignore


class PaymentRowBuilder:
    """
    Constructor de filas compactas para pagos.

    CONTRATOS (muy importante):
    - Pendientes (edición): deben calzar con COLUMNS_EDICION (16 columnas).
    - Confirmados (lectura/compacto): deben calzar con COLUMNS_COMPACTAS_CONFIRMADO (11 columnas).
    - Usa claves del motor PaymentViewMath (valores calculados):
        descuentos_view, prestamos_view, total_vista, saldo_ajuste, deposito, efectivo

    OBJETIVO:
    - Construir UI de manera segura, sin tocar DB.
    - Si se provee `row_refresh`, registra referencias para refresco granular sin reconstruir tablas.

    NOTA:
    - Tolerante a keys faltantes y a tipos raros (str/None/Decimal/int).
    """

    # Colores por default para estados (solo UI)
    _BG_PAGADO = ft.colors.GREEN_100
    _BG_PENDIENTE = ft.colors.GREY_200

    def __init__(
        self,
        font_size: int = 11,
        *,
        deposito_width: int = 110,
        deposito_height: int = 28,
    ):
        self.font_size = int(font_size or 11)
        self.deposito_width = int(deposito_width or 110)
        self.deposito_height = int(deposito_height or 28)

    # ------------------------------------------------------------------
    # Helpers seguros (a prueba de tipos raros)
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_str(v: Any) -> str:
        try:
            return "" if v is None else str(v)
        except Exception:
            return ""

    @staticmethod
    def _safe_int(v: Any, default: int = 0) -> int:
        try:
            if v is None:
                return default
            s = str(v).strip()
            if not s:
                return default
            return int(float(s))  # permite "123.0"
        except Exception:
            return default

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        """
        Convierte casi cualquier cosa a float:
        - None / "" -> default
        - "1,234.50" -> 1234.50
        - "$1,234.50" -> 1234.50
        - Decimal -> float
        """
        try:
            if v is None:
                return default
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, Decimal):
                return float(v)
            s = str(v).strip()
            if not s:
                return default
            s = s.replace("$", "").replace(",", "")
            return float(s)
        except Exception:
            return default

    def _t_money(self, v: Any) -> str:
        """Formatea moneda de forma segura."""
        try:
            return f"${self._safe_float(v, 0.0):,.2f}"
        except Exception:
            return "$0.00"

    def _fmt2(self, v: Any) -> str:
        """Formatea float a 2 decimales (string) para inputs."""
        try:
            return f"{self._safe_float(v, 0.0):.2f}"
        except Exception:
            return "0.00"

    # ------------------------------------------------------------------
    # Horas
    # ------------------------------------------------------------------
    @staticmethod
    def _horas_to_hhmm(v: Any) -> str:
        """
        Convierte decimal de horas a HH:MM (sin tocar valor en DB).
        - None/"" -> ""
        - Acepta float/Decimal/str
        - Trunca segundos (no redondea)
        """
        if v is None:
            return ""
        try:
            s = str(v).strip()
            if not s:
                return ""
            s = s.replace(",", "")  # defensivo: evita romper con "1,25"
            horas = Decimal(s)

            total_seconds = int(Decimal(3600) * horas)
            if total_seconds < 0:
                total_seconds = 0

            hh = total_seconds // 3600
            mm = (total_seconds % 3600) // 60
            return f"{int(hh):02}:{int(mm):02}"
        except (InvalidOperation, ValueError, TypeError):
            return ""

    @staticmethod
    def format_horas(v: Any) -> str:
        return PaymentRowBuilder._horas_to_hhmm(v)

    def _nombre(self, pago: Dict[str, Any]) -> str:
        """Nombre tolerante a variantes de key."""
        if not isinstance(pago, dict):
            return ""
        return str(
            pago.get("nombre_completo")
            or pago.get("nombre_empleado")
            or pago.get("nombre")
            or ""
        )

    # ------------------------------------------------------------------
    # Chip/Estado visual (opcional, para que PaymentRowRefresh lo pueda tocar)
    # ------------------------------------------------------------------
    def _build_estado_chip(self, estado: str) -> ft.Container:
        st = (estado or "").strip().lower()
        is_pagado = st == "pagado"
        return ft.Container(
            content=ft.Text("PAGADO" if is_pagado else "PENDIENTE", size=self.font_size),
            bgcolor=self._BG_PAGADO if is_pagado else self._BG_PENDIENTE,
            padding=ft.padding.symmetric(6, 3),
            border_radius=8,
        )

    # ------------------------------------------------------------------
    # FILA DE LECTURA (CONFIRMADOS) -> 11 celdas
    # Orden esperado COLUMNS_COMPACTAS_CONFIRMADO:
    # id_pago, id_empleado, nombre, monto_base, descuentos, prestamos,
    # deposito, saldo, efectivo, total, estado
    # ------------------------------------------------------------------
    def build_row_lectura(
        self,
        pago: Dict[str, Any],
        valores: Dict[str, Any],
        *,
        row_refresh: Optional["PaymentRowRefresh"] = None,
    ) -> ft.DataRow:
        pago = pago or {}
        valores = valores or {}

        id_pago = self._safe_int(pago.get("id_pago_nomina") or pago.get("id_pago"), 0)
        num = self._safe_str(pago.get("numero_nomina", ""))
        nombre = self._nombre(pago)

        monto_base = self._safe_float(pago.get("monto_base") or valores.get("monto_base"), 0.0)
        descuentos = self._safe_float(valores.get("descuentos_view"), 0.0)
        prestamos = self._safe_float(valores.get("prestamos_view"), 0.0)

        # deposito en confirmados: preferir calculado -> si no, el guardado del pago
        deposito = self._safe_float(valores.get("deposito", pago.get("pago_deposito", pago.get("deposito"))), 0.0)
        saldo = self._safe_float(valores.get("saldo_ajuste"), 0.0)
        efectivo = self._safe_float(valores.get("efectivo"), 0.0)
        total = self._safe_float(valores.get("total_vista"), 0.0)
        estado = self._safe_str(pago.get("estado", ""))

        # IMPORTANTE: guardar refs a Text para refresco granular
        txt_desc = ft.Text(self._t_money(descuentos), size=self.font_size)
        txt_prest = ft.Text(self._t_money(prestamos), size=self.font_size)
        txt_saldo = ft.Text(self._t_money(saldo), size=self.font_size)
        txt_efec = ft.Text(self._t_money(efectivo), size=self.font_size)
        txt_total = ft.Text(self._t_money(total), size=self.font_size)

        # estado puede ser texto o chip; si quieres consistencia visual, usa chip
        estado_chip = self._build_estado_chip(estado)

        cells = [
            ft.DataCell(ft.Text(str(id_pago), size=self.font_size)),
            ft.DataCell(ft.Text(str(num), size=self.font_size)),
            ft.DataCell(ft.Text(nombre, size=self.font_size)),
            ft.DataCell(ft.Text(self._t_money(monto_base), size=self.font_size)),
            ft.DataCell(txt_desc),
            ft.DataCell(txt_prest),
            ft.DataCell(ft.Text(self._t_money(deposito), size=self.font_size)),
            ft.DataCell(txt_saldo),
            ft.DataCell(txt_efec),
            ft.DataCell(txt_total),
            ft.DataCell(estado_chip),
        ]

        row = ft.DataRow(cells=cells)
        row._id_pago = id_pago  # type: ignore[attr-defined]

        row.data = {
            "id_pago": id_pago,
            "numero_nomina": num,
            "estado": estado,
            "kind": "lectura",
        }

        # Registro opcional en refresher (si te lo pasan)
        if row_refresh is not None and hasattr(row_refresh, "register_row"):
            try:
                row_refresh.register_row(
                    id_pago,
                    row,
                    txt_desc=txt_desc,
                    txt_prest=txt_prest,
                    txt_saldo=txt_saldo,
                    txt_efectivo=txt_efec,
                    txt_total=txt_total,
                    estado_chip=estado_chip,
                )
            except Exception:
                pass

        return row

    # ------------------------------------------------------------------
    # FILA DE EDICIÓN (PENDIENTES) -> 16 celdas
    # Orden esperado COLUMNS_EDICION:
    # id_pago, id_empleado, nombre, fecha_pago, horas, sueldo_hora, monto_base,
    # descuentos, prestamos, saldo, deposito(TF), efectivo, total, ediciones, acciones, estado
    # ------------------------------------------------------------------
    def build_row_edicion(
        self,
        pago: Dict[str, Any],
        valores: Dict[str, Any],
        *,
        on_editar_descuentos: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_editar_prestamos: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_confirmar: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_eliminar: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_deposito_change: Optional[Callable[[int, str], None]] = None,
        on_deposito_blur: Optional[Callable[[int], None]] = None,
        on_deposito_submit: Optional[Callable[[int], None]] = None,
        row_refresh: Optional["PaymentRowRefresh"] = None,
    ) -> ft.DataRow:
        pago = pago or {}
        valores = valores or {}

        id_pago = self._safe_int(pago.get("id_pago_nomina") or pago.get("id_pago"), 0)
        num = self._safe_str(pago.get("numero_nomina", ""))
        nombre = self._nombre(pago)

        fecha_pago = self._safe_str(pago.get("fecha_pago", ""))

        horas_raw = pago.get("horas")
        horas_float = self._safe_float(horas_raw, 0.0)

        sueldo_hora = self._safe_float(pago.get("sueldo_por_hora") or pago.get("sueldo_hora"), 0.0)
        monto_base = self._safe_float(pago.get("monto_base"), 0.0)

        descuentos = self._safe_float(valores.get("descuentos_view"), 0.0)
        prestamos = self._safe_float(valores.get("prestamos_view"), 0.0)
        saldo = self._safe_float(valores.get("saldo_ajuste"), 0.0)

        deposito = self._safe_float(valores.get("deposito"), 0.0)
        efectivo = self._safe_float(valores.get("efectivo"), 0.0)
        total = self._safe_float(valores.get("total_vista"), 0.0)

        estado = self._safe_str(pago.get("estado", "pendiente") or "pendiente")
        estado_lower = estado.strip().lower()

        # Seguridad: si por error llega un pago "pagado" aquí, bloqueamos depósito y acciones
        is_pagado = estado_lower == "pagado"
        deposito_editable = not is_pagado

        # Texts “refrescables”
        txt_desc = ft.Text(self._t_money(descuentos), size=self.font_size)
        txt_prest = ft.Text(self._t_money(prestamos), size=self.font_size)
        txt_saldo = ft.Text(self._t_money(saldo), size=self.font_size)
        txt_efec = ft.Text(self._t_money(efectivo), size=self.font_size)
        txt_total = ft.Text(self._t_money(total), size=self.font_size)

        estado_chip = self._build_estado_chip(estado)

        # -------------------- Depósito editable --------------------
        def _safe_call(fn: Optional[Callable], *a):
            if callable(fn) and id_pago > 0:
                try:
                    fn(*a)
                except Exception:
                    pass

        tf_deposito = ft.TextField(
            value=self._fmt2(deposito),
            text_align=ft.TextAlign.RIGHT,
            width=self.deposito_width,
            height=self.deposito_height,
            dense=True,
            text_size=self.font_size,
            content_padding=ft.padding.all(6),
            disabled=not deposito_editable,
            on_change=(lambda e, pid=id_pago: _safe_call(on_deposito_change, pid, e.control.value)),
            on_blur=(lambda e, pid=id_pago: _safe_call(on_deposito_blur, pid)),
            on_submit=(lambda e, pid=id_pago: _safe_call(on_deposito_submit, pid)),
        )

        # -------------------- Ediciones / acciones --------------------
        ediciones_row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.icons.REMOVE_CIRCLE_OUTLINE,
                    tooltip="Editar descuentos",
                    on_click=(lambda e, p=pago: on_editar_descuentos(p)) if callable(on_editar_descuentos) else None,
                    icon_color=ft.colors.AMBER_700,
                    disabled=is_pagado,
                ),
                ft.IconButton(
                    icon=ft.icons.ACCOUNT_BALANCE_WALLET,
                    tooltip="Editar préstamos",
                    on_click=(lambda e, p=pago: on_editar_prestamos(p)) if callable(on_editar_prestamos) else None,
                    icon_color=ft.colors.BLUE_600,
                    disabled=is_pagado,
                ),
            ],
            spacing=4,
        )

        acciones_row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.icons.CHECK,
                    tooltip="Confirmar pago",
                    icon_color=ft.colors.GREEN_600,
                    on_click=(lambda e, p=pago: on_confirmar(p)) if callable(on_confirmar) else None,
                    disabled=is_pagado,
                ),
                ft.IconButton(
                    icon=ft.icons.DELETE_OUTLINE,
                    tooltip="Eliminar pago",
                    icon_color=ft.colors.RED_500,
                    on_click=(lambda e, p=pago: on_eliminar(p)) if callable(on_eliminar) else None,
                    disabled=is_pagado,
                ),
            ],
            spacing=4,
        )

        # Tooltip horas: muestra el valor crudo con 4 decimales si es numérico
        try:
            tooltip_horas = f"{horas_float:.4f}"
        except Exception:
            tooltip_horas = self._safe_str(horas_raw)

        cells = [
            ft.DataCell(ft.Text(str(id_pago), size=self.font_size)),  # 0 id_pago
            ft.DataCell(ft.Text(str(num), size=self.font_size)),     # 1 id_empleado
            ft.DataCell(ft.Text(nombre, size=self.font_size)),       # 2 nombre
            ft.DataCell(ft.Text(fecha_pago, size=self.font_size)),   # 3 fecha_pago
            ft.DataCell(ft.Text(self._horas_to_hhmm(horas_raw), size=self.font_size, tooltip=tooltip_horas)),  # 4 horas
            ft.DataCell(ft.Text(self._t_money(sueldo_hora), size=self.font_size)),  # 5 sueldo_hora
            ft.DataCell(ft.Text(self._t_money(monto_base), size=self.font_size)),   # 6 monto_base
            ft.DataCell(txt_desc),   # 7 descuentos (refrescable)
            ft.DataCell(txt_prest),  # 8 prestamos  (refrescable)
            ft.DataCell(txt_saldo),  # 9 saldo      (refrescable)
            ft.DataCell(tf_deposito),  # 10 deposito (editable/refrescable)
            ft.DataCell(txt_efec),   # 11 efectivo  (refrescable)
            ft.DataCell(txt_total),  # 12 total     (refrescable)
            ft.DataCell(ediciones_row),  # 13 ediciones
            ft.DataCell(acciones_row),   # 14 acciones
            ft.DataCell(estado_chip),    # 15 estado (chip)
        ]

        row = ft.DataRow(cells=cells)
        row._id_pago = id_pago  # type: ignore[attr-defined]

        row.data = {
            "id_pago": id_pago,
            "numero_nomina": num,
            "estado": estado,
            "kind": "edicion",
        }

        # Registro opcional en refresher (clave para refresco granular)
        if row_refresh is not None and hasattr(row_refresh, "register_row"):
            try:
                row_refresh.register_row(
                    id_pago,
                    row,
                    txt_desc=txt_desc,
                    txt_prest=txt_prest,
                    txt_saldo=txt_saldo,
                    tf_deposito=tf_deposito,
                    txt_efectivo=txt_efec,
                    txt_total=txt_total,
                    estado_chip=estado_chip,
                )
            except Exception:
                pass

        # Si es pagado, aplicamos bloqueo visual coherente (por si acaso)
        if is_pagado:
            try:
                tf_deposito.read_only = True
            except Exception:
                pass

        return row

    # ------------------------------------------------------------------
    # FILA COMPACTA (EXPANSIBLE CONFIRMADOS) -> 11 celdas
    # Misma estructura que lectura para consistencia.
    # ------------------------------------------------------------------
    def build_row_compacto(
        self,
        pago: Dict[str, Any],
        valores: Dict[str, Any],
        *,
        row_refresh: Optional["PaymentRowRefresh"] = None,
    ) -> ft.DataRow:
        # Para compactos confirmados usamos el mismo “layout” que lectura
        # (si en tu UI compactos no requieren registro, igual lo dejamos opcional).
        return self.build_row_lectura(pago, valores, row_refresh=row_refresh)
