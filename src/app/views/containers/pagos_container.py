from datetime import datetime
from decimal import Decimal
import flet as ft

from app.core.app_state import AppState
from app.models.payment_model import PaymentModel
from app.models.discount_model import DiscountModel
from app.models.assistance_model import AssistanceModel
from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.descuento_detalles_model import DescuentoDetallesModel
from app.views.containers.modal_alert import ModalAlert
from app.views.containers.date_modal_selector import DateModalSelector
from app.views.containers.modal_descuentos import ModalDescuentos
from app.views.containers.modal_pagos_prestamos import ModalPrestamos  # ✅ Se agregó este import
import functools



class PagosContainer(ft.Container):
    """Contenedor principal para gestionar pagos."""

    def __init__(self):
        super().__init__(expand=True, padding=20, alignment=ft.alignment.top_center)
        self.page = AppState().page

        # modelos principales
        self.payment_model = PaymentModel()
        self.payment_model.crear_sp_horas_trabajadas_para_pagos()
        self.discount_model = DiscountModel()
        self.assistance_model = AssistanceModel()
        self.loan_model = LoanModel()
        self.loan_payment_model = LoanPaymentModel()
        self.detalles_model = DescuentoDetallesModel()

        
        # rangos de fechas
        self.fecha_inicio_id = None
        self.fecha_fin_id = None
        self.fecha_inicio_periodo = None
        self.fecha_fin_periodo = None

        # almacenamiento temporal
        self.depositos_temporales = {}

        # controles de UI
        self.input_id = ft.TextField(
            label="ID Empleado", width=150, height=40,
            border_color=ft.colors.OUTLINE,
            on_change=self._validar_input_id
        )
        self.date_selector_id = DateModalSelector(on_dates_confirmed=self._set_fechas_id)
        self.date_selector_periodo = DateModalSelector(on_dates_confirmed=self._generar_por_periodo)

        self.tabla_pagos = ft.DataTable(columns=[], rows=[], expand=True)
        self.resumen_pagos = ft.Text(value="", weight=ft.FontWeight.BOLD, size=14)

        self._build()
        self._cargar_pagos()

    # ------------------------------------------------------------------ UI
    def _build(self):
        self.content = ft.Container(
            expand=True,
            padding=20,
            content=ft.Row(
                expand=True,
                scroll=ft.ScrollMode.ALWAYS,
                controls=[
                    ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.ALWAYS,
                        spacing=20,
                        controls=[
                            ft.Text("ÁREA DE PAGOS", style=ft.TextThemeStyle.TITLE_MEDIUM),
                            self._build_buttons_area(),
                            ft.Divider(),
                            self.tabla_pagos,
                            ft.Container(
                                content=self.resumen_pagos,
                                padding=10,
                                alignment=ft.alignment.center
                            ),
                        ],
                    )
                ],
            ),
        )

    def _build_buttons_area(self):
        return ft.Row(
            [
                self._icon_button("Importar", ft.icons.FILE_DOWNLOAD, lambda _: print("Importar")),
                self._icon_button("Exportar", ft.icons.FILE_UPLOAD, lambda _: print("Exportar")),
                ft.Container(
                    content=ft.ElevatedButton(
                        text="Pagos por Período",
                        icon=ft.icons.CALENDAR_VIEW_MONTH,
                        on_click=self._abrir_modal_fecha_periodo,
                        height=40,
                        style=ft.ButtonStyle(
                            bgcolor=ft.colors.WHITE,
                            shape=ft.RoundedRectangleBorder(radius=4),
                            side=ft.BorderSide(1, ft.colors.BLACK),
                        ),
                    ),
                    padding=5,
                    border_radius=10,
                    border=ft.border.all(1, ft.colors.OUTLINE),
                ),
            ],
            spacing=15,
        )

    def _icon_button(self, text, icon, handler):
        return ft.GestureDetector(
            on_tap=handler,
            content=ft.Row([ft.Icon(icon), ft.Text(text)], spacing=5)
        )


    # ------------------------------------------------------------------ actions
