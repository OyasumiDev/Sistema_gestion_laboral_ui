import flet as ft
from app.helpers.class_singleton import class_singleton

@class_singleton
class AppState:
    """
    Clase para manejar el estado global de la aplicación.
    """
    def __init__(self):
        self.page: ft.Page = None
        self.data = {}
        self.window_width: int = 0
        self.window_height: int = 0
        self.responsive_mode: str = "desktop"
        
    def set(self, key, value):
        """
        Establece un valor en el estado global.
        """
        self.data[key] = value

    def get(self, key, default=None):
        """
        Obtiene un valor del estado global.
        """
        return self.data.get(key, default)

    def set_page(self, page: ft.Page):
        """
        Establece la instancia de la página principal.
        """
        self.page = page

    def get_page(self) -> ft.Page:
        """
        Obtiene la instancia de la página principal.
        """
        return self.page

    def set_theme(self, dark_mode: bool):
        """
        Establece el tema de la aplicación y lo guarda en el almacenamiento del cliente.
        """
        self.set("dark_mode", dark_mode)
        if self.page:
            self.page.client_storage.set("dark_mode", dark_mode)

    def get_theme(self) -> bool:
        """
        Obtiene el tema actual de la aplicación.
        """
        return self.get("dark_mode", True)

    def load_theme_from_storage(self):
        """
        Carga el tema desde el almacenamiento del cliente.
        """
        if self.page:
            dark_mode = self.page.client_storage.get("dark_mode")
            if dark_mode is not None:
                self.set("dark_mode", dark_mode)

    def update_window_dimensions(self):
        """
        Actualiza las dimensiones actuales de la ventana y define el modo responsive.
        """
        if self.page:
            self.window_width = self.page.window_width
            self.window_height = self.page.window_height

            # Detectar tipo de vista
            if self.window_width < 768:
                self.responsive_mode = "mobile"
            elif self.window_width < 1200:
                self.responsive_mode = "tablet"
            else:
                self.responsive_mode = "desktop"

            print(f"📐 Resolución: {self.window_width}x{self.window_height} -> Modo: {self.responsive_mode}")
