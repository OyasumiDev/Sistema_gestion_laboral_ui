from app.core.enums.e_payment_model import E_PAYMENT
from app.core.interfaces.database_mysql import DatabaseMysql

class PaymentModel:
    """
    Modelo de pagos (nómina).
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self._exits_table = self.check_table()

    def check_table(self) -> bool:
        """
        Verifica si la tabla de pagos existe.
        """
        query = "SHOW TABLES"
        result_tables = self.db.get_data_list(query)

        if result_tables:
            key = list(result_tables[0].keys())[0]
            for tabla in result_tables:
                if tabla[key] == E_PAYMENT.TABLE.value:
                    return True
        return False

    def add(self, numero_nomina, fecha_pago, monto_total, saldo, pago_deposito, pago_efectivo, retenciones_imss):
        """
        Registra un nuevo pago.
        """
        try:
            query = f"""
            INSERT INTO {E_PAYMENT.TABLE.value} (
                {E_PAYMENT.NUMERO_NOMINA.value},
                {E_PAYMENT.FECHA_PAGO.value},
                {E_PAYMENT.MONTO_TOTAL.value},
                {E_PAYMENT.SALDO.value},
                {E_PAYMENT.PAGO_DEPOSITO.value},
                {E_PAYMENT.PAGO_EFECTIVO.value},
                {E_PAYMENT.RETENCIONES_IMSS.value}
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(query, (
                numero_nomina,
                fecha_pago,
                monto_total,
                saldo,
                pago_deposito,
                pago_efectivo,
                retenciones_imss
            ))
            return {"status": "success", "message": "Pago registrado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al registrar el pago: {ex}"}

    def get_all(self):
        """
        Retorna todos los pagos registrados.
        """
        try:
            query = f"SELECT * FROM {E_PAYMENT.TABLE.value}"
            result = self.db.get_data_list(query)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener pagos: {ex}"}

    def get_by_id(self, id_pago: int):
        """
        Retorna un pago por su ID.
        """
        try:
            query = f"""
                SELECT * FROM {E_PAYMENT.TABLE.value}
                WHERE {E_PAYMENT.ID.value} = %s
            """
            result = self.db.get_data(query, (id_pago,))
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener el pago: {ex}"}

    def get_by_empleado(self, numero_nomina: int):
        """
        Retorna todos los pagos asociados a un número de nómina.
        """
        try:
            query = f"""
                SELECT * FROM {E_PAYMENT.TABLE.value}
                WHERE {E_PAYMENT.NUMERO_NOMINA.value} = %s
            """
            result = self.db.get_data_list(query, (numero_nomina,))
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener pagos del empleado: {ex}"}