# ... todo el código anterior igual ...


    def _abrir_modal_fecha_periodo(self, e):
        fechas_bloqueadas = self.payment_model.get_fechas_utilizadas()
        fechas_bloqueadas = [
            datetime.strptime(f, "%Y-%m-%d").date() if isinstance(f, str) else f
            for f in fechas_bloqueadas
        ]
        self.date_selector_periodo.set_fechas_bloqueadas(fechas_bloqueadas)
        self.date_selector_periodo.abrir_dialogo()



    def _generar_por_periodo(self, inicio, fin):
        if not inicio or not fin:
            return
        inicio = self._parse_fecha(inicio)
        fin = self._parse_fecha(fin)

        min_fecha = self.assistance_model.get_fecha_minima_asistencia()
        max_fecha = self.assistance_model.get_fecha_maxima_asistencia()
        if not min_fecha or not max_fecha:
            ModalAlert.mostrar_info("Error de datos", "No se pudo obtener el rango válido de asistencias.")
            return

        if inicio < min_fecha or fin > max_fecha:
            ModalAlert.mostrar_info(
                "Fechas fuera de rango",
                f"Las fechas deben estar entre:\nMínima: {min_fecha}\nMáxima: {max_fecha}",
            )
            return

        self.fecha_inicio_periodo = inicio
        self.fecha_fin_periodo = fin
        self.date_selector_periodo.cerrar_dialogo()

        try:
            resultado = self.payment_model.generar_pagos_por_rango(fecha_inicio=inicio, fecha_fin=fin)
            if resultado["status"] == "success":
                # ✅ Marcar asistencias como generadas en la base de datos
                self.assistance_model.marcar_asistencias_como_generadas(
                    fecha_inicio=inicio.strftime("%Y-%m-%d"),
                    fecha_fin=fin.strftime("%Y-%m-%d")
                )
                ModalAlert.mostrar_info("Nómina Generada", resultado["message"])
            else:
                ModalAlert.mostrar_info("Error", resultado["message"])
            self._cargar_pagos()
        except Exception as ex:
            ModalAlert.mostrar_info("Error al generar pagos", str(ex))


    # ------------------------------------------------------------------ tabla
    def _cargar_pagos(self):
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
                ft.DataColumn(label=ft.Text("Préstamos")),
                ft.DataColumn(label=ft.Text("Saldo")),
                ft.DataColumn(label=ft.Text("Depósito")),
                ft.DataColumn(label=ft.Text("Efectivo")),
                ft.DataColumn(label=ft.Text("Total")),
                ft.DataColumn(label=ft.Text("Acciones")),
                ft.DataColumn(label=ft.Text("Estado")),
            ]

            self.tabla_pagos.rows.clear()
            total_pagado = 0.0

            query = (
                "SELECT p.id_pago, p.numero_nomina, p.fecha_pago, p.total_horas_trabajadas, "
                "p.monto_base, p.monto_total, p.estado, p.saldo, "
                "p.pago_deposito, p.pago_efectivo, e.nombre_completo, e.sueldo_por_hora "
                "FROM pagos p JOIN empleados e ON p.numero_nomina = e.numero_nomina "
                "ORDER BY p.fecha_pago DESC"
            )

            pagos = self.payment_model.db.get_data_list(query, dictionary=True)

            if not pagos:
                self.tabla_pagos.rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text("-")) for _ in range(15)]))
            else:
                for p in pagos:
                    if not p:
                        continue

                    id_pago = p["id_pago"]
                    numero_nomina = p["numero_nomina"]
                    estado = p["estado"]

                    descuentos = self._sumar_descuentos_totales(id_pago)
                    prestamos = self.loan_payment_model.get_total_prestamos_por_pago(id_pago)

                    acciones = (
                        ft.DataCell(ft.Text("✔️")) if estado == "pagado" else
                        ft.DataCell(
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.CHECK,
                                    tooltip="Confirmar pago",
                                    on_click=lambda e, pid=id_pago: self._guardar_pago_confirmado(pid)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.CANCEL,
                                    tooltip="Eliminar pago",
                                    on_click=lambda e, pid=id_pago: self._eliminar_pago(pid)
                                ),
                            ])
                        )
                    )

                    prestamo_activo = self.loan_model.get_prestamo_activo_por_empleado(numero_nomina)  # ✅ corregido
                    boton_prestamo = ft.IconButton(
                        icon=ft.icons.EDIT_NOTE,
                        tooltip="Editar préstamos" if prestamo_activo else "Sin préstamo activo",
                        icon_color=ft.colors.BLUE if prestamo_activo else ft.colors.GREY,
                        disabled=not prestamo_activo,
                        on_click=lambda e, pago=p: self._abrir_modal_prestamos(pago, e)
                    )




                    self.tabla_pagos.rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(str(id_pago))),
                                ft.DataCell(ft.Text(str(numero_nomina))),
                                ft.DataCell(ft.Text(p["nombre_completo"])),
                                ft.DataCell(ft.Text(str(p["fecha_pago"]))),
                                ft.DataCell(ft.Text(str(p["total_horas_trabajadas"]))),
                                ft.DataCell(ft.Text(f"${p['sueldo_por_hora']:.2f}")),
                                ft.DataCell(ft.Text(f"${p['monto_base']:.2f}")),
                                ft.DataCell(
                                    ft.Row([
                                        ft.Text(f"${descuentos:.2f}"),
                                        ft.IconButton(
                                            icon=ft.icons.EDIT_NOTE,
                                            tooltip="Editar descuentos",
                                            on_click=lambda e, pago=p: self._abrir_modal_descuentos(pago)
                                        ),
                                    ])
                                ),
                                ft.DataCell(
                                    ft.Row([
                                        ft.Text(f"${prestamos:.2f}"),
                                        boton_prestamo
                                    ])
                                ),
                                ft.DataCell(ft.Text(f"${p['saldo']:.2f}")),
                                ft.DataCell(ft.Text(f"${p['pago_deposito']:.2f}")),
                                ft.DataCell(ft.Text(f"${p['pago_efectivo']:.2f}")),
                                ft.DataCell(ft.Text(f"${p['monto_total']:.2f}")),
                                acciones,
                                ft.DataCell(ft.Text("Pagado" if estado == "pagado" else "Pendiente")),
                            ]
                        )
                    )

                    if estado == "pagado":
                        total_pagado += float(p["monto_total"])

            self.resumen_pagos.value = f"Total pagado: ${total_pagado:.2f}"
            self.page.update()

        except Exception as ex:
            ModalAlert.mostrar_info("Error al cargar pagos", str(ex))



    def _sumar_descuentos_totales(self, id_pago):
        detalles = self.detalles_model.obtener_por_id_pago(id_pago)
        return (
            Decimal(detalles.get("monto_imss", 0)) +
            Decimal(detalles.get("monto_transporte", 0)) +
            Decimal(detalles.get("monto_comida", 0)) +
            Decimal(detalles.get("monto_extra", 0))
        )

    def _sumar_prestamos_totales(self, id_pago: int) -> Decimal:
        try:
            query = """
                SELECT COALESCE(SUM(monto_pagado + interes_aplicado), 0) AS total
                FROM pagos_prestamo
                WHERE id_pago = %s
            """
            resultado = self.loan_payment_model.db.get_data(query, (id_pago,), dictionary=True)
            return Decimal(resultado.get("total", 0) or 0)
        except Exception as ex:
            print(f"❌ Error al sumar préstamos: {ex}")
            return Decimal(0)


    def _eliminar_pago(self, id_pago: int):
        def eliminar():
            try:
                resultado = self.payment_model.delete_pago(id_pago)
                if resultado["status"] == "success":
                    self._cargar_pagos()
                else:
                    ModalAlert.mostrar_info("Error", resultado["message"])
            except Exception as ex:
                ModalAlert.mostrar_info("Error al eliminar", str(ex))

        ModalAlert(
            title_text="Eliminar Pago",
            message=f"¿Estás seguro de eliminar el pago con ID {id_pago}?",
            on_confirm=eliminar,
        ).mostrar()

    def _guardar_pago_confirmado(self, id_pago: int):
        try:
            descuentos = self.detalles_model.obtener_por_id_pago(id_pago)

            confirmacion = self.payment_model.update_pago_completo(
                id_pago=id_pago,
                descuentos=descuentos,
                estado="pagado"
            )

            if confirmacion["status"] == "success":
                ModalAlert.mostrar_info("Éxito", confirmacion["message"])
                self._cargar_pagos()
            else:
                ModalAlert.mostrar_info("Error", confirmacion["message"])

        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo confirmar el pago: {str(ex)}")



    def _abrir_modal_descuentos(self, pago: dict):
        print(f"🟢 Llamando ModalDescuentos para pago ID: {pago['id_pago']}")
        def on_confirmar(_):
            self._cargar_pagos()
        ModalDescuentos(pago_data=pago, on_confirmar=on_confirmar).mostrar()

    def _abrir_modal_prestamos(self, pago: dict, e=None):
        print(f"🟢 Verificando préstamo activo para empleado {pago['numero_nomina']} (pago ID: {pago['id_pago']})")

        prestamo = self.loan_model.get_prestamo_activo_por_empleado(pago["numero_nomina"])  # ✅ corregido
        if not prestamo:
            ModalAlert.mostrar_info(
                "Sin préstamo",
                f"El empleado {pago['numero_nomina']} no tiene préstamos activos registrados."
            )
            return

        def on_confirmar(_):
            self._cargar_pagos()

        ModalPrestamos(pago_data=pago, on_confirmar=on_confirmar).mostrar()




    # ------------------------------------------------------------------ util
    def _set_fechas_id(self, inicio, fin):
        inicio = self._parse_fecha(inicio)
        fin = self._parse_fecha(fin)

        min_fecha = self.assistance_model.get_fecha_minima_asistencia()
        max_fecha = self.assistance_model.get_fecha_maxima_asistencia()
        if not min_fecha or not max_fecha:
            ModalAlert.mostrar_info("Error de datos", "No se pudo obtener el rango válido de asistencias.")
            return

        if inicio < min_fecha or fin > max_fecha:
            ModalAlert.mostrar_info(
                "Fechas fuera de rango",
                f"Las fechas deben estar entre:\nMínima: {min_fecha}\nMáxima: {max_fecha}",
            )
            return

        # Verificar si ya existe un pago confirmado en el rango para el ID actual
        if not self.input_id.value.isdigit():
            ModalAlert.mostrar_info("ID inválido", "Debes ingresar un número de nómina válido.")
            return

        numero_nomina = int(self.input_id.value)

        existe = self.payment_model.existe_pago_para_fecha(
            numero_nomina=numero_nomina,
            fecha=fin.strftime("%Y-%m-%d"),
            incluir_pendientes=False
        )
        if existe:
            ModalAlert.mostrar_info(
                "Ya pagado",
                f"Ya existe un pago confirmado para el empleado {numero_nomina} en la fecha {fin.strftime('%Y-%m-%d')}"
            )
            return

        self.fecha_inicio_id = inicio
        self.fecha_fin_id = fin
        self.date_selector_id.cerrar_dialogo()


    def _parse_fecha(self, fecha):
        if isinstance(fecha, str):
            return datetime.strptime(fecha, "%Y-%m-%d").date()
        return fecha


    def _validar_input_id(self, e):
        texto = self.input_id.value.strip()
        self.input_id.border_color = ft.colors.OUTLINE if not texto or texto.isdigit() else ft.colors.RED_400
        self.page.update()

