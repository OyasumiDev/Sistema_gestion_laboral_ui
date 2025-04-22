from app.core.enums.e_employes_model import E_EMPLOYE
from app.core.interfaces.database_mysql import DatabaseMysql

class EmployesModel:
    """
    Modelo para el manejo de empleados.
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self._exits_table = self.check_table()

    def check_table(self) -> bool:
        """
        Verifica si la tabla de empleados existe.
        """
        query = "SHOW TABLES"
        result_tables = self.db.get_data_list(query)

        if result_tables:
            key = list(result_tables[0].keys())[0]
            for tabla in result_tables:
                if tabla[key] == E_EMPLOYE.TABLE.value:
                    return True
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
