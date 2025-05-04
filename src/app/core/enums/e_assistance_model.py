# Constante de tabla de asistencia
from enum import Enum

class E_ASSISTANCE(Enum):
    TABLE = 'asistencias'
    ID = 'id'
    NUMERO_NOMINA = 'numero_nomina'
    FECHA = 'fecha'
    HORA_ENTRADA = 'entrada'
    HORA_SALIDA = 'salida'
    DURACION_COMIDA = 'tiempo_descanso'
    TIPO_REGISTRO = 'tipo_registro'
    HORAS_TRABAJADAS = 'tiempo_trabajo'
    TOTAL_HORAS_TRABAJADAS = 'total_horas_trabajadas'
