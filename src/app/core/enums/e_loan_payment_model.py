from enum import Enum

class E_PAGOS_PRESTAMO(Enum):
    TABLE = 'pagos_prestamo'

    PAGO_ID = 'id_pago'
    PAGO_ID_PRESTAMO = 'id_prestamo'
    PAGO_MONTO_PAGADO = 'monto_pagado'
    PAGO_FECHA_PAGO = 'fecha_pago'                  # Fecha programada del pago
    PAGO_FECHA_REAL = 'fecha_real_pago'             # Fecha en que se hizo el pago realmente
    PAGO_INTERES_PORCENTAJE = 'interes_porcentaje'  # % de interés manual ingresado
    PAGO_INTERES_APLICADO = 'interes_aplicado'      # Interés en pesos aplicado en este pago
    PAGO_DIAS_RETRASO = 'dias_retraso'              # Calculado al momento del pago
    PAGO_SALDO_RESTANTE = 'saldo_restante'          # Después de aplicar el pago
    PAGO_OBSERVACIONES = 'observaciones'            # Campo opcional para notas
