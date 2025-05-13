from datetime import datetime, timedelta
import flet as ft
from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert
from app.models.payment_model import PaymentModel
from app.models.discount_model import DiscountModel
from app.views.containers.date_modal_selector import DateModalSelector
from app.views.containers.modal_descuentos import ModalDescuentos


class PagosContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20, alignment=ft.alignment.top_center)
        self.page = AppState().page
        self.payment_model = PaymentModel()
        self.payment_model.crear_sp_horas_trabajadas_para_pagos()
        self.discount_model = DiscountModel()

        self.fecha_inicio_id = None
        self.fecha_fin_id = None
        self.fecha_inicio_periodo = None
        self.fecha_fin_periodo = None

        self.input_id = ft.TextField(label="ID Empleado", width=150, height=40)

        self.date_selector_id = DateModalSelector(on_dates_confirmed=self._actualizar_fechas_id)
        self.date_selector_periodo = DateModalSelector(on_dates_confirmed=self._auto_generar_por_periodo)

        self.tabla_pagos = ft.DataTable(columns=[], rows=[], expand=True)
        self.resumen_pagos = ft.Text(value="", weight=ft.FontWeight.BOLD, size=14)

        self._build()
        self._mostrar_pagos_pagados()

    def _actualizar_fechas_id(self, inicio, fin):
        self.fecha_inicio_id = inicio
        self.fecha_fin_id = fin

    def _auto_generar_por_periodo(self, inicio, fin):
        self.fecha_inicio_periodo = inicio
        self.fecha_fin_periodo = fin
        self._buscar_por_periodo(None)

    def _generar_pago_individual(self, e):
        if not self.fecha_inicio_id or not self.fecha_fin_id:
            ModalAlert.mostrar_info("Fechas no seleccionadas", "Primero selecciona el rango de fechas.")
            return

        if not self.input_id.value.strip():
            ModalAlert.mostrar_info("Campo vacío", "Debes escribir un número de nómina.")
            return

        try:
            numero = int(self.input_id.value.strip())
            resultado = self.payment_model.generar_pago_por_empleado(numero, self.fecha_inicio_id, self.fecha_fin_id)
            if resultado["status"] == "success":
                ModalAlert.mostrar_info("Pago generado", resultado["message"])
                self._mostrar_pagos_pagados()
            else:
                ModalAlert.mostrar_info("Error", resultado["message"])
        except Exception as ex:
            ModalAlert.mostrar_info("Error interno", str(ex))

    def _buscar_por_periodo(self, e):
        if not self.fecha_inicio_periodo or not self.fecha_fin_periodo:
            ModalAlert.mostrar_info("Fechas no seleccionadas", "Primero selecciona el rango de fechas.")
            return

        try:
            resultado = self.payment_model.generar_pagos_por_rango(
                fecha_inicio=self.fecha_inicio_periodo,
                fecha_fin=self.fecha_fin_periodo
            )
            if resultado["status"] == "success":
                ModalAlert.mostrar_info("Nómina Generada", resultado["message"])
            else:
                ModalAlert.mostrar_info("Error", resultado["message"])
            self._mostrar_pagos_pagados()
        except Exception as ex:
            ModalAlert.mostrar_info("Error al generar pagos", str(ex))

    def _abrir_modal_fecha_id(self, e):
        self.date_selector_id.fecha_inicio = self.fecha_inicio_id
        self.date_selector_id.fecha_fin = self.fecha_fin_id
        self.date_selector_id.abrir_dialogo()

    def _abrir_modal_fecha_periodo(self, e):
        self.date_selector_periodo.fecha_inicio = self.fecha_inicio_periodo
        self.date_selector_periodo.fecha_fin = self.fecha_fin_periodo
        self.date_selector_periodo.abrir_dialogo()

    def _build(self):
        self.content = ft.Column([
            ft.Text("ÁREA DE PAGOS", style=ft.TextThemeStyle.TITLE_MEDIUM),
            self._build_buttons_area(),
            ft.Divider(),
            self.tabla_pagos,
            ft.Container(content=self.resumen_pagos, padding=10, alignment=ft.alignment.center)
        ])

    def _build_buttons_area(self):
        return ft.Row([
            self._build_icon_button("Importar", ft.icons.FILE_DOWNLOAD, lambda _: print("📁 Importar presionado")),
            self._build_icon_button("Exportar", ft.icons.FILE_UPLOAD, lambda _: print("📤 Exportar presionado")),
            ft.Container(
                content=ft.Row([
                    ft.Icon(name=ft.icons.PERSON_SEARCH),
                    self.input_id,
                    ft.IconButton(icon=ft.icons.CALENDAR_MONTH, on_click=self._abrir_modal_fecha_id),
                    ft.IconButton(icon=ft.icons.SEARCH, on_click=self._generar_pago_individual)
                ], spacing=10),
                padding=5,
                border_radius=10,
                border=ft.border.all(1, ft.colors.OUTLINE)
            ),
            ft.Container(
                content=ft.ElevatedButton(
                    text="Pagos por Período",
                    icon=ft.icons.CALENDAR_VIEW_MONTH,
                    on_click=self._abrir_modal_fecha_periodo,
                    height=40,
                    style=ft.ButtonStyle(
                        bgcolor=ft.colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=4),
                        side=ft.BorderSide(1, ft.colors.BLACK)
                    )
                ),
                padding=5,
                border_radius=10,
                border=ft.border.all(1, ft.colors.OUTLINE)
            )
        ], spacing=15)

    def _build_icon_button(self, text, icon, handler):
        return ft.GestureDetector(
            on_tap=handler,
            content=ft.Row([
                ft.Icon(name=icon),
                ft.Text(text)
            ], spacing=5)
        )

    def _make_descuento_handler(self, pago):
        return lambda e: self._abrir_modal_descuentos(pago)

    def _guardar_pago_confirmado(self, id_pago: int):
        def confirmar():
            try:
                pago = self.payment_model.get_by_id(id_pago)
                if pago["status"] != "success" or not pago["data"]:
                    ModalAlert.mostrar_info("Error", f"No se encontró el pago con ID {id_pago}")
                    return

                total_descuentos = self.discount_model.get_total_descuentos_por_pago(id_pago)
                monto_base = pago["data"]["monto_base"]
                monto_total = max(0, monto_base - total_descuentos)

                campos = {
                    "estado": "pagado",
                    "monto_total": monto_total,
                    "pago_efectivo": monto_total,
                    "fecha_pago": datetime.today().strftime("%Y-%m-%d")
                }

                result = self.payment_model.update_pago(id_pago, campos)
                if result["status"] == "success":
                    self._mostrar_pagos_pagados()
                else:
                    ModalAlert.mostrar_info("Error", result["message"])
            except Exception as ex:
                ModalAlert.mostrar_info("Error interno", str(ex))

        ModalAlert(
            title_text="Confirmar pago",
            message=f"¿Deseas confirmar el pago con ID {id_pago}?",
            on_confirm=confirmar
        ).mostrar()

    def _eliminar_pago(self, id_pago: int):
        def eliminar():
            try:
                self.discount_model.eliminar_por_id_pago(id_pago)
                self.payment_model.db.run_query("DELETE FROM pagos WHERE id_pago = %s", (id_pago,))
                self._mostrar_pagos_pagados()
            except Exception as ex:
                ModalAlert.mostrar_info("Error al eliminar", str(ex))

        ModalAlert(
            title_text="Eliminar Pago",
            message=f"¿Estás seguro de eliminar el pago con ID {id_pago}?",
            on_confirm=eliminar
        ).mostrar()

    def _mostrar_pagos_pagados(self):
        try:
            self.tabla_pagos.columns = [
                ft.DataColumn(label=ft.Text("ID Pago")),
                ft.DataColumn(label=ft.Text("ID Empleado")),
                ft.DataColumn(label=ft.Text("Nombre")),
                ft.DataColumn(label=ft.Text("Fecha Pago")),
                ft.DataColumn(label=ft.Text("Horas")),
                ft.DataColumn(label=ft.Text("Sueldo/Hora")),
                ft.DataColumn(label=ft.Text("Monto Base")),
                ft.DataColumn(label=ft.Text("Descuentos")),
                ft.DataColumn(label=ft.Text("Total")),
                ft.DataColumn(label=ft.Text("Acciones")),
                ft.DataColumn(label=ft.Text("Estado"))
            ]

            self.tabla_pagos.rows.clear()
            total_pagado = 0

            query = """
                SELECT p.id_pago, p.numero_nomina, p.fecha_pago,
                    p.total_horas_trabajadas, p.monto_base, p.monto_total, p.estado,
                    e.nombre_completo, e.sueldo_por_hora
                FROM pagos p
                JOIN empleados e ON p.numero_nomina = e.numero_nomina
                ORDER BY p.fecha_pago DESC
            """
            pagos = self.payment_model.db.get_data_list(query, dictionary=True)

            if not pagos:
                self.tabla_pagos.rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text("-")) for _ in range(11)
                ]))
            else:
                for p in pagos:
                    if not p:
                        continue
                    descuentos = self.discount_model.get_total_descuentos_por_pago(p["id_pago"])
                    estado = p["estado"]
                    acciones = ft.DataCell(ft.Text("✔️")) if estado == "pagado" else ft.DataCell(ft.Row([
                        ft.IconButton(icon=ft.icons.CHECK, tooltip="Confirmar pago", on_click=lambda e, id=p["id_pago"]: self._guardar_pago_confirmado(id)),
                        ft.IconButton(icon=ft.icons.CANCEL, tooltip="Eliminar pago", on_click=lambda e, id=p["id_pago"]: self._eliminar_pago(id))
                    ]))

                    self.tabla_pagos.rows.append(ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(p["id_pago"]))),
                        ft.DataCell(ft.Text(str(p["numero_nomina"]))),
                        ft.DataCell(ft.Text(p["nombre_completo"])),
                        ft.DataCell(ft.Text(str(p["fecha_pago"]))),
                        ft.DataCell(ft.Text(str(p["total_horas_trabajadas"]))),
                        ft.DataCell(ft.Text(f"${p['sueldo_por_hora']:.2f}")),
                        ft.DataCell(ft.Text(f"${p['monto_base']:.2f}")),
                        ft.DataCell(ft.Row([
                            ft.Text(f"${descuentos:.2f}"),
                            ft.IconButton(icon=ft.icons.EDIT_NOTE, tooltip="Editar descuentos", on_click=self._make_descuento_handler(p))
                        ])),
                        ft.DataCell(ft.Text(f"${p['monto_total']:.2f}")),
                        acciones,
                        ft.DataCell(ft.Text("Pagado" if estado == "pagado" else "Pendiente"))
                    ]))

                    if estado == "pagado":
                        total_pagado += float(p["monto_total"])

            self.resumen_pagos.value = f"Total pagado: ${total_pagado:.2f}"
            self.page.update()

        except Exception as ex:
            ModalAlert.mostrar_info("Error al cargar pagos", str(ex))

    def _abrir_modal_descuentos(self, pago: dict):
        def on_confirmar(data):
            self.discount_model.guardar_descuentos_editables(
                id_pago=pago["id_pago"],
                aplicar_imss=data["aplicar_imss"],
                aplicar_transporte=data["aplicar_transporte"],
                monto_transporte=data["monto_transporte"],
                aplicar_comida=data["aplicar_comida"],
                estado_comida=data["estado_comida"],
                descuento_extra=data["descuento_extra"],
                descripcion_extra=data["descripcion_extra"],
                numero_nomina=pago["numero_nomina"]
            )
            self._mostrar_pagos_pagados()

        # ✅ MANTENER REFERENCIA
        self.modal_descuentos = ModalDescuentos(pago, on_confirmar)
        self.modal_descuentos.mostrar()
