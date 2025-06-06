# Constante de la tabla reportes_semanales
from enum import Enum

class E_WEEKLY_REPORT(Enum):
    TABLE = "reportes_semanales"
    ID = "reporte_id"
    NUMERO_NOMINA = "reporte_numero_nomina"
    FECHA_INICIO = "reporte_fecha_inicio"
    FECHA_FIN = "reporte_fecha_fin"
    TOTAL_HORAS_TRABAJADAS = "reporte_total_horas_trabajadas"
    TOTAL_DEUDAS = "reporte_total_deudas"
    TOTAL_ABONADO = "reporte_total_abonado"
    SALDO_FINAL = "reporte_saldo_final"
    TOTAL_EFECTIVO = "reporte_total_efectivo"
    TOTAL_TARJETA = "reporte_total_tarjeta"