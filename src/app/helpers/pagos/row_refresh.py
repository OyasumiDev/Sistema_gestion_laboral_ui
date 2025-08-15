# helpers/pagos/payment_row_refresh.py
from __future__ import annotations

from typing import Any, Dict, Optional, Callable
import flet as ft

from app.helpers.pagos.payment_view_math import PaymentViewMath, RowCalcDict
from app.models.discount_model import DiscountModel
from app.models.descuento_detalles_model import DescuentoDetallesModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.detalles_pagos_prestamo_model import DetallesPagosPrestamoModel


class PaymentRowRefresh:
    """
    Row helper para Pagos, compatible con Flet 0.24:
      - Sin InputFilter/regex (validación manual suave).
      - Escritura continua en 'Depósito' (no se reescribe .value en on_change).
      - Recalcula y pinta campos derivados en vivo.
      - Usa callbacks externos (editar descuentos, préstamos, confirmar, eliminar).
    """

    def __init__(
        self,
        *,
        aplicar_redondeo_50: bool = True,
        key_id_pago: str = "id_pago_nomina",
        key_monto_base: str = "monto_base",
        key_estado: str = "estado",
        # Inyección de modelos (opcional)
        discount_model: Optional[DiscountModel] = None,
        detalles_desc_model: Optional[DescuentoDetallesModel] = None,
        loan_payment_model: Optional[LoanPaymentModel] = None,
        detalles_prestamo_model: Optional[DetallesPagosPrestamoModel] = None,
        # Callbacks generales (opcionales)
        on_after_recalc: Optional[Callable[[RowCalcDict], None]] = None,
    ):
        self.key_id_pago = key_id_pago
        self.key_monto_base = key_monto_base
        self.key_estado = key_estado
        self.aplicar_redondeo_50 = aplicar_redondeo_50
        self.on_after_recalc = on_after_recalc

        self.math = PaymentViewMath(
            discount_model=discount_model or DiscountModel(),
            detalles_desc_model=detalles_desc_model or DescuentoDetallesModel(),
            loan_payment_model=loan_payment_model or LoanPaymentModel(),
            detalles_prestamo_model=detalles_prestamo_model or DetallesPagosPrestamoModel(),
        )

        # refs por fila (se guardan en row.data)
        # no se definen aquí; se crean en build_row y se acceden vía setters

    # -----------------------------
    # Construcción de fila
    # -----------------------------
    def build_row(
        self,
        pago_row: Dict[str, Any],
        *,
        descuentos_value: float,
        prestamos_value: float,
        saldo_value: float,
        deposito_value: float,
        efectivo_value: float,
        total_value: float,
        esta_pagado: bool,
        on_confirmar: Callable[[int], None],
        on_eliminar: Callable[[int], None],
        on_editar_descuentos: Callable[[Dict[str, Any]], None],
        on_editar_prestamos: Callable[[Dict[str, Any]], None],
        on_deposito_change: Callable[[str], None],
        on_deposito_blur: Callable[[], None],
        on_deposito_submit: Callable[[], None],
        tiene_prestamo_activo: bool,
    ) -> ft.DataRow:
        """
        Misma firma/estilo que tu RowRefresh previo.
        Guarda refs en row.data para setters posteriores.
        """
        id_pago = int(pago_row.get(self.key_id_pago) or pago_row.get("id_pago") or 0)
        id_empleado = int(pago_row.get("numero_nomina") or pago_row.get("id_empleado") or 0)
        nombre = str(pago_row.get("nombre_completo") or pago_row.get("nombre") or "-")
        fecha_pago = str(pago_row.get("fecha_pago") or pago_row.get("fecha") or "-")
        horas = f"{float(pago_row.get('horas', 0) or 0):.2f}"
        sueldo_hora = f"{float(pago_row.get('sueldo_hora', 0) or 0):.2f}"
        monto_base = f"{float(pago_row.get(self.key_monto_base, 0) or 0):.2f}"
        estado = str(pago_row.get(self.key_estado) or "").strip()

        def _wrap(control: ft.Control, width: int) -> ft.Container:
            return ft.Container(
                content=control,
                width=width,
                alignment=ft.alignment.center,
                padding=ft.padding.symmetric(horizontal=2),
            )

        def fmt2(v: float) -> str:
            try:
                return f"{float(v):.2f}"
            except Exception:
                return "0.00"

        # --- Campos de solo lectura derivados ---
        txt_desc = ft.TextField(value=fmt2(descuentos_value), read_only=True, text_align=ft.TextAlign.RIGHT, width=120)
        txt_prest = ft.TextField(value=fmt2(prestamos_value), read_only=True, text_align=ft.TextAlign.RIGHT, width=110)
        txt_saldo = ft.TextField(value=fmt2(saldo_value), read_only=True, text_align=ft.TextAlign.RIGHT, width=100)
        txt_efec = ft.TextField(value=fmt2(efectivo_value), read_only=True, text_align=ft.TextAlign.RIGHT, width=110)
        txt_total = ft.TextField(value=fmt2(total_value), read_only=True, text_align=ft.TextAlign.RIGHT, width=110)

        # --- Depósito editable (sin regex / InputFilter) ---
        #     Validación suave en on_change, sin reescribir .value (para escritura continua).
        txt_dep = ft.TextField(
            value=fmt2(deposito_value),
            text_align=ft.TextAlign.RIGHT,
            width=120,
            read_only=esta_pagado,
            keyboard_type=ft.KeyboardType.NUMBER,  # en Flet 0.24 esto funciona como hint
            on_change=lambda e: self._on_dep_change(
                e, pago_row, txt_desc, txt_prest, txt_total, txt_efec, txt_saldo, on_deposito_change
            ),
            on_blur=lambda e: on_deposito_blur(),
            on_submit=lambda e: on_deposito_submit(),
        )

        # --- Acciones ---
        btn_desc = ft.IconButton(
            icon=ft.icons.PRICE_CHANGE_OUTLINED,
            tooltip="Editar descuentos",
            on_click=lambda e: on_editar_descuentos(pago_row),
        )
        btn_prest = ft.IconButton(
            icon=ft.icons.ACCOUNT_BALANCE_WALLET_OUTLINED,
            tooltip="Editar préstamos",
            disabled=not tiene_prestamo_activo,
            on_click=(lambda e: on_editar_prestamos(pago_row)) if tiene_prestamo_activo else None,
        )
        btn_ok = ft.IconButton(
            icon=ft.icons.CHECK_CIRCLE_OUTLINE,
            tooltip="Confirmar pago",
            disabled=esta_pagado,
            on_click=lambda e: on_confirmar(id_pago),
            icon_color=ft.colors.GREEN_600 if not esta_pagado else ft.colors.GREY,
        )
        btn_del = ft.IconButton(
            icon=ft.icons.DELETE_OUTLINE,
            tooltip="Eliminar pago",
            icon_color=ft.colors.RED_600,
            on_click=lambda e: on_eliminar(id_pago),
        )
        acciones = ft.Row([btn_desc, btn_prest, btn_ok, btn_del], spacing=6, alignment=ft.MainAxisAlignment.CENTER)

        txt_estado = ft.Text(estado.upper() if estado else "-", weight=ft.FontWeight.BOLD)

        row = ft.DataRow(
            cells=[
                ft.DataCell(_wrap(ft.Text(str(id_pago)), 70)),
                ft.DataCell(_wrap(ft.Text(str(id_empleado)), 90)),
                ft.DataCell(_wrap(ft.Text(nombre, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1), 120)),
                ft.DataCell(_wrap(ft.Text(fecha_pago), 110)),
                ft.DataCell(_wrap(ft.Text(horas), 70)),
                ft.DataCell(_wrap(ft.Text(sueldo_hora), 100)),
                ft.DataCell(_wrap(ft.Text(monto_base), 110)),
                ft.DataCell(_wrap(txt_desc, 120)),
                ft.DataCell(_wrap(txt_prest, 110)),
                ft.DataCell(_wrap(txt_saldo, 100)),
                ft.DataCell(_wrap(txt_dep, 120)),
                ft.DataCell(_wrap(txt_efec, 110)),
                ft.DataCell(_wrap(txt_total, 110)),
                ft.DataCell(_wrap(acciones, 100)),
                ft.DataCell(_wrap(txt_estado, 90)),
            ],
        )

        # Refs para setters
        row.data = {
            "id_pago": id_pago,
            "txt_descuentos": txt_desc,
            "txt_prestamos": txt_prest,
            "txt_saldo": txt_saldo,
            "txt_deposito": txt_dep,
            "txt_efectivo": txt_efec,
            "txt_total": txt_total,
            "txt_estado": txt_estado,
            "btn_confirmar": btn_ok,
            "btn_prest": btn_prest,
            # cache último calc pintado (opcional)
            "_ultimo_calc": {
                "descuentos_view": descuentos_value,
                "prestamos_view": prestamos_value,
                "saldo_ajuste": saldo_value,
                "efectivo": efectivo_value,
                "total_vista": total_value,
            },
            # por si quieres saber si está escribiendo
            "_editing_deposito": False,
            "_pago_row": pago_row,  # para recalcular dentro del on_change
        }

        return row

    # -----------------------------
    # Eventos y validación (sin regex)
    # -----------------------------
    def _on_dep_change(
        self,
        e: ft.ControlEvent,
        pago_row: Dict[str, Any],
        txt_desc: ft.TextField,
        txt_prest: ft.TextField,
        txt_total: ft.TextField,
        txt_efec: ft.TextField,
        txt_saldo: ft.TextField,
        on_deposito_change_cb: Callable[[str], None],
    ) -> None:
        """
        - NO se reescribe el value (escritura continua).
        - Validación suave del texto y borde.
        - Recalcula derivados en vivo usando PaymentViewMath con el texto actual.
        """
        raw = e.control.value or ""
        on_deposito_change_cb(raw)  # buffer externo del contenedor

        # Validación manual sin regex (permite "", ".", "-"; los tratamos como 0 temporalmente)
        dep = self._safe_float(raw)

        # Recalc rápido (solo lectura de modelos si hace falta)
        try:
            calc = self.math.recalc_from_pago_row(
                pago_row,
                deposito_ui=dep,
                key_monto_base=self.key_monto_base,
                key_id_pago=self.key_id_pago,
                aplicar_redondeo_50=self.aplicar_redondeo_50,
            )
        except Exception:
            calc = RowCalcDict(descuentos_view=0.0, prestamos_view=0.0, total_vista=0.0, efectivo=0.0, saldo_ajuste=0.0)

        # Pintar derivados (no tocar el value del depósito)
        txt_desc.value = f"{calc['descuentos_view']:.2f}"
        txt_prest.value = f"{calc['prestamos_view']:.2f}"
        txt_total.value = f"{calc['total_vista']:.2f}"
        txt_efec.value = f"{calc['efectivo']:.2f}"
        txt_saldo.value = f"{calc['saldo_ajuste']:.2f}"

        txt_desc.update()
        txt_prest.update()
        txt_total.update()
        txt_efec.update()
        txt_saldo.update()
        e.control.border_color = ft.colors.RED if dep > calc["total_vista"] + 1e-9 else None
        e.control.update()

        if callable(self.on_after_recalc):
            try:
                self.on_after_recalc(calc)
            except Exception:
                pass

    # -----------------------------
    # Getters / Setters
    # -----------------------------
    def get_row(self, table: ft.DataTable, id_pago_nomina: int) -> Optional[ft.DataRow]:
        for r in table.rows:
            try:
                if getattr(r, "data", None) and r.data.get("id_pago") == id_pago_nomina:
                    return r
            except Exception:
                continue
        return None

    def set_descuentos(self, row: ft.DataRow, value: float) -> None:
        try:
            row.data["txt_descuentos"].value = f"{float(value):.2f}"
            row.data["txt_descuentos"].update()
        except Exception:
            pass

    def set_prestamos(self, row: ft.DataRow, value: float) -> None:
        try:
            row.data["txt_prestamos"].value = f"{float(value):.2f}"
            row.data["txt_prestamos"].update()
        except Exception:
            pass

    def set_saldo(self, row: ft.DataRow, value: float) -> None:
        try:
            row.data["txt_saldo"].value = f"{float(value):.2f}"
            row.data["txt_saldo"].update()
        except Exception:
            pass

    def set_efectivo(self, row: ft.DataRow, value: float) -> None:
        try:
            row.data["txt_efectivo"].value = f"{float(value):.2f}"
            row.data["txt_efectivo"].update()
        except Exception:
            pass

    def set_total(self, row: ft.DataRow, value: float) -> None:
        try:
            row.data["txt_total"].value = f"{float(value):.2f}"
            row.data["txt_total"].update()
        except Exception:
            pass

    def set_deposito_border_color(self, row: ft.DataRow, color: Optional[str]) -> None:
        try:
            dep = row.data["txt_deposito"]
            dep.border_color = color
            dep.update()
        except Exception:
            pass

    def set_estado_pagado(self, row: ft.DataRow) -> None:
        try:
            row.data["txt_estado"].value = "PAGADO"
            row.data["txt_estado"].update()

            if "btn_confirmar" in row.data and isinstance(row.data["btn_confirmar"], ft.IconButton):
                row.data["btn_confirmar"].disabled = True
                row.data["btn_confirmar"].icon_color = ft.colors.GREY
                row.data["btn_confirmar"].update()

            dep = row.data.get("txt_deposito")
            if dep:
                dep.read_only = True
                dep.border_color = None
                dep.update()
        except Exception:
            pass

    # -----------------------------
    # Utils
    # -----------------------------
    @staticmethod
    def _safe_float(texto: Any) -> float:
        """
        Convierte texto a float sin lanzar error:
          - "", ".", "-", "-." -> 0.0 (permite escritura continua)
          - recorta a 2 decimales si trae muchos (sin regex)
        """
        try:
            s = str(texto).strip().replace(",", "")
            if s in ("", ".", "-", "-."):
                return 0.0
            # recorte manual a 2 decimales sin regex
            if "." in s:
                partes = s.split(".")
                enteros = "".join(ch for ch in partes[0] if ch.isdigit() or (ch == "-" and not partes[0].startswith("-")))
                dec = "".join(ch for ch in partes[1] if ch.isdigit())[:2]
                s = f"{enteros}.{dec}" if dec != "" else f"{enteros}."
            else:
                s = "".join(ch for ch in s if ch.isdigit() or ch == "-")
            return float(s) if s not in ("", "-", "-.") else 0.0
        except Exception:
            return 0.0
