from app.core.enums.e_user_model import E_USER
from app.core.interfaces.database_mysql import DatabaseMysql

class UserModel:
    """
    Modelo de usuarios.
    """

    def __init__(self):
        # Se obtiene la instancia centralizada de la base de datos.
        self.db = DatabaseMysql()
        
        # Se verifica y crea el usuario root si no existe.
        self.check_root_user()
        

    def check_table(self) -> bool:
        """
        Verifica si la tabla existe.
        :return: True si la tabla existe, False en caso contrario.
        """
        query = "SHOW TABLES"
        result_tables = self.db.get_data_list(query) 

        # Detectamos el nombre de la columna (usualmente: 'Tables_in_<nombre_base>')
        if result_tables:
            key = list(result_tables[0].keys())[0]
            for tabla in result_tables:
                if tabla[key] == E_USER.TABLE.value:
                    self._exits_table = True
                    return True
        return False

    def check_root_user(self):
        """
        Verifica si existe el usuario root y en caso de que no exista, lo crea.
        """
        # Consulta parametrizada para evitar inyección y problemas de comillas.
        query = f"SELECT * FROM {E_USER.TABLE.value} WHERE {E_USER.USERNAME.value} = %s"
        result = self.db.get_data_list(query, ('root',))
        if not result:
            default_password = 'root'  # Se recomienda cambiar y hashear esta contraseña en producción.
            self.add('root', default_password, role='root')

    def add(self, username: str, password_hash: str, role: str = 'user') -> dict:
        try:
            query = f"""
            INSERT INTO {E_USER.TABLE.value}
                ({E_USER.USERNAME.value}, {E_USER.PASSWORD.value}, {E_USER.ROLE.value})
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
            query = f"SELECT * FROM {E_USER.TABLE.value}"
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
                SELECT * FROM {E_USER.TABLE.value}
                WHERE {E_USER.ID.value} = %s
            """
            result = self.db.get_data(query, (user_id,))
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener usuario por ID: {ex}"}

    def get_by_username(self, username: str) -> dict | None:
        """
        Retorna un diccionario con los datos del usuario o None si no existe.
        """
        try:
            query = f"SELECT * FROM {E_USER.TABLE.value} WHERE {E_USER.USERNAME.value} = %s"
            result = self.db.get_data(query, (username,))
            return result
            # print(result)
        except Exception as ex:
            print(f"Error al obtener usuario por nombre de usuario: {ex}")
            return None


    def get_users(self) -> dict:
        """
        Retorna todos los usuarios sin mostrar la contraseña hash.
        """
        try:
            query = f"""
                SELECT 
                    {E_USER.ID.value},
                    {E_USER.USERNAME.value},
                    {E_USER.ROLE.value},
                    {E_USER.FECHA_CREACION.value},
                    {E_USER.FECHA_MODIFICACION.value}
                FROM {E_USER.TABLE.value}
            """
            result = self.db.get_data_list(query)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener lista de usuarios: {ex}"}
