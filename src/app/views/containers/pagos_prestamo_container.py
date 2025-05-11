from datetime import datetime
import pandas as pd
import flet as ft
from urllib.parse import urlparse, parse_qs
from decimal import Decimal

from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert
from app.models.loan_payment_model import LoanPaymentModel
from app.models.loan_model import LoanModel
from app.core.invokers.file_open_invoker import FileOpenInvoker
from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.core.enums.e_loan_payment_model import E_LOAN_PAYMENT
from app.core.enums.e_loan_model import E_LOAN


class PagosPrestamoContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20)
        self.page = AppState().page
        self.pago_model = LoanPaymentModel()
        self.prestamo_model = LoanModel()
        self.tabla_pagos = ft.DataTable(columns=[], rows=[], expand=True)

        self.orden_actual = "id_pago_prestamo"
        self.orden_desc = False
        self.interes_fijo = 10.0

        self.fila_resumen = None
        self.fila_nueva = None

        self.importador = FileOpenInvoker(
            page=self.page,
            on_select=self._procesar_importacion,
            allowed_extensions=["xlsx"]
        )
        self.exportador = FileSaveInvoker(
            page=self.page,
            on_save=self._guardar_exportacion,
            save_dialog_title="Guardar pagos en Excel",
            file_name="pagos_prestamo.xlsx",
            allowed_extensions=["xlsx"]
        )

        self.boton_agregar = self._boton_estilizado("Agregar", ft.icons.ADD, self._agregar_fila_pago)

        self.layout = ft.Column(
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[]
        )
        self.content = self.layout

        self.did_mount()
        
    def _boton_estilizado(self, texto, icono, handler):
        return ft.ElevatedButton(
            icon=ft.Icon(icono),
            text=texto,
            on_click=handler,
            style=ft.ButtonStyle(
                padding=ft.padding.all(10),
                shape=ft.RoundedRectangleBorder(radius=8)
            )
        )

    def _volver(self, e=None):
        ruta = "/prestamos"
        if self.id_empleado and self.id_empleado.isdigit():
            ruta += f"?id_empleado={self.id_empleado}"
        self.page.go(ruta)

    def did_mount(self):
        parsed = urlparse(self.page.route)
        query_params = parse_qs(parsed.query)
        self.id_prestamo = query_params.get("id_prestamo", [None])[0]
        self.id_empleado = query_params.get("id_empleado", [None])[0]

        self._build()
        if self.id_prestamo and self.id_prestamo.isdigit():
            self._cargar_pagos(int(self.id_prestamo))
        else:
            ModalAlert.mostrar_info("Error", "ID de préstamo no válido o faltante.")

    def _crear_fila_resumen(self, total_pagado, saldo_recalculado):
        return ft.DataRow(cells=[
            ft.DataCell(ft.Text("")),
            ft.DataCell(ft.Text("")),
            ft.DataCell(ft.Text("Total pagado:", weight=ft.FontWeight.BOLD)),
            ft.DataCell(ft.Text(f"${total_pagado:.2f}", weight=ft.FontWeight.BOLD)),
            ft.DataCell(ft.Text("")),
            ft.DataCell(ft.Text(f"${saldo_recalculado:.2f}", weight=ft.FontWeight.BOLD)),
            ft.DataCell(ft.Text("")),
            ft.DataCell(ft.Text("")),
            ft.DataCell(ft.Text(""))
        ])

    def _crear_fila_nueva(self, monto_total, saldo_actual):
        hoy = datetime.today().strftime("%Y-%m-%d")
        nuevo_id = str(self.pago_model.get_next_id())

        interes_selector = ft.Dropdown(
            label="Interés %",
            value=str(self.interes_fijo),
            options=[
                ft.dropdown.Option("0.0"),
                ft.dropdown.Option("5.0"),
                ft.dropdown.Option("10.0"),
                ft.dropdown.Option("15.0")
            ]
        )

        monto_input = ft.TextField(label="Monto a Pagar", value="")
        saldo_sin_interes = Decimal(str(saldo_actual))
        saldo_text = ft.Text(value=f"${saldo_sin_interes:.2f}")
        saldo_nuevo_text = ft.Text(value="")

        def actualizar_saldo_con_interes(e):
            try:
                interes = float(interes_selector.value)
                nuevo_saldo = saldo_sin_interes + (saldo_sin_interes * Decimal(str(interes)) / 100)
                saldo_nuevo_text.value = f"${nuevo_saldo:.2f}"
                self.interes_fijo = interes
                self.page.update()
            except Exception:
                saldo_nuevo_text.value = f"${saldo_sin_interes:.2f}"

        interes_selector.on_change = actualizar_saldo_con_interes
        actualizar_saldo_con_interes(None)

        def confirmar_pago():
            try:
                interes = float(interes_selector.value)
                monto = float(monto_input.value)
                if monto <= 0:
                    raise ValueError("Monto no válido")

                saldo_con_interes = saldo_sin_interes + (saldo_sin_interes * Decimal(str(interes)) / 100)
                nuevo_saldo = saldo_con_interes - Decimal(str(monto))

                if nuevo_saldo < 0:
                    ModalAlert.mostrar_info("Error", "El monto es mayor al saldo total con intereses.")
                    return
            except Exception:
                ModalAlert.mostrar_info("Error", "Debe ingresar un monto válido.")
                return

            resultado = self.pago_model.add_payment(
                int(self.id_prestamo),
                monto,
                hoy,
                hoy,
                interes
            )
            ModalAlert.mostrar_info("Resultado", resultado["message"])
            self._cargar_pagos(int(self.id_prestamo))

        return ft.DataRow(cells=[
            ft.DataCell(ft.Text(nuevo_id)),
            ft.DataCell(ft.Text(hoy)),
            ft.DataCell(ft.Text(hoy)),
            ft.DataCell(monto_input),
            ft.DataCell(ft.Text(f"${monto_total:.2f}")),
            ft.DataCell(saldo_text),
            ft.DataCell(saldo_nuevo_text),
            ft.DataCell(interes_selector),
            ft.DataCell(ft.Row([
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, on_click=lambda _: confirmar_pago()),
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600, on_click=lambda _: self._cargar_pagos(int(self.id_prestamo)))
            ]))
        ])


    def _build(self):
        botones = ft.Row([
            self._boton_estilizado("Regresar", ft.icons.ARROW_BACK, self._volver),
            self.importador.get_open_button("Importar Pagos"),
            self.exportador.get_save_button("Exportar Pagos"),
            self.boton_agregar
        ], spacing=15)

        self.layout.controls = [
            ft.Text("PAGOS DEL PRÉSTAMO", style=ft.TextThemeStyle.TITLE_MEDIUM),
            botones,
            self.tabla_pagos
        ]

    def _cargar_pagos(self, id_prestamo):
        self.tabla_pagos.rows.clear()

        resultado = self.pago_model.get_by_prestamo(id_prestamo)
        if resultado["status"] != "success":
            ModalAlert.mostrar_info("Error", resultado["message"])
            return

        datos = resultado["data"]
        datos = sorted(datos, key=lambda p: p.get(self.orden_actual, 0), reverse=self.orden_desc)

        prestamo_info = self.prestamo_model.get_by_id(id_prestamo)
        if prestamo_info["status"] != "success":
            ModalAlert.mostrar_info("Error", prestamo_info["message"])
            return

        info = prestamo_info["data"]
        monto_total = float(info[E_LOAN.PRESTAMO_MONTO.value])
        saldo_actual = Decimal(str(monto_total))
        total_pagado = 0

        self.tabla_pagos.columns = [
            ft.DataColumn(label=ft.Text("ID Pago")),
            ft.DataColumn(label=ft.Text("Fecha Generada")),
            ft.DataColumn(label=ft.Text("Fecha Pagada")),
            ft.DataColumn(label=ft.Text("Monto Pagado")),
            ft.DataColumn(label=ft.Text("Monto Original")),
            ft.DataColumn(label=ft.Text("Saldo Actual")),
            ft.DataColumn(label=ft.Text("Interés %")),
            ft.DataColumn(label=ft.Text("Días de Retraso")),
            ft.DataColumn(label=ft.Text("Acciones"))
        ]

        for p in datos:
            monto_pagado = Decimal(str(p["monto_pagado"]))
            interes_pct = Decimal(str(p["interes_aplicado"]))
            saldo_actual -= monto_pagado
            saldo_actual += round(saldo_actual * (interes_pct / 100), 2)
            total_pagado += float(monto_pagado)

            self.tabla_pagos.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(p["id_pago_prestamo"])),
                ft.DataCell(ft.Text(p["fecha_generacion"])),
                ft.DataCell(ft.Text(p["fecha_pago"])),
                ft.DataCell(ft.Text(f"${monto_pagado:.2f}")),
                ft.DataCell(ft.Text(f"${monto_total:.2f}")),
                ft.DataCell(ft.Text(f"${max(saldo_actual, 0):.2f}")),
                ft.DataCell(ft.Text(f"{interes_pct:.1f}%")),
                ft.DataCell(ft.Text(str(p["dias_retraso"]))),
                ft.DataCell(self._build_acciones_cell(p))
            ]))

        self.boton_agregar.disabled = saldo_actual <= 0

        if saldo_actual > 0:
            self.fila_nueva = self._crear_fila_nueva(monto_total, float(saldo_actual))
            self.tabla_pagos.rows.append(self.fila_nueva)

        self.fila_resumen = self._crear_fila_resumen(total_pagado, saldo_actual)
        self.tabla_pagos.rows.append(self.fila_resumen)
        self.page.update()


    def _build_acciones_cell(self, pago):
        return ft.Row([
            ft.IconButton(icon=ft.icons.EDIT, tooltip="Editar", on_click=lambda _: self._editar_pago(pago)),
            ft.IconButton(icon=ft.icons.DELETE, tooltip="Eliminar", on_click=lambda _: self._eliminar_pago(pago["id_pago_prestamo"]))
        ])

    def _ordenar_por_columna(self, nombre_columna):
        try:
            if self.orden_actual == nombre_columna:
                self.orden_desc = not self.orden_desc
            else:
                self.orden_actual = nombre_columna
                self.orden_desc = False
            self._cargar_pagos(int(self.id_prestamo))
        except Exception as e:
            print(f"⚠️ Error al ordenar: {e}")

    def _editar_pago(self, pago):
        ModalAlert.mostrar_info("Editar", "Los pagos no pueden ser editados una vez registrados.")

    def _eliminar_pago(self, id_pago):
        resultado = self.pago_model.delete_by_id_pago(id_pago)
        ModalAlert.mostrar_info("Resultado", resultado["message"])
        self._cargar_pagos(int(self.id_prestamo))

    def _agregar_fila_pago(self, e=None):
        prestamo_info = self.prestamo_model.get_by_id(int(self.id_prestamo))
        if prestamo_info["status"] != "success":
            ModalAlert.mostrar_info("Error", prestamo_info["message"])
            return

        datos = prestamo_info["data"]
        monto_total = float(datos[E_LOAN.PRESTAMO_MONTO.value])
        saldo = float(datos[E_LOAN.PRESTAMO_SALDO.value])

        if self.fila_resumen and self.fila_resumen in self.tabla_pagos.rows:
            self.tabla_pagos.rows.remove(self.fila_resumen)
        if self.fila_nueva and self.fila_nueva in self.tabla_pagos.rows:
            self.tabla_pagos.rows.remove(self.fila_nueva)

        self.fila_nueva = self._crear_fila_nueva(monto_total, saldo)
        self.tabla_pagos.rows.append(self.fila_nueva)
        self.tabla_pagos.rows.append(self.fila_resumen)
        self.page.update()

    def _procesar_importacion(self, path):
        try:
            df = pd.read_excel(path)
            for _, row in df.iterrows():
                monto = float(row.get(E_LOAN_PAYMENT.PAGO_MONTO_PAGADO.value, 0))
                fecha_pago = str(row.get(E_LOAN_PAYMENT.PAGO_FECHA_PAGO.value, datetime.today().strftime("%Y-%m-%d")))
                fecha_generacion = str(row.get(E_LOAN_PAYMENT.PAGO_FECHA_GENERACION.value, datetime.today().strftime("%Y-%m-%d")))
                interes = float(row.get(E_LOAN_PAYMENT.PAGO_INTERES_APLICADO.value, self.interes_fijo))

                self.pago_model.add_payment(
                    int(self.id_prestamo),
                    monto,
                    fecha_pago,
                    fecha_generacion,
                    interes
                )
            ModalAlert.mostrar_info("Éxito", "Pagos importados correctamente.")
            self._cargar_pagos(int(self.id_prestamo))
        except Exception as ex:
            ModalAlert.mostrar_info("Error", str(ex))

    def _guardar_exportacion(self, path):
        resultado = self.pago_model.get_by_prestamo(int(self.id_prestamo))
        if resultado["status"] != "success":
            ModalAlert.mostrar_info("Error", resultado["message"])
            return
        try:
            df = pd.DataFrame(resultado["data"])
            df[E_LOAN_PAYMENT.PAGO_FECHA_PAGO.value] = pd.to_datetime(df[E_LOAN_PAYMENT.PAGO_FECHA_PAGO.value]).dt.strftime("%Y-%m-%d")
            df[E_LOAN_PAYMENT.PAGO_FECHA_GENERACION.value] = pd.to_datetime(df[E_LOAN_PAYMENT.PAGO_FECHA_GENERACION.value]).dt.strftime("%Y-%m-%d")
            df.to_excel(path, index=False)
            ModalAlert.mostrar_info("Exportado", f"Archivo guardado en {path}")
        except Exception as ex:
            ModalAlert.mostrar_info("Error", str(ex))
