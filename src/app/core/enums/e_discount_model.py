from enum import Enum

class E_DISCOUNT(Enum):
    TABLE = "descuentos"
    ID = "id_descuento"
    ID_PAGO = "id_pago"
    TIPO = "tipo_descuento"            # (comida, imss, transporte, etc.)
    DESCRIPCION = "descripcion"
    MONTO_DESCUENTO = "monto_descuento"
    FECHA_APLICACION = "fecha_aplicacion"
    FECHA_CREACION = "fecha_creacion"
