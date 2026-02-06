# helpers/pagos/pagos_scroll_helper.py
from __future__ import annotations

from typing import Optional, Callable, List
import flet as ft


class PagosScrollHelper:
    """
    Helper de layout con scroll para la vista de Pagos.

    Objetivo: scroll lo más "smooth" posible en Flet 0.24, sin romper taps/clicks.

    Claves:
    - Un solo scroll vertical real: ListView.
    - Un solo scroll horizontal real: Row scroller por contenido ancho.
    - Resize con debounce: evita tirones por updates en ráfaga.
    - Evita acumulación de contenedores viejos (no crecer _wide_containers sin límite).
    - run_task debe recibir una coroutine function (NO _debounced()).
    """

    def __init__(self):
        self._resize_registered: bool = False
        self._required_min_width: int = 1780
        self._get_window_width: Callable[[], int] = lambda: 1200

        # Solo mantenemos el "wide" actual para resize (evita fugas/rendimiento)
        self._wide_containers: List[ft.Container] = []
        self._wide_current: Optional[ft.Container] = None

        self._prev_on_resized: Optional[Callable] = None

        self._extra_margin_px: int = 0

        # Debounce para resize (suaviza mucho)
        self._resize_debounce_ms: int = 120
        self._resize_scheduled: bool = False

        # refs opcionales para scroll programático
        self._vlist: Optional[ft.ListView] = None
        self._hrow: Optional[ft.Row] = None  # scroller horizontal principal

    # -----------------------
    # API pública principal
    # -----------------------
    def build_scaffold(
        self,
        *,
        page: ft.Page,
        datatable: Optional[ft.DataTable] = None,
        header: Optional[ft.Control] = None,
        footer: Optional[ft.Control] = None,
        required_min_width: int = 1780,
        body_override: Optional[ft.Control] = None,
        center: bool = True,
        padding: int | ft.Padding = 12,
    ) -> ft.Container:
        self._required_min_width = max(1200, int(required_min_width))
        self._get_window_width = lambda: int(page.window_width or page.width or 1200)

        # Reset de referencias del "wide" previo (evita crecer lista con cada rebuild)
        self._wide_containers.clear()
        self._wide_current = None
        self._hrow = None
        self._vlist = None

        # 1) Body core (uno de dos modos)
        if body_override is not None:
            body_core = self._wrap_horizontally(body_override, center=center)
        elif datatable is not None:
            # DataTable mejor NO expand aquí, para que el wrapper controle overflow
            datatable.expand = False
            body_core = self._wrap_horizontally(datatable, center=center)
        else:
            body_core = self._wrap_horizontally(ft.Container(ft.Text("-"), padding=10), center=center)

        # 2) Vertical scroller: ListView (smooth)
        v_controls: List[ft.Control] = []
        if header is not None:
            v_controls.append(header)
            v_controls.append(ft.Divider(height=1))

        v_controls.append(body_core)

        if footer is not None:
            v_controls.append(ft.Divider(height=1))
            v_controls.append(footer)

        self._vlist = ft.ListView(
            controls=v_controls,
            expand=True,
            spacing=10,
            auto_scroll=False,
            padding=0,
        )

        root = ft.Container(
            content=self._vlist,
            expand=True,
            padding=padding,
            alignment=ft.alignment.top_center,
        )

        self._register_resize_handler(page)
        return root

    # -----------------------
    # Scroll programático opcional
    # -----------------------
    def scroll_to_top(self, *, duration_ms: int = 220) -> None:
        lv = self._vlist
        if lv is None:
            return
        try:
            lv.scroll_to(offset=0, duration=duration_ms)
        except Exception:
            try:
                lv.scroll_to(offset=0)
            except Exception:
                pass

    def scroll_to_left(self, *, duration_ms: int = 220) -> None:
        hr = self._hrow
        if hr is None:
            return
        try:
            hr.scroll_to(offset=0, duration=duration_ms)
        except Exception:
            try:
                hr.scroll_to(offset=0)
            except Exception:
                pass

    # -----------------------
    # Internos
    # -----------------------
    def _wrap_horizontally(self, control: ft.Control, *, center: bool) -> ft.Container:
        """
        Envuelve el control en un contenedor ancho y lo mete en un Row con scroll horizontal.
        Importante: evitar scrolls horizontales anidados.
        """
        forced_min_width = self._compute_forced_width()

        wide = ft.Container(
            content=control,
            width=forced_min_width,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        # Mantener solo el actual para resize (más estable)
        self._wide_current = wide
        self._wide_containers[:] = [wide]

        # ✅ FIX Flet 0.24:
        # scroll ALWAYS compite con taps (drag vs tap) cuando hay overflow forzado.
        # AUTO solo habilita scroll horizontal si realmente hay overflow.
        self._hrow = ft.Row(
            controls=[wide],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            wrap=False,
            alignment=ft.MainAxisAlignment.CENTER if center else ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        return ft.Container(
            content=self._hrow,
            expand=False,
        )

    def _compute_forced_width(self) -> int:
        ww = self._get_window_width()
        return max(self._required_min_width, ww + self._extra_margin_px)

    # -----------------------
    # Resize: debounce + encadenado seguro (Flet 0.24)
    # -----------------------
    def _register_resize_handler(self, page: ft.Page) -> None:
        if self._resize_registered:
            return
        self._resize_registered = True

        self._prev_on_resized = getattr(page, "on_resized", None)

        def _apply_resize() -> None:
            try:
                new_width = self._compute_forced_width()

                # Solo actualizamos el contenedor "wide" actual
                c = self._wide_current
                if c is not None and getattr(c, "page", None) is not None:
                    if getattr(c, "width", None) != new_width:
                        c.width = new_width
                        page.update()

            except Exception as ex:
                print(f"⚠️ PagosScrollHelper._apply_resize: {ex}")
            finally:
                self._resize_scheduled = False

        def _on_resized(e) -> None:
            try:
                if not self._resize_scheduled and callable(getattr(page, "run_task", None)):
                    self._resize_scheduled = True

                    async def _debounced():
                        try:
                            await ft.sleep(self._resize_debounce_ms / 1000)
                        except Exception:
                            pass
                        _apply_resize()

                    # ✅ Flet 0.24: pasar la coroutine function, NO llamar _debounced()
                    page.run_task(_debounced)
                else:
                    _apply_resize()

            except Exception as ex:
                print(f"⚠️ PagosScrollHelper._on_resized: {ex}")
            finally:
                try:
                    if callable(self._prev_on_resized):
                        self._prev_on_resized(e)
                except Exception as chain_ex:
                    print(f"⚠️ PagosScrollHelper._on_resized (prev handler): {chain_ex}")

        page.on_resized = _on_resized
