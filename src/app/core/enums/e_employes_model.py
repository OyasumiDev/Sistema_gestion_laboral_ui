# Constante de tabla de empleados
from enum import Enum

class E_EMPLOYE(Enum):
    TABLE = "empleados"
    NUMERO_NOMINA = "empleado_numero_nomina"
    NOMBRE_COMPLETO = "empleado_nombre_completo"
    ESTADO = "empleado_estado"
    TIPO_TRABAJADOR = "empleado_tipo_trabajador"
    SUELDO_POR_HORA = "empleado_sueldo_por_hora"
