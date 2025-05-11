from datetime import datetime
from decimal import Decimal
from app.core.interfaces.database_mysql import DatabaseMysql
from app.core.enums.e_loan_payment_model import E_LOAN_PAYMENT
from app.core.enums.e_loan_model import E_LOAN

class LoanPaymentModel:
    """
    Modelo de pagos de préstamos.
    Permite registrar pagos con interés, fechas de generación/pago y días de retraso.
    Solo se permiten los porcentajes: 5%, 10% o 15%.
    """

    INTERESES_PERMITIDOS = (5.0, 10.0, 15.0)

    def __init__(self):
        self.db = DatabaseMysql()
        self._exists_table = self.check_table()

    def check_table(self) -> bool:
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, E_LOAN_PAYMENT.TABLE.value), dictionary=True)
            count = result.get("c", 0)

            if count == 0:
                print(f"⚠️ La tabla {E_LOAN_PAYMENT.TABLE.value} no existe. Creando...")
                create_query = f"""
                CREATE TABLE {E_LOAN_PAYMENT.TABLE.value} (
                    {E_LOAN_PAYMENT.PAGO_ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {E_LOAN_PAYMENT.PAGO_ID_PRESTAMO.value} INT NOT NULL,
                    {E_LOAN_PAYMENT.PAGO_MONTO_PAGADO.value} DECIMAL(10,2) NOT NULL,
                    {E_LOAN_PAYMENT.PAGO_FECHA_PAGO.value} DATE NOT NULL,
                    {E_LOAN_PAYMENT.PAGO_FECHA_GENERACION.value} DATE NOT NULL,
                    {E_LOAN_PAYMENT.PAGO_INTERES_APLICADO.value} DECIMAL(10,2) NOT NULL,
                    {E_LOAN_PAYMENT.PAGO_DIAS_RETRASO.value} INT DEFAULT 0,
                    FOREIGN KEY ({E_LOAN_PAYMENT.PAGO_ID_PRESTAMO.value})
                        REFERENCES {E_LOAN.TABLE.value}({E_LOAN.PRESTAMO_ID.value})
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {E_LOAN_PAYMENT.TABLE.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {E_LOAN_PAYMENT.TABLE.value} ya existe.")
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {E_LOAN_PAYMENT.TABLE.value}: {ex}")
            return False

    def add_payment(self, id_prestamo: int, monto_pagado: float, fecha_pago: str, fecha_generacion: str, interes: float = None):
        try:
            # 1. Obtener saldo actual
            query_saldo = f"""
                SELECT {E_LOAN.PRESTAMO_SALDO.value}
                FROM {E_LOAN.TABLE.value}
                WHERE {E_LOAN.PRESTAMO_ID.value} = %s
            """
            result = self.db.get_data(query_saldo, (id_prestamo,), dictionary=True)
            if not result:
                return {"status": "error", "message": "Préstamo no encontrado"}

            saldo_actual = float(result.get(E_LOAN.PRESTAMO_SALDO.value, 0))

            # 2. Aplicar interés permitido
            porcentaje_interes = 10.0 if interes is None else float(interes)
            if porcentaje_interes not in self.INTERESES_PERMITIDOS:
                return {"status": "error", "message": "Solo se permiten intereses del 5%, 10% o 15%"}

            # 3. Calcular el interés y nuevo saldo
            interes_monto = round(saldo_actual * (porcentaje_interes / 100), 2)
            saldo_actual += interes_monto
            nuevo_saldo = round(saldo_actual - monto_pagado, 2)

            # 4. Calcular días de retraso
            f_gen = datetime.strptime(fecha_generacion, "%Y-%m-%d")
            f_pago = datetime.strptime(fecha_pago, "%Y-%m-%d")
            dias_retraso = max((f_pago - f_gen).days, 0)

            # 5. Insertar pago
            insert_query = f"""
                INSERT INTO {E_LOAN_PAYMENT.TABLE.value} (
                    {E_LOAN_PAYMENT.PAGO_ID_PRESTAMO.value},
                    {E_LOAN_PAYMENT.PAGO_MONTO_PAGADO.value},
                    {E_LOAN_PAYMENT.PAGO_FECHA_PAGO.value},
                    {E_LOAN_PAYMENT.PAGO_FECHA_GENERACION.value},
                    {E_LOAN_PAYMENT.PAGO_INTERES_APLICADO.value},
                    {E_LOAN_PAYMENT.PAGO_DIAS_RETRASO.value}
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(insert_query, (
                id_prestamo,
                monto_pagado,
                fecha_pago,
                fecha_generacion,
                interes_monto,
                dias_retraso
            ))

            # 6. Actualizar saldo del préstamo
            self.db.run_query(
                f"UPDATE {E_LOAN.TABLE.value} SET {E_LOAN.PRESTAMO_SALDO.value} = %s WHERE {E_LOAN.PRESTAMO_ID.value} = %s",
                (nuevo_saldo, id_prestamo)
            )

            # 7. Cerrar préstamo si ya se liquidó
            if nuevo_saldo <= 0:
                self.db.run_query(
                    f"UPDATE {E_LOAN.TABLE.value} SET {E_LOAN.PRESTAMO_ESTADO.value} = 'terminado' WHERE {E_LOAN.PRESTAMO_ID.value} = %s",
                    (id_prestamo,)
                )

            return {
                "status": "success",
                "message": f"Pago registrado. Interés aplicado: ${interes_monto}, nuevo saldo: ${nuevo_saldo}, días de retraso: {dias_retraso}"
            }

        except Exception as ex:
            return {"status": "error", "message": f"Error al registrar pago: {ex}"}


    def get_by_prestamo(self, id_prestamo: int):
        try:
            query = f"""
                SELECT
                    {E_LOAN_PAYMENT.PAGO_ID.value} AS id_pago_prestamo,
                    {E_LOAN_PAYMENT.PAGO_ID_PRESTAMO.value} AS id_prestamo,
                    {E_LOAN_PAYMENT.PAGO_MONTO_PAGADO.value} AS monto_pagado,
                    {E_LOAN_PAYMENT.PAGO_FECHA_PAGO.value} AS fecha_pago,
                    {E_LOAN_PAYMENT.PAGO_FECHA_GENERACION.value} AS fecha_generacion,
                    {E_LOAN_PAYMENT.PAGO_INTERES_APLICADO.value} AS interes_aplicado,
                    {E_LOAN_PAYMENT.PAGO_DIAS_RETRASO.value} AS dias_retraso
                FROM {E_LOAN_PAYMENT.TABLE.value}
                WHERE {E_LOAN_PAYMENT.PAGO_ID_PRESTAMO.value} = %s
                ORDER BY {E_LOAN_PAYMENT.PAGO_FECHA_PAGO.value} ASC
            """
            result = self.db.get_data_list(query, (id_prestamo,), dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener pagos: {ex}"}


    def update_by_id_pago(self, id_pago: int, campos: dict):
        try:
            if not campos:
                return {"status": "error", "message": "No se proporcionaron campos para actualizar"}

            campos_sql = ", ".join(f"{k.value} = %s" for k in campos.keys())
            valores = [v for v in campos.values()]

            query = f"""
                UPDATE {E_LOAN_PAYMENT.TABLE.value}
                SET {campos_sql}
                WHERE {E_LOAN_PAYMENT.PAGO_ID.value} = %s
            """
            valores.append(id_pago)
            self.db.run_query(query, tuple(valores))

            return {"status": "success", "message": "Pago actualizado correctamente"}

        except Exception as ex:
            return {"status": "error", "message": f"Error al actualizar el pago: {ex}"}

    def delete_by_id_pago(self, id_pago: int):
        try:
            query = f"""
                DELETE FROM {E_LOAN_PAYMENT.TABLE.value}
                WHERE {E_LOAN_PAYMENT.PAGO_ID.value} = %s
            """
            self.db.run_query(query, (id_pago,))
            return {"status": "success", "message": f"Pago ID {id_pago} eliminado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al eliminar el pago: {ex}"}

    def get_saldo_y_monto_prestamo(self, id_prestamo: int):
        try:
            query = f"""
                SELECT {E_LOAN.PRESTAMO_MONTO.value} AS monto_prestamo, {E_LOAN.PRESTAMO_SALDO.value} AS saldo_prestamo
                FROM {E_LOAN.TABLE.value}
                WHERE {E_LOAN.PRESTAMO_ID.value} = %s
            """
            result = self.db.get_data(query, (id_prestamo,), dictionary=True)
            return result if result else {}
        except Exception:
            return {}
        
    def get_next_id(self):
        query = "SELECT MAX(id_pago) AS max_id FROM pagos_prestamo"
        result = self.db.get_data(query, dictionary=True)
        max_id = result.get("max_id", 0) if result else 0
        return int(max_id) + 1 if max_id else 1
