import flet as ft
import calendar
from datetime import datetime, date
from app.core.app_state import AppState
from app.models.assistance_model import AssistanceModel  # para sincronizar estados

_cal = calendar.Calendar()
_date_class = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
_month_class = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
}


class DateModalSelector:
    """
    Selector de fechas para pagos.
    - Muestra días con asistencias completas (verde claro) e incompletas (rojo).
    - Bloquea la selección en días incompletos o días con grupo PAGADO.
    - Selección individual o autorango (sin atravesar inválidas).
    """

    def __init__(
        self,
        on_dates_confirmed,
        *,
        cell_size: int = 40,
        dialog_width: int = 480,
        dialog_height: int = 560,
        auto_range: bool = True,
    ):
        self.page = AppState().page
        self.on_dates_confirmed = on_dates_confirmed
        self.dialog = ft.AlertDialog(modal=True)

        self.cell_size = int(cell_size)
        self.dialog_width = int(dialog_width)
        self.dialog_height = int(dialog_height)
        self.auto_range = bool(auto_range)

        hoy = datetime.now()
        self.year = hoy.year
        self.month = hoy.month

        self.fechas_bloqueadas: set[date] = set()     # solo PAGADOS
        self.fechas_disponibles: set[date] = set()    # clicables
        self.asistencias_estado: dict[date, str] = {} # {date: "completo"/"incompleto"}

        self.seleccionadas: set[date] = set()
        self._anchor: date | None = None

        # modelo (opcional para refrescar estados)
        self.assistance_model = AssistanceModel()

        # modal centrado propio
        self._center_alert = ft.AlertDialog(modal=True)

    # ------------------ API pública ------------------

    def sincronizar_asistencias(self, fi: date = None, ff: date = None, numero_nomina: int = None):
        estados = self.assistance_model.get_fechas_estado_completo_y_incompleto(fi, ff, numero_nomina)
        self.set_asistencias(estados)

    def set_fechas_bloqueadas(self, fechas):
        self.fechas_bloqueadas = set(self._normalize_dates(fechas))
        self._sanitize_selection()

    def set_fechas_disponibles(self, fechas):
        self.fechas_disponibles = set(self._normalize_dates(fechas))
        self._sanitize_selection()

    def set_asistencias(self, asistencias: dict):
        # dict => {date/str: estado}
        self.asistencias_estado = {
            self._normalize_dates([k])[0]: (v or "").lower() for k, v in asistencias.items()
        }

    def reset(self):
        self.seleccionadas.clear()
        self._anchor = None

    def abrir_dialogo(self, *, reset_selection: bool = True):
        if reset_selection:
            self.reset()

        if self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        self._reconstruir()
        self.dialog.open = True
        self.page.update()

    def cerrar_dialogo(self):
        self.dialog.open = False
        if self.page:
            self.page.update()

    # ------------------ UI ------------------

    def _reconstruir(self):
        encabezado = ft.Row(
            [
                ft.IconButton("chevron_left", on_click=lambda e: self._cambiar_mes(-1)),
                ft.Text(f"{_month_class[self.month]} {self.year}", expand=True, text_align="center"),
                ft.IconButton("chevron_right", on_click=lambda e: self._cambiar_mes(1)),
            ],
            alignment="center",
        )

        semana = ft.Row(
            [ft.Text(d, width=self.cell_size, text_align="center") for d in _date_class],
            alignment="center",
        )

        grid = ft.Column([encabezado, semana], expand=True, spacing=8)

        for semana_dias in _cal.monthdayscalendar(self.year, self.month):
            fila = ft.Row(alignment="center", spacing=6)
            for dia in semana_dias:
                if dia == 0:
                    fila.controls.append(ft.Container(width=self.cell_size, height=self.cell_size))
                    continue

                f_actual = date(self.year, self.month, dia)

                estado = (self.asistencias_estado.get(f_actual) or "").lower()
                is_disponible = f_actual in self.fechas_disponibles
                is_bloqueada = f_actual in self.fechas_bloqueadas
                is_incompleta = estado == "incompleto"
                is_completa = estado == "completo"
                is_selected = f_actual in self.seleccionadas

                clickable = is_disponible and not is_bloqueada and not is_incompleta

                # Colores / prioridad visual
                if is_selected:
                    bgcolor = ft.colors.GREEN
                    text_color = ft.colors.WHITE
                elif is_incompleta:
                    bgcolor = ft.colors.RED_400
                    text_color = ft.colors.WHITE
                elif is_bloqueada:
                    bgcolor = ft.colors.GREY_300
                    text_color = ft.colors.BLACK45
                elif is_completa:
                    bgcolor = ft.colors.GREEN_200
                    text_color = ft.colors.BLACK
                elif is_disponible:
                    bgcolor = ft.colors.GREY_50
                    text_color = ft.colors.BLACK
                else:
                    bgcolor = ft.colors.GREY_100
                    text_color = ft.colors.BLACK38

                box = ft.Container(
                    width=self.cell_size,
                    height=self.cell_size,
                    bgcolor=bgcolor,
                    border_radius=8,
                    alignment=ft.alignment.center,
                    content=ft.Text(str(dia), color=text_color, size=13),
                    on_click=(lambda e, f=f_actual: self._toggle_fecha(f)) if clickable
                             else (lambda e, f=f_actual: self._alerta_invalida(f)),
                )
                fila.controls.append(box)
            grid.controls.append(fila)

        leyenda = ft.Row(
            [
                ft.Container(width=12, height=12, bgcolor=ft.colors.GREEN, border_radius=3),
                ft.Text("Seleccionada", size=11),
                ft.Container(width=12, height=12, bgcolor=ft.colors.GREEN_200, border_radius=3),
                ft.Text("Asistencia completa", size=11),
                ft.Container(width=12, height=12, bgcolor=ft.colors.RED_400, border_radius=3),
                ft.Text("Asistencia incompleta", size=11),
                ft.Container(width=12, height=12, bgcolor=ft.colors.GREY_300, border_radius=3),
                ft.Text("Bloqueada", size=11),
            ],
            spacing=10,
        )

        botones = ft.Row(
            [
                ft.TextButton("Cancelar", on_click=lambda e: self._on_cancel()),
                ft.ElevatedButton("Guardar", on_click=lambda e: self._guardar_fechas()),
            ],
            alignment="end",
        )

        self.dialog.content = ft.Container(
            content=ft.Column([grid, leyenda, ft.Divider(), botones], spacing=16),
            padding=20,
            width=self.dialog_width,
            height=self.dialog_height,
            bgcolor=ft.colors.SURFACE_VARIANT,
            border_radius=20,
            alignment=ft.alignment.center,
        )

    # ------------------ Interacción ------------------

    def _show_center_alert(self, title: str, message: str, *, kind: str = "info"):
        """Cuadro centrado en pantalla (reemplaza mensajes laterales)."""
        icon = ft.Icon(ft.icons.ERROR_OUTLINE if kind == "error" else ft.icons.INFO_OUTLINE, size=26)
        content = ft.Container(
            width=520,
            bgcolor=ft.colors.SURFACE,
            padding=20,
            border_radius=16,
            content=ft.Column(
                [
                    ft.Row([icon, ft.Text(title or "Aviso", weight=ft.FontWeight.BOLD, size=16)], spacing=10),
                    ft.Text(message or ""),
                    ft.Row(
                        [ft.ElevatedButton("Cerrar", on_click=lambda e: self._close_center_alert())],
                        alignment="end",
                    ),
                ],
                spacing=14,
                tight=True,
            ),
        )
        self._center_alert.content = content
        if self._center_alert not in self.page.overlay:
            self.page.overlay.append(self._center_alert)
        self._center_alert.open = True
        self.page.update()

    def _close_center_alert(self):
        self._center_alert.open = False
        if self.page:
            self.page.update()

    def _alerta_invalida(self, f: date):
        estado = (self.asistencias_estado.get(f) or "").lower()
        if estado == "incompleto":
            self._show_center_alert(
                "Asistencia incompleta",
                f"No puedes seleccionar el día {f.strftime('%d/%m/%Y')} porque su asistencia está INCOMPLETA.",
                kind="error",
            )
        elif f in self.fechas_bloqueadas:
            self._show_center_alert(
                "Fecha bloqueada",
                f"El día {f.strftime('%d/%m/%Y')} pertenece a un grupo PAGADO y no puede seleccionarse.",
                kind="info",
            )
        else:
            self._show_center_alert(
                "No disponible",
                f"El día {f.strftime('%d/%m/%Y')} no está disponible para selección.",
                kind="info",
            )

    def _on_cancel(self):
        self.reset()
        self.cerrar_dialogo()

    def _toggle_fecha(self, f: date):
        # Seguridad
        if (self.asistencias_estado.get(f) or "").lower() == "incompleto" or f in self.fechas_bloqueadas:
            self._alerta_invalida(f)
            return
        if f not in self.fechas_disponibles:
            self._alerta_invalida(f)
            return

        # Click único / autorango
        if (not self.auto_range) or (self._anchor is None) or (f == self._anchor):
            if f in self.seleccionadas:
                self.seleccionadas.remove(f)
                if self._anchor == f:
                    self._anchor = None
            else:
                self.seleccionadas.add(f)
                self._anchor = f
        else:
            f1, f2 = (self._anchor, f) if self._anchor < f else (f, self._anchor)
            rango = list(self._daterange(f1, f2))

            # Si hay incompletas o bloqueadas, cancelar y soltar anchor para evitar “movimientos raros”
            invalidas = [d for d in rango if ((self.asistencias_estado.get(d) or "").lower() == "incompleto") or (d in self.fechas_bloqueadas)]
            if invalidas:
                fechas_txt = ", ".join(d.strftime("%d/%m/%Y") for d in invalidas)
                self._show_center_alert(
                    "Rango inválido",
                    f"No puedes seleccionar este rango porque contiene días inválidos: {fechas_txt}",
                    kind="error",
                )
                self._anchor = None
                self._reconstruir()
                if self.page:
                    self.page.update()
                return

            # Aplicar solo válidas dentro del rango
            rango_validas = [
                d for d in rango
                if d in self.fechas_disponibles and d not in self.fechas_bloqueadas
                and (self.asistencias_estado.get(d) or "").lower() != "incompleto"
            ]
            self.seleccionadas.update(rango_validas)
            self._anchor = f  # nuevo extremo

        self._reconstruir()
        if self.page:
            self.page.update()

    def _guardar_fechas(self):
        if not self.seleccionadas:
            self._show_center_alert("Sin selección", "Selecciona al menos una fecha disponible.", kind="info")
            return

        fechas = sorted(list(self.seleccionadas))
        incompletas = [f for f in fechas if (self.asistencias_estado.get(f) or "").lower() == "incompleto"]

        if incompletas:
            fechas_txt = ", ".join(d.strftime("%d/%m/%Y") for d in incompletas)
            self._show_center_alert(
                "Asistencias incompletas",
                f"No puedes continuar. Corrige primero las asistencias INCOMPLETAS: {fechas_txt}",
                kind="error",
            )
            return

        try:
            self.on_dates_confirmed(fechas)
        finally:
            self.reset()
            self.cerrar_dialogo()

    def _cambiar_mes(self, delta: int):
        self.month += int(delta)
        if self.month > 12:
            self.month = 1
            self.year += 1
        elif self.month < 1:
            self.month = 12
            self.year -= 1
        self._sanitize_selection()
        self._reconstruir()
        if self.page:
            self.page.update()

    # ------------------ Utils ------------------

    @staticmethod
    def _normalize_dates(items):
        out = []
        if not items:
            return out
        for x in items:
            if isinstance(x, date):
                out.append(x)
            elif isinstance(x, str):
                try:
                    out.append(datetime.strptime(x, "%Y-%m-%d").date())
                except Exception:
                    continue
        return out

    @staticmethod
    def _daterange(d1: date, d2: date):
        cur = d1
        while cur <= d2:
            yield cur
            cur = date.fromordinal(cur.toordinal() + 1)

    def _sanitize_selection(self):
        if not self.seleccionadas:
            return
        validas = {
            d for d in self.seleccionadas
            if (
                d in self.fechas_disponibles
                and d not in self.fechas_bloqueadas
                and (self.asistencias_estado.get(d) or "").lower() != "incompleto"
            )
        }
        if validas != self.seleccionadas:
            self.seleccionadas = validas

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
