# Constante de la tabla pago
from enum import Enum

class EPago(Enum):
    TABLE = 'pagos'
    ID = 'id_pago'
    NUMERO_NOMINA = 'numero_nomina'
    FECHA_PAGO = 'fecha_pago'
    MONTO_TOTAL = 'monto_total'
    SALDO = 'saldo'
    PAGO_DEPOSITO = 'pago_deposito'
    PAGO_EFECTIVO = 'pago_efectivo'
    RETENCIONES_IMSS = 'retenciones_imss'
