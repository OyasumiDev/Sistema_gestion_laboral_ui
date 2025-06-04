import flet as ft
import calendar
from datetime import datetime, date
from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert

cal = calendar.Calendar()
date_class = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
month_class = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
}


class DateModalSelector:
    def __init__(self, on_dates_confirmed):
        self.page = AppState().page
        self.on_dates_confirmed = on_dates_confirmed
        self.dialog = ft.AlertDialog(modal=True)
        self.fechas_bloqueadas = []
        self._reset_seleccion()
        self.year = datetime.now().year
        self.month = datetime.now().month

    def set_fechas_bloqueadas(self, fechas):
        """Recibe una lista de objetos date en formato YYYY-MM-DD"""
        self.fechas_bloqueadas = fechas or []

    def abrir_dialogo(self):
        self._reset_seleccion()
        self._construir_contenido()
        if self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    def cerrar_dialogo(self):
        self.dialog.open = False
        self.page.update()

    def _reset_seleccion(self):
        self.fecha_inicio = None
        self.fecha_fin = None

    def _construir_contenido(self):
        def seleccionar_fecha(fecha: date):
            if fecha in self.fechas_bloqueadas:
                ModalAlert.mostrar_info(
                    "Fecha bloqueada",
                    "Esta fecha ya fue utilizada para generar un periodo anterior. Por favor, selecciona un rango diferente."
                )
                return

            if self.fecha_inicio == fecha:
                self.fecha_inicio = None
            elif self.fecha_fin == fecha:
                self.fecha_fin = None
            elif not self.fecha_inicio:
                self.fecha_inicio = fecha
            elif not self.fecha_fin:
                if fecha < self.fecha_inicio:
                    self.fecha_fin = self.fecha_inicio
                    self.fecha_inicio = fecha
                else:
                    self.fecha_fin = fecha
            else:
                ModalAlert.mostrar_info("Límite de selección", "Solo puedes seleccionar dos fechas. Cancela o guarda para continuar.")
                return

            self._construir_contenido()
            self.page.update()

        encabezado = ft.Row([
            ft.IconButton("chevron_left", on_click=lambda e: self._cambiar_mes(-1)),
            ft.Text(f"{month_class[self.month]} {self.year}", expand=True, text_align="center"),
            ft.IconButton("chevron_right", on_click=lambda e: self._cambiar_mes(1))
        ], alignment="center")

        semana = ft.Row([ft.Text(d, width=30, text_align="center") for d in date_class], alignment="center")
        grid = ft.Column([encabezado, semana], expand=True)

        for semana_dias in cal.monthdayscalendar(self.year, self.month):
            fila = ft.Row(alignment="center")
            for dia in semana_dias:
                if dia == 0:
                    fila.controls.append(ft.Container(width=30, height=30))
                    continue

                fecha_actual = date(self.year, self.month, dia)
                color = None
                text_color = ft.colors.BLACK

                if fecha_actual in self.fechas_bloqueadas:
                    color = ft.colors.GREY_300
                    text_color = ft.colors.BLACK45
                    clickable = False
                else:
                    clickable = True
                    if self.fecha_inicio and self.fecha_fin:
                        if fecha_actual == self.fecha_inicio:
                            color = ft.colors.GREEN
                        elif fecha_actual == self.fecha_fin:
                            color = ft.colors.RED
                        elif self.fecha_inicio < fecha_actual < self.fecha_fin:
                            color = ft.colors.GREEN_100
                    elif self.fecha_inicio == fecha_actual:
                        color = ft.colors.GREEN

                box = ft.Container(
                    width=30,
                    height=30,
                    bgcolor=color,
                    border_radius=5,
                    alignment=ft.alignment.center,
                    content=ft.Text(str(dia), color=text_color),
                    on_click=(lambda e, f=fecha_actual: seleccionar_fecha(f)) if clickable else None
                )
                fila.controls.append(box)
            grid.controls.append(fila)

        botones = ft.Row([
            ft.TextButton("Cancelar", on_click=lambda e: self.cerrar_dialogo()),
            ft.ElevatedButton("Guardar", on_click=lambda e: self._guardar_fechas())
        ], alignment="end")

        self.dialog.content = ft.Container(
            content=ft.Column([grid, botones], spacing=15),
            padding=20,
            width=330,
            height=350,
            bgcolor=ft.colors.SURFACE_VARIANT,
            border_radius=20,
            alignment=ft.alignment.center
        )

    def _guardar_fechas(self):
        if self.fecha_inicio and self.fecha_fin:
            self.on_dates_confirmed(self.fecha_inicio, self.fecha_fin)
            self.cerrar_dialogo()

    def _cambiar_mes(self, delta):
        self.month += delta
        if self.month > 12:
            self.month = 1
            self.year += 1
        elif self.month < 1:
            self.month = 12
            self.year -= 1
        self._construir_contenido()
        self.page.update()
