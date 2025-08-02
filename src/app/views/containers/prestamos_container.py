import flet as ft
from datetime import datetime
import pandas as pd
from urllib.parse import urlencode

from app.core.app_state import AppState
from app.models.loan_model import LoanModel
from app.models.payment_model import PaymentModel
from app.models.descuento_detalles_model import DescuentoDetallesModel
from app.views.containers.modal_alert import ModalAlert
from app.core.enums.e_prestamos_model import E_PRESTAMOS
from app.core.invokers.file_open_invoker import FileOpenInvoker
from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.helpers.prestamos_helper.prestamos_row_helper import PrestamosRowHelper
from app.helpers.boton_factory import crear_boton_importar, crear_boton_exportar, crear_boton_agregar


class PrestamosContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20)
        self.page = AppState().page
        self.loan_model = LoanModel()
        self.payment_model = PaymentModel()
        self.detalles_model = DescuentoDetallesModel()
        self.E = E_PRESTAMOS

        self.tabla = ft.DataTable(columns=[], rows=[], expand=True)
        self.row_helper = PrestamosRowHelper(actualizar_callback=self._actualizar_vista)

        self.importador = FileOpenInvoker(self.page, self._procesar_importacion, allowed_extensions=["xlsx"])
        self.exportador = FileSaveInvoker(
            self.page, self._procesar_exportacion,
            file_name=f"Exporte_Prestamos_{datetime.today().strftime('%Y-%m-%d')}.xlsx"
        )

        self.layout = ft.Column(expand=True)
        self._build()
        self._actualizar_vista()

    def _build(self):
        self.layout.controls = [
            ft.Text("Área actual: Préstamos", style=ft.TextThemeStyle.TITLE_MEDIUM),
            ft.Row([
                crear_boton_importar(self.importador.open),
                crear_boton_exportar(self.exportador.open_save),
                crear_boton_agregar(self._agregar_nueva_fila)
            ], spacing=15),
            self.tabla
        ]
        self.content = self.layout

    def _actualizar_vista(self):
        resultado = self.loan_model.get_all()
        if resultado["status"] != "success":
            ModalAlert.mostrar_info("Error", resultado["message"])
            return

        self.tabla.columns = [
            ft.DataColumn(ft.Text("ID")),
            ft.DataColumn(ft.Text("Empleado")),
            ft.DataColumn(ft.Text("Monto")),
            ft.DataColumn(ft.Text("Saldo")),
            ft.DataColumn(ft.Text("Pagado")),
            ft.DataColumn(ft.Text("Estado")),
            ft.DataColumn(ft.Text("Fecha Solicitud")),
            ft.DataColumn(ft.Text("Acciones")),
        ]

        self.tabla.rows = []

        for prestamo in resultado["data"]:
            id_pago = self.payment_model.get_pago_id_por_empleado_y_estado(
                numero_nomina=prestamo[self.E.PRESTAMO_NUMERO_NOMINA.value],
                estado="pendiente"
            )

            fila = self.row_helper.build_fila_lectura(
                registro=prestamo,
                on_edit=lambda p=prestamo: self._editar_fila(p),
                on_delete=lambda p=prestamo: self._eliminar_prestamo(p[self.E.PRESTAMO_ID.value]),
                on_pagos=lambda p=prestamo: self._ir_a_pagos(p, id_pago)
            )
            self.tabla.rows.append(fila)

        self.page.update()

    def _editar_fila(self, prestamo):
        if prestamo[self.E.PRESTAMO_ESTADO.value] == "terminado":
            ModalAlert.mostrar_info("No editable", "Este préstamo ya fue terminado.")
            return

        def on_guardar():
            self.loan_model.update_by_id_prestamo(
                prestamo[self.E.PRESTAMO_ID.value],
                prestamo  # El diccionario ya está modificado por los on_change del helper
            )
            ModalAlert.mostrar_info("Éxito", "Préstamo actualizado correctamente.")
            self._actualizar_vista()

        def on_cancelar():
            self._actualizar_vista()

        fila_edicion = self.row_helper.build_fila_edicion(prestamo, on_guardar, on_cancelar)

        for i, fila in enumerate(self.tabla.rows):
            if str(fila.cells[0].content.value) == str(prestamo[self.E.PRESTAMO_ID.value]):
                self.tabla.rows[i] = fila_edicion
                break

        self.page.update()

    def _agregar_nueva_fila(self, _):
        hoy = datetime.today().strftime("%d/%m/%Y")
        nuevo = {
            "numero_nomina": "",
            "monto": "",
            "fecha_solicitud": hoy,
            "saldo": "0.00",
            "pagado": "0.00",
            "estado": "pagando"
        }

        def on_save():
            resultado = self.loan_model.add(
                numero_nomina=int(nuevo["numero_nomina"]),
                monto_prestamo=float(nuevo["monto"]),
                saldo_prestamo=float(nuevo["monto"]),
                estado=nuevo["estado"],
                fecha_solicitud=hoy
            )
            if resultado["status"] == "success":
                ModalAlert.mostrar_info("Éxito", "Préstamo agregado.")
            else:
                ModalAlert.mostrar_info("Error", resultado["message"])
            self._actualizar_vista()

        def on_cancel():
            self._actualizar_vista()

        nueva_fila = self.row_helper.build_fila_nueva(
            registro=nuevo,
            on_save=on_save,
            on_cancel=on_cancel,
            page=self.page,
            scroll_key="prestamos"
        )
        self.tabla.rows.append(nueva_fila)
        self.page.update()

    def _ir_a_pagos(self, prestamo, id_pago):
        params = urlencode({
            "id_prestamo": prestamo[self.E.PRESTAMO_ID.value],
            "id_pago": id_pago
        })
        self.page.go(f"/home/prestamos/pagosprestamos?{params}")

    def _procesar_importacion(self, path):
        try:
            df = pd.read_excel(path)
            nuevos, duplicados = 0, 0
            for _, row in df.iterrows():
                numero = int(row["ID Empleado"])
                monto = float(row["Monto"])
                fecha = str(row["Fecha Solicitud"])

                existe = self.loan_model.db.get_data(
                    f"SELECT COUNT(*) AS c FROM {self.E.TABLE.value} WHERE {self.E.PRESTAMO_NUMERO_NOMINA.value} = %s AND {self.E.PRESTAMO_FECHA_SOLICITUD.value} = %s",
                    (numero, fecha), dictionary=True
                )
                if existe.get("c", 0) > 0:
                    duplicados += 1
                    continue

                self.loan_model.add(numero, monto, monto, "pagando", fecha)
                nuevos += 1

            mensaje = f"Importados: {nuevos}"
            if duplicados:
                mensaje += f" | Duplicados ignorados: {duplicados}"
            ModalAlert.mostrar_info("Importación completada", mensaje)
            self._actualizar_vista()
        except Exception as e:
            ModalAlert.mostrar_info("Error", f"Falló la importación: {e}")

    def _procesar_exportacion(self, path):
        try:
            resultado = self.loan_model.get_all()
            if resultado["status"] != "success":
                ModalAlert.mostrar_info("Error", resultado["message"])
                return

            prestamos = resultado["data"]
            if not prestamos:
                ModalAlert.mostrar_info("Sin datos", "No hay préstamos para exportar.")
                return

            columnas = [
                (self.E.PRESTAMO_ID.value, "ID"),
                (self.E.PRESTAMO_NUMERO_NOMINA.value, "ID Empleado"),
                (self.E.PRESTAMO_MONTO.value, "Monto"),
                (self.E.PRESTAMO_SALDO.value, "Saldo"),
                (self.E.PRESTAMO_ESTADO.value, "Estado"),
                (self.E.PRESTAMO_FECHA_SOLICITUD.value, "Fecha")
            ]

            datos = []
            for p in prestamos:
                fila = []
                for clave, _ in columnas:
                    val = p.get(clave)
                    if isinstance(val, (datetime, pd.Timestamp)):
                        fila.append(val.strftime("%Y-%m-%d"))
                    else:
                        fila.append(str(val) if val is not None else "")
                datos.append(fila)

            df = pd.DataFrame(datos, columns=[t for _, t in columnas])
            df.to_excel(path, index=False)
            ModalAlert.mostrar_info("Éxito", f"Exportado correctamente a: {path}")
        except Exception as e:
            ModalAlert.mostrar_info("Error", f"Falló la exportación: {e}")

    def _eliminar_prestamo(self, id_prestamo):
        resultado = self.loan_model.delete_by_id_prestamo(id_prestamo)
        if resultado["status"] == "success":
            ModalAlert.mostrar_info("Eliminado", "El préstamo fue eliminado correctamente.")
        else:
            ModalAlert.mostrar_info("Error", resultado["message"])
        self._actualizar_vista()

