from app.helpers.class_singleton import class_singleton
from app.config.config import DB_HOST, DB_USER, DB_PASSWORD, DB_DATABASE, DB_PORT
import mysql.connector as mysql
from mysql.connector import Error
import os

@class_singleton
class DatabaseMysql:
    def __init__(self):
        # Estos atributos siempre se inicializan, pero __init__ solo corre una vez gracias al decorator
        self.host     = DB_HOST
        self.port     = DB_PORT
        self.user     = DB_USER
        self.password = DB_PASSWORD
        self.database = DB_DATABASE

        # Crear BD (si no existe), conectar y crear tablas
        self.verificar_y_crear_base_datos()
        self.connect()
        self.verificar_y_crear_tablas()

    def verificar_y_crear_base_datos(self) -> None:
        """Verifica si la base de datos existe y, si no, la crea."""
        try:
            temp_conn = mysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password
            )
            temp_conn.autocommit = True
            cursor = temp_conn.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{self.database}` "
                "DEFAULT CHARACTER SET utf8mb4 "
                "DEFAULT COLLATE utf8mb4_unicode_ci"
            )
            print(f"Base de datos '{self.database}' existe o fue creada.")
            cursor.close()
            temp_conn.close()
        except Error as e:
            print(f"Error al verificar/crear la base de datos: {e}")

    def connect(self) -> None:
        """Conexión a la base de datos MySQL."""
        try:
            self.conn = mysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
            )
            print('Conexión exitosa a la base de datos')
        except Error as e:
            print(f"Error al conectar: {e}")

    def disconnect(self) -> None:
        """Se desconecta de la base de datos MySQL."""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            print('Conexión cerrada a la base de datos')

    def run_query(self, query, params=None) -> bool:
        """Ejecuta las consultas a la base de datos MySQL."""
        try:
            with self.conn.cursor() as cursor:
                if params is None:
                    cursor.execute(query)
                else:
                    cursor.execute(query, params)
            self.conn.commit()
            return True
        except Exception as ex:
            print(f"Error de conexión: {ex} (tipo: {type(ex).__name__})")
            return False

    def get_data(self, query, params=None) -> dict:
        """Obtiene los datos de MySQL en formato de diccionario."""
        try:
            with self.conn.cursor(dictionary=True) as cursor:
                if params is None:
                    cursor.execute(query)
                else:
                    cursor.execute(query, params)
                return cursor.fetchone() or {}
        except Exception as ex:
            print(f"Error al obtener datos: {ex}")
            return {}

    def get_data_list(self, query, params=None) -> list:
        """Obtiene los datos de MySQL en formato de lista (diccionarios)."""
        try:
            with self.conn.cursor(dictionary=True) as cursor:
                if params is None:
                    cursor.execute(query)
                else:
                    cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as ex:
            print(f"Error al obtener la lista de datos: {ex}")
            return []

    def verificar_y_crear_tablas(self) -> None:
        """Verifica si las tablas requeridas existen y, si no, ejecuta el script SQL para crearlas."""
        try:
            tablas_requeridas = [
                'empleados',
                'asistencias',
                'pagos',
                'prestamos',
                'desempeno',
                'reportes_semanales',
                'usuarios_app'
            ]

            query = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
            """

            with self.conn.cursor() as cursor:
                cursor.execute(query, (self.database,))
                tablas_encontradas = [row[0] for row in cursor.fetchall()]

            faltantes = [t for t in tablas_requeridas if t not in tablas_encontradas]

            if faltantes:
                print(f"Tablas faltantes: {faltantes}. Ejecutando script SQL para crearlas...")
                ruta_archivo = os.path.normpath(
                    os.path.join(
                        os.path.dirname(__file__),
                        '..', 'core', 'interfaces', 'gestion_laboral.sql'
                    )
                )
                self.ejecutar_sql_desde_archivo(ruta_archivo)
                print("Script ejecutado correctamente.")
            else:
                print("Todas las tablas requeridas ya existen.")
        except Error as e:
            print(f"Error al verificar/crear tablas: {e}")

    def ejecutar_sql_desde_archivo(self, ruta_archivo: str) -> None:
        """Ejecuta todas las instrucciones SQL contenidas en un archivo .sql."""
        try:
            with open(ruta_archivo, "r", encoding="utf-8") as archivo_sql:
                script = archivo_sql.read()

            for statement in script.split(";"):
                sql = statement.strip()
                if sql:
                    with self.conn.cursor() as cursor:
                        cursor.execute(sql)
            self.conn.commit()
            print(f"Archivo SQL '{ruta_archivo}' ejecutado correctamente.")
        except Exception as e:
            print(f"Error al ejecutar el archivo SQL: {e}")
