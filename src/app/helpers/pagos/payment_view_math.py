# app/helpers/pagos/payment_view_math.py
from __future__ import annotations

from typing import Any, Dict, Optional

from app.models.discount_model import DiscountModel
from app.models.descuento_detalles_model import DescuentoDetallesModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.detalles_pagos_prestamo_model import DetallesPagosPrestamoModel


class PaymentViewMath:
    """
    Motor de cálculo para pintar cada fila de pago en la UI.
    - Si el pago está 'pendiente': usa BORRADOR de descuentos (o defaults si no existe).
    - Suma préstamos: confirmados (pagos_prestamo) + pendientes (detalles_pagos_prestamo).
    - Calcula efectivo y saldo visual en función del 'depósito' tipeado por el usuario.
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
        Lee el borrador (o defaults) y suma solo lo 'aplicado'.
        """
        det = self.detalles_desc_model.obtener_por_id_pago(id_pago) or {}
        imss = float(det.get(self.detalles_desc_model.COL_MONTO_IMSS, 0) or 0) if det.get(self.detalles_desc_model.COL_APLICADO_IMSS) else 0.0
        transporte = float(det.get(self.detalles_desc_model.COL_MONTO_TRANSPORTE, 0) or 0) if det.get(self.detalles_desc_model.COL_APLICADO_TRANSPORTE) else 0.0
        extra = float(det.get(self.detalles_desc_model.COL_MONTO_EXTRA, 0) or 0) if det.get(self.detalles_desc_model.COL_APLICADO_EXTRA) else 0.0
        return round(imss + transporte + extra, 2)

    def _descuentos_confirmados(self, id_pago: int) -> float:
        """
        Total de la tabla 'descuentos' para el pago ya confirmado.
        """
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
        Suma de detalles_pagos_prestamo vinculados al pago (pendientes).
        Soporta varios nombres/metodos según tu implementación.
        """
        # Intento por método explícito
        for m in ("get_total_pendiente_por_pago", "get_total_por_pago", "get_total", "sumar_por_pago"):
            if hasattr(self.detalles_prestamo_model, m) and callable(getattr(self.detalles_prestamo_model, m)):
                try:
                    return float(getattr(self.detalles_prestamo_model, m)(id_pago) or 0.0)
                except Exception:
                    pass
        # Fallback robusto directo a DB si expone .db
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

    # -------------------- Recalculo Vista ----------------
    def recalc_from_pago_row(self, pago_row: Dict[str, Any], deposito_ui: float) -> Dict[str, float]:
        """
        Retorna los valores listos para pintar:
        - descuentos_view, prestamos_view, saldo_ajuste, efectivo, total_vista
        """
        id_pago = int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago") or 0)
        estado = str(pago_row.get("estado") or "").lower()
        monto_base = float(pago_row.get("monto_base") or 0.0)

        if estado == "pagado":
            descuentos = self._descuentos_confirmados(id_pago)
            prestamos = self._prestamos_confirmados(id_pago)
        else:
            descuentos = self._descuentos_pendientes_desde_borrador(id_pago)
            prestamos = self._prestamos_pendientes(id_pago) + self._prestamos_confirmados(id_pago)

        total_vista = max(0.0, round(monto_base - descuentos - prestamos, 2))

        # Regla: deposito + efectivo = total_vista
        deposito_ui = float(deposito_ui or 0.0)
        if deposito_ui <= total_vista:
            efectivo = round(total_vista - deposito_ui, 2)
            saldo_ajuste = 0.0
        else:
            efectivo = 0.0
            saldo_ajuste = round(deposito_ui - total_vista, 2)  # sobre-depósito

        return {
            "descuentos_view": round(descuentos, 2),
            "prestamos_view": round(prestamos, 2),
            "saldo_ajuste": round(saldo_ajuste, 2),
            "efectivo": round(efectivo, 2),
            "total_vista": round(total_vista, 2),
        }
