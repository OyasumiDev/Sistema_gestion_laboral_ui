from datetime import date
from app.core.enums.e_discount_model import E_DISCOUNT
from app.core.interfaces.database_mysql import DatabaseMysql

VALOR_IMSS_POR_DEFECTO = 50.0


class DiscountModel:
    def __init__(self):
        self.db = DatabaseMysql()
        self.E = E_DISCOUNT
        self._create_table()

    def _create_table(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self.E.TABLE.value} (
            {self.E.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
            numero_nomina SMALLINT UNSIGNED NOT NULL,
            {self.E.ID_PAGO.value} INT DEFAULT NULL,
            {self.E.TIPO.value} VARCHAR(50) NOT NULL,
            {self.E.DESCRIPCION.value} VARCHAR(100) DEFAULT NULL,
            {self.E.MONTO_DESCUENTO.value} DECIMAL(10,2) NOT NULL,
            {self.E.FECHA_APLICACION.value} DATE NOT NULL DEFAULT (CURRENT_DATE),
            {self.E.FECHA_CREACION.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE,
            FOREIGN KEY ({self.E.ID_PAGO.value}) REFERENCES pagos(id_pago) ON DELETE SET NULL
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
                {self.E.DESCRIPCION.value}, {self.E.MONTO_DESCUENTO.value}
            ) VALUES (%s, %s, %s, %s, %s)
            """
            self.db.run_query(query, (numero_nomina, id_pago, tipo, descripcion, monto))
            return {"status": "success"}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def agregar_descuentos_opcionales(
        self,
        id_pago: int,
        numero_nomina: int,
        aplicar_imss: bool = True,
        aplicar_transporte: bool = False,
        monto_transporte: float = 0.0,
        aplicar_comida: bool = False,
        estado_comida: str = "No cobro",
        descuento_extra: float = 0.0,
        descripcion_extra: str = ""
    ) -> dict:
        print(f"🟡 Llamando agregar_descuentos_opcionales con: id_pago={id_pago}, numero_nomina={numero_nomina}")
        print(f"    aplicar_imss={aplicar_imss}, aplicar_transporte={aplicar_transporte}, monto_transporte={monto_transporte}")
        print(f"    aplicar_comida={aplicar_comida}, estado_comida={estado_comida}")
        print(f"    descuento_extra={descuento_extra}, descripcion_extra={descripcion_extra}")
        try:
            resultado = self.guardar_descuentos_editables(
                id_pago=id_pago,
                numero_nomina=numero_nomina,
                aplicar_imss=aplicar_imss,
                aplicar_transporte=aplicar_transporte,
                monto_transporte=monto_transporte,
                aplicar_comida=aplicar_comida,
                estado_comida=estado_comida,
                descuento_extra=descuento_extra,
                descripcion_extra=descripcion_extra
            )
            print(f"✅ Descuentos opcionales agregados correctamente para ID pago: {id_pago}")
            return resultado
        except Exception as e:
            print(f"❌ Error en agregar_descuentos_opcionales: {e}")
            return {"status": "error", "message": str(e)}


    def guardar_descuentos_completos(
        self,
        id_pago: int,
        numero_nomina: int,
        aplicar_imss: bool,
        monto_imss: float,
        aplicar_transporte: bool,
        monto_transporte: float,
        aplicar_comida: bool,
        monto_comida: float,
        aplicar_extra: bool,
        monto_extra: float,
        descripcion_extra: str
    ) -> dict:
        try:
            self.eliminar_por_id_pago(id_pago)

            if aplicar_imss and monto_imss >= 0:
                self.agregar_descuento(numero_nomina, "retenciones_imss", "Cuota IMSS", monto_imss or VALOR_IMSS_POR_DEFECTO, id_pago)

            if aplicar_transporte and monto_transporte >= 0:
                self.agregar_descuento(numero_nomina, "transporte", "Pasaje diario", monto_transporte, id_pago)

            if aplicar_comida and monto_comida >= 0:
                self.agregar_descuento(numero_nomina, "comida", "Comida diaria", monto_comida, id_pago)

            if aplicar_extra and monto_extra > 0 and descripcion_extra:
                self.agregar_descuento(numero_nomina, "descuento_extra", descripcion_extra, monto_extra, id_pago)

            return {"status": "success"}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def guardar_descuentos_editables(
        self,
        id_pago: int,
        numero_nomina: int,
        aplicar_imss: bool,
        aplicar_transporte: bool,
        monto_transporte: float,
        aplicar_comida: bool,
        estado_comida: str,
        descuento_extra: float,
        descripcion_extra: str
    ) -> dict:
        try:
            self.eliminar_por_id_pago(id_pago)

            if aplicar_imss:
                self.agregar_descuento(numero_nomina, "retenciones_imss", "Cuota IMSS", VALOR_IMSS_POR_DEFECTO, id_pago)

            if aplicar_transporte:
                self.agregar_descuento(numero_nomina, "transporte", "Pasaje diario", monto_transporte, id_pago)

            if aplicar_comida:
                monto_comida = (
                    50.0 if estado_comida == "50 pesos"
                    else 100.0 if estado_comida == "100 pesos"
                    else 0.0
                )
                self.agregar_descuento(numero_nomina, "comida", estado_comida, monto_comida, id_pago)

            if descuento_extra > 0 and descripcion_extra:
                self.agregar_descuento(numero_nomina, "descuento_extra", descripcion_extra, descuento_extra, id_pago)

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
            SELECT {self.E.TIPO.value}, {self.E.DESCRIPCION.value}, {self.E.MONTO_DESCUENTO.value}
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
            SELECT SUM({self.E.MONTO_DESCUENTO.value}) AS total
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
            total = sum(float(d[self.E.MONTO_DESCUENTO.value]) for d in descuentos)
            return {
                "status": "success",
                "descuentos": descuentos,
                "total": round(total, 2)
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def guardar_o_actualizar_descuentos(
        self,
        id_pago: int,
        numero_nomina: int,
        monto_imss: float = 0.0,
        monto_transporte: float = 0.0,
        monto_comida: float = 0.0,
        monto_extra: float = 0.0,
        descripcion_extra: str = ""
    ) -> dict:
        try:
            # Primero eliminamos si ya existía
            self.eliminar_por_id_pago(id_pago)

            # Insertamos el nuevo registro
            query = f"""
            INSERT INTO {self.E.TABLE.value} (
                numero_nomina, {self.E.ID_PAGO.value},
                monto_imss, monto_transporte, monto_comida,
                monto_extra, descripcion_extra
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            values = (
                numero_nomina, id_pago,
                monto_imss, monto_transporte, monto_comida,
                monto_extra, descripcion_extra
            )
            self.db.run_query(query, values)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
