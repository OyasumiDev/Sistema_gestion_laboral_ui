from app.core.enums.e_weekly_report_model import E_WEEKLY_REPORT
from app.core.interfaces.database_mysql import DatabaseMysql

class WeeklyReportModel:
    """
    Modelo para el manejo de reportes semanales de empleados.
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self._exists_table = self.check_table()

    def check_table(self) -> bool:
        """
        Verifica si la tabla de reportes_semanales existe. Si no, la crea con la estructura correcta del .sql.
        """
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, E_WEEKLY_REPORT.TABLE.value), dictionary=True)
            if result.get("c", 0) == 0:
                print(f"⚠️ La tabla {E_WEEKLY_REPORT.TABLE.value} no existe. Creando...")

                create_query = f"""
                CREATE TABLE IF NOT EXISTS {E_WEEKLY_REPORT.TABLE.value} (
                    {E_WEEKLY_REPORT.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {E_WEEKLY_REPORT.NUMERO_NOMINA.value} SMALLINT UNSIGNED NOT NULL,
                    {E_WEEKLY_REPORT.FECHA_INICIO.value} DATE NOT NULL,
                    {E_WEEKLY_REPORT.FECHA_FIN.value} DATE NOT NULL,
                    {E_WEEKLY_REPORT.TOTAL_HORAS_TRABAJADAS.value} DECIMAL(10,2) NOT NULL,
                    {E_WEEKLY_REPORT.TOTAL_DEUDAS.value} DECIMAL(10,2) NOT NULL,
                    {E_WEEKLY_REPORT.TOTAL_ABONADO.value} DECIMAL(10,2) NOT NULL,
                    {E_WEEKLY_REPORT.SALDO_FINAL.value} DECIMAL(10,2) NOT NULL,
                    {E_WEEKLY_REPORT.TOTAL_EFECTIVO.value} DECIMAL(10,2) NOT NULL,
                    {E_WEEKLY_REPORT.TOTAL_TARJETA.value} DECIMAL(10,2) NOT NULL,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY ({E_WEEKLY_REPORT.NUMERO_NOMINA.value})
                        REFERENCES empleados(numero_nomina)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {E_WEEKLY_REPORT.TABLE.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {E_WEEKLY_REPORT.TABLE.value} ya existe.")
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {E_WEEKLY_REPORT.TABLE.value}: {ex}")
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
            result = self.db.get_data(query, (id_reporte,), dictionary=True)
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
