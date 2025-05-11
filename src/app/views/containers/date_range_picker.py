import flet as ft
import calendar
from datetime import datetime
from app.core.app_state import AppState

cal = calendar.Calendar()
date_class = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
month_class = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
}


class Settings:
    year = datetime.now().year
    month = datetime.now().month

    @staticmethod
    def get_year(): return Settings.year
    @staticmethod
    def get_month(): return Settings.month

    @staticmethod
    def get_date(delta: int):
        if delta == 1:
            if Settings.month + 1 > 12:
                Settings.month = 1
                Settings.year += 1
            else:
                Settings.month += 1
        elif delta == -1:
            if Settings.month - 1 < 1:
                Settings.month = 12
                Settings.year -= 1
            else:
                Settings.month -= 1


class DateBox(ft.Container):
    def __init__(self, day, date=None, grid_ref=None, on_select=None):
        super().__init__(
            width=30,
            height=30,
            alignment=ft.alignment.center,
            border_radius=5,
            bgcolor=None,
            content=ft.Text(str(day), text_align="center"),
            on_click=self._select
        )
        self.date = date
        self.grid_ref = grid_ref
        self.on_select = on_select

    def _select(self, e):
        for row in self.grid_ref.controls[2:]:
            for cell in row.controls:
                cell.bgcolor = None
                cell.border = None
        self.bgcolor = "#20303e"
        self.border = ft.border.all(1, "#4fadf9")
        if self.on_select:
            formatted = datetime.strptime(self.date, "%B %d, %Y").strftime("%Y-%m-%d")
            self.on_select(formatted)
        self.grid_ref.update()


class DateRangePicker(ft.Container):
    def __init__(self, text_inicio="Inicio", text_fin="Fin", on_range_selected=None, square_style=False):
        super().__init__(alignment=ft.alignment.center, padding=10)

        self.page = AppState().page
        self.on_range_selected = on_range_selected
        self.fecha_inicio = None
        self.fecha_fin = None
        self.tipo_activo = None
        self.square_style = square_style

        self.dialog = ft.AlertDialog(modal=True, content=ft.Container(), actions=[])

        self.inicio_btn = ft.TextButton(text_inicio, on_click=lambda _: self._abrir_modal("inicio"))
        self.fin_btn = ft.TextButton(text_fin, on_click=lambda _: self._abrir_modal("fin"))
        self.mensaje = ft.Text("Selecciona una fecha", size=12)

        self.content = ft.Column([
            ft.Row([self.inicio_btn, self.fin_btn], alignment="center", spacing=10),
            self.mensaje
        ])

    def _abrir_modal(self, tipo):
        self.tipo_activo = tipo
        self._actualizar_contenido_dialogo()
        if self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    def _actualizar_contenido_dialogo(self):
        year = Settings.get_year()
        month = Settings.get_month()
        tipo = self.tipo_activo

        def seleccionar_fecha(fecha_mysql):
            if tipo == "inicio":
                self.fecha_inicio = fecha_mysql
                self.inicio_btn.text = f"Inicio: {fecha_mysql}"
            else:
                self.fecha_fin = fecha_mysql
                self.fin_btn.text = f"Fin: {fecha_mysql}"

            if self.on_range_selected and self.fecha_inicio and self.fecha_fin:
                self.on_range_selected(self.fecha_inicio, self.fecha_fin)

            self.dialog.open = False
            self.page.update()

        encabezado = ft.Row([
            ft.IconButton("chevron_left", on_click=lambda e: self._cambiar_mes(-1)),
            ft.Text(f"{month_class[month]} {year}", expand=True, text_align="center"),
            ft.IconButton("chevron_right", on_click=lambda e: self._cambiar_mes(1))
        ], alignment="center")

        semana = ft.Row([ft.Text(day, width=30, text_align="center") for day in date_class], alignment="center")
        grid = ft.Column([encabezado, semana], expand=True)

        for semana_dias in cal.monthdayscalendar(year, month):
            fila = ft.Row(alignment="center")
            for dia in semana_dias:
                if dia == 0:
                    fila.controls.append(ft.Container(width=30, height=30))
                else:
                    fecha = f"{month_class[month]} {dia}, {year}"
                    fila.controls.append(DateBox(dia, fecha, grid, on_select=seleccionar_fecha))
            grid.controls.append(fila)

        self.dialog.content = ft.Container(
            content=grid,
            padding=20,
            bgcolor=ft.colors.SURFACE_VARIANT,
            border_radius=10,
            alignment=ft.alignment.center,
            width=360 if self.square_style else None,
            height=360 if self.square_style else None,
        )

    def _cambiar_mes(self, delta):
        Settings.get_date(delta)
        self._actualizar_contenido_dialogo()
        self.page.update()
