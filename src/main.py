import flet as ft
from app.views.window_main_view import window_main
from app.core.interfaces.database_mysql import DatabaseMysql

def iniciar_aplicacion():
    # Inicializamos la base de datos y nos aseguramos que el esquema esté en su lugar.
    db = DatabaseMysql()
    db.verificar_y_crear_tablas()  # Método central que crea las tablas faltantes.

    # Ya puedes lanzar tu app sin preocupaciones, dado que el esquema está inicializado.
    ft.app(target=window_main, assets_dir="assets")

if __name__ == "__main__":
    iniciar_aplicacion()
