from app.core.enums.e_performance_model import E_PERFORMANCE
from app.core.interfaces.database_mysql import DatabaseMysql

class PerformanceModel:
    """
    Modelo de desempeño de empleados.
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self._exists_table = self.check_table()

    def check_table(self) -> bool:
        """
        Verifica si la tabla de desempeño existe y la crea con la misma estructura que el .sql si no existe.
        """
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, E_PERFORMANCE.TABLE.value), dictionary=True)
            if result.get("c", 0) == 0:
                print(f"⚠️ La tabla {E_PERFORMANCE.TABLE.value} no existe. Creando...")

                create_query = f"""
                CREATE TABLE IF NOT EXISTS {E_PERFORMANCE.TABLE.value} (
                    {E_PERFORMANCE.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {E_PERFORMANCE.NUMERO_NOMINA.value} SMALLINT UNSIGNED NOT NULL,
                    {E_PERFORMANCE.PUNTUALIDAD.value} TINYINT UNSIGNED CHECK ({E_PERFORMANCE.PUNTUALIDAD.value} BETWEEN 0 AND 100),
                    {E_PERFORMANCE.EFICIENCIA.value} DECIMAL(5,2),
                    {E_PERFORMANCE.BONIFICACION.value} DECIMAL(10,2),
                    {E_PERFORMANCE.HISTORIAL_FALTAS.value} JSON,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY ({E_PERFORMANCE.NUMERO_NOMINA.value})
                        REFERENCES empleados(numero_nomina)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {E_PERFORMANCE.TABLE.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {E_PERFORMANCE.TABLE.value} ya existe.")
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {E_PERFORMANCE.TABLE.value}: {ex}")
            return False

    def add(self, numero_nomina, puntualidad, eficiencia, bonificacion, historial_faltas):
        """
        Agrega un nuevo registro de desempeño.
        """
        try:
            query = f"""
            INSERT INTO {E_PERFORMANCE.TABLE.value} (
                {E_PERFORMANCE.NUMERO_NOMINA.value},
                {E_PERFORMANCE.PUNTUALIDAD.value},
                {E_PERFORMANCE.EFICIENCIA.value},
                {E_PERFORMANCE.BONIFICACION.value},
                {E_PERFORMANCE.HISTORIAL_FALTAS.value}
            ) VALUES (%s, %s, %s, %s, %s)
            """
            self.db.run_query(query, (
                numero_nomina,
                puntualidad,
                eficiencia,
                bonificacion,
                historial_faltas
            ))
            return {"status": "success", "message": "Desempeño registrado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al registrar desempeño: {ex}"}

    def get_all(self):
        """
        Retorna todos los registros de desempeño.
        """
        try:
            query = f"SELECT * FROM {E_PERFORMANCE.TABLE.value}"
            result = self.db.get_data_list(query)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener desempeños: {ex}"}

    def get_by_id(self, id_desempeno: int):
        """
        Retorna un registro de desempeño por su ID.
        """
        try:
            query = f"""
                SELECT * FROM {E_PERFORMANCE.TABLE.value}
                WHERE {E_PERFORMANCE.ID.value} = %s
            """
            result = self.db.get_data(query, (id_desempeno,), dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener el desempeño: {ex}"}

    def get_by_empleado(self, numero_nomina: int):
        """
        Retorna todos los registros de desempeño de un empleado.
        """
        try:
            query = f"""
                SELECT * FROM {E_PERFORMANCE.TABLE.value}
                WHERE {E_PERFORMANCE.NUMERO_NOMINA.value} = %s
            """
            result = self.db.get_data_list(query, (numero_nomina,))
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener desempeño del empleado: {ex}"}
