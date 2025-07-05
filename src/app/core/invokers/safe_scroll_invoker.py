# app/core/invokers/safe_scroll_invoker.py

from threading import Timer

class SafeScrollInvoker:
    @staticmethod
    def scroll_to_bottom(page, key="bottom-anchor", delay=0.1):
        """
        Intenta hacer scroll al fondo después de un retardo.
        Evita el error 'View Control must be added to the page first'.

        :param page: Instancia de flet.Page
        :param key: Clave del ancla al fondo (por defecto: "bottom-anchor")
        :param delay: Tiempo de espera antes del scroll (en segundos)
        """
        def hacer_scroll():
            try:
                if page.views and page.views[-1] == page:
                    page.scroll_to(key=key, duration=300)
                    page.update()
                else:
                    print("⏳ View aún no está activa. No se hace scroll.")
            except Exception as e:
                print(f"⚠️ Error al hacer scroll: {e}")

        Timer(delay, hacer_scroll).start()
