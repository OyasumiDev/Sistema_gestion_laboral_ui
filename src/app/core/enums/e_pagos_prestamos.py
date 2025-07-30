from enum import Enum

class E_PAGOS_PRESTAMO(Enum):
    TABLE_PAGOS_PRESTAMOS = 'pagos_prestamo'

    ID_PAGO_PRESTAMO = 'id_pago_prestamo'  # ID único del pago de préstamo
    ID_PRESTAMO = 'id_prestamo'  # FK al préstamo correspondiente
    ID_PAGO_NOMINA = 'id_pago_nomina'  # FK al pago de nómina (mismo nombre que en E_PAYMENT)

    PAGO_MONTO_PAGADO = 'monto_pagado'  # Monto abonado
    PAGO_FECHA_PAGO = 'fecha_pago'  # Fecha programada del pago
    PAGO_FECHA_REAL = 'fecha_real_pago'  # Fecha en la que realmente se aplicó el pago

    PAGO_APLICADO = 'aplicado'  # Booleano: si el pago fue aplicado en la nómina
    PAGO_INTERES_PORCENTAJE = 'interes_porcentaje'  # % de interés
    PAGO_INTERES_APLICADO = 'interes_aplicado'  # Interés aplicado en monto

    PAGO_DIAS_RETRASO = 'dias_retraso'  # Días de retraso (fecha_real - fecha_pago)
    PAGO_SALDO_RESTANTE = 'saldo_restante'  # Saldo restante del préstamo después del pago

    PAGO_OBSERVACIONES = 'observaciones'  # Comentarios u observaciones del pago
