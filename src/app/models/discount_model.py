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
            numero_nomina SMALLINT UNSIGNED NOT NULL,
            {E_DISCOUNT.ID_PAGO.value} INT DEFAULT NULL,
            {E_DISCOUNT.DESCRIPCION.value} VARCHAR(100) NOT NULL,
            {E_DISCOUNT.MONTO.value} DECIMAL(10,2) NOT NULL,
            fecha_aplicacion DATE NOT NULL DEFAULT (CURRENT_DATE),
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE,
            FOREIGN KEY ({E_DISCOUNT.ID_PAGO.value}) REFERENCES pagos(id_pago) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        self.db.run_query(query)


    def agregar_descuento(self, numero_nomina: int, descripcion: str, monto: float, id_pago: int = None) -> dict:
        try:
            query = f"""
            INSERT INTO {E_DISCOUNT.TABLE.value} (
                numero_nomina,
                {E_DISCOUNT.ID_PAGO.value},
                {E_DISCOUNT.DESCRIPCION.value},
                {E_DISCOUNT.MONTO.value}
            ) VALUES (%s, %s, %s, %s)
            """
            self.db.run_query(query, (numero_nomina, id_pago, descripcion, monto))
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def agregar_descuentos_opcionales(
        self,
        numero_nomina: int,
        id_pago: int = None,
        aplicar_imss=True,
        aplicar_transporte=True,
        aplicar_comida=True,
        estado_comida="media",
        descuento_extra=None,
        descripcion_extra=None
    ) -> dict:
        try:
            if aplicar_imss:
                self.agregar_descuento(numero_nomina, "retenciones_imss", 50.00, id_pago)
            if aplicar_transporte:
                self.agregar_descuento(numero_nomina, "transporte", 50.00, id_pago)
            if aplicar_comida:
                monto_comida = 100.00 if estado_comida == "completa" else 50.00
                self.agregar_descuento(numero_nomina, "comida", monto_comida, id_pago)
            if descuento_extra and descripcion_extra:
                self.agregar_descuento(numero_nomina, descripcion_extra, float(descuento_extra), id_pago)
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
            SELECT * FROM {E_DISCOUNT.TABLE.value}
            WHERE numero_nomina = %s
            ORDER BY {E_DISCOUNT.ID.value} ASC
            """
            return self.db.get_data_list(query, (numero_nomina,), dictionary=True)
        except Exception as e:
            print("❌ Error al obtener descuentos por empleado:", e)
            return []

    def get_all(self) -> list:
        try:
            query = f"SELECT * FROM {E_DISCOUNT.TABLE.value} ORDER BY {E_DISCOUNT.ID.value} ASC"
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
