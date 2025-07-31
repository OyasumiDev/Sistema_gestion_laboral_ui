from enum import Enum

class E_PAYMENT(Enum):
    TABLE = "pagos"
    ID_PAGO_NOMINA = "id_pago_nomina"
    NUMERO_NOMINA = "numero_nomina"
    FECHA_PAGO = "fecha_pago"
    TOTAL_HORAS_TRABAJADAS = "total_horas_trabajadas"  # ← Actualizado aquí
    MONTO_BASE = "monto_base"
    MONTO_TOTAL = "monto_total"
    SALDO = "saldo"
    PAGO_DEPOSITO = "pago_deposito"
    PAGO_EFECTIVO = "pago_efectivo"
    ESTADO = "estado"




