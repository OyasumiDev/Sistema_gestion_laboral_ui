from enum import Enum

class E_DETALLES_PAGOS_PRESTAMO(Enum):
    TABLE = "detalles_pagos_prestamo"
    ID = "id_detalle"
    ID_PAGO = "id_pago"
    ID_PRESTAMO = "id_prestamo"
    MONTO_GUARDADO = "monto_guardado"
    INTERES_GUARDADO = "interes_guardado"
    OBSERVACIONES = "observaciones"
    FECHA = "fecha_guardado"
