from enum import Enum

class E_PAYMENT(Enum):
    TABLE = "pagos"
    ID = "id_pago"
    NUMERO_NOMINA = "numero_nomina"
    FECHA_PAGO = "fecha_pago"
    MONTO_BASE = "monto_base"  # 🆕 Antes de descuentos
    MONTO_TOTAL = "monto_total"  # Después de descuentos y abonos
    SALDO = "saldo"  # Lo que queda por pagar si se difiere (opcional)
    PAGO_DEPOSITO = "pago_deposito"  # Parte en tarjeta (por ahora 0.00)
    PAGO_EFECTIVO = "pago_efectivo"  # Parte en efectivo (por ahora todo)
