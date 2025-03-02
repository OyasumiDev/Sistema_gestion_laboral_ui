import hashlib

class PasswordManager:
    @staticmethod
    def encrypt_password(password: str) -> str:
        """
        Genera el hash SHA-256 en formato hexadecimal (en minúsculas)
        para que coincida con el valor almacenado en la base de datos.
        """
        return hashlib.sha256(password.encode("utf-8")).hexdigest()
    


























