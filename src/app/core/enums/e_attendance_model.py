# Constante de tabla de asistencia
from enum import Enum

class EAsistencia(Enum):
    TABLE = 'asistencias'
    ID = 'id_asistencia'
    NUMERO_NOMINA = 'numero_nomina'
    FECHA = 'fecha'
    HORA_ENTRADA = 'hora_entrada'
    HORA_SALIDA = 'hora_salida'
    DURACION_COMIDA = 'duracion_comida'
    TIPO_REGISTRO = 'tipo_registro'
    HORAS_TRABAJADAS = 'horas_trabajadas'
