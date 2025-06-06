from app.core.enums.e_employes_model import E_EMPLOYE
from app.core.interfaces.database_mysql import DatabaseMysql

class EmployesModel:
    """
    Modelo para el manejo de empleados. Crea la tabla 'empleados' si no existe.
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self.E = E_EMPLOYE
        self._exists_table = self.check_table()

    def check_table(self) -> bool:
        """
        Verifica si la tabla de empleados existe y la crea con la estructura adecuada si no existe.
        """
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, self.E.TABLE.value), dictionary=True)
            existe = result.get("c", 0) > 0

            if not existe:
                print(f"⚠️ La tabla {self.E.TABLE.value} no existe. Creando...")

                create_query = f"""
                CREATE TABLE IF NOT EXISTS {self.E.TABLE.value} (
                    {self.E.NUMERO_NOMINA.value} SMALLINT UNSIGNED PRIMARY KEY,
                    {self.E.NOMBRE_COMPLETO.value} VARCHAR(255) NOT NULL,
                    {self.E.ESTADO.value} ENUM('activo','inactivo') NOT NULL,
                    {self.E.TIPO_TRABAJADOR.value} ENUM('taller','externo','no definido') NOT NULL,
                    {self.E.SUELDO_POR_HORA.value} DECIMAL(8,2) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {self.E.TABLE.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {self.E.TABLE.value} ya existe.")
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {self.E.TABLE.value}: {ex}")
            return False


    def add(self, numero_nomina, nombre_completo, estado, tipo_trabajador, sueldo_por_hora):
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
                {E_EMPLOYE.SUELDO_POR_HORA.value}
            ) VALUES (%s, %s, %s, %s, %s)
            """
            self.db.run_query(query, (
                numero_nomina,
                nombre_completo,
                estado,
                tipo_trabajador,
                sueldo_por_hora
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
            result = self.db.get_data_list(query, dictionary=True)
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
            return self.db.get_data(query, (numero_nomina,), dictionary=True)
        except Exception as ex:
            print(f"❌ Error al obtener el empleado: {ex}")
            return {}
        
    def delete_by_numero_nomina(self, numero_nomina: int):
        """
        Elimina un empleado por su número de nómina.
        """
        try:
            query = f"DELETE FROM {E_EMPLOYE.TABLE.value} WHERE {E_EMPLOYE.NUMERO_NOMINA.value} = %s"
            self.db.run_query(query, (numero_nomina,))
            return {"status": "success", "message": "Empleado eliminado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al eliminar el empleado: {ex}"}

    def get_ultimo_numero_nomina(self) -> int:
        try:
            query = f"SELECT MAX({E_EMPLOYE.NUMERO_NOMINA.value}) AS ultimo FROM {E_EMPLOYE.TABLE.value}"
            result = self.db.get_data(query, dictionary=True)
            return int(result.get("ultimo", 0)) if result else 0
        except Exception:
            return 0

    def update(self, numero_nomina, estado, tipo_trabajador, sueldo_por_hora):
        """
        Actualiza un empleado por su número de nómina.
        """
        try:
            query = f"""
                UPDATE {E_EMPLOYE.TABLE.value}
                SET
                    {E_EMPLOYE.ESTADO.value} = %s,
                    {E_EMPLOYE.TIPO_TRABAJADOR.value} = %s,
                    {E_EMPLOYE.SUELDO_POR_HORA.value} = %s
                WHERE {E_EMPLOYE.NUMERO_NOMINA.value} = %s
            """
            self.db.run_query(query, (
                estado,
                tipo_trabajador,
                sueldo_por_hora,
                numero_nomina
            ))
            return { "status": "success", "message": "Empleado actualizado correctamente" }
        except Exception as ex:
            return { "status": "error", "message": f"Error al actualizar el empleado: {ex}" }
