from app.core.interfaces.database_mysql import DatabaseMysql
from app.core.enums.e_prestamo_detalles_model import E_DETALLES_PRESTAMO

class PrestamoDetallesModel:
    def __init__(self):
        self.db = DatabaseMysql()
        self.E = E_DETALLES_PRESTAMO
        self._crear_tabla()

    def _crear_tabla(self):
        query = f"""
            CREATE TABLE IF NOT EXISTS {self.E.TABLE.value} (
                {self.E.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                {self.E.ID_PAGO.value} INT NOT NULL,
                {self.E.ID_PAGO_PRESTAMO.value} INT NOT NULL,
                {self.E.MONTO_PAGADO.value} DECIMAL(10,2) NOT NULL,
                {self.E.INTERES_APLICADO.value} DECIMAL(5,2) NOT NULL,
                {self.E.FECHA_PAGO.value} DATE NOT NULL,
                {self.E.DESDE_NOMINA.value} BOOLEAN DEFAULT FALSE,
                {self.E.OBSERVACIONES.value} TEXT,
                UNIQUE KEY uk_pago_prestamo ({self.E.ID_PAGO.value}, {self.E.ID_PAGO_PRESTAMO.value}),
                FOREIGN KEY ({self.E.ID_PAGO.value}) REFERENCES pagos(id_pago) ON DELETE CASCADE,
                FOREIGN KEY ({self.E.ID_PAGO_PRESTAMO.value}) REFERENCES pagos_prestamo(id_pago_prestamo) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        self.db.run_query(query)

    def guardar_detalle(self, id_pago, id_pago_prestamo, monto_pagado, interes_aplicado, fecha_pago, desde_nomina=False, observaciones=""):
        try:
            self.eliminar_detalle(id_pago, id_pago_prestamo)
            query = f"""
                INSERT INTO {self.E.TABLE.value} (
                    {self.E.ID_PAGO.value},
                    {self.E.ID_PAGO_PRESTAMO.value},
                    {self.E.MONTO_PAGADO.value},
                    {self.E.INTERES_APLICADO.value},
                    {self.E.FECHA_PAGO.value},
                    {self.E.DESDE_NOMINA.value},
                    {self.E.OBSERVACIONES.value}
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            valores = (id_pago, id_pago_prestamo, monto_pagado, interes_aplicado, fecha_pago, desde_nomina, observaciones)
            self.db.run_query(query, valores)
            return {"status": "success", "message": "Detalle de préstamo guardado correctamente."}
        except Exception as ex:
            return {"status": "error", "message": f"Error al guardar el detalle: {ex}"}

    def obtener_detalle(self, id_pago, id_pago_prestamo):
        try:
            query = f"""
                SELECT * FROM {self.E.TABLE.value}
                WHERE {self.E.ID_PAGO.value} = %s AND {self.E.ID_PAGO_PRESTAMO.value} = %s
            """
            return self.db.get_data(query, (id_pago, id_pago_prestamo), dictionary=True) or {}
        except Exception as ex:
            print(f"❌ Error al obtener detalle: {ex}")
            return {}

    def eliminar_detalle(self, id_pago, id_pago_prestamo):
        try:
            query = f"""
                DELETE FROM {self.E.TABLE.value}
                WHERE {self.E.ID_PAGO.value} = %s AND {self.E.ID_PAGO_PRESTAMO.value} = %s
            """
            self.db.run_query(query, (id_pago, id_pago_prestamo))
        except Exception as ex:
            print(f"❌ Error al eliminar detalle específico: {ex}")

    def eliminar_por_pago(self, id_pago: int):
        try:
            query = f"DELETE FROM {self.E.TABLE.value} WHERE {self.E.ID_PAGO.value} = %s"
            self.db.run_query(query, (id_pago,))
        except Exception as ex:
            print(f"❌ Error al eliminar detalles por id_pago: {ex}")

    def listar_por_pago(self, id_pago: int):
        try:
            query = f"""
                SELECT * FROM {self.E.TABLE.value}
                WHERE {self.E.ID_PAGO.value} = %s
            """
            return self.db.get_data_list(query, (id_pago,), dictionary=True)
        except Exception as ex:
            print(f"❌ Error al listar detalles de préstamo: {ex}")
            return []
