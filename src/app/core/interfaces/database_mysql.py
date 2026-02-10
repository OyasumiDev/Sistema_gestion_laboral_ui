import flet as ft
from app.helpers.class_singleton import class_singleton
from app.config.config import DB_HOST, DB_USER, DB_PASSWORD, DB_DATABASE, DB_PORT
import mysql.connector as mysql
from mysql.connector import Error
import subprocess
from pathlib import Path
import os, shutil, glob, io, zipfile, json, decimal, traceback
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple
from app.views.containers.messages import mostrar_mensaje


@class_singleton
class DatabaseMysql:
    def __init__(self):
        self.host     = DB_HOST
        self.port     = DB_PORT
        self.user     = DB_USER
        self.password = DB_PASSWORD
        self.database = DB_DATABASE

        self.verificar_y_crear_base_datos()
        self.connect()

    # ---------------------- Conexión ----------------------
    def verificar_y_crear_base_datos(self) -> bool:
        created = False
        try:
            tmp = mysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password
            )
            tmp.autocommit = True
            cur = tmp.cursor()
            cur.execute(
                "SELECT SCHEMA_NAME FROM information_schema.schemata WHERE schema_name = %s",
                (self.database,)
            )
            if cur.fetchone() is None:
                cur.execute(
                    f"CREATE DATABASE `{self.database}` "
                    "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
                created = True
            cur.close()
            tmp.close()
        except Error as e:
            print(f"❌ Error al verificar/crear BD: {e}")
        return created

    def connect(self) -> None:
        try:
            self.connection = mysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )
            print("✅ Conexión exitosa a la base de datos")
        except Error as e:
            print(f"❌ Error al conectar: {e}")

    def _ensure_connection(self):
        try:
            if not getattr(self, "connection", None) or not self.connection.is_connected():
                self.connect()
        except Exception:
            self.connect()

    def disconnect(self) -> None:
        if hasattr(self, "connection") and self.connection:
            self.connection.close() 
            print("ℹ️ Conexión cerrada a la base de datos")

    def _cursor(self, dictionary: bool = False):
        self._ensure_connection()
        return self.connection.cursor(dictionary=dictionary)

    # ---------------------- Utilidades comunes ----------------------
    def _ensure_suffix(self, path: str, suffix: str) -> str:
        """
        Asegura que el archivo tenga la extensión indicada y crea la carpeta si no existe.
        """
        p = Path(path)
        if p.suffix.lower() != suffix.lower():
            p = p.with_suffix(suffix)
        if p.parent and not p.parent.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
        return str(p)

    def _find_mysql_tool(self, name: str) -> str | None:
        """
        Busca binarios (mysqldump/mysql) en:
        - src/app/core/interfaces/tools/
        - variables de entorno: MYSQL_BIN, DB_TOOLS_DIR
        - rutas típicas Windows
        - PATH del sistema
        """
        exe = name + (".exe" if os.name == "nt" else "")
        candidates = []

        # carpeta tools del proyecto
        candidates.append(Path(__file__).parent / "tools" / exe)

        # variables de entorno
        for env in ("MYSQL_BIN", "DB_TOOLS_DIR"):
            p = os.getenv(env)
            if p:
                candidates.append(Path(p) / exe)

        # instaladores comunes en Windows
        common = [
            r"C:\Program Files\MySQL\MySQL Server *\bin",
            r"C:\Program Files\MariaDB *\bin",
            r"C:\xampp\mysql\bin",
            r"C:\wamp64\bin\mysql\mysql*\bin",
        ]
        for pat in common:
            for base in glob.glob(pat):
                candidates.append(Path(base) / exe)

        # PATH
        w = shutil.which(name)
        if w:
            candidates.append(Path(w))

        for c in candidates:
            try:
                if Path(c).is_file():
                    return str(Path(c).resolve())
            except Exception:
                pass
        return None

    # ---------------------- SQL genéricos ----------------------
    def run_query(self, query: str, params: tuple = ()) -> None:
        try:
            with self._cursor() as cursor:
                cursor.execute(query, params)
                while cursor.nextset():
                    pass
            self.connection.commit()
        except mysql.Error as e:
            print(f"❌ Error ejecutando query: {e}")
            raise

    def get_data(self, query: str, params: tuple = (), dictionary: bool = False):
        try:
            cursor = self._cursor(dictionary=dictionary)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            while cursor.nextset():
                pass
            cursor.close()
            if not rows:
                return {} if dictionary else None
            return rows[0]
        except Exception as e:
            print(f"❌ Error ejecutando query: {e}")
            return {} if dictionary else None

    def get_data_list(self, query: str, params: tuple = (), dictionary: bool = False):
        try:
            cursor = self._cursor(dictionary=dictionary)
            cursor.execute(query, params)
            result = cursor.fetchall()
            while cursor.nextset():
                pass
            cursor.close()
            return result
        except Exception as e:
            print(f"❌ Error ejecutando query: {e}")
            return []

    def is_empty(self) -> bool:
        tablas = [
            "empleados", "asistencias", "pagos",
            "prestamos", "desempeno", "reportes_semanales", "usuarios_app"
        ]
        for tbl in tablas:
            try:
                with self._cursor(dictionary=True) as cur:
                    cur.execute(f"SELECT COUNT(*) AS c FROM `{tbl}`")
                    row = cur.fetchone()
                    if (row or {}).get("c", 0) > 0:
                        return False
            except Exception:
                continue
        return True

    # ---------------------- Export / Import SQL (con fallback) ----------------------
    def exportar_base_datos(self, ruta_destino: str) -> bool:
        """
        Intenta usar mysqldump. Si no está, exporta con fallback en Python (estructura + datos).
        Fuerza extensión .sql y crea carpeta destino.
        """
        try:
            ruta_destino = self._ensure_suffix(ruta_destino, ".sql")
            dump_bin = self._find_mysql_tool("mysqldump")
            if dump_bin:
                comando = [
                    dump_bin,
                    f"--user={self.user}",
                    f"--password={self.password}",
                    f"--host={self.host}",
                    f"--port={self.port}",
                    "--routines",  # incluye SP si el binario está
                    self.database,
                ]
                with open(ruta_destino, "w", encoding="utf-8") as salida:
                    subprocess.run(comando, stdout=salida, check=True)
                print(f"✅ Base de datos exportada a: {ruta_destino}")
                return True

            # ---- Fallback puro Python ----
            ok = self._exportar_sql_fallback(ruta_destino)
            if ok:
                print(f"✅ (fallback) SQL exportado en: {ruta_destino}")
            return ok

        except Exception:
            print("❌ Error al exportar la base de datos:")
            print(traceback.format_exc())
            return False

    def importar_base_datos(self, ruta_sql: str, page: ft.Page = None) -> bool:
        """
        Restaura completamente la base de datos desde un archivo .sql.
        Compatible con Flet 0.23 y MySQL 8.0.
        Incluye reconexión automática y notificación PubSub segura.
        """
        try:
            ruta = Path(ruta_sql)
            if not ruta.exists():
                raise FileNotFoundError(f"Archivo SQL no encontrado: {ruta_sql}")

            print(f"[DB_LOG] 🚀 Iniciando importación completa desde: {ruta_sql}")
            print(f"[DB_LOG] 📂 Base destino: {self.database}")

            mysql_bin = self._find_mysql_tool("mysql")
            if not mysql_bin:
                print("[DB_LOG] ⚠️ No se encontró cliente MySQL CLI, usando fallback con conector.")
                return self._import_sql_via_connector(ruta_sql, page)

            # 1️⃣ Cerrar conexión activa antes del DROP
            try:
                if hasattr(self, "connection") and self.connection.is_connected():
                    self.connection.close()
                    print("[DB_LOG] 🔒 Conexión anterior cerrada correctamente.")
            except Exception:
                pass

            # 2️⃣ Conexión temporal sin base seleccionada
            tmp = mysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password
            )
            tmp.autocommit = True
            cur = tmp.cursor()

            # 3️⃣ Eliminar y recrear la base
            print(f"[DB_LOG] 🔄 Eliminando base de datos '{self.database}' si existe...")
            cur.execute(f"DROP DATABASE IF EXISTS `{self.database}`")
            print(f"[DB_LOG] 🧱 Creando base de datos '{self.database}'...")
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{self.database}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cur.close()
            tmp.close()
            print(f"[DB_LOG] ✅ Base '{self.database}' recreada correctamente.")

            # 4️⃣ Ejecutar importación con cliente MySQL
            comando = [
                mysql_bin,
                f"-h{self.host}",
                f"-P{self.port}",
                f"-u{self.user}",
                f"-p{self.password}",
                self.database,
            ]

            print(f"[DB_LOG] ▶️ Ejecutando importación con cliente MySQL CLI...")
            with open(ruta, "r", encoding="utf-8") as f:
                resultado = subprocess.run(
                    comando,
                    stdin=f,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

            if resultado.returncode != 0:
                print("[DB_LOG] ❌ Error durante la importación CLI:")
                print(resultado.stderr)
                print("[DB_LOG] 🔁 Intentando fallback con conector MySQL interno...")
                ok = self._import_sql_via_connector(ruta_sql, page)
                if not ok:
                    return False

            print(f"[DB_LOG] ✅ Base '{self.database}' importada correctamente (via CLI).")

            # 5️⃣ Reconectar instancia principal
            print(f"[DB_LOG] 🔁 Reconectando a '{self.database}'...")
            self.connect()

            # 6️⃣ Notificación PubSub segura (compatible Flet 0.23)
            if page:
                pubsub = getattr(page, "pubsub", None)
                if pubsub:
                    try:
                        if hasattr(pubsub, "publish"):
                            pubsub.publish("db:refrescar_datos", True)
                        elif hasattr(pubsub, "send_all"):
                            try:
                                pubsub.send_all("db:refrescar_datos", True)
                            except TypeError:
                                pubsub.send_all("db:refrescar_datos")
                    except Exception:
                        pass

            print(f"[DB_LOG] 🎯 Importación finalizada sin errores.\n")
            return True

        except Exception:
            print("[DB_LOG] ❌ Error crítico en importar_base_datos():")
            print(traceback.format_exc())
            return False


    # -------- Utilidades de serialización SQL y fallbacks --------
    def _sql_literal(self, v):
        from decimal import Decimal
        if v is None:
            return "NULL"
        if isinstance(v, bool):
            return "1" if v else "0"
        if isinstance(v, (int, float, Decimal)):
            return str(v)
        if isinstance(v, datetime):
            return f"'{v.strftime('%Y-%m-%d %H:%M:%S')}'"
        if isinstance(v, date):
            return f"'{v.strftime('%Y-%m-%d')}'"
        if isinstance(v, time):
            return f"'{v.strftime('%H:%M:%S')}'"
        s = str(v).replace("\\", "\\\\").replace("'", "\\'")
        return f"'{s}'"

    def _exportar_sql_fallback(self, ruta_destino: str) -> bool:
        """
        Exporta estructura + datos en SQL (sin SP/triggers) usando el conector.
        """
        try:
            cn = self.connection
            cur = cn.cursor()
            with open(ruta_destino, "w", encoding="utf-8") as f:
                f.write("-- Fallback export (sin routines/triggers)\n")
                f.write("SET FOREIGN_KEY_CHECKS=0;\n")
                f.write("SET SQL_MODE='NO_AUTO_VALUE_ON_ZERO';\n")
                f.write("START TRANSACTION;\n")
                f.write(f"CREATE DATABASE IF NOT EXISTS `{self.database}` "
                        "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n")
                f.write(f"USE `{self.database}`;\n\n")

                # tablas
                cur.execute("""
                    SELECT TABLE_NAME FROM information_schema.tables
                    WHERE table_schema = %s AND table_type='BASE TABLE'
                    ORDER BY TABLE_NAME
                """, (self.database,))
                tables = [t[0] for t in cur.fetchall()]

                for t in tables:
                    # Estructura
                    cur.execute(f"SHOW CREATE TABLE `{t}`")
                    _, create_sql = cur.fetchone()
                    f.write(f"\n-- ----------------------------\n-- Table structure for `{t}`\n-- ----------------------------\n")
                    f.write(f"DROP TABLE IF EXISTS `{t}`;\n{create_sql};\n")

                    # Datos
                    cur.execute(f"SELECT * FROM `{t}`")
                    rows = cur.fetchall()
                    if not rows:
                        continue

                    # columnas
                    cur.execute("""
                        SELECT COLUMN_NAME FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
                        ORDER BY ORDINAL_POSITION
                    """, (self.database, t))
                    cols = [r[0] for r in cur.fetchall()]
                    cols_sql = ",".join(f"`{c}`" for c in cols)

                    f.write(f"\n-- Data for `{t}` ({len(rows)} filas)\n")
                    batch_size = 1000
                    for i in range(0, len(rows), batch_size):
                        chunk = rows[i:i+batch_size]
                        values = []
                        for r in chunk:
                            vals = ",".join(self._sql_literal(v) for v in r)
                            values.append(f"({vals})")
                        f.write(f"INSERT INTO `{t}` ({cols_sql}) VALUES\n")
                        f.write(",\n".join(values))
                        f.write(";\n")

                f.write("\nCOMMIT;\nSET FOREIGN_KEY_CHECKS=1;\n")
            print(f"✅ (fallback) SQL exportado en: {ruta_destino}")
            return True
        except Exception:
            print("❌ Error en fallback de exportación SQL:")
            print(traceback.format_exc())
            return False

    def _import_sql_via_connector(self, ruta_sql: str, page: ft.Page | None = None) -> bool:
        """
        Fallback interno: importa un archivo .sql usando mysql.connector,
        sin necesidad del cliente MySQL CLI.
        Compatible con MySQL 8.0 y Flet 0.23.
        """
        try:
            print(f"[DB_LOG] 🔁 Ejecutando importación fallback con conector MySQL...")
            cn = mysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password
            )
            cn.autocommit = True
            cur = cn.cursor()

            # 1️⃣ Recrear la base desde cero
            cur.execute(f"DROP DATABASE IF EXISTS `{self.database}`")
            cur.execute(
                f"CREATE DATABASE `{self.database}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cur.execute(f"USE `{self.database}`")

            # 2️⃣ Leer y ejecutar el SQL línea a línea
            sql = Path(ruta_sql).read_text(encoding="utf-8", errors="ignore")
            for _ in cur.execute(sql, multi=True):
                pass

            cur.close()
            cn.close()

            # 3️⃣ Reconectar instancia principal
            self.connect()
            print(f"[DB_LOG] ✅ Base '{self.database}' importada correctamente (fallback conector).")

            # 4️⃣ Notificación PubSub segura
            if page:
                pubsub = getattr(page, "pubsub", None)
                if pubsub:
                    try:
                        if hasattr(pubsub, "publish"):
                            pubsub.publish("db:refrescar_datos", True)
                        elif hasattr(pubsub, "send_all"):
                            try:
                                pubsub.send_all("db:refrescar_datos", True)
                            except TypeError:
                                pubsub.send_all("db:refrescar_datos")
                    except Exception:
                        pass

            print(f"[DB_LOG] 🎯 Importación fallback finalizada sin errores.\n")
            return True

        except Exception:
            print("[DB_LOG] ❌ Error en fallback de importación SQL:")
            print(traceback.format_exc())
            return False


    # ====================== EXPORT / IMPORT de DATOS (ZIP JSONL) ======================
    # -------- Serialización --------

    def importar_datos_zip(self, ruta_zip: str, modo: str = "truncate", batch_size: int = 1000) -> bool:
        """
        Importa masivamente datos desde un ZIP con logs detallados.
        """
        self._ensure_connection()
        cn = self.connection
        cn.start_transaction()
        try:
            cur = cn.cursor()

            print(f"[DB_LOG] 🚀 Iniciando importación de datos ZIP → {ruta_zip}")
            print(f"[DB_LOG] 📂 Base destino: {self.database}")
            print(f"[DB_LOG] ⚙️ Modo de importación: {modo}")

            with zipfile.ZipFile(ruta_zip, mode="r") as zf:
                # Tablas en ZIP
                if "meta.json" in zf.namelist():
                    meta = json.loads(zf.read("meta.json").decode("utf-8"))
                    tables_in_zip = meta.get("tables") or [
                        n[:-6] for n in zf.namelist() if n.endswith(".jsonl")
                    ]
                    print(f"[DB_LOG] 📜 meta.json detectado → {len(tables_in_zip)} tablas")
                else:
                    tables_in_zip = [n[:-6] for n in zf.namelist() if n.endswith(".jsonl")]
                    print(f"[DB_LOG] ⚠️ No se encontró meta.json, detectadas {len(tables_in_zip)} tablas JSONL")

                all_tables = self._fetch_tables(cur)
                edges = self._fetch_fks(cur)
                ordered = self._topo_sort_tables(all_tables, edges)
                target = [t for t in ordered if t in tables_in_zip]

                print(f"[DB_LOG] 🔗 Dependencias FK procesadas: {len(edges)} relaciones detectadas")
                print(f"[DB_LOG] 🧩 Orden final de importación: {target}")

                cur.execute("SET FOREIGN_KEY_CHECKS = 0")

                total_inserts = 0
                for t in target:
                    name = f"{t}.jsonl"
                    if name not in zf.namelist():
                        print(f"[DB_LOG] ⚠️ Tabla '{t}' no encontrada en ZIP, omitida.")
                        continue
                    lines = zf.read(name).decode("utf-8").splitlines()
                    print(f"[DB_LOG] 📦 Procesando tabla '{t}' con {len(lines)} registros...")

                    cols = self._fetch_table_columns(cur, t)
                    if modo == "truncate":
                        cur.execute(f"TRUNCATE TABLE `{t}`")
                        cn.commit()
                        print(f"[DB_LOG] 🚮 Tabla '{t}' truncada.")

                    if not lines:
                        continue

                    placeholders = ",".join(["%s"] * len(cols))
                    cols_sql = ",".join([f"`{c}`" for c in cols])

                    if modo == "upsert":
                        updates = ",".join([f"`{c}`=VALUES(`{c}`)" for c in cols])
                        sql = f"INSERT INTO `{t}` ({cols_sql}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {updates}"
                    elif modo == "insert_ignore":
                        sql = f"INSERT IGNORE INTO `{t}` ({cols_sql}) VALUES ({placeholders})"
                    else:
                        sql = f"INSERT INTO `{t}` ({cols_sql}) VALUES ({placeholders})"

                    batch = []
                    for line in lines:
                        obj = json.loads(line)
                        vals = [self._json_to_db(obj.get(c)) for c in cols]
                        batch.append(vals)
                        if len(batch) >= batch_size:
                            cur.executemany(sql, batch)
                            total_inserts += len(batch)
                            batch.clear()
                    if batch:
                        cur.executemany(sql, batch)
                        total_inserts += len(batch)

                    print(f"[DB_LOG] ✅ Tabla '{t}' importada ({total_inserts} filas acumuladas).")

                cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            cn.commit()

            print(f"[DB_LOG] 🎯 Importación ZIP completada correctamente en base '{self.database}'.")
            print(f"[DB_LOG] 🧾 Total de registros importados: {total_inserts}")
            print(f"[DB_LOG] ✅ Proceso finalizado sin errores.\n")
            return True

        except Exception:
            cn.rollback()
            print(f"[DB_LOG] ❌ Error durante importación ZIP en base '{self.database}':")
            print(traceback.format_exc())
            return False
        finally:
            try:
                cur.close()
            except Exception:
                pass


    def _py_to_json(self, v):
        # Normaliza valores Python a tipos JSON-serializables
        if v is None:
            return None

        # Fechas / horas
        if isinstance(v, (datetime, date)):
            return v.isoformat()
        if isinstance(v, time):
            return v.strftime("%H:%M:%S")
        if isinstance(v, timedelta):
            # MySQL TIME → timedelta. Lo convertimos a HH:MM:SS (soporta negativos)
            total = int(v.total_seconds())
            sign = "-" if total < 0 else ""
            total = abs(total)
            h = total // 3600
            m = (total % 3600) // 60
            s = total % 60
            return f"{sign}{h:02d}:{m:02d}:{s:02d}"

        # Números decimales
        if isinstance(v, decimal.Decimal):
            return str(v)

        # Binarios: intenta texto UTF-8, si no, Base64 con marca
        if isinstance(v, (bytes, bytearray, memoryview)):
            try:
                return bytes(v).decode("utf-8")
            except Exception:
                import base64
                return {"__b64__": True, "data": base64.b64encode(bytes(v)).decode("ascii")}

        # Conjuntos / tuplas → lista
        if isinstance(v, (set, tuple)):
            return list(v)

        # Fallback: si JSON lo acepta, devuélvelo; si no, str()
        try:
            json.dumps(v)
            return v
        except TypeError:
            return str(v)

    def _json_to_db(self, v):
        # Reconversión mínima (por ahora solo binarios envueltos)
        if isinstance(v, dict) and v.get("__b64__") and "data" in v:
            import base64
            try:
                return base64.b64decode(v["data"])
            except Exception:
                return None
        return v


    # -------- Metadatos de esquema (robustos a cursor diccionario/tupla) --------
    def _fetch_tables(self, cursor) -> List[str]:
        cursor.execute("""
            SELECT TABLE_NAME
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_type = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        rows = cursor.fetchall()
        if not rows:
            return []
        if isinstance(rows[0], dict):
            return [r.get("TABLE_NAME") for r in rows if r.get("TABLE_NAME")]
        return [r[0] for r in rows]

    def _fetch_table_columns(self, cursor, table: str) -> List[str]:
        cursor.execute("""
            SELECT COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """, (table,))
        rows = cursor.fetchall()
        if not rows:
            return []
        if isinstance(rows[0], dict):
            return [r.get("COLUMN_NAME") for r in rows if r.get("COLUMN_NAME")]
        return [r[0] for r in rows]

    def _fetch_fks(self, cursor) -> List[Tuple[str, str]]:
        """
        Devuelve aristas (padre -> hijo) entre tablas de la BD actual.
        Soporta filas dict o tupla (evita KeyError/ValueError).
        """
        cursor.execute("""
            SELECT
              kcu.REFERENCED_TABLE_NAME AS parent_table,
              kcu.TABLE_NAME            AS child_table
            FROM information_schema.KEY_COLUMN_USAGE kcu
            WHERE kcu.CONSTRAINT_SCHEMA = DATABASE()
              AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
        """)
        rows = cursor.fetchall()
        edges: List[Tuple[str, str]] = []
        if not rows:
            return edges
        if isinstance(rows[0], dict):
            for r in rows:
                p = r.get("parent_table")
                c = r.get("child_table")
                if p and c:
                    edges.append((p, c))
        else:
            for tup in rows:
                try:
                    p, c = tup[0], tup[1]
                    if p and c:
                        edges.append((p, c))
                except Exception:
                    continue
        return edges

    # -------- Exportación: ZIP JSONL --------
    def exportar_datos_zip(self, ruta_zip: str, tablas: Optional[List[str]] = None, batch_size: int = 2000) -> bool:
        """
        Exporta datos de tablas a un ZIP con:
        - meta.json
        - {tabla}.jsonl   (una línea por registro en JSON)
        """
        self._ensure_connection()
        cn = self.connection
        cur = None
        try:
            cur = cn.cursor(dictionary=True)

            # 1) Determinar tablas a exportar
            all_tables = self._fetch_tables(cur)
            target = [t for t in all_tables if t in (tablas or all_tables)]

            # 2) Crear ZIP y escribir metadatos
            with zipfile.ZipFile(ruta_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                meta = {
                    "db": self.database,
                    "dumped_at": datetime.utcnow().isoformat() + "Z",
                    "tables": target,
                    "format": "jsonl",
                    "version": 1,
                }
                zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))

                # 3) Escribir cada tabla como JSONL
                for t in target:
                    cur.execute(f"SELECT * FROM `{t}`")
                    rows = cur.fetchall()

                    buf = io.StringIO()
                    for r in rows:
                        # ⬇️ Parche: NO mutar 'r' y normalizar tipos (incluye timedelta → HH:MM:SS)
                        sanitized = {k: self._py_to_json(v) for k, v in r.items()}
                        buf.write(json.dumps(sanitized, ensure_ascii=False))
                        buf.write("\n")

                    zf.writestr(f"{t}.jsonl", buf.getvalue())

            print(f"✅ Datos exportados a ZIP: {ruta_zip}")
            return True

        except Exception as e:
            print(f"❌ Error al exportar datos ZIP: {e}")
            return False
        finally:
            try:
                if cur:
                    cur.close()
            except Exception:
                pass

    # -------- Importación: ZIP JSONL (masiva) --------
    def importar_datos_zip(self, ruta_zip: str, modo: str = "truncate", batch_size: int = 1000) -> bool:
        """
        Importa masivamente datos desde un ZIP:
          - 'truncate'       -> TRUNCATE + INSERT
          - 'upsert'         -> INSERT ... ON DUPLICATE KEY UPDATE ...
          - 'insert_ignore'  -> INSERT IGNORE ...
        Inserta respetando orden de dependencias (FKs). Desactiva FK temporalmente.
        """
        self._ensure_connection()
        cn = self.connection
        cn.start_transaction()
        try:
            cur = cn.cursor()

            with zipfile.ZipFile(ruta_zip, mode="r") as zf:
                # Tablas en ZIP
                if "meta.json" in zf.namelist():
                    meta = json.loads(zf.read("meta.json").decode("utf-8"))
                    tables_in_zip = meta.get("tables") or [
                        n[:-6] for n in zf.namelist() if n.endswith(".jsonl")
                    ]
                else:
                    tables_in_zip = [n[:-6] for n in zf.namelist() if n.endswith(".jsonl")]

                # Orden por FKs
                all_tables = self._fetch_tables(cur)
                edges = self._fetch_fks(cur)
                ordered = self._topo_sort_tables(all_tables, edges)
                target = [t for t in ordered if t in tables_in_zip]

                # Desactivar FK checks
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")

                for t in target:
                    name = f"{t}.jsonl"
                    if name not in zf.namelist():
                        continue
                    lines = zf.read(name).decode("utf-8").splitlines()

                    cols = self._fetch_table_columns(cur, t)  # columnas reales (ordenadas)
                    if modo == "truncate":
                        cur.execute(f"TRUNCATE TABLE `{t}`")
                        cn.commit()  # libera espacio y evita locks prolongados

                    if not lines:
                        continue

                    placeholders = ",".join(["%s"] * len(cols))
                    cols_sql = ",".join([f"`{c}`" for c in cols])

                    if modo == "upsert":
                        updates = ",".join([f"`{c}`=VALUES(`{c}`)" for c in cols])
                        sql = f"INSERT INTO `{t}` ({cols_sql}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {updates}"
                    elif modo == "insert_ignore":
                        sql = f"INSERT IGNORE INTO `{t}` ({cols_sql}) VALUES ({placeholders})"
                    else:
                        sql = f"INSERT INTO `{t}` ({cols_sql}) VALUES ({placeholders})"

                    batch = []
                    for line in lines:
                        obj = json.loads(line)
                        vals = [self._json_to_db(obj.get(c)) for c in cols]
                        batch.append(vals)
                        if len(batch) >= batch_size:
                            cur.executemany(sql, batch)
                            batch.clear()
                    if batch:
                        cur.executemany(sql, batch)

                # Reactivar FK checks
                cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            cn.commit()

            print("✅ Importación ZIP completada.")
            return True
        except Exception:
            cn.rollback()
            print("❌ Error al importar datos ZIP:")
            print(traceback.format_exc())
            return False
        finally:
            try:
                cur.close()
            except Exception:
                pass

    # ---------------------- Limpieza total de tablas ----------------------
    def clear_tables(self) -> bool:
        """
        Borra TODO el contenido de TODAS las tablas de la base de datos actual.
        - Respeta el orden de dependencias FK (trunca hijos antes que padres).
        - Desactiva FOREIGN_KEY_CHECKS temporalmente.
        - Devuelve True si se completa sin errores.
        """
        import traceback
        cur = None
        fk_disabled = False
        try:
            self._ensure_connection()
            cn = self.connection
            cur = cn.cursor()

            print(f"[DB_LOG] ⚠️ Iniciando limpieza completa de todas las tablas en '{self.database}'...")
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            fk_disabled = True

            # Obtener todas las tablas base
            cur.execute("""
                SELECT TABLE_NAME 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() AND table_type='BASE TABLE'
                ORDER BY TABLE_NAME
            """)
            tables = [r[0] for r in cur.fetchall()]
            if not tables:
                print("[DB_LOG] ℹ️ No se encontraron tablas en la base de datos.")
                return True

            # Obtener dependencias (padre -> hijo)
            edges = self._fetch_fks(cur)
            # Invertimos dependencias para truncar primero las tablas hijas
            order = self._topo_sort_tables(tables, edges)
            order.reverse()  # truncar hijos → padres

            for tbl in order:
                try:
                    cur.execute(f"TRUNCATE TABLE `{tbl}`")
                    print(f"[DB_LOG] 🧹 Tabla '{tbl}' limpiada correctamente.")
                except Exception as e:
                    print(f"[DB_LOG] ⚠️ No se pudo limpiar tabla '{tbl}': {e}")

            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            fk_disabled = False
            cn.commit()

            print(f"[DB_LOG] ✅ Limpieza completa finalizada correctamente en '{self.database}'.\n")

            # ✅ Mostrar mensaje si hay acceso a la interfaz
            try:
                from app.views.containers.messages import mostrar_mensaje
                if hasattr(self, "page") and self.page:
                    mostrar_mensaje(
                        self.page,
                        "✅ Limpieza completada",
                        f"Todas las tablas de '{self.database}' fueron limpiadas correctamente."
                    )
                else:
                    print(f"[DB_LOG] ✅ Todas las tablas de '{self.database}' fueron limpiadas correctamente (sin UI).")
            except Exception:
                print(f"[DB_LOG] ✅ Limpieza completada (sin mostrar mensaje en UI).")

            return True

        except Exception:
            print(f"[DB_LOG] ❌ Error crítico al limpiar tablas en '{self.database}':")
            print(traceback.format_exc())

            try:
                from app.views.containers.messages import mostrar_mensaje
                if hasattr(self, "page") and self.page:
                    mostrar_mensaje(
                        self.page,
                        "❌ Error al limpiar",
                        f"Ocurrió un error al limpiar todas las tablas de '{self.database}'. Revisa la consola."
                    )
            except Exception:
                pass

            return False

        finally:
            try:
                if fk_disabled and getattr(self, "connection", None):
                    c2 = self.connection.cursor()
                    c2.execute("SET FOREIGN_KEY_CHECKS = 1")
                    self.connection.commit()
                    c2.close()
            except Exception:
                pass
            try:
                if cur:
                    cur.close()
            except Exception:
                pass
            try:
                self._ensure_connection()
            except Exception:
                pass


    # ---------------------- Helpers para limpieza de tablas ----------------------
    def _fetch_fks(self, cursor):
        """
        Devuelve un diccionario con las relaciones de claves foráneas:
        { tabla_hija: [tabla_padre, ...], ... }
        """
        cursor.execute("""
            SELECT
                TABLE_NAME AS child_table,
                REFERENCED_TABLE_NAME AS parent_table
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE
                TABLE_SCHEMA = DATABASE()
                AND REFERENCED_TABLE_NAME IS NOT NULL
        """)
        deps = {}
        for child, parent in cursor.fetchall():
            deps.setdefault(child, []).append(parent)
        return deps


    def _topo_sort_tables(self, tables: list[str], edges: dict[str, list[str]]):
        """
        Ordena las tablas topológicamente (padres antes que hijos).
        Usa DFS para evitar dependencias cíclicas.
        """
        visited = set()
        temp = set()
        result = []

        def visit(node):
            if node in visited:
                return
            if node in temp:
                print(f"[DB_LOG] ⚠️ Dependencia cíclica detectada en {node}. Se omitirá parcialmente.")
                return
            temp.add(node)
            for parent in edges.get(node, []):
                if parent in tables:
                    visit(parent)
            temp.remove(node)
            visited.add(node)
            result.append(node)

        for t in tables:
            visit(t)
        return result
