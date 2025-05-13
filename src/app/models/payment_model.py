from datetime import datetime, date
from app.core.enums.e_payment_model import E_PAYMENT
from app.core.interfaces.database_mysql import DatabaseMysql
from app.models.employes_model import EmployesModel
from app.models.discount_model import DiscountModel

class PaymentModel:
    """
    Modelo de pagos (nómina).
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self.employee_model = EmployesModel()
        self._exists_table = self.check_table()
        self.discount_model = DiscountModel()

    def check_table(self) -> bool:
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, E_PAYMENT.TABLE.value), dictionary=True)
            if result.get("c", 0) == 0:
                print(f"⚠️ La tabla {E_PAYMENT.TABLE.value} no existe. Creando...")

                create_query = f"""
                CREATE TABLE IF NOT EXISTS {E_PAYMENT.TABLE.value} (
                    {E_PAYMENT.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {E_PAYMENT.NUMERO_NOMINA.value} SMALLINT UNSIGNED NOT NULL,
                    {E_PAYMENT.FECHA_PAGO.value} DATE NOT NULL,
                    {E_PAYMENT.MONTO_BASE.value} DECIMAL(10,2) NOT NULL,
                    {E_PAYMENT.MONTO_TOTAL.value} DECIMAL(10,2) NOT NULL,
                    {E_PAYMENT.SALDO.value} DECIMAL(10,2) DEFAULT 0,
                    {E_PAYMENT.PAGO_DEPOSITO.value} DECIMAL(10,2) NOT NULL,
                    {E_PAYMENT.PAGO_EFECTIVO.value} DECIMAL(10,2) NOT NULL,
                    {E_PAYMENT.ESTADO.value} VARCHAR(20) DEFAULT 'pendiente',
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
            empleado = self.employee_model.get_by_numero_nomina(numero_nomina)
            if not empleado or not isinstance(empleado, dict):
                return {"status": "error", "message": "Empleado no encontrado"}

            resultado = self.get_total_horas_trabajadas(fecha_inicio, fecha_fin, numero_nomina)
            print(f"📤 Consulta de horas trabajadas: ID={numero_nomina}, del {fecha_inicio} al {fecha_fin}")
            print(f"📥 Resultado del SP: {resultado}")

            if resultado["status"] != "success" or not resultado["data"]:
                return {"status": "error", "message": "No hay horas registradas para ese empleado"}

            tiempo_str = resultado["data"][0]["total_horas_trabajadas"]
            h, m, s = map(int, tiempo_str.split(":"))
            horas_decimales = h + m / 60 + s / 3600
            sueldo_hora = float(empleado["sueldo_por_hora"])
            monto_base = round(sueldo_hora * horas_decimales, 2)

            insert_pago = f"""
                INSERT INTO {E_PAYMENT.TABLE.value}
                ({E_PAYMENT.NUMERO_NOMINA.value}, {E_PAYMENT.FECHA_PAGO.value},
                {E_PAYMENT.MONTO_BASE.value}, {E_PAYMENT.MONTO_TOTAL.value},
                {E_PAYMENT.PAGO_DEPOSITO.value}, {E_PAYMENT.PAGO_EFECTIVO.value})
                VALUES (%s, CURDATE(), %s, %s, %s, %s)
            """
            self.db.run_query(insert_pago, (numero_nomina, monto_base, monto_base, 0.0, monto_base))
            id_pago = self.db.get_last_insert_id()

            self.discount_model.agregar_descuentos_opcionales(
                numero_nomina=numero_nomina,
                id_pago=id_pago,
                aplicar_imss=True,
                aplicar_transporte=True,
                aplicar_comida=True,
                estado_comida="media"
            )

            total_descuentos = self.discount_model.get_total_descuentos_por_pago(id_pago)
            monto_final = max(0, monto_base - total_descuentos)

            self.update_pago(id_pago, {
                E_PAYMENT.MONTO_TOTAL.value: monto_final,
                E_PAYMENT.PAGO_EFECTIVO.value: monto_final
            })

            return {
                "status": "success",
                "message": f"✅ Pago generado por ${monto_final:.2f} con ${total_descuentos:.2f} en descuentos",
                "id_pago": id_pago,
                "monto_base": monto_base,
                "total_descuentos": total_descuentos
            }

        except Exception as e:
            print(f"❌ Error en generar_pago_por_empleado: {e}")
            return {"status": "error", "message": str(e)}

    def get_total_horas_trabajadas(self, fecha_inicio: str, fecha_fin: str, numero_nomina: int = None) -> dict:
        try:
            print(f"📤 Llamando SP 'horas_trabajadas' con: ID={numero_nomina}, inicio={fecha_inicio}, fin={fecha_fin}")
            resultados = self.db.execute_procedure("horas_trabajadas", (numero_nomina, fecha_inicio, fecha_fin))
            print(f"📥 Resultados recibidos: {resultados}")
            if not resultados:
                return {"status": "success", "data": [], "message": "No se encontraron registros en ese rango"}
            return {"status": "success", "data": resultados}
        except Exception as e:
            print(f"❌ Error en get_total_horas_trabajadas: {e}")
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

    def get_pagos_pagados(self):
        """
        Retorna todos los pagos con estado 'pagado'.
        """
        try:
            query = f"""
                SELECT *
                FROM {E_PAYMENT.TABLE.value}
                WHERE {E_PAYMENT.ESTADO.value} = 'pagado'
            """
            return self.db.get_all(query)
        except Exception as e:
            print(f"❌ Error al obtener pagos pagados: {e}")
            return []
