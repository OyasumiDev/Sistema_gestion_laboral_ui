from app.core.enums.e_performance_model import E_PERFORMANCE
from app.core.interfaces.database_mysql import DatabaseMysql

class PerformanceModel:
    """
    Modelo de desempeño de empleados.
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self._exits_table = self.check_table()

    def check_table(self) -> bool:
        """
        Verifica si la tabla de desempeño existe.
        """
        query = "SHOW TABLES"
        result_tables = self.db.get_data_list(query)

        if result_tables:
            key = list(result_tables[0].keys())[0]
            for tabla in result_tables:
                if tabla[key] == E_PERFORMANCE.TABLE.value:
                    return True
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
            result = self.db.get_data(query, (id_desempeno,))
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
