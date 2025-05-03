from app.core.enums.e_loan_model import E_LOAN
from app.core.interfaces.database_mysql import DatabaseMysql

class LoanModel:
    """
    Modelo de préstamos.
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self._exists_table = self.check_table()

    def check_table(self) -> bool:
        """
        Verifica si la tabla de préstamos existe y la crea con la estructura correcta si no.
        """
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, E_LOAN.TABLE.value))
            # Ajuste aquí: `result` puede ser una tupla, no un dict
            count = result[0] if isinstance(result, tuple) else result.get("c", 0)
            if count == 0:
                print(f"⚠️ La tabla {E_LOAN.TABLE.value} no existe. Creando...")

                create_query = f"""
                CREATE TABLE IF NOT EXISTS {E_LOAN.TABLE.value} (
                    {E_LOAN.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {E_LOAN.NUMERO_NOMINA.value} SMALLINT UNSIGNED NOT NULL,
                    {E_LOAN.MONTO.value} DECIMAL(10,2) NOT NULL,
                    {E_LOAN.SALDO_PRESTAMO.value} DECIMAL(10,2) NOT NULL,
                    {E_LOAN.ESTADO.value} ENUM('aprobado','pendiente','rechazado') NOT NULL,
                    {E_LOAN.FECHA_SOLICITUD.value} DATE NOT NULL,
                    {E_LOAN.HISTORIAL_PAGOS.value} JSON,
                    {E_LOAN.DESCUENTO_SEMANAL.value} DECIMAL(10,2) DEFAULT 50,
                    {E_LOAN.TIPO_DESCUENTO.value} ENUM('monto fijo','porcentaje') NOT NULL DEFAULT 'monto fijo',
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY ({E_LOAN.NUMERO_NOMINA.value})
                        REFERENCES empleados(numero_nomina)
                        ON DELETE CASCADE
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
