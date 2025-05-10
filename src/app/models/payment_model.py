from app.core.enums.e_payment_model import E_PAYMENT
from app.core.interfaces.database_mysql import DatabaseMysql
from app.models.discount_model import DiscountModel

class PaymentModel:
    """
    Modelo de pagos (nómina).
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self._exists_table = self.check_table()

    def check_table(self) -> bool:
        """
        Verifica si la tabla de pagos existe y la crea si no existe.
        """
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, E_PAYMENT.TABLE.value), dictionary=True)
            count = result.get("c", 0)

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

    def add(self, numero_nomina: int, fecha_pago: str, monto_total: float, saldo: float, pago_deposito: float, pago_efectivo: float):
        try:
            query = f"""
            INSERT INTO {E_PAYMENT.TABLE.value} (
                {E_PAYMENT.NUMERO_NOMINA.value},
                {E_PAYMENT.FECHA_PAGO.value},
                {E_PAYMENT.MONTO_TOTAL.value},
                {E_PAYMENT.SALDO.value},
                {E_PAYMENT.PAGO_DEPOSITO.value},
                {E_PAYMENT.PAGO_EFECTIVO.value}
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(query, (numero_nomina, fecha_pago, monto_total, saldo, pago_deposito, pago_efectivo))
            return {"status": "success", "message": "Pago registrado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al registrar el pago: {ex}"}

    def get_all(self):
        try:
            query = f"SELECT * FROM {E_PAYMENT.TABLE.value}"
            result = self.db.get_data_list(query, dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener pagos: {ex}"}

    def get_by_id(self, id_pago: int):
        try:
            query = f"""
                SELECT * FROM {E_PAYMENT.TABLE.value}
                WHERE {E_PAYMENT.ID.value} = %s
            """
            result = self.db.get_data(query, (id_pago,), dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener el pago: {ex}"}

    def get_by_empleado(self, numero_nomina: int):
        try:
            query = f"""
                SELECT * FROM {E_PAYMENT.TABLE.value}
                WHERE {E_PAYMENT.NUMERO_NOMINA.value} = %s
            """
            result = self.db.get_data_list(query, (numero_nomina,), dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener pagos del empleado: {ex}"}

    def get_by_fecha_rango(self, fecha_inicio: str, fecha_fin: str):
        try:
            query = f"""
            SELECT * FROM {E_PAYMENT.TABLE.value}
            WHERE {E_PAYMENT.FECHA_PAGO.value} BETWEEN %s AND %s
            """
            result = self.db.get_data_list(query, (fecha_inicio, fecha_fin), dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al filtrar por fechas: {ex}"}

    def get_by_mes(self, mes: int, anio: int):
        try:
            query = f"""
            SELECT * FROM {E_PAYMENT.TABLE.value}
            WHERE MONTH({E_PAYMENT.FECHA_PAGO.value}) = %s AND YEAR({E_PAYMENT.FECHA_PAGO.value}) = %s
            """
            result = self.db.get_data_list(query, (mes, anio), dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener pagos por mes: {ex}"}

    def get_pagos_con_saldo(self):
        try:
            query = f"""
            SELECT * FROM {E_PAYMENT.TABLE.value}
            WHERE {E_PAYMENT.SALDO.value} > 0
            """
            result = self.db.get_data_list(query, dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener pagos con saldo: {ex}"}

    def update_pago(self, id_pago: int, campos_actualizados: dict):
        try:
            campos_sql = ", ".join([f"{campo} = %s" for campo in campos_actualizados.keys()])
            valores = list(campos_actualizados.values()) + [id_pago]

            query = f"""
            UPDATE {E_PAYMENT.TABLE.value}
            SET {campos_sql}
            WHERE {E_PAYMENT.ID.value} = %s
            """
            self.db.run_query(query, tuple(valores))
            return {"status": "success", "message": "Pago actualizado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al actualizar el pago: {ex}"}

    def get_pago_con_descuentos(self, id_pago: int):
        try:
            pago = self.get_by_id(id_pago)
            if pago["status"] != "success":
                return pago
            descuentos = DiscountModel().get_by_pago(id_pago)
            return {
                "status": "success",
                "data": {
                    "pago": pago["data"],
                    "descuentos": descuentos
                }
            }
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener el pago con descuentos: {ex}"}