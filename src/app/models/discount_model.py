from datetime import date
from app.core.enums.e_discount_model import E_DISCOUNT
from app.core.enums.e_employes_model import E_EMPLOYE
from app.core.enums.e_payment_model import E_PAYMENT
from app.core.interfaces.database_mysql import DatabaseMysql

VALOR_IMSS_POR_DEFECTO = 50.0


class DiscountModel:
    """
    Modelo para la gestión de la tabla de descuentos.
    Relaciona empleados y pagos, y permite registrar descuentos diversos.
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self.E = E_DISCOUNT
        self.EE = E_EMPLOYE
        self.EP = E_PAYMENT
        self._create_table()

    def _create_table(self):
        """
        Crea la tabla 'descuentos' si no existe, utilizando claves foráneas a empleados y pagos.
        """
        query = f"""
        CREATE TABLE IF NOT EXISTS {self.E.TABLE.value} (
            {self.E.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
            {self.EE.NUMERO_NOMINA.value} SMALLINT UNSIGNED NOT NULL,
            {self.E.ID_PAGO.value} INT DEFAULT NULL,
            {self.E.TIPO.value} VARCHAR(50) NOT NULL,
            {self.E.DESCRIPCION.value} VARCHAR(100) DEFAULT NULL,
            {self.E.MONTO.value} DECIMAL(10,2) NOT NULL,
            {self.E.FECHA_APLICACION.value} DATE NOT NULL DEFAULT (CURRENT_DATE),
            {self.E.FECHA_CREACION.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY ({self.EE.NUMERO_NOMINA.value})
                REFERENCES {self.EE.TABLE.value}({self.EE.NUMERO_NOMINA.value}) ON DELETE CASCADE,
            FOREIGN KEY ({self.E.ID_PAGO.value})
                REFERENCES {self.EP.TABLE.value}({self.EP.ID.value}) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        self.db.run_query(query)


    # --------------------------------------------------------
    # Inserción
    # --------------------------------------------------------

    def agregar_descuento(self, numero_nomina: int, tipo: str, descripcion: str, monto: float, id_pago: int = None) -> dict:
        try:
            if monto < 0:
                return {"status": "error", "message": "El monto no puede ser negativo"}

            query = f"""
            INSERT INTO {self.E.TABLE.value} (
                numero_nomina, {self.E.ID_PAGO.value}, {self.E.TIPO.value},
                {self.E.DESCRIPCION.value}, {self.E.MONTO.value}
            ) VALUES (%s, %s, %s, %s, %s)
            """
            self.db.run_query(query, (numero_nomina, id_pago, tipo, descripcion, monto))
            return {"status": "success"}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def guardar_descuentos(
        self,
        id_pago: int,
        numero_nomina: int,
        descuentos: list[dict]
    ) -> dict:
        """
        Reemplaza todos los descuentos de un pago por una nueva lista.

        Cada elemento debe tener:
        - tipo (str)
        - descripcion (str)
        - monto (float)
        """
        try:
            self.eliminar_por_id_pago(id_pago)

            for d in descuentos:
                tipo = d.get("tipo")
                descripcion = d.get("descripcion", "")
                monto = float(d.get("monto", 0))

                if tipo and monto >= 0:
                    self.agregar_descuento(numero_nomina, tipo, descripcion, monto, id_pago)

            return {"status": "success"}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    # --------------------------------------------------------
    # Eliminación
    # --------------------------------------------------------

    def eliminar_por_id_pago(self, id_pago: int) -> dict:
        try:
            query = f"DELETE FROM {self.E.TABLE.value} WHERE {self.E.ID_PAGO.value} = %s"
            self.db.run_query(query, (id_pago,))
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # --------------------------------------------------------
    # Consulta
    # --------------------------------------------------------

    def get_descuentos_por_pago(self, id_pago: int) -> list:
        try:
            query = f"""
            SELECT {self.E.TIPO.value}, {self.E.DESCRIPCION.value}, {self.E.MONTO.value}
            FROM {self.E.TABLE.value}
            WHERE {self.E.ID_PAGO.value} = %s
            """
            return self.db.get_data_list(query, (id_pago,), dictionary=True)
        except Exception as e:
            print(f"❌ Error al obtener descuentos del pago {id_pago}: {e}")
            return []

    def get_total_descuentos_por_pago(self, id_pago: int) -> float:
        try:
            query = f"""
            SELECT SUM({self.E.MONTO.value}) AS total
            FROM {self.E.TABLE.value}
            WHERE {self.E.ID_PAGO.value} = %s
            """
            result = self.db.get_data(query, (id_pago,), dictionary=True)
            return float(result["total"]) if result and result.get("total") else 0.0
        except Exception as e:
            print(f"❌ Error al obtener total de descuentos para el pago {id_pago}: {e}")
            return 0.0

    def resumen_por_pago(self, id_pago: int) -> dict:
        try:
            descuentos = self.get_descuentos_por_pago(id_pago)
            total = sum(float(d[self.E.MONTO.value]) for d in descuentos)
            return {
                "status": "success",
                "descuentos": descuentos,
                "total": round(total, 2)
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def agregar_descuentos_opcionales(self, id_pago: int, numero_nomina: int) -> dict:
        """
        Este método se conserva por compatibilidad, y solo agrega el descuento IMSS por defecto (50.00).
        Es usado en la generación de pagos cuando aún no se aplican descuentos desde el modal.
        """
        try:
            return self.guardar_descuentos(
                id_pago=id_pago,
                numero_nomina=numero_nomina,
                descuentos=[
                    {
                        "tipo": "retenciones_imss",
                        "descripcion": "Cuota IMSS",
                        "monto": VALOR_IMSS_POR_DEFECTO
                    }
                ]
            )
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_by_pago(self, id_pago: int) -> list[dict]:
        """
        Obtiene todos los descuentos aplicados a un pago específico.
        """
        try:
            query = f"""
                SELECT 
                    {self.E.TIPO.value}, 
                    {self.E.DESCRIPCION.value}, 
                    {self.E.MONTO.value}
                FROM {self.E.TABLE.value}
                WHERE {self.E.ID_PAGO.value} = %s
            """
            return self.db.get_data_list(query, (id_pago,), dictionary=True)
        except Exception as e:
            print(f"❌ Error al obtener descuentos del pago {id_pago}: {e}")
            return []
