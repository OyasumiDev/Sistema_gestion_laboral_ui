from app.core.enums.e_payment_model import E_PAYMENT
from app.core.interfaces.database_mysql import DatabaseMysql
from app.models.discount_model import DiscountModel

class PaymentModel:
    """
    Modelo de pagos (nómina).
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self._exists_table = self.check_table()

    def check_table(self) -> bool:
        """
        Verifica si la tabla de pagos existe y la crea si no existe.
        """
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, E_PAYMENT.TABLE.value), dictionary=True)
            count = result.get("c", 0)

            if count == 0:
                print(f"⚠️ La tabla {E_PAYMENT.TABLE.value} no existe. Creando...")

                create_query = f"""
                CREATE TABLE IF NOT EXISTS {E_PAYMENT.TABLE.value} (
                    {E_PAYMENT.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {E_PAYMENT.NUMERO_NOMINA.value} SMALLINT UNSIGNED NOT NULL,
                    {E_PAYMENT.FECHA_PAGO.value} DATE NOT NULL,
                    monto_base DECIMAL(10,2) NOT NULL,
                    {E_PAYMENT.MONTO_TOTAL.value} DECIMAL(10,2) NOT NULL,
                    {E_PAYMENT.SALDO.value} DECIMAL(10,2) DEFAULT 0,
                    {E_PAYMENT.PAGO_DEPOSITO.value} DECIMAL(10,2) NOT NULL,
                    {E_PAYMENT.PAGO_EFECTIVO.value} DECIMAL(10,2) NOT NULL,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY ({E_PAYMENT.NUMERO_NOMINA.value})
                        REFERENCES empleados(numero_nomina)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """

                self.db.run_query(create_query)
                print(f"✅ Tabla {E_PAYMENT.TABLE.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {E_PAYMENT.TABLE.value} ya existe.")
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {E_PAYMENT.TABLE.value}: {ex}")
            return False

    def generar_pago_por_empleado(self, numero_nomina: int, fecha_inicio: str, fecha_fin: str) -> dict:
        try:
            resultado = self.get_total_horas_trabajadas(fecha_inicio, fecha_fin, numero_nomina)
            if resultado["status"] != "success" or not resultado["data"]:
                return {"status": "error", "message": "No hay horas registradas para ese empleado"}

            tiempo_str = resultado["data"][0]["total_horas_trabajadas"]
            h, m, s = map(int, tiempo_str.split(":"))
            horas_decimales = h + m / 60 + s / 3600

            query_sueldo = "SELECT sueldo_diario FROM empleados WHERE numero_nomina = %s"
            sueldo = self.db.get_data(query_sueldo, (numero_nomina,), dictionary=True)
            if not sueldo:
                return {"status": "error", "message": "Empleado no encontrado"}
            sueldo_diario = sueldo["sueldo_diario"]

            monto_base = round(sueldo_diario * horas_decimales, 2)

            insert_pago = f"""
                INSERT INTO {E_PAYMENT.TABLE.value}
                ({E_PAYMENT.NUMERO_NOMINA.value}, {E_PAYMENT.FECHA_PAGO.value},
                {E_PAYMENT.MONTO_TOTAL.value}, {E_PAYMENT.PAGO_DEPOSITO.value},
                {E_PAYMENT.PAGO_EFECTIVO.value})
                VALUES (%s, CURDATE(), %s, %s, 0)
            """
            self.db.run_query(insert_pago, (numero_nomina, monto_base, monto_base))
            id_pago = self.db.get_last_insert_id()

            discount_model = DiscountModel()
            discount_model.agregar_descuentos_opcionales(
                numero_nomina=numero_nomina,
                id_pago=id_pago,
                aplicar_imss=True,
                aplicar_transporte=True,
                aplicar_comida=True,
                estado_comida="media"
            )

            total_descuentos = discount_model.get_total_descuentos_por_pago(id_pago)
            monto_final = max(0, monto_base - total_descuentos)

            self.update_pago(id_pago, {
                E_PAYMENT.MONTO_TOTAL.value: monto_final,
                E_PAYMENT.PAGO_DEPOSITO.value: monto_final
            })

            return {
                "status": "success",
                "message": f"✅ Pago generado por ${monto_final:.2f} con ${total_descuentos:.2f} en descuentos",
                "id_pago": id_pago,
                "monto_base": monto_base,
                "total_descuentos": total_descuentos
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_total_horas_trabajadas(self, fecha_inicio: str, fecha_fin: str, numero_nomina: int = None) -> dict:
        try:
            resultados = self.db.call_procedure("horas_trabajadas", (numero_nomina, fecha_inicio, fecha_fin))
            if not resultados:
                return {"status": "success", "data": [], "message": "No se encontraron registros en ese rango"}
            return {"status": "success", "data": resultados}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def update_pago(self, id_pago: int, campos_actualizados: dict):
        try:
            campos_sql = ", ".join([f"{campo} = %s" for campo in campos_actualizados.keys()])
            valores = list(campos_actualizados.values()) + [id_pago]
            query = f"""
            UPDATE {E_PAYMENT.TABLE.value}
            SET {campos_sql}
            WHERE {E_PAYMENT.ID.value} = %s
            """
            self.db.run_query(query, tuple(valores))
            return {"status": "success", "message": "Pago actualizado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al actualizar el pago: {ex}"}

    def get_pago_con_descuentos(self, id_pago: int):
        try:
            pago = self.get_by_id(id_pago)
            if pago["status"] != "success":
                return pago
            descuentos = DiscountModel().get_by_pago(id_pago)
            return {
                "status": "success",
                "data": {
                    "pago": pago["data"],
                    "descuentos": descuentos
                }
            }
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener el pago con descuentos: {ex}"}

    def get_by_id(self, id_pago: int):
        try:
            query = f"""
                SELECT * FROM {E_PAYMENT.TABLE.value}
                WHERE {E_PAYMENT.ID.value} = %s
            """
            result = self.db.get_data(query, (id_pago,), dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener el pago: {ex}"}
