
from enum import Enum
class E_PRESTAMOS(Enum):
    TABLE_PRESTAMOS = 'prestamos'

    PRESTAMO_ID = 'id_prestamo'
    PRESTAMO_NUMERO_NOMINA = 'numero_nomina'
    PRESTAMO_NOMBRE_EMPLEADO = 'nombre_empleado'        # Nuevo
    PRESTAMO_GRUPO_EMPLEADO = 'grupo_empleado'          # Nuevo
    PRESTAMO_MONTO = 'monto_prestamo'
    PRESTAMO_SALDO = 'saldo_prestamo'
    PRESTAMO_ESTADO = 'estado'
    PRESTAMO_FECHA_SOLICITUD = 'fecha_solicitud'
    PRESTAMO_FECHA_CIERRE = 'fecha_cierre'              # Nuevo
    PRESTAMO_FECHA_CREACION = 'fecha_creacion'
    PRESTAMO_FECHA_MODIFICACION = 'fecha_modificacion'


