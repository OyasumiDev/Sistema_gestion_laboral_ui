# helpers/pagos/payment_view_math.py

from typing import Optional, Tuple, Dict, Any, TypedDict

from app.models.discount_model import DiscountModel
from app.models.descuento_detalles_model import DescuentoDetallesModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.detalles_pagos_prestamo_model import DetallesPagosPrestamoModel


class RowCalcDict(TypedDict):
    """
    Estructura simple para pintar fila:
      - descuentos_view: total de descuentos para mostrar
      - prestamos_view: total de préstamos (aplicados + pendientes)
      - total_vista: monto_base - descuentos_view - prestamos_view (>= 0)
      - efectivo: efectivo tras depósito_ui (con o sin redondeo a 50)
      - saldo_ajuste: ajuste por redondeo (±) o remanente si depósito cubre todo
    """
    descuentos_view: float
    prestamos_view: float
    total_vista: float
    efectivo: float
    saldo_ajuste: float


class PaymentViewMath:
    """
    Helper matemático para el área de Pagos:
      - Calcula lo que la UI debe mostrar sin tocar BD de pagos.
      - Recalcula en tiempo real efectivo/ajustes con redondeo a 50 (opcional).
      - Evita “doble resta” partiendo SIEMPRE de monto_base.

    Reglas:
      - Descuentos (view):
          * Si existen confirmados -> usar confirmados
          * Si no, usar borrador (descuento_detalles)
      - Préstamos (view):
          * Aplicados (pagos_prestamo) + Pendientes (detalles_pagos_prestamo)
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

        # Columnas del borrador (por si tienes alias en el modelo)
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
                self._to_float(det.get(self._col_imss))
                + self._to_float(det.get(self._col_trans))
                + self._to_float(det.get(self._col_extra))
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
        Redondea al múltiplo de 50 más cercano:
          - Si sobrante >= 25, sube; si no, baja.
        Retorna (valor_redondeado, ajuste_aplicado).
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
    ) -> RowCalcDict:
        """
        Recalcula valores para UI partiendo de monto_base:
          - total_vista = max(0, monto_base - descuentos_view - prestamos_view)
          - efectivo = round50(max(0, total_vista - deposito_ui)) (opcional)
          - saldo_ajuste = ajuste por redondeo o remanente si depósito >= total_vista
        """
        try:
            mb = float(monto_base)
            desc = float(descuentos_view)
            prest = float(prestamos_view)
            dep = max(0.0, float(deposito_ui))
        except Exception:
            mb, desc, prest, dep = 0.0, 0.0, 0.0, 0.0

        total_vista = max(0.0, mb - desc - prest)
        base_efectivo = total_vista - dep

        if base_efectivo <= 0:
            return RowCalcDict(
                descuentos_view=round(desc, 2),
                prestamos_view=round(prest, 2),
                total_vista=round(total_vista, 2),
                efectivo=0.0,
                saldo_ajuste=round(base_efectivo, 2),
            )

        if aplicar_redondeo_50:
            efectivo, ajuste = self.redondear_a_50(base_efectivo)
            return RowCalcDict(
                descuentos_view=round(desc, 2),
                prestamos_view=round(prest, 2),
                total_vista=round(total_vista, 2),
                efectivo=round(efectivo, 2),
                saldo_ajuste=round(ajuste, 2),
            )
        else:
            return RowCalcDict(
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
    ) -> RowCalcDict:
        """
        Calcula todo lo necesario para renderizar una fila dado un registro
        como lo devuelve PaymentModel.get_all_pagos().
        """
        try:
            id_pago_nomina = int(pago_row.get(key_id_pago))
        except Exception:
            id_pago_nomina = 0

        try:
            monto_base = float(pago_row.get(key_monto_base, 0) or 0)
        except Exception:
            monto_base = 0.0

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
