from datetime import datetime
from decimal import Decimal
from app.core.interfaces.database_mysql import DatabaseMysql
from app.core.enums.e_loan_payment_model import E_PAGOS_PRESTAMO
from app.core.enums.e_prestamos_model import E_PRESTAMOS


class LoanPaymentModel:
    INTERESES_PERMITIDOS = (5, 10, 15)

    def __init__(self):
        self.db = DatabaseMysql()
        self.E = E_PAGOS_PRESTAMO
        self.P = E_PRESTAMOS
        self._exists_table = self.check_table()

    def check_table(self) -> bool:
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, self.E.TABLE.value), dictionary=True)
            if result.get("c", 0) == 0:
                print(f"⚠️ La tabla {self.E.TABLE.value} no existe. Creando...")
                create_query = f"""
                CREATE TABLE {self.E.TABLE.value} (
                    {self.E.PAGO_ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {self.E.PAGO_ID_PRESTAMO.value} INT NOT NULL,
                    {self.E.PAGO_MONTO_PAGADO.value} DECIMAL(10,2) NOT NULL,
                    {self.E.PAGO_FECHA_PAGO.value} DATE NOT NULL,
                    {self.E.PAGO_FECHA_REAL.value} DATE,
                    {self.E.PAGO_INTERES_PORCENTAJE.value} INT NOT NULL,
                    {self.E.PAGO_INTERES_APLICADO.value} DECIMAL(10,2) NOT NULL,
                    {self.E.PAGO_DIAS_RETRASO.value} INT DEFAULT 0,
                    {self.E.PAGO_SALDO_RESTANTE.value} DECIMAL(10,2),
                    {self.E.PAGO_OBSERVACIONES.value} TEXT,
                    FOREIGN KEY ({self.E.PAGO_ID_PRESTAMO.value})
                        REFERENCES {self.P.TABLE.value}({self.P.PRESTAMO_ID.value})
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {self.E.TABLE.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {self.E.TABLE.value} ya existe.")
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla: {ex}")
            return False

    def add_payment(self, id_prestamo: int, monto_pagado: float, fecha_pago: str, fecha_generacion: str,
                    interes_porcentaje: int, fecha_real_pago: str = None, observaciones: str = None):
        try:
            result = self.db.get_data(f"""
                SELECT {self.P.PRESTAMO_SALDO.value}
                FROM {self.P.TABLE.value}
                WHERE {self.P.PRESTAMO_ID.value} = %s
            """, (id_prestamo,), dictionary=True)

            if not result:
                return {"status": "error", "message": "Préstamo no encontrado"}

            saldo_actual = float(result.get(self.P.PRESTAMO_SALDO.value, 0))

            if interes_porcentaje not in self.INTERESES_PERMITIDOS:
                return {"status": "error", "message": "Solo se permiten intereses del 5%, 10% o 15%"}

            interes_aplicado = round(saldo_actual * (interes_porcentaje / 100), 2)
            saldo_con_interes = saldo_actual + interes_aplicado
            nuevo_saldo = round(saldo_con_interes - monto_pagado, 2)

            f_gen = datetime.strptime(fecha_generacion, "%Y-%m-%d")
            f_pago = datetime.strptime(fecha_real_pago or fecha_pago, "%Y-%m-%d")
            dias_retraso = max((f_pago - f_gen).days, 0)

            insert_query = f"""
                INSERT INTO {self.E.TABLE.value} (
                    {self.E.PAGO_ID_PRESTAMO.value},
                    {self.E.PAGO_MONTO_PAGADO.value},
                    {self.E.PAGO_FECHA_PAGO.value},
                    {self.E.PAGO_FECHA_REAL.value},
                    {self.E.PAGO_INTERES_PORCENTAJE.value},
                    {self.E.PAGO_INTERES_APLICADO.value},
                    {self.E.PAGO_DIAS_RETRASO.value},
                    {self.E.PAGO_SALDO_RESTANTE.value},
                    {self.E.PAGO_OBSERVACIONES.value}
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(insert_query, (
                id_prestamo,
                monto_pagado,
                fecha_pago,
                fecha_real_pago or fecha_pago,
                interes_porcentaje,
                interes_aplicado,
                dias_retraso,
                nuevo_saldo,
                observaciones
            ))

            self.db.run_query(
                f"UPDATE {self.P.TABLE.value} SET {self.P.PRESTAMO_SALDO.value} = %s WHERE {self.P.PRESTAMO_ID.value} = %s",
                (nuevo_saldo, id_prestamo)
            )

            if nuevo_saldo <= 0:
                self.db.run_query(
                    f"UPDATE {self.P.TABLE.value} SET {self.P.PRESTAMO_ESTADO.value} = 'terminado' WHERE {self.P.PRESTAMO_ID.value} = %s",
                    (id_prestamo,)
                )

            return {
                "status": "success",
                "message": f"Pago registrado. Interés: ${interes_aplicado}, nuevo saldo: ${nuevo_saldo}, retraso: {dias_retraso} días"
            }

        except Exception as ex:
            return {"status": "error", "message": f"Error al registrar pago: {ex}"}

    def get_by_prestamo(self, id_prestamo: int):
        try:
            query = f"""
                SELECT * FROM {self.E.TABLE.value}
                WHERE {self.E.PAGO_ID_PRESTAMO.value} = %s
                ORDER BY {self.E.PAGO_FECHA_PAGO.value} ASC
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
            valores.append(id_pago)

            query = f"""
                UPDATE {self.E.TABLE.value}
                SET {campos_sql}
                WHERE {self.E.PAGO_ID.value} = %s
            """
            self.db.run_query(query, tuple(valores))

            return {"status": "success", "message": "Pago actualizado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al actualizar el pago: {ex}"}

    def delete_by_id_pago(self, id_pago: int):
        try:
            query = f"""
                DELETE FROM {self.E.TABLE.value}
                WHERE {self.E.PAGO_ID.value} = %s
            """
            self.db.run_query(query, (id_pago,))
            return {"status": "success", "message": f"Pago ID {id_pago} eliminado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al eliminar el pago: {ex}"}

    def get_saldo_y_monto_prestamo(self, id_prestamo: int):
        try:
            query = f"""
                SELECT {self.P.PRESTAMO_MONTO.value} AS monto_prestamo,
                    {self.P.PRESTAMO_SALDO.value} AS saldo_prestamo
                FROM {self.P.TABLE.value}
                WHERE {self.P.PRESTAMO_ID.value} = %s
            """
            result = self.db.get_data(query, (id_prestamo,), dictionary=True)
            return result if result else {}
        except Exception:
            return {}

    def get_next_id(self):
        query = f"SELECT MAX({self.E.PAGO_ID.value}) AS max_id FROM {self.E.TABLE.value}"
        result = self.db.get_data(query, dictionary=True)
        max_id = result.get("max_id", 0) if result else 0
        return int(max_id) + 1 if max_id else 1
