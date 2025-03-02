from abc import ABC, abstractmethod


class Database(ABC):
    def __init__(self, user, password, database, host, port = None, ):
        self.host = host
        self.port = port
        self.user = user
        self.password= password
        self.database = database
        self.conn = None
        self._connect()
    
    @abstractmethod
    def _connect(self):
        pass

    @abstractmethod
    def _disconnect(self):
        pass

    @abstractmethod
    def run_query(self, query, params=()) -> bool:
        pass

    @abstractmethod
    def get_data(self, query, params=()) -> list:
        pass
    
    @abstractmethod
    def get_data_list(self, query, params=()) -> list:
        pass
