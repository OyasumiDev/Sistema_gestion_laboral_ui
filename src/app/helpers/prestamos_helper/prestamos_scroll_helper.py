# app/helpers/prestamos_helper/prestamos_scroll_helper.py
import asyncio
from threading import Timer
from typing import Optional
import flet as ft


class PrestamosScrollHelper:
    """
    Scroll NO bloqueante y seguro:
    - No usa page.on_after_build ni time.sleep().
    - Reintenta sólo si la View está montada y la key existe.
    """

    @staticmethod
    def scroll_to_group_after_build(
        page: ft.Page,
        group_id: str,
        delay: float = 0.08,
        retries: int = 20,
    ) -> None:
        """
        Hace scroll a key=group_id cuando:
          1) La View está montada (page.views no vacío), y
          2) Existe un control con esa key.
        Reintenta hasta `retries` veces con espera `delay`.
        """
        async def _go():
            for _ in range(max(1, retries)):
                try:
                    # 1) Espera un poco para permitir render
                    await asyncio.sleep(max(0.0, delay))

                    # 2) La View debe estar montada
                    if not getattr(page, "views", None) or len(page.views) == 0:
                        continue

                    # 3) El control con esa key debe existir
                    ctrl = page.get_control(group_id)
                    if ctrl is None:
                        continue

                    # 4) Ahora sí: scroll
                    page.scroll_to(key=group_id, duration=300)
                    page.update()
                    return
                except Exception as ex:
                    # Si hay error (p. ej. la view aún no está), lo intentamos en el siguiente ciclo
                    print(f"[scroll_to_group_after_build] retry: {ex}")
                    continue

        try:
            page.run_task(_go)
        except Exception as ex:
            # Fallback sin asyncio (raro, pero por si acaso)
            print(f"[scroll_to_group_after_build] run_task fallback: {ex}")
            Timer(delay, lambda: PrestamosScrollHelper._fallback_scroll(page, group_id)).start()

    @staticmethod
    def _fallback_scroll(page: ft.Page, group_id: str):
        try:
            if getattr(page, "views", None) and len(page.views) > 0:
                if page.get_control(group_id) is not None:
                    page.scroll_to(key=group_id, duration=300)
                    page.update()
        except Exception as ex:
            print(f"[scroll fallback] {ex}")

    @staticmethod
    def scroll_after_table_update(page: ft.Page, group_id: str, delay: float = 0.08) -> None:
        PrestamosScrollHelper.scroll_to_group_after_build(page, group_id, delay=delay, retries=10)

    # --- Opcional: scroll a fin de ListView/Column (si los usas como contenedor scrolleable) ---

    def __init__(self, page: ft.Page, lista_ref: Optional[ft.Control] = None):
        self.page = page
        self.lista_ref = lista_ref

    def scroll_a_nueva_fila(self, delay: float = 0.08) -> None:
        async def _go():
            await asyncio.sleep(max(0.0, delay))
            try:
                if isinstance(self.lista_ref, ft.ListView):
                    idx = max(0, len(self.lista_ref.controls) - 1)
                    if idx >= 0:
                        self.lista_ref.scroll_to(index=idx, duration=200)
                        self.page.update()
                elif isinstance(self.lista_ref, ft.Column):
                    if self.lista_ref.controls:
                        last = self.lista_ref.controls[-1]
                        if isinstance(last, ft.Control) and last.key:
                            self.page.scroll_to(key=last.key, duration=300)
                            self.page.update()
            except Exception as ex:
                print(f"[scroll_a_nueva_fila] {ex}")

        try:
            self.page.run_task(_go)
        except Exception as ex:
            print(f"[scroll_a_nueva_fila] run_task fallback: {ex}")
            Timer(delay, lambda: self._fallback_list_scroll()).start()

    def _fallback_list_scroll(self):
        try:
            if isinstance(self.lista_ref, ft.ListView):
                idx = max(0, len(self.lista_ref.controls) - 1)
                if idx >= 0:
                    self.lista_ref.scroll_to(index=idx, duration=200)
                    self.page.update()
            elif isinstance(self.lista_ref, ft.Column) and self.lista_ref.controls:
                last = self.lista_ref.controls[-1]
                if isinstance(last, ft.Control) and last.key:
                    self.page.scroll_to(key=last.key, duration=300)
                    self.page.update()
        except Exception as ex:
            print(f"[fallback_list_scroll] {ex}")
