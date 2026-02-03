from __future__ import annotations

import os
import base64
import hashlib
import hmac
from typing import Any, Dict, Optional, Tuple, List

from app.core.enums.e_user_model import E_USER
from app.core.interfaces.database_mysql import DatabaseMysql


class UserModel:
    PBKDF2_PREFIX = "pbkdf2_sha256"
    DEFAULT_ITERATIONS = 200_000

    def __init__(self):
        self.db = DatabaseMysql()
        self.check_table()
        self.check_root_user()

    # -------------------------
    # Retorno estándar
    # -------------------------
    def _ok(self, message: str = "ok", data: Any = None, rows_affected: int = 0) -> Dict[str, Any]:
        return {
            "ok": True,
            "status": "success",
            "message": message,
            "data": data,
            "rows_affected": int(rows_affected or 0),
        }

    def _err(self, message: str, data: Any = None, rows_affected: int = 0) -> Dict[str, Any]:
        return {
            "ok": False,
            "status": "error",
            "message": str(message),
            "data": data,
            "rows_affected": int(rows_affected or 0),
        }

    # -------------------------
    # Sanitización / validación
    # -------------------------
    def _sanitize_username(self, username: str) -> str:
        return (username or "").strip()

    def _sanitize_role(self, role: str) -> str:
        r = (role or "").strip() or "user"
        if r not in ("root", "user"):
            raise ValueError("Rol inválido. Solo se permite 'root' o 'user'.")
        return r

    def _ensure_int_id(self, user_id: Any) -> int:
        try:
            return int(user_id)
        except Exception:
            raise ValueError("ID de usuario inválido.")

    # -------------------------
    # Password hashing PBKDF2
    # -------------------------
    def hash_password(self, password: str, *, iterations: int = DEFAULT_ITERATIONS) -> str:
        pwd = (password or "").strip()
        if not pwd:
            raise ValueError("La contraseña no puede estar vacía.")
        salt = os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt, int(iterations), dklen=32)
        return f"{self.PBKDF2_PREFIX}${int(iterations)}${base64.b64encode(salt).decode('ascii')}${base64.b64encode(dk).decode('ascii')}"

    def verify_password(self, password: str, stored_hash: str) -> bool:
        try:
            pwd = (password or "").strip()
            sh = (stored_hash or "").strip()
            if not pwd or not sh:
                return False

            parts = sh.split("$")
            if len(parts) != 4:
                return False
            prefix, it_s, salt_b64, dk_b64 = parts
            if prefix != self.PBKDF2_PREFIX:
                return False

            iterations = int(it_s)
            salt = base64.b64decode(salt_b64.encode("ascii"))
            dk_expected = base64.b64decode(dk_b64.encode("ascii"))

            dk = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt, iterations, dklen=len(dk_expected))
            return hmac.compare_digest(dk, dk_expected)
        except Exception:
            return False

    def is_pbkdf2_hash(self, value: str) -> bool:
        v = (value or "").strip()
        return v.startswith(self.PBKDF2_PREFIX + "$") and v.count("$") == 3

    # -------------------------
    # Exec wrapper (sin pelear con tu wrapper)
    # -------------------------
    def _exec(self, query: str, params: Tuple = ()) -> int:
        if hasattr(self.db, "run_query"):
            out = self.db.run_query(query, params)
            return int(out) if isinstance(out, int) else 0
        if hasattr(self.db, "execute_query"):
            out = self.db.execute_query(query, params)
            return int(out) if isinstance(out, int) else 0

        conn = getattr(self.db, "connection", None)
        if conn is not None:
            cur = conn.cursor()
            try:
                cur.execute(query, params)
                ra = cur.rowcount
                conn.commit()
                return int(ra or 0)
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise
            finally:
                try:
                    cur.close()
                except Exception:
                    pass

        raise RuntimeError("DatabaseMysql no expone run_query/execute_query/connection.")

    # -------------------------
    # Schema / bootstrap
    # -------------------------
    def check_table(self) -> bool:
        try:
            query = """
                SELECT COUNT(*) AS c FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            db_name = getattr(self.db, "database", None)
            if not db_name:
                raise RuntimeError("DatabaseMysql no expone self.db.database (schema).")

            result = self.db.get_data(query, (db_name, E_USER.TABLE.value), dictionary=True) or {}
            if int(result.get("c", 0) or 0) == 0:
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
                self._exec(create_query)
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear tabla: {ex}")
            return False

    def check_root_user(self) -> None:
        try:
            query = f"SELECT COUNT(*) AS total FROM {E_USER.TABLE.value}"
            result = self.db.get_data(query, (), dictionary=True) or {}
            total = int(result.get("total", 0) or 0)
            if total == 0:
                self.add(username="root", password="root", role="root")
                self.add(username="usuario", password="usuario", role="user")
        except Exception as ex:
            print(f"❌ Error verificando usuarios por defecto: {ex}")

    # -------------------------
    # Helpers
    # -------------------------
    def count_roots(self) -> int:
        try:
            q = f"SELECT COUNT(*) AS c FROM {E_USER.TABLE.value} WHERE {E_USER.ROLE.value} = 'root'"
            r = self.db.get_data(q, (), dictionary=True) or {}
            return int(r.get("c", 0) or 0)
        except Exception:
            return 0

    # -------------------------
    # Queries (compat UI)
    # -------------------------
    def get_users(self) -> Dict[str, Any]:
        try:
            query = f"""
                SELECT
                    {E_USER.ID.value} AS id,
                    {E_USER.USERNAME.value} AS username,
                    {E_USER.ROLE.value} AS role,
                    {E_USER.FECHA_CREACION.value} AS fecha_creacion,
                    {E_USER.FECHA_MODIFICACION.value} AS fecha_modificacion
                FROM {E_USER.TABLE.value}
                ORDER BY {E_USER.ID.value} ASC
            """
            result = self.db.get_data_list(query, dictionary=True) or []
            return self._ok("ok", result, 0)
        except Exception as ex:
            return self._err(f"Error al obtener lista de usuarios: {ex}")

    def get_last_id(self) -> int:
        try:
            query = f"SELECT MAX({E_USER.ID.value}) AS last_id FROM {E_USER.TABLE.value}"
            result = self.db.get_data(query, (), dictionary=True) or {}
            return int(result.get("last_id", 0) or 0)
        except Exception:
            return 0

    # -------------------------
    # CRUD
    # -------------------------
    def get_by_username(self, username: str) -> Optional[dict]:
        try:
            u = self._sanitize_username(username)
            if not u:
                return None
            query = f"SELECT * FROM {E_USER.TABLE.value} WHERE {E_USER.USERNAME.value} = %s"
            return self.db.get_data(query, (u,), dictionary=True)
        except Exception:
            return None

    def add(self, username: str, password: str, role: str = "user", *, password_hash: Optional[str] = None) -> Dict[str, Any]:
        try:
            u = self._sanitize_username(username)
            if not u:
                return self._err("El nombre de usuario no puede estar vacío.")

            r = self._sanitize_role(role)

            if self.get_by_username(u):
                return self._err(f"El usuario '{u}' ya existe.")

            if password_hash:
                ph = str(password_hash).strip()
                if not self.is_pbkdf2_hash(ph):
                    return self._err("password_hash inválido (se esperaba pbkdf2_sha256$...).")
                pw_hash = ph
            else:
                pw_hash = self.hash_password(password)

            query = f"""
                INSERT INTO {E_USER.TABLE.value}
                    ({E_USER.USERNAME.value}, {E_USER.PASSWORD.value}, {E_USER.ROLE.value})
                VALUES (%s, %s, %s)
            """
            ra = self._exec(query, (u, pw_hash, r))
            fresh = self.db.get_data(
                f"""
                SELECT
                    {E_USER.ID.value} AS id,
                    {E_USER.USERNAME.value} AS username,
                    {E_USER.ROLE.value} AS role,
                    {E_USER.FECHA_CREACION.value} AS fecha_creacion,
                    {E_USER.FECHA_MODIFICACION.value} AS fecha_modificacion
                FROM {E_USER.TABLE.value}
                WHERE {E_USER.USERNAME.value} = %s
                ORDER BY {E_USER.ID.value} DESC
                LIMIT 1
                """,
                (u,),
                dictionary=True,
            )
            return self._ok(f"Usuario '{u}' agregado correctamente.", fresh, ra)
        except Exception as ex:
            return self._err(f"Error al agregar usuario: {ex}")

    def delete_by_id(self, user_id: int) -> Dict[str, Any]:
        try:
            uid = self._ensure_int_id(user_id)
            current = self.db.get_data(
                f"SELECT {E_USER.ROLE.value} AS role FROM {E_USER.TABLE.value} WHERE {E_USER.ID.value} = %s",
                (uid,),
                dictionary=True,
            )
            if not current:
                return self._err("Usuario no encontrado.")

            if str(current.get("role")) == "root" and self.count_roots() == 1:
                return self._err("No puedes eliminar el último usuario root.")

            ra = self._exec(f"DELETE FROM {E_USER.TABLE.value} WHERE {E_USER.ID.value} = %s", (uid,))
            return self._ok(f"Usuario con ID {uid} eliminado correctamente.", None, ra)
        except Exception as ex:
            return self._err(f"Error al eliminar usuario: {ex}")

    def update(self, user_id: int, campos: Dict[str, Any]) -> Dict[str, Any]:
        try:
            uid = self._ensure_int_id(user_id)
            if not isinstance(campos, dict):
                return self._err("Campos inválidos: se esperaba dict.")

            current = self.db.get_data(
                f"""
                SELECT
                    {E_USER.USERNAME.value} AS username,
                    {E_USER.ROLE.value} AS role
                FROM {E_USER.TABLE.value}
                WHERE {E_USER.ID.value} = %s
                """,
                (uid,),
                dictionary=True,
            )
            if not current:
                return self._err("Usuario no encontrado.")

            sets: List[str] = []
            values: List[Any] = []

            if "username" in campos:
                new_user = self._sanitize_username(str(campos.get("username") or ""))
                if not new_user:
                    return self._err("El nombre de usuario no puede estar vacío.")
                if new_user != str(current.get("username")) and self.get_by_username(new_user):
                    return self._err(f"El usuario '{new_user}' ya existe.")
                sets.append(f"{E_USER.USERNAME.value} = %s")
                values.append(new_user)

            if "role" in campos:
                new_role = self._sanitize_role(str(campos.get("role") or ""))
                if str(current.get("role")) == "root" and new_role != "root" and self.count_roots() == 1:
                    return self._err("Debe existir al menos un usuario root.")
                sets.append(f"{E_USER.ROLE.value} = %s")
                values.append(new_role)

            if "password" in campos:
                raw_pw = str(campos.get("password") or "").strip()
                if raw_pw:
                    sets.append(f"{E_USER.PASSWORD.value} = %s")
                    values.append(self.hash_password(raw_pw))

            if not sets:
                fresh = self.post_update_refresh(uid)
                return self._ok("Sin cambios para aplicar.", fresh, 0)

            query = f"""
                UPDATE {E_USER.TABLE.value}
                SET {", ".join(sets)}
                WHERE {E_USER.ID.value} = %s
            """
            values.append(uid)
            ra = self._exec(query, tuple(values))

            fresh = self.post_update_refresh(uid)
            return self._ok("Usuario actualizado.", fresh, ra)
        except Exception as ex:
            return self._err(str(ex))

    def post_update_refresh(self, user_id: int) -> Optional[Dict[str, Any]]:
        try:
            uid = self._ensure_int_id(user_id)
            row = self.db.get_data(
                f"""
                SELECT
                    {E_USER.ID.value} AS id,
                    {E_USER.USERNAME.value} AS username,
                    {E_USER.ROLE.value} AS role,
                    {E_USER.FECHA_CREACION.value} AS fecha_creacion,
                    {E_USER.FECHA_MODIFICACION.value} AS fecha_modificacion
                FROM {E_USER.TABLE.value}
                WHERE {E_USER.ID.value} = %s
                """,
                (uid,),
                dictionary=True,
            )
            return row
        except Exception:
            return None

    # -------------------------
    # NUEVO: Verificar contraseña por ID (para root edit)
    # -------------------------
    def verify_user_password(self, user_id: int, password: str) -> Dict[str, Any]:
        """
        Verifica si 'password' coincide con el hash guardado del usuario 'user_id'.
        """
        try:
            uid = self._ensure_int_id(user_id)
            row = self.db.get_data(
                f"SELECT {E_USER.PASSWORD.value} AS password_hash FROM {E_USER.TABLE.value} WHERE {E_USER.ID.value} = %s",
                (uid,),
                dictionary=True,
            )
            if not row:
                return self._err("Usuario no encontrado.")

            stored = str(row.get("password_hash") or "")
            if not stored:
                return self._err("El usuario no tiene password_hash guardado.")

            if self.verify_password(password, stored):
                return self._ok("ok", True, 0)

            return self._err("Contraseña incorrecta.", False)

        except Exception as ex:
            return self._err(f"Error verificando contraseña: {ex}")

    # Compat histórica (NO revela nada)
    def get_password(self, user_id: int) -> Dict[str, Any]:
        return self._ok("ok", "●●●●●●●●", 0)
