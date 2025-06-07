from app.core.interfaces.database_mysql import DatabaseMysql
from app.core.enums.e_detalles_pagos_prestamo_model import E_DETALLES_PAGOS_PRESTAMO as E

class DetallesPagosPrestamoModel:
    def __init__(self):
        self.db = DatabaseMysql()
        self.E = E
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
                        {self.E.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                        {self.E.ID_PAGO.value} INT NOT NULL,
                        {self.E.ID_PRESTAMO.value} INT NOT NULL,
                        {self.E.MONTO_GUARDADO.value} DECIMAL(10,2),
                        {self.E.INTERES_GUARDADO.value} INT,
                        {self.E.OBSERVACIONES.value} TEXT,
                        {self.E.FECHA.value} DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE KEY uk_pago_prestamo ({self.E.ID_PAGO.value}, {self.E.ID_PRESTAMO.value}),
                        FOREIGN KEY ({self.E.ID_PAGO.value}) REFERENCES pagos(id_pago) ON DELETE CASCADE,
                        FOREIGN KEY ({self.E.ID_PRESTAMO.value}) REFERENCES prestamos(id_prestamo) ON DELETE CASCADE
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

    def upsert_detalle(self, id_pago: int, id_prestamo: int, monto: float, interes: int, observaciones: str):
        try:
            query = f"""
                INSERT INTO {self.E.TABLE.value} (
                    {self.E.ID_PAGO.value},
                    {self.E.ID_PRESTAMO.value},
                    {self.E.MONTO_GUARDADO.value},
                    {self.E.INTERES_GUARDADO.value},
                    {self.E.OBSERVACIONES.value}
                ) VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    {self.E.MONTO_GUARDADO.value} = VALUES({self.E.MONTO_GUARDADO.value}),
                    {self.E.INTERES_GUARDADO.value} = VALUES({self.E.INTERES_GUARDADO.value}),
                    {self.E.OBSERVACIONES.value} = VALUES({self.E.OBSERVACIONES.value}),
                    {self.E.FECHA.value} = CURRENT_TIMESTAMP
            """
            self.db.run_query(query, (id_pago, id_prestamo, monto, interes, observaciones))
            return {"status": "success", "message": "Guardado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al guardar detalles: {ex}"}

    def get_detalle(self, id_pago: int, id_prestamo: int) -> dict:
        try:
            query = f"""
                SELECT * FROM {self.E.TABLE.value}
                WHERE {self.E.ID_PAGO.value} = %s AND {self.E.ID_PRESTAMO.value} = %s
            """
            return self.db.get_data(query, (id_pago, id_prestamo), dictionary=True)
        except Exception as ex:
            print(f"❌ Error al obtener detalle: {ex}")
            return {}

    def delete_detalle(self, id_pago: int, id_prestamo: int):
        try:
            query = f"""
                DELETE FROM {self.E.TABLE.value}
                WHERE {self.E.ID_PAGO.value} = %s AND {self.E.ID_PRESTAMO.value} = %s
            """
            self.db.run_query(query, (id_pago, id_prestamo))
            return {"status": "success", "message": "Detalle eliminado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al eliminar: {ex}"}
