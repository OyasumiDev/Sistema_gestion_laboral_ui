import flet as ft
import hashlib
import hmac
import base64
import re
from datetime import datetime

from app.models.user_model import UserModel
from app.core.enums.e_user_model import E_USER
from app.core.app_state import AppState


class LoginContainer(ft.Container):
    DEBUG_AUTH = True  # ponlo False cuando ya quede

    def __init__(self):
        super().__init__(
            width=450,
            padding=20,
            border_radius=10,
            bgcolor=ft.colors.BLUE_ACCENT_100,
            alignment=ft.alignment.center,
        )

        self.user_model = UserModel()

        self.user_field = ft.TextField(label="Usuario", on_submit=self.on_login)
        self.password_field = ft.TextField(
            label="Contraseña",
            password=True,
            can_reveal_password=True,
            on_submit=self.on_login
        )

        self.login_message = ft.Text(color=ft.colors.BLACK)

        self.content = ft.Column(
            [
                ft.Image(src="logos/loggin.png", width=300),
                self.user_field,
                self.password_field,
                ft.CupertinoButton(
                    "Iniciar sesión",
                    on_click=self.on_login,
                    bgcolor=ft.colors.BLUE_ACCENT_100,
                    color=ft.colors.WHITE
                ),
                self.login_message
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )

    # ---------------------------------------------------------------------
    # Logging helpers
    # ---------------------------------------------------------------------
    def _log(self, msg: str) -> None:
        if not self.DEBUG_AUTH:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[AUTH {ts}] {msg}")

    @staticmethod
    def _mask(s: str, keep: int = 6) -> str:
        s = (s or "").strip()
        if not s:
            return "<empty>"
        if len(s) <= keep:
            return "*" * len(s)
        return s[:keep] + "..." + f"({len(s)} chars)"

    # ---------------------------------------------------------------------
    # Extra verifiers (opcional)
    # ---------------------------------------------------------------------
    @staticmethod
    def _is_bcrypt_hash(stored: str) -> bool:
        return bool(re.match(r"^\$2[aby]\$", stored or ""))

    def _verify_bcrypt(self, plain: str, stored: str) -> bool:
        self._log("Ruta: bcrypt")
        try:
            import bcrypt  # type: ignore
        except Exception:
            self._log("bcrypt NO instalado -> FAIL bcrypt")
            return False

        try:
            ok = bcrypt.checkpw(plain.encode("utf-8"), stored.encode("utf-8"))
            self._log(f"bcrypt result: {ok}")
            return ok
        except Exception as ex:
            self._log(f"bcrypt EXCEPTION: {ex}")
            return False

    @staticmethod
    def _verify_sha256_salt(plain: str, stored: str) -> bool:
        # sha256$SALT$HASH  (HASH base64 o hex)
        try:
            parts = (stored or "").split("$")
            if len(parts) != 3:
                return False
            _, salt, digest_str = parts
            raw = hashlib.sha256((salt + plain).encode("utf-8")).digest()

            try:
                expected = base64.b64decode(digest_str.encode("utf-8"), validate=True)
                if len(expected) != len(raw):
                    raise ValueError("base64 mismatch")
            except Exception:
                expected = bytes.fromhex(digest_str)

            return hmac.compare_digest(raw, expected)
        except Exception:
            return False

    # ---------------------------------------------------------------------
    # Password verification (delegando a UserModel cuando es pbkdf2)
    # ---------------------------------------------------------------------
    def _verify_password(self, plain: str, stored: str) -> bool:
        stored = (stored or "").strip()
        if not stored:
            self._log("stored_pwd vacío -> FAIL")
            return False

        self._log(f"stored_pwd preview: {self._mask(stored)}")

        # ✅ 1) PBKDF2 (USAR EXACTAMENTE TU UserModel)
        if stored.startswith(self.user_model.PBKDF2_PREFIX + "$"):
            self._log("Detectado: pbkdf2_sha256$ -> usando UserModel.verify_password()")
            try:
                ok = self.user_model.verify_password(plain, stored)
                self._log(f"UserModel.verify_password result: {ok}")
                return bool(ok)
            except Exception as ex:
                self._log(f"UserModel.verify_password EXCEPTION: {ex}")
                return False

        # ✅ 2) bcrypt (opcional)
        if self._is_bcrypt_hash(stored):
            self._log("Detectado: bcrypt ($2*)")
            return self._verify_bcrypt(plain, stored)

        # ✅ 3) sha256 salteado (opcional)
        if stored.startswith("sha256$"):
            self._log("Detectado: sha256$ -> verify_sha256_salt")
            ok = self._verify_sha256_salt(plain, stored)
            self._log(f"sha256 result: {ok}")
            return ok

        # ✅ 4) fallback texto plano (compat usuarios viejos)
        self._log("Detectado: texto plano (fallback)")
        ok = hmac.compare_digest(plain, stored)
        self._log(f"plaintext result: {ok}")
        return ok

    # ---------------------------------------------------------------------
    # Login
    # ---------------------------------------------------------------------
    def on_login(self, e: ft.ControlEvent):
        page: ft.Page = AppState().page

        user_value = (self.user_field.value or "").strip()
        pass_value = (self.password_field.value or "").strip()

        self._log("---- LOGIN ATTEMPT ----")
        self._log(f"user_value: '{user_value}' (len={len(user_value)})")
        self._log(f"pass_value len: {len(pass_value)}")

        if not user_value and not pass_value:
            self.login_message.value = "Por favor, ingrese usuario y contraseña."
            page.update()
            self._log("FAIL: faltan usuario y contraseña")
            return
        elif not user_value:
            self.login_message.value = "Por favor, ingrese el nombre de usuario."
            page.update()
            self._log("FAIL: falta usuario")
            return
        elif not pass_value:
            self.login_message.value = "Por favor, ingrese la contraseña."
            page.update()
            self._log("FAIL: falta contraseña")
            return

        try:
            self._log("Consultando DB: get_by_username() ...")
            user_data = self.user_model.get_by_username(user_value)

            if not user_data:
                self._log("Usuario no encontrado -> FAIL")
                self.login_message.value = "El usuario o la contraseña no son correctos."
                return

            uid = user_data.get(E_USER.ID.value, user_data.get("id", None))
            role = user_data.get(E_USER.ROLE.value, user_data.get("role", None))
            self._log(f"Usuario encontrado: id={uid} role={role}")

            stored_pwd = (user_data.get(E_USER.PASSWORD.value) or "").strip()
            self._log("Verificando contraseña...")

            if self._verify_password(pass_value, stored_pwd):
                self._log("LOGIN OK ✅")

                # Normaliza fechas para client_storage
                if E_USER.FECHA_CREACION.value in user_data:
                    user_data[E_USER.FECHA_CREACION.value] = str(user_data[E_USER.FECHA_CREACION.value])
                if E_USER.FECHA_MODIFICACION.value in user_data:
                    user_data[E_USER.FECHA_MODIFICACION.value] = str(user_data[E_USER.FECHA_MODIFICACION.value])

                page.client_storage.set("app.user", user_data)
                page.go("/home")
            else:
                self._log("LOGIN FAIL ❌ (password mismatch)")
                self.login_message.value = "El usuario o la contraseña no son correctos."

        except Exception as ex:
            self._log(f"EXCEPTION en login: {ex}")
            self.login_message.value = f"Error inesperado: {ex}"
        finally:
            page.update()
            self._log("---- END LOGIN ----")
