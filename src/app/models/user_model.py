from app.core.database_manager import DatabaseManager
from app.core.interfaces.database import Database
from app.core.enums.e_user_model import EUserModel

class UserModel:
    """
    Modelo de usuarios
    """
    _exits_table: bool

    def __init__(self):
        self.db: Database = DatabaseManager()

        if not self.check_table():
            self.__init__db()

    def __init__db(self):
        query = f"""
            CREATE TABLE IF NOT EXISTS {EUserModel.TABLE.value} (
                {EUserModel.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                {EUserModel.USERNAME.value} VARCHAR(50) NOT NULL UNIQUE,
                {EUserModel.PASSWORD.value} VARCHAR(255) NOT NULL, -- Se guarda el hash de la contraseña
                {EUserModel.ROLE.value} ENUM('ROOT','USER') NOT NULL DEFAULT 'USER',
                {EUserModel.FECHA_CREACION.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                {EUserModel.FECHA_MODIFICACION.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """

        result_query = self.db.run_query(query)

    def check_table(self):
        '''
        Verifica si la tabla existe
        :return:
        '''
        query= "SHOW TABLES"
        result_tables = self.db.get_data_list(query)

        print(result_tables)

        for tabla in result_tables:
            if tabla[0] == EUserModel.TABLE.value:
                self._exits_table = True
                return

        self.__init__db()

    def add(self) -> dict:
        pass

    def get(self) -> dict:
        pass

    def get_by_id(self, user_id: int) -> dict:
        pass


    def get_by_username(self, username: str) -> dict:
        """
        Este metodo obtener por usuario lo que hace es una consulta a la base de datos mysql los usuarios que en este caso serian
        nuestros parametros de entrada y retornara un diccionario con toda la informacion de los usuarios (id_usuario,username,password_hash,role,fehca_creacion,fecha_modificacion)
        :param username:
        :return:
        """
        try:
            query = "SELECT * FROM usuarios_app WHERE username = %s"
            return self.db.get_data(query, (username,))
        except Exception as ex:
            raise Exception(f"Error de en la consulta: {ex}")

    def get_users(self) -> dict:
        pass