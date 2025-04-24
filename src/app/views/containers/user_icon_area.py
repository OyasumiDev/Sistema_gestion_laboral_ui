import flet as ft

class UserIconArea(ft.Container):
    def __init__(
        self,
        is_root: bool,
        accent: str,      # color de fondo
        nav_width: int,   # ancho actual del nav
        height: int = 64  # altura fija
    ):
        avatar_src = "assets/logos/root.png" if is_root else "assets/logos/user.png"
        super().__init__(
            width        = nav_width,   # se ensancha con el layout
            height       = height,      # altura constante
            bgcolor      = accent,      # fondo de acento
            border_radius= 8,           # esquinas suaves
            alignment    = ft.alignment.center,
            content      = ft.Image(
                src = avatar_src,
                width = 32,
                height = 32,
                fit = ft.ImageFit.COVER
            )
        )
