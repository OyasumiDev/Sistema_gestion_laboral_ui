from enum import Enum

class E_PRESTAMOS(Enum):
    TABLE = 'prestamos'

    PRESTAMO_ID = 'id_prestamo'
    PRESTAMO_NUMERO_NOMINA = 'numero_nomina'
    PRESTAMO_MONTO = 'monto'
    PRESTAMO_SALDO = 'saldo_prestamo'
    PRESTAMO_ESTADO = 'estado'
    PRESTAMO_FECHA_SOLICITUD = 'fecha_solicitud'
    PRESTAMO_FECHA_CREACION = 'fecha_creacion'
    PRESTAMO_FECHA_MODIFICACION = 'fecha_modificacion'
