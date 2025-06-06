from datetime import datetime, date, timedelta
from app.core.enums.e_payment_model import E_PAYMENT
from app.core.enums.e_employes_model import E_EMPLOYE
from app.core.interfaces.database_mysql import DatabaseMysql
from app.models.employes_model import EmployesModel
from app.models.discount_model import DiscountModel


class PaymentModel:
    def __init__(self):
        self.db = DatabaseMysql()
        self.employee_model = EmployesModel()
        self.discount_model = DiscountModel()
        self.E = E_PAYMENT
        self.EE = E_EMPLOYE
        self._exists_table = self.check_table()

    def check_table(self) -> bool:
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, self.E.TABLE.value), dictionary=True)
            if result.get("c", 0) == 0:
                print(f"⚠️ La tabla {self.E.TABLE.value} no existe. Creando...")

                create_query = f"""
                CREATE TABLE IF NOT EXISTS {self.E.TABLE.value} (
                    {self.E.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {self.E.NUMERO_NOMINA.value} SMALLINT UNSIGNED NOT NULL,
                    {self.E.FECHA_PAGO.value} DATE NOT NULL,
                    {self.E.TOTAL_HORAS_TRABAJADAS.value} DECIMAL(5,2) NOT NULL DEFAULT 0.00,
                    {self.E.SUELDO_POR_HORA.value} DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                    {self.E.MONTO_BASE.value} DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                    {self.E.MONTO_DESCUENTOS.value} DECIMAL(10,2) DEFAULT 0.00,
                    {self.E.MONTO_PRESTAMO.value} DECIMAL(10,2) DEFAULT 0.00,
                    {self.E.MONTO_TOTAL.value} DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                    {self.E.PAGO_DEPOSITO.value} DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                    {self.E.PAGO_EFECTIVO.value} DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                    {self.E.SALDO.value} DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                    {self.E.ESTADO.value} VARCHAR(20) DEFAULT 'pendiente',
                    {self.E.FECHA_CREACION.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    {self.E.FECHA_MODIFICACION.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY ({self.E.NUMERO_NOMINA.value})
                        REFERENCES {self.EE.TABLE.value}({self.EE.NUMERO_NOMINA.value})
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {self.E.TABLE.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {self.E.TABLE.value} ya existe.")
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {self.E.TABLE.value}: {ex}")
            return False


    def get_by_id(self, id_pago: int):
        try:
            if not isinstance(id_pago, int) or id_pago <= 0:
                return {"status": "error", "message": "ID de pago inválido"}

            query = f"""
                SELECT * FROM {E_PAYMENT.TABLE.value}
                WHERE {E_PAYMENT.ID.value} = %s
            """
            result = self.db.get_data(query, (id_pago,), dictionary=True)

            if not result:
                return {"status": "error", "message": "No se encontró el pago con ese ID"}

            if isinstance(result, list) and result:
                return {"status": "success", "data": result[0]}

            return {"status": "error", "message": "Resultado inesperado al obtener el pago."}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener el pago: {ex}"}


    def crear_sp_horas_trabajadas_para_pagos(self):
        try:
            check_query = """
                SELECT COUNT(*) AS c
                FROM information_schema.routines
                WHERE routine_schema = %s
                AND routine_name = 'horas_trabajadas_para_pagos'
                AND routine_type = 'PROCEDURE'
            """
            result = self.db.get_data(check_query, (self.db.database,), dictionary=True)
            if result.get("c", 0) == 0:
                print("⚠️ Stored Procedure 'horas_trabajadas_para_pagos' no existe. Creando...")

                cursor = self.db.connection.cursor()
                cursor.execute("DROP PROCEDURE IF EXISTS horas_trabajadas_para_pagos")

                sp_sql = """
                CREATE PROCEDURE horas_trabajadas_para_pagos (
                    IN p_numero_nomina INT,
                    IN p_fecha_inicio DATE,
                    IN p_fecha_fin DATE
                )
                BEGIN
                    IF p_numero_nomina IS NOT NULL THEN
                        IF EXISTS (SELECT 1 FROM empleados WHERE numero_nomina = p_numero_nomina) THEN
                            SELECT
                                a.numero_nomina,
                                e.nombre_completo,
                                IFNULL(SEC_TO_TIME(SUM(TIME_TO_SEC(a.tiempo_trabajo))), '00:00:00') AS total_horas_trabajadas
                            FROM asistencias a
                            JOIN empleados e ON a.numero_nomina = e.numero_nomina
                            WHERE a.numero_nomina = p_numero_nomina
                            AND a.fecha BETWEEN p_fecha_inicio AND p_fecha_fin
                            AND a.estado = 'completo'
                            GROUP BY a.numero_nomina, e.nombre_completo;
                        ELSE
                            SELECT 'Empleado no encontrado' AS mensaje;
                        END IF;
                    ELSE
                        SELECT
                            a.numero_nomina,
                            e.nombre_completo,
                            IFNULL(SEC_TO_TIME(SUM(TIME_TO_SEC(a.tiempo_trabajo))), '00:00:00') AS total_horas_trabajadas
                        FROM asistencias a
                        JOIN empleados e ON a.numero_nomina = e.numero_nomina
                        WHERE a.fecha BETWEEN p_fecha_inicio AND p_fecha_fin
                        AND a.estado = 'completo'
                        GROUP BY a.numero_nomina, e.nombre_completo;
                    END IF;
                END
                """

                cursor.execute(sp_sql)
                self.db.connection.commit()
                cursor.close()

                print("✅ Stored Procedure 'horas_trabajadas_para_pagos' creado correctamente.")
            else:
                print("✔️ Stored Procedure 'horas_trabajadas_para_pagos' ya existe.")
        except Exception as ex:
            print(f"❌ Error al crear SP 'horas_trabajadas_para_pagos': {ex}")


    def generar_pagos_por_rango(self, fecha_inicio: str, fecha_fin: str) -> dict:
        try:
            empleados = self.employee_model.get_all()
            if empleados["status"] != "success":
                return {"status": "error", "message": "No se pudieron cargar los empleados."}

            pagos_generados = 0
            errores = 0

            for emp in empleados["data"]:
                numero_nomina = emp.get("numero_nomina")
                if not numero_nomina:
                    continue

                # Verificar si ya existe un pago pagado dentro del rango
                query = f"""
                    SELECT COUNT(*) AS c FROM {E_PAYMENT.TABLE.value}
                    WHERE {E_PAYMENT.NUMERO_NOMINA.value} = %s
                    AND {E_PAYMENT.ESTADO.value} = 'pagado'
                    AND {E_PAYMENT.FECHA_PAGO.value} BETWEEN %s AND %s
                """
                existente = self.db.get_data(query, (numero_nomina, fecha_inicio, fecha_fin), dictionary=True)

                if existente and isinstance(existente, list) and existente[0]["c"] > 0:
                    continue  # Ya tiene un pago confirmado en ese rango

                resultado = self.generar_pago_por_empleado(numero_nomina, fecha_inicio, fecha_fin)

                if resultado["status"] != "success":
                    errores += 1
                else:
                    pagos_generados += 1

            mensaje = f"{pagos_generados} pagos generados del {fecha_inicio} al {fecha_fin}."
            if errores > 0:
                mensaje += f" {errores} empleados fallaron o no tenían asistencias válidas."

            return {"status": "success", "message": mensaje}

        except Exception as e:
            return {"status": "error", "message": str(e)}


    def get_total_horas_trabajadas(self, fecha_inicio: str, fecha_fin: str, numero_nomina: int = None) -> dict:
        """
        Obtiene el total de horas trabajadas desde el SP 'horas_trabajadas_para_pagos'.
        Si se proporciona un número de nómina, devuelve solo ese empleado; si no, devuelve todos.
        """
        try:
            if not fecha_inicio or not fecha_fin:
                return {"status": "error", "message": "Fechas no válidas"}

            if numero_nomina is not None and not isinstance(numero_nomina, int):
                return {"status": "error", "message": "Número de nómina inválido"}

            print(f"📤 Llamando SP 'horas_trabajadas_para_pagos' con: ID={numero_nomina}, inicio={fecha_inicio}, fin={fecha_fin}")
            resultados = self.db.call_procedure("horas_trabajadas_para_pagos", (numero_nomina, fecha_inicio, fecha_fin))
            print(f"📥 Resultados recibidos: {resultados}")

            if not resultados or (isinstance(resultados, list) and len(resultados) == 0):
                return {"status": "success", "data": [], "message": "No se encontraron registros"}

            if isinstance(resultados, list) and "mensaje" in resultados[0]:
                return {"status": "error", "message": resultados[0]["mensaje"]}

            return {"status": "success", "data": resultados}

        except Exception as e:
            print(f"❌ Error en get_total_horas_trabajadas: {e}")
            return {"status": "error", "message": str(e)}

    def delete_pago(self, id_pago: int) -> dict:
        try:
            if not isinstance(id_pago, int) or id_pago <= 0:
                return {"status": "error", "message": "ID de pago inválido"}

            self.discount_model.delete_by_pago(id_pago)

            delete_query = f"DELETE FROM {E_PAYMENT.TABLE.value} WHERE {E_PAYMENT.ID.value} = %s"
            self.db.run_query(delete_query, (id_pago,))

            print(f"🗑️ Pago con ID {id_pago} eliminado correctamente.")
            return {"status": "success", "message": "Pago eliminado correctamente."}
        except Exception as ex:
            print(f"❌ Error al eliminar el pago {id_pago}: {ex}")
            return {"status": "error", "message": str(ex)}

        
    def generar_pago_por_empleado(self, numero_nomina: int, fecha_inicio: str, fecha_fin: str) -> bool:
        try:
            resultado = self.db.call_procedure("horas_trabajadas_para_pagos", (numero_nomina, fecha_inicio, fecha_fin))
            print(f"🔍 Resultado del SP: {resultado}")
            if not resultado:
                return False

            data = resultado[0]
            tiempo_str = data.get("total_horas_trabajadas")
            if not tiempo_str:
                print(f"⚠️ No hay tiempo trabajado para {numero_nomina}")
                return False

            horas, minutos, segundos = map(int, tiempo_str.split(":"))
            total_horas = round(horas + minutos / 60 + segundos / 3600, 2)
            sueldo_por_hora = float(data.get("sueldo_por_hora", 0.0))

            if total_horas <= 0 or sueldo_por_hora <= 0:
                print(f"⚠️ Horas ({total_horas}) o sueldo por hora ({sueldo_por_hora}) inválidos para {numero_nomina}")
                return False

            monto_base = round(total_horas * sueldo_por_hora, 2)
            monto_total = monto_base

            query = f"""
                INSERT INTO {E_PAYMENT.TABLE.value} (
                    {E_PAYMENT.NUMERO_NOMINA.value},
                    {E_PAYMENT.FECHA_PAGO.value},
                    {E_PAYMENT.TOTAL_HORAS_TRABAJADAS.value},
                    {E_PAYMENT.SUELDO_POR_HORA.value},
                    {E_PAYMENT.MONTO_BASE.value},
                    {E_PAYMENT.MONTO_TOTAL.value},
                    {E_PAYMENT.ESTADO.value},
                    {E_PAYMENT.FECHA_CREACION.value}
                ) VALUES (%s, %s, %s, %s, %s, %s, 'pendiente', NOW())
            """

            self.db.run_query(query, (
                numero_nomina,
                fecha_fin,
                total_horas,
                sueldo_por_hora,
                monto_base,
                monto_total
            ))

            print(f"✅ Pago generado para {numero_nomina} por {total_horas} horas (${monto_base})")
            return True
        except Exception as e:
            print("❌ Error en generar_pago_por_empleado:")
            print(e)
            return False




    def update_pago(self, id_pago: int, campos_actualizados: dict):
        try:
            campos_sql = ", ".join([f"{campo.value} = %s" for campo in campos_actualizados.keys()])
            valores = list(campos_actualizados.values()) + [id_pago]
            query = f"""
                UPDATE {E_PAYMENT.TABLE.value}
                SET {campos_sql}, {E_PAYMENT.FECHA_MODIFICACION.value} = NOW()
                WHERE {E_PAYMENT.ID.value} = %s
            """
            self.db.run_query(query, tuple(valores))
            return {"status": "success", "message": "Pago actualizado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al actualizar el pago: {ex}"}


    def get_fecha_minima_pago(self) -> date | None:
        try:
            query = f"SELECT MIN({E_PAYMENT.FECHA_PAGO.value}) AS min_fecha FROM {E_PAYMENT.TABLE.value}"
            result = self.db.get_data(query, dictionary=True)
            min_fecha = result.get("min_fecha")
            if isinstance(min_fecha, str):
                min_fecha = datetime.strptime(min_fecha, "%Y-%m-%d").date()
            return min_fecha
        except Exception as ex:
            print(f"❌ Error al obtener fecha mínima: {ex}")
            return None

    def get_fecha_maxima_pago(self) -> date | None:
        try:
            query = f"SELECT MAX({E_PAYMENT.FECHA_PAGO.value}) AS max_fecha FROM {E_PAYMENT.TABLE.value}"
            result = self.db.get_data(query, dictionary=True)
            max_fecha = result.get("max_fecha")
            if isinstance(max_fecha, str):
                max_fecha = datetime.strptime(max_fecha, "%Y-%m-%d").date()
            return max_fecha
        except Exception as ex:
            print(f"❌ Error al obtener fecha máxima: {ex}")
            return None

    def get_ultima_fecha_pago_generada(self) -> date | None:
        """
        Retorna la fecha de pago más reciente registrada (pagada o no).
        """
        try:
            query = f"SELECT MAX({E_PAYMENT.FECHA_PAGO.value}) AS ultima_fecha FROM {E_PAYMENT.TABLE.value}"
            result = self.db.get_data(query, dictionary=True)
            ultima_fecha = result.get("ultima_fecha")
            if isinstance(ultima_fecha, str):
                ultima_fecha = datetime.strptime(ultima_fecha, "%Y-%m-%d").date()
            return ultima_fecha
        except Exception as ex:
            print(f"❌ Error al obtener la última fecha de pago: {ex}")
            return None

    def get_pagos_por_rango(self, fecha_inicio: str, fecha_fin: str):
        try:
            query = f"""
                SELECT p.*, e.nombre_completo AS nombre
                FROM {E_PAYMENT.TABLE.value} p
                JOIN empleados e ON p.{E_PAYMENT.NUMERO_NOMINA.value} = e.numero_nomina
                WHERE p.{E_PAYMENT.FECHA_PAGO.value} BETWEEN %s AND %s
                ORDER BY p.{E_PAYMENT.FECHA_PAGO.value} ASC
            """
            pagos = self.db.get_data_list(query, (fecha_inicio, fecha_fin), dictionary=True)
            return {"status": "success", "data": pagos}
        except Exception as ex:
            print(f"❌ Error en get_pagos_por_rango: {ex}")
            return {"status": "error", "message": str(ex)}

    def get_fechas_utilizadas(self) -> list:
        """
        Retorna una lista de fechas únicas ya utilizadas en pagos.
        Asegura que todas sean objetos datetime.date.
        """
        try:
            query = f"SELECT DISTINCT {E_PAYMENT.FECHA_PAGO.value} AS fecha_pago FROM {E_PAYMENT.TABLE.value}"
            resultados = self.db.get_data_list(query, dictionary=True)
            fechas = []
            for r in resultados:
                fecha = r.get("fecha_pago")
                if isinstance(fecha, str):
                    fecha = datetime.strptime(fecha, "%Y-%m-%d").date()
                if isinstance(fecha, date):
                    fechas.append(fecha)
            return fechas
        except Exception as ex:
            print(f"❌ Error al obtener fechas utilizadas: {ex}")
            return []


    @staticmethod
    def calcular_pago_efectivo_y_saldo(monto_total: float, pago_deposito: float):
        if pago_deposito > monto_total:
            return None, "❌ El depósito no puede ser mayor al monto total."

        restante = monto_total - pago_deposito
        sobrante = restante % 50

        if sobrante < 25:
            pago_efectivo_real = restante - sobrante
            saldo = sobrante
        else:
            pago_efectivo_real = restante - sobrante + 50
            saldo = restante - pago_efectivo_real

        return {
            "pago_efectivo": round(pago_efectivo_real, 2),
            "saldo": round(saldo, 2),
            "total": round(pago_deposito + pago_efectivo_real, 2)
        }, None

    def confirmar_pago(self, id_pago: int, pago_deposito: float) -> dict:
        try:
            if not isinstance(id_pago, int) or id_pago <= 0:
                return {"status": "error", "message": "ID de pago inválido"}

            if not isinstance(pago_deposito, (int, float)) or pago_deposito < 0:
                return {"status": "error", "message": "El pago por depósito debe ser un número positivo"}

            pago_data = self.get_by_id(id_pago)
            if pago_data["status"] != "success":
                return pago_data

            pago = pago_data["data"]
            monto_total = float(pago.get(E_PAYMENT.MONTO_TOTAL.value, 0))

            resultado, error = self.calcular_pago_efectivo_y_saldo(monto_total, pago_deposito)
            if error:
                return {"status": "error", "message": error}

            actualizacion = {
                E_PAYMENT.PAGO_DEPOSITO.value: resultado["total"] - resultado["pago_efectivo"],
                E_PAYMENT.PAGO_EFECTIVO.value: resultado["pago_efectivo"],
                E_PAYMENT.SALDO.value: resultado["saldo"],
                E_PAYMENT.ESTADO.value: "pagado"
            }

            self.update_pago(id_pago, actualizacion)

            return {
                "status": "success",
                "message": f"✅ Pago confirmado. Depósito: ${actualizacion[E_PAYMENT.PAGO_DEPOSITO.value]:.2f}, "
                        f"Efectivo: ${actualizacion[E_PAYMENT.PAGO_EFECTIVO.value]:.2f}, "
                        f"Saldo a favor: ${actualizacion[E_PAYMENT.SALDO.value]:.2f}."
            }

        except Exception as ex:
            return {"status": "error", "message": f"Error al confirmar el pago: {ex}"}

    def get_pago_prestamo_asociado(self, id_pago: int) -> float:
        try:
            query = """
                SELECT pago_prestamo_monto_pagado
                FROM pagos_prestamo
                WHERE id_pago = %s AND desde_nomina = TRUE
                LIMIT 1
            """
            resultado = self.db.get_data(query, (id_pago,), dictionary=True)
            return float(resultado["pago_prestamo_monto_pagado"]) if resultado else 0.0
        except Exception as e:
            print(f"❌ Error al obtener pago de préstamo asociado a pago {id_pago}: {e}")
            return 0.0


    def get_id_pago_por_empleado(self, numero_nomina: int):
        try:
            query = f"""
                SELECT {self.E.ID.value} AS id_pago
                FROM {self.E.TABLE.value}
                WHERE {self.E.NUMERO_NOMINA.value} = %s AND {self.E.ESTADO.value} = 'pendiente'
                ORDER BY {self.E.FECHA_PAGO.value} DESC
                LIMIT 1
            """
            result = self.db.get_data(query, (numero_nomina,), dictionary=True)
            return result.get("id_pago") if result else None
        except Exception as e:
            print(f"❌ Error al obtener ID de pago: {e}")
            return None

    def existe_pago_para_fecha(self, numero_nomina: int, fecha_pago: str) -> bool:
        try:
            query = f"""
                SELECT COUNT(*) AS total
                FROM {self.E.TABLE.value}
                WHERE {self.E.NUMERO_NOMINA.value} = %s AND {self.E.FECHA_PAGO.value} = %s
            """
            result = self.db.get_data(query, (numero_nomina, fecha_pago), dictionary=True)
            return result.get("total", 0) > 0
        except Exception as ex:
            print(f"❌ Error verificando existencia de pago: {ex}")
            return False

    def get_horas_trabajadas(self, numero_nomina: int, fecha: str) -> str:
        try:
            resultado = self.get_total_horas_trabajadas(fecha, fecha, numero_nomina)
            if resultado["status"] == "success" and resultado["data"]:
                return resultado["data"][0].get("total_horas_trabajadas", "00:00:00")
            return "00:00:00"
        except Exception as ex:
            print(f"❌ Error al obtener horas trabajadas para {numero_nomina}: {ex}")
            return "00:00:00"
