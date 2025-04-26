from app.helpers.class_singleton import class_singleton
from app.config.config import DB_HOST, DB_USER, DB_PASSWORD, DB_DATABASE, DB_PORT
import mysql.connector as mysql
from mysql.connector import Error
from pathlib import Path
import re
import traceback

@class_singleton
class DatabaseMysql:
    def __init__(self):
        # Parámetros de conexión
        self.host     = DB_HOST
        self.port     = DB_PORT
        self.user     = DB_USER
        self.password = DB_PASSWORD
        self.database = DB_DATABASE

        # Ruta al script SQL interno en database
        base_dir = Path(__file__).parent
        self.default_sql = base_dir / "database" / "gestion_laboral.sql"
        if not self.default_sql.is_file():
            print(f"⚠️ No se encontró gestion_laboral.sql en {self.default_sql}")

        # 1) Crear BD si no existe
        just_created = self.verificar_y_crear_base_datos()

        # 2) Conectar a BD
        self.connect()
        # 2.b) Crear o actualizar SP init_gestion_laboral antes de usarlo
        self._crear_sp_init()

        # 3) Si la BD recién se creó, cargar esquema completo
        if just_created:
            print("Inicializando esquema desde archivo SQL...")
            self.ejecutar_sql_desde_archivo(self.default_sql)

        # 4) Verificar tablas y crear si faltan
        self.verificar_y_crear_tablas()

    def _crear_sp_init(self) -> None:
        """Carga la definición del stored procedure init_gestion_laboral desde el .sql"""
        try:
            text = self.default_sql.read_text(encoding='utf-8')
            # Extraer bloque del SP desde DROP hasta END;
            match = re.search(
                r"DROP PROCEDURE IF EXISTS init_gestion_laboral;.*?END;",
                text, re.S | re.I
            )
            if not match:
                print("⚠️ No se encontró la definición del SP init_gestion_laboral en el script SQL.")
                return
            proc_block = match.group()
            # Ejecutar cada sentencia via run_query
            for stmt in proc_block.split(';'):
                sql = stmt.strip()
                if sql:
                    self.run_query(sql)

            # Verificar si el SP se creó correctamente
            with self.conn.cursor() as cur:
                cur.execute("SHOW PROCEDURE STATUS WHERE Name = 'init_gestion_laboral';")
                if cur.fetchone():
                    print("Stored procedure init_gestion_laboral creado/actualizado correctamente.")
                else:
                    print("⚠️ No se pudo crear/actualizar el SP init_gestion_laboral.")
        except Exception as e:
            print(f"Error al crear/actualizar SP init_gestion_laboral: {e}")
            traceback.print_exc()


    def verificar_y_crear_base_datos(self) -> bool:
        created = False
        try:
            tmp = mysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password
            )
            tmp.autocommit = True
            cur = tmp.cursor()
            cur.execute(
                "SELECT SCHEMA_NAME FROM information_schema.schemata WHERE schema_name = %s",
                (self.database,)
            )
            if cur.fetchone() is None:
                cur.execute(
                    f"CREATE DATABASE `{self.database}` "
                    "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
                created = True
            cur.close()
            tmp.close()
        except Error as e:
            print(f"Error al verificar/crear BD: {e}")
        return created

    def connect(self) -> None:
        try:
            self.conn = mysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )
            print("Conexión exitosa a la base de datos")
        except Error as e:
            print(f"Error al conectar: {e}")

    def disconnect(self) -> None:
        if hasattr(self, "conn") and self.conn:
            self.conn.close()
            print("Conexión cerrada a la base de datos")

    def run_query(self, query, params=None) -> bool:
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, params or ())
            self.conn.commit()
            return True
        except Exception as ex:
            print(f"Error de conexión: {ex}")
            return False

    def get_data(self, query, params=None) -> dict:
        try:
            with self.conn.cursor(dictionary=True) as cur:
                cur.execute(query, params or ())
                return cur.fetchone() or {}
        except Exception as ex:
            print(f"Error al obtener datos: {ex}")
            return {}

    def get_data_list(self, query, params=None) -> list:
        try:
            with self.conn.cursor(dictionary=True) as cur:
                cur.execute(query, params or ())
                return cur.fetchall()
        except Exception as ex:
            print(f"Error al obtener lista: {ex}")
            return []

    def is_empty(self) -> bool:
        tablas = [
            "empleados", "asistencias", "pagos",
            "prestamos", "desempeno", "reportes_semanales", "usuarios_app"
        ]
        for tbl in tablas:
            try:
                with self.conn.cursor(dictionary=True) as cur:
                    cur.execute(f"SELECT COUNT(*) AS c FROM `{tbl}`")
                    if cur.fetchone().get("c", 0) > 0:
                        return False
            except Exception:
                continue
        return True

    def verificar_y_crear_tablas(self) -> None:
        tablas_req = [
            "empleados", "asistencias", "pagos",
            "prestamos", "desempeno", "reportes_semanales", "usuarios_app"
        ]
        cur = self.conn.cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
            (self.database,)
        )
        existentes = {row[0] for row in cur.fetchall()}
        cur.close()

        missing = [t for t in tablas_req if t not in existentes]
        if missing:
            print(f"Tablas faltantes: {missing}. Intentando SP init_gestion_laboral...")
            try:
                cp = self.conn.cursor()
                cp.callproc('init_gestion_laboral')
                while cp.nextset():
                    pass
                cp.close()
                self.conn.commit()
                print("Esquema inicializado vía stored procedure.")
            except mysql.ProgrammingError as pe:
                print(f"⚠️ Stored procedure falló: {pe}\nEjecutando SQL manual... (fallback)")
                self.ejecutar_sql_desde_archivo(self.default_sql)

    def ejecutar_sql_desde_archivo(self, ruta: Path) -> None:
        try:
            script = ruta.read_text(encoding="utf-8")
            for stmt in script.split(';'):
                sql = stmt.strip()
                if sql:
                    self.run_query(sql)
            print(f"Script ejecutado: {ruta}")
        except Exception as e:
            print(f"Error ejecutando SQL desde {ruta}: {e}")
            traceback.print_exc()

    def import_db(self, sql_file: str) -> None:
        if not sql_file.lower().endswith(".sql"):
            raise ValueError("El archivo debe tener extensión .sql")
        sql_path = Path(sql_file)
        if self.database not in sql_path.name:
            raise ValueError(f"El archivo no corresponde a '{self.database}'")
        sql_path.replace(self.default_sql)
        self.ejecutar_sql_desde_archivo(self.default_sql)
