import mysql.connector
from app.core.config import DB_HOST, DB_USER, DB_PASSWORD, DB_DATABASE, DB_PORT
from app.models.mysql_database_model import MySQLDatabase
from app.helpers.class_singleton import class_singleton

@class_singleton
class DatabaseManager(MySQLDatabase):
     
    def __init__(self):
        super().__init__()
        
    def get_user_data(self, username: str) -> dict:
        try:
            query = "SELECT * FROM usuarios_app WHERE username = %s"
            data = self.get_data(query, (username,))
            return data
        except Exception as ex:
            raise Exception(f"Error de conexión: {ex}")
