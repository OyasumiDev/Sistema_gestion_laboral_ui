import time
from threading import Timer
import flet as ft

class AsistenciasScrollHelper:
    @staticmethod
    def scroll_to_group_after_build(page: ft.Page, group_id: str, delay: float = 0.02):
        """
        Programa el scroll al grupo después del ciclo completo de construcción visual,
        usando on_after_build y un pequeño delay para asegurar que el control esté renderizado.
        """
        def after_build(e):
            try:
                print(f"🕒 [scroll_to_group_after_build] Esperando {delay*1000:.0f}ms para scroll al grupo '{group_id}'")
                time.sleep(delay)
                print(f"🔍 Buscando control con key='{group_id}'")

                # Verificar que exista el container con key=group_id dentro de scroll_column
                found = page.get_control(group_id) is not None
                print(f"🔍 Control encontrado: {found}")

                if found:
                    page.scroll_to(key=group_id, duration=300)
                    page.update()
                    print(f"✅ Scroll al grupo '{group_id}' realizado")
                else:
                    print(f"⚠️ No se encontró el grupo '{group_id}' para hacer scroll")
            except Exception as ex:
                print(f"⚠️ [scroll_to_group_after_build] Error al hacer scroll al grupo '{group_id}': {ex}")
            finally:
                page.on_after_build = None  # limpiar callback

        print(f"🔧 Registrando on_after_build para grupo '{group_id}'")
        page.on_after_build = after_build

    @staticmethod
    def scroll_after_table_update(page: ft.Page, group_id: str, delay: float = 0.05):
        """
        Scroll después de actualizar tabla sin bloquear la UI.
        Usa Timer para dar chance a que Flet renderice.
        """
        def hacer_scroll():
            try:
                print(f"🔍 [scroll_after_table_update] Esperando {delay*1000:.0f}ms para scroll al grupo '{group_id}'")
                # Verificar existencia del control
                found = page.get_control(group_id) is not None
                print(f"🔍 Control encontrado: {found}")

                if found:
                    page.scroll_to(key=group_id, duration=300)
                    page.update()
                    print(f"✅ Scroll al grupo '{group_id}' realizado")
                else:
                    print(f"⏳ Control no existe aún, no se hace scroll al grupo '{group_id}'")
            except Exception as e:
                print(f"⚠️ [scroll_after_table_update] Error al hacer scroll al grupo '{group_id}': {e}")

        Timer(delay, hacer_scroll).start()
