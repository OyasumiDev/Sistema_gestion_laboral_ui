import flet as ft
from tabulate import tabulate
from app.core.app_state import AppState
from app.models.payment_model import PaymentModel
from app.models.discount_model import DiscountModel
from app.views.containers.date_modal_selector import DateModalSelector
from app.views.containers.modal_alert import ModalAlert

class PagosContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20)
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

        self.tabla_pagos = ft.Text(tabulate([], headers=[
            "ID Empleado", "Nombre Completo", "Horas Trabajadas",
            "Sueldo Diario", "Monto Base", "Total Descuentos", "Monto Final"
        ], tablefmt="grid"), selectable=True)

        self._build()

    def _actualizar_fechas_id(self, inicio, fin):
        self.fecha_inicio_id = inicio
        self.fecha_fin_id = fin
        print(f"\U0001F4C5 Fecha ID: {inicio} a {fin}")

    def _actualizar_fechas_periodo(self, inicio, fin):
        self.fecha_inicio_periodo = inicio
        self.fecha_fin_periodo = fin
        print(f"\U0001F4C5 Fecha Período: {inicio} a {fin}")

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
            filas = [
                [
                    p["numero_nomina"],
                    p["nombre_completo"],
                    p["horas_trabajadas"],
                    f"${p['sueldo_diario']:.2f}",
                    f"${p['monto_base']:.2f}",
                    f"${p.get('total_descuentos', 0):.2f}",
                    f"${p['monto_total']:.2f}"
                ] for p in pagos
            ]
            self.tabla_pagos.value = tabulate(filas, headers=[
                "ID Empleado", "Nombre Completo", "Horas Trabajadas",
                "Sueldo Diario", "Monto Base", "Total Descuentos", "Monto Final"
            ], tablefmt="grid")
            self.page.update()
        except Exception as ex:
            ModalAlert.mostrar_info("Error al actualizar tabla", str(ex))

    def _abrir_modal_fecha_id(self, e):
        print("🟡 Abriendo selector de fechas para ID")
        try:
            self.date_selector_id.fecha_inicio = self.fecha_inicio_id
            self.date_selector_id.fecha_fin = self.fecha_fin_id
            self.date_selector_id.abrir_dialogo()
        except Exception as ex:
            ModalAlert.mostrar_info("Error de Fecha", f"No se pudo abrir el calendario: {str(ex)}")

    def _abrir_modal_fecha_periodo(self, e):
        print("🟡 Abriendo selector de fechas para período")
        try:
            self.date_selector_periodo.fecha_inicio = self.fecha_inicio_periodo
            self.date_selector_periodo.fecha_fin = self.fecha_fin_periodo
            self.date_selector_periodo.abrir_dialogo()
        except Exception as ex:
            ModalAlert.mostrar_info("Error de Fecha", f"No se pudo abrir el calendario: {str(ex)}")

    def _build(self):
        self.content = ft.Column([
            ft.Text("Área actual: Pagos", style=ft.TextThemeStyle.TITLE_MEDIUM),
            self._build_buttons_area(),
            ft.Divider(),
            ft.Container(content=self.tabla_pagos, expand=True, padding=10, alignment=ft.alignment.center)
        ])

    def _build_buttons_area(self):
        return ft.Row([
            self._build_icon_button("Importar", ft.icons.FILE_DOWNLOAD, lambda _: print("📁 Importar presionado")),
            self._build_icon_button("Exportar", ft.icons.FILE_UPLOAD, lambda _: print("📤 Exportar presionado")),
            self._build_icon_button("Agregar", ft.icons.ADD, lambda _: print("➕ Agregar presionado")),

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
