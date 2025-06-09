import flet as ft
from datetime import datetime
import os
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


class PrestamosContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20)
        self.page = AppState().page
        self.loan_model = LoanModel()
        self.payment_model = PaymentModel()
        self.detalles_model = DescuentoDetallesModel()
        self.E = E_PRESTAMOS
        self.tabla_prestamos = ft.DataTable(columns=[], rows=[], expand=True)

        self.importador = FileOpenInvoker(
            page=self.page,
            on_select=self._procesar_archivo_importado,
            allowed_extensions=["xlsx"]
        )

        self.exportador = FileSaveInvoker(
            page=self.page,
            on_save=self._guardar_exportacion,
            file_name=f"Exporte_Prestamos_{datetime.today().strftime('%Y-%m-%d')}.xlsx"
        )

        self.layout_tabla_prestamos = ft.Column(
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
        self._build()
        self._actualizar_vista_prestamos()

    def _build(self):
        self.layout_tabla_prestamos.controls = [
            ft.Text("Área actual: Préstamos", style=ft.TextThemeStyle.TITLE_MEDIUM),
            self._build_buttons_area(),
            self.tabla_prestamos
        ]

    def _build_buttons_area(self):
        return ft.Row([
            self._build_icon_button("Importar", ft.icons.FILE_DOWNLOAD, lambda _: self.importador.open()),
            self._build_icon_button("Exportar", ft.icons.FILE_UPLOAD, lambda _: self.exportador.open_save()),
            self._build_icon_button("Agregar", ft.icons.ADD, self._insertar_fila_prestamo)
        ], spacing=15)

    def _build_icon_button(self, text, icon, handler):
        return ft.ElevatedButton(
            icon=ft.Icon(name=icon),
            text=text,
            on_click=handler,
            style=ft.ButtonStyle(padding=10, shape=ft.RoundedRectangleBorder(radius=6))
        )

    def _actualizar_vista_prestamos(self):
        self._cargar_tabla_prestamos()
        self.content = ft.Column(expand=True, controls=[self.layout_tabla_prestamos])
        self.page.update()

    def _cargar_tabla_prestamos(self):
        resultado = self.loan_model.get_all()
        if resultado["status"] != "success":
            ModalAlert.mostrar_info("Error", resultado["message"])
            return

        prestamos = resultado["data"]
        self.tabla_prestamos.columns = [
            ft.DataColumn(ft.Text("ID")),
            ft.DataColumn(ft.Text("Empleado")),
            ft.DataColumn(ft.Text("Monto")),
            ft.DataColumn(ft.Text("Saldo")),
            ft.DataColumn(ft.Text("Dinero Pagado")),
            ft.DataColumn(ft.Text("Estado")),
            ft.DataColumn(ft.Text("Fecha Solicitud")),
            ft.DataColumn(ft.Text("Acciones")),
        ]

        self.tabla_prestamos.rows = []

        for p in prestamos:
            dinero_pagado = p[self.E.PRESTAMO_MONTO.value] - p[self.E.PRESTAMO_SALDO.value]

            id_pago_nomina = self.payment_model.get_pago_id_por_empleado_y_estado(
                numero_nomina=p[self.E.PRESTAMO_NUMERO_NOMINA.value],
                estado="pendiente"
            )

            fila = ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(p[self.E.PRESTAMO_ID.value]))),
                ft.DataCell(ft.Text(str(p[self.E.PRESTAMO_NUMERO_NOMINA.value]))),
                ft.DataCell(ft.Text(f"${p[self.E.PRESTAMO_MONTO.value]:,.2f}")),
                ft.DataCell(ft.Text(f"${p[self.E.PRESTAMO_SALDO.value]:,.2f}")),
                ft.DataCell(ft.Text(f"${dinero_pagado:,.2f}")),
                ft.DataCell(ft.Text(p[self.E.PRESTAMO_ESTADO.value])),
                ft.DataCell(ft.Text(p[self.E.PRESTAMO_FECHA_SOLICITUD.value])),
                ft.DataCell(self._build_acciones_cell(p, id_pago_nomina))
            ])
            self.tabla_prestamos.rows.append(fila)


    def _build_acciones_cell(self, prestamo, id_pago_nomina):
        def on_guardar_edicion(_):
            nuevo_monto_str = monto_input.value.strip()
            nuevo_estado = estado_dropdown.value

            if not nuevo_monto_str:
                ModalAlert("Monto requerido", "El campo de monto no puede estar vacío.").mostrar()
                return

            try:
                nuevo_monto = float(nuevo_monto_str)
                if nuevo_monto <= 0:
                    raise ValueError
            except ValueError:
                ModalAlert("Monto inválido", "Debe ingresar un monto válido mayor a 0.").mostrar()
                return

            resultado = self.loan_model.update_by_id_prestamo(
                prestamo[self.E.PRESTAMO_ID.value],
                {
                    self.E.PRESTAMO_MONTO: nuevo_monto,
                    self.E.PRESTAMO_ESTADO: nuevo_estado
                }
            )

            if resultado["status"] == "success":
                ModalAlert.mostrar_info("Éxito", "Préstamo editado correctamente.")
            else:
                ModalAlert.mostrar_info("Error", resultado["message"])

            self._actualizar_vista_prestamos()

        def on_cancelar_edicion(_):
            self._actualizar_vista_prestamos()

        monto_input = ft.TextField(hint_text="Monto", expand=True, width=100)

        estado_dropdown = ft.Dropdown(
            value=prestamo[self.E.PRESTAMO_ESTADO.value],
            options=[
                ft.dropdown.Option("pagando"),
                ft.dropdown.Option("terminado")
            ],
            width=120
        )

        return ft.Row([
            ft.IconButton(
                icon=ft.icons.EDIT,
                tooltip="Editar préstamo",
                on_click=lambda _: self._reemplazar_fila_con_edicion(
                    prestamo, monto_input, estado_dropdown,
                    on_guardar_edicion, on_cancelar_edicion
                )
            ),
            ft.IconButton(
                icon=ft.icons.DELETE,
                tooltip="Eliminar préstamo",
                on_click=lambda _: ModalAlert(
                    title_text="¿Eliminar préstamo?",
                    message="Esta acción no se puede deshacer.",
                    on_confirm=lambda: self._eliminar_prestamo(prestamo[self.E.PRESTAMO_ID.value]),
                    on_cancel=lambda: self.page.update()
                ).mostrar()
            ),
            ft.IconButton(
                icon=ft.icons.LIST_ALT,
                tooltip="Ver pagos del préstamo",
                on_click=lambda _: self.page.go(
                    f"/home/prestamos/pagosprestamos?{urlencode({'id_prestamo': prestamo[self.E.PRESTAMO_ID.value], 'id_pago': id_pago_nomina})}"
                )
            )
        ], spacing=5)

    def recargar_datos(self):
        self._actualizar_vista_prestamos()


    def _reemplazar_fila_con_edicion(self, prestamo, monto_input, estado_dropdown, on_guardar, on_cancelar):
        id_editando = str(prestamo[self.E.PRESTAMO_ID.value])
        monto_total = prestamo[self.E.PRESTAMO_MONTO.value]
        saldo_actual = prestamo[self.E.PRESTAMO_SALDO.value]
        dinero_pagado = monto_total - saldo_actual

        for i, row in enumerate(self.tabla_prestamos.rows):
            if str(row.cells[0].content.value).strip() == id_editando:
                self.tabla_prestamos.rows[i] = ft.DataRow(cells=[
                    ft.DataCell(ft.Text(id_editando)),  # ID
                    ft.DataCell(ft.Text(str(prestamo[self.E.PRESTAMO_NUMERO_NOMINA.value]))),  # Empleado
                    ft.DataCell(monto_input),  # Monto editable
                    ft.DataCell(ft.Text(f"${saldo_actual:,.2f}")),  # Saldo actual
                    ft.DataCell(ft.Text(f"${dinero_pagado:,.2f}")),  # Dinero pagado
                    ft.DataCell(estado_dropdown),  # Estado editable
                    ft.DataCell(ft.Text(prestamo[self.E.PRESTAMO_FECHA_SOLICITUD.value])),  # Fecha
                    ft.DataCell(ft.Row([
                        ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, on_click=on_guardar),
                        ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600, on_click=on_cancelar)
                    ]))
                ])
                break
        self.page.update()

    def _insertar_fila_prestamo(self, e=None):
        numero_input = ft.TextField(hint_text="ID Empleado", width=120)
        monto_textfield = ft.TextField(hint_text="Monto", expand=True)

        hoy = datetime.today().strftime("%Y-%m-%d")
        nuevo_id = self.loan_model.get_next_id_prestamo() or "?"

        def validar_id_empleado(e=None):
            val = numero_input.value.strip()
            numero_input.border_color = None
            if not val.isdigit() or int(val) <= 0:
                numero_input.border_color = ft.colors.RED
            else:
                existe = self.loan_model.db.get_data(
                    "SELECT COUNT(*) AS c FROM empleados WHERE numero_nomina = %s",
                    (val,), dictionary=True
                )
                if existe.get("c", 0) == 0:
                    numero_input.border_color = ft.colors.RED
            self.page.update()

        def validar_monto(e=None):
            val = monto_textfield.value.strip()
            monto_textfield.border_color = None
            if not val.isdigit():
                monto_textfield.border_color = ft.colors.RED
            else:
                if int(val) <= 0 or int(val) > 20000:
                    monto_textfield.border_color = ft.colors.RED
            self.page.update()

        numero_input.on_change = validar_id_empleado
        monto_textfield.on_change = validar_monto

        def on_guardar(_):
            numero_input.border_color = None
            monto_textfield.border_color = None

            numero_nomina = numero_input.value.strip()
            monto_str = monto_textfield.value.strip()

            if not numero_nomina.isdigit() or int(numero_nomina) <= 0:
                numero_input.border_color = ft.colors.RED
                ModalAlert.mostrar_info("ID inválido", "El número de empleado debe ser un entero positivo.")
                self.page.update()
                return

            existe = self.loan_model.db.get_data(
                "SELECT COUNT(*) AS c FROM empleados WHERE numero_nomina = %s",
                (numero_nomina,), dictionary=True
            )
            if existe.get("c", 0) == 0:
                numero_input.border_color = ft.colors.RED
                ModalAlert.mostrar_info("Empleado no encontrado", f"No existe un empleado con número de nómina {numero_nomina}")
                self.page.update()
                return

            if not monto_str.isdigit():
                monto_textfield.border_color = ft.colors.RED
                ModalAlert.mostrar_info("Monto inválido", "El monto debe ser un número entero positivo.")
                self.page.update()
                return

            monto = int(monto_str)
            if monto <= 0 or monto > 20000:
                monto_textfield.border_color = ft.colors.RED
                ModalAlert.mostrar_info("Monto inválido", "El monto debe ser mayor a 0 y no mayor a $20,000.")
                self.page.update()
                return

            resultado = self.loan_model.add(
                numero_nomina=int(numero_nomina),
                monto_prestamo=monto,
                saldo_prestamo=monto,
                estado="pagando",
                fecha_solicitud=hoy
            )

            if resultado["status"] == "success":
                ModalAlert.mostrar_info("Éxito", "Préstamo agregado correctamente.")
                self._actualizar_vista_prestamos()
            else:
                ModalAlert.mostrar_info("Error", resultado["message"])
            self.page.update()

        def on_cancelar(_):
            self._actualizar_vista_prestamos()

        self.tabla_prestamos.rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Text(str(nuevo_id))),             # ID Préstamo
            ft.DataCell(numero_input),                       # ID Empleado
            ft.DataCell(monto_textfield),                    # Monto
            ft.DataCell(ft.Text("Auto")),                    # Saldo actual
            ft.DataCell(ft.Text("Auto")),                    # Dinero pagado
            ft.DataCell(ft.Text("pagando")),                 # Estado
            ft.DataCell(ft.Text(hoy)),                       # Fecha solicitud
            ft.DataCell(ft.Row([
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, on_click=on_guardar),
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600, on_click=on_cancelar)
            ]))
        ]))

        self.page.update()


    def _procesar_archivo_importado(self, path):
        try:
            df = pd.read_excel(path)
            registros_agregados = 0
            registros_duplicados = 0

            for _, row in df.iterrows():
                numero = int(row["ID Empleado"])
                monto = float(row["Monto"])
                fecha = str(row["Fecha Solicitud"])

                existe = self.loan_model.db.get_data(
                    f"SELECT COUNT(*) as c FROM {self.E.TABLE.value} WHERE {self.E.PRESTAMO_NUMERO_NOMINA.value} = %s AND {self.E.PRESTAMO_FECHA_SOLICITUD.value} = %s",
                    (numero, fecha),
                    dictionary=True
                )

                if existe.get("c", 0) > 0:
                    registros_duplicados += 1
                    continue

                self.loan_model.add(
                    numero_nomina=numero,
                    monto_prestamo=monto,  # ✅ corregido aquí
                    saldo_prestamo=monto,
                    estado="pagando",
                    fecha_solicitud=fecha
                )
                registros_agregados += 1

            mensaje = f"Importación completada.\nNuevos registros: {registros_agregados}"
            if registros_duplicados:
                mensaje += f"\nRegistros duplicados ignorados: {registros_duplicados}"

            ModalAlert.mostrar_info("Importación de préstamos", mensaje)
            self._actualizar_vista_prestamos()

        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"Falló la importación: {ex}")



    def _guardar_exportacion(self, path):
        try:
            resultado = self.loan_model.get_all()
            if resultado["status"] != "success":
                ModalAlert.mostrar_info("Error", resultado["message"])
                return

            prestamos = resultado["data"]
            if not prestamos:
                ModalAlert.mostrar_info("Aviso", "No hay préstamos para exportar.")
                return

            columnas = [
                (self.E.PRESTAMO_ID.value, "ID Préstamo"),
                (self.E.PRESTAMO_NUMERO_NOMINA.value, "ID Empleado"),
                (self.E.PRESTAMO_MONTO.value, "Monto"),
                (self.E.PRESTAMO_SALDO.value, "Saldo Actual"),
                (self.E.PRESTAMO_ESTADO.value, "Estado"),
                (self.E.PRESTAMO_FECHA_SOLICITUD.value, "Fecha Solicitud")
            ]

            cuerpo = []
            for p in prestamos:
                fila = []
                for clave, _ in columnas:
                    val = p.get(clave)
                    if isinstance(val, (datetime, pd.Timestamp)):
                        fila.append(val.strftime("%Y-%m-%d"))
                    elif val is None:
                        fila.append("")
                    else:
                        fila.append(str(val))
                cuerpo.append(fila)

            df = pd.DataFrame(cuerpo, columns=[nombre for _, nombre in columnas])

            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Prestamos")

            ModalAlert.mostrar_info("Éxito", f"Préstamos exportados correctamente a:\n{path}")

        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"Falló la exportación: {ex}")

    def _eliminar_prestamo(self, id_prestamo: int):
        resultado = self.loan_model.delete_by_id_prestamo(id_prestamo)
        if resultado["status"] == "success":
            ModalAlert.mostrar_info("Eliminado", "El préstamo fue eliminado correctamente.")
            self._actualizar_vista_prestamos()
        else:
            ModalAlert.mostrar_info("Error", resultado["message"])
