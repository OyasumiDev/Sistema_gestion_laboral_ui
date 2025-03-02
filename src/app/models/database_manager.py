import mysql.connector
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_DATABASE, DB_PORT

class DatabaseManager:
     
    def __init__(self):
        self.host = DB_HOST
        self.user = DB_USER
        self.passwoord= DB_PASSWORD
        self.database = DB_DATABASE
        self.port = DB_PORT
        self.conn = None
        self.connect()

    def connect(self):
        try:
            self.conn = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.passwoord,
                database=self.database
            )

        except Exception as e:
            print(e)
        
    def build_database(self, script_path):
        ''''
        Construye la base de datos local
        '''
        pass

    def tables_exists(self, table_name: str):
        query = '''
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
        '''
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, (self.database, table_name))
                return cursor.fetchone()[0] > 0
        except Exception as e:
            print(e)
    
    def create_table_usuarios_app(self):
        ''''
        crea la tabla usuarios_app en la base de datos
        '''
        query = '''
            CREATE TABLE IF NOT EXISTS usuarios_app (
                id_usuario INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role ENUM('ROOT','USER') NOT NULL DEFAULT 'USER',
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );
        '''
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query)
            print('Tablas creadas')
        except Exception as e:
            print(e)


    def get_user_data(self, username: str):
            if self.tables_exists('usuarios_app'):
                try:
                    cursor = self.conn.cursor(dictionary=True)
                    query = "SELECT * FROM usuarios_app WHERE username = %s"
                    cursor.execute(query, (username,))
                    return cursor.fetchone()
                except Exception as ex:
                    raise Exception(f"Error de conexión: {ex}")
                finally:
                    if self.conn:
                        self.conn.close()
            else:
                print('La tabla no existe, creando tablas...')
                self.create_table_usuarios_app()

db = DatabaseManager()
result = db.get_user_data('gabriel')
print(result)