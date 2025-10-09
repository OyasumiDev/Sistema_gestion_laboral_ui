from __future__ import annotations

import calendar
from datetime import datetime, date
from typing import Callable, Iterable, Optional, Set, List, Union

import flet as ft

from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert

_cal = calendar.Calendar()
_WDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
_MONTHS = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
}


class ModalFechaGrupoPagado:
    """
    Selector de UNA fecha para crear grupo 'pagado' (estilo DateModalSelector).

    - Bloquea días con grupo pagado existente.
    - Bloquea FUTURO (no puedes seleccionar más allá de hoy).
    - Muestra (informativo) días con pagos de cualquier estado.
    - Devuelve una fecha (date) a on_date_confirmed.
    """

    def __init__(
        self,
        on_date_confirmed: Callable[[date], None],
        *,
        cell_size: int = 40,
        dialog_width: int = 520,
        dialog_height: int = 560,
    ):
        self.page = AppState().page
        self.on_date_confirmed = on_date_confirmed
        self.dialog = ft.AlertDialog(modal=True)

        self.cell_size = int(cell_size)
        self.dialog_width = int(dialog_width)
        self.dialog_height = int(dialog_height)

        hoy = datetime.now()
        self.year = hoy.year
        self.month = hoy.month
        self._today = hoy.date()

        # Conjuntos
        self.fechas_pagadas: Set[date] = set()     # BLOQUEADAS (ya hay grupo pagado)
        self.fechas_con_pagos: Set[date] = set()   # Informativas (pagos de cualquier estado)

        # Selección única
        self.seleccionada: Optional[date] = None

    # ------------------ API pública ------------------

    def set_fechas_pagadas(self, fechas: Iterable[Union[date, str]]):
        self.fechas_pagadas = set(self._normalize_dates(fechas))
        if self.seleccionada and self.seleccionada in self.fechas_pagadas:
            self.seleccionada = None

    def set_fechas_con_pagos(self, fechas: Iterable[Union[date, str]]):
        self.fechas_con_pagos = set(self._normalize_dates(fechas))

    def cargar_desde_payment_model(self, payment_model) -> None:
        """Inicializa usando PaymentModel."""
        try:
            # Fechas 'pagadas' (bloqueadas)
            pagadas_fast = getattr(payment_model, "get_fechas_pagadas", None)
            if callable(pagadas_fast):
                self.fechas_pagadas = set(self._normalize_dates(pagadas_fast() or []))
            else:
                get_all = getattr(payment_model, "get_all_pagos", None)
                if callable(get_all):
                    res = get_all() or {}
                    rows: List[dict] = res.get("data") or []
                    pagadas: Set[date] = set()
                    for r in rows:
                        if str(r.get("estado", "")).lower() != "pagado":
                            continue
                        fechas_norm = self._normalize_dates([r.get("fecha_pago")])
                        if fechas_norm:
                            pagadas.add(fechas_norm[0])
                    self.fechas_pagadas = pagadas

            # Fechas usadas (informativo)
            usadas = getattr(payment_model, "get_fechas_utilizadas", None)
            if callable(usadas):
                self.fechas_con_pagos = set(self._normalize_dates(usadas()))
        except Exception:
            pass  # no romper UI

    def set_mes_anio(self, year: int, month: int):
        self.year = int(year)
        self.month = int(month)

    def abrir_dialogo(self, *, reset_selection: bool = True, focus_month_of: Optional[date] = None):
        if reset_selection:
            self.seleccionada = None
        if focus_month_of:
            self.year, self.month = focus_month_of.year, focus_month_of.month

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
        # Header tipo DateModalSelector: chevrons + título + botón "Hoy"
        can_next = not self._is_month_after_today(self.year, self.month)

        encabezado = ft.Row(
            [
                ft.IconButton("chevron_left", on_click=lambda e: self._cambiar_mes(-1)),
                ft.Text(f"{_MONTHS[self.month]} {self.year}", expand=True, text_align="center"),
                ft.IconButton("calendar_today", tooltip="Hoy", on_click=lambda e: self._go_today()),
                ft.IconButton("chevron_right", disabled=not can_next, on_click=lambda e: self._cambiar_mes(1)),
            ],
            alignment="center",
        )

        semana_hdr = ft.Row(
            [ft.Text(d, width=self.cell_size, text_align=ft.TextAlign.CENTER) for d in _WDAYS],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        grid_rows: List[ft.Control] = []
        for semana_dias in _cal.monthdayscalendar(self.year, self.month):
            fila = ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=6)
            for dia in semana_dias:
                if dia == 0:
                    fila.controls.append(ft.Container(width=self.cell_size, height=self.cell_size))
                    continue

                f_actual = date(self.year, self.month, dia)
                is_pagada = f_actual in self.fechas_pagadas
                has_pagos = f_actual in self.fechas_con_pagos
                is_future = f_actual > self._today
                is_selected = self.seleccionada == f_actual

                # colores / tooltip
                if is_selected:
                    bgcolor = ft.colors.GREEN
                    text_color = ft.colors.WHITE
                    tip = "Seleccionada"
                elif is_pagada:
                    bgcolor = ft.colors.GREY_400
                    text_color = ft.colors.BLACK54
                    tip = "Bloqueada: ya existe grupo pagado"
                elif is_future:
                    bgcolor = ft.colors.GREY_200
                    text_color = ft.colors.BLACK45
                    tip = "Futuro no permitido"
                elif has_pagos:
                    bgcolor = ft.colors.AMBER_200
                    text_color = ft.colors.BLACK
                    tip = "Con pagos (informativo)"
                else:
                    bgcolor = ft.colors.GREY_100
                    text_color = ft.colors.BLACK87
                    tip = "Disponible"

                clickable = (not is_pagada) and (not is_future)
                box = ft.Container(
                    width=self.cell_size,
                    height=self.cell_size,
                    bgcolor=bgcolor,
                    border_radius=8,
                    alignment=ft.alignment.center,
                    content=ft.Text(str(dia), color=text_color, size=13),
                    on_click=(lambda e, f=f_actual: self._toggle_unica(f)) if clickable else None,
                    tooltip=tip,
                )
                fila.controls.append(box)
            grid_rows.append(fila)

        leyenda = ft.Row(
            [
                ft.Container(width=12, height=12, bgcolor=ft.colors.GREEN, border_radius=3),
                ft.Text("Seleccionada", size=11),
                ft.Container(width=12, height=12, bgcolor=ft.colors.AMBER_200, border_radius=3),
                ft.Text("Con pagos (informativo)", size=11),
                ft.Container(width=12, height=12, bgcolor=ft.colors.GREY_100, border_radius=3),
                ft.Text("Disponible", size=11),
                ft.Container(width=12, height=12, bgcolor=ft.colors.GREY_400, border_radius=3),
                ft.Text("Bloqueada (grupo pagado)", size=11),
            ],
            spacing=10,
        )

        btn_guardar = ft.ElevatedButton(
            "Guardar", icon=ft.icons.CHECK, on_click=lambda e: self._guardar_fecha(),
            disabled=(self.seleccionada is None)
        )
        botones = ft.Row(
            [ft.TextButton("Cancelar", on_click=lambda e: self._on_cancel()), btn_guardar],
            alignment=ft.MainAxisAlignment.END,
        )

        self.dialog.content = ft.Container(
            content=ft.Column(
                [encabezado, semana_hdr, *grid_rows, ft.Divider(), leyenda, botones],
                spacing=12,
                tight=False,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=20,
            width=self.dialog_width,
            height=self.dialog_height,
            bgcolor=ft.colors.SURFACE_VARIANT,
            border_radius=20,
            alignment=ft.alignment.top_center,
        )

    # ------------------ Interacción ------------------

    def _on_cancel(self):
        self.seleccionada = None
        self.cerrar_dialogo()

    def _toggle_unica(self, f: date):
        if f in self.fechas_pagadas or f > self._today:
            return
        self.seleccionada = None if self.seleccionada == f else f
        self._reconstruir()
        if self.page:
            self.page.update()

    def _guardar_fecha(self):
        if not self.seleccionada:
            ModalAlert.mostrar_info("Sin selección", "Selecciona una fecha disponible.")
            return
        if self.seleccionada in self.fechas_pagadas:
            ModalAlert.mostrar_info("Fecha bloqueada", "Esa fecha ya tiene un grupo pagado.")
            return
        if self.seleccionada > self._today:
            ModalAlert.mostrar_info("No permitido", "No puedes crear grupos en fechas futuras.")
            return
        try:
            self.on_date_confirmed(self.seleccionada)
        finally:
            self.seleccionada = None
            self.cerrar_dialogo()

    def _cambiar_mes(self, delta: int):
        new_m = self.month + int(delta)
        new_y = self.year
        if new_m > 12:
            new_m, new_y = 1, new_y + 1
        elif new_m < 1:
            new_m, new_y = 12, new_y - 1

        # No permitir navegar más allá del mes de hoy (hacia futuro)
        if self._is_month_after_today(new_y, new_m):
            return

        self.month, self.year = new_m, new_y
        self._reconstruir()
        if self.page:
            self.page.update()

    def _go_today(self):
        self.year, self.month = self._today.year, self._today.month
        if self._today in self.fechas_pagadas:
            self.seleccionada = None
        self._reconstruir()
        if self.page:
            self.page.update()

    # ------------------ Utils ------------------

    def _is_month_after_today(self, y: int, m: int) -> bool:
        """True si (y, m) es posterior al mes actual."""
        return (y, m) > (self._today.year, self._today.month)

    @staticmethod
    def _normalize_dates(items: Optional[Iterable[Union[date, str]]]) -> List[date]:
        out: List[date] = []
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
