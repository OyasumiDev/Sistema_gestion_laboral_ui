from app.core.enums.e_descuento_detalles_model import E_DESCUENTO_DETALLES as E
from app.core.interfaces.database_mysql import DatabaseMysql


class DescuentoDetallesModel:
    def __init__(self):
        self.db = DatabaseMysql()
        self._create_table()

    def _create_table(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {E.TABLE.value} (
            {E.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
            {E.ID_PAGO.value} INT NOT NULL,

            {E.APLICADO_IMSS.value} BOOLEAN DEFAULT FALSE,
            {E.MONTO_IMSS.value} DECIMAL(10,2) DEFAULT 50.0,

            {E.APLICADO_TRANSPORTE.value} BOOLEAN DEFAULT FALSE,
            {E.MONTO_TRANSPORTE.value} DECIMAL(10,2) DEFAULT 0.0,

            {E.APLICADO_COMIDA.value} BOOLEAN DEFAULT FALSE,
            {E.MONTO_COMIDA.value} DECIMAL(10,2) DEFAULT 0.0,

            {E.APLICADO_EXTRA.value} BOOLEAN DEFAULT FALSE,
            {E.DESCRIPCION_EXTRA.value} VARCHAR(100) DEFAULT '',
            {E.MONTO_EXTRA.value} DECIMAL(10,2) DEFAULT 0.0,

            FOREIGN KEY ({E.ID_PAGO.value}) REFERENCES pagos({E.ID_PAGO.value}) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        self.db.run_query(query)

    def guardar_detalles(self, id_pago: int, detalles: dict):
        self.eliminar_por_id_pago(id_pago)
        query = f"""
        INSERT INTO {E.TABLE.value} (
            {E.ID_PAGO.value},
            {E.APLICADO_IMSS.value}, {E.MONTO_IMSS.value},
            {E.APLICADO_TRANSPORTE.value}, {E.MONTO_TRANSPORTE.value},
            {E.APLICADO_COMIDA.value}, {E.MONTO_COMIDA.value},
            {E.APLICADO_EXTRA.value}, {E.DESCRIPCION_EXTRA.value}, {E.MONTO_EXTRA.value}
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            id_pago,
            detalles.get(E.APLICADO_IMSS.value, False), detalles.get(E.MONTO_IMSS.value, 50.0),
            detalles.get(E.APLICADO_TRANSPORTE.value, False), detalles.get(E.MONTO_TRANSPORTE.value, 0.0),
            detalles.get(E.APLICADO_COMIDA.value, False), detalles.get(E.MONTO_COMIDA.value, 0.0),
            detalles.get(E.APLICADO_EXTRA.value, False), detalles.get(E.DESCRIPCION_EXTRA.value, ""), detalles.get(E.MONTO_EXTRA.value, 0.0)
        )
        self.db.run_query(query, values)

    def obtener_por_id_pago(self, id_pago: int) -> dict:
        query = f"SELECT * FROM {E.TABLE.value} WHERE {E.ID_PAGO.value} = %s"
        return self.db.get_data(query, (id_pago,), dictionary=True) or {}

    def eliminar_por_id_pago(self, id_pago: int):
        query = f"DELETE FROM {E.TABLE.value} WHERE {E.ID_PAGO.value} = %s"
        self.db.run_query(query, (id_pago,))

    def guardar_o_actualizar_detalles(self, id_pago: int, detalles: dict):
        self.guardar_detalles(id_pago, detalles)
