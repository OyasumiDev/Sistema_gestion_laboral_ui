import flet as ft
from app.views.containers.navbar_container import NavBarContainer

class NavBarView(ft.Container):
    """Vista que expone el NavBarContainer como un control Flet"""
    def __init__(self, is_root: bool = False):
        super().__init__(content=NavBarContainer(is_root=is_root))
