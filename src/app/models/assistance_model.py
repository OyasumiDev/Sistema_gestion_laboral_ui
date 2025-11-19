from app.core.enums.e_assistance_model import E_ASSISTANCE
from app.core.interfaces.database_mysql import DatabaseMysql
from app.models.payment_model import PaymentModel
from datetime import date, datetime, timedelta
from typing import Optional
import pandas as pd 
from datetime import time
from datetime import datetime, date
from typing import List, Tuple
from app.core.app_state import AppState  # CHANGE: publicar eventos a page.pubsub
    
class AssistanceModel:
    def __init__(self):
        self.db = DatabaseMysql()
        self.payment_model = PaymentModel()
        self._exists_table = self.check_table()
        self.verificar_o_crear_triggers()

    def _publish_pagamentos_delta(self, numero_nomina: int, periodo_ini: str, periodo_fin: str) -> None:
        # CHANGE: difunde cambios relevantes a través de page.pubsub
        page = AppState().page
        if not page:
            return
        pubsub = getattr(page, "pubsub", None)
        if not pubsub:
            return
        payload = {
            "id_empleado": int(numero_nomina),
            "periodo_ini": periodo_ini,
            "periodo_fin": periodo_fin,
        }
        try:
            if hasattr(pubsub, "publish"):
                pubsub.publish("asistencias:changed", payload)
            elif hasattr(pubsub, "send_all"):
                pubsub.send_all("asistencias:changed", payload)
        except Exception:
            pass


    def check_table(self) -> bool:
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, E_ASSISTANCE.TABLE.value), dictionary=True)
            existe = result.get("c", 0) > 0

            if not existe:
                print(f"⚠️ La tabla {E_ASSISTANCE.TABLE.value} no existe. Creando...")

                create_query = f"""
                CREATE TABLE IF NOT EXISTS {E_ASSISTANCE.TABLE.value} (
                    {E_ASSISTANCE.ID_ASISTENCIA.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {E_ASSISTANCE.NUMERO_NOMINA.value} SMALLINT UNSIGNED NOT NULL,
                    {E_ASSISTANCE.FECHA.value} DATE NOT NULL,
                    {E_ASSISTANCE.HORA_ENTRADA.value} TIME,
                    {E_ASSISTANCE.HORA_SALIDA.value} TIME,
                    {E_ASSISTANCE.DESCANSO.value} TINYINT DEFAULT 0,
                    {E_ASSISTANCE.ESTADO.value} VARCHAR(20),
                    {E_ASSISTANCE.TIEMPO_TRABAJO.value} DECIMAL(5,2) DEFAULT 0.00,
                    {E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value} DECIMAL(5,2) DEFAULT 0.00,
                    {E_ASSISTANCE.FECHA_GENERADA.value} DATE DEFAULT NULL,
                    {E_ASSISTANCE.GRUPO_IMPORTACION.value} VARCHAR(150) DEFAULT NULL,
                    FOREIGN KEY ({E_ASSISTANCE.NUMERO_NOMINA.value}) REFERENCES empleados(numero_nomina) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {E_ASSISTANCE.TABLE.value} creada correctamente.")
            else:
                # Validar columnas necesarias y su tipo correcto
                columnas_requeridas = {
                    E_ASSISTANCE.DESCANSO.value: "TINYINT DEFAULT 0",
                    E_ASSISTANCE.GRUPO_IMPORTACION.value: "VARCHAR(150) DEFAULT NULL",
                    E_ASSISTANCE.TIEMPO_TRABAJO.value: "DECIMAL(5,2) DEFAULT 0.00",
                    E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value: "DECIMAL(5,2) DEFAULT 0.00",
                }

                for columna, tipo in columnas_requeridas.items():
                    check_col_query = """
                        SELECT DATA_TYPE, COLUMN_TYPE
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s AND column_name = %s
                    """
                    col_result = self.db.get_data(
                        check_col_query,
                        (self.db.database, E_ASSISTANCE.TABLE.value, columna),
                        dictionary=True,
                    )

                    if not col_result:
                        alter_query = f"ALTER TABLE {E_ASSISTANCE.TABLE.value} ADD COLUMN {columna} {tipo}"
                        self.db.run_query(alter_query)
                        print(f"🛠️ Columna '{columna}' agregada como {tipo}.")
                    else:
                        # Si existe pero con tipo incorrecto, forzamos el cambio
                        current_type = col_result.get("COLUMN_TYPE", "").upper()
                        expected_type = tipo.upper()
                        if expected_type not in current_type:
                            alter_query = f"ALTER TABLE {E_ASSISTANCE.TABLE.value} MODIFY COLUMN {columna} {tipo}"
                            self.db.run_query(alter_query)
                            print(f"🔄 Columna '{columna}' actualizada a {tipo}.")
                        else:
                            print(f"✔️ Columna '{columna}' ya existe con el tipo correcto.")

            return True

        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {E_ASSISTANCE.TABLE.value}: {ex}")
            return False


    def verificar_o_crear_triggers(self):
        try:
            self._crear_trigger_calculo_horas()
            self._crear_trigger_actualizar_horas()
            self._crear_trigger_estado()
        except Exception as ex:
            print(f"❌ Error al verificar/crear triggers: {ex}")


    def _crear_trigger_calculo_horas(self):
        trigger_name = "trg_calcular_horas_trabajadas"
        check_query = """
            SELECT COUNT(*) AS c
            FROM information_schema.triggers
            WHERE trigger_schema = %s AND trigger_name = %s
        """
        result = self.db.get_data(check_query, (self.db.database, trigger_name), dictionary=True)
        if result.get("c", 0) == 0:
            print(f"⚠️ Trigger '{trigger_name}' no existe. Creando...")

            cursor = self.db.connection.cursor()
            cursor.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")

            trigger_sql = """
            CREATE TRIGGER trg_calcular_horas_trabajadas
            BEFORE INSERT ON asistencias
            FOR EACH ROW
            BEGIN
                DECLARE minutos_descanso INT DEFAULT 0;
                DECLARE minutos_trabajo INT;

                IF NEW.hora_entrada IS NOT NULL AND NEW.hora_entrada NOT IN ('00:00:00', '0:00:00')
                AND NEW.hora_salida IS NOT NULL AND NEW.hora_salida NOT IN ('00:00:00', '0:00:00') THEN

                    SET minutos_trabajo = TIME_TO_SEC(TIMEDIFF(NEW.hora_salida, NEW.hora_entrada)) / 60;
                    IF minutos_trabajo < 0 THEN
                        SET minutos_trabajo = 0;
                    END IF;

                    -- BRUTO en horas decimales
                    SET NEW.tiempo_trabajo_con_descanso = TRUNCATE(minutos_trabajo / 60, 2);

                    -- Descanso: 2=60min, 1=30min, 0/NULL => si jornada >= 6h, default 30min
                    IF NEW.descanso = 2 THEN
                        SET minutos_descanso = 60;
                    ELSEIF NEW.descanso = 1 THEN
                        SET minutos_descanso = 30;
                    ELSE
                        IF minutos_trabajo >= 360 THEN
                            SET minutos_descanso = 30;
                        ELSE
                            SET minutos_descanso = 0;
                        END IF;
                    END IF;

                    -- NETO en horas decimales
                    SET minutos_trabajo = GREATEST(0, minutos_trabajo - minutos_descanso);
                    SET NEW.tiempo_trabajo = TRUNCATE(minutos_trabajo / 60, 2);
                ELSE
                    SET NEW.tiempo_trabajo = 0.00;
                    SET NEW.tiempo_trabajo_con_descanso = 0.00;
                END IF;
            END;
            """
            cursor.execute(trigger_sql)
            self.db.connection.commit()
            cursor.close()

            print(f"✅ Trigger '{trigger_name}' creado correctamente.")
        else:
            print(f"✔️ Trigger '{trigger_name}' ya existe.")


    def _crear_trigger_actualizar_horas(self):
        trigger_name = "trg_actualizar_horas_trabajadas"
        check_query = """
            SELECT COUNT(*) AS c
            FROM information_schema.triggers
            WHERE trigger_schema = %s AND trigger_name = %s
        """
        result = self.db.get_data(check_query, (self.db.database, trigger_name), dictionary=True)
        if result.get("c", 0) == 0:
            print(f"⚠️ Trigger '{trigger_name}' no existe. Creando...")

            cursor = self.db.connection.cursor()
            cursor.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")

            trigger_sql = """
            CREATE TRIGGER trg_actualizar_horas_trabajadas
            BEFORE UPDATE ON asistencias
            FOR EACH ROW
            BEGIN
                DECLARE minutos_descanso INT DEFAULT 0;
                DECLARE minutos_trabajo INT;

                IF NEW.hora_entrada IS NOT NULL AND NEW.hora_entrada NOT IN ('00:00:00', '0:00:00')
                AND NEW.hora_salida IS NOT NULL AND NEW.hora_salida NOT IN ('00:00:00', '0:00:00') THEN

                    SET minutos_trabajo = TIME_TO_SEC(TIMEDIFF(NEW.hora_salida, NEW.hora_entrada)) / 60;
                    IF minutos_trabajo < 0 THEN
                        SET minutos_trabajo = 0;
                    END IF;

                    -- BRUTO
                    SET NEW.tiempo_trabajo_con_descanso = TRUNCATE(minutos_trabajo / 60, 2);

                    -- Descanso: 2=60min, 1=30min, 0/NULL => si jornada >= 6h, default 30min
                    IF NEW.descanso = 2 THEN
                        SET minutos_descanso = 60;
                    ELSEIF NEW.descanso = 1 THEN
                        SET minutos_descanso = 30;
                    ELSE
                        IF minutos_trabajo >= 360 THEN
                            SET minutos_descanso = 30;
                        ELSE
                            SET minutos_descanso = 0;
                        END IF;
                    END IF;

                    -- NETO
                    SET minutos_trabajo = GREATEST(0, minutos_trabajo - minutos_descanso);
                    SET NEW.tiempo_trabajo = TRUNCATE(minutos_trabajo / 60, 2);
                ELSE
                    SET NEW.tiempo_trabajo = 0.00;
                    SET NEW.tiempo_trabajo_con_descanso = 0.00;
                END IF;
            END;
            """
            cursor.execute(trigger_sql)
            self.db.connection.commit()
            cursor.close()

            print(f"✅ Trigger '{trigger_name}' creado correctamente.")
        else:
            print(f"✔️ Trigger '{trigger_name}' ya existe.")


    def _crear_trigger_estado(self):
        try:
            cursor = self.db.connection.cursor()

            # BEFORE INSERT
            trigger_name_bi = "trg_verificar_estado_asistencia_bi"
            check_sql = """
                SELECT COUNT(*) AS c
                FROM information_schema.triggers
                WHERE trigger_schema = %s AND trigger_name = %s
            """
            r_bi = self.db.get_data(check_sql, (self.db.database, trigger_name_bi), dictionary=True) or {}
            if (r_bi.get("c") or 0) == 0:
                print(f"⚠️ Trigger '{trigger_name_bi}' no existe. Creando...")
                cursor.execute(f"DROP TRIGGER IF EXISTS {trigger_name_bi}")
                trigger_sql_bi = """
                CREATE TRIGGER trg_verificar_estado_asistencia_bi
                BEFORE INSERT ON asistencias
                FOR EACH ROW
                BEGIN
                    IF NEW.hora_entrada IS NULL OR NEW.hora_salida IS NULL
                    OR NEW.hora_entrada IN ('00:00:00','0:00:00')
                    OR NEW.hora_salida  IN ('00:00:00','0:00:00')
                    OR TIMEDIFF(NEW.hora_salida, NEW.hora_entrada) <= '00:00:00' THEN
                        SET NEW.estado = 'incompleto';
                    ELSE
                        SET NEW.estado = 'completo';
                    END IF;
                END;
                """
                cursor.execute(trigger_sql_bi)
                self.db.connection.commit()
                print(f"✅ Trigger '{trigger_name_bi}' creado correctamente.")
            else:
                print(f"✔️ Trigger '{trigger_name_bi}' ya existe.")

            # BEFORE UPDATE
            trigger_name_bu = "trg_verificar_estado_asistencia_bu"
            r_bu = self.db.get_data(check_sql, (self.db.database, trigger_name_bu), dictionary=True) or {}
            if (r_bu.get("c") or 0) == 0:
                print(f"⚠️ Trigger '{trigger_name_bu}' no existe. Creando...")
                cursor.execute(f"DROP TRIGGER IF EXISTS {trigger_name_bu}")
                trigger_sql_bu = """
                CREATE TRIGGER trg_verificar_estado_asistencia_bu
                BEFORE UPDATE ON asistencias
                FOR EACH ROW
                BEGIN
                    IF NEW.hora_entrada IS NULL OR NEW.hora_salida IS NULL
                    OR NEW.hora_entrada IN ('00:00:00','0:00:00')
                    OR NEW.hora_salida  IN ('00:00:00','0:00:00')
                    OR TIMEDIFF(NEW.hora_salida, NEW.hora_entrada) <= '00:00:00' THEN
                        SET NEW.estado = 'incompleto';
                    ELSE
                        SET NEW.estado = 'completo';
                    END IF;
                END;
                """
                cursor.execute(trigger_sql_bu)
                self.db.connection.commit()
                print(f"✅ Trigger '{trigger_name_bu}' creado correctamente.")
            else:
                print(f"✔️ Trigger '{trigger_name_bu}' ya existe.")
        except Exception as ex:
            print(f"❌ Error al verificar/crear triggers de estado: {ex}")
        finally:
            try:
                cursor.close()
            except Exception:
                pass

    def collect_ranges_for_period(
        self,
        periodo_ini: str,
        periodo_fin: str,
        id_empleado: Optional[int] = None,
    ) -> List[Tuple[int, str, str]]:
        # CHANGE: agrupa asistencias en rangos compactos por empleado
        condiciones = []
        params: list = []

        if periodo_ini and periodo_fin:
            condiciones.append(f"{E_ASSISTANCE.FECHA.value} BETWEEN %s AND %s")
            params.extend([periodo_ini, periodo_fin])
        elif periodo_ini:
            condiciones.append(f"{E_ASSISTANCE.FECHA.value} >= %s")
            params.append(periodo_ini)
        elif periodo_fin:
            condiciones.append(f"{E_ASSISTANCE.FECHA.value} <= %s")
            params.append(periodo_fin)

        if id_empleado:
            condiciones.append(f"{E_ASSISTANCE.NUMERO_NOMINA.value} = %s")
            params.append(id_empleado)

        where_clause = " AND ".join(condiciones) if condiciones else "1=1"
        q = f"""
            SELECT
                {E_ASSISTANCE.NUMERO_NOMINA.value} AS numero_nomina,
                MIN({E_ASSISTANCE.FECHA.value}) AS fecha_inicio,
                MAX({E_ASSISTANCE.FECHA.value}) AS fecha_fin
            FROM {E_ASSISTANCE.TABLE.value}
            WHERE {where_clause}
            GROUP BY {E_ASSISTANCE.NUMERO_NOMINA.value}
        """
        rows = self.db.get_data_list(q, tuple(params), dictionary=True) or []
        rangos: List[Tuple[int, str, str]] = []
        for row in rows:
            numero = int(row.get("numero_nomina") or 0)
            if numero <= 0:
                continue
            fi = row.get("fecha_inicio")
            ff = row.get("fecha_fin")
            fi_str = fi.strftime("%Y-%m-%d") if hasattr(fi, "strftime") else str(fi)
            ff_str = ff.strftime("%Y-%m-%d") if hasattr(ff, "strftime") else str(ff)
            rangos.append((numero, fi_str, ff_str))
        return rangos



    def add(
        self,
        numero_nomina: int,
        fecha: str,
        hora_entrada: str = None,
        hora_salida: str = None,
        descanso: int = 0,
        grupo_importacion: str = None,
    ):
        """Inserta una asistencia y sincroniza pagos relacionados."""
        try:
            def limpiar_y_parsear_hora(hora, campo):
                if isinstance(hora, timedelta):
                    return (datetime.min + hora).time().strftime("%H:%M:%S")
                if isinstance(hora, str) and ":" in hora:
                    return hora.strip()
                print(f"[WARN] {campo} invalida para {numero_nomina} - {fecha}, se asigna 00:00:00")
                return "00:00:00"

            hora_entrada = limpiar_y_parsear_hora(hora_entrada, "Hora Entrada")
            hora_salida = limpiar_y_parsear_hora(hora_salida, "Hora Salida")
            fecha_mysql = self._convertir_fecha_a_mysql(fecha)

            query = """
                INSERT INTO asistencias (
                    numero_nomina, fecha, hora_entrada, hora_salida, descanso,
                    estado, tiempo_trabajo, tiempo_trabajo_con_descanso, fecha_generada, grupo_importacion
                ) VALUES (%s, %s, %s, %s, %s, NULL, NULL, NULL, NULL, %s)
            """

            params = (
                numero_nomina,
                fecha_mysql,
                hora_entrada,
                hora_salida,
                descanso,
                grupo_importacion,
            )

            print(f"[INFO] Parametros INSERT asistencia: {params}")
            self.db.run_query(query, params)
            print("[INFO] Asistencia registrada correctamente.")

            sync = self.payment_model.sincronizar_desde_asistencia(numero_nomina, fecha_mysql)
            self._publish_pagamentos_delta(numero_nomina, fecha_mysql, fecha_mysql)  # CHANGE: notificar delta a Pagos
            return {"status": "success", "sync": sync}

        except Exception as ex:
            print(f"[ERROR] Error al agregar asistencia: {ex}")
            return {"status": "error", "message": str(ex)}

    def add_manual_assistance(
        self,
        numero_nomina: int,
        fecha: str,
        hora_entrada: str,
        hora_salida: str,
        descanso: int = 0,
        grupo_importacion: str = None
    ):
        try:
            if not all(isinstance(h, str) for h in [hora_entrada, hora_salida]):
                raise ValueError("Las horas deben ser cadenas en formato HH:MM:SS")

            try:
                h_entrada = datetime.strptime(hora_entrada, "%H:%M:%S")
                h_salida = datetime.strptime(hora_salida, "%H:%M:%S")
            except ValueError:
                raise ValueError("Formato de hora invalido. Usa HH:MM:SS")

            if h_salida <= h_entrada:
                raise ValueError("La hora de salida debe ser mayor que la de entrada")

            if descanso not in (0, 1, 2):
                print(f"[WARN] Descanso invalido ({descanso}), se usara 0.")
                descanso = 0

            fecha_mysql = self._convertir_fecha_a_mysql(fecha)

            query_check = f"""
                SELECT COUNT(*) AS existe
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.NUMERO_NOMINA.value} = %s AND {E_ASSISTANCE.FECHA.value} = %s
            """
            resultado = self.db.get_data(query_check, (numero_nomina, fecha_mysql), dictionary=True)
            if resultado.get("existe", 0) > 0:
                return {"status": "error", "message": "Ya existe una asistencia registrada para ese empleado en esa fecha"}

            query_insert = f"""
                INSERT INTO {E_ASSISTANCE.TABLE.value} (
                    {E_ASSISTANCE.NUMERO_NOMINA.value},
                    {E_ASSISTANCE.FECHA.value},
                    {E_ASSISTANCE.HORA_ENTRADA.value},
                    {E_ASSISTANCE.HORA_SALIDA.value},
                    {E_ASSISTANCE.DESCANSO.value},
                    {E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value},
                    {E_ASSISTANCE.GRUPO_IMPORTACION.value}
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(
                query_insert,
                (numero_nomina, fecha_mysql, hora_entrada, hora_salida, descanso, None, grupo_importacion)
            )
            print("OK. Asistencia manual agregada correctamente.")

            sync = self.payment_model.sincronizar_desde_asistencia(numero_nomina, fecha_mysql)
            self._publish_pagamentos_delta(numero_nomina, fecha_mysql, fecha_mysql)  # CHANGE: notificar delta en inserción manual
            return {
                "status": "success",
                "message": "Asistencia agregada correctamente",
                "sync": sync,
            }

        except Exception as e:
            print(f"[ERROR] Error en add_manual_assistance: {e}")
            return {"status": "error", "message": str(e)}

    def update_asistencia(self, registro: dict) -> dict:
        try:
            print(f"[INFO] Ejecutando UPDATE con datos: {registro}")

            def formatear_hora(hora_valor):
                from datetime import time, timedelta, datetime as dt
                if isinstance(hora_valor, time):
                    return hora_valor.strftime("%H:%M:%S")
                if isinstance(hora_valor, timedelta):
                    total_seconds = int(hora_valor.total_seconds())
                    horas = total_seconds // 3600
                    minutos = (total_seconds % 3600) // 60
                    segundos = total_seconds % 60
                    return f"{horas:02}:{minutos:02}:{segundos:02}"
                if isinstance(hora_valor, str):
                    for fmt in ("%H:%M:%S", "%H:%M"):
                        try:
                            return dt.strptime(hora_valor.strip(), fmt).strftime("%H:%M:%S")
                        except Exception:
                            continue
                return "00:00:00"

            fecha_mysql = self._convertir_fecha_a_mysql(registro.get("fecha"))
            numero_nomina = int(registro.get("numero_nomina") or 0)

            query = """
                UPDATE asistencias
                SET 
                    hora_entrada = %s,
                    hora_salida  = %s,
                    descanso     = %s
                WHERE numero_nomina = %s AND fecha = %s
            """

            params = (
                formatear_hora(registro.get("hora_entrada")),
                formatear_hora(registro.get("hora_salida")),
                self._mapear_descanso_str_a_int(registro.get("descanso", "SN")),
                numero_nomina,
                fecha_mysql,
            )

            print(f"[INFO] Parametros finales para UPDATE: {params}")
            self.db.run_query(query, params)
            print("OK. Actualizacion realizada correctamente.")

            sync = self.payment_model.sincronizar_desde_asistencia(numero_nomina, fecha_mysql)
            self._publish_pagamentos_delta(numero_nomina, fecha_mysql, fecha_mysql)  # CHANGE: informar delta tras actualización
            return {"status": "success", "sync": sync}

        except Exception as e:
            print(f"[ERROR] Error al actualizar asistencia: {e}")
            return {"status": "error", "message": str(e)}

    def get_all(self) -> dict:
        try:
            query = f"""
            SELECT a.*, e.nombre_completo
            FROM {E_ASSISTANCE.TABLE.value} a
            JOIN empleados e ON a.numero_nomina = e.numero_nomina
            ORDER BY a.fecha ASC
            """
            result = self.db.get_data_list(query, dictionary=True)

            for row in result:
                self._mapear_fila_asistencia(row)

            print(f"✅ {len(result)} registros obtenidos correctamente.")
            return {"status": "success", "data": result}

        except Exception as ex:
            print(f"❌ Error al obtener asistencias: {ex}")
            return {"status": "error", "message": f"Error al obtener asistencias: {ex}"}



    def get_by_id(self, id_asistencia: int) -> dict:
        try:
            query = f"""
                SELECT * FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.ID_ASISTENCIA.value} = %s
            """
            result = self.db.get_data(query, (id_asistencia,), dictionary=True)

            if result:
                result = self._mapear_fila_asistencia(result)
                print(f"✅ Asistencia obtenida por ID {id_asistencia}: {result}")
                return {"status": "success", "data": result}

            print(f"ℹ️ No se encontró asistencia para ID {id_asistencia}")
            return {"status": "error", "message": "Asistencia no encontrada"}

        except Exception as ex:
            print(f"❌ Error al obtener asistencia por ID: {ex}")
            return {"status": "error", "message": str(ex)}



    def get_by_empleado_fecha(self, numero_nomina: int, fecha: str) -> dict | None:
        try:
            if "/" in fecha:
                fecha = datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")

            query = f"""
                SELECT * FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.NUMERO_NOMINA.value} = %s AND {E_ASSISTANCE.FECHA.value} = %s
            """
            result = self.db.get_data(query, (numero_nomina, fecha), dictionary=True)

            if result:
                self._mapear_fila_asistencia(result)
                print(f"✅ Asistencia encontrada para {numero_nomina} en {fecha}")
                return result

            print(f"ℹ️ No se encontró asistencia para {numero_nomina} en {fecha}")
            return None

        except Exception as ex:
            print(f"❌ Error al obtener asistencia por empleado y fecha: {ex}")
            return None



    def delete_by_numero_nomina_and_fecha(self, numero_nomina: int, fecha: str) -> dict:
        try:
            # Convertir a formato compatible con MySQL (YYYY-MM-DD)
            fecha_sql = datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")

            query = """
                DELETE FROM asistencias
                WHERE numero_nomina = %s AND fecha = %s
            """
            self.db.run_query(query, (numero_nomina, fecha_sql))
            self._publish_pagamentos_delta(numero_nomina, fecha_sql, fecha_sql)  # CHANGE: propagar eliminación a Pagos
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


    def get_ultimo_id(self):
        try:
            query = "SELECT MAX(numero_nomina) AS ultimo FROM asistencias"
            result = self.db.get_data(query, dictionary=True)
            return int(result.get("ultimo", 0)) if result else 0
        except Exception as e:
            print(f"❌ Error al obtener último ID: {e}")
            return 0


    def actualizar_horas_manualmente(self, numero_nomina, fecha, hora_entrada, hora_salida):
        try:
            if not all(isinstance(h, str) for h in [hora_entrada, hora_salida]):
                raise ValueError("Las horas deben ser texto en formato HH:MM:SS")

            h_ent = datetime.strptime(hora_entrada, "%H:%M:%S")
            h_sal = datetime.strptime(hora_salida, "%H:%M:%S")
            if h_sal <= h_ent:
                raise ValueError("La hora de salida debe ser mayor que la de entrada")

            query = """
                UPDATE asistencias
                SET hora_entrada = %s,
                    hora_salida  = %s
                WHERE numero_nomina = %s AND fecha = %s
            """
            self.db.run_query(query, (hora_entrada, hora_salida, numero_nomina, fecha))
            return {"status": "success"}

        except Exception as e:
            return {"status": "error", "message": str(e)}



    def actualizar_estado_asistencia(self, numero_nomina: int, fecha: str) -> dict:
        try:
            query = """
            UPDATE asistencias
            SET estado = CASE
                WHEN hora_entrada IS NOT NULL AND hora_entrada != '00:00:00'
                AND hora_salida IS NOT NULL AND hora_salida != '00:00:00'
                THEN 'completo'
                ELSE 'incompleto'
            END
            WHERE numero_nomina = %s AND fecha = %s
            """
            self.db.run_query(query, (numero_nomina, fecha))
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


    def actualizar_asistencia_completa(self, numero_nomina, fecha, hora_entrada, hora_salida, estado, descanso: int = 0, tiempo_con_descanso: Optional[str] = None):
        """
        Mantén la firma por compatibilidad, pero deja que los triggers calculen
        estado y tiempos. Ignoramos 'estado' y 'tiempo_con_descanso' al persistir.
        """
        try:
            fecha_sql = datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")

            def parse_hora(hora):
                if isinstance(hora, timedelta):
                    return (datetime.min + hora).time().strftime("%H:%M:%S")
                if isinstance(hora, str) and ":" in hora:
                    return hora.strip()
                return "00:00:00"

            hora_entrada = parse_hora(hora_entrada)
            hora_salida  = parse_hora(hora_salida)

            query = """
                UPDATE asistencias
                SET hora_entrada = %s,
                    hora_salida  = %s,
                    descanso     = %s
                WHERE numero_nomina = %s AND fecha = %s
            """
            params = (hora_entrada, hora_salida, descanso, numero_nomina, fecha_sql)

            print(f"📝 Parámetros para UPDATE COMPLETO (con triggers): {params}")
            self.db.run_query(query, params)
            print("✅ Asistencia actualizada correctamente.")
            return {"status": "success"}

        except Exception as e:
            print(f"❌ Error al actualizar asistencia completa: {e}")
            return {"status": "error", "message": str(e)}


    def get_fecha_minima_asistencia(self) -> Optional[date]:
        try:
            query = f"SELECT MIN({E_ASSISTANCE.FECHA.value}) AS min_fecha FROM {E_ASSISTANCE.TABLE.value}"
            result = self.db.get_data(query, dictionary=True)

            print(f"🟡 Resultado crudo MIN fecha asistencia: {result}")

            if isinstance(result, list) and result:
                result = result[0]

            min_fecha = result.get("min_fecha") if result else None

            print(f"🔍 min_fecha recibida de base de datos: {min_fecha}")

            if isinstance(min_fecha, str):
                min_fecha = datetime.strptime(min_fecha, "%Y-%m-%d").date()

            print(f"✅ min_fecha convertida a datetime.date: {min_fecha}")
            return min_fecha
        except Exception as e:
            print(f"❌ Error al obtener fecha mínima de asistencia: {e}")
            return None


    def get_fecha_maxima_asistencia(self) -> Optional[date]:
        try:
            query = f"SELECT MAX({E_ASSISTANCE.FECHA.value}) AS max_fecha FROM {E_ASSISTANCE.TABLE.value}"
            result = self.db.get_data(query, dictionary=True)

            print(f"🟡 Resultado crudo MAX fecha asistencia: {result}")

            if isinstance(result, list) and result:
                result = result[0]

            max_fecha = result.get("max_fecha") if result else None

            print(f"🔍 max_fecha recibida de base de datos: {max_fecha}")

            if isinstance(max_fecha, str):
                max_fecha = datetime.strptime(max_fecha, "%Y-%m-%d").date()

            print(f"✅ max_fecha convertida a datetime.date: {max_fecha}")
            return max_fecha
        except Exception as e:
            print(f"❌ Error al obtener fecha máxima de asistencia: {e}")
            return None


    def marcar_asistencias_como_generadas(self, fecha_inicio: str, fecha_fin: str, fecha_generacion: Optional[str] = None) -> dict:
        try:
            fecha_generacion = fecha_generacion or datetime.today().strftime("%Y-%m-%d")
            query = """
                UPDATE asistencias
                SET fecha_generada = %s
                WHERE fecha BETWEEN %s AND %s
                AND estado = 'completo'
            """
            self.db.run_query(query, (fecha_generacion, fecha_inicio, fecha_fin))
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}



    def get_fechas_generadas(self) -> list:
        """
        Retorna todas las fechas de asistencias que ya fueron usadas para generar pagos.
        """
        try:
            query = "SELECT DISTINCT fecha FROM asistencias WHERE fecha_generada IS NOT NULL"
            resultados = self.db.get_data_list(query, dictionary=True)
            return [r["fecha"] for r in resultados if r.get("fecha")]
        except Exception as e:
            print(f"❌ Error al obtener fechas generadas: {e}")
            return []


    def _convertir_fecha_a_mysql(self, fecha: str) -> str:
        try:
            if "/" in fecha:
                return datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")
            return fecha
        except Exception as e:
            print(f"❌ Error formateando fecha para MySQL '{fecha}': {e}")
            return fecha


    def _mapear_descanso_str_a_int(self, descanso_str: str) -> int:
        mapa = {"SN": 0, "MD": 1, "CMP": 2}
        return mapa.get(descanso_str, 0)


    def _mapear_fila_asistencia(self, row: dict) -> dict:
        try:
            descanso_map = {0: "SN", 1: "MD", 2: "CMP"}

            if "fecha" in row:
                row["fecha"] = self._formatear_fecha(str(row["fecha"]))

            row["descanso"] = descanso_map.get(row.get("descanso", 0), "SN")

            # ✅ Corregido para validar vacíos y ceros
            tiempo_con_descanso = row.get("tiempo_trabajo_con_descanso")
            if not tiempo_con_descanso or str(tiempo_con_descanso).strip() in ("0", "0.00", "00:00:00"):
                row["tiempo_trabajo_con_descanso"] = row.get("tiempo_trabajo", "00:00:00")

            return row
        except Exception as e:
            print(f"❌ Error al mapear fila asistencia: {e}")
            return row


    def convertir_decimal_a_time(decimal_horas: float) -> str:
        try:
            total_segundos = int(decimal_horas * 3600)
            horas = total_segundos // 3600
            minutos = (total_segundos % 3600) // 60
            segundos = total_segundos % 60
            return f"{horas:02}:{minutos:02}:{segundos:02}"
        except Exception:
            return "00:00:00"


    def _formatear_fecha(self, fecha_sql: str) -> str:
        try:
            return datetime.strptime(fecha_sql, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return fecha_sql


    def get_fechas_disponibles_para_pago(self) -> List[date]:
        """
        Fechas (DISTINCT) con asistencias completas y que aún NO se han usado
        para nómina (fecha_generada IS NULL). Sirve para el DateModalSelector.
        """
        try:
            q = """
                SELECT DISTINCT fecha
                FROM asistencias
                WHERE estado = 'completo'
                AND fecha_generada IS NULL
                ORDER BY fecha ASC
            """
            rows = self.db.get_data_list(q, (), dictionary=True) or []
            out: List[date] = []
            for r in rows:
                f = r.get("fecha")
                if isinstance(f, date):
                    out.append(f)
                elif isinstance(f, str):
                    out.append(datetime.strptime(f, "%Y-%m-%d").date())
            return out
        except Exception as ex:
            print(f"❌ Error al obtener fechas disponibles para pago: {ex}")
            return []


    def get_fechas_disponibles_para_pago_por_empleado(self, numero_nomina: int) -> List[date]:
        """
        Igual que el anterior, pero filtrando por empleado.
        Útil si más adelante quieres generar por empleado específico.
        """
        try:
            q = """
                SELECT DISTINCT fecha
                FROM asistencias
                WHERE numero_nomina = %s
                AND estado = 'completo'
                AND fecha_generada IS NULL
                ORDER BY fecha ASC
            """
            rows = self.db.get_data_list(q, (numero_nomina,), dictionary=True) or []
            out: List[date] = []
            for r in rows:
                f = r.get("fecha")
                if isinstance(f, date):
                    out.append(f)
                elif isinstance(f, str):
                    out.append(datetime.strptime(f, "%Y-%m-%d").date())
            return out
        except Exception as ex:
            print(f"❌ Error al obtener fechas disponibles por empleado: {ex}")
            return []


    def get_fecha_minima_asistencia(self) -> Optional[date]:
        """
        Devuelve la fecha mínima registrada en asistencias como datetime.date.
        """
        try:
            query = f"SELECT MIN({E_ASSISTANCE.FECHA.value}) AS fi FROM {E_ASSISTANCE.TABLE.value}"
            result = self.db.get_data(query, dictionary=True)
            fi = result.get("fi") if result else None
            if isinstance(fi, str):
                fi = datetime.strptime(fi, "%Y-%m-%d").date()
            return fi
        except Exception as e:
            print(f"❌ Error al obtener fecha mínima de asistencia: {e}")
            return None


    def get_fecha_maxima_asistencia(self) -> Optional[date]:
        """
        Devuelve la fecha máxima registrada en asistencias como datetime.date.
        """
        try:
            query = f"SELECT MAX({E_ASSISTANCE.FECHA.value}) AS ff FROM {E_ASSISTANCE.TABLE.value}"
            result = self.db.get_data(query, dictionary=True)
            ff = result.get("ff") if result else None
            if isinstance(ff, str):
                ff = datetime.strptime(ff, "%Y-%m-%d").date()
            return ff
        except Exception as e:
            print(f"❌ Error al obtener fecha máxima de asistencia: {e}")
            return None


    def get_fechas_disponibles_para_pago(self) -> List[date]:
        """
        Fechas con asistencias completas y que aún NO se han usado en nómina (fecha_generada IS NULL).
        """
        try:
            q = f"""
                SELECT DISTINCT {E_ASSISTANCE.FECHA.value} AS fecha
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.ESTADO.value} = 'completo'
                AND {E_ASSISTANCE.FECHA_GENERADA.value} IS NULL
                ORDER BY fecha ASC
            """
            rows = self.db.get_data_list(q, dictionary=True) or []
            out: List[date] = []
            for r in rows:
                f = r.get("fecha")
                if isinstance(f, date):
                    out.append(f)
                elif isinstance(f, str):
                    out.append(datetime.strptime(f, "%Y-%m-%d").date())
            return out
        except Exception as ex:
            print(f"❌ Error al obtener fechas disponibles para pago: {ex}")
            return []


    def get_fechas_vacias(self, fi: date, ff: date) -> List[date]:
        """
        Retorna todas las fechas entre fi y ff que no tienen asistencias registradas.
        """
        try:
            if not fi or not ff:
                return []

            # Fechas ocupadas
            q = f"""
                SELECT DISTINCT {E_ASSISTANCE.FECHA.value} AS fecha
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.FECHA.value} BETWEEN %s AND %s
            """
            rows = self.db.get_data_list(q, (fi, ff), dictionary=True) or []
            ocupadas = set()
            for r in rows:
                f = r.get("fecha")
                if isinstance(f, date):
                    ocupadas.add(f)
                elif isinstance(f, str):
                    ocupadas.add(datetime.strptime(f, "%Y-%m-%d").date())

            # Generar rango completo y filtrar
            vacias = []
            cur = fi
            while cur <= ff:
                if cur not in ocupadas:
                    vacias.append(cur)
                cur += timedelta(days=1)

            return vacias
        except Exception as ex:
            print(f"❌ Error al obtener fechas vacías: {ex}")
            return []

    def marcar_asistencias_como_no_generadas(self, fecha_inicio, fecha_fin):
        q = "UPDATE asistencias SET fecha_generada = NULL WHERE fecha BETWEEN %s AND %s"
        self.db.run_query(q, (fecha_inicio, fecha_fin))


    def get_fechas_incompletas(
        self,
        fi: Optional[date] = None,
        ff: Optional[date] = None,
        numero_nomina: Optional[int] = None
    ) -> dict:
        """
        Retorna un diccionario {date: "incompleto"} con todas las fechas
        que contengan al menos una asistencia incompleta o con datos vacíos.
        - Soporta rango [fi, ff]
        - Soporta filtro opcional por empleado
        """
        try:
            params = []
            condiciones = ["1=1"]

            # Filtro por rango
            if fi and ff:
                condiciones.append(f"{E_ASSISTANCE.FECHA.value} BETWEEN %s AND %s")
                params.extend([fi, ff])

            # Filtro por empleado
            if numero_nomina:
                condiciones.append(f"{E_ASSISTANCE.NUMERO_NOMINA.value} = %s")
                params.append(numero_nomina)

            # Condiciones de incompletitud
            condiciones_incompletas = f"""
            (
                {E_ASSISTANCE.ESTADO.value} = 'incompleto'
                OR {E_ASSISTANCE.ESTADO.value} IS NULL
                OR {E_ASSISTANCE.ESTADO.value} = ''
                OR {E_ASSISTANCE.HORA_ENTRADA.value} IS NULL
                OR {E_ASSISTANCE.HORA_SALIDA.value} IS NULL
                OR {E_ASSISTANCE.HORA_ENTRADA.value} IN ('00:00:00','0:00:00')
                OR {E_ASSISTANCE.HORA_SALIDA.value}  IN ('00:00:00','0:00:00')
                OR TIMEDIFF({E_ASSISTANCE.HORA_SALIDA.value}, {E_ASSISTANCE.HORA_ENTRADA.value}) <= '00:00:00'
            )
            """

            q = f"""
                SELECT DISTINCT {E_ASSISTANCE.FECHA.value} AS fecha
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {" AND ".join(condiciones)}
                AND {condiciones_incompletas}
                ORDER BY {E_ASSISTANCE.FECHA.value} ASC
            """

            rows = self.db.get_data_list(q, tuple(params), dictionary=True) or []
            out = {}

            for r in rows:
                f = r.get("fecha")
                if isinstance(f, str):
                    f = datetime.strptime(f, "%Y-%m-%d").date()
                out[f] = "incompleto"

            print(f"✅ Fechas incompletas detectadas: {len(out)}")
            return out

        except Exception as ex:
            print(f"❌ Error al obtener fechas incompletas: {ex}")
            return {}


    def get_fechas_estado_completo_y_incompleto(
        self,
        fi: Optional[date] = None,
        ff: Optional[date] = None,
        numero_nomina: Optional[int] = None
    ) -> dict:
        """
        Devuelve {fecha: 'completo' | 'incompleto'} evaluando las horas reales,
        sin depender del campo 'estado' guardado (más preciso).
        """
        try:
            params = []
            condiciones = ["1=1"]

            if fi and ff:
                condiciones.append(f"{E_ASSISTANCE.FECHA.value} BETWEEN %s AND %s")
                params.extend([fi, ff])

            if numero_nomina:
                condiciones.append(f"{E_ASSISTANCE.NUMERO_NOMINA.value} = %s")
                params.append(numero_nomina)

            q = f"""
                SELECT DISTINCT {E_ASSISTANCE.FECHA.value} AS fecha,
                    CASE
                        WHEN {E_ASSISTANCE.HORA_ENTRADA.value} IS NOT NULL
                            AND {E_ASSISTANCE.HORA_SALIDA.value} IS NOT NULL
                            AND {E_ASSISTANCE.HORA_ENTRADA.value} NOT IN ('00:00:00','0:00:00')
                            AND {E_ASSISTANCE.HORA_SALIDA.value}  NOT IN ('00:00:00','0:00:00')
                            AND TIMEDIFF({E_ASSISTANCE.HORA_SALIDA.value}, {E_ASSISTANCE.HORA_ENTRADA.value}) > '00:00:00'
                        THEN 'completo'
                        ELSE 'incompleto'
                    END AS estado
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {" AND ".join(condiciones)}
                ORDER BY {E_ASSISTANCE.FECHA.value} ASC
            """

            rows = self.db.get_data_list(q, tuple(params), dictionary=True) or []
            out = {}

            for r in rows:
                f = r.get("fecha")
                estado = str(r.get("estado", "incompleto")).lower().strip()
                if isinstance(f, str):
                    f = datetime.strptime(f, "%Y-%m-%d").date()
                out[f] = estado

            print(f"✅ Fechas con estado recalculado: {len(out)}")
            return out

        except Exception as ex:
            print(f"❌ Error al obtener fechas por estado: {ex}")
            return {}


    def get_fechas_incompletas(
        self,
        fi: Optional[date] = None,
        ff: Optional[date] = None,
        numero_nomina: Optional[int] = None
    ) -> dict:
        """
        Retorna un diccionario {date: "incompleto"} con todas las fechas
        que contengan al menos una asistencia incompleta o con datos vacíos.
        - Soporta filtro por rango [fi, ff].
        - Soporta filtro opcional por empleado (numero_nomina).
        """
        try:
            params = []
            condiciones = ["1=1"]

            # Filtro por rango
            if fi and ff:
                condiciones.append(f"{E_ASSISTANCE.FECHA.value} BETWEEN %s AND %s")
                params.extend([fi, ff])

            # Filtro por empleado
            if numero_nomina:
                condiciones.append(f"{E_ASSISTANCE.NUMERO_NOMINA.value} = %s")
                params.append(numero_nomina)

            # Condiciones de incompletitud
            condiciones_incompletas = f"""
            (
                {E_ASSISTANCE.ESTADO.value} = 'incompleto'
                OR {E_ASSISTANCE.ESTADO.value} IS NULL
                OR {E_ASSISTANCE.ESTADO.value} = ''
                OR {E_ASSISTANCE.HORA_ENTRADA.value} IS NULL
                OR {E_ASSISTANCE.HORA_SALIDA.value} IS NULL
                OR {E_ASSISTANCE.HORA_ENTRADA.value} IN ('00:00:00','0:00:00')
                OR {E_ASSISTANCE.HORA_SALIDA.value}  IN ('00:00:00','0:00:00')
                OR TIMEDIFF({E_ASSISTANCE.HORA_SALIDA.value}, {E_ASSISTANCE.HORA_ENTRADA.value}) <= '00:00:00'
            )
            """

            q = f"""
                SELECT DISTINCT {E_ASSISTANCE.FECHA.value} AS fecha
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {" AND ".join(condiciones)}
                AND {condiciones_incompletas}
                ORDER BY {E_ASSISTANCE.FECHA.value} ASC
            """

            rows = self.db.get_data_list(q, tuple(params), dictionary=True) or []
            out = {}

            for r in rows:
                f = r.get("fecha")
                if isinstance(f, str):
                    f = datetime.strptime(f, "%Y-%m-%d").date()
                out[f] = "incompleto"

            print(f"✅ Fechas incompletas detectadas: {len(out)}")
            return out

        except Exception as ex:
            print(f"❌ Error al obtener fechas incompletas: {ex}")
            return {}


    def get_fechas_estado(self, fi: date = None, ff: date = None) -> dict:
        """
        Retorna un diccionario {date: estado} para todas las asistencias dentro del rango dado.
        Si no se especifica rango, devuelve todas.
        """
        try:
            params = []
            filtro = ""
            if fi and ff:
                filtro = f"AND {E_ASSISTANCE.FECHA.value} BETWEEN %s AND %s"
                params = [fi, ff]

            q = f"""
                SELECT {E_ASSISTANCE.FECHA.value} AS fecha, {E_ASSISTANCE.ESTADO.value} AS estado
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE 1=1 {filtro}
            """
            rows = self.db.get_data_list(q, tuple(params), dictionary=True) or []
            out = {}
            for r in rows:
                f = r.get("fecha")
                if isinstance(f, str):
                    f = datetime.strptime(f, "%Y-%m-%d").date()
                out[f] = r.get("estado", "").lower()
            return out
        except Exception as ex:
            print(f"❌ Error al obtener fechas con estado: {ex}")
            return {}

