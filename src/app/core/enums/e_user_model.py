from enum import Enum

class EUserModel(Enum):
    ID = 'id'
    USERNAME = 'username'
    PASSWORD = 'password_hash'
    ROLE = 'role'

    def __str__(self):
        return self.value