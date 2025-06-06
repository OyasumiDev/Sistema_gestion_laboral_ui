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
            {self.E.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
            {self.E.ID_PAGO.value} INT UNIQUE NOT NULL,
            {self.E.APLICAR_IMSS.value} BOOLEAN DEFAULT FALSE,
            {self.E.MONTO_IMSS.value} DECIMAL(10,2) DEFAULT 0.00,
            {self.E.APLICAR_TRANSPORTE.value} BOOLEAN DEFAULT FALSE,
            {self.E.MONTO_TRANSPORTE.value} DECIMAL(10,2) DEFAULT 0.00,
            {self.E.APLICAR_COMIDA.value} BOOLEAN DEFAULT FALSE,
            {self.E.MONTO_COMIDA.value} DECIMAL(10,2) DEFAULT 0.00,
            {self.E.APLICAR_EXTRA.value} BOOLEAN DEFAULT FALSE,
            {self.E.MONTO_EXTRA.value} DECIMAL(10,2) DEFAULT 0.00,
            {self.E.DESCRIPCION_EXTRA.value} VARCHAR(100) DEFAULT '',
            FOREIGN KEY ({self.E.ID_PAGO.value}) REFERENCES pagos(id_pago) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        self.db.run_query(query)

    def guardar_detalles(self, id_pago: int, detalles: dict) -> dict:
        """
        Guarda o actualiza la configuración visual de descuentos para un pago específico.
        Si ya existe un registro, se actualiza; si no, se inserta uno nuevo.
        """
        try:
            # Verifica si ya existe
            existing = self.obtener_detalles(id_pago)
            if existing:
                set_clause = ", ".join(f"{k} = %s" for k in detalles.keys())
                query = f"""
                    UPDATE {self.E.TABLE.value}
                    SET {set_clause}
                    WHERE {self.E.ID_PAGO.value} = %s
                """
                valores = list(detalles.values()) + [id_pago]
            else:
                campos = [self.E.ID_PAGO.value] + list(detalles.keys())
                valores = [id_pago] + list(detalles.values())
                placeholders = ", ".join(["%s"] * len(valores))
                query = f"""
                    INSERT INTO {self.E.TABLE.value}
                    ({", ".join(campos)}) VALUES ({placeholders})
                """

            self.db.run_query(query, valores)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def obtener_detalles(self, id_pago: int) -> dict:
        """
        Devuelve los detalles visuales guardados para un pago.
        Si no existen, retorna un diccionario vacío.
        """
        try:
            query = f"""
                SELECT * FROM {self.E.TABLE.value}
                WHERE {self.E.ID_PAGO.value} = %s
            """
            result = self.db.get_data(query, (id_pago,), dictionary=True)
            return result or {}
        except Exception as e:
            print(f"❌ Error al obtener detalles del pago {id_pago}: {e}")
            return {}

    def eliminar_por_id_pago(self, id_pago: int) -> None:
        """
        Elimina los detalles visuales existentes de un pago.
        """
        query = f"DELETE FROM {self.E.TABLE.value} WHERE {self.E.ID_PAGO.value} = %s"
        self.db.run_query(query, (id_pago,))

    def tiene_datos_para_pago(self, id_pago: int) -> bool:
        """
        Verifica si hay detalles relevantes guardados para un pago específico.
        Retorna True solo si hay datos distintos a los predeterminados.
        """
        detalles = self.obtener_detalles(id_pago)
        if not detalles:
            return False

        return any([
            detalles.get("aplicar_imss", False),
            detalles.get("aplicar_transporte", False),
            detalles.get("aplicar_comida", False),
            detalles.get("aplicar_extra", False),
            detalles.get("monto_imss", 0.0) > 0,
            detalles.get("monto_transporte", 0.0) > 0,
            detalles.get("monto_comida", 0.0) > 0,
            detalles.get("monto_extra", 0.0) > 0,
            detalles.get("descripcion_extra", "").strip() != ""
        ])
