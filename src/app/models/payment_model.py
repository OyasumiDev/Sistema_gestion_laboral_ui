from datetime import datetime, date
from app.core.enums.e_payment_model import E_PAYMENT
from app.core.interfaces.database_mysql import DatabaseMysql
from app.models.employes_model import EmployesModel
from app.models.discount_model import DiscountModel
from app.models.assistance_model import AssistanceModel

class PaymentModel:
    def __init__(self):
        self.db = DatabaseMysql()
        self.employee_model = EmployesModel()
        self._exists_table = self.check_table()
        self.discount_model = DiscountModel()
        self.assistance_model = AssistanceModel()

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
                    {E_PAYMENT.TOTAL_HORAS_TRABAJADAS.value} DECIMAL(5,2) DEFAULT 0,
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


    def get_pago_con_descuentos(self, id_pago: int):
        try:
            pago = self.get_by_id(id_pago)

            # Validación de estado y existencia de datos
            if pago["status"] != "success":
                return pago
            if not pago.get("data"):
                return {"status": "error", "message": f"Pago con ID {id_pago} no encontrado."}
            if not isinstance(pago["data"], dict):
                return {"status": "error", "message": f"Formato inesperado de datos del pago con ID {id_pago}."}

            # Obtener descuentos
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
            if not isinstance(id_pago, int) or id_pago <= 0:
                return {"status": "error", "message": "ID de pago inválido"}

            query = f"""
                SELECT * FROM {E_PAYMENT.TABLE.value}
                WHERE {E_PAYMENT.ID.value} = %s
            """
            result = self.db.get_data(query, (id_pago,), dictionary=True)

            if not result:
                return {"status": "error", "message": "No se encontró el pago con ese ID"}

            return {"status": "success", "data": result}

        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener el pago: {ex}"}



    def get_pagos_pagados(self):
        try:
            query = f"""
                SELECT * FROM {E_PAYMENT.TABLE.value}
                WHERE {E_PAYMENT.ESTADO.value} = 'pagado'
            """
            result = self.db.get_all(query)

            if not isinstance(result, list) or (result and not isinstance(result[0], dict)):
                return {"status": "error", "message": "Los pagos no se pudieron interpretar correctamente."}

            return {"status": "success", "data": result}

        except Exception as e:
            return {"status": "error", "message": f"Error al obtener pagos pagados: {e}"}




    def crear_sp_horas_trabajadas_para_pagos(self):
        """
        Crea el stored procedure 'horas_trabajadas_para_pagos' si no existe.
        Este procedimiento usa el campo correcto 'tiempo_trabajo' de la tabla asistencias.
        """
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
                existente = self.db.get_data(
                    query,
                    (numero_nomina, fecha_inicio, fecha_fin),
                    dictionary=True,
                )

                if existente and isinstance(existente, list) and existente[0]["c"] > 0:
                    continue  # Ya tiene un pago confirmado en ese rango

                sueldo_hora = float(emp.get("sueldo_por_hora", 0))
                if sueldo_hora <= 0:
                    errores += 1
                    continue

                resultado = self.get_total_horas_trabajadas(fecha_inicio, fecha_fin, numero_nomina)
                if (
                    resultado["status"] != "success"
                    or not resultado["data"]
                    or "total_horas_trabajadas" not in resultado["data"][0]
                ):
                    errores += 1
                    continue

                tiempo_str = resultado["data"][0]["total_horas_trabajadas"]
                try:
                    h, m, s = map(int, tiempo_str.split(":"))
                except ValueError:
                    errores += 1
                    continue

                horas_decimales = round(h + m / 60 + s / 3600, 2)
                monto_base = round(sueldo_hora * horas_decimales, 2)

                insert_pago = f"""
                    INSERT INTO {E_PAYMENT.TABLE.value}
                    ({E_PAYMENT.NUMERO_NOMINA.value}, {E_PAYMENT.FECHA_PAGO.value},
                    {E_PAYMENT.TOTAL_HORAS_TRABAJADAS.value}, {E_PAYMENT.MONTO_BASE.value},
                    {E_PAYMENT.MONTO_TOTAL.value}, {E_PAYMENT.PAGO_DEPOSITO.value},
                    {E_PAYMENT.PAGO_EFECTIVO.value})
                    VALUES (%s, CURDATE(), %s, %s, %s, %s, %s)
                """
                self.db.run_query(
                    insert_pago,
                    (numero_nomina, horas_decimales, monto_base, monto_base, 0.0, monto_base),
                )

                id_pago = self.db.get_last_insert_id()

                self.discount_model.agregar_descuentos_opcionales(
                    numero_nomina=numero_nomina,
                    id_pago=id_pago,
                    aplicar_imss=True,
                    aplicar_transporte=True,
                    aplicar_comida=True,
                    estado_comida="media",
                )

                total_descuentos = self.discount_model.get_total_descuentos_por_pago(id_pago)
                monto_final = max(0, monto_base - total_descuentos)

                self.update_pago(
                    id_pago,
                    {
                        E_PAYMENT.MONTO_TOTAL.value: monto_final,
                        E_PAYMENT.PAGO_EFECTIVO.value: monto_final,
                    },
                )

                pagos_generados += 1

            self.assistance_model.marcar_asistencias_como_generadas(fecha_inicio, fecha_fin)

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

    def existe_pago_para_fecha(self, numero_nomina: int, fecha: str, incluir_pendientes=False) -> bool:
        try:
            if incluir_pendientes:
                query = f"""
                    SELECT COUNT(*) AS c
                    FROM {E_PAYMENT.TABLE.value}
                    WHERE {E_PAYMENT.NUMERO_NOMINA.value} = %s
                    AND {E_PAYMENT.FECHA_PAGO.value} = %s
                """
                params = (numero_nomina, fecha)
            else:
                query = f"""
                    SELECT COUNT(*) AS c
                    FROM {E_PAYMENT.TABLE.value}
                    WHERE {E_PAYMENT.NUMERO_NOMINA.value} = %s
                    AND {E_PAYMENT.FECHA_PAGO.value} = %s
                    AND {E_PAYMENT.ESTADO.value} = 'pagado'
                """
                params = (numero_nomina, fecha)

            res = self.db.get_data(query, params, dictionary=True)
            return res.get("c", 0) > 0
        except:
            return False


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


    def update_pago_completo(self, id_pago: int, descuentos: dict, estado: str = "pagado") -> dict:
        try:
            # Validar tipo de entrada
            if not isinstance(id_pago, int) or not isinstance(descuentos, dict):
                return {"status": "error", "message": "Parámetros inválidos para actualizar el pago."}

            pago = self.get_by_id(id_pago)

            if pago["status"] != "success" or not pago.get("data") or not isinstance(pago["data"], dict):
                return {"status": "error", "message": f"Pago ID {id_pago} no encontrado o inválido."}

            monto_base = float(pago["data"].get("monto_base", 0.0))
            if monto_base <= 0:
                return {"status": "error", "message": "Monto base inválido o no definido."}

            self.discount_model.actualizar_descuentos(id_pago, descuentos)

            total_descuentos = self.discount_model.get_total_descuentos_por_pago(id_pago)
            monto_final = max(0.0, monto_base - total_descuentos)

            campos_actualizados = {
                E_PAYMENT.MONTO_TOTAL.value: monto_final,
                E_PAYMENT.PAGO_EFECTIVO.value: monto_final,
                E_PAYMENT.ESTADO.value: estado
            }
            return self.update_pago(id_pago, campos_actualizados)

        except Exception as ex:
            print(f"❌ Error en update_pago_completo: {ex}")
            return {"status": "error", "message": str(ex)}




    def update_pago(self, id_pago: int, campos_actualizados: dict):
        try:
            campos_sql = ", ".join([f"{campo} = %s" for campo in campos_actualizados.keys()])
            valores = list(campos_actualizados.values()) + [id_pago]
            query = f"""
            UPDATE pagos
            SET {campos_sql}
            WHERE id_pago = %s
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

    def get_fechas_utilizadas(self) -> list[date]:
        """Obtiene una lista de fechas ya utilizadas para generar pagos."""
        try:
            query = f"SELECT DISTINCT {E_PAYMENT.FECHA_PAGO.value} FROM {E_PAYMENT.TABLE.value}"
            resultados = self.db.get_data_list(query, dictionary=True)
            fechas = []
            for row in resultados:
                fecha = row.get(E_PAYMENT.FECHA_PAGO.value)
                if isinstance(fecha, str):
                    fecha = datetime.strptime(fecha, "%Y-%m-%d").date()
                if isinstance(fecha, date):
                    fechas.append(fecha)
            return fechas
        except Exception as ex:
            print(f"❌ Error al obtener fechas utilizadas: {ex}")
            return []
