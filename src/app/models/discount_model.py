from app.core.enums.e_discount_model import E_DISCOUNT
from app.core.interfaces.database_mysql import DatabaseMysql

VALORES_DESC_POR_DEFECTO = {
    "retenciones_imss": 50.0,
    "transporte": 50.0,
    "comida_completa": 100.0,
    "comida_media": 50.0,
}


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
            {E_DISCOUNT.TIPO.value} VARCHAR(50) NOT NULL,
            {E_DISCOUNT.DESCRIPCION.value} VARCHAR(100) DEFAULT NULL,
            {E_DISCOUNT.MONTO.value} DECIMAL(10,2) NOT NULL,
            {E_DISCOUNT.FECHA_APLICACION.value} DATE NOT NULL DEFAULT (CURRENT_DATE),
            {E_DISCOUNT.FECHA_CREACION.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE,
            FOREIGN KEY ({E_DISCOUNT.ID_PAGO.value}) REFERENCES pagos(id_pago) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        self.db.run_query(query)

    def agregar_descuento(self, numero_nomina: int, tipo: str, descripcion: str, monto: float, id_pago: int = None) -> dict:
        try:
            if monto < 0:
                return {"status": "error", "message": "El monto no puede ser negativo"}
            query = f"""
            INSERT INTO {E_DISCOUNT.TABLE.value} (
                numero_nomina, {E_DISCOUNT.ID_PAGO.value}, {E_DISCOUNT.TIPO.value},
                {E_DISCOUNT.DESCRIPCION.value}, {E_DISCOUNT.MONTO.value}
            ) VALUES (%s, %s, %s, %s, %s)
            """
            self.db.run_query(query, (numero_nomina, id_pago, tipo, descripcion, monto))
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
        descripcion_extra=None,
        montos_personalizados: dict = None
    ) -> dict:
        try:
            montos = montos_personalizados or {}
            descuentos = []

            if aplicar_imss:
                monto = montos.get("retenciones_imss", VALORES_DESC_POR_DEFECTO["retenciones_imss"])
                descuentos.append(("retenciones_imss", "Cuota IMSS", monto))

            if aplicar_transporte:
                monto = montos.get("transporte", VALORES_DESC_POR_DEFECTO["transporte"])
                descuentos.append(("transporte", "Pasaje diario", monto))

            if aplicar_comida:
                clave = f"comida_{estado_comida}"
                monto = montos.get("comida", VALORES_DESC_POR_DEFECTO.get(clave, 50.0))
                descripcion = f"Comida {estado_comida}"
                descuentos.append(("comida", descripcion, monto))

            if descuento_extra and descripcion_extra:
                monto = float(montos.get("descuento_extra", descuento_extra))
                descuentos.append(("descuento_extra", descripcion_extra, monto))

            for tipo, descripcion, monto in descuentos:
                self.agregar_descuento(numero_nomina, tipo, descripcion, monto, id_pago)

            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def eliminar_por_id_pago(self, id_pago: int) -> dict:
        try:
            query = f"DELETE FROM {E_DISCOUNT.TABLE.value} WHERE {E_DISCOUNT.ID_PAGO.value} = %s"
            self.db.run_query(query, (id_pago,))
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def guardar_descuentos_editables(
        self,
        id_pago: int,
        aplicar_imss: bool,
        aplicar_transporte: bool,
        aplicar_comida: bool,
        estado_comida: str,
        descuento_extra: float = None,
        descripcion_extra: str = None,
        montos_personalizados: dict = None,
        numero_nomina: int = None
    ) -> dict:
        try:
            if not numero_nomina:
                return {"status": "error", "message": "Se requiere el número de nómina"}

            resultado = self.eliminar_por_id_pago(id_pago)
            if resultado["status"] != "success":
                return resultado

            return self.agregar_descuentos_opcionales(
                numero_nomina=numero_nomina,
                id_pago=id_pago,
                aplicar_imss=aplicar_imss,
                aplicar_transporte=aplicar_transporte,
                aplicar_comida=aplicar_comida,
                estado_comida=estado_comida,
                descuento_extra=descuento_extra,
                descripcion_extra=descripcion_extra,
                montos_personalizados=montos_personalizados
            )
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_descuentos_por_pago(self, id_pago: int) -> list:
        try:
            query = f"""
            SELECT {E_DISCOUNT.TIPO.value}, {E_DISCOUNT.DESCRIPCION.value}, {E_DISCOUNT.MONTO.value}
            FROM {E_DISCOUNT.TABLE.value}
            WHERE {E_DISCOUNT.ID_PAGO.value} = %s
            """
            return self.db.get_data_list(query, (id_pago,), dictionary=True)
        except Exception as e:
            print(f"❌ Error al obtener descuentos del pago {id_pago}: {e}")
            return []

    def get_by_pago(self, id_pago: int) -> list:
        return self.get_descuentos_por_pago(id_pago)

    def get_total_descuentos_por_pago(self, id_pago: int) -> float:
        try:
            query = f"""
            SELECT SUM({E_DISCOUNT.MONTO.value}) AS total
            FROM {E_DISCOUNT.TABLE.value}
            WHERE {E_DISCOUNT.ID_PAGO.value} = %s
            """
            result = self.db.get_data(query, (id_pago,), dictionary=True)
            return float(result["total"]) if result and result["total"] else 0.0
        except Exception as e:
            print(f"❌ Error al obtener total de descuentos para el pago {id_pago}: {e}")
            return 0.0

    def resumen_por_pago(self, id_pago: int) -> dict:
        try:
            descuentos = self.get_descuentos_por_pago(id_pago)
            total = sum(float(d[E_DISCOUNT.MONTO.value]) for d in descuentos)
            return {
                "status": "success",
                "descuentos": descuentos,
                "total": round(total, 2)
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def resumen_descuentos_por_empleado(self, numero_nomina: int) -> dict:
        try:
            query = f"""
            SELECT {E_DISCOUNT.TIPO.value}, {E_DISCOUNT.DESCRIPCION.value}, {E_DISCOUNT.MONTO.value}
            FROM {E_DISCOUNT.TABLE.value}
            WHERE numero_nomina = %s
            """
            descuentos = self.db.get_data_list(query, (numero_nomina,), dictionary=True)
            if not descuentos:
                return {"status": "success", "resumen": "No hay descuentos registrados para este empleado"}

            resumen_total = [
                f"{d[E_DISCOUNT.TIPO.value].replace('_', ' ').capitalize()}: ${d[E_DISCOUNT.MONTO.value]:.2f} ({d[E_DISCOUNT.DESCRIPCION.value]})"
                for d in descuentos
            ]
            total = sum(float(d[E_DISCOUNT.MONTO.value]) for d in descuentos)

            return {"status": "success", "resumen": resumen_total, "total": round(total, 2)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def resumen_descuentos_global(self) -> dict:
        try:
            query = f"""
            SELECT numero_nomina, {E_DISCOUNT.TIPO.value}, SUM({E_DISCOUNT.MONTO.value}) AS total
            FROM {E_DISCOUNT.TABLE.value}
            GROUP BY numero_nomina, {E_DISCOUNT.TIPO.value}
            ORDER BY numero_nomina
            """
            datos = self.db.get_data_list(query, (), dictionary=True)
            return {"status": "success", "data": datos}
        except Exception as e:
            return {"status": "error", "message": str(e)}
