from app.core.enums.e_loan_model import E_LOAN
from app.core.interfaces.database_mysql import DatabaseMysql

class LoanModel:
    """
    Modelo de préstamos.
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self._exits_table = self.check_table()

    def check_table(self) -> bool:
        """
        Verifica si la tabla de préstamos existe.
        """
        query = "SHOW TABLES"
        result_tables = self.db.get_data_list(query)

        if result_tables:
            key = list(result_tables[0].keys())[0]
            for tabla in result_tables:
                if tabla[key] == E_LOAN.TABLE.value:
                    return True
        return False

    def add(self, numero_nomina, monto, saldo_prestamo, estado, fecha_solicitud, historial_pagos, descuento_semanal, tipo_descuento):
        """
        Agrega un nuevo préstamo.
        """
        try:
            query = f"""
            INSERT INTO {E_LOAN.TABLE.value} (
                {E_LOAN.NUMERO_NOMINA.value},
                {E_LOAN.MONTO.value},
                {E_LOAN.SALDO_PRESTAMO.value},
                {E_LOAN.ESTADO.value},
                {E_LOAN.FECHA_SOLICITUD.value},
                {E_LOAN.HISTORIAL_PAGOS.value},
                {E_LOAN.DESCUENTO_SEMANAL.value},
                {E_LOAN.TIPO_DESCUENTO.value}
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(query, (
                numero_nomina,
                monto,
                saldo_prestamo,
                estado,
                fecha_solicitud,
                historial_pagos,
                descuento_semanal,
                tipo_descuento
            ))
            return {"status": "success", "message": "Préstamo registrado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al registrar el préstamo: {ex}"}

    def get_all(self):
        """
        Retorna todos los préstamos registrados.
        """
        try:
            query = f"SELECT * FROM {E_LOAN.TABLE.value}"
            result = self.db.get_data_list(query)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener préstamos: {ex}"}

    def get_by_id(self, id_prestamo: int):
        """
        Retorna un préstamo por su ID.
        """
        try:
            query = f"""
                SELECT * FROM {E_LOAN.TABLE.value}
                WHERE {E_LOAN.ID.value} = %s
            """
            result = self.db.get_data(query, (id_prestamo,))
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener el préstamo: {ex}"}

    def get_by_empleado(self, numero_nomina: int):
        """
        Retorna los préstamos asociados a un número de nómina.
        """
        try:
            query = f"""
                SELECT * FROM {E_LOAN.TABLE.value}
                WHERE {E_LOAN.NUMERO_NOMINA.value} = %s
            """
            result = self.db.get_data_list(query, (numero_nomina,))
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener préstamos del empleado: {ex}"}
