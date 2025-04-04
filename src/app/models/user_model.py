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

        # Verifica si la tabla existe, y si no, la crea.
        if not self.check_table():
            self.__init__db()

        # Verifica y crea el usuario root si no existe.
        self.check_root_user()

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
        """
        Verifica si la tabla existe.
        :return: True si la tabla existe, False en caso contrario.
        """
        query = "SHOW TABLES"
        result_tables = self.db.get_data_list(query)

        for tabla in result_tables:
            if tabla[0] == EUserModel.TABLE.value:
                self._exits_table = True
                return True
        return False

    def check_root_user(self):
        """
        Verifica si existe el usuario root y en caso de que no exista, lo crea.
        """
        query = f"SELECT * FROM {EUserModel.TABLE.value} WHERE {EUserModel.USERNAME.value} = 'root'"
        result = self.db.get_data_list(query)
        if not result:
            # Si no existe el usuario root, se agrega con nombre y contraseña 'root' y rol 'ROOT'
            self.add("root", "root", "ROOT")

    
    def add(self, username: str, password_hash: str, role: str = 'USER') -> dict:
        try:
            query = f"""
            INSERT INTO {EUserModel.TABLE.value} 
                ({EUserModel.USERNAME.value}, {EUserModel.PASSWORD.value}, {EUserModel.ROLE.value})
            VALUES (%s, %s, %s)
            """
            self.db.run_query(query, (username, password_hash, role))
            return {"status": "success", "message": "Usuario agregado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al agregar usuario: {ex}"}

    def get(self) -> dict:
        """
        Retorna todos los usuarios registrados (incluye contraseña hash).
        """
        try:
            query = f"SELECT * FROM {EUserModel.TABLE.value}"
            result = self.db.get_data_list(query)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener usuarios: {ex}"}
    
    def get_by_id(self, user_id: int) -> dict:
        """
        Retorna un usuario por su ID.
        """
        try:
            query = f"""
                SELECT * FROM {EUserModel.TABLE.value}
                WHERE {EUserModel.ID.value} = %s
            """
            result = self.db.get_data(query, (user_id,))
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener usuario por ID: {ex}"}


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
        """
        Retorna todos los usuarios sin mostrar la contraseña hash.
        """
        try:
            query = f"""
                SELECT 
                    {EUserModel.ID.value}, 
                    {EUserModel.USERNAME.value}, 
                    {EUserModel.ROLE.value}, 
                    {EUserModel.FECHA_CREACION.value}, 
                    {EUserModel.FECHA_MODIFICACION.value}
                FROM {EUserModel.TABLE.value}
            """
            result = self.db.get_data_list(query)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener lista de usuarios: {ex}"}    
