import flet as ft
import calendar
from datetime import datetime
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
        self.fecha_inicio = None
        self.fecha_fin = None
        self.year = datetime.now().year
        self.month = datetime.now().month

        self.dialog = ft.AlertDialog(modal=True)

    def abrir_dialogo(self):
        self._construir_contenido()
        if self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    def _construir_contenido(self):
        def seleccionar_fecha(fecha):
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

        def formato_fecha_mysql(fecha):
            return datetime.strptime(fecha, "%B %d, %Y").strftime("%Y-%m-%d")

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

                fecha = f"{month_class[self.month]} {dia}, {self.year}"
                fecha_mysql = formato_fecha_mysql(fecha)
                color = None
                if self.fecha_inicio and self.fecha_fin:
                    if fecha_mysql == self.fecha_inicio:
                        color = ft.colors.GREEN
                    elif fecha_mysql == self.fecha_fin:
                        color = ft.colors.RED
                elif self.fecha_inicio and fecha_mysql == self.fecha_inicio:
                    color = ft.colors.GREEN

                box = ft.Container(
                    width=30,
                    height=30,
                    bgcolor=color,
                    border_radius=5,
                    alignment=ft.alignment.center,
                    content=ft.Text(str(dia)),
                    on_click=lambda e, f=fecha: seleccionar_fecha(formato_fecha_mysql(f))
                )
                fila.controls.append(box)
            grid.controls.append(fila)

        botones = ft.Row([
            ft.TextButton("Cancelar", on_click=lambda e: self._cerrar_dialogo()),
            ft.ElevatedButton("Guardar", on_click=lambda e: self._guardar_fechas())
        ], alignment="end")

        self.dialog.content = ft.Container(
            content=ft.Column([
                grid,
                botones
            ], spacing=15),
            padding=20,
            width=330,
            height=350,
            bgcolor=ft.colors.SURFACE_VARIANT,
            border_radius=20,
            alignment=ft.alignment.center
        )

    def _guardar_fechas(self):
        if self.fecha_inicio and self.fecha_fin:
            self.dialog.open = False
            self.page.update()
            self.on_dates_confirmed(self.fecha_inicio, self.fecha_fin)

    def _cerrar_dialogo(self):
        self.dialog.open = False
        self.page.update()

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
