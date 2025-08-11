# helpers/pagos/scroll_pagos_helper.py
from __future__ import annotations
from typing import Optional, List, Callable
import flet as ft


class ScrollPagosHelper:
    """
    Scaffold de scroll persistente para Pagos:
    - Vertical SIEMPRE visible (Column con scroll=ALWAYS).
    - Horizontal SIEMPRE visible (viewport con alto fijo) usando ListView horizontal
      o Row(scroll=ALWAYS) como fallback.
    - Evita `expand` en el hijo (DataTable) para permitir overflow estable.
    - Puede auto-ajustar el ancho mínimo con el tamaño de la ventana y disparar
      un callback para rearmar el layout.
    """

    def __init__(
        self,
        *,
        min_table_height: int = 480,   # alto fijo del viewport de la tabla (barra H queda visible)
        min_table_width: int = 1600,   # ancho mínimo del contenido para provocar overflow
        spacing: int = 12,
        padding: int = 20,
        force_hbar: bool = True,       # ghost pixel para asegurar overflow cuando coincide el ancho
        use_listview_h: bool = True,   # True: ListView horizontal; False: Row(scroll=ALWAYS)
    ):
        self.min_table_height = min_table_height
        self.min_table_width = min_table_width
        self.spacing = spacing
        self.padding = padding
        self.force_hbar = force_hbar
        self.use_listview_h = use_listview_h

        # estado para re-armado en resize
        self._page: Optional[ft.Page] = None
        self._rebuild_cb: Optional[Callable[[], None]] = None

    # ----- Integración con Page (opcional) -----
    def bind_to_page(self, page: ft.Page, on_resize_rebuild: Optional[Callable[[], None]] = None, extra_px: int = 1):
        """
        Llama esto en tu _build() del contenedor para:
        - Guardar la referencia a la page
        - Auto-ajustar min_table_width con el ancho de ventana
        - Re-armar el layout en cada resize (si pasas callback)
        """
        self._page = page
        self._rebuild_cb = on_resize_rebuild
        self.auto_fit_width(page, extra_px=extra_px)

        # Evita registrar múltiples veces:
        if not getattr(page, "_scroll_pagos_helper_bound", False):
            def _on_resize(e):
                try:
                    self.auto_fit_width(page, extra_px=extra_px)
                    if self._rebuild_cb:
                        self._rebuild_cb()
                except Exception:
                    pass
            page.on_resize = _on_resize
            setattr(page, "_scroll_pagos_helper_bound", True)

    # Ajusta el ancho mínimo con el ancho de ventana
    def auto_fit_width(self, page: ft.Page, extra_px: int = 1):
        try:
            w = int(page.window_width or page.width or 1200)
            # +1px garantiza overflow incluso si iguala el viewport
            self.min_table_width = max(self.min_table_width, w + extra_px)
        except Exception:
            pass

    def build_header_bar(self, controls: List[ft.Control]) -> ft.Row:
        return ft.Row(controls=controls, spacing=10, alignment=ft.MainAxisAlignment.START)

    def build_footer_bar(self, control: ft.Control) -> ft.Container:
        return ft.Container(content=control, padding=10, alignment=ft.alignment.center)

    # ----- Viewport horizontal persistente -----
    def _make_wide_content(self, body: ft.Control) -> List[ft.Control]:
        # ¡No usar expand en body! (la DataTable ya te llega sin expand)
        wide = ft.Container(content=body, width=self.min_table_width)
        ghost = ft.Container(width=1, height=1, opacity=0) if self.force_hbar else None
        return [wide] + ([ghost] if ghost else [])

    def wrap_horizontal(self, body: ft.Control) -> ft.Container:
        """
        Zona con scrollbar H persistente:
        - Alto fijo -> barra H siempre visible y fija.
        - Contenido con ancho mínimo grande -> overflow garantizado.
        - Estrategia primaria: ListView horizontal (scroll suave y continuo).
        - Fallback: Row(scroll=ALWAYS) si prefieres algo más simple.
        """
        controls = self._make_wide_content(body)

        if self.use_listview_h:
            viewport: ft.Control = ft.ListView(
                horizontal=True,
                expand=True,                       # viewport ocupa todo el ancho disponible
                height=self.min_table_height,      # alto fijo -> barra H fija
                controls=controls,
                spacing=0,
                padding=0,
                auto_scroll=False,
            )
        else:
            viewport = ft.Row(
                controls=controls,
                scroll=ft.ScrollMode.ALWAYS,       # barra horizontal visible
                expand=True,
            )

        # Contenedor con alto fijo para mantener la barra H visible y no se vaya “abajo”
        return ft.Container(
            content=viewport,
            height=self.min_table_height,
            expand=False,
        )

    # ----- Scaffold principal (V y H persistentes) -----
    def build_scaffold(
        self,
        *,
        header: Optional[ft.Control],
        body: ft.Control,
        footer: Optional[ft.Control] = None,
    ) -> ft.Container:
        # Si accidentalmente llega con expand=True, lo anulamos para no romper overflow
        try:
            if getattr(body, "expand", False):
                body.expand = False
        except Exception:
            pass

        horiz = self.wrap_horizontal(body)

        col_controls: List[ft.Control] = []
        if header:
            col_controls.append(header)
        col_controls.append(ft.Divider(height=1))
        col_controls.append(horiz)                   # alto fijo -> barra H siempre visible
        if footer:
            col_controls.append(footer)

        return ft.Container(
            expand=True,
            padding=self.padding,
            content=ft.Column(
                controls=col_controls,
                expand=True,
                spacing=self.spacing,
                scroll=ft.ScrollMode.ALWAYS,        # barra vertical persistente
            ),
        )
