from app.core.enums.e_assistance_model import E_ASSISTANCE
from app.core.interfaces.database_mysql import DatabaseMysql
from datetime import datetime, timedelta


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
            if result.get("c", 0) == 0:
                print(f"⚠️ La tabla {E_ASSISTANCE.TABLE.value} no existe. Creando...")
                create_query = f"""
                CREATE TABLE IF NOT EXISTS asistencias (
                    id_asistencia INT AUTO_INCREMENT PRIMARY KEY,
                    numero_nomina SMALLINT UNSIGNED NOT NULL,
                    fecha DATE NOT NULL,
                    hora_entrada TIME,
                    hora_salida TIME,
                    retardo TIME,
                    estado VARCHAR(20),
                    tiempo_trabajo TIME,
                    FOREIGN KEY (numero_nomina)
                        REFERENCES empleados(numero_nomina)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {E_ASSISTANCE.TABLE.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {E_ASSISTANCE.TABLE.value} ya existe.")
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {E_ASSISTANCE.TABLE.value}: {ex}")
            return False



    def verificar_o_crear_triggers(self):
        try:
            self._crear_trigger_calculo_horas()
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
                DECLARE entrada_ajustada TIME;
                DECLARE salida_ajustada TIME;
                DECLARE tiempo_final TIME;

                IF NEW.hora_entrada IS NOT NULL AND NEW.hora_entrada NOT IN ('00:00:00', '0:00:00')
                AND NEW.hora_salida IS NOT NULL AND NEW.hora_salida NOT IN ('00:00:00', '0:00:00') THEN

                    -- Redondear hora de entrada hacia arriba al siguiente bloque de 30 minutos
                    SET entrada_ajustada = MAKETIME(
                        HOUR(NEW.hora_entrada),
                        IF(MINUTE(NEW.hora_entrada) <= 30, 30, 0),
                        0
                    );
                    IF MINUTE(NEW.hora_entrada) > 30 THEN
                        SET entrada_ajustada = ADDTIME(entrada_ajustada, '01:00:00');
                    END IF;

                    -- Redondear hora de salida hacia abajo al bloque de 30 minutos anterior
                    SET salida_ajustada = MAKETIME(
                        HOUR(NEW.hora_salida),
                        IF(MINUTE(NEW.hora_salida) >= 30, 30, 0),
                        0
                    );

                    -- Si la salida es menor o igual a la entrada, asumimos cruce de día
                    IF salida_ajustada <= entrada_ajustada THEN
                        SET salida_ajustada = ADDTIME(salida_ajustada, '24:00:00');
                    END IF;

                    -- Calcular tiempo trabajado
                    SET tiempo_final = TIMEDIFF(salida_ajustada, entrada_ajustada);

                    -- Asignar valores
                    SET NEW.retardo = entrada_ajustada;
                    SET NEW.tiempo_trabajo = tiempo_final;
                END IF;
            END
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



    def add(self,
            numero_nomina: int,
            fecha: str,
            turno: str = None,
            entrada_turno: str = None,
            salida_turno: str = None,
            hora_entrada: str = None,
            hora_salida: str = None,
            tiempo_descanso: str = None,
            retardo: str = None,
            tipo_registro: str = "manual"
        ):
        try:
            if tipo_registro not in ['automático', 'manual']:
                tipo_registro = 'manual'

            query = f"""
            INSERT INTO {E_ASSISTANCE.TABLE.value} (
                {E_ASSISTANCE.NUMERO_NOMINA.value},
                {E_ASSISTANCE.FECHA.value},
                {E_ASSISTANCE.HORA_ENTRADA.value},
                {E_ASSISTANCE.HORA_SALIDA.value},
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            valores = (
                numero_nomina,
                fecha,
                turno,
                entrada_turno,
                salida_turno,
                hora_entrada,
                hora_salida,
                tiempo_descanso,
                retardo,
                tipo_registro
            )

            self.db.run_query(query, valores)
            return {"status": "success", "message": "Asistencia agregada correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al agregar asistencia: {ex}"}


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
            
    def add_manual_assistance(self, numero_nomina: int, fecha: str, hora_entrada: str, hora_salida: str):
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

            # ✅ Ya viene en formato YYYY-MM-DD desde la interfaz
            fecha_formateada = fecha

            query_check = """
                SELECT COUNT(*) AS existe
                FROM asistencias
                WHERE numero_nomina = %s AND fecha = %s
            """
            resultado = self.db.get_data(query_check, (numero_nomina, fecha_formateada), dictionary=True)
            if resultado.get("existe", 0) > 0:
                return {"status": "error", "message": "Ya existe una asistencia registrada para ese empleado en esa fecha"}

            query_insert = """
                INSERT INTO asistencias (
                    numero_nomina, fecha, hora_entrada, hora_salida
                ) VALUES (%s, %s, %s, %s)
            """
            self.db.run_query(query_insert, (numero_nomina, fecha_formateada, hora_entrada, hora_salida))
            return {"status": "success", "message": "Asistencia agregada correctamente"}

        except Exception as e:
            return {"status": "error", "message": str(e)}



    def actualizar_horas_manualmente(self, numero_nomina, fecha, hora_entrada, hora_salida):
        try:
            # Validar tipos
            if not all(isinstance(h, str) for h in [hora_entrada, hora_salida]):
                raise ValueError("Las horas deben ser texto en formato HH:MM:SS")

            h_ent = datetime.strptime(hora_entrada, "%H:%M:%S")
            h_sal = datetime.strptime(hora_salida, "%H:%M:%S")
            if h_sal <= h_ent:
                raise ValueError("La hora de salida debe ser mayor que la de entrada")

            query = """
                UPDATE asistencias
                SET hora_entrada = %s, hora_salida = %s
                WHERE numero_nomina = %s AND fecha = %s AND estado = 'incompleto'
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
        

    def actualizar_asistencia_completa(self, numero_nomina, fecha, hora_entrada, hora_salida, estado):
        try:
            # Convertir fecha de DD/MM/YYYY a YYYY-MM-DD
            fecha_sql = datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")

            query = """
                UPDATE asistencias
                SET hora_entrada = %s,
                    hora_salida = %s,
                    estado = %s
                WHERE numero_nomina = %s AND fecha = %s
            """
            params = (hora_entrada, hora_salida, estado, numero_nomina, fecha_sql)
            self.db.run_query(query, params)
            return {"status": "success", "message": "Asistencia actualizada"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


