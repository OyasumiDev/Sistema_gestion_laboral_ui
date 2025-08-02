from enum import Enum


class E_DESCUENTO_DETALLES(Enum):
    TABLE = "descuento_detalles"

    ID = "id_detalle"
    ID_PAGO = "id_pago_nomina"

    APLICADO_IMSS = "aplicado_imss"
    APLICADO_TRANSPORTE = "aplicado_transporte"
    APLICADO_COMIDA = "aplicado_comida"
    APLICADO_EXTRA = "aplicado_extra"

    MONTO_IMSS = "monto_imss"
    MONTO_TRANSPORTE = "monto_transporte"
    MONTO_COMIDA = "monto_comida"
    MONTO_EXTRA = "monto_extra"
    DESCRIPCION_EXTRA = "descripcion_extra"

