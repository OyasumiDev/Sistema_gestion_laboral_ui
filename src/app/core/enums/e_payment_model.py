from enum import Enum

class E_PAYMENT(Enum):
    TABLE = "pagos"
    ID = "pago_id"
    NUMERO_NOMINA = "pago_numero_nomina"
    FECHA_PAGO = "pago_fecha_pago"
    TOTAL_HORAS_TRABAJADAS = "pago_total_horas_trabajadas"
    SUELDO_POR_HORA = "pago_sueldo_por_hora"
    MONTO_BASE = "pago_monto_base"
    MONTO_DESCUENTOS = "pago_monto_descuentos"
    MONTO_PRESTAMO = "pago_monto_prestamo"
    MONTO_TOTAL = "pago_monto_total"
    PAGO_DEPOSITO = "pago_deposito"
    PAGO_EFECTIVO = "pago_efectivo"
    SALDO = "pago_saldo"
    ESTADO = "pago_estado"
    FECHA_CREACION = "pago_fecha_creacion"
    FECHA_MODIFICACION = "pago_fecha_modificacion"


