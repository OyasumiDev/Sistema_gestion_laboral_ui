from datetime import datetime, timedelta
import flet as ft
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
        self.date_selector_periodo = DateModalSelector(on_dates_confirmed=self._auto_generar_por_periodo)

        self.tabla_pagos = ft.DataTable(columns=[], rows=[], expand=True)
        self.resumen_pagos = ft.Text(value="", weight=ft.FontWeight.BOLD, size=14)

        self._build()
        self._mostrar_pagos_pagados()  # 🆕 Mostrar pagos pagados al iniciar

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
            empleados = self.payment_model.employee_model.get_all()
            if empleados["status"] != "success":
                ModalAlert.mostrar_info("Error", "No se pudieron cargar los empleados.")
                return

            errores = 0
            for emp in empleados["data"]:
                res = self.payment_model.generar_pago_por_empleado(
                    emp["numero_nomina"], self.fecha_inicio_periodo, self.fecha_fin_periodo
                )
                if res["status"] != "success":
                    errores += 1

            mensaje = f"Pagos generados del {self.fecha_inicio_periodo} al {self.fecha_fin_periodo}."
            if errores > 0:
                mensaje += f" Algunos empleados no tenían asistencias registradas ({errores} errores)."

            ModalAlert.mostrar_info("Nómina Generada", mensaje)
            self._mostrar_pagos_pagados()
        except Exception as ex:
            ModalAlert.mostrar_info("Error al generar pagos", str(ex))

    def _generar_nomina_automatica(self, e):
        try:
            ultima_fecha = self.payment_model.get_ultima_fecha_pago()
            if not ultima_fecha:
                ModalAlert.mostrar_info("Sin historial", "No hay pagos previos registrados.")
                return

            fecha_inicio = (ultima_fecha + timedelta(days=1)).strftime("%Y-%m-%d")
            fecha_fin = datetime.now().strftime("%Y-%m-%d")

            empleados = self.payment_model.employee_model.get_all()
            if empleados["status"] != "success":
                ModalAlert.mostrar_info("Error", "No se pudieron cargar los empleados.")
                return

            for emp in empleados["data"]:
                self.payment_model.generar_pago_por_empleado(emp["numero_nomina"], fecha_inicio, fecha_fin)

            ModalAlert.mostrar_info("Nómina Automática", f"Pagos generados desde {fecha_inicio} hasta hoy.")
            self._mostrar_pagos_pagados()
        except Exception as ex:
            ModalAlert.mostrar_info("Error automático", str(ex))

    def _mostrar_pagos_pagados(self):
        try:
            self.tabla_pagos.columns = [
                ft.DataColumn(label=ft.Text("ID Empleado")),
                ft.DataColumn(label=ft.Text("Nombre")),
                ft.DataColumn(label=ft.Text("Fecha Pago")),
                ft.DataColumn(label=ft.Text("Horas Trabajadas")),
                ft.DataColumn(label=ft.Text("Sueldo x Hora")),
                ft.DataColumn(label=ft.Text("Monto Base")),
                ft.DataColumn(label=ft.Text("Descuentos")),
                ft.DataColumn(label=ft.Text("Monto Final")),
                ft.DataColumn(label=ft.Text("Acciones"))
            ]

            self.tabla_pagos.rows.clear()
            total_pagado = 0

            query = """
                SELECT p.id_pago, p.numero_nomina, p.fecha_pago, p.horas_trabajadas,
                       p.monto_base, p.monto_total, p.estado,
                       e.nombre_completo, e.sueldo_por_hora
                FROM pagos p
                JOIN empleados e ON p.numero_nomina = e.numero_nomina
                WHERE p.estado = 'pagado'
            """
            pagos = self.payment_model.db.get_data(query, dictionary=True)

            for p in pagos:
                descuentos = self.discount_model.get_total_descuentos_por_pago(p["id_pago"])
                self.tabla_pagos.rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(p["numero_nomina"]))),
                    ft.DataCell(ft.Text(p["nombre_completo"])),
                    ft.DataCell(ft.Text(str(p["fecha_pago"]))),
                    ft.DataCell(ft.Text(str(p["horas_trabajadas"]))),
                    ft.DataCell(ft.Text(f"${p['sueldo_por_hora']:.2f}")),
                    ft.DataCell(ft.Text(f"${p['monto_base']:.2f}")),
                    ft.DataCell(ft.Text(f"${descuentos:.2f}")),
                    ft.DataCell(ft.Text(f"${p['monto_total']:.2f}")),
                    ft.DataCell(ft.Row([
                        ft.IconButton(icon=ft.icons.EDIT),
                        ft.IconButton(icon=ft.icons.DELETE)
                    ]))
                ]))
                total_pagado += float(p["monto_total"])

            if not self.tabla_pagos.rows:
                self.tabla_pagos.rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text("-")) for _ in range(9)
                ]))

            self.resumen_pagos.value = f"Total pagado: ${total_pagado:.2f}"
            self.page.update()
        except Exception as ex:
            ModalAlert.mostrar_info("Error al cargar pagos", str(ex))

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
            self._build_icon_button("Generar automáticamente", ft.icons.PLAY_ARROW, self._generar_nomina_automatica),
            self._build_icon_button("Limpiar", ft.icons.CLEAR_ALL, self._mostrar_pagos_pagados),
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
