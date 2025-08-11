# helpers/pagos/payment_view_math.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

from app.models.discount_model import DiscountModel
from app.models.descuento_detalles_model import DescuentoDetallesModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.detalles_pagos_prestamo_model import DetallesPagosPrestamoModel


@dataclass
class RowCalc:
    """
    Resultado estándar para pintar una fila en la tabla:
    - descuentos_view: lo que se debe mostrar (confirmados si existen; si no, borrador)
    - prestamos_view: confirmados + pendientes (detalles)
    - total_vista: monto_base - descuentos_view - prestamos_view
    - efectivo: efectivo resultante tras depósito_ui y redondeo a 50
    - saldo_ajuste: diferencia introducida por el redondeo (puede ser +/-) o base negativa
    """
    descuentos_view: float
    prestamos_view: float
    total_vista: float
    efectivo: float
    saldo_ajuste: float


class PaymentViewMath:
    """
    Helper matemático para el área de Pagos:
    - Calcula descuentos/préstamos a MOSTRAR en la UI (sin tocar BD de pagos).
    - Recalcula en tiempo real el efectivo/ajustes con redondeo a 50.
    - Evita “doble descuento/préstamo” (siempre parte de monto_base).

    Reglas:
    - Descuentos a mostrar:
        - Si hay confirmados (tabla 'descuentos') -> usar confirmados
        - Si no hay confirmados -> usar borrador (tabla 'descuento_detalles')
    - Préstamos a mostrar:
        - Confirmados (pagos_prestamo por id_pago_nomina) + pendientes (detalles de préstamos)
    """

    def __init__(
        self,
        discount_model: DiscountModel,
        detalles_desc_model: DescuentoDetallesModel,
        loan_payment_model: LoanPaymentModel,
        detalles_prestamo_model: DetallesPagosPrestamoModel,
    ):
        self.discount_model = discount_model
        self.detalles_desc_model = detalles_desc_model
        self.loan_payment_model = loan_payment_model
        self.detalles_prestamo_model = detalles_prestamo_model

        # Para acceder a nombres de columnas del borrador sin hardcodear strings
        # (los definimos en el modelo de detalles que rehicimos).
        self._col_imss = getattr(detalles_desc_model, "COL_MONTO_IMSS", "monto_imss")
        self._col_trans = getattr(detalles_desc_model, "COL_MONTO_TRANSPORTE", "monto_transporte")
        self._col_extra = getattr(detalles_desc_model, "COL_MONTO_EXTRA", "monto_extra")

    # ---------------------------------------------------------------------
    # Descuentos / Préstamos (VIEW)
    # ---------------------------------------------------------------------
    def total_descuentos_view(self, id_pago_nomina: int) -> float:
        """
        Total de descuentos a mostrar por pago:
        - Confirmados si existen (tabla 'descuentos')
        - Si no, valores del borrador (tabla 'descuento_detalles')
        """
        try:
            if self.discount_model.tiene_descuentos_guardados(id_pago_nomina):
                return float(self.discount_model.get_total_descuentos_por_pago(id_pago_nomina) or 0.0)

            det = self.detalles_desc_model.obtener_por_id_pago(id_pago_nomina) or {}
            return (
                self._to_float(det.get(self._col_imss)) +
                self._to_float(det.get(self._col_trans)) +
                self._to_float(det.get(self._col_extra))
            )
        except Exception:
            return 0.0

    def total_prestamos_view(self, id_pago_nomina: int) -> float:
        """
        Total de préstamos a mostrar por pago:
        - Confirmados (pagos_prestamo) + Pendientes (detalles_pagos_prestamo)
        """
        try:
            confirmados = float(self.loan_payment_model.get_total_prestamos_por_pago(id_pago_nomina) or 0.0)
        except Exception:
            confirmados = 0.0
        try:
            pendientes = float(self.detalles_prestamo_model.calcular_total_pendiente_por_pago(id_pago_nomina) or 0.0)
        except Exception:
            pendientes = 0.0
        return round(confirmados + pendientes, 2)

    # ---------------------------------------------------------------------
    # Redondeos / Recalc
    # ---------------------------------------------------------------------
    @staticmethod
    def redondear_a_50(valor: float) -> Tuple[float, float]:
        """
        Redondea al múltiplo de 50 más cercano con tu regla:
        - Si sobra >= 25, sube; si no, baja.
        Retorna (valor_redondeado, ajuste) donde ajuste es la diferencia aplicada (puede ser +/-).
        """
        try:
            v = float(valor)
        except Exception:
            return 0.0, 0.0

        sobrante = v % 50
        if sobrante == 0:
            return v, 0.0
        if sobrante >= 25:
            ajuste = 50 - sobrante
            return v + ajuste, ajuste
        else:
            ajuste = -sobrante
            return v + ajuste, ajuste

    def recalcular_vista(
        self,
        *,
        monto_base: float,
        descuentos_view: float,
        prestamos_view: float,
        deposito_ui: float,
        aplicar_redondeo_50: bool = True,
    ) -> RowCalc:
        """
        Recalcula los valores para la UI partiendo SIEMPRE de monto_base (evita doble resta).
        - total_vista = max(0, monto_base - descuentos_view - prestamos_view)
        - efectivo = round50(max(0, total_vista - deposito_ui))
        - saldo_ajuste = ajuste por redondeo (o el remanente negativo sin redondeo)
        """
        try:
            mb = float(monto_base)
            desc = float(descuentos_view)
            prest = float(prestamos_view)
            dep = max(0.0, float(deposito_ui))
        except Exception:
            # si algo falla, no truenes la UI
            mb, desc, prest, dep = 0.0, 0.0, 0.0, 0.0

        total_vista = max(0.0, mb - desc - prest)
        base_efectivo = total_vista - dep

        if base_efectivo <= 0:
            # No hay efectivo; saldo_ajuste es el remanente (negativo o cero)
            return RowCalc(
                descuentos_view=round(desc, 2),
                prestamos_view=round(prest, 2),
                total_vista=round(total_vista, 2),
                efectivo=0.0,
                saldo_ajuste=round(base_efectivo, 2),
            )

        if aplicar_redondeo_50:
            efectivo, ajuste = self.redondear_a_50(base_efectivo)
            return RowCalc(
                descuentos_view=round(desc, 2),
                prestamos_view=round(prest, 2),
                total_vista=round(total_vista, 2),
                efectivo=round(efectivo, 2),
                saldo_ajuste=round(ajuste, 2),
            )
        else:
            # Sin redondeo
            return RowCalc(
                descuentos_view=round(desc, 2),
                prestamos_view=round(prest, 2),
                total_vista=round(total_vista, 2),
                efectivo=round(base_efectivo, 2),
                saldo_ajuste=0.0,
            )

    # ---------------------------------------------------------------------
    # Alto nivel: recálculo completo a partir de la fila del modelo
    # ---------------------------------------------------------------------
    def recalc_from_pago_row(
        self,
        pago_row: Dict[str, Any],
        deposito_ui: float,
        *,
        key_monto_base: str = "monto_base",
        key_id_pago: str = "id_pago_nomina",
        aplicar_redondeo_50: bool = True,
    ) -> RowCalc:
        """
        Calcula todo lo necesario para renderizar una fila dado un registro tal cual
        lo devuelve PaymentModel.get_all_pagos().

        - Obtiene descuentos_view y prestamos_view vía modelos.
        - Usa SIEMPRE 'monto_base' del row (no 'monto_total') para evitar doble resta.
        - Aplica depósito temporal de la UI y (opcional) redondeo a 50.
        """
        id_pago_nomina = int(pago_row.get(key_id_pago))
        monto_base = float(pago_row.get(key_monto_base, 0) or 0)

        desc_view = self.total_descuentos_view(id_pago_nomina)
        prest_view = self.total_prestamos_view(id_pago_nomina)

        return self.recalcular_vista(
            monto_base=monto_base,
            descuentos_view=desc_view,
            prestamos_view=prest_view,
            deposito_ui=deposito_ui,
            aplicar_redondeo_50=aplicar_redondeo_50,
        )

    # ---------------------------------------------------------------------
    # Utils
    # ---------------------------------------------------------------------
    @staticmethod
    def _to_float(v: Any) -> float:
        try:
            return float(v or 0)
        except Exception:
            return 0.0
