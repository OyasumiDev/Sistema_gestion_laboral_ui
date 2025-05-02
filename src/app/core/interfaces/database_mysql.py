import flet as ft
from app.helpers.class_singleton import class_singleton
from app.config.config import DB_HOST, DB_USER, DB_PASSWORD, DB_DATABASE, DB_PORT
import mysql.connector as mysql
from mysql.connector import Error
import subprocess
from pathlib import Path
from app.views.containers.messages import mostrar_mensaje

@class_singleton
class DatabaseMysql:
    def __init__(self):
        self.host     = DB_HOST
        self.port     = DB_PORT
        self.user     = DB_USER
        self.password = DB_PASSWORD
        self.database = DB_DATABASE

        self.verificar_y_crear_base_datos()
        self.connect()

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
            print(f"❌ Error al verificar/crear BD: {e}")
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
            print("✅ Conexión exitosa a la base de datos")
        except Error as e:
            print(f"❌ Error al conectar: {e}")

    def disconnect(self) -> None:
        if hasattr(self, "conn") and self.conn:
            self.conn.close()
            print("ℹ️ Conexión cerrada a la base de datos")

    def run_query(self, query, params=None) -> bool:
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, params or ())
            self.conn.commit()
            return True
        except Exception as ex:
            print(f"❌ Error ejecutando query: {ex}")
            return False

    def get_data(self, query, params=None) -> dict:
        try:
            with self.conn.cursor(dictionary=True) as cur:
                cur.execute(query, params or ())
                return cur.fetchone() or {}
        except Exception as ex:
            print(f"❌ Error al obtener datos: {ex}")
            return {}

    def get_data_list(self, query, params=None) -> list:
        try:
            with self.conn.cursor(dictionary=True) as cur:
                cur.execute(query, params or ())
                return cur.fetchall()
        except Exception as ex:
            print(f"❌ Error al obtener lista: {ex}")
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

    def exportar_base_datos(self, ruta_destino: str) -> bool:
        try:
            mysqldump_path = Path(__file__).parent / "tools" / "mysqldump.exe"
            if not mysqldump_path.is_file():
                raise FileNotFoundError(f"No se encontró mysqldump en: {mysqldump_path}")

            comando = [
                str(mysqldump_path.resolve()),
                f"--user={self.user}",
                f"--password={self.password}",
                f"--host={self.host}",
                f"--port={self.port}",
                self.database
            ]

            with open(ruta_destino, "w", encoding="utf-8") as salida:
                subprocess.run(comando, stdout=salida, check=True)

            print(f"✅ Base de datos exportada a: {ruta_destino}")
            return True
        except Exception as e:
            print(f"❌ Error al exportar la base de datos: {e}")
            return False

    def importar_base_datos(self, ruta_sql: str, page: ft.Page = None) -> bool:
        try:
            ruta = Path(ruta_sql)
            if not ruta.exists():
                raise FileNotFoundError("Archivo SQL no encontrado")

            tmp = mysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password
            )
            tmp.autocommit = True
            cur = tmp.cursor()
            cur.execute(f"DROP DATABASE IF EXISTS `{self.database}`")
            cur.execute(f"CREATE DATABASE `{self.database}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cur.close()
            tmp.close()

            mysql_client_path = Path(__file__).parent / "tools" / "mysql.exe"
            if not mysql_client_path.is_file():
                raise FileNotFoundError(f"No se encontró mysql.exe en: {mysql_client_path}")

            comando = [
                str(mysql_client_path.resolve()),
                f"-h{self.host}",
                f"-P{self.port}",
                f"-u{self.user}",
                f"-p{self.password}",
                self.database
            ]

            with open(ruta, "r", encoding="utf-8") as f:
                resultado = subprocess.run(
                    comando,
                    stdin=f,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

            if resultado.returncode != 0:
                print("❌ Error durante la importación:")
                print(resultado.stderr)
                if page:
                    mostrar_mensaje(page, "Error de Importación", "Hubo un problema al importar la base de datos.")
                return False
            else:
                print("✅ Base de datos importada correctamente.")
                if page:
                    mostrar_mensaje(page, "Importación Exitosa", "La base de datos fue importada correctamente.")
                return True
        except Exception as e:
            print(f"❌ Error al importar la base de datos: {e}")
            if page:
                mostrar_mensaje(page, "Error de Importación", str(e))
            return False
