from app.core.enums.e_payment_model import E_PAYMENT
from app.core.interfaces.database_mysql import DatabaseMysql

class PaymentModel:
    """
    Modelo de pagos (nómina).
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self._exists_table = self.check_table()

    def check_table(self) -> bool:
        """
        Verifica si la tabla de pagos existe y la crea si no existe, con estructura igual al .sql.
        """
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, E_PAYMENT.TABLE.value))
            count = result[0] if isinstance(result, tuple) else result.get("c", 0)

            if count == 0:
                print(f"⚠️ La tabla {E_PAYMENT.TABLE.value} no existe. Creando...")

                create_query = f"""
                CREATE TABLE IF NOT EXISTS {E_PAYMENT.TABLE.value} (
                    {E_PAYMENT.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {E_PAYMENT.NUMERO_NOMINA.value} SMALLINT UNSIGNED NOT NULL,
                    {E_PAYMENT.FECHA_PAGO.value} DATE NOT NULL,
                    {E_PAYMENT.MONTO_TOTAL.value} DECIMAL(10,2) NOT NULL,
                    {E_PAYMENT.SALDO.value} DECIMAL(10,2) DEFAULT 0,
                    {E_PAYMENT.PAGO_DEPOSITO.value} DECIMAL(10,2) NOT NULL,
                    {E_PAYMENT.PAGO_EFECTIVO.value} DECIMAL(10,2) NOT NULL,
                    {E_PAYMENT.RETENCIONES_IMSS.value} DECIMAL(10,2) NOT NULL DEFAULT 50,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY ({E_PAYMENT.NUMERO_NOMINA.value})
                        REFERENCES empleados(numero_nomina)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {E_PAYMENT.TABLE.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {E_PAYMENT.TABLE.value} ya existe.")
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {E_PAYMENT.TABLE.value}: {ex}")
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
