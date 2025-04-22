from app.core.enums.e_weekly_report_model import E_WEEKLY_REPORT
from app.core.interfaces.database_mysql import DatabaseMysql

class WeeklyReportModel:
    """
    Modelo para el manejo de reportes semanales de empleados.
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self._exits_table = self.check_table()

    def check_table(self) -> bool:
        """
        Verifica si la tabla de reportes_semanales existe.
        """
        query = "SHOW TABLES"
        result_tables = self.db.get_data_list(query)

        if result_tables:
            key = list(result_tables[0].keys())[0]
            for tabla in result_tables:
                if tabla[key] == E_WEEKLY_REPORT.TABLE.value:
                    return True
        return False

    def add(self, numero_nomina, fecha_inicio, fecha_fin, total_horas_trabajadas,
            total_deudas, total_abonado, saldo_final, total_efectivo, total_tarjeta):
        """
        Agrega un nuevo reporte semanal.
        """
        try:
            query = f"""
            INSERT INTO {E_WEEKLY_REPORT.TABLE.value} (
                {E_WEEKLY_REPORT.NUMERO_NOMINA.value},
                {E_WEEKLY_REPORT.FECHA_INICIO.value},
                {E_WEEKLY_REPORT.FECHA_FIN.value},
                {E_WEEKLY_REPORT.TOTAL_HORAS_TRABAJADAS.value},
                {E_WEEKLY_REPORT.TOTAL_DEUDAS.value},
                {E_WEEKLY_REPORT.TOTAL_ABONADO.value},
                {E_WEEKLY_REPORT.SALDO_FINAL.value},
                {E_WEEKLY_REPORT.TOTAL_EFECTIVO.value},
                {E_WEEKLY_REPORT.TOTAL_TARJETA.value}
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(query, (
                numero_nomina,
                fecha_inicio,
                fecha_fin,
                total_horas_trabajadas,
                total_deudas,
                total_abonado,
                saldo_final,
                total_efectivo,
                total_tarjeta
            ))
            return {"status": "success", "message": "Reporte semanal registrado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al registrar el reporte: {ex}"}

    def get_all(self):
        """
        Retorna todos los reportes semanales registrados.
        """
        try:
            query = f"SELECT * FROM {E_WEEKLY_REPORT.TABLE.value}"
            result = self.db.get_data_list(query)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener reportes: {ex}"}

    def get_by_id(self, id_reporte: int):
        """
        Retorna un reporte semanal por su ID.
        """
        try:
            query = f"""
                SELECT * FROM {E_WEEKLY_REPORT.TABLE.value}
                WHERE {E_WEEKLY_REPORT.ID.value} = %s
            """
            result = self.db.get_data(query, (id_reporte,))
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener el reporte: {ex}"}

    def get_by_empleado(self, numero_nomina: int):
        """
        Retorna todos los reportes semanales de un empleado.
        """
        try:
            query = f"""
                SELECT * FROM {E_WEEKLY_REPORT.TABLE.value}
                WHERE {E_WEEKLY_REPORT.NUMERO_NOMINA.value} = %s
            """
            result = self.db.get_data_list(query, (numero_nomina,))
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener reportes del empleado: {ex}"}
