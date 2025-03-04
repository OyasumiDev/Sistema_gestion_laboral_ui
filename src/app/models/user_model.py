from app.core.database_manager import DatabaseManager
from app.core.interfaces.database import Database

class UserModel:
    """
    Modelo de usuarios
    """
    def __init__(self):
        self.db: Database = DatabaseManager()

    def __init__db(self):
        """
        Creamos la tabla usuarios_app
        :return:
        """
        pass

    def add(self) -> dict:
        pass

    def get(self) -> dict:
        pass

    def get_by_id(self, user_id: int) -> dict:
        pass

    def get_by_username(self, username: str) -> dict:
        try:
            query = "SELECT * FROM usuarios_app WHERE username = %s"
            return self.db.get_data(query, (username,))
        except Exception as ex:
            raise Exception(f"Error de en la consulta: {ex}")

    def get_users(self) -> dict:
        pass