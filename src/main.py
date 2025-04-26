import flet as ft
from app.views.window_main_view import window_main




def iniciar_aplicacion(): # Método central que crea las tablas faltantes.

    # Ya puedes lanzar tu app sin preocupaciones, dado que el esquema está inicializado.
    ft.app(target=window_main, assets_dir="assets")

if __name__ == "__main__":
    iniciar_aplicacion()
