from app.core.enums.e_assistance_model import E_ASSISTANCE
from app.core.interfaces.database_mysql import DatabaseMysql
from datetime import date, datetime, timedelta
from typing import Optional
import pandas as pd 

class AssistanceModel:
    def __init__(self):
        self.db = DatabaseMysql()
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
                    id_asistencia INT AUTO_INCREMENT PRIMARY KEY,
                    numero_nomina SMALLINT UNSIGNED NOT NULL,
                    fecha DATE NOT NULL,
                    hora_entrada TIME,
                    hora_salida TIME,
                    descanso TINYINT DEFAULT 0,
                    estado VARCHAR(20),
                    tiempo_trabajo TIME,
                    fecha_generada DATE DEFAULT NULL,
                    grupo_importacion VARCHAR(50) DEFAULT NULL,
                    FOREIGN KEY (numero_nomina) REFERENCES empleados(numero_nomina) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {E_ASSISTANCE.TABLE.value} creada correctamente.")
            else:
                # Asegurarse que la columna exista si la tabla ya está creada
                columna_query = """
                    SELECT COUNT(*) AS existe
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s AND column_name = 'grupo_importacion'
                """
                col_result = self.db.get_data(columna_query, (self.db.database, E_ASSISTANCE.TABLE.value), dictionary=True)
                if col_result.get("existe", 0) == 0:
                    alter_query = f"""
                        ALTER TABLE {E_ASSISTANCE.TABLE.value}
                        ADD COLUMN grupo_importacion VARCHAR(50) DEFAULT NULL
                    """
                    self.db.run_query(alter_query)
                    print("🛠️ Columna 'grupo_importacion' agregada a la tabla asistencias.")
                else:
                    print("✔️ Columna 'grupo_importacion' ya existe en asistencias.")

            return True

        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {E_ASSISTANCE.TABLE.value}: {ex}")
            return False



    def verificar_o_crear_triggers(self):
        try:
            self._crear_trigger_calculo_horas()
            self._crear_trigger_actualizar_horas()  # <<—— aquí lo agregas
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


    def add(
        self,
        numero_nomina: int,
        fecha: str,
        turno: str = None,
        entrada_turno: str = None,
        salida_turno: str = None,
        hora_entrada: str = None,
        hora_salida: str = None,
        descanso: int = 0,
        tipo_registro: str = "manual",
        grupo_importacion: str = None
    ):
        try:
            if tipo_registro not in ['automático', 'manual']:
                tipo_registro = 'manual'

            def limpiar_hora(valor, campo: str):
                motivo = None
                if valor is None:
                    motivo = "valor None"
                elif isinstance(valor, float) and pd.isna(valor):
                    motivo = "valor NaN como float"
                else:
                    valor_str = str(valor).strip().lower()
                    if valor_str in ['nan', '', 'none']:
                        motivo = f"cadena inválida: '{valor_str}'"
                if motivo:
                    print(f"⚠️ {campo.upper()} inválida para empleado {numero_nomina} en fecha {fecha} ({motivo}). Reemplazada por '00:00:00'")
                    return "00:00:00"
                return str(valor).strip()

            hora_entrada = limpiar_hora(hora_entrada, "hora_entrada")
            hora_salida = limpiar_hora(hora_salida, "hora_salida")

            if descanso not in (0, 1, 2):
                print(f"⚠️ Valor de descanso inválido ({descanso}), se asigna 0 por defecto.")
                descanso = 0

            query = f"""
            INSERT INTO {E_ASSISTANCE.TABLE.value} (
                {E_ASSISTANCE.NUMERO_NOMINA.value},
                {E_ASSISTANCE.FECHA.value},
                {E_ASSISTANCE.HORA_ENTRADA.value},
                {E_ASSISTANCE.HORA_SALIDA.value},
                {E_ASSISTANCE.DESCANSO.value},
                {E_ASSISTANCE.ESTADO.value},
                {E_ASSISTANCE.TIEMPO_TRABAJO.value},
                {E_ASSISTANCE.FECHA_GENERADA.value},
                {E_ASSISTANCE.GRUPO_IMPORTACION.value}
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            valores = (
                numero_nomina,
                fecha,
                hora_entrada,
                hora_salida,
                descanso,
                None,
                None,
                None,
                grupo_importacion
            )

            self.db.run_query(query, valores)
            return {"status": "success", "message": "Asistencia agregada correctamente"}

        except Exception as ex:
            return {"status": "error", "message": f"Error al agregar asistencia: {ex}"}


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

            fecha_formateada = fecha

            query_check = f"""
                SELECT COUNT(*) AS existe
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.NUMERO_NOMINA.value} = %s AND {E_ASSISTANCE.FECHA.value} = %s
            """
            resultado = self.db.get_data(query_check, (numero_nomina, fecha_formateada), dictionary=True)
            if resultado.get("existe", 0) > 0:
                return {"status": "error", "message": "Ya existe una asistencia registrada para ese empleado en esa fecha"}

            query_insert = f"""
                INSERT INTO {E_ASSISTANCE.TABLE.value} (
                    {E_ASSISTANCE.NUMERO_NOMINA.value},
                    {E_ASSISTANCE.FECHA.value},
                    {E_ASSISTANCE.HORA_ENTRADA.value},
                    {E_ASSISTANCE.HORA_SALIDA.value},
                    {E_ASSISTANCE.DESCANSO.value},
                    {E_ASSISTANCE.GRUPO_IMPORTACION.value}
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(query_insert, (numero_nomina, fecha_formateada, hora_entrada, hora_salida, descanso, grupo_importacion))
            return {"status": "success", "message": "Asistencia agregada correctamente"}

        except Exception as e:
            return {"status": "error", "message": str(e)}


    def _formatear_fecha(self, fecha_sql: str) -> str:
        try:
            return datetime.strptime(fecha_sql, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return fecha_sql


    def get_all(self) -> dict:
        try:
            query = f"""
            SELECT a.*, e.nombre_completo AS nombre
            FROM {E_ASSISTANCE.TABLE.value} a
            JOIN empleados e ON a.numero_nomina = e.numero_nomina
            ORDER BY a.fecha ASC
            """
            result = self.db.get_data_list(query, dictionary=True)
            for row in result:
                if "fecha" in row:
                    row["fecha"] = self._formatear_fecha(str(row["fecha"]))
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener asistencias: {ex}"}


    def get_by_id(self, id_asistencia: int) -> dict:
        try:
            query = f"""
                SELECT * FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.ID.value} = %s
            """
            result = self.db.get_data(query, (id_asistencia,), dictionary=True)
            if result and "fecha" in result:
                result["fecha"] = self._formatear_fecha(str(result["fecha"]))
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener asistencia por ID: {ex}"}


    def get_by_empleado_fecha(self, numero_nomina: int, fecha: str) -> dict | None:
        try:
            # Detectar si la fecha viene en formato DD/MM/YYYY
            if "/" in fecha:
                fecha = datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")

            query = f"""
                SELECT * FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.NUMERO_NOMINA.value} = %s AND {E_ASSISTANCE.FECHA.value} = %s
            """
            result = self.db.get_data(query, (numero_nomina, fecha), dictionary=True)
            if result and "fecha" in result:
                result["fecha"] = self._formatear_fecha(str(result["fecha"]))
            return result
        except Exception as ex:
            print(f"Error al obtener asistencia: {ex}")
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


    def actualizar_asistencia_completa(self, numero_nomina, fecha, hora_entrada, hora_salida, estado, descanso: int = 0):
        try:
            fecha_sql = datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")

            if descanso not in (0, 1, 2):
                print(f"⚠️ Descanso inválido ({descanso}), se usará 0.")
                descanso = 0

            query = """
                UPDATE asistencias
                SET hora_entrada = %s,
                    hora_salida = %s,
                    estado = %s,
                    descanso = %s
                WHERE numero_nomina = %s AND fecha = %s
            """
            params = (hora_entrada, hora_salida, estado, descanso, numero_nomina, fecha_sql)
            self.db.run_query(query, params)
            return {"status": "success", "message": "Asistencia actualizada"}
        except Exception as e:
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
