from datetime import datetime
import pandas as pd
import flet as ft
from urllib.parse import urlparse, parse_qs
from decimal import Decimal

from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert
from app.models.payment_model import PaymentModel
from app.models.discount_model import DiscountModel
from app.views.containers.date_modal_selector import DateModalSelector

class PagosContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20, alignment=ft.alignment.top_center)
        self.page = AppState().page
        self.payment_model = PaymentModel()
        self.discount_model = DiscountModel()

        self.fecha_inicio_id = None
        self.fecha_fin_id = None
        self.fecha_inicio_periodo = None
        self.fecha_fin_periodo = None

        self.input_id = ft.TextField(label="ID Empleado", width=150, height=40)

        self.date_selector_id = DateModalSelector(on_dates_confirmed=self._actualizar_fechas_id)
        self.date_selector_periodo = DateModalSelector(on_dates_confirmed=self._actualizar_fechas_periodo)

        self.tabla_pagos = ft.DataTable(columns=[], rows=[], expand=True)
        self.resumen_pagos = ft.Text(value="", weight=ft.FontWeight.BOLD, size=14)

        self._build()
        self._actualizar_tabla_pagos(None, None)

    def _actualizar_fechas_id(self, inicio, fin):
        self.fecha_inicio_id = inicio
        self.fecha_fin_id = fin

    def _actualizar_fechas_periodo(self, inicio, fin):
        self.fecha_inicio_periodo = inicio
        self.fecha_fin_periodo = fin

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
                self._actualizar_tabla_pagos(self.fecha_inicio_id, self.fecha_fin_id)
            else:
                ModalAlert.mostrar_info("Error", resultado["message"])
        except Exception as ex:
            ModalAlert.mostrar_info("Error interno", str(ex))

    def _buscar_por_periodo(self, e):
        if not self.fecha_inicio_periodo or not self.fecha_fin_periodo:
            ModalAlert.mostrar_info("Fechas no seleccionadas", "Primero selecciona el rango de fechas.")
            return
        try:
            self.payment_model.db.run_query("CALL generar_pagos_por_rango(%s, %s)", (self.fecha_inicio_periodo, self.fecha_fin_periodo))
            ModalAlert.mostrar_info("Nómina Generada", f"Pagos generados del {self.fecha_inicio_periodo} al {self.fecha_fin_periodo}.")
            self._actualizar_tabla_pagos(self.fecha_inicio_periodo, self.fecha_fin_periodo)
        except Exception as ex:
            ModalAlert.mostrar_info("Error al generar pagos", str(ex))

    def _actualizar_tabla_pagos(self, inicio, fin):
        try:
            self.tabla_pagos.columns = [
                ft.DataColumn(label=ft.Text("ID Empleado")),
                ft.DataColumn(label=ft.Text("Nombre Completo")),
                ft.DataColumn(label=ft.Text("Horas Trabajadas")),
                ft.DataColumn(label=ft.Text("Sueldo Diario")),
                ft.DataColumn(label=ft.Text("Monto Base")),
                ft.DataColumn(label=ft.Text("Total Descuentos")),
                ft.DataColumn(label=ft.Text("Monto Final")),
                ft.DataColumn(label=ft.Text("Acciones"))
            ]

            self.tabla_pagos.rows.clear()
            total_pagado = 0

            if inicio and fin:
                query = """
                    SELECT p.numero_nomina, e.nombre_completo,
                        p.horas_trabajadas, e.sueldo_diario,
                        p.monto_base, d.total_descuentos, p.monto_total
                    FROM pagos p
                    JOIN empleados e ON e.numero_nomina = p.numero_nomina
                    LEFT JOIN (
                        SELECT id_pago, SUM(monto) AS total_descuentos
                        FROM descuentos_pago
                        GROUP BY id_pago
                    ) d ON d.id_pago = p.id_pago
                    WHERE p.fecha_pago BETWEEN %s AND %s
                """
                pagos = self.payment_model.db.get_data(query, (inicio, fin), dictionary=True)
                for p in pagos:
                    self.tabla_pagos.rows.append(ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(p["numero_nomina"]))),
                        ft.DataCell(ft.Text(p["nombre_completo"])),
                        ft.DataCell(ft.Text(str(p["horas_trabajadas"]))),
                        ft.DataCell(ft.Text(f"${p['sueldo_diario']:.2f}")),
                        ft.DataCell(ft.Text(f"${p['monto_base']:.2f}")),
                        ft.DataCell(ft.Text(f"${p.get('total_descuentos', 0):.2f}")),
                        ft.DataCell(ft.Text(f"${p['monto_total']:.2f}")),
                        ft.DataCell(ft.Row([
                            ft.IconButton(icon=ft.icons.EDIT),
                            ft.IconButton(icon=ft.icons.DELETE)
                        ]))
                    ]))
                    total_pagado += float(p['monto_total'])

            if not self.tabla_pagos.rows:
                self.tabla_pagos.rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text("-")) for _ in range(8)
                ]))

            self.resumen_pagos.value = f"Total pagado: ${total_pagado:.2f}"
            self.page.update()
        except Exception as ex:
            ModalAlert.mostrar_info("Error al actualizar tabla", str(ex))

    def _abrir_modal_fecha_id(self, e):
        try:
            self.date_selector_id.fecha_inicio = self.fecha_inicio_id
            self.date_selector_id.fecha_fin = self.fecha_fin_id
            self.date_selector_id.abrir_dialogo()
        except Exception as ex:
            ModalAlert.mostrar_info("Error de Fecha", f"No se pudo abrir el calendario: {str(ex)}")

    def _abrir_modal_fecha_periodo(self, e):
        try:
            self.date_selector_periodo.fecha_inicio = self.fecha_inicio_periodo
            self.date_selector_periodo.fecha_fin = self.fecha_fin_periodo
            self.date_selector_periodo.abrir_dialogo()
        except Exception as ex:
            ModalAlert.mostrar_info("Error de Fecha", f"No se pudo abrir el calendario: {str(ex)}")

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
            self._build_icon_button("Agregar", ft.icons.ADD, self._agregar_columna_pago),

            ft.Container(
                content=ft.Row([
                    ft.Icon(name=ft.icons.PERSON_SEARCH),
                    self.input_id,
                    ft.IconButton(icon=ft.icons.CALENDAR_MONTH, on_click=self._abrir_modal_fecha_id, icon_size=20, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4))),
                    ft.IconButton(icon=ft.icons.SEARCH, on_click=self._generar_pago_individual, icon_size=20, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4)))
                ], spacing=10),
                padding=5,
                bgcolor=None,
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
                        shape=ft.RoundedRectangleBorder(radius=6),
                        side=ft.BorderSide(1, ft.colors.BLACK)
                    )
                ),
                padding=5,
                bgcolor=None,
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

    def _agregar_columna_pago(self, e):
        try:
            id_input = ft.TextField(hint_text="ID Empleado", width=100)
            nombre_text = ft.Text("Nombre...", width=150)
            horas_text = ft.Text("00:00:00", width=100)
            sueldo_input = ft.TextField(hint_text="$0.00", width=100)
            monto_base_input = ft.TextField(hint_text="$0.00", width=100)
            descuentos_input = ft.TextField(hint_text="$0.00", width=100)
            monto_total_input = ft.TextField(hint_text="$0.00", width=100)

            async def actualizar_datos_id(e):
                try:
                    numero = int(id_input.value)
                    if self.fecha_inicio_id and self.fecha_fin_id:
                        query = "CALL horas_trabajadas(%s, %s, %s)"
                        result = self.payment_model.db.get_data(query, (numero, self.fecha_inicio_id, self.fecha_fin_id), dictionary=True)
                        if result:
                            nombre_text.value = result[0]["nombre_completo"]
                            horas_text.value = result[0]["total_horas_trabajadas"]
                            self.page.update()
                except Exception as ex:
                    ModalAlert.mostrar_info("Error", str(ex))

            id_input.on_change = actualizar_datos_id

            nueva_fila = ft.DataRow(cells=[
                ft.DataCell(id_input),
                ft.DataCell(nombre_text),
                ft.DataCell(horas_text),
                ft.DataCell(sueldo_input),
                ft.DataCell(monto_base_input),
                ft.DataCell(descuentos_input),
                ft.DataCell(monto_total_input),
                ft.DataCell(ft.Row([
                    ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600),
                    ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600, on_click=lambda _: self._actualizar_tabla_pagos(self.fecha_inicio_id, self.fecha_fin_id))
                ]))
            ])

            if self.tabla_pagos.rows and self.tabla_pagos.rows[0].cells[0].content.value == "-":
                self.tabla_pagos.rows[0] = nueva_fila
            else:
                self.tabla_pagos.rows.insert(0, nueva_fila)

            self.page.update()

        except Exception as ex:
            ModalAlert.mostrar_info("Error al agregar fila", str(ex))
