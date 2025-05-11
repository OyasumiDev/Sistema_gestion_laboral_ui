from datetime import datetime
from app.core.interfaces.database_mysql import DatabaseMysql
from app.core.enums.e_loan_payment_model import E_LOAN_PAYMENT
from app.core.enums.e_loan_model import E_LOAN

class LoanPaymentModel:
    """
    Modelo de pagos de préstamos.
    Permite registrar pagos con interés, fechas de generación/pago y días de retraso.
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self._exists_table = self.check_table()
        self.verificar_o_crear_triggers()

    def check_table(self) -> bool:
        """
        Verifica si la tabla de pagos de préstamo existe y la crea si no.
        """
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, E_LOAN_PAYMENT.TABLE.value))
            count = result[0] if isinstance(result, tuple) else result.get("c", 0)

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

    def verificar_o_crear_triggers(self):
        self._crear_trigger_actualizar_saldo()
        self._crear_trigger_cerrar_prestamo()

    def _crear_trigger_actualizar_saldo(self):
        try:
            trigger_name = "trg_actualizar_saldo_prestamo"
            check_query = """
                SELECT COUNT(*) AS c
                FROM information_schema.triggers
                WHERE trigger_schema = %s AND trigger_name = %s
            """
            result = self.db.get_data(check_query, (self.db.database, trigger_name), dictionary=True)
            count = result.get("c", 0)

            if count == 0:
                print(f"⚠️ Trigger '{trigger_name}' no existe. Creando...")
                trigger_sql = """
                CREATE TRIGGER trg_actualizar_saldo_prestamo
                AFTER INSERT ON pagos_prestamo
                FOR EACH ROW
                BEGIN
                    DECLARE saldo_anterior DECIMAL(10,2);
                    DECLARE saldo_actualizado DECIMAL(10,2);

                    SELECT saldo_prestamo INTO saldo_anterior
                    FROM prestamos
                    WHERE id_prestamo = NEW.id_prestamo;

                    SET saldo_actualizado = (saldo_anterior - NEW.monto_pagado) * 1.10;

                    UPDATE prestamos
                    SET saldo_prestamo = ROUND(saldo_actualizado, 2)
                    WHERE id_prestamo = NEW.id_prestamo;
                END
                """
                cursor = self.db.connection.cursor()
                cursor.execute(trigger_sql)
                self.db.connection.commit()
                cursor.close()
                print(f"✅ Trigger '{trigger_name}' creado correctamente.")
            else:
                print(f"✔️ Trigger '{trigger_name}' ya existe.")
        except Exception as ex:
            print(f"❌ Error creando trigger '{trigger_name}': {ex}")

    def _crear_trigger_cerrar_prestamo(self):
        try:
            trigger_name = "trg_cerrar_prestamo_si_pagado"
            check_query = """
                SELECT COUNT(*) AS c
                FROM information_schema.triggers
                WHERE trigger_schema = %s AND trigger_name = %s
            """
            result = self.db.get_data(check_query, (self.db.database, trigger_name), dictionary=True)
            count = result.get("c", 0)

            if count == 0:
                print(f"⚠️ Trigger '{trigger_name}' no existe. Creando...")
                trigger_sql = """
                CREATE TRIGGER trg_cerrar_prestamo_si_pagado
                AFTER UPDATE ON prestamos
                FOR EACH ROW
                BEGIN
                    IF NEW.saldo_prestamo <= 0 THEN
                        UPDATE prestamos
                        SET estado = 'pagado'
                        WHERE id_prestamo = NEW.id_prestamo;
                    END IF;
                END
                """
                cursor = self.db.connection.cursor()
                cursor.execute(trigger_sql)
                self.db.connection.commit()
                cursor.close()
                print(f"✅ Trigger '{trigger_name}' creado correctamente.")
            else:
                print(f"✔️ Trigger '{trigger_name}' ya existe.")
        except Exception as ex:
            print(f"❌ Error creando trigger '{trigger_name}': {ex}")

    def add_payment(self, id_prestamo: int, monto_pagado: float, fecha_pago: str, fecha_generacion: str):
        """
        Registra un nuevo pago, calcula interés y días de retraso.
        """
        try:
            query_saldo = f"""
                SELECT {E_LOAN.PRESTAMO_SALDO.value}
                FROM {E_LOAN.TABLE.value}
                WHERE {E_LOAN.PRESTAMO_ID.value} = %s
            """
            result = self.db.get_data(query_saldo, (id_prestamo,))
            if not result:
                return {"status": "error", "message": "Préstamo no encontrado"}

            saldo_actual = float(result[E_LOAN.PRESTAMO_SALDO.value])
            interes_aplicado = round(saldo_actual * 0.10, 2)
            nuevo_saldo = round(saldo_actual + interes_aplicado - monto_pagado, 2)

            f_gen = datetime.strptime(fecha_generacion, "%Y-%m-%d")
            f_pago = datetime.strptime(fecha_pago, "%Y-%m-%d")
            dias_retraso = max((f_pago - f_gen).days, 0)

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
                interes_aplicado,
                dias_retraso
            ))

            update_saldo_query = f"""
                UPDATE {E_LOAN.TABLE.value}
                SET {E_LOAN.PRESTAMO_SALDO.value} = %s
                WHERE {E_LOAN.PRESTAMO_ID.value} = %s
            """
            self.db.run_query(update_saldo_query, (nuevo_saldo, id_prestamo))

            return {
                "status": "success",
                "message": f"Pago registrado. Interés aplicado: ${interes_aplicado}, nuevo saldo: ${nuevo_saldo}, días de retraso: {dias_retraso}"
            }

        except Exception as ex:
            return {"status": "error", "message": f"Error al registrar pago: {ex}"}

    def get_by_prestamo(self, id_prestamo: int):
        """
        Obtiene todos los pagos asociados a un préstamo.
        """
        try:
            query = f"""
                SELECT * FROM {E_LOAN_PAYMENT.TABLE.value}
                WHERE {E_LOAN_PAYMENT.PAGO_ID_PRESTAMO.value} = %s
                ORDER BY {E_LOAN_PAYMENT.PAGO_FECHA_PAGO.value} ASC
            """
            result = self.db.get_data_list(query, (id_prestamo,))
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener pagos: {ex}"}

    def update_by_id_pago(self, id_pago: int, campos: dict):
        """
        Actualiza cualquier campo de un pago específico usando su ID.
        """
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
        """
        Elimina un pago por su ID.
        """
        try:
            query = f"""
                DELETE FROM {E_LOAN_PAYMENT.TABLE.value}
                WHERE {E_LOAN_PAYMENT.PAGO_ID.value} = %s
            """
            self.db.run_query(query, (id_pago,))
            return {"status": "success", "message": f"Pago ID {id_pago} eliminado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al eliminar el pago: {ex}"}
