# Constante de la tabla prestamos

from enum import Enum

class EPrestamo(Enum):
    TABLE = 'prestamos'
    ID = 'id_prestamo'
    NUMERO_NOMINA = 'numero_nomina'
    MONTO = 'monto'
    SALDO_PRESTAMO = 'saldo_prestamo'
    ESTADO = 'estado'
    FECHA_SOLICITUD = 'fecha_solicitud'
    HISTORIAL_PAGOS = 'historial_pagos'
    DESCUENTO_SEMANAL = 'descuento_semanal'
    TIPO_DESCUENTO = 'tipo_descuento'
    FECHA_CREACION = 'fecha_creacion'
    FECHA_MODIFICACION = 'fecha_modificacion'
