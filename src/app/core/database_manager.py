from app.core.interfaces.database_mysql import DatabaseMysql
from app.helpers.class_singleton import class_singleton
from app.config.config import DB_TYPE

@class_singleton
class DatabaseManager:
    
    def __new__(cls, db_type=DB_TYPE):
        """
        Sobreescribimos __new__ para que DatabaseManager herede directamente
        de la implementación de base de datos seleccionada.
        """

        db_classes = {
            'mysql': DatabaseMysql,
        }

        if db_type not in db_classes:
            raise ValueError(f"Tipo de base de datos desconocido: {db_type}, o no implementado.")

        print(f'Usando base de datos {db_type}')

        class DynamicDatabaseManager(db_classes[db_type]):
            pass

        instance = super().__new__(DynamicDatabaseManager)
        instance.__init__()

        return instance
