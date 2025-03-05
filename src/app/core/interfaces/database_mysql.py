import mysql.connector
from app.core.interfaces.database import Database
from app.config.config import DB_HOST, DB_USER, DB_DATABASE, DB_PASSWORD, DB_PORT

class DatabaseMysql(Database):
     
    def __init__(self):
        super().__init__()
        self.host = DB_HOST
        self.port = DB_PORT
        self.user = DB_USER
        self.password = DB_PASSWORD
        self.database = DB_DATABASE
        self._connect()
        
    def _connect(self) -> None:
        """ Conexion a la base de datos mysql """
        try:
            self.conn = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )
            print('Conexión exitosa a la base de datos')

        except Exception as e:
            print(e)
    def _disconnect(self) -> None:
        """ Se desconecta de a la base de datos mysql """
        if self.conn:
            self.conn.close()
            print('Conexión cerrada a la base de datos')

    def run_query(self, query, params = None) -> bool:
        """ Ejecuta las consultas a la base de datos mysql """
        try:
            if params:
                with self.conn.cursor() as cr:
                    cr.execute(query)
                    self.conn.commit()
                    return True

            with self.conn.cursor() as cursor:
                cursor.execute(query, params)
                self.conn.commit()
                return True
        except Exception as ex:
            print(f"Error de conexión: {ex}, type: {type(ex).__name__}")
            return False
    
    def get_data(self, query, params = None) -> dict:
        """ Obtiene los datos de mysql en formato de diccionario """
        try:
            if params:
                with self.conn.cursor(dictionary=True) as cr:
                    cr.execute(query)
                    return cr.fetchone()

            with self.conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, params)
                return cursor.fetchone()
        except Exception as ex:
            print(f"Error de conexión: {ex}")
            return {}

    def get_data_list(self, query, params = None) -> list:
        """ Obtiene los datos de mysql en formato de lista """
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as ex:
            print(f"Error de conexión: {ex}")
            return []