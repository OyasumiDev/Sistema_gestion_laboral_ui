from app.core.enums.e_assistance_model import E_ASSISTANCE
from app.core.interfaces.database_mysql import DatabaseMysql
from datetime import datetime

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
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    numero_nomina SMALLINT UNSIGNED NOT NULL,
                    fecha DATE NOT NULL,
                    turno VARCHAR(50),
                    entrada_turno TIME,
                    salida_turno TIME,
                    hora_entrada TIME,
                    hora_salida TIME,
                    tiempo_trabajo TIME,
                    tiempo_descanso TIME,
                    retardo TIME,
                    estado VARCHAR(20),
                    tipo_registro VARCHAR(20),
                    total_horas_trabajadas TIME,
                    estado_registro VARCHAR(20) DEFAULT 'listo',
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
                DECLARE hora_real TIME;
                DECLARE retardo TIME;
                DECLARE salida_ajustada TIME;
                DECLARE descanso TIME;
                DECLARE tiempo_final TIME;

                SET hora_real = NEW.hora_entrada;

                IF hora_real IS NOT NULL AND NEW.hora_salida IS NOT NULL THEN
                    -- Calcular hora de retardo
                    IF hora_real < '06:00:00' THEN
                        SET retardo = '06:00:00';
                    ELSE
                        SET retardo = ADDTIME(
                            MAKETIME(HOUR(hora_real), FLOOR(MINUTE(hora_real) / 30) * 30, 0),
                            IF(MINUTE(hora_real) % 30 = 0, '00:00:00', '00:30:00')
                        );
                    END IF;

                    SET NEW.retardo = retardo;

                    -- Ajustar salida si es menor o igual que la hora de retardo
                    SET salida_ajustada = NEW.hora_salida;
                    IF salida_ajustada <= retardo THEN
                        SET salida_ajustada = ADDTIME(salida_ajustada, '24:00:00');
                    END IF;

                    -- Calcular horas trabajadas
                    SET descanso = IFNULL(NEW.tiempo_descanso, '00:00:00');
                    SET tiempo_final = SUBTIME(TIMEDIFF(salida_ajustada, retardo), descanso);

                    SET NEW.tiempo_trabajo = tiempo_final;
                    SET NEW.total_horas_trabajadas = tiempo_final;
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
                OR NEW.hora_entrada = '00:00:00' OR NEW.hora_salida = '00:00:00' THEN
                    SET NEW.estado = 'incompleto';
                ELSE
                    SET NEW.estado = 'completo';
                END IF;
            END;
            """  # <-- Aquí estaba el error: faltaba el `;` después del END

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
                {E_ASSISTANCE.TURNO.value},
                {E_ASSISTANCE.ENTRADA_TURNO.value},
                {E_ASSISTANCE.SALIDA_TURNO.value},
                {E_ASSISTANCE.HORA_ENTRADA.value},
                {E_ASSISTANCE.HORA_SALIDA.value},
                {E_ASSISTANCE.TIEMPO_DESCANSO.value},
                {E_ASSISTANCE.RETARDO.value},
                {E_ASSISTANCE.TIPO_REGISTRO.value}
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
            fecha_sql = datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")
            query = f"""
                SELECT * FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.NUMERO_NOMINA.value} = %s AND {E_ASSISTANCE.FECHA.value} = %s
            """
            result = self.db.get_data(query, (numero_nomina, fecha_sql), dictionary=True)
            if result and "fecha" in result:
                result["fecha"] = self._formatear_fecha(str(result["fecha"]))
            return result
        except Exception as ex:
            print(f"Error al obtener asistencia: {ex}")
            return None