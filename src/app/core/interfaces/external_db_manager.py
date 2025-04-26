import subprocess
import shlex
import shutil
from pathlib import Path
from datetime import date
from app.config.config import DB_HOST, DB_USER, DB_PASSWORD, DB_DATABASE, DB_PORT

class ExternalDatabaseManager:
    """
    Permite importar y exportar un volcado SQL de la base de datos configurada.

    - import_dump(dump_file): importa un fichero SQL (.sql) a la base de datos,
    reemplazando el script de inicialización en app/core/interfaces/database/gestion_laboral.sql.
    - export_dump(): exporta toda la base de datos a un fichero SQL dentro de
    un directorio con la fecha actual llamado Export_DB_<YYYY-MM-DD>.
    """
    def __init__(self,
                host: str = DB_HOST,
                port: int = DB_PORT,
                user: str = DB_USER,
                password: str = DB_PASSWORD,
                database: str = DB_DATABASE):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        # Ruta al script de inicialización SQL que usa el módulo
        self.default_sql = Path(__file__).parent / "database" / "gestion_laboral.sql"

    def import_dump(self, dump_file: str) -> None:
        """
        Importa el fichero SQL especificado en la base de datos y reemplaza
        el script de inicialización local.
        """
        path = Path(dump_file)
        if not path.is_file():
            raise FileNotFoundError(f"No existe el archivo de volcado: {dump_file}")
        # 1) Reemplazar el archivo de inicialización
        try:
            shutil.copy(path, self.default_sql)
        except Exception as e:
            raise RuntimeError(f"Error al reemplazar script SQL: {e}")
        # 2) Importar a MySQL
        cmd = (
            f"mysql --host={self.host} --port={self.port} "
            f"--user={self.user} --password={shlex.quote(self.password)} "
            f"{self.database} < {shlex.quote(str(path))}"
        )
        subprocess.run(cmd, shell=True, check=True)

    def export_dump(self) -> Path:
        """
        Exporta la base de datos a un fichero SQL dentro de
        Export_DB_<YYYY-MM-DD>/<database>.sql y retorna la ruta.
        """
        # Directorio con fecha de hoy
        today = date.today().isoformat()  # 'YYYY-MM-DD'
        export_dir = Path.cwd() / f"Export_DB_{today}"
        export_dir.mkdir(parents=True, exist_ok=True)
        # Nombre del volcado
        dump_file = export_dir / f"{self.database}.sql"
        # Ejecutar mysqldump
        cmd = (
            f"mysqldump --host={self.host} --port={self.port} "
            f"--user={self.user} --password={shlex.quote(self.password)} "
            f"{self.database} > {shlex.quote(str(dump_file))}"
        )
        subprocess.run(cmd, shell=True, check=True)
        return dump_file
