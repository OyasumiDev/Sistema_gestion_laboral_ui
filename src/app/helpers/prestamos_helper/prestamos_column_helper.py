import flet as ft
from app.core.enums.e_prestamos_model import E_PRESTAMOS as E


class PrestamosColumnHelper:
    """
    Columnas estándar para tablas de préstamos.
    - `get_columnas()` es alias de `construir_columnas_tabla()` para compatibilidad.
    - `include_grupo`: para mostrar/ocultar la columna de grupo/empleado.
    - `include_acciones`: para mostrar/ocultar la columna de acciones.
    """

    @staticmethod
    def get_columnas(include_grupo: bool = True, include_acciones: bool = True) -> list[ft.DataColumn]:
        return PrestamosColumnHelper.construir_columnas_tabla(include_grupo, include_acciones)

    @staticmethod
    def construir_columnas_tabla(
        include_grupo: bool = True,
        include_acciones: bool = True,
    ) -> list[ft.DataColumn]:
        cols: list[ft.DataColumn] = [
            ft.DataColumn(ft.Text("ID"), numeric=True, tooltip="ID del préstamo"),
            ft.DataColumn(ft.Text("Empleado"), tooltip="Nombre del empleado"),
            ft.DataColumn(ft.Text("Monto"), numeric=True, tooltip="Monto del préstamo"),
            ft.DataColumn(ft.Text("Saldo"), numeric=True, tooltip="Saldo pendiente"),
            ft.DataColumn(ft.Text("Dinero Pagado"), numeric=True, tooltip="Total pagado"),
            ft.DataColumn(ft.Text("Estado"), tooltip="Estado del préstamo"),
            ft.DataColumn(ft.Text("Fecha Solicitud"), tooltip="Fecha en DD/MM/YYYY"),
        ]

        if include_grupo:
            # Inserta “Grupo” después de Estado (ajusta si prefieres otra posición)
            cols.insert(6, ft.DataColumn(ft.Text("Grupo"), tooltip="Grupo del empleado"))

        if include_acciones:
            cols.append(ft.DataColumn(ft.Text("Acciones"), tooltip="Editar / Eliminar / Pagos"))

        return cols

    @staticmethod
    def construir_columnas_exportacion() -> list[tuple]:
        """
        Devuelve [(clave_interna, nombre_visible), ...] para exportar a Excel/CSV.
        Incluye 'Dinero Pagado' si existe en el enum (PRESTAMO_PAGADO).
        """
        columnas = [
            (E.PRESTAMO_ID.value, "ID Préstamo"),
            (E.PRESTAMO_NUMERO_NOMINA.value, "ID Empleado"),
            (E.PRESTAMO_MONTO.value, "Monto"),
            (E.PRESTAMO_SALDO.value, "Saldo Actual"),
            (E.PRESTAMO_ESTADO.value, "Estado"),
            (E.PRESTAMO_FECHA_SOLICITUD.value, "Fecha Solicitud"),
        ]

        # Si tu enum define PRESTAMO_PAGADO lo incluimos.
        miembro_pagado = getattr(E, "PRESTAMO_PAGADO", None)
        if miembro_pagado is not None:
            # lo ponemos después de Saldo
            columnas.insert(4, (miembro_pagado.value, "Dinero Pagado"))

        # Si tu enum define PRESTAMO_GRUPO_EMPLEADO también lo agregamos
        miembro_grupo = getattr(E, "PRESTAMO_GRUPO_EMPLEADO", None)
        if miembro_grupo is not None:
            columnas.append((miembro_grupo.value, "Grupo Empleado"))

        return columnas
