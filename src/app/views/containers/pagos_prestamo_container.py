from datetime import datetime
from decimal import Decimal
from urllib.parse import urlparse, parse_qs
import flet as ft
import os
from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert
from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.core.enums.e_loan_payment_model import E_PAGOS_PRESTAMO
from app.core.enums.e_prestamos_model import E_PRESTAMOS
import pandas as pd
from app.core.invokers.file_open_invoker import FileOpenInvoker
from app.core.invokers.file_save_invoker import FileSaveInvoker


class PagosPrestamoContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20)
        self.page = AppState().page
        self.pago_model = LoanPaymentModel()
        self.prestamo_model = LoanModel()
        self.E = E_PAGOS_PRESTAMO
        self.P = E_PRESTAMOS
        self.tabla_pagos = ft.DataTable(columns=[], rows=[], expand=True)

        self.id_prestamo = None
        self.fila_nueva = None
        self.resumen = ft.Text(value="", size=14, weight="bold", text_align=ft.TextAlign.CENTER)

        self.importador = FileOpenInvoker(
            page=self.page,
            on_select=self._procesar_importacion,
            allowed_extensions=["xlsx"]
        )

        fecha_actual = datetime.today().strftime("%Y-%m-%d")
        self.exportador = FileSaveInvoker(
            page=self.page,
            on_save=self._exportar_pagos,
            save_dialog_title="Exportar pagos del préstamo",
            file_name=f"Pagos_Prestamo_Fecha_{fecha_actual}_Exportados.xlsx",
            allowed_extensions=["xlsx"]
        )

        self.boton_regresar = self._boton_estilizado("Regresar", ft.icons.ARROW_BACK, self._volver)
        self.boton_importar = self._boton_estilizado(
            "Importar", ft.icons.FILE_UPLOAD, lambda _: self.importador.open()
        )

        self.boton_exportar = self._boton_estilizado(
            "Exportar", ft.icons.FILE_DOWNLOAD, lambda _: self.exportador.open_save()
        )

        self.boton_agregar = self._boton_estilizado("Agregar", ft.icons.ADD, self._agregar_fila_pago)

        self.layout = ft.Column(expand=True, controls=[])
        self.content = ft.Container(
            expand=True,
            alignment=ft.alignment.top_center,
            content=ft.Column([
                ft.Container(
                    alignment=ft.alignment.top_center,
                    content=ft.Row([
                        ft.Container(
                            content=ft.Column(
                                controls=[self.layout],
                                alignment=ft.MainAxisAlignment.START,
                                scroll=ft.ScrollMode.ADAPTIVE
                            ),
                            expand=True
                        )
                    ], scroll=ft.ScrollMode.ALWAYS, expand=True)
                )
            ])
        )




        self.did_mount()

    def _boton_estilizado(self, texto, icono, evento):
        return ft.ElevatedButton(
            text=texto,
            icon=ft.Icon(icono),
            on_click=evento,
            style=ft.ButtonStyle(padding=10, shape=ft.RoundedRectangleBorder(radius=6))
        )

    def did_mount(self):
        query = urlparse(self.page.route).query
        params = parse_qs(query)
        self.id_prestamo = int(params.get("id_prestamo", [0])[0])
        self._cargar_pagos(self.id_prestamo)

    def _cargar_pagos(self, id_prestamo: int):
        self.tabla_pagos.columns = [
            ft.DataColumn(label=ft.Container(ft.Text("ID Pago"), width=80)),
            ft.DataColumn(label=ft.Container(ft.Text("Fecha Gen."), width=100)),
            ft.DataColumn(label=ft.Container(ft.Text("Fecha Real"), width=100)),
            ft.DataColumn(label=ft.Container(ft.Text("Monto Pagado"), width=120)),
            ft.DataColumn(label=ft.Container(ft.Text("Monto Original"), width=120)),
            ft.DataColumn(label=ft.Container(ft.Text("Saldo Actual"), width=120)),
            ft.DataColumn(label=ft.Container(ft.Text("Saldo + Interés"), width=130)),
            ft.DataColumn(label=ft.Container(ft.Text("Interés %"), width=90)),
            ft.DataColumn(label=ft.Container(ft.Text("Observaciones"), width=300)),
            ft.DataColumn(label=ft.Container(ft.Text("Acciones"), width=100)),
        ]

        datos_prestamo = self.pago_model.get_saldo_y_monto_prestamo(id_prestamo)
        if not datos_prestamo:
            ModalAlert.mostrar_info("Error", "Préstamo no encontrado.")
            return

        resultado = self.pago_model.get_by_prestamo(id_prestamo)
        if resultado["status"] != "success":
            ModalAlert.mostrar_info("Error", resultado["message"])
            return

        total_pagado = self.pago_model.get_total_pagado_por_prestamo(id_prestamo)
        saldo_restante = float(datos_prestamo["saldo_prestamo"])
        self.tabla_pagos.rows.clear()

        for p in resultado["data"]:
            interes_aplicado = float(p[self.E.PAGO_INTERES_APLICADO.value])
            monto_pagado = float(p[self.E.PAGO_MONTO_PAGADO.value])
            saldo_actual = float(p[self.E.PAGO_SALDO_RESTANTE.value])
            saldo_con_interes = saldo_actual + interes_aplicado

            self.tabla_pagos.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(p[self.E.PAGO_ID.value])),
                ft.DataCell(ft.Text(p[self.E.PAGO_FECHA_PAGO.value])),
                ft.DataCell(ft.Text(p[self.E.PAGO_FECHA_REAL.value])),
                ft.DataCell(ft.Text(f"${monto_pagado:.2f}")),
                ft.DataCell(ft.Text(f"${datos_prestamo['monto_prestamo']:.2f}")),
                ft.DataCell(ft.Text(f"${saldo_actual:.2f}")),
                ft.DataCell(ft.Text(f"${saldo_con_interes:.2f}")),
                ft.DataCell(ft.Text(f"{p[self.E.PAGO_INTERES_PORCENTAJE.value]}%")),
                ft.DataCell(ft.Text(p.get(self.E.PAGO_OBSERVACIONES.value, "") or "")),
                ft.DataCell(ft.IconButton(
                    icon=ft.icons.DELETE,
                    icon_color=ft.colors.RED,
                    tooltip="Eliminar pago",
                    on_click=lambda e, pid=p[self.E.PAGO_ID.value]: self._eliminar_pago(pid)
                ))
            ]))

        self.resumen.value = f"💰 Total pagado: ${total_pagado:.2f} | 💸 Saldo restante: ${saldo_restante:.2f}"

        self.layout.controls = [
            ft.Row([
                ft.Container(
                    content=ft.Text(f"PRÉSTAMO DEL EMPLEADO #{self.id_prestamo}",
                                    style=ft.TextThemeStyle.TITLE_LARGE,
                                    text_align=ft.TextAlign.CENTER), expand=True
                )
            ]),
            ft.Row([
                self.boton_importar,
                self.boton_exportar,
                self.boton_agregar,
                self.boton_regresar
            ], alignment=ft.MainAxisAlignment.START),
            ft.Row([self.tabla_pagos], alignment=ft.MainAxisAlignment.CENTER),
            self.resumen
        ]
        self.page.update()



    def _crear_fila_nueva(self, monto_total, saldo_actual):
        hoy = datetime.today().strftime("%Y-%m-%d")
        nuevo_id = str(self.pago_model.get_next_id())

        interes_selector = ft.Dropdown(
            label="Interés %",
            value="10",
            options=[ft.dropdown.Option("5"), ft.dropdown.Option("10"), ft.dropdown.Option("15")],
            width=80
        )

        monto_input = ft.TextField(
            label="Monto",
            value="",
            text_align=ft.TextAlign.RIGHT,
            max_length=8,
            width=120,
            multiline=False
        )

        observaciones_input = ft.TextField(
            label="Observaciones",
            value="",
            multiline=True,
            min_lines=3,
            max_lines=6,
            width=300,
            height=100,
            autofocus=False,
            expand=False
        )

        # Declarar botón desactivado inicialmente (será habilitado al validar)
        boton_guardar = ft.IconButton(
            icon=ft.icons.CHECK,
            icon_color=ft.colors.GREEN_600,
            disabled=True,  # ⛔ Desactivado por defecto
            on_click=lambda _: confirmar_pago()
        )


        saldo_con_interes_text = ft.Text(value="-", width=100)
        saldo_actual_decimal = Decimal(str(saldo_actual))
        total_pagado_base = Decimal(str(self.pago_model.get_total_pagado_por_prestamo(self.id_prestamo)))

        def actualizar_interes(e=None):
            try:
                interes = int(interes_selector.value)
                monto_ingresado = Decimal(monto_input.value.strip() or "0")
                interes_aplicado = saldo_actual_decimal * Decimal(interes) / 100
                saldo_con_interes = saldo_actual_decimal + interes_aplicado

                saldo_con_interes_text.value = f"${saldo_con_interes:.2f}"
                total_temporal = total_pagado_base + monto_ingresado
                self.resumen.value = f"💰 Total pagado: ${total_temporal:.2f} | 💸 Saldo restante: ${(saldo_con_interes - monto_ingresado):.2f}"

                if monto_ingresado > saldo_con_interes:
                    monto_input.border_color = ft.colors.RED
                    boton_guardar.disabled = True
                else:
                    monto_input.border_color = None
                    boton_guardar.disabled = False
            except:
                saldo_con_interes_text.value = "-"
                boton_guardar.disabled = True
            self.page.update()

        interes_selector.on_change = actualizar_interes

        def validar_monto_tiempo_real(e=None):
            actualizar_interes()

        monto_input.on_change = validar_monto_tiempo_real
        actualizar_interes()

        def confirmar_pago():
            try:
                prestamo = self.prestamo_model.get_by_id(self.id_prestamo)
                if not prestamo:
                    ModalAlert.mostrar_info("Error", "Este ID de préstamo no existe.")
                    return

                monto_str = monto_input.value.strip()
                if not monto_str.isdigit():
                    monto_input.border_color = ft.colors.RED
                    raise ValueError("El monto debe ser un número entero positivo.")
                monto = int(monto_str)
                if monto <= 0:
                    monto_input.border_color = ft.colors.RED
                    raise ValueError("El monto debe ser mayor a cero.")

                observaciones = observaciones_input.value.strip()
                if len(observaciones) > 100:
                    observaciones_input.border_color = ft.colors.RED
                    raise ValueError("Observaciones demasiado largas (máx. 100 caracteres).")

                interes = int(interes_selector.value)

                resultado = self.pago_model.add_payment(
                    id_prestamo=int(self.id_prestamo),
                    id_pago_nomina=int(self.id_prestamo),  # <-- Asumiendo que id_prestamo también es el id del pago de nómina (ajusta si no es así)
                    monto_pagado=monto,
                    fecha_pago=hoy,
                    fecha_generacion=hoy,
                    interes_porcentaje=interes,
                    fecha_real_pago=hoy,
                    observaciones=observaciones
                )


                ModalAlert.mostrar_info("Resultado", resultado["message"])
                self._cargar_pagos(int(self.id_prestamo))

            except Exception as ex:
                ModalAlert.mostrar_info("Error", str(ex))
            self.page.update()

        return ft.DataRow(cells=[
            ft.DataCell(ft.Text(nuevo_id)),
            ft.DataCell(ft.Text(hoy)),
            ft.DataCell(ft.Text(hoy)),
            ft.DataCell(monto_input),
            ft.DataCell(ft.Text(f"${monto_total:.2f}")),
            ft.DataCell(ft.Text(f"${saldo_actual:.2f}")),
            ft.DataCell(saldo_con_interes_text),
            ft.DataCell(interes_selector),
            ft.DataCell(observaciones_input),
            ft.DataCell(ft.Row([
                boton_guardar,
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600,
                            on_click=lambda _: self._cargar_pagos(int(self.id_prestamo)))
            ]))
        ])



    def _agregar_fila_pago(self, e=None):
        datos_prestamo = self.pago_model.get_saldo_y_monto_prestamo(self.id_prestamo)
        if not datos_prestamo:
            ModalAlert.mostrar_info("Error", "No se puede generar fila sin datos de préstamo.")
            return

        self.fila_nueva = self._crear_fila_nueva(
            monto_total=float(datos_prestamo["monto_prestamo"]),
            saldo_actual=float(datos_prestamo["saldo_prestamo"])
        )

        self.tabla_pagos.rows.append(self.fila_nueva)
        self.page.update()

    def _eliminar_pago(self, id_pago: int):
        resultado = self.pago_model.delete_by_id_pago(id_pago)
        if resultado["status"] == "success":
            ModalAlert.mostrar_info("Eliminado", "El pago fue eliminado correctamente.")
            self._cargar_pagos(int(self.id_prestamo))
        else:
            ModalAlert.mostrar_info("Error", resultado["message"])

    def _procesar_importacion(self, ruta_archivo: str):
        try:
            df = pd.read_excel(ruta_archivo)
            columnas_requeridas = [
                "Monto Pagado", "Fecha Generación", "Interés %", "Fecha Real", "Observaciones"
            ]
            for col in columnas_requeridas:
                if col not in df.columns:
                    ModalAlert.mostrar_info("Error", f"Falta la columna requerida: '{col}'")
                    return

            exitos = 0
            duplicados = 0

            for _, row in df.iterrows():
                fecha_pago = str(row["Fecha Generación"])[:10]
                fecha_real = str(row["Fecha Real"])[:10]
                monto = float(row["Monto Pagado"])
                interes = int(row["Interés %"])
                observaciones = str(row.get("Observaciones", ""))

                # Verificar duplicados
                existente = self.pago_model.db.get_data(
                    f"""SELECT COUNT(*) AS c FROM {self.E.TABLE.value}
                        WHERE {self.E.PAGO_FECHA_PAGO.value} = %s
                        AND {self.E.PAGO_FECHA_REAL.value} = %s
                        AND {self.E.PAGO_MONTO_PAGADO.value} = %s
                        AND {self.E.PAGO_ID_PRESTAMO.value} = %s""",
                    (fecha_pago, fecha_real, monto, int(self.id_prestamo)),
                    dictionary=True
                )

                if existente.get("c", 0) > 0:
                    duplicados += 1
                    continue

                resultado = self.pago_model.add_payment(
                    id_prestamo=int(self.id_prestamo),
                    monto_pagado=monto,
                    fecha_pago=fecha_pago,
                    fecha_generacion=fecha_pago,
                    interes_porcentaje=interes,
                    fecha_real_pago=fecha_real,
                    observaciones=observaciones
                )

                if resultado["status"] == "success":
                    exitos += 1

            mensaje = f"Importación completada.\nPagos agregados: {exitos}"
            if duplicados:
                mensaje += f"\nPagos duplicados ignorados: {duplicados}"

            ModalAlert.mostrar_info("Resultado", mensaje)
            self._cargar_pagos(int(self.id_prestamo))

        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo importar el archivo: {str(ex)}")


    def _exportar_pagos(self, path: str = None):
        try:
            resultado = self.pago_model.get_by_prestamo(self.id_prestamo)
            if resultado["status"] != "success":
                ModalAlert.mostrar_info("Error", resultado["message"])
                return

            datos = resultado["data"]
            if not datos:
                ModalAlert.mostrar_info("Aviso", "No hay pagos registrados para exportar.")
                return

            columnas = [
                (self.E.PAGO_ID.value, "ID Pago"),
                (self.E.PAGO_FECHA_PAGO.value, "Fecha Generación"),
                (self.E.PAGO_FECHA_REAL.value, "Fecha Real"),
                (self.E.PAGO_MONTO_PAGADO.value, "Monto Pagado"),
                (self.E.PAGO_INTERES_PORCENTAJE.value, "Interés %"),
                (self.E.PAGO_INTERES_APLICADO.value, "Interés Aplicado"),
                (self.E.PAGO_SALDO_RESTANTE.value, "Saldo Restante"),
                (self.E.PAGO_OBSERVACIONES.value, "Observaciones")
            ]

            cuerpo = []
            for reg in datos:
                fila = []
                for clave, _ in columnas:
                    val = reg.get(clave)
                    if isinstance(val, (pd.Timestamp, datetime)):
                        fila.append(val.strftime("%Y-%m-%d"))
                    elif val is None:
                        fila.append("")
                    else:
                        fila.append(str(val))
                cuerpo.append(fila)

            df = pd.DataFrame(cuerpo, columns=[nombre for _, nombre in columnas])

            if not path:
                fecha = datetime.today().strftime("%Y-%m-%d")
                nombre = f"Pagos_Prestamo_{self.id_prestamo}_{fecha}_Exportados.xlsx"
                path = os.path.join(os.path.expanduser("~/Downloads"), nombre)

            os.makedirs(os.path.dirname(path), exist_ok=True)

            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Pagos")

            ModalAlert.mostrar_info("Éxito", f"Pagos exportados correctamente a:\n{path}")

        except Exception as e:
            ModalAlert.mostrar_info("Error", f"Falló la exportación: {e}")


    def _volver(self, e=None):
        self.page.go("/home/prestamos")
