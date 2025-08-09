import flet as ft
from typing import Callable, Optional, List
from app.core.enums.e_pagos_prestamos import E_PAGOS_PRESTAMO as E
from app.helpers.boton_factory import crear_boton_editar, crear_boton_eliminar


# --------------------- Columnas (homogeneizadas) ---------------------

class PagosPrestamosColumnHelper:
    """
    Columnas estándar para la DataTable de pagos de préstamos.
    - `get_columnas()` es alias de `construir_columnas_tabla()` para compatibilidad.
    - `include_acciones`: mostrar/ocultar columna de acciones.
    """

    @staticmethod
    def get_columnas(include_acciones: bool = True) -> List[ft.DataColumn]:
        return PagosPrestamosColumnHelper.construir_columnas_tabla(include_acciones=include_acciones)

    @staticmethod
    def construir_columnas_tabla(include_acciones: bool = True) -> List[ft.DataColumn]:
        cols: List[ft.DataColumn] = [
            ft.DataColumn(ft.Text("ID"), numeric=True, tooltip="ID del pago"),
            ft.DataColumn(ft.Text("Fecha programada"), tooltip="Fecha programada (DD/MM/YYYY)"),
            ft.DataColumn(ft.Text("Fecha real"), tooltip="Fecha real (DD/MM/YYYY)"),
            ft.DataColumn(ft.Text("Pagado"), numeric=True, tooltip="Monto pagado"),
            ft.DataColumn(ft.Text("Saldo restante"), numeric=True, tooltip="Saldo restante después del pago"),
            ft.DataColumn(ft.Text("Saldo + interés"), numeric=True, tooltip="Saldo restante más interés aplicado"),
            ft.DataColumn(ft.Text("Interés (%)"), numeric=True, tooltip="Porcentaje de interés aplicado"),
            ft.DataColumn(ft.Text("Observaciones"), tooltip="Notas u observaciones del pago"),
        ]
        if include_acciones:
            cols.append(ft.DataColumn(ft.Text("Acciones"), tooltip="Editar / Eliminar"))
        return cols


# --------------------- Filas (UI de pagos) ---------------------

class PagosPrestamosRowHelper:
    def build_fila_pago(
        self,
        pago: dict,
        editable: bool,
        on_edit: Optional[Callable] = None,
        on_delete: Optional[Callable] = None,
    ) -> ft.DataRow:
        """
        Construye una fila visual para un pago de préstamo.
        Si `editable` es True, se muestran botones de editar y/o eliminar.
        """

        def _to_float(v, default=0.0) -> float:
            try:
                return float(v)
            except Exception:
                return float(default)

        def _to_text(v, default="-") -> str:
            return str(v) if (v is not None and v != "") else default

        # Parseo con fallback
        try:
            pago_id = pago.get(E.ID_PAGO_PRESTAMO.value, "-")
            fecha_gen = pago.get(E.PAGO_FECHA_PAGO.value, "-")
            fecha_real = pago.get(E.PAGO_FECHA_REAL.value, "-")
            monto_pagado = _to_float(pago.get(E.PAGO_MONTO_PAGADO.value, 0))
            interes_aplicado = _to_float(pago.get(E.PAGO_INTERES_APLICADO.value, 0))
            interes_porcentaje = _to_text(pago.get(E.PAGO_INTERES_PORCENTAJE.value, "0"))
            saldo_restante = _to_float(pago.get(E.PAGO_SALDO_RESTANTE.value, 0))
            observaciones = _to_text(pago.get(E.PAGO_OBSERVACIONES.value, ""))
            saldo_con_interes = saldo_restante + interes_aplicado
        except Exception as ex:
            print(f"❌ Error al construir fila de pago: {ex}")
            pago_id = "-"
            fecha_gen = fecha_real = "-"
            monto_pagado = 0.0
            interes_aplicado = 0.0
            interes_porcentaje = "0"
            saldo_restante = 0.0
            saldo_con_interes = 0.0
            observaciones = "-"

        # Acciones
        acciones: List[ft.Control] = []
        if editable:
            if on_edit:
                acciones.append(crear_boton_editar(lambda e: on_edit(pago)))
            if on_delete:
                acciones.append(crear_boton_eliminar(lambda e: on_delete(pago)))

        return ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(str(pago_id))),
                ft.DataCell(ft.Text(_to_text(fecha_gen))),
                ft.DataCell(ft.Text(_to_text(fecha_real))),
                ft.DataCell(ft.Text(f"${monto_pagado:.2f}")),
                ft.DataCell(ft.Text(f"${saldo_restante:.2f}")),
                ft.DataCell(ft.Text(f"${saldo_con_interes:.2f}")),
                ft.DataCell(ft.Text(f"{interes_porcentaje}%")),
                ft.DataCell(ft.Text(_to_text(observaciones))),
                ft.DataCell(ft.Row(acciones, spacing=5)),
            ]
        )

    # Back-compat con tu contenedor actual
    def get_columnas(self) -> List[ft.DataColumn]:
        return PagosPrestamosColumnHelper.get_columnas(include_acciones=True)
