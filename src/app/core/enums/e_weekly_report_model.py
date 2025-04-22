# Constante de la tabla reportes_semanales
from enum import Enum

class E_WEEKLY_REPORT(Enum):
    TABLE = 'reportes_semanales'
    ID = 'id_reporte'
    NUMERO_NOMINA = 'numero_nomina'
    FECHA_INICIO = 'fecha_inicio'
    FECHA_FIN = 'fecha_fin'
    TOTAL_HORAS_TRABAJADAS = 'total_horas_trabajadas'
    TOTAL_DEUDAS = 'total_deudas'
    TOTAL_ABONADO = 'total_abonado'
    SALDO_FINAL = 'saldo_final'
    TOTAL_EFECTIVO = 'total_efectivo'
    TOTAL_TARJETA = 'total_tarjeta'
