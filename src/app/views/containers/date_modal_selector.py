import flet as ft
import calendar
from datetime import datetime, date
from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert

_cal = calendar.Calendar()
_date_class = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
_month_class = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
}


class DateModalSelector:
    """
    Selector de fechas para pagos.
    - Solo días DISPONIBLES son clicables.
    - Selección 1..N días sueltos.
    - Autorrango: segundo clic llena los días disponibles del intervalo.
    - Guardar -> callback on_dates_confirmed(List[date]) con fechas ORDENADAS.
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

        self.fechas_bloqueadas: set[date] = set()
        self.fechas_disponibles: set[date] = set()

        self.seleccionadas: set[date] = set()
        self._anchor: date | None = None

    # ------------------ API pública ------------------

    def set_fechas_bloqueadas(self, fechas):
        self.fechas_bloqueadas = set(self._normalize_dates(fechas))
        self._sanitize_selection()   # ← limpia verdes fuera de reglas

    def set_fechas_disponibles(self, fechas):
        self.fechas_disponibles = set(self._normalize_dates(fechas))
        self._sanitize_selection()   # ← limpia verdes fuera de reglas

    def reset(self):
        """Limpia selección y ancla (útil al reabrir)."""
        self.seleccionadas.clear()
        self._anchor = None

    def abrir_dialogo(self, *, reset_selection: bool = True):
        # ← Limpia selección al abrir, para no arrastrar verdes del uso anterior
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

    # ------------------ Render UI ------------------

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

                # REGLA NUEVA: clicable = disponible Y NO bloqueada
                is_disponible = f_actual in self.fechas_disponibles
                is_bloqueada = f_actual in self.fechas_bloqueadas
                clickable = is_disponible and not is_bloqueada

                if is_bloqueada:
                    bgcolor = ft.colors.GREY_300
                    text_color = ft.colors.BLACK45
                elif clickable:
                    bgcolor = ft.colors.GREEN if f_actual in self.seleccionadas else None
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
                    on_click=(lambda e, f=f_actual: self._toggle_fecha(f)) if clickable else None,
                )
                fila.controls.append(box)
            grid.controls.append(fila)

        leyenda = ft.Row(
            [
                ft.Container(width=12, height=12, bgcolor=ft.colors.GREEN, border_radius=3),
                ft.Text("Seleccionada", size=11),
                ft.Container(width=12, height=12, bgcolor=ft.colors.GREY_100, border_radius=3),
                ft.Text("No disponible", size=11),
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

    def _on_cancel(self):
        # Limpia selección al cerrar para que no queden verdes “pegados”
        self.reset()
        self.cerrar_dialogo()

    def _toggle_fecha(self, f: date):
        # seguridad extra: solo permitir toggle si sigue siendo clicable
        if not (f in self.fechas_disponibles and f not in self.fechas_bloqueadas):
            return

        if not self.auto_range or self._anchor is None or f == self._anchor:
            if f in self.seleccionadas:
                self.seleccionadas.remove(f)
                if self._anchor == f:
                    self._anchor = None
            else:
                self.seleccionadas.add(f)
                self._anchor = f
        else:
            f1, f2 = (self._anchor, f) if self._anchor < f else (f, self._anchor)
            intervalo = [d for d in self._daterange(f1, f2) if d in self.fechas_disponibles and d not in self.fechas_bloqueadas]
            faltantes = [d for d in intervalo if d not in self.seleccionadas]
            if faltantes:
                self.seleccionadas.update(faltantes)
            else:
                for d in intervalo:
                    self.seleccionadas.discard(d)
            self._anchor = f

        self._reconstruir()
        if self.page:
            self.page.update()

    def _guardar_fechas(self):
        if not self.seleccionadas:
            ModalAlert.mostrar_info("Sin selección", "Selecciona al menos una fecha disponible.")
            return
        fechas = sorted(list(self.seleccionadas))
        try:
            self.on_dates_confirmed(fechas)
        finally:
            # Limpia selección después de guardar
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
        # sanea selección al cambiar de mes (por si verdes quedaron fuera o bloqueados)
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
        """Quita seleccionadas que no sean disponibles o estén bloqueadas."""
        if not self.seleccionadas:
            return
        validas = {d for d in self.seleccionadas if (d in self.fechas_disponibles and d not in self.fechas_bloqueadas)}
        if validas != self.seleccionadas:
            self.seleccionadas = validas
