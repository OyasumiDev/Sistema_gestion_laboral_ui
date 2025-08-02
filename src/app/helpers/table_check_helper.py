from app.core.interfaces.database_mysql import DatabaseMysql

class TablaCheckerHelper:
    def __init__(self):
        self.db = DatabaseMysql()

    def existe_tabla(self, nombre_tabla: str) -> bool:
        """Verifica si una tabla existe en la base de datos."""
        query = """
            SELECT COUNT(*) AS c
            FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
        """
        result = self.db.get_data(query, (self.db.database, nombre_tabla), dictionary=True)
        return result.get("c", 0) > 0

    def crear_tabla_si_no_existe(self, nombre_tabla: str, ddl_sql: str, tablas_requeridas: list[str] = None) -> bool:
        """
        Crea una tabla si no existe, validando que las tablas requeridas estén presentes.

        :param nombre_tabla: Nombre de la tabla a crear.
        :param ddl_sql: Instrucción SQL completa para crear la tabla.
        :param tablas_requeridas: Lista de nombres de tablas que deben existir antes.
        :return: True si la tabla existe o fue creada, False si no se pudo crear.
        """
        try:
            if self.existe_tabla(nombre_tabla):
                print(f"✔️ La tabla {nombre_tabla} ya existe.")
                return True

            if tablas_requeridas:
                for tabla in tablas_requeridas:
                    if not self.existe_tabla(tabla):
                        print(f"❌ No se puede crear {nombre_tabla} porque falta la tabla requerida: {tabla}")
                        return False

            print(f"⚠️ La tabla {nombre_tabla} no existe. Creando...")
            self.db.run_query(ddl_sql)
            print(f"✅ Tabla {nombre_tabla} creada correctamente.")
            return True

        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {nombre_tabla}: {ex}")
            return False
