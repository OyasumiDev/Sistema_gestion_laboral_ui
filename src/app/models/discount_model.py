from app.core.enums.e_discount_model import E_DISCOUNT
from app.core.interfaces.database_mysql import DatabaseMysql

class DiscountModel:
    def __init__(self):
        self.db = DatabaseMysql()
        self._create_table()

    def _create_table(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {E_DISCOUNT.TABLE.value} (
            {E_DISCOUNT.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
            {E_DISCOUNT.ID_PAGO.value} INT NOT NULL,
            {E_DISCOUNT.DESCRIPCION.value} VARCHAR(100) NOT NULL,
            {E_DISCOUNT.MONTO.value} DECIMAL(10,2) NOT NULL,
            FOREIGN KEY ({E_DISCOUNT.ID_PAGO.value}) REFERENCES pagos(id_pago) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        self.db.run_query(query)

    def agregar_descuento(self, id_pago: int, descripcion: str, monto: float) -> dict:
        try:
            query = f"""
            INSERT INTO {E_DISCOUNT.TABLE.value} (
                {E_DISCOUNT.ID_PAGO.value},
                {E_DISCOUNT.DESCRIPCION.value},
                {E_DISCOUNT.MONTO.value}
            ) VALUES (%s, %s, %s)
            """
            self.db.run_query(query, (id_pago, descripcion, monto))
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def agregar_descuentos_opcionales(
        self,
        id_pago: int,
        aplicar_imss=True,
        aplicar_transporte=True,
        aplicar_comida=True,
        estado_comida="media",
        descuento_extra=None,
        descripcion_extra=None
    ) -> dict:
        try:
            if aplicar_imss:
                self.agregar_descuento(id_pago, "retenciones_imss", 50.00)
            if aplicar_transporte:
                self.agregar_descuento(id_pago, "transporte", 50.00)
            if aplicar_comida:
                monto_comida = 100.00 if estado_comida == "completa" else 50.00
                self.agregar_descuento(id_pago, "comida", monto_comida)
            if descuento_extra and descripcion_extra:
                self.agregar_descuento(id_pago, descripcion_extra, float(descuento_extra))
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_by_pago(self, id_pago: int) -> list:
        try:
            query = f"""
            SELECT * FROM {E_DISCOUNT.TABLE.value}
            WHERE {E_DISCOUNT.ID_PAGO.value} = %s
            ORDER BY {E_DISCOUNT.ID.value} ASC
            """
            return self.db.get_data_list(query, (id_pago,), dictionary=True)
        except Exception as e:
            print("❌ Error al obtener descuentos:", e)
            return []

    def get_by_numero_nomina(self, numero_nomina: int) -> list:
        try:
            query = f"""
            SELECT d.* FROM {E_DISCOUNT.TABLE.value} d
            JOIN pagos p ON d.{E_DISCOUNT.ID_PAGO.value} = p.id_pago
            WHERE p.numero_nomina = %s
            ORDER BY d.{E_DISCOUNT.ID.value} ASC
            """
            return self.db.get_data_list(query, (numero_nomina,), dictionary=True)
        except Exception as e:
            print("❌ Error al obtener descuentos por empleado:", e)
            return []

    def get_all(self) -> list:
        try:
            query = f"""
            SELECT d.*, p.numero_nomina FROM {E_DISCOUNT.TABLE.value} d
            JOIN pagos p ON d.{E_DISCOUNT.ID_PAGO.value} = p.id_pago
            ORDER BY d.{E_DISCOUNT.ID.value} ASC
            """
            return self.db.get_data_list(query, (), dictionary=True)
        except Exception as e:
            print("❌ Error al obtener todos los descuentos:", e)
            return []

    def update(self, id_descuento: int, descripcion: str, monto: float) -> dict:
        try:
            query = f"""
            UPDATE {E_DISCOUNT.TABLE.value}
            SET {E_DISCOUNT.DESCRIPCION.value} = %s,
                {E_DISCOUNT.MONTO.value} = %s
            WHERE {E_DISCOUNT.ID.value} = %s
            """
            self.db.run_query(query, (descripcion, monto, id_descuento))
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def delete(self, id_descuento: int) -> dict:
        try:
            query = f"""
            DELETE FROM {E_DISCOUNT.TABLE.value}
            WHERE {E_DISCOUNT.ID.value} = %s
            """
            self.db.run_query(query, (id_descuento,))
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_total_descuentos_por_pago(self, id_pago: int) -> float:
        try:
            query = f"SELECT SUM({E_DISCOUNT.MONTO.value}) AS total FROM {E_DISCOUNT.TABLE.value} WHERE {E_DISCOUNT.ID_PAGO.value} = %s"
            result = self.db.get_data(query, (id_pago,), dictionary=True)
            return result.get("total", 0.0) if result else 0.0
        except Exception as e:
            print(f"❌ Error al calcular total de descuentos: {e}")
            return 0.0
