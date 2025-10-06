# helpers/pagos/pagos_scroll_helper.py
from __future__ import annotations

from typing import Optional, Callable, List
import flet as ft


class PagosScrollHelper:
    """
    Helper de layout con scroll para la vista de Pagos.

    - Soporta dos modos de cuerpo:
        1) datatable:     un ft.DataTable renderizado con overflow horizontal.
        2) body_override: cualquier Control (expansibles, columnas compuestas, etc.).
           En ambos casos se envuelve en un contenedor ancho para habilitar scroll horizontal.
    - Scroll vertical SIEMPRE visible en el área de trabajo.
    - Scroll horizontal SIEMPRE visible cuando el contenido supera el ancho del viewport.
    - Manejo de 'on_resized' con encadenado seguro para no pisar otros listeners.
    """

    def __init__(self):
        # Estado interno
        self._resize_registered: bool = False
        self._required_min_width: int = 1780
        self._get_window_width: Callable[[], int] = lambda: 1200

        # Puedes tener más de un contenedor "ancho" en la misma vista
        # (si el día de mañana envuelves más de una tabla/panel horizontal):
        self._wide_containers: List[ft.Container] = []

        # Encadenamiento de on_resized (para no pisar handlers existentes)
        self._prev_on_resized: Optional[Callable] = None

        # Margen adicional para forzar overflow horizontal de forma predecible
        self._extra_margin_px: int = 80

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
        """
        Devuelve un contenedor listo para usar como self.content en tu PagosContainer.

        Args:
            page:               ft.Page actual (para leer ancho y registrar on_resized).
            datatable:          Modo clásico: una DataTable a mostrar.
            header:             Control para cabecera.
            footer:             Control para pie.
            required_min_width: Ancho mínimo "útil" de la zona de trabajo (suma aproximada columnas).
            body_override:      Modo nuevo: control compuesto (expansibles/columnas) para ser el cuerpo.
            center:             Centra horizontalmente el contenido (true por defecto).
            padding:            Padding del contenedor raíz.

        Returns:
            ft.Container expandible con:
                - Header (opcional)
                - Body con scroll vertical (y horizontal si aplica)
                - Footer (opcional)
        """
        self._required_min_width = max(1200, int(required_min_width))
        self._get_window_width = lambda: int(page.window_width or page.width or 1200)

        # 1) Construir el cuerpo principal (uno de los dos modos)
        if body_override is not None:
            body_core = self._wrap_horizontally(body_override)
        elif datatable is not None:
            datatable.expand = False  # clave: que el overflow lo controle el wrapper
            body_core = self._wrap_horizontally(datatable)
        else:
            # Fallback vacío para evitar errores si se llama sin contenido
            body_core = self._wrap_horizontally(ft.Container(ft.Text("-"), padding=10))

        # 2) Vertical area (scroll ALWAYS). El core (horizontal) vive dentro.
        vertical_area = ft.Column(
            controls=[body_core],
            scroll=ft.ScrollMode.ALWAYS,  # barra vertical
            expand=True,
            spacing=10,
        )

        # 3) Montaje total (header / body / footer)
        col_controls: List[ft.Control] = []
        if header is not None:
            col_controls.append(header)
            col_controls.append(ft.Divider(height=1))
        col_controls.append(vertical_area)
        if footer is not None:
            col_controls.append(ft.Divider(height=1))
            col_controls.append(footer)

        content_column = ft.Column(
            controls=col_controls,
            expand=True,
            spacing=10,
        )

        # 4) Centrado y scroll horizontal global (por si el contenido excede)
        #    - El Row externo agrega scroll horizontal a TODO el layout si hiciera falta.
        centered = ft.Row(
            controls=[content_column] if not center else [
                ft.Container(
                    content=content_column,
                    width=self._compute_forced_width(),  # asegura ancho minimo útil
                )
            ],
            alignment=ft.MainAxisAlignment.CENTER if center else ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
            scroll=ft.ScrollMode.ALWAYS,  # scroll horizontal global como red
        )

        # 5) Contenedor raíz
        root = ft.Container(
            content=centered,
            expand=True,
            padding=padding,
            alignment=ft.alignment.top_center,
        )

        # 6) Registrar handler de resize una sola vez (encadenado)
        self._register_resize_handler(page)

        return root

    def scroll_to_left(self) -> None:
        """Punto de extensión si quisieras animar el offset horizontal en el futuro."""
        # No implementado; se puede agregar con animate_offset y refs a Rows/Containers.
        pass

    # -----------------------
    # Internos
    # -----------------------
    def _wrap_horizontally(self, control: ft.Control) -> ft.Container:
        """
        Envuélve el control en un contenedor ancho para forzar overflow horizontal,
        luego lo coloca dentro de un Row con scroll horizontal SIEMPRE.
        """
        forced_min_width = self._compute_forced_width()

        wide = ft.Container(
            content=control,
            width=forced_min_width,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )
        # Mantener referencia para actualizar en on_resized
        self._wide_containers.append(wide)

        horiz_scroller = ft.Row(
            controls=[wide],
            scroll=ft.ScrollMode.ALWAYS,  # barra horizontal
            expand=True,
        )

        # Contenedor que se estira a la altura disponible (aporta a scroll vertical del padre)
        return ft.Container(
            content=horiz_scroller,
            expand=True,
        )

    def _compute_forced_width(self) -> int:
        ww = self._get_window_width()
        # margen extra para asegurar que haya overflow horizontal cuando corresponde
        return max(self._required_min_width, ww + self._extra_margin_px)

    def _register_resize_handler(self, page: ft.Page) -> None:
        if self._resize_registered:
            return
        self._resize_registered = True

        # Guardar handler previo (si existe) para encadenarlo
        self._prev_on_resized = getattr(page, "on_resized", None)

        def _on_resized(e):
            try:
                new_width = self._compute_forced_width()

                # Actualizar todos los contenedores anchos montados
                updated = False
                for c in list(self._wide_containers):
                    if c is not None and getattr(c, "page", None) is not None:
                        c.width = new_width
                        updated = True

                if updated and page:
                    page.update()

            except Exception as ex:
                print(f"⚠️ PagosScrollHelper._on_resized: {ex}")
            finally:
                # Encadenar handler previo si existía
                try:
                    if callable(self._prev_on_resized):
                        self._prev_on_resized(e)
                except Exception as chain_ex:
                    print(f"⚠️ PagosScrollHelper._on_resized (prev handler): {chain_ex}")

        # Registrar nuestro handler
        page.on_resized = _on_resized
