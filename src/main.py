# main.py
import flet as ft
from app.views.window_main_view import window_main

if __name__ == "__main__":
    ft.app(target=window_main, assets_dir="assets")
