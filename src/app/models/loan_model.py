from app.core.enums.e_loan_model import E_LOAN
from app.core.interfaces.database_mysql import DatabaseMysql

class LoanModel:
    """
    Modelo de préstamos: permite registrar múltiples préstamos por empleado
    y consultarlos por empleado o globalmente.
    """

    def __init__(self):
        self.db = DatabaseMysql()
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
            result = self.db.get_data(query, (self.db.database, E_LOAN.TABLE.value))
            count = result[0] if isinstance(result, tuple) else result.get("c", 0)

            if count == 0:
                print(f"⚠️ La tabla {E_LOAN.TABLE.value} no existe. Creando...")

                create_query = f"""
                CREATE TABLE {E_LOAN.TABLE.value} (
                    {E_LOAN.PRESTAMO_ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {E_LOAN.PRESTAMO_NUMERO_NOMINA.value} SMALLINT UNSIGNED NOT NULL,
                    {E_LOAN.PRESTAMO_MONTO.value} DECIMAL(10,2) NOT NULL,
                    {E_LOAN.PRESTAMO_SALDO.value} DECIMAL(10,2) NOT NULL,
                    {E_LOAN.PRESTAMO_ESTADO.value} ENUM('aprobado','pendiente','rechazado') NOT NULL,
                    {E_LOAN.PRESTAMO_FECHA_SOLICITUD.value} DATE NOT NULL,
                    {E_LOAN.PRESTAMO_FECHA_CREACION.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    {E_LOAN.PRESTAMO_FECHA_MODIFICACION.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY ({E_LOAN.PRESTAMO_NUMERO_NOMINA.value}) REFERENCES empleados(numero_nomina) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {E_LOAN.TABLE.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {E_LOAN.TABLE.value} ya existe.")
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {E_LOAN.TABLE.value}: {ex}")
            return False

    def add(self, numero_nomina, monto, saldo_prestamo, estado, fecha_solicitud):
        """
        Registra un nuevo préstamo.
        """
        try:
            query = f"""
                INSERT INTO {E_LOAN.TABLE.value} (
                    {E_LOAN.PRESTAMO_NUMERO_NOMINA.value},
                    {E_LOAN.PRESTAMO_MONTO.value},
                    {E_LOAN.PRESTAMO_SALDO.value},
                    {E_LOAN.PRESTAMO_ESTADO.value},
                    {E_LOAN.PRESTAMO_FECHA_SOLICITUD.value}
                ) VALUES (%s, %s, %s, %s, %s)
            """
            self.db.run_query(query, (
                numero_nomina,
                monto,
                saldo_prestamo,
                estado,
                fecha_solicitud
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
                WHERE {E_LOAN.PRESTAMO_ID.value} = %s
            """
            result = self.db.get_data(query, (id_prestamo,))
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener el préstamo: {ex}"}

    def get_by_empleado(self, numero_nomina: int):
        """
        Retorna todos los préstamos asociados a un número de nómina.
        """
        try:
            query = f"""
                SELECT * FROM {E_LOAN.TABLE.value}
                WHERE {E_LOAN.PRESTAMO_NUMERO_NOMINA.value} = %s
            """
            result = self.db.get_data_list(query, (numero_nomina,))
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener préstamos del empleado: {ex}"}

    def update_by_id_prestamo(self, id_prestamo: int, campos: dict):
        """
        Actualiza cualquier campo del préstamo especificado por su ID.
        """
        try:
            if not campos:
                return {"status": "error", "message": "No se proporcionaron campos para actualizar"}

            campos_sql = ", ".join(f"{k.value} = %s" for k in campos.keys())
            valores = [v for v in campos.values()]

            query = f"""
                UPDATE {E_LOAN.TABLE.value}
                SET {campos_sql}
                WHERE {E_LOAN.PRESTAMO_ID.value} = %s
            """
            valores.append(id_prestamo)

            self.db.run_query(query, tuple(valores))
            return {"status": "success", "message": "Préstamo actualizado correctamente"}

        except Exception as ex:
            return {"status": "error", "message": f"Error al actualizar el préstamo: {ex}"}

    def delete_by_id_prestamo(self, id_prestamo: int):
        """
        Elimina un préstamo por su ID.
        """
        try:
            query = f"""
                DELETE FROM {E_LOAN.TABLE.value}
                WHERE {E_LOAN.PRESTAMO_ID.value} = %s
            """
            self.db.run_query(query, (id_prestamo,))
            return {"status": "success", "message": f"Préstamo ID {id_prestamo} eliminado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al eliminar el préstamo: {ex}"}
