from app.core.enums.e_employes_model import E_EMPLOYE
from app.core.interfaces.database_mysql import DatabaseMysql

class EmployesModel:
    """
    Modelo para el manejo de empleados.
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self._exists_table = self.check_table()

    def check_table(self) -> bool:
        """
        Verifica si la tabla de empleados existe y la crea con la estructura correcta si no.
        """
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, E_EMPLOYE.TABLE.value))
            if result.get("c", 0) == 0:
                print(f"⚠️ La tabla {E_EMPLOYE.TABLE.value} no existe. Creando...")

                create_query = f"""
                CREATE TABLE IF NOT EXISTS {E_EMPLOYE.TABLE.value} (
                    {E_EMPLOYE.NUMERO_NOMINA.value} SMALLINT UNSIGNED PRIMARY KEY,
                    {E_EMPLOYE.NOMBRE_COMPLETO.value} VARCHAR(255) NOT NULL,
                    {E_EMPLOYE.ESTADO.value} ENUM('activo','inactivo') NOT NULL,
                    {E_EMPLOYE.TIPO_TRABAJADOR.value} ENUM('taller','externo','no definido') NOT NULL,
                    {E_EMPLOYE.SUELDO_DIARIO.value} DECIMAL(8,2) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {E_EMPLOYE.TABLE.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {E_EMPLOYE.TABLE.value} ya existe.")
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {E_EMPLOYE.TABLE.value}: {ex}")
            return False

    def add(self, numero_nomina, nombre_completo, estado, tipo_trabajador, sueldo_diario):
        """
        Agrega un nuevo empleado.
        """
        try:
            query = f"""
            INSERT INTO {E_EMPLOYE.TABLE.value} (
                {E_EMPLOYE.NUMERO_NOMINA.value},
                {E_EMPLOYE.NOMBRE_COMPLETO.value},
                {E_EMPLOYE.ESTADO.value},
                {E_EMPLOYE.TIPO_TRABAJADOR.value},
                {E_EMPLOYE.SUELDO_DIARIO.value}
            ) VALUES (%s, %s, %s, %s, %s)
            """
            self.db.run_query(query, (
                numero_nomina,
                nombre_completo,
                estado,
                tipo_trabajador,
                sueldo_diario
            ))
            return {"status": "success", "message": "Empleado registrado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al registrar el empleado: {ex}"}

    def get_all(self):
        """
        Retorna todos los empleados registrados.
        """
        try:
            query = f"SELECT * FROM {E_EMPLOYE.TABLE.value}"
            result = self.db.get_data_list(query)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener empleados: {ex}"}

    def get_by_numero_nomina(self, numero_nomina: int):
        """
        Retorna un empleado por su número de nómina.
        """
        try:
            query = f"""
                SELECT * FROM {E_EMPLOYE.TABLE.value}
                WHERE {E_EMPLOYE.NUMERO_NOMINA.value} = %s
            """
            result = self.db.get_data(query, (numero_nomina,))
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener el empleado: {ex}"}
