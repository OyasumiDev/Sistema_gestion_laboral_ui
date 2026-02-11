# app/views/containers/date_modal_selector.py
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

import flet as ft

from app.core.app_state import AppState
from app.models.fechas_modal_model import FechasModalModel, CalendarState


# -------------------------
# Config estático calendario
# -------------------------
_CAL = calendar.Calendar()
_WEEK_LABELS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
_MONTH_LABELS = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
}


@dataclass(frozen=True)
class DateModalSyncOptions:
    """
    Opciones de sincronización para el modal.

    - numero_nomina:
        Si lo pasas, el calendario se calcula SOLO con asistencias/pagos de ese empleado.
        Si None, se calcula de forma global.

    - bloquear_pagados:
        Si True, bloquea fechas cubiertas por rangos ya pagados.
        (Regla de inmutabilidad real)

    - incluir_bloqueo_admin_pagado:
        Si True, incluye bloqueo administrativo proveniente de `fecha_grupos_pagados` (si lo usas).
    """
    numero_nomina: Optional[int] = None
    bloquear_pagados: bool = True
    incluir_bloqueo_admin_pagado: bool = True


class DateModalSelector:
    """
    Selector de fechas (modal) para el área de pagos.

    ✅ Dependencia ÚNICA de datos: FechasModalModel.build_calendar_state()
       (el modelo es quien decide: disponibles, bloqueadas, completo/incompleto)

    Reglas (alineadas a tu lógica final)
    -----------------------------------
    - Una fecha ES seleccionable si:
        • está en fechas_disponibles (=> tiene asistencias existentes)
        • NO está bloqueada (pagados o bloqueo admin)
        • su estado de asistencias NO es "incompleto"
    - NO se bloquea una fecha solo por "haber sido usada".
      Si aparece una nueva asistencia en una fecha ya usada, puede volver a seleccionarse,
      siempre que el modelo la considere disponible.

    Flujo típico
    ------------
    selector = DateModalSelector(on_dates_confirmed=cb)
    selector.sync_mes()   # trae estado del mes actual desde FechasModalModel
    selector.abrir_dialogo()
    """

    def __init__(
        self,
        on_dates_confirmed: Callable[[List[date]], None],
        *,
        cell_size: int = 40,
        dialog_width: int = 560,
        dialog_height: int = 640,
        auto_range: bool = True,
    ):
        self.page = AppState().page
        self.on_dates_confirmed = on_dates_confirmed

        self.cell_size = int(cell_size)
        self.dialog_width = int(dialog_width)
        self.dialog_height = int(dialog_height)
        self.auto_range = bool(auto_range)

        now = datetime.now()
        self.year = now.year
        self.month = now.month

        # Estado de selección
        self.seleccionadas: Set[date] = set()
        self._anchor: Optional[date] = None

        # Estado calculado por modelo
        self.fechas_disponibles: Set[date] = set()
        self.fechas_bloqueadas: Set[date] = set()
        self.asistencias_estado: Dict[date, str] = {}  # date -> "completo"/"incompleto"/...

        # Debug opcional para inspección (si algo no pinta como esperas)
        self.debug: Dict[str, Any] = {}

        # Modelo (única fuente)
        self.fechas_model = FechasModalModel()

        # Dialogs
        self.dialog = ft.AlertDialog(modal=True)
        self._center_alert = ft.AlertDialog(modal=True)

        # Últimas opciones de sync (para reusar al cambiar mes)
        self._last_sync_opts = DateModalSyncOptions()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def reset(self) -> None:
        self.seleccionadas.clear()
        self._anchor = None

    def abrir_dialogo(self, *, reset_selection: bool = True) -> None:
        if reset_selection:
            self.reset()

        if self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)

        # por default, asegúrate de tener estado del mes actual
        if not self.fechas_disponibles and not self.asistencias_estado and not self.fechas_bloqueadas:
            self.sync_mes(self._last_sync_opts)

        self._reconstruir()
        self.dialog.open = True
        self.page.update()

    def cerrar_dialogo(self) -> None:
        self.dialog.open = False
        if self.page:
            self.page.update()

    # ------------------------------------------------------------------
    # Sync (dependiente 100% de FechasModalModel)
    # ------------------------------------------------------------------

    def sync_mes(self, opts: Optional[DateModalSyncOptions] = None) -> None:
        """
        Sincroniza el mes actual desde FechasModalModel.

        Esto llena:
        - fechas_disponibles
        - fechas_bloqueadas
        - asistencias_estado
        """
        if opts is None:
            opts = self._last_sync_opts
        else:
            self._last_sync_opts = opts

        try:
            cal_state: CalendarState = self.fechas_model.build_calendar_state(
                self.year,
                self.month,
                numero_nomina=opts.numero_nomina,
                bloquear_pagados=opts.bloquear_pagados,
                incluir_bloqueo_admin_pagado=opts.incluir_bloqueo_admin_pagado,
            )

            self.fechas_disponibles = set(cal_state.fechas_disponibles or set())
            self.fechas_bloqueadas = set(cal_state.fechas_bloqueadas or set())
            self.asistencias_estado = dict(cal_state.asistencias_estado or {})
            self.debug = dict(cal_state.debug or {})

        except Exception as ex:
            # Fallback: sin bloqueos y sin asistencias (no habrá selección)
            self.fechas_disponibles = set()
            self.fechas_bloqueadas = set()
            self.asistencias_estado = {}
            self.debug = {"error": str(ex)}

        self._sanitize_selection()

    # ------------------------------------------------------------------
    # UI builder
    # ------------------------------------------------------------------

    def _reconstruir(self) -> None:
        encabezado = ft.Row(
            [
                ft.IconButton("chevron_left", on_click=lambda e: self._cambiar_mes(-1)),
                ft.Text(f"{_MONTH_LABELS[self.month]} {self.year}", expand=True, text_align="center"),
                ft.IconButton("chevron_right", on_click=lambda e: self._cambiar_mes(1)),
            ],
            alignment="center",
        )

        semana = ft.Row(
            [ft.Text(d, width=self.cell_size, text_align="center") for d in _WEEK_LABELS],
            alignment="center",
        )

        grid = ft.Column([encabezado, semana], expand=True, spacing=8)

        for week in _CAL.monthdayscalendar(self.year, self.month):
            row = ft.Row(alignment="center", spacing=6)
            for day in week:
                if day == 0:
                    row.controls.append(ft.Container(width=self.cell_size, height=self.cell_size))
                    continue

                f_actual = date(self.year, self.month, day)

                estado = (self.asistencias_estado.get(f_actual) or "").lower()
                is_disponible = f_actual in self.fechas_disponibles
                is_bloqueada = f_actual in self.fechas_bloqueadas
                is_incompleta = estado == "incompleto"
                is_completa = estado == "completo"
                is_selected = f_actual in self.seleccionadas

                clickable = is_disponible and (not is_bloqueada) and (not is_incompleta)

                # prioridad visual
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

                row.controls.append(
                    ft.Container(
                        width=self.cell_size,
                        height=self.cell_size,
                        bgcolor=bgcolor,
                        border_radius=8,
                        alignment=ft.alignment.center,
                        content=ft.Text(str(day), color=text_color, size=13),
                        on_click=(lambda e, f=f_actual: self._toggle_fecha(f)) if clickable
                        else (lambda e, f=f_actual: self._alerta_invalida(f)),
                    )
                )

            grid.controls.append(row)

        leyenda = ft.Row(
            [
                ft.Container(width=12, height=12, bgcolor=ft.colors.GREEN, border_radius=3),
                ft.Text("Seleccionada", size=11),
                ft.Container(width=12, height=12, bgcolor=ft.colors.GREEN_200, border_radius=3),
                ft.Text("Asistencia completa", size=11),
                ft.Container(width=12, height=12, bgcolor=ft.colors.RED_400, border_radius=3),
                ft.Text("Asistencia incompleta", size=11),
                ft.Container(width=12, height=12, bgcolor=ft.colors.GREY_300, border_radius=3),
                ft.Text("Bloqueada (pagado)", size=11),
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
            content=ft.Column([grid, leyenda, ft.Divider(), botones], spacing=16, scroll=ft.ScrollMode.AUTO),
            padding=20,
            width=self.dialog_width,
            height=self.dialog_height,
            bgcolor=ft.colors.SURFACE_VARIANT,
            border_radius=20,
            alignment=ft.alignment.center,
        )

    # ------------------------------------------------------------------
    # Interacción
    # ------------------------------------------------------------------

    def _on_cancel(self) -> None:
        self.reset()
        self.cerrar_dialogo()

    def _toggle_fecha(self, f: date) -> None:
        # hard guards, definidos por el modelo
        if (self.asistencias_estado.get(f) or "").lower() == "incompleto":
            self._alerta_invalida(f)
            return
        if f in self.fechas_bloqueadas:
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
            a = self._anchor
            f1, f2 = (a, f) if a < f else (f, a)
            rango = list(self._daterange(f1, f2))

            invalidas = [
                d for d in rango
                if (d in self.fechas_bloqueadas)
                or ((self.asistencias_estado.get(d) or "").lower() == "incompleto")
                or (d not in self.fechas_disponibles)
            ]
            if invalidas:
                fechas_txt = ", ".join(d.strftime("%d/%m/%Y") for d in invalidas)
                self._show_center_alert(
                    "Rango inválido",
                    f"No puedes seleccionar este rango porque contiene días inválidos: {fechas_txt}",
                    kind="error",
                )
                self._anchor = None
                self._reconstruir()
                self.page.update()
                return

            self.seleccionadas.update(rango)
            self._anchor = f

        self._reconstruir()
        self.page.update()

    def _guardar_fechas(self) -> None:
        if not self.seleccionadas:
            self._show_center_alert("Sin selección", "Selecciona al menos una fecha disponible.", kind="info")
            return

        fechas = sorted(list(self.seleccionadas))
        incompletas = [d for d in fechas if (self.asistencias_estado.get(d) or "").lower() == "incompleto"]
        bloqueadas = [d for d in fechas if d in self.fechas_bloqueadas]
        no_disponibles = [d for d in fechas if d not in self.fechas_disponibles]

        if incompletas or bloqueadas or no_disponibles:
            parts = []
            if incompletas:
                parts.append("INCOMPLETAS: " + ", ".join(d.strftime("%d/%m/%Y") for d in incompletas))
            if bloqueadas:
                parts.append("BLOQUEADAS (pagado): " + ", ".join(d.strftime("%d/%m/%Y") for d in bloqueadas))
            if no_disponibles:
                parts.append("NO DISPONIBLES: " + ", ".join(d.strftime("%d/%m/%Y") for d in no_disponibles))

            self._show_center_alert(
                "Selección inválida",
                "No puedes continuar. Corrige primero:\n\n" + "\n".join(parts),
                kind="error",
            )
            return

        try:
            self.on_dates_confirmed(fechas)
        finally:
            self.reset()
            self.cerrar_dialogo()

    def _cambiar_mes(self, delta: int) -> None:
        self.month += int(delta)
        if self.month > 12:
            self.month = 1
            self.year += 1
        elif self.month < 1:
            self.month = 12
            self.year -= 1

        # ✅ clave: al cambiar mes, vuelve a sincronizar desde el modelo
        self.sync_mes(self._last_sync_opts)

        self._reconstruir()
        self.page.update()

    # ------------------------------------------------------------------
    # Alertas centradas
    # ------------------------------------------------------------------

    def _show_center_alert(self, title: str, message: str, *, kind: str = "info") -> None:
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
                    ft.Row([ft.ElevatedButton("Cerrar", on_click=lambda e: self._close_center_alert())], alignment="end"),
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

    def _close_center_alert(self) -> None:
        self._center_alert.open = False
        self.page.update()

    def _alerta_invalida(self, f: date) -> None:
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
                f"El día {f.strftime('%d/%m/%Y')} pertenece a un rango PAGADO y no puede seleccionarse.",
                kind="info",
            )
        elif f not in self.fechas_disponibles:
            self._show_center_alert(
                "No disponible",
                f"El día {f.strftime('%d/%m/%Y')} no está disponible para selección (no hay asistencias).",
                kind="info",
            )
        else:
            self._show_center_alert(
                "No disponible",
                f"El día {f.strftime('%d/%m/%Y')} no está disponible para selección.",
                kind="info",
            )

    # ------------------------------------------------------------------
    # Utils
    # ------------------------------------------------------------------

    def _sanitize_selection(self) -> None:
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

        if self._anchor and self._anchor not in self.seleccionadas:
            self._anchor = None

    @staticmethod
    def _daterange(d1: date, d2: date):
        cur = d1
        while cur <= d2:
            yield cur
            cur = date.fromordinal(cur.toordinal() + 1)
