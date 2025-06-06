# app/core/enums/e_prestamo_detalles_model.py
from enum import Enum

class E_DETALLES_PRESTAMO(Enum):
    TABLE = "detalle_pago_prestamo"
    ID = "detalle_prestamo_id"
    ID_PAGO = "detalle_prestamo_id_pago"
    ID_PAGO_PRESTAMO = "detalle_prestamo_id_pago_prestamo"
    MONTO_PAGADO = "detalle_prestamo_monto_pagado"
    INTERES_APLICADO = "detalle_prestamo_interes_aplicado"
    FECHA_PAGO = "detalle_prestamo_fecha_pago"
    DESDE_NOMINA = "detalle_prestamo_desde_nomina"
    OBSERVACIONES = "detalle_prestamo_observaciones"
