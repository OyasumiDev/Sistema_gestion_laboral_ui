# app/helpers/pagos/payment_view_math.py
from __future__ import annotations
from typing import Any, Dict

from app.models.discount_model import DiscountModel
from app.models.descuento_detalles_model import DescuentoDetallesModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.detalles_pagos_prestamo_model import DetallesPagosPrestamoModel


class PaymentViewMath:
    """
    Motor de cálculo para pagos de nómina (solo vista/UI):
    - PENDIENTE: toma descuentos del borrador + préstamos (pendientes + confirmados).
    - PAGADO: toma descuentos y préstamos ya confirmados.
    - Con el depósito tipeado en UI calcula: total neto, efectivo (nunca negativo) y saldo
      aplicando la regla de billetes de $50 (redondeo al múltiplo de 50 y saldo de ajuste).
    - No persiste nada; solo devuelve números para pintar.
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

    # -------------------- Descuentos --------------------
    def _descuentos_pendientes_desde_borrador(self, id_pago: int) -> float:
        """
        Lee el borrador de descuentos y suma solo los aplicados.
        """
        det = self.detalles_desc_model.obtener_por_id_pago(id_pago) or {}
        imss = (
            float(det.get(self.detalles_desc_model.COL_MONTO_IMSS, 0) or 0)
            if det.get(self.detalles_desc_model.COL_APLICADO_IMSS)
            else 0.0
        )
        transporte = (
            float(det.get(self.detalles_desc_model.COL_MONTO_TRANSPORTE, 0) or 0)
            if det.get(self.detalles_desc_model.COL_APLICADO_TRANSPORTE)
            else 0.0
        )
        extra = (
            float(det.get(self.detalles_desc_model.COL_MONTO_EXTRA, 0) or 0)
            if det.get(self.detalles_desc_model.COL_APLICADO_EXTRA)
            else 0.0
        )
        return round(imss + transporte + extra, 2)

    def _descuentos_confirmados(self, id_pago: int) -> float:
        """Total de la tabla definitiva 'descuentos'."""
        try:
            return float(self.discount_model.get_total_descuentos_por_pago(id_pago) or 0.0)
        except Exception:
            return 0.0

    # -------------------- Préstamos ---------------------
    def _prestamos_confirmados(self, id_pago: int) -> float:
        try:
            return float(self.loan_payment_model.get_total_prestamos_por_pago(id_pago) or 0.0)
        except Exception:
            return 0.0

    def _prestamos_pendientes(self, id_pago: int) -> float:
        """
        Suma de detalles_pagos_prestamo (pendientes) asociados al pago.
        Intenta métodos conocidos y, si no existen, hace fallback a SQL directo.
        """
        for m in ("get_total_pendiente_por_pago", "get_total_por_pago", "get_total", "sumar_por_pago"):
            if hasattr(self.detalles_prestamo_model, m) and callable(getattr(self.detalles_prestamo_model, m)):
                try:
                    return float(getattr(self.detalles_prestamo_model, m)(id_pago) or 0.0)
                except Exception:
                    pass
        # Fallback defensivo
        try:
            db = getattr(self.detalles_prestamo_model, "db", None)
            E = getattr(self.detalles_prestamo_model, "E", None)
            if db and E:
                q = f"SELECT IFNULL(SUM({E.MONTO_GUARDADO.value}),0) AS t FROM {E.TABLE.value} WHERE {E.ID_PAGO.value}=%s"
                r = db.get_data(q, (id_pago,), dictionary=True)
                return float((r or {}).get("t", 0) or 0.0)
        except Exception:
            pass
        return 0.0

    # -------------------- Recalculo para la UI --------------------
    def recalc_from_pago_row(self, pago_row: Dict[str, Any], deposito_ui: float) -> Dict[str, float]:
        """
        Retorna valores listos para pintar en la UI:
        - descuentos_view, prestamos_view, total_vista (neto = base - desc - préstamos)
        - deposito (tal cual tipeado pero normalizado a float >= 0)
        - efectivo (NUNCA negativo) y saldo_ajuste (regla de $50)
        """
        id_pago = int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago") or 0)
        estado = str(pago_row.get("estado") or "").lower()
        monto_base = float(pago_row.get("monto_base") or 0.0)

        # 1) Descuentos + préstamos según estado
        if estado == "pagado":
            descuentos = self._descuentos_confirmados(id_pago)
            prestamos = self._prestamos_confirmados(id_pago)
        else:
            descuentos = self._descuentos_pendientes_desde_borrador(id_pago)
            # Sumar confirmados (si existieran) + pendientes del borrador de préstamos
            prestamos = self._prestamos_confirmados(id_pago) + self._prestamos_pendientes(id_pago)

        # 2) Neto a pagar
        total_vista = max(0.0, round(monto_base - descuentos - prestamos, 2))

        # 3) Depósito tipeado -> float >= 0 (no lo recortamos al neto; la UI marcará en rojo si excede)
        try:
            deposito = float(deposito_ui or 0.0)
        except Exception:
            deposito = 0.0
        if deposito < 0:
            deposito = 0.0
        deposito = round(deposito, 2)

        # 4) Efectivo y saldo con regla de billetes de $50 (efectivo nunca negativo)
        calculo = self._calcular_pago_y_saldo(total_vista, deposito)

        return {
            "descuentos_view": round(descuentos, 2),
            "prestamos_view": round(prestamos, 2),
            "total_vista": round(total_vista, 2),
            "deposito": deposito,                    # lo que ve la UI / se persiste
            "efectivo": calculo["pago_efectivo"],    # nunca negativo
            "saldo_ajuste": calculo["saldo"],        # + a favor / - adelanto
        }

    # -------------------- Regla billetes de $50 --------------------
    def _calcular_pago_y_saldo(self, monto_total: float, deposito: float) -> dict:
        """
        Calcula efectivo y saldo aplicando la regla de múltiplos de $50:
        - restante = monto_total - deposito
        - si restante <= 0: efectivo = 0, saldo = restante (puede ser negativo)
        - si 0 < restante:
            residuo = restante % 50
            efectivo = restante - residuo  (múltiplo inferior de 50)
            si residuo >= 25:
                efectivo += 50
                saldo = -(50 - residuo)     (adelanto: saldo negativo)
            si residuo < 25:
                saldo = residuo             (a favor: saldo positivo)
        """
        try:
            restante = round(monto_total - deposito, 2)

            # Nada que pagar o depósito pasado
            if restante <= 0:
                return {"pago_efectivo": 0.0, "saldo": round(restante, 2)}

            residuo = round(restante % 50, 2)
            pago_efectivo = round(restante - residuo, 2)  # múltiplo inferior

            if residuo >= 25:
                pago_efectivo = round(pago_efectivo + 50, 2)
                saldo = round(-(50 - residuo), 2)  # adelanto (negativo)
            else:
                saldo = round(residuo, 2)          # a favor (positivo)

            # Blindaje: efectivo nunca negativo
            if pago_efectivo < 0:
                pago_efectivo = 0.0

            return {"pago_efectivo": pago_efectivo, "saldo": saldo}

        except Exception as ex:
            print(f"❌ Error en _calcular_pago_y_saldo: {ex}")
            return {"pago_efectivo": 0.0, "saldo": 0.0}
