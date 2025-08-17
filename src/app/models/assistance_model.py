from app.core.enums.e_assistance_model import E_ASSISTANCE
from app.core.interfaces.database_mysql import DatabaseMysql
from app.models.payment_model import PaymentModel
from datetime import date, datetime, timedelta
from typing import Optional
import pandas as pd 
from datetime import time
from datetime import datetime, date
from typing import List, Tuple
    
class AssistanceModel:
    def __init__(self):
        self.db = DatabaseMysql()
        self.payment_model = PaymentModel()
        self._exists_table = self.check_table()
        self.verificar_o_crear_triggers()


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
                    {E_ASSISTANCE.TIEMPO_TRABAJO.value} TIME,
                    {E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value} TIME,
                    {E_ASSISTANCE.FECHA_GENERADA.value} DATE DEFAULT NULL,
                    {E_ASSISTANCE.GRUPO_IMPORTACION.value} VARCHAR(150) DEFAULT NULL,
                    FOREIGN KEY ({E_ASSISTANCE.NUMERO_NOMINA.value}) REFERENCES empleados(numero_nomina) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {E_ASSISTANCE.TABLE.value} creada correctamente.")
            else:
                # Validar columnas necesarias
                columnas_requeridas = [
                    E_ASSISTANCE.GRUPO_IMPORTACION.value,
                    E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value
                ]

                for columna in columnas_requeridas:
                    check_col_query = """
                        SELECT COUNT(*) AS existe
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s AND column_name = %s
                    """
                    col_result = self.db.get_data(check_col_query, (self.db.database, E_ASSISTANCE.TABLE.value, columna), dictionary=True)
                    if col_result.get("existe", 0) == 0:
                        tipo = "VARCHAR(150) DEFAULT NULL" if columna == E_ASSISTANCE.GRUPO_IMPORTACION.value else "TIME"
                        alter_query = f"""
                            ALTER TABLE {E_ASSISTANCE.TABLE.value}
                            ADD COLUMN {columna} {tipo}
                        """
                        self.db.run_query(alter_query)
                        print(f"🛠️ Columna '{columna}' agregada a la tabla {E_ASSISTANCE.TABLE.value}.")
                    else:
                        print(f"✔️ Columna '{columna}' ya existe en {E_ASSISTANCE.TABLE.value}.")

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
                DECLARE entrada TIME;
                DECLARE salida TIME;
                DECLARE tiempo_bruto TIME;
                DECLARE minutos_descanso INT DEFAULT 0;
                DECLARE minutos_trabajo INT;

                IF NEW.hora_entrada IS NOT NULL AND NEW.hora_entrada NOT IN ('00:00:00', '0:00:00')
                AND NEW.hora_salida IS NOT NULL AND NEW.hora_salida NOT IN ('00:00:00', '0:00:00') THEN

                    SET entrada = NEW.hora_entrada;
                    SET salida = NEW.hora_salida;

                    IF salida <= entrada THEN
                        SET salida = ADDTIME(salida, '24:00:00');
                    END IF;

                    SET tiempo_bruto = TIMEDIFF(salida, entrada);
                    SET minutos_trabajo = TIME_TO_SEC(tiempo_bruto) / 60;

                    IF NEW.descanso = 1 THEN
                        SET minutos_descanso = 30;
                    ELSEIF NEW.descanso = 2 THEN
                        SET minutos_descanso = 60;
                    END IF;

                    SET minutos_trabajo = GREATEST(0, minutos_trabajo - minutos_descanso);
                    SET NEW.tiempo_trabajo = SEC_TO_TIME(minutos_trabajo * 60);
                ELSE
                    SET NEW.tiempo_trabajo = '00:00:00';
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
                DECLARE entrada TIME;
                DECLARE salida TIME;
                DECLARE tiempo_bruto TIME;
                DECLARE minutos_descanso INT DEFAULT 0;
                DECLARE minutos_trabajo INT;

                IF NEW.hora_entrada IS NOT NULL AND NEW.hora_entrada NOT IN ('00:00:00', '0:00:00')
                AND NEW.hora_salida IS NOT NULL AND NEW.hora_salida NOT IN ('00:00:00', '0:00:00') THEN

                    SET entrada = NEW.hora_entrada;
                    SET salida = NEW.hora_salida;

                    IF salida <= entrada THEN
                        SET salida = ADDTIME(salida, '24:00:00');
                    END IF;

                    SET tiempo_bruto = TIMEDIFF(salida, entrada);
                    SET minutos_trabajo = TIME_TO_SEC(tiempo_bruto) / 60;

                    IF NEW.descanso = 1 THEN
                        SET minutos_descanso = 30;
                    ELSEIF NEW.descanso = 2 THEN
                        SET minutos_descanso = 60;
                    END IF;

                    SET minutos_trabajo = GREATEST(0, minutos_trabajo - minutos_descanso);
                    SET NEW.tiempo_trabajo = SEC_TO_TIME(minutos_trabajo * 60);
                ELSE
                    SET NEW.tiempo_trabajo = '00:00:00';
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
        trigger_name = "trg_verificar_estado_asistencia"
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
            CREATE TRIGGER trg_verificar_estado_asistencia
            BEFORE INSERT ON asistencias
            FOR EACH ROW
            BEGIN
                IF NEW.hora_entrada IS NULL OR NEW.hora_salida IS NULL
                OR NEW.hora_entrada IN ('00:00:00', '0:00:00')
                OR NEW.hora_salida IN ('00:00:00', '0:00:00') THEN
                    SET NEW.estado = 'incompleto';
                ELSE
                    SET NEW.estado = 'completo';
                END IF;
            END;
            """

            cursor.execute(trigger_sql)
            self.db.connection.commit()
            cursor.close()

            print(f"✅ Trigger '{trigger_name}' creado correctamente.")
        else:
            print(f"✔️ Trigger '{trigger_name}' ya existe.")


    def add(self, numero_nomina: int, fecha: str, hora_entrada: str = None, hora_salida: str = None, descanso: int = 0, grupo_importacion: str = None):
        try:
            def limpiar_y_parsear_hora(hora, campo):
                if isinstance(hora, timedelta):
                    return (datetime.min + hora).time().strftime("%H:%M:%S")
                if isinstance(hora, str) and ":" in hora:
                    return hora.strip()
                print(f"⚠️ {campo} inválida para {numero_nomina} - {fecha}, se asigna 00:00:00")
                return "00:00:00"

            hora_entrada = limpiar_y_parsear_hora(hora_entrada, "Hora Entrada")
            hora_salida = limpiar_y_parsear_hora(hora_salida, "Hora Salida")

            query = """
                INSERT INTO asistencias (
                    numero_nomina, fecha, hora_entrada, hora_salida, descanso,
                    estado, tiempo_trabajo, tiempo_trabajo_con_descanso, fecha_generada, grupo_importacion
                ) VALUES (%s, %s, %s, %s, %s, NULL, NULL, NULL, NULL, %s)
            """

            params = (
                numero_nomina,
                fecha,
                hora_entrada,
                hora_salida,
                descanso,
                grupo_importacion
            )

            print(f"📝 Parámetros INSERT: {params}")
            self.db.run_query(query, params)
            print("✅ Asistencia registrada correctamente.")
            return {"status": "success"}

        except Exception as ex:
            print(f"❌ Error al agregar asistencia: {ex}")
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
                raise ValueError("Formato de hora inválido. Usa HH:MM:SS")

            if h_salida <= h_entrada:
                raise ValueError("La hora de salida debe ser mayor que la de entrada")

            if descanso not in (0, 1, 2):
                print(f"⚠️ Descanso inválido ({descanso}), se usará 0.")
                descanso = 0

            query_check = f"""
                SELECT COUNT(*) AS existe
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.NUMERO_NOMINA.value} = %s AND {E_ASSISTANCE.FECHA.value} = %s
            """
            resultado = self.db.get_data(query_check, (numero_nomina, fecha), dictionary=True)
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
            self.db.run_query(query_insert, (numero_nomina, fecha, hora_entrada, hora_salida, descanso, None, grupo_importacion))
            print("✅ Asistencia manual agregada correctamente.")
            return {"status": "success", "message": "Asistencia agregada correctamente"}

        except Exception as e:
            print(f"❌ Error en add_manual_assistance: {e}")
            return {"status": "error", "message": str(e)}


    def update_asistencia(self, registro: dict) -> dict:
        try:
            print(f"📤 Ejecutando UPDATE con datos: {registro}")

            def formatear_hora(hora_valor):
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
                            return datetime.strptime(hora_valor.strip(), fmt).strftime("%H:%M:%S")
                        except:
                            continue
                return "00:00:00"

            query = """
                UPDATE asistencias
                SET 
                    hora_entrada = %s,
                    hora_salida = %s,
                    descanso = %s,
                    estado = %s
                WHERE numero_nomina = %s AND fecha = %s
            """

            params = (
                formatear_hora(registro.get("hora_entrada")),
                formatear_hora(registro.get("hora_salida")),
                self._mapear_descanso_str_a_int(registro.get("descanso", "SN")),
                registro.get("estado"),
                registro.get("numero_nomina"),
                self._convertir_fecha_a_mysql(registro.get("fecha"))
            )

            print(f"📝 Parámetros finales para UPDATE: {params}")
            self.db.run_query(query, params)
            print("✅ Actualización realizada correctamente.")
            return {"status": "success"}

        except Exception as e:
            print(f"❌ Error al actualizar asistencia: {e}")
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
                    hora_salida = %s,
                    estado = CASE
                        WHEN %s != '00:00:00' AND %s != '00:00:00' THEN 'completo'
                        ELSE 'incompleto'
                    END
                WHERE numero_nomina = %s AND fecha = %s
            """
            self.db.run_query(query, (hora_entrada, hora_salida, hora_entrada, hora_salida, numero_nomina, fecha))
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
        try:
            fecha_sql = datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")

            def parse_hora(hora):
                if isinstance(hora, timedelta):
                    return (datetime.min + hora).time().strftime("%H:%M:%S")
                if isinstance(hora, str) and ":" in hora:
                    return hora.strip()
                return "00:00:00"

            hora_entrada = parse_hora(hora_entrada)
            hora_salida = parse_hora(hora_salida)

            if isinstance(tiempo_con_descanso, (float, int)):
                tiempo_con_descanso = self.convertir_decimal_a_time(tiempo_con_descanso)

            query = """
                UPDATE asistencias
                SET hora_entrada = %s,
                    hora_salida = %s,
                    estado = %s,
                    descanso = %s,
                    tiempo_trabajo_con_descanso = %s
                WHERE numero_nomina = %s AND fecha = %s
            """

            params = (
                hora_entrada,
                hora_salida,
                estado,
                descanso,
                tiempo_con_descanso,
                numero_nomina,
                fecha_sql
            )

            print(f"📝 Parámetros para UPDATE COMPLETO: {params}")
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
        """
        Marca las asistencias en el rango como utilizadas para generar pagos, asignando la fecha de generación.
        """
        try:
            fecha_generacion = fecha_generacion or datetime.today().strftime("%Y-%m-%d")
            query = """
                UPDATE asistencias
                SET fecha_generada = %s
                WHERE fecha BETWEEN %s AND %s
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



    def _get_fechas_disponibles(self) -> Tuple[List[date], List[date]]:
        """
        Devuelve (bloqueadas, disponibles) como listas de datetime.date ordenadas.
        - bloqueadas: fechas ya usadas en nómina (pagadas o pendientes).
        - disponibles: fechas con asistencias completas y NO usadas aún.
        """
        # 1) Bloqueadas desde pagos (string -> date)
        try:
            usadas = self.payment_model.get_fechas_utilizadas() or []
        except Exception:
            usadas = []
        bloqueadas_set = set()
        for f in usadas:
            if isinstance(f, date):
                bloqueadas_set.add(f)
            elif isinstance(f, str):
                try:
                    bloqueadas_set.add(datetime.strptime(f, "%Y-%m-%d").date())
                except Exception:
                    pass

        # 2) Disponibles desde asistencias (ya vienen como date o str)
        try:
            disp_raw = self.get_fechas_disponibles_para_pago() or []
        except Exception:
            disp_raw = []

        disponibles_set = set()
        for f in disp_raw:
            if isinstance(f, date):
                disponibles_set.add(f)
            elif isinstance(f, str):
                try:
                    disponibles_set.add(datetime.strptime(f, "%Y-%m-%d").date())
                except Exception:
                    pass

        # 3) Quita las bloqueadas de las disponibles
        disponibles_set -= bloqueadas_set

        bloqueadas = sorted(bloqueadas_set)
        disponibles = sorted(disponibles_set)
        return bloqueadas, disponibles
