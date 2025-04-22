from enum import Enum

class E_USER(Enum):
    TABLE = 'usuarios_app'
    ID = 'id_usuario'
    USERNAME = 'username'
    PASSWORD = 'password_hash'
    ROLE = 'role'
    FECHA_CREACION = 'fecha_creacion'
    FECHA_MODIFICACION = 'fecha_modificacion'