# helpers/pagos/pagos_scroll_helper.py
from __future__ import annotations

from typing import Optional, Callable, List
import flet as ft


class PagosScrollHelper:
    """
    Helper de layout con scroll para la vista de Pagos.

    Objetivo: scroll lo más "smooth" posible en Flet.

    Cambios clave para suavidad:
    - Un solo scroll vertical real: ListView (mejor rendimiento que Column con scroll).
    - Un solo scroll horizontal real: Row scroller por contenido ancho (sin duplicar scroll horizontal global).
    - Resize con debounce: evita "tirones" por page.update() en ráfaga.
    - Actualizaciones mínimas: se actualizan contenedores, luego 1 page.update() máximo.

    Mantiene:
    - Modo datatable o body_override.
    - Forzado de ancho mínimo para overflow horizontal.
    - Encadenado seguro de page.on_resized sin pisar otros handlers.
    """

    def __init__(self):
        self._resize_registered: bool = False
        self._required_min_width: int = 1780
        self._get_window_width: Callable[[], int] = lambda: 1200

        self._wide_containers: List[ft.Container] = []
        self._prev_on_resized: Optional[Callable] = None

        self._extra_margin_px: int = 80

        # Debounce para resize (suaviza mucho)
        self._resize_debounce_ms: int = 120
        self._resize_scheduled: bool = False

        # refs opcionales para scroll programático
        self._vlist: Optional[ft.ListView] = None
        self._hrow: Optional[ft.Row] = None  # el scroller horizontal principal (si quieres animar luego)

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

        # 1) Body core (uno de dos modos)
        if body_override is not None:
            body_core = self._wrap_horizontally(body_override, center=center)
        elif datatable is not None:
            # DataTable mejor NO expand aquí, para que el wrapper controle overflow
            datatable.expand = False
            body_core = self._wrap_horizontally(datatable, center=center)
        else:
            body_core = self._wrap_horizontally(ft.Container(ft.Text("-"), padding=10), center=center)

        # 2) Vertical scroller "smooth": ListView
        #    - tight=True evita espacios raros
        #    - spacing pequeño
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
            auto_scroll=False,  # True solo si necesitas que se vaya al final (normalmente no)
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
    # Scroll programático opcional (si lo usas)
    # -----------------------
    def scroll_to_top(self, *, duration_ms: int = 220) -> None:
        """Scroll vertical suave al inicio (si la versión de Flet lo soporta)."""
        lv = self._vlist
        if lv is None:
            return
        try:
            # Algunas versiones soportan scroll_to con duration
            lv.scroll_to(offset=0, duration=duration_ms)
        except Exception:
            try:
                lv.scroll_to(offset=0)
            except Exception:
                pass

    def scroll_to_left(self, *, duration_ms: int = 220) -> None:
        """Scroll horizontal suave a la izquierda (si lo usas)."""
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
        Envuelve el control en un contenedor ancho (forced width) y lo mete en un Row con scroll horizontal.
        Importante: NO anidar otro scroll horizontal encima (eso hace "tosco").
        """
        forced_min_width = self._compute_forced_width()

        wide = ft.Container(
            content=control,
            width=forced_min_width,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )
        self._wide_containers.append(wide)

        # Row con scroll horizontal único
        self._hrow = ft.Row(
            controls=[wide],
            scroll=ft.ScrollMode.ALWAYS,
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER if center else ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        # Contenedor que ocupa el ancho disponible; el "wide" fuerza overflow
        return ft.Container(
            content=self._hrow,
            expand=False,  # el ListView ya es el que expande; aquí solo damos un bloque estable
        )

    def _compute_forced_width(self) -> int:
        ww = self._get_window_width()
        return max(self._required_min_width, ww + self._extra_margin_px)

    # -----------------------
    # Resize: debounce + encadenado seguro
    # -----------------------
    def _register_resize_handler(self, page: ft.Page) -> None:
        if self._resize_registered:
            return
        self._resize_registered = True

        self._prev_on_resized = getattr(page, "on_resized", None)

        def _apply_resize():
            try:
                new_width = self._compute_forced_width()

                updated_any = False
                for c in list(self._wide_containers):
                    if c is not None and getattr(c, "page", None) is not None:
                        if getattr(c, "width", None) != new_width:
                            c.width = new_width
                            updated_any = True

                if updated_any and page:
                    page.update()

            except Exception as ex:
                print(f"⚠️ PagosScrollHelper._apply_resize: {ex}")
            finally:
                self._resize_scheduled = False

        def _on_resized(e):
            # debounce: evita 20 updates seguidos al redimensionar
            try:
                if not self._resize_scheduled and getattr(page, "run_task", None):
                    self._resize_scheduled = True

                    async def _debounced():
                        try:
                            # dormir un poco (ms) sin bloquear UI
                            await ft.sleep(self._resize_debounce_ms / 1000)
                        except Exception:
                            pass
                        _apply_resize()

                    page.run_task(_debounced())
                else:
                    # fallback sin run_task: aplica directo (igual está protegido)
                    _apply_resize()

            except Exception as ex:
                print(f"⚠️ PagosScrollHelper._on_resized: {ex}")
            finally:
                # Encadenar handler previo si existía
                try:
                    if callable(self._prev_on_resized):
                        self._prev_on_resized(e)
                except Exception as chain_ex:
                    print(f"⚠️ PagosScrollHelper._on_resized (prev handler): {chain_ex}")

        page.on_resized = _on_resized
