from enum import Enum

class E_DESCUENTO_DETALLES(Enum):
    TABLE = "descuento_detalles"
    ID = "descuento_detalle_id"
    ID_PAGO = "descuento_detalle_id_pago"
    APLICAR_IMSS = "descuento_aplicar_imss"
    MONTO_IMSS = "descuento_monto_imss"
    APLICAR_TRANSPORTE = "descuento_aplicar_transporte"
    MONTO_TRANSPORTE = "descuento_monto_transporte"
    APLICAR_COMIDA = "descuento_aplicar_comida"
    MONTO_COMIDA = "descuento_monto_comida"
    APLICAR_EXTRA = "descuento_aplicar_extra"
    DESCRIPCION_EXTRA = "descuento_descripcion_extra"
    MONTO_EXTRA = "descuento_monto_extra"