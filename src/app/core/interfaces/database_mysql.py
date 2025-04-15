import mysql.connector
# from app.core.interfaces.database import Database
from app.config.config import DB_HOST, DB_USER, DB_PASSWORD, DB_DATABASE, DB_PORT 
# ,DB_TYPE

class DatabaseMysql(Database):
    
    def __init__(self):
        super().__init__()
        self.host = DB_HOST
        self.port = DB_PORT
        self.user = DB_USER
        self.password = DB_PASSWORD
        self.database = DB_DATABASE
        # self.db_type = DB_TYPE
        self._connect()

        
        
    def _connect(self) -> None:
        """Conexión a la base de datos MySQL."""
        try:
            self.conn = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                db_type=self.db_type
                
            )
            print('Conexión exitosa a la base de datos')
        except Exception as e:
            print(f"Error al conectarrr: {e}")
    
    def _disconnect(self) -> None:
        """Se desconecta de la base de datos MySQL."""
        if self.conn:
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
                return cursor.fetchone()
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
                'reportes_semanales'
            ]

            query = """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = %s
            """

            with self.conn.cursor() as cursor:
                cursor.execute(query, (self.database,))
                tablas_encontradas = [tabla[0] for tabla in cursor.fetchall()]

            faltantes = [t for t in tablas_requeridas if t not in tablas_encontradas]

            if faltantes:
                print(f"Tablas faltantes: {faltantes}. Ejecutando script SQL para crearlas...")
                # Asumiendo que tu script ya tiene 'IF NOT EXISTS', es seguro ejecutarlo
                self.ejecutar_sql_desde_archivo("ruta/del/archivo.sql")
                print("Script ejecutado correctamente.")
            else:
                print("Todas las tablas requeridas ya existen.")

        except Exception as e:
            print(f"Error al verificar/crear tablas: {e}")
        
            
    def ejecutar_sql_desde_archivo(self, ruta_archivo: str) -> None:
        """Ejecuta todas las instrucciones SQL contenidas en un archivo .sql."""
        try:
            with open(ruta_archivo, "r", encoding="utf-8") as archivo_sql:
                script = archivo_sql.read()
    
            # Separa y ejecuta cada sentencia SQL individualmente
            for statement in script.split(";"):
                clean_statement = statement.strip()
                if clean_statement:
                    with self.conn.cursor() as cursor:
                        cursor.execute(clean_statement)
            self.conn.commit()
            print(f"Archivo SQL '{ruta_archivo}' ejecutado correctamente.")
        except Exception as e:
            print(f"Error al ejecutar el archivo SQL: {e}")
