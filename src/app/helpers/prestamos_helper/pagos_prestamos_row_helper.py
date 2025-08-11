import flet as ft
from typing import Callable, Optional, List
from app.core.enums.e_pagos_prestamos import E_PAGOS_PRESTAMO as E
from app.helpers.boton_factory import (
    crear_boton_editar,
    crear_boton_eliminar,
)

class PagosPrestamosRowHelper:
    """
    Helper para listar pagos de préstamo sin DataTable (compatible Flet 0.24.0).
    - Mantiene API amigable con tu contenedor: build_fila_pago(...) y get_columnas().
    - Recomendado usar build_list(...) para render completo (header + filas).
    """

    # Anchos de “columnas” (alineados al estilo de PrestamosRowHelper)
    W_ID = 80
    W_FECHA = 120
    W_NUM = 110
    W_SALDO = 120
    W_SALDOI = 130
    W_INTERES = 90
    W_OBS = 340
    W_ACC = 130

    def _fmt_float(self, v, d=0.0) -> float:
        try:
            return float(v)
        except Exception:
            return float(d)

    def _cell(self, text: str, w: int | None = None, bold: bool = False, tooltip: str | None = None) -> ft.Control:
        t = ft.Text(text, weight=ft.FontWeight.BOLD if bold else None, size=12, no_wrap=True)
        c = ft.Container(t, width=w, padding=ft.padding.symmetric(horizontal=4, vertical=8))
        if tooltip:
            return ft.Tooltip(message=tooltip, content=c)
        return c

    # ------------------ Cabecera ------------------

    def build_header(self) -> ft.Control:
        return ft.Container(
            bgcolor=ft.colors.SURFACE_VARIANT,
            border_radius=10,
            padding=4,
            content=ft.Row(
                [
                    self._cell("ID", self.W_ID, True),
                    self._cell("Fecha prog.", self.W_FECHA, True),
                    self._cell("Fecha real", self.W_FECHA, True),
                    self._cell("Pagado", self.W_NUM, True),
                    self._cell("Saldo", self.W_SALDO, True),
                    self._cell("Saldo + interés", self.W_SALDOI, True),
                    self._cell("Interés (%)", self.W_INTERES, True),
                    self._cell("Observaciones", self.W_OBS, True),
                    ft.Container(width=self.W_ACC),
                ],
                spacing=0,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=False,
            ),
        )

    # --------------- Fila individual ----------------

    def build_fila_pago(
        self,
        pago: dict,
        editable: bool,
        on_edit: Optional[Callable[[dict], None]] = None,
        on_delete: Optional[Callable[[dict], None]] = None,
    ) -> ft.Control:
        """
        Devuelve una fila visual de pago (Container) lista para insertar en un Column.
        Mantiene firma usada por tu contenedor.
        """
        # Lectura segura de campos
        pid = pago.get(E.ID_PAGO_PRESTAMO.value, "-")
        fecha_prog = str(pago.get(E.PAGO_FECHA_PAGO.value, "-"))
        fecha_real = str(pago.get(E.PAGO_FECHA_REAL.value, "-"))
        pagado = self._fmt_float(pago.get(E.PAGO_MONTO_PAGADO.value, 0))
        interes_apl = self._fmt_float(pago.get(E.PAGO_INTERES_APLICADO.value, 0))
        interes_pct = str(pago.get(E.PAGO_INTERES_PORCENTAJE.value, "0") or "0")
        saldo_rest = self._fmt_float(pago.get(E.PAGO_SALDO_RESTANTE.value, 0))
        obs_raw = str(pago.get(E.PAGO_OBSERVACIONES.value, "") or "")
        obs_short = obs_raw if len(obs_raw) <= 60 else obs_raw[:57] + "…"
        saldo_mas_interes = saldo_rest + interes_apl

        # Acciones
        acciones: list[ft.Control] = []
        if editable:
            if on_edit:
                acciones.append(crear_boton_editar(lambda e, p=pago: on_edit(p)))
            if on_delete:
                acciones.append(crear_boton_eliminar(lambda e, p=pago: on_delete(p)))

        return ft.Container(
            border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.GREY_200)),
            padding=0,
            content=ft.Row(
                [
                    self._cell(str(pid), self.W_ID),
                    self._cell(fecha_prog, self.W_FECHA),
                    self._cell(fecha_real, self.W_FECHA),
                    self._cell(f"${pagado:.2f}", self.W_NUM),
                    self._cell(f"${saldo_rest:.2f}", self.W_SALDO),
                    self._cell(f"${saldo_mas_interes:.2f}", self.W_SALDOI),
                    self._cell(f"{interes_pct}%", self.W_INTERES),
                    self._cell(obs_short, self.W_OBS, tooltip=obs_raw if obs_short.endswith("…") else None),
                    ft.Container(ft.Row(acciones, spacing=6), width=self.W_ACC, alignment=ft.alignment.center_right),
                ],
                spacing=0,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=False,
            ),
        )

    # --------------- Lista completa ----------------

    def build_list(
        self,
        pagos: List[dict],
        editable: bool,
        on_edit: Optional[Callable[[dict], None]] = None,
        on_delete: Optional[Callable[[dict], None]] = None,
        max_height: int | None = 260,
    ) -> ft.Control:
        filas: list[ft.Control] = [self.build_header()]
        for p in pagos:
            filas.append(self.build_fila_pago(p, editable=editable, on_edit=on_edit, on_delete=on_delete))

        body = ft.Column(filas, spacing=0)
        if max_height:
            return ft.Container(
                content=body,
                height=max_height,
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                expand=False,
                bgcolor=ft.colors.TRANSPARENT,
            )
        return body

    # --------- Compat: API antigua de columnas ---------
    def get_columnas(self) -> List[ft.DataColumn]:
        # Conservado para no romper imports existentes, aunque ya no usamos DataTable.
        return [
            ft.DataColumn(ft.Text("ID")),
            ft.DataColumn(ft.Text("Fecha prog.")),
            ft.DataColumn(ft.Text("Fecha real")),
            ft.DataColumn(ft.Text("Pagado")),
            ft.DataColumn(ft.Text("Saldo")),
            ft.DataColumn(ft.Text("Saldo + interés")),
            ft.DataColumn(ft.Text("Interés (%)")),
            ft.DataColumn(ft.Text("Observaciones")),
            ft.DataColumn(ft.Text("Acciones")),
        ]
