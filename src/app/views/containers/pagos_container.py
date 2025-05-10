import flet as ft
from datetime import date
from app.core.app_state import AppState
from app.models.payment_model import PaymentModel
from app.models.discount_model import DiscountModel
from app.core.enums.e_payment_model import E_PAYMENT
from app.views.containers import messages  # Se importa el módulo de mensajes

class PagosContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20)
        self.page = AppState().page
        self.payment_model = PaymentModel()
        self.discount_model = DiscountModel()

        self.fecha_inicio = ft.TextField(label="Fecha inicio", width=150, hint_text="YYYY-MM-DD")
        self.fecha_fin = ft.TextField(label="Fecha fin", width=150, hint_text="YYYY-MM-DD")
        self.numero_nomina_input = ft.TextField(label="Número de nómina", width=150)
        self.id_pago_input = ft.TextField(label="ID de pago", width=150)

        self.tabla = ft.DataTable(columns=[], rows=[], expand=True)

        self._build()
        self._actualizar_tabla()

    def _build(self):
        filtros = ft.Column([
            ft.Row([
                self._build_icon_button("Importar", ft.icons.FILE_UPLOAD, lambda _: None),
                self._build_icon_button("Exportar", ft.icons.FILE_DOWNLOAD, lambda _: None),
                self._build_icon_button("Agregar", ft.icons.ADD, self._agregar_pago),
            ], spacing=15),
            ft.Row([
                self.id_pago_input,
                ft.TextButton("Filtrar por ID", on_click=self._filtrar_por_id),
                self.numero_nomina_input,
                ft.TextButton("Filtrar por Nómina", on_click=self._filtrar_por_nomina),
                self.fecha_inicio,
                self.fecha_fin,
                ft.TextButton("Generar pagos por rango", on_click=self._generar_pagos_por_rango),
                ft.TextButton("Con saldo", on_click=self._filtrar_con_saldo),
                ft.TextButton("Mostrar todos", on_click=self._actualizar_tabla)
            ], spacing=10, wrap=True)
        ])

        self.content = ft.Column([
            ft.Text("Área actual: Pagos", style=ft.TextThemeStyle.TITLE_MEDIUM),
            filtros,
            ft.Divider(),
            self.tabla
        ])

    def _build_icon_button(self, text, icon, handler):
        return ft.GestureDetector(
            on_tap=handler,
            content=ft.Row([
                ft.Icon(name=icon),
                ft.Text(text)
            ], spacing=5)
        )

    def _actualizar_tabla(self, e=None, datos=None):
        if not datos:
            hoy = str(date.today())
            resultado = self.payment_model.get_by_fecha_rango(hoy, hoy)
            if resultado["status"] != "success":
                print("❌", resultado["message"])
                return
            datos = resultado["data"]

        columnas = [
            ft.DataColumn(label=ft.Text("Nómina")),
            ft.DataColumn(label=ft.Text("Nombre")),
            ft.DataColumn(label=ft.Text("ID Pago")),
            ft.DataColumn(label=ft.Text("Fecha")),
            ft.DataColumn(label=ft.Text("Saldo")),
            ft.DataColumn(label=ft.Text("Depósito")),
            ft.DataColumn(label=ft.Text("Efectivo")),
            ft.DataColumn(label=ft.Text("Creación")),
            ft.DataColumn(label=ft.Text("Modificación")),
            ft.DataColumn(label=ft.Text("Editar/Borrar"))
        ]

        filas = []
        for pago in datos:
            numero = pago[E_PAYMENT.NUMERO_NOMINA.value]
            empleado = self.payment_model.db.get_data(
                "SELECT nombre_completo FROM empleados WHERE numero_nomina = %s",
                (numero,), dictionary=True
            ).get("nombre_completo", "-")

            fila = ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(numero))),
                ft.DataCell(ft.Text(empleado)),
                ft.DataCell(ft.Text(str(pago[E_PAYMENT.ID.value]))),
                ft.DataCell(ft.Text(str(pago[E_PAYMENT.FECHA_PAGO.value]))),
                ft.DataCell(ft.Text(str(pago[E_PAYMENT.SALDO.value]))),
                ft.DataCell(ft.Text(str(pago[E_PAYMENT.PAGO_DEPOSITO.value]))),
                ft.DataCell(ft.Text(str(pago[E_PAYMENT.PAGO_EFECTIVO.value]))),
                ft.DataCell(ft.Text(str(pago.get("fecha_creacion", "-")))),
                ft.DataCell(ft.Text(str(pago.get("fecha_modificacion", "-")))),
                ft.DataCell(
                    ft.Row([
                        ft.IconButton(icon=ft.icons.EDIT, tooltip="Editar", on_click=lambda e, p=pago: self._mostrar_dialogo_edicion(p)),
                        ft.IconButton(icon=ft.icons.DELETE, tooltip="Borrar", on_click=lambda e, id=pago[E_PAYMENT.ID.value]: self._confirmar_borrado(id))
                    ])
                )
            ])
            filas.append(fila)

        self.tabla.columns = columnas
        self.tabla.rows = filas
        self.page.update()

    def _filtrar_por_id(self, e):
        try:
            id_pago = int(self.id_pago_input.value)
            resultado = self.payment_model.get_by_id(id_pago)
            if resultado["status"] == "success":
                self._actualizar_tabla(datos=[resultado["data"]])
        except:
            print("⚠️ ID inválido")

    def _filtrar_por_nomina(self, e):
        try:
            nomina = int(self.numero_nomina_input.value)
            resultado = self.payment_model.get_by_empleado(nomina)
            if resultado["status"] == "success":
                self._actualizar_tabla(datos=resultado["data"])
        except:
            print("⚠️ Número de nómina inválido")

    def _generar_pagos_por_rango(self, e):
        inicio = self.fecha_inicio.value
        fin = self.fecha_fin.value
        try:
            self.payment_model.db.run_query("CALL generar_pagos_por_rango(%s, %s)", (inicio, fin))
            print("✅ Pagos generados exitosamente")
            self._actualizar_tabla()
        except Exception as ex:
            print(f"❌ Error al generar pagos: {ex}")

    def _filtrar_con_saldo(self, e):
        resultado = self.payment_model.get_pagos_con_saldo()
        if resultado["status"] == "success":
            self._actualizar_tabla(datos=resultado["data"])

    def _mostrar_dialogo_edicion(self, pago):
        id_pago = pago[E_PAYMENT.ID.value]
        saldo_input = ft.TextField(label="Saldo", value=str(pago[E_PAYMENT.SALDO.value]))
        deposito_input = ft.TextField(label="Depósito", value=str(pago[E_PAYMENT.PAGO_DEPOSITO.value]))
        efectivo_input = ft.TextField(label="Efectivo", value=str(pago[E_PAYMENT.PAGO_EFECTIVO.value]))

        def aplicar_cambios(e):
            def confirmar_actualizacion(ev):
                campos = {
                    E_PAYMENT.SALDO.value: float(saldo_input.value),
                    E_PAYMENT.PAGO_DEPOSITO.value: float(deposito_input.value),
                    E_PAYMENT.PAGO_EFECTIVO.value: float(efectivo_input.value),
                    "fecha_modificacion": date.today().strftime("%Y-%m-%d")
                }
                resultado = self.payment_model.update_pago(id_pago, campos)
                if resultado["status"] == "success":
                    print("✅ Pago actualizado")
                    self._actualizar_tabla()
                else:
                    print("❌ Error al actualizar pago:", resultado["message"])

            messages.mostrar_mensaje(
                page=self.page,
                titulo="¿Aplicar cambios?",
                mensaje="¿Deseas guardar los cambios realizados en este pago?",
                texto_boton="Sí, actualizar",
                on_close=confirmar_actualizacion
            )

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Editar pago ID {id_pago}"),
            content=ft.Column([
                saldo_input,
                deposito_input,
                efectivo_input
            ], tight=True),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: setattr(dialogo, "open", False)),
                ft.IconButton(icon=ft.icons.CHECK, tooltip="Aplicar cambios", on_click=aplicar_cambios)
            ],
            on_dismiss=lambda e: self.page.update()
        )

        self.page.dialog = dialogo
        dialogo.open = True
        self.page.update()

    def _confirmar_borrado(self, id_pago):
        def on_confirmar(e):
            self.payment_model.db.run_query(
                f"DELETE FROM {E_PAYMENT.TABLE.value} WHERE {E_PAYMENT.ID.value} = %s",
                (id_pago,)
            )
            print("🗑️ Pago eliminado")
            self._actualizar_tabla()

        messages.mostrar_mensaje(
            page=self.page,
            titulo="¿Deseas eliminar este pago?",
            mensaje=f"Esta acción no se puede deshacer. ID pago: {id_pago}",
            texto_boton="Sí, eliminar",
            on_close=on_confirmar
        )


    def _agregar_pago(self, e):
        print("🟢 Botón de agregar presionado")  # depuración
        numero_nomina_input = ft.TextField(label="Número de nómina")
        fecha_pago_input = ft.TextField(label="Fecha de pago (YYYY-MM-DD)", value=str(date.today()))
        monto_total_input = ft.TextField(label="Monto total")
        saldo_input = ft.TextField(label="Saldo", value="0")
        deposito_input = ft.TextField(label="Pago depósito")
        efectivo_input = ft.TextField(label="Pago efectivo")

        dialogo = ft.AlertDialog(modal=True)

        def aplicar_agregado(ev):
            print("🔵 Aplicar agregado presionado")  # depuración

            def confirmar_agregado(evv):
                print("🟡 Confirmación recibida, intentando registrar...")  # depuración
                try:
                    resultado = self.payment_model.add(
                        int(numero_nomina_input.value),
                        fecha_pago_input.value,
                        float(monto_total_input.value),
                        float(saldo_input.value),
                        float(deposito_input.value),
                        float(efectivo_input.value)
                    )
                    if resultado["status"] == "success":
                        print("✅ Pago agregado correctamente")
                        dialogo.open = False
                        self.page.update()
                        self._actualizar_tabla()
                    else:
                        print("❌ Error al agregar pago:", resultado["message"])
                except Exception as ex:
                    print("❌ Datos inválidos:", ex)

            dialogo.open = False
            self.page.update()

            from app.views.containers import messages
            messages.mostrar_mensaje(
                page=self.page,
                titulo="¿Agregar nuevo pago?",
                mensaje="¿Deseas registrar este nuevo pago en el sistema?",
                texto_boton="Sí, registrar",
                on_close=confirmar_agregado
            )

        dialogo.title = ft.Text("Agregar nuevo pago")
        dialogo.content = ft.Column([
            numero_nomina_input,
            fecha_pago_input,
            monto_total_input,
            saldo_input,
            deposito_input,
            efectivo_input
        ], tight=True)
        dialogo.actions = [
            ft.TextButton("Cancelar", on_click=lambda e: setattr(dialogo, "open", False)),
            ft.TextButton("Registrar", icon=ft.icons.CHECK, on_click=aplicar_agregado)
        ]
        dialogo.on_dismiss = lambda e: self.page.update()

        self.page.dialog = dialogo
        dialogo.open = True
        self.page.update()
