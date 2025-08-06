import flet as ft
from app.core.enums.e_prestamos_model import E_PRESTAMOS as E


class PrestamosColumnHelper:
    @staticmethod
    def construir_columnas_tabla() -> list[ft.DataColumn]:
        return [
            ft.DataColumn(ft.Text("ID")),
            ft.DataColumn(ft.Text("Empleado")),
            ft.DataColumn(ft.Text("Monto")),
            ft.DataColumn(ft.Text("Saldo")),
            ft.DataColumn(ft.Text("Dinero Pagado")),
            ft.DataColumn(ft.Text("Estado")),
            ft.DataColumn(ft.Text("Fecha Solicitud")),
            ft.DataColumn(ft.Text("Acciones")),
        ]

    @staticmethod
    def construir_columnas_exportacion() -> list[tuple]:
        """
        Devuelve las columnas requeridas para exportación a Excel,
        con sus claves internas y nombres visibles.
        """
        return [
            (E.PRESTAMO_ID.value, "ID Préstamo"),
            (E.PRESTAMO_NUMERO_NOMINA.value, "ID Empleado"),
            (E.PRESTAMO_MONTO.value, "Monto"),
            (E.PRESTAMO_SALDO.value, "Saldo Actual"),
            (E.PRESTAMO_ESTADO.value, "Estado"),
            (E.PRESTAMO_FECHA_SOLICITUD.value, "Fecha Solicitud")
        ]
