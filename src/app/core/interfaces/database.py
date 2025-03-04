from abc import ABC, abstractmethod

class Database(ABC):
    def __init__(self):
        self.host: str = None
        self.port: str = None
        self.user: str = None
        self.password: str = None
        self.database: str = None
        self.conn = None
        self._connect()

    @abstractmethod
    def _connect(self) -> None:
        """
        Conexion a la base de datos
        :return:
        """
        pass

    @abstractmethod
    def _disconnect(self) -> None:
        """
        Se desconecta de a la base de datos
        :return:
        """
        pass

    @abstractmethod
    def run_query(self, query: str, params=()) -> bool:
        """
        Ejecuta las consultas a la base de datos
        :param query:
        :param params:
        :return:
        """
        pass

    @abstractmethod
    def get_data(self, query: str, params=()) -> dict:
        """
        Obtiene los datos de mysql en formato de diccionario
        :param query:
        :param params:
        :return:
        """
        pass
    
    @abstractmethod
    def get_data_list(self, query: str, params=()) -> list:
        """
        Obtiene los datos de mysql en formato de lista
        :param query:
        :param params:
        :return:
        """
        pass
