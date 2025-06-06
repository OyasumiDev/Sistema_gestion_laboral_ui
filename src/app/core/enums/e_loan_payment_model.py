from enum import Enum

class E_PAGOS_PRESTAMO(Enum):
    TABLE = "pagos_prestamo"
    ID = "pago_prestamo_id"
    ID_PRESTAMO = "pago_prestamo_id_prestamo"
    MONTO_PAGADO = "pago_prestamo_monto_pagado"
    FECHA_PAGO = "pago_prestamo_fecha_pago"
    FECHA_REAL = "pago_prestamo_fecha_real_pago"
    INTERES_PORCENTAJE = "pago_prestamo_interes_porcentaje"
    INTERES_APLICADO = "pago_prestamo_interes_aplicado"
    DIAS_RETRASO = "pago_prestamo_dias_retraso"
    SALDO_RESTANTE = "pago_prestamo_saldo_restante"
    OBSERVACIONES = "pago_prestamo_observaciones"