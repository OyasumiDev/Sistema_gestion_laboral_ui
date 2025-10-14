# app/views/containers/navbar_container.py

import flet as ft
from app.core.app_state import AppState
from app.views.containers.theme_controller import ThemeController
from app.views.containers.layout_controller import LayoutController
from app.views.containers.user_icon_area import UserIconArea
from app.views.containers.menu_buttons_area import MenuButtonsArea
from app.views.containers.control_buttons_area import ControlButtonsArea


class NavBarContainer(ft.Container):
    """
    Barra lateral con manejo SEGURO de page:
    - No se asigna self.page manualmente en __init__ (Flet lo inyecta al montar).
    - _get_page() obtiene page de forma segura (desde el control o AppState()).
    - _safe_update(), _safe_go() y _safe_close_window() evitan AttributeError.
    """

    def __init__(self, is_root: bool = False, modo_settings: bool = False):
        super().__init__(padding=10)

        self.is_root = is_root
        self.modo_settings = modo_settings

        self.theme_ctrl = ThemeController()
        self.layout_ctrl = LayoutController()

        self._build()

    # -------------------------
    # Helpers de seguridad UI
    # -------------------------
    def _get_page(self) -> ft.Page | None:
        """Obtiene la Page inyectada por Flet o cae a AppState().page."""
        p = getattr(self, "page", None)
        if p is None:
            # Fallback en caso de que aún no esté montado el control
            try:
                p = AppState().page
            except Exception:
                p = None
        return p

    def _safe_update(self):
        """Actualiza el control/página sin explotar si page aún es None."""
        try:
            # Preferimos actualizar este control si ya está montado
            self.update()
            return
        except Exception:
            pass

        p = self._get_page()
        if p is not None:
            try:
                p.update()
            except Exception:
                pass

    def _safe_go(self, route: str):
        """Navega de forma segura y actualiza la UI."""
        p = self._get_page()
        if p is not None:
            try:
                p.go(route)
            except Exception:
                # Si por alguna razón la navegación falla, al menos intentamos refrescar
                pass
            finally:
                try:
                    p.update()
                except Exception:
                    pass

    def _safe_close_window(self, _=None):
        """Cierra la ventana sin lanzar errores si no está disponible."""
        p = self._get_page()
        if p is not None and getattr(p, "window", None) is not None:
            try:
                p.window.close()
            except Exception:
                pass

    # -------------------------
    # Construcción de la vista
    # -------------------------
    def _build(self):
        expanded = self.layout_ctrl.expandido
        colors = self.theme_ctrl.get_colors()

        self.width = 250 if expanded else 80
        self.bgcolor = colors["BG_COLOR"]

        avatar_area = UserIconArea(
            is_root=self.is_root,
            accent=colors["AVATAR_ACCENT"],  # color dinámico
            nav_width=self.width,
            height=64,
        )

        if self.modo_settings:
            menu_area = self._build_settings_menu(expanded, colors)
        else:
            menu_area = MenuButtonsArea(
                is_root=self.is_root,
                expanded=expanded,
                fg=colors["FG_COLOR"],
                btn_bg=colors["BTN_BG"],
            )

        control_area = ControlButtonsArea(
            expanded=expanded,
            dark=self.theme_ctrl.tema_oscuro,
            on_toggle_nav=self._on_toggle_nav,
            on_toggle_theme=self._on_toggle_theme,
            on_settings=self._on_settings,       # callback real
            on_exit=self._safe_close_window,     # ✅ ahora es seguro
            bg=colors["BTN_BG"],
            mostrar_settings=True,
            mostrar_theme=True,
        )

        self.content = ft.Column(
            controls=[
                avatar_area,
                ft.Divider(thickness=1, color=colors["DIVIDER_COLOR"]),
                menu_area,
                ft.Container(expand=True),
                control_area,
            ],
            spacing=16,
        )

    def _build_settings_menu(self, expanded: bool, colors: dict) -> ft.Column:
        """Menú especial para Settings (usa FG_COLOR igual que Home)."""
        btn_return = ft.GestureDetector(
            on_tap=self._on_return,
            content=ft.Container(
                bgcolor=colors["BTN_BG"],
                padding=6,
                border_radius=6,
                content=ft.Row(
                    controls=[
                        ft.Image(src="assets/buttons/return-button.png", width=24, height=24),
                        ft.Text("Return", size=12, visible=expanded, color=colors["FG_COLOR"]),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
        )

        btn_database = ft.GestureDetector(
            on_tap=self._on_database,
            content=ft.Container(
                bgcolor=colors["BTN_BG"],
                padding=6,
                border_radius=6,
                content=ft.Row(
                    controls=[
                        ft.Image(src="assets/buttons/database-button.png", width=24, height=24),
                        ft.Text("Database", size=12, visible=expanded, color=colors["FG_COLOR"]),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
        )

        return ft.Column(controls=[btn_return, btn_database], spacing=10)

    # -------------------------
    # Callbacks
    # -------------------------
    def _on_toggle_nav(self, _):
        self.layout_ctrl.toggle()
        self._build()
        self._safe_update()

    def _on_toggle_theme(self, _):
        self.theme_ctrl.toggle()
        self._build()
        self._safe_update()

    def _on_settings(self, _):
        # Navega a /settings de forma segura
        self._safe_go("/settings")

    def _on_return(self, _):
        self._safe_go("/home")

    def _on_database(self, _):
        self._safe_go("/settings/db")
