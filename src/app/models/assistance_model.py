from app.core.enums.e_assistance_model import E_ASSISTANCE
from app.core.interfaces.database_mysql import DatabaseMysql

class AssistanceModel:
    """
    Modelo de asistencias.
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self._exists_table = self.check_table()

    def check_table(self) -> bool:
        """
        Verifica si la tabla de asistencias existe y la crea con la estructura del archivo SQL si no existe.
        """
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, E_ASSISTANCE.TABLE.value))
            if result.get("c", 0) == 0:
                print(f"⚠️ La tabla {E_ASSISTANCE.TABLE.value} no existe. Creando...")

                create_query = f"""
                CREATE TABLE IF NOT EXISTS {E_ASSISTANCE.TABLE.value} (
                    {E_ASSISTANCE.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {E_ASSISTANCE.NUMERO_NOMINA.value} SMALLINT UNSIGNED NOT NULL,
                    {E_ASSISTANCE.FECHA.value} DATE NOT NULL,
                    {E_ASSISTANCE.HORA_ENTRADA.value} TIME,
                    {E_ASSISTANCE.HORA_SALIDA.value} TIME,
                    {E_ASSISTANCE.DURACION_COMIDA.value} TIME,
                    {E_ASSISTANCE.TIPO_REGISTRO.value} ENUM('automático','manual') NOT NULL,
                    {E_ASSISTANCE.HORAS_TRABAJADAS.value} TIME,
                    FOREIGN KEY ({E_ASSISTANCE.NUMERO_NOMINA.value})
                        REFERENCES empleados(numero_nomina)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {E_ASSISTANCE.TABLE.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {E_ASSISTANCE.TABLE.value} ya existe.")
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {E_ASSISTANCE.TABLE.value}: {ex}")
            return False

    def add(self, numero_nomina, fecha, hora_entrada, hora_salida, duracion_comida, tipo_registro, horas_trabajadas):
        """
        Agrega una nueva asistencia.
        """
        try:
            query = f"""
            INSERT INTO {E_ASSISTANCE.TABLE.value} (
                {E_ASSISTANCE.NUMERO_NOMINA.value},
                {E_ASSISTANCE.FECHA.value},
                {E_ASSISTANCE.HORA_ENTRADA.value},
                {E_ASSISTANCE.HORA_SALIDA.value},
                {E_ASSISTANCE.DURACION_COMIDA.value},
                {E_ASSISTANCE.TIPO_REGISTRO.value},
                {E_ASSISTANCE.HORAS_TRABAJADAS.value}
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(query, (
                numero_nomina,
                fecha,
                hora_entrada,
                hora_salida,
                duracion_comida,
                tipo_registro,
                horas_trabajadas
            ))
            return {"status": "success", "message": "Asistencia agregada correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al agregar asistencia: {ex}"}

    def get_all(self) -> dict:
        """
        Retorna todas las asistencias registradas.
        """
        try:
            query = f"SELECT * FROM {E_ASSISTANCE.TABLE.value}"
            result = self.db.get_data_list(query)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener asistencias: {ex}"}

    def get_by_id(self, id_asistencia: int) -> dict:
        """
        Retorna una asistencia por su ID.
        """
        try:
            query = f"""
                SELECT * FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.ID.value} = %s
            """
            result = self.db.get_data(query, (id_asistencia,))
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener asistencia por ID: {ex}"}

    def get_by_empleado_fecha(self, numero_nomina: int, fecha: str) -> dict | None:
        """
        Retorna la asistencia de un empleado en una fecha específica.
        """
        try:
            query = f"""
                SELECT * FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.NUMERO_NOMINA.value} = %s AND {E_ASSISTANCE.FECHA.value} = %s
            """
            result = self.db.get_data(query, (numero_nomina, fecha))
            return result
        except Exception as ex:
            print(f"Error al obtener asistencia: {ex}")
            return None
