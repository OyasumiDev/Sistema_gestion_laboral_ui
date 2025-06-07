from app.core.interfaces.database_mysql import DatabaseMysql
from app.core.enums.e_descuento_detalles_model import E_DESCUENTO_DETALLES


class DescuentoDetallesModel:
    def __init__(self):
        self.db = DatabaseMysql()
        self.E = E_DESCUENTO_DETALLES
        self._create_table()

    def _create_table(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self.E.TABLE.value} (
            id_detalle INT AUTO_INCREMENT PRIMARY KEY,
            id_pago INT NOT NULL,

            aplicado_imss BOOLEAN DEFAULT FALSE,
            monto_imss DECIMAL(10,2) DEFAULT 50.0,

            aplicado_transporte BOOLEAN DEFAULT FALSE,
            monto_transporte DECIMAL(10,2) DEFAULT 0.0,

            aplicado_comida BOOLEAN DEFAULT FALSE,
            monto_comida DECIMAL(10,2) DEFAULT 0.0,

            aplicado_extra BOOLEAN DEFAULT FALSE,
            descripcion_extra VARCHAR(100) DEFAULT '',
            monto_extra DECIMAL(10,2) DEFAULT 0.0,

            FOREIGN KEY (id_pago) REFERENCES pagos(id_pago) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        self.db.run_query(query)

    def guardar_detalles(self, id_pago: int, detalles: dict):
        """Guarda visualmente los detalles del modal, sobrescribiendo si ya existían."""
        self.eliminar_por_id_pago(id_pago)

        query = f"""
        INSERT INTO {self.E.TABLE.value} (
            id_pago,
            aplicado_imss, monto_imss,
            aplicado_transporte, monto_transporte,
            aplicado_comida, monto_comida,
            aplicado_extra, descripcion_extra, monto_extra
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            id_pago,
            detalles.get("aplicado_imss", False), detalles.get("monto_imss", 50.0),
            detalles.get("aplicado_transporte", False), detalles.get("monto_transporte", 0.0),
            detalles.get("aplicado_comida", False), detalles.get("monto_comida", 0.0),
            detalles.get("aplicado_extra", False), detalles.get("descripcion_extra", ""), detalles.get("monto_extra", 0.0)
        )
        self.db.run_query(query, values)

    def obtener_por_id_pago(self, id_pago: int) -> dict:
        """Obtiene los detalles visuales guardados para el modal, si existen."""
        query = f"SELECT * FROM {self.E.TABLE.value} WHERE id_pago = %s"
        result = self.db.get_data(query, (id_pago,), dictionary=True)
        return result or {}

    def eliminar_por_id_pago(self, id_pago: int):
        """Elimina los detalles visuales del modal para un pago específico."""
        query = f"DELETE FROM {self.E.TABLE.value} WHERE id_pago = %s"
        self.db.run_query(query, (id_pago,))

    def guardar_o_actualizar_detalles(self, id_pago: int, detalles: dict):
        """
        Guarda o reemplaza los detalles visuales del modal de descuentos.
        """
        self.eliminar_por_id_pago(id_pago)

        query = f"""
        INSERT INTO {self.E.TABLE.value} (
            id_pago,
            aplicado_imss, monto_imss,
            aplicado_transporte, monto_transporte,
            aplicado_comida, monto_comida,
            aplicado_extra, descripcion_extra, monto_extra
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            id_pago,
            detalles.get("aplicado_imss", False), detalles.get("monto_imss", 0.0),
            detalles.get("aplicado_transporte", False), detalles.get("monto_transporte", 0.0),
            detalles.get("aplicado_comida", False), detalles.get("monto_comida", 0.0),
            detalles.get("aplicado_extra", False), detalles.get("descripcion_extra", ""), detalles.get("monto_extra", 0.0)
        )
        self.db.run_query(query, values)
