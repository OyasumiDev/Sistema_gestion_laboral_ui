from app.helpers.class_singleton import class_singleton
from app.config.config import DB_HOST, DB_USER, DB_PASSWORD, DB_DATABASE, DB_PORT
import mysql.connector as mysql
from mysql.connector import Error
from pathlib import Path
import shutil
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

        # Ubicación del script SQL: app/core/interfaces/database/gestion_laboral.sql
        base_dir = Path(__file__).parent.resolve()
        self.default_sql = base_dir / "database" / "gestion_laboral.sql"
        if not self.default_sql.is_file():
            print(f"⚠️ No se encontró gestion_laboral.sql en {self.default_sql}")

        # 1) Crear BD si no existe
        try:
            just_created = self.verificar_y_crear_base_datos()
        except Exception as e:
            self._handle_db_creation_error(e)
            just_created = False

        # 2) Conectar a la base de datos
        try:
            self.connect()
        except Exception as e:
            self._handle_connection_error(e)
            return      # abortar inicialización si falla conexión

        # 3) Si BD recién creada, cargar esquema completo
        if just_created:
            print("Inicializando esquema desde archivo SQL...")
            try:
                self.ejecutar_sql_desde_archivo(self.default_sql)
            except Exception as e:
                self._handle_sql_execution_error(e)

        # 4) Verificar tablas y crear si faltan
        try:
            self.verificar_y_crear_tablas()
        except Exception as e:
            self._handle_table_verification_error(e)

    def verificar_y_crear_base_datos(self) -> bool:
        """Verifica si la base existe, si no, la crea y retorna True."""
        created = False
        conn_tmp = None
        try:
            conn_tmp = mysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password
            )
            conn_tmp.autocommit = True
            cur = conn_tmp.cursor()
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
        finally:
            if conn_tmp:
                conn_tmp.close()
        return created

    def connect(self) -> None:
        """Establece conexión a la BD usando mysql.connector."""
        self.conn = mysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database
        )
        print("Conexión exitosa a la base de datos")

    def disconnect(self) -> None:
        """Cierra la conexión si existe."""
        if hasattr(self, "conn") and self.conn:
            self.conn.close()
            print("Conexión cerrada a la base de datos")

    def run_query(self, query, params=None) -> bool:
        """Ejecuta una query de modificación y retorna True si tuvo éxito."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, params or ())
            self.conn.commit()
            return True
        except Exception as ex:
            self._handle_query_error(ex)
            return False

    def get_data(self, query, params=None) -> dict:
        """Ejecuta una consulta y retorna un solo registro como dict."""
        try:
            with self.conn.cursor(dictionary=True) as cur:
                cur.execute(query, params or ())
                return cur.fetchone() or {}
        except Exception as ex:
            self._handle_query_error(ex)
            return {}

    def get_data_list(self, query, params=None) -> list:
        """Ejecuta una consulta y retorna todos los registros como lista de dicts."""
        try:
            with self.conn.cursor(dictionary=True) as cur:
                cur.execute(query, params or ())
                return cur.fetchall()
        except Exception as ex:
            self._handle_query_error(ex)
            return []

    def is_empty(self) -> bool:
        """Comprueba si todas las tablas principales están vacías."""
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
        """Verifica existencia de tablas y crea esquema completo si faltan."""
        tablas_req = [
            "empleados", "asistencias", "pagos",
            "prestamos", "desempeno", "reportes_semanales", "usuarios_app"
        ]
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
                (self.database,)
            )
            existentes = {row[0] for row in cur.fetchall()}

        missing = [t for t in tablas_req if t not in existentes]
        if missing:
            print(f"Tablas faltantes: {missing}. Intentando CALL init_gestion_laboral()...")
            try:
                with self.conn.cursor() as cp:
                    cp.execute("CALL init_gestion_laboral();")
                self.conn.commit()
                print("Esquema inicializado vía stored procedure.")
                return
            except mysql.ProgrammingError as pe:
                self._handle_stored_proc_error(pe)
                print("FALLBACK: ejecutando script SQL completo...")
                self.ejecutar_sql_desde_archivo(self.default_sql)
            except Error as e:
                self._handle_table_verification_error(e)

    def ejecutar_sql_desde_archivo(self, ruta: Path) -> None:
        """
        Carga y ejecuta todo el script SQL de inicialización de golpe.
        Connector/Python 9.2+ soporta múltiples declaraciones y delimiters.
        """
        script = ruta.read_text(encoding="utf-8")
        try:
            with self.conn.cursor() as cur:
                cur.execute(script)
            self.conn.commit()
            print(f"Script ejecutado exitosamente: {ruta}")
        except Exception as ex:
            raise

    def import_db(self, sql_file: str) -> None:
        """Reemplaza el script SQL de inicialización y recarga el esquema."""
        new_path = Path(sql_file)
        if not new_path.exists():
            raise FileNotFoundError(f"No existe el archivo {sql_file}")
        if not sql_file.lower().endswith('.sql'):
            raise ValueError("El archivo debe terminar en .sql")
        self._backup_default_sql()
        new_path.replace(self.default_sql)
        print(f"Script SQL reemplazado por: {new_path}")
        self.ejecutar_sql_desde_archivo(self.default_sql)

    # Backups y manejadores de errores
    def _backup_default_sql(self) -> None:
        bak = self.default_sql.with_suffix('.bak')
        shutil.copy(self.default_sql, bak)
        print(f"Backup creado en {bak}")

    def _handle_db_creation_error(self, ex):
        print(f"Error creando BD: {ex}")
        traceback.print_exc()

    def _handle_connection_error(self, ex):
        print(f"Error conectando a BD: {ex}")
        traceback.print_exc()

    def _handle_sql_execution_error(self, ex):
        print(f"Error ejecutando script SQL: {ex}")
        traceback.print_exc()

    def _handle_table_verification_error(self, ex):
        print(f"Error verificando/creando tablas: {ex}")
        traceback.print_exc()

    def _handle_stored_proc_error(self, ex):
        print(f"Error en CALL init_gestion_laboral: {ex}")
        traceback.print_exc()

    def _handle_query_error(self, ex):
        print(f"Error en consulta: {ex}")
        traceback.print_exc()
