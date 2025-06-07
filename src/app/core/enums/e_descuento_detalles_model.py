from enum import Enum


class E_DESCUENTO_DETALLES(Enum):
    TABLE = "descuento_detalles"

    ID = "id_detalle"
    ID_PAGO = "id_pago"

    APLICADO_IMSS = "aplicado_imss"
    MONTO_IMSS = "monto_imss"

    APLICADO_TRANSPORTE = "aplicado_transporte"
    MONTO_TRANSPORTE = "monto_transporte"

    APLICADO_COMIDA = "aplicado_comida"
    MONTO_COMIDA = "monto_comida"

    APLICADO_EXTRA = "aplicado_extra"
    MONTO_EXTRA = "monto_extra"
    DESCRIPCION_EXTRA = "descripcion_extra"
