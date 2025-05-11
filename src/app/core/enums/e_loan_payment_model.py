from enum import Enum

class E_LOAN_PAYMENT(Enum):
    TABLE = 'pagos_prestamo'

    PAGO_ID = 'id_pago'
    PAGO_ID_PRESTAMO = 'id_prestamo'
    PAGO_MONTO_PAGADO = 'monto_pagado'
    PAGO_FECHA_PAGO = 'fecha_pago'
    PAGO_FECHA_GENERACION = 'fecha_generacion'
    PAGO_INTERES_APLICADO = 'interes_aplicado'
    PAGO_DIAS_RETRASO = 'dias_retraso'
