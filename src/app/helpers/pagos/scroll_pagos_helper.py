# helpers/pagos/pagos_scroll_helper.py
from __future__ import annotations

from typing import Optional, Callable
import flet as ft


class PagosScrollHelper:
    """
    Helper de scroll para Pagos:
      - Garantiza barra vertical SIEMPRE visible (ScrollMode.ALWAYS).
      - Garantiza overflow y barra horizontal SIEMPRE visibles alrededor de la DataTable.
      - Expande el viewport horizontal hasta el fondo de la pantalla (sin cortar).
      - Handler de resize SEGURO (sin actualizar controles no montados).
    """

    def __init__(self):
        self._resize_registered: bool = False
        self._wide_table: Optional[ft.Container] = None
        self._required_min_width: int = 1780  # suma aproximada de columnas + margen
        self._get_window_width: Callable[[], int] = lambda: 1200

    # -----------------------
    # API pública principal
    # -----------------------
    def build_scaffold(
        self,
        *,
        page: ft.Page,
        datatable: ft.DataTable,
        header: ft.Control,
        footer: ft.Control,
        required_min_width: int = 1780,
    ) -> ft.Container:
        """
        Devuelve un contenedor listo para usar como self.content en tu Container.
        Incluye:
          - Column con scroll vertical ALWAYS
          - Viewport horizontal con Row(scroll=ALWAYS) y ancho forzado
          - Footer y header fijos por encima y debajo del área de la tabla
        """
        self._required_min_width = max(1400, int(required_min_width))
        self._get_window_width = lambda: int(page.window_width or page.width or 1200)

        # === 1) Forzar ancho mínimo para overflow horizontal ===
        forced_min_width = self._compute_forced_width()

        # === 2) Configuración de DataTable para permitir overflow H ===
        datatable.expand = False  # << clave: la tabla no expande, el scroll lo hace el contenedor

        # === 3) Contenedor ancho que produce el overflow horizontal ===
        self._wide_table = ft.Container(
            content=datatable,
            width=forced_min_width,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        # === 4) Viewport horizontal con barra SIEMPRE visible ===
        horiz_scroller = ft.Row(
            controls=[self._wide_table],
            scroll=ft.ScrollMode.ALWAYS,
            expand=True,  # ocupa todo el ancho disponible
        )

        # === 5) Área que se extiende hasta abajo (para que la barra vertical recorra todo) ===
        horizontal_area = ft.Container(
            content=horiz_scroller,
            expand=True,  # << crece para ocupar altura sobrante
        )

        # === 6) Columna con scroll vertical persistente ===
        col = ft.Column(
            controls=[
                header,
                ft.Divider(height=1),
                horizontal_area,
                footer,
            ],
            expand=True,
            spacing=12,
            scroll=ft.ScrollMode.ALWAYS,  # << barra vertical siempre visible
        )

        # === 7) Contenedor final (self.content en tu PagosContainer) ===
        content = ft.Container(
            expand=True,
            padding=20,
            content=col,
        )

        # === 8) Registrar handler de resize una sola vez (seguro) ===
        self._register_resize_handler(page)

        return content

    def scroll_to_left(self) -> None:
        """API opcional para re-ubicar al inicio horizontal (si agregas controles con animate_offset)."""
        # Reservado para futuras mejoras si necesitas animación lateral.
        pass

    # -----------------------
    # Internos
    # -----------------------
    def _compute_forced_width(self) -> int:
        ww = self._get_window_width()
        # Un pequeño margen adicional para asegurar overflow
        return max(self._required_min_width, ww + 80)

    def _register_resize_handler(self, page: ft.Page) -> None:
        if self._resize_registered:
            return
        self._resize_registered = True

        def _on_resize(e):
            try:
                new_width = self._compute_forced_width()
                # Solo actualizar si el contenedor ya está montado en la page
                if self._wide_table is not None and getattr(self._wide_table, "page", None) is not None:
                    self._wide_table.width = new_width
                # Un único page.update() es suficiente
                if page:
                    page.update()
            except Exception as ex:
                # Silencioso pero informativo en consola
                print(f"⚠️ PagosScrollHelper._on_resize: {ex}")

        page.on_resized = _on_resize
