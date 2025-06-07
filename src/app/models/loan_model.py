from app.core.enums.e_prestamos_model import E_PRESTAMOS
from app.core.interfaces.database_mysql import DatabaseMysql
from datetime import datetime

class LoanModel:
    """
    Modelo de préstamos: permite registrar múltiples préstamos por empleado
    y consultarlos por empleado o globalmente.
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self.E = E_PRESTAMOS
        self._exists_table = self.check_table()

    def check_table(self) -> bool:
        """
        Verifica si la tabla de préstamos existe y la crea si no.
        """
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, self.E.TABLE.value), dictionary=True)
            count = result.get("c", 0)

            if count == 0:
                print(f"⚠️ La tabla {self.E.TABLE.value} no existe. Creando...")

                create_query = f"""
                CREATE TABLE {self.E.TABLE.value} (
                    {self.E.PRESTAMO_ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {self.E.PRESTAMO_NUMERO_NOMINA.value} SMALLINT UNSIGNED NOT NULL,
                    {self.E.PRESTAMO_MONTO.value} DECIMAL(10,2) NOT NULL,
                    {self.E.PRESTAMO_SALDO.value} DECIMAL(10,2) NOT NULL,
                    {self.E.PRESTAMO_ESTADO.value} ENUM('pagando','terminado') NOT NULL,
                    {self.E.PRESTAMO_FECHA_SOLICITUD.value} DATE NOT NULL,
                    {self.E.PRESTAMO_FECHA_CREACION.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    {self.E.PRESTAMO_FECHA_MODIFICACION.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY ({self.E.PRESTAMO_NUMERO_NOMINA.value}) REFERENCES empleados(numero_nomina) ON DELETE CASCADE
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

    def add(self, numero_nomina, monto_prestamo, saldo_prestamo=None, estado="pagando", fecha_solicitud=None):
        try:
            query_id = f"SELECT MAX({self.E.PRESTAMO_ID.value}) AS max_id FROM {self.E.TABLE.value}"
            result = self.db.get_data(query_id, dictionary=True)
            next_id = (result.get("max_id") or 0) + 1

            saldo = saldo_prestamo if saldo_prestamo is not None else monto_prestamo
            fecha = fecha_solicitud or datetime.today().strftime("%Y-%m-%d")

            query = f"""
                INSERT INTO {self.E.TABLE.value} (
                    {self.E.PRESTAMO_ID.value},
                    {self.E.PRESTAMO_NUMERO_NOMINA.value},
                    {self.E.PRESTAMO_MONTO.value},
                    {self.E.PRESTAMO_SALDO.value},
                    {self.E.PRESTAMO_ESTADO.value},
                    {self.E.PRESTAMO_FECHA_SOLICITUD.value}
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(query, (
                next_id,
                numero_nomina,
                monto_prestamo,
                saldo,
                estado,
                fecha
            ))
            return {"status": "success", "message": "Préstamo registrado correctamente", "id": next_id}
        except Exception as ex:
            return {"status": "error", "message": f"Error al registrar el préstamo: {ex}"}


    def get_all(self):
        try:
            query = f"SELECT * FROM {self.E.TABLE.value}"
            result = self.db.get_data_list(query, dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener préstamos: {ex}"}

    def get_by_id(self, id_prestamo: int):
        try:
            query = f"""
                SELECT * FROM {self.E.TABLE.value}
                WHERE {self.E.PRESTAMO_ID.value} = %s
            """
            result = self.db.get_data(query, (id_prestamo,), dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener el préstamo: {ex}"}

    def get_by_empleado(self, numero_nomina: int):
        try:
            query = f"""
                SELECT * FROM {self.E.TABLE.value}
                WHERE {self.E.PRESTAMO_NUMERO_NOMINA.value} = %s
            """
            result = self.db.get_data_list(query, (numero_nomina,), dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener préstamos del empleado: {ex}"}

    def update_by_id_prestamo(self, id_prestamo: int, campos: dict):
        try:
            if not campos:
                return {"status": "error", "message": "No se proporcionaron campos para actualizar"}

            campos_sql = ", ".join(f"{k.value} = %s" for k in campos.keys())
            valores = [v for v in campos.values()]

            query = f"""
                UPDATE {self.E.TABLE.value}
                SET {campos_sql}
                WHERE {self.E.PRESTAMO_ID.value} = %s
            """
            valores.append(id_prestamo)
            self.db.run_query(query, tuple(valores))
            return {"status": "success", "message": "Préstamo actualizado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al actualizar el préstamo: {ex}"}

    def delete_by_id_prestamo(self, id_prestamo: int):
        try:
            query = f"""
                DELETE FROM {self.E.TABLE.value}
                WHERE {self.E.PRESTAMO_ID.value} = %s
            """
            self.db.run_query(query, (id_prestamo,))
            return {"status": "success", "message": f"Préstamo ID {id_prestamo} eliminado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al eliminar el préstamo: {ex}"}

    def get_next_id_prestamo(self):
        query = "SELECT AUTO_INCREMENT FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'prestamos'"
        result = self.db.get_data(query, (self.db.database,), dictionary=True)
        return result.get("AUTO_INCREMENT", None)

    def get_total_prestamos_por_empleado(self, numero_nomina: int, fecha_pago: str) -> float:
        try:
            query = f"""
                SELECT COALESCE(SUM(pp.monto_pagado), 0) AS total
                FROM pagos_prestamo pp
                JOIN prestamos p ON pp.id_prestamo = p.id_prestamo
                WHERE p.estado = 'pagando'
                AND p.numero_nomina = %s
                AND pp.fecha_pago = %s
            """
            result = self.db.get_data(query, (numero_nomina, fecha_pago), dictionary=True)
            return float(result.get("total", 0.0)) if result else 0.0
        except Exception as ex:
            print(f"❌ Error al obtener préstamos por empleado: {ex}")
            return 0.0

    def get_prestamo_activo_por_empleado(self, numero_nomina: int):
        """
        Devuelve el préstamo activo (estado = 'pagando') de un empleado si existe.
        """
        try:
            query = f"""
                SELECT * FROM {self.E.TABLE.value}
                WHERE {self.E.PRESTAMO_NUMERO_NOMINA.value} = %s
                AND {self.E.PRESTAMO_ESTADO.value} = 'pagando'
                LIMIT 1
            """
            result = self.db.get_data(query, (numero_nomina,), dictionary=True)
            return result if result else None
        except Exception as ex:
            print(f"❌ Error al verificar préstamo activo: {ex}")
            return None

    def get_prestamos_por_empleado(self, numero_nomina: int) -> list:
        query = """
            SELECT id_prestamo, saldo_prestamo, estado
            FROM prestamos
            WHERE numero_nomina = %s
            ORDER BY fecha_solicitud DESC
        """
        return self.db.get_data_list(query, (numero_nomina,), dictionary=True)