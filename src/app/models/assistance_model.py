from app.core.enums.e_assistance_model import E_ASSISTANCE
from app.core.interfaces.database_mysql import DatabaseMysql
from datetime import datetime

class AssistanceModel:
    def __init__(self):
        self.db = DatabaseMysql()
        self._exists_table = self.check_table()
        self.verificar_o_crear_trigger()

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
                    nombre VARCHAR(100) NOT NULL,
                    sucursal VARCHAR(100),
                    fecha DATE NOT NULL,
                    turno VARCHAR(50),
                    entrada_turno TIME,
                    salida_turno TIME,
                    entrada TIME,
                    salida TIME,
                    tiempo_trabajo TIME,
                    tiempo_descanso TIME,
                    retardo TIME,
                    estado VARCHAR(20),
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

    def verificar_o_crear_trigger(self):
        try:
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

                trigger_sql = f"""
                CREATE TRIGGER {trigger_name}
                BEFORE INSERT ON {E_ASSISTANCE.TABLE.value}
                FOR EACH ROW
                BEGIN
                    DECLARE entrada_redondeada TIME;
                    DECLARE salida TIME;
                    DECLARE descanso TIME;

                    -- Redondear la hora de entrada
                    SET entrada_redondeada = IF(
                        HOUR(NEW.entrada) < 6,
                        MAKETIME(6, 0, 0),
                        IF(MINUTE(NEW.entrada) > 0,
                            ADDTIME(MAKETIME(HOUR(NEW.entrada), 0, 0), '00:30:00'),
                            MAKETIME(HOUR(NEW.entrada), 0, 0)
                        )
                    );

                    SET salida = NEW.salida;
                    SET descanso = IFNULL(NEW.tiempo_descanso, '00:00:00');

                    SET NEW.entrada = entrada_redondeada;
                    SET NEW.tiempo_trabajo = SUBTIME(TIMEDIFF(salida, entrada_redondeada), descanso);
                END
                """

                cursor.execute(trigger_sql)
                self.db.connection.commit()
                cursor.close()

                print(f"✅ Trigger '{trigger_name}' creado correctamente.")
            else:
                print(f"✔️ Trigger '{trigger_name}' ya existe.")
        except Exception as ex:
            print(f"❌ Error al verificar/crear trigger: {ex}")

    def add(self, numero_nomina, fecha, hora_entrada, hora_salida, duracion_comida, tipo_registro, horas_trabajadas):
        try:
            if tipo_registro not in ['automático', 'manual']:
                print(f"⚠️ tipo_registro inválido: '{tipo_registro}'. Se forzará a 'manual'.")
                tipo_registro = 'manual'

            print("📥 Insertando asistencia:", numero_nomina, fecha, hora_entrada, hora_salida, duracion_comida, tipo_registro, horas_trabajadas)

            query = f"""
            INSERT INTO {E_ASSISTANCE.TABLE.value} (
                {E_ASSISTANCE.NUMERO_NOMINA.value},
                {E_ASSISTANCE.FECHA.value},
                {E_ASSISTANCE.HORA_ENTRADA.value},
                {E_ASSISTANCE.HORA_SALIDA.value},
                {E_ASSISTANCE.DURACION_COMIDA.value},
                {E_ASSISTANCE.TIPO_REGISTRO.value},
                {E_ASSISTANCE.HORAS_TRABAJADAS.value}
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(query, (
                numero_nomina,
                fecha,
                hora_entrada,
                hora_salida,
                duracion_comida,
                tipo_registro,
                horas_trabajadas
            ))
            return {"status": "success", "message": "Asistencia agregada correctamente"}
        except Exception as ex:
            print(f"❌ Error al agregar asistencia: {ex}")
            return {"status": "error", "message": f"Error al agregar asistencia: {ex}"}

    def _formatear_fecha(self, fecha_sql: str) -> str:
        try:
            return datetime.strptime(fecha_sql, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return fecha_sql

    def get_all(self) -> dict:
        try:
            query = f"SELECT * FROM {E_ASSISTANCE.TABLE.value}"
            result = self.db.get_data_list(query, dictionary=True)  # <--- AÑADIR ESTO
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
