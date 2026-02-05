# app/helpers/pagos/payment_view_math.py
from __future__ import annotations

from typing import Any, Dict

from app.models.discount_model import DiscountModel
from app.models.descuento_detalles_model import DescuentoDetallesModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.detalles_pagos_prestamo_model import DetallesPagosPrestamoModel


class PaymentViewMath:
    """
    Motor de cálculo para pagos de nómina (SOLO vista/UI).

    ✅ Regla del proyecto:
    - NO persiste nada.
    - ModalDescuentos es el único que "aplica" descuentos a DB.
    - Este módulo SOLO calcula números para pintar.

    Reglas de vista:
    - Pagos PENDIENTES:
        - Descuentos: si hay confirmados -> confirmados; si no -> borrador (detalles).
        - Préstamos: confirmados + borrador (detalles).
    - Pagos PAGADO-like (inmutable):
        - Descuentos: confirmados.
        - Préstamos: confirmados.
    - Depósito UI:
        - float >= 0 (2 decimales)
        - efectivo (NUNCA negativo) y saldo_ajuste con regla de billetes de $50 (sin errores de float)
    """

    def __init__(
        self,
        *,
        discount_model: DiscountModel,
        detalles_desc_model: DescuentoDetallesModel,
        loan_payment_model: LoanPaymentModel,
        detalles_prestamo_model: DetallesPagosPrestamoModel,
    ):
        self.discount_model = discount_model
        self.detalles_desc_model = detalles_desc_model
        self.loan_payment_model = loan_payment_model
        self.detalles_prestamo_model = detalles_prestamo_model

    # ============================================================
    # Helpers numéricos (blindaje)
    # ============================================================
    @staticmethod
    def _to_int(v: Any, default: int = 0) -> int:
        try:
            if v is None or v == "":
                return default
            return int(v)
        except Exception:
            try:
                return int(float(str(v).strip()))
            except Exception:
                return default

    @staticmethod
    def _to_float(v: Any, default: float = 0.0) -> float:
        """
        Convierte a float con tolerancia:
        - None / "" -> default
        - "$1,234.50" / "1,234.50" -> 1234.50
        - "  1234 " -> 1234
        """
        try:
            if v is None or v == "":
                return default
            if isinstance(v, (int, float)):
                return float(v)
            s = str(v).strip()
            if not s:
                return default
            s = s.replace("$", "").replace(" ", "")
            if "," in s and "." in s:
                s = s.replace(",", "")
            else:
                s = s.replace(",", ".")
            return float(s)
        except Exception:
            return default

    @staticmethod
    def _round2(v: Any) -> float:
        try:
            return round(float(v), 2)
        except Exception:
            return 0.0

    @staticmethod
    def _safe_lower(v: Any) -> str:
        try:
            return str(v or "").strip().lower()
        except Exception:
            return ""

    @staticmethod
    def _is_pagado_like(estado: str) -> bool:
        """
        Estados inmutables/solo lectura.
        Ajusta aquí si tu backend maneja más estados.
        """
        st = (estado or "").strip().lower()
        return st in ("pagado", "cerrado", "cancelado")

    # ============================================================
    # DESCUENTOS
    # ============================================================
    def _descuentos_pendientes_desde_borrador(self, id_pago: int) -> float:
        """
        Lee borrador (descuento_detalles) y suma SOLO los aplicados.
        """
        if id_pago <= 0:
            return 0.0

        try:
            det = self.detalles_desc_model.obtener_por_id_pago(id_pago) or {}
        except Exception:
            det = {}

        def _flag(k: str) -> bool:
            try:
                return bool(det.get(k, False))
            except Exception:
                return False

        def _val(k: str) -> float:
            return self._to_float(det.get(k), 0.0)

        imss = _val(self.detalles_desc_model.COL_MONTO_IMSS) if _flag(self.detalles_desc_model.COL_APLICADO_IMSS) else 0.0
        transporte = _val(self.detalles_desc_model.COL_MONTO_TRANSPORTE) if _flag(self.detalles_desc_model.COL_APLICADO_TRANSPORTE) else 0.0
        extra = _val(self.detalles_desc_model.COL_MONTO_EXTRA) if _flag(self.detalles_desc_model.COL_APLICADO_EXTRA) else 0.0

        return self._round2(imss + transporte + extra)

    def _descuentos_confirmados(self, id_pago: int) -> float:
        if id_pago <= 0:
            return 0.0
        try:
            return self._to_float(self.discount_model.get_total_descuentos_por_pago(id_pago), 0.0)
        except Exception:
            return 0.0

    def _descuentos_desde_pago_row(self, pago_row: Dict[str, Any]) -> float:
        """
        Lee descuentos ya persistidos en la fila de pagos (monto_descuento / descuentos).
        Esto permite que la UI refleje inmediatamente lo guardado en DB desde el modal.
        """
        return self._to_float(
            pago_row.get("monto_descuento", pago_row.get("descuentos", 0.0)),
            0.0,
        )

    def _has_descuentos_confirmados(self, id_pago: int) -> bool:
        if id_pago <= 0:
            return False

        fn = getattr(self.discount_model, "tiene_descuentos_guardados", None)
        if callable(fn):
            try:
                return bool(fn(id_pago))
            except Exception:
                pass

        try:
            total = self._to_float(self.discount_model.get_total_descuentos_por_pago(id_pago), 0.0)
            if total > 0:
                return True
        except Exception:
            pass

        try:
            get_list = getattr(self.discount_model, "get_descuentos_por_pago", None)
            if callable(get_list):
                lst = get_list(id_pago) or []
                return len(lst) > 0
        except Exception:
            pass

        return False

    # ============================================================
    # PRÉSTAMOS
    # ============================================================
    def _prestamos_confirmados(self, id_pago: int) -> float:
        if id_pago <= 0:
            return 0.0
        try:
            return self._to_float(self.loan_payment_model.get_total_prestamos_por_pago(id_pago), 0.0)
        except Exception:
            return 0.0

    def _prestamos_pendientes(self, id_pago: int) -> float:
        if id_pago <= 0:
            return 0.0

        for m in ("get_total_pendiente_por_pago", "get_total_por_pago", "get_total", "sumar_por_pago"):
            fn = getattr(self.detalles_prestamo_model, m, None)
            if callable(fn):
                try:
                    return self._to_float(fn(id_pago), 0.0)
                except Exception:
                    pass

        try:
            db = getattr(self.detalles_prestamo_model, "db", None)
            E = getattr(self.detalles_prestamo_model, "E", None)
            if not db or not E:
                return 0.0

            q = (
                f"SELECT IFNULL(SUM({E.MONTO_GUARDADO.value}),0) AS t "
                f"FROM {E.TABLE.value} "
                f"WHERE {E.ID_PAGO.value}=%s"
            )
            r = db.get_data(q, (id_pago,), dictionary=True)
            return self._to_float((r or {}).get("t", 0.0), 0.0)
        except Exception:
            return 0.0

    # ============================================================
    # RECÁLCULO PRINCIPAL (UI)
    # ============================================================
    def recalc_from_pago_row(self, pago_row: Dict[str, Any], deposito_ui: Any) -> Dict[str, Any]:
        pago_row = dict(pago_row or {})

        id_pago = self._to_int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago") or 0, 0)
        estado = self._safe_lower(pago_row.get("estado"))
        monto_base = self._to_float(pago_row.get("monto_base"), 0.0)

        descuentos = 0.0
        prestamos = 0.0
        fuente_desc = "none"
        fuente_pres = "none"

        # Pagado-like => solo confirmados
        if self._is_pagado_like(estado):
            descuentos = self._descuentos_confirmados(id_pago)
            prestamos = self._prestamos_confirmados(id_pago)
            fuente_desc = "confirmados"
            fuente_pres = "confirmados"
        else:
            # Pendiente-like => descuentos prefieren confirmados; si no, borrador
            desc_guardado_pago = self._descuentos_desde_pago_row(pago_row)
            if desc_guardado_pago > 0:
                descuentos = desc_guardado_pago
                fuente_desc = "pagos"
            elif self._has_descuentos_confirmados(id_pago):
                descuentos = self._descuentos_confirmados(id_pago)
                fuente_desc = "confirmados"
            else:
                descuentos = self._descuentos_pendientes_desde_borrador(id_pago)
                fuente_desc = "borrador" if descuentos > 0 else "none"

            # Préstamos => confirmados + borrador
            conf = self._prestamos_confirmados(id_pago)
            pend = self._prestamos_pendientes(id_pago)
            prestamos = conf + pend

            if conf > 0 and pend > 0:
                fuente_pres = "confirmados+borrador"
            elif conf > 0:
                fuente_pres = "confirmados"
            elif pend > 0:
                fuente_pres = "borrador"
            else:
                fuente_pres = "none"

        descuentos = self._round2(descuentos)
        prestamos = self._round2(prestamos)

        total_vista = self._round2(max(0.0, monto_base - descuentos - prestamos))

        deposito = self._to_float(deposito_ui, 0.0)
        if deposito < 0:
            deposito = 0.0
        deposito = self._round2(deposito)

        deposito_excede_total = deposito > (total_vista + 1e-9)

        calculo = self._calcular_pago_y_saldo(total_vista, deposito)

        return {
            "descuentos_view": descuentos,
            "prestamos_view": prestamos,
            "total_vista": total_vista,
            "deposito": deposito,
            "efectivo": self._round2(calculo.get("pago_efectivo", 0.0)),
            "saldo_ajuste": self._round2(calculo.get("saldo", 0.0)),
            "deposito_excede_total": bool(deposito_excede_total),
            "fuente_descuentos": fuente_desc,
            "fuente_prestamos": fuente_pres,
        }

    # ============================================================
    # REGLA billetes de $50 (blindaje con centavos)
    # ============================================================
    def _calcular_pago_y_saldo(self, monto_total: float, deposito: float) -> Dict[str, float]:
        """
        Regla múltiplos de $50 usando enteros (centavos) para evitar errores de float.

        resto = monto_total - deposito

        Si resto <= 0:
            efectivo = 0
            saldo = resto (negativo = adelanto)

        Si resto > 0:
            residuo = resto % 50
            efectivo = resto - residuo
            si residuo >= 25 => efectivo += 50; saldo = -(50 - residuo)
            si residuo < 25  => saldo = residuo
        """
        try:
            mt = self._to_float(monto_total, 0.0)
            dp = self._to_float(deposito, 0.0)

            # centavos
            mt_c = int(round(mt * 100))
            dp_c = int(round(dp * 100))
            resto_c = mt_c - dp_c

            if resto_c <= 0:
                return {"pago_efectivo": 0.0, "saldo": self._round2(resto_c / 100)}

            # 50 pesos en centavos
            cincuenta_c = 50 * 100
            veinticinco_c = 25 * 100

            residuo_c = resto_c % cincuenta_c
            efectivo_c = resto_c - residuo_c

            if residuo_c >= veinticinco_c:
                efectivo_c += cincuenta_c
                saldo_c = -(cincuenta_c - residuo_c)
            else:
                saldo_c = residuo_c

            if efectivo_c < 0:
                efectivo_c = 0

            return {
                "pago_efectivo": self._round2(efectivo_c / 100),
                "saldo": self._round2(saldo_c / 100),
            }
        except Exception:
            return {"pago_efectivo": 0.0, "saldo": 0.0}
