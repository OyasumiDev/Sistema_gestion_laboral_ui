from app.core.enums.e_user_model import E_USER
from app.core.interfaces.database_mysql import DatabaseMysql

class UserModel:
    def __init__(self):
        self.db = DatabaseMysql()
        self.check_table()
        self.check_root_user()

    def check_table(self) -> bool:
        try:
            query = """
                SELECT COUNT(*) AS c FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, E_USER.TABLE.value), dictionary=True)
            if result.get("c", 0) == 0:
                print(f"⚠️ Tabla '{E_USER.TABLE.value}' no existe. Creando...")
                create_query = f"""
                CREATE TABLE {E_USER.TABLE.value} (
                    {E_USER.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {E_USER.USERNAME.value} VARCHAR(100) NOT NULL UNIQUE,
                    {E_USER.PASSWORD.value} VARCHAR(255) NOT NULL,
                    {E_USER.ROLE.value} ENUM('root','user') NOT NULL DEFAULT 'user',
                    {E_USER.FECHA_CREACION.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    {E_USER.FECHA_MODIFICACION.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print("✅ Tabla creada correctamente.")
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear tabla: {ex}")
            return False

    def check_root_user(self):
        try:
            query = f"SELECT 1 FROM {E_USER.TABLE.value} WHERE {E_USER.USERNAME.value} = %s"
            result = self.db.get_data_list(query, ('root',), dictionary=True)

            if not result:
                print("🔐 Usuario root no encontrado. Creando usuarios por defecto...")
                self.add('root', 'root', 'root')        # ⚠️ Hashear en producción
                self.add('usuario', 'usuario', 'usuario')  # ⚠️ Hashear en producción también
            else:
                print("✅ Usuario root ya existe. No se crean usuarios por defecto.")
        except Exception as ex:
            print(f"❌ Error verificando root: {ex}")


    def add(self, username: str, password_hash: str, role: str = 'user') -> dict:
        try:
            if self.get_by_username(username):
                return {"status": "error", "message": f"El usuario '{username}' ya existe."}
            query = f"""
                INSERT INTO {E_USER.TABLE.value} 
                    ({E_USER.USERNAME.value}, {E_USER.PASSWORD.value}, {E_USER.ROLE.value})
                VALUES (%s, %s, %s)
            """
            self.db.run_query(query, (username, password_hash, role))
            return {"status": "success", "message": f"Usuario '{username}' agregado correctamente."}
        except Exception as ex:
            return {"status": "error", "message": f"Error al agregar usuario: {ex}"}

    def get(self) -> dict:
        try:
            query = f"SELECT * FROM {E_USER.TABLE.value}"
            result = self.db.get_data_list(query, dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener usuarios: {ex}"}


    def get_by_id(self, user_id: int) -> dict:
        try:
            query = f"SELECT * FROM {E_USER.TABLE.value} WHERE {E_USER.ID.value} = %s"
            result = self.db.get_data(query, (user_id,), dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener usuario por ID: {ex}"}

    def get_by_username(self, username: str) -> dict | None:
        try:
            query = f"SELECT * FROM {E_USER.TABLE.value} WHERE {E_USER.USERNAME.value} = %s"
            return self.db.get_data(query, (username,), dictionary=True)
        except Exception as ex:
            print(f"❌ Error al obtener usuario por nombre: {ex}")
            return None

    def get_users(self) -> dict:
        try:
            query = f"""
                SELECT 
                    {E_USER.ID.value} AS id,
                    {E_USER.USERNAME.value} AS username,
                    {E_USER.ROLE.value} AS role,
                    {E_USER.FECHA_CREACION.value} AS fecha_creacion,
                    {E_USER.FECHA_MODIFICACION.value} AS fecha_modificacion
                FROM {E_USER.TABLE.value}
            """
            result = self.db.get_data_list(query, dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener lista de usuarios: {ex}"}

    def delete_by_id(self, user_id: int) -> dict:
        try:
            query = f"DELETE FROM {E_USER.TABLE.value} WHERE {E_USER.ID.value} = %s"
            self.db.run_query(query, (user_id,))
            return {"status": "success", "message": f"Usuario con ID {user_id} eliminado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al eliminar usuario: {ex}"}

    def get_last_id(self) -> int:
        try:
            query = f"SELECT MAX({E_USER.ID.value}) AS last_id FROM {E_USER.TABLE.value}"
            result = self.db.get_data(query, dictionary=True)
            return result.get("last_id", 0) or 0
        except Exception as ex:
            print(f"❌ Error al obtener el último ID: {ex}")
            return 0
        
    def get_password(self, user_id: int) -> dict:
        """
        Retorna la contraseña de un usuario específico.
        """
        try:
            query = f"SELECT {E_USER.PASSWORD.value} FROM {E_USER.TABLE.value} WHERE {E_USER.ID.value} = %s"
            result = self.db.get_data(query, (user_id,), dictionary=True)
            if result:
                return {"status": "success", "data": result[E_USER.PASSWORD.value]}
            return {"status": "error", "message": "Usuario no encontrado"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener contraseña: {ex}"}

