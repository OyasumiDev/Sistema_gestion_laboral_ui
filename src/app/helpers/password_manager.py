import hashlib

class PasswordManager:
    @staticmethod
    def encrypt_password(password: str) -> str:
        """
        Genera el hash SHA-256 en formato hexadecimal (minúsculas).
        Maneja errores si la entrada no es una cadena válida.
        """
        if not isinstance(password, str):
            raise TypeError("La contraseña debe ser una cadena de texto.")

        try:
            return hashlib.sha256(password.encode("utf-8")).hexdigest()
        except Exception as e:
            raise ValueError(f"No se pudo encriptar la contraseña: {e}")