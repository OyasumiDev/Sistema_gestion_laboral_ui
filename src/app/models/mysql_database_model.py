import mysql.connector
from app.core.config import DB_HOST, DB_USER, DB_PASSWORD, DB_DATABASE, DB_PORT
from app.models.database_model import Database

class MySQLDatabase(Database):
     
    def __init__(self):
        super().__init__(
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_DATABASE,
            host=DB_HOST
        )
        # Conectamos a la base de datos mysql
        self._connect()
        
    def _connect(self):
        ''' Conexion a la base de datos mysql '''
        try:
            self.conn = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            print('Conexión exitosa a la base de datos')

        except Exception as e:
            print(e)
    def _disconnect(self):
        ''' Se desconecta de a la base de datos mysql '''
        if self.conn:
            self.conn.close()
        print('Conexión cerrada a la base de datos')

    def run_query(self, query, params=...) -> bool:
        '''' Ejecuta las consultas a la base de datos mysql '''
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, params)
                self.conn.commit()
                return True
        except Exception as ex:
            return False
    
    def get_data(self, query, params=...) -> dict:
        '''' Obtiene los datos de mysql en formato de diccionario '''
        try:
            with self.conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, params)
                return cursor.fetchone()
        except Exception as ex:
            raise Exception(f"Error de conexión: {ex}")

    def get_data_list(self, query, params=...) -> list:
        '''' Obtiene los datos de mysql en formato de lista '''
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as ex:
            raise Exception(f"Error de conexión: {ex}")