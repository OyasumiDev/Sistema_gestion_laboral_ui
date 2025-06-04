from datetime import datetime
from decimal import Decimal, InvalidOperation
import flet as ft

from app.core.app_state import AppState
from app.core.enums.e_payment_model import E_PAYMENT
from app.models.payment_model import PaymentModel
from app.models.discount_model import DiscountModel
from app.models.assistance_model import AssistanceModel
from app.views.containers.modal_alert import ModalAlert
from app.views.containers.date_modal_selector import DateModalSelector
from app.views.containers.modal_descuentos import ModalDescuentos


class PagosContainer(ft.Container):
    """Contenedor principal para gestionar pagos."""

    def __init__(self):
        super().__init__(expand=True, padding=20, alignment=ft.alignment.top_center)
        self.page = AppState().page

        # modelos
        self.payment_model = PaymentModel()
        self.payment_model.crear_sp_horas_trabajadas_para_pagos()
        self.discount_model = DiscountModel()
        self.assistance_model = AssistanceModel()

        # rangos de fechas
        self.fecha_inicio_periodo = None
        self.fecha_fin_periodo = None

        # mapas para edicion de depositos
        self.inputs_deposito: dict[int, ft.TextField] = {}
        self.labels_efectivo: dict[int, ft.Text] = {}
        self.monto_base_map: dict[int, float] = {}
        self.descuentos_map: dict[int, float] = {}
        self.depositos_temporales: dict[int, Decimal] = {}

        # controles
        fechas_bloqueadas = self.assistance_model.get_fechas_generadas()
        self.date_selector_periodo = DateModalSelector(
            on_dates_confirmed=self._generar_por_periodo,
            fechas_bloqueadas=fechas_bloqueadas,
        )

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
                            ft.Container(content=self.resumen_pagos, padding=10,
                                         alignment=ft.alignment.center),
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
                        text="Buscar Período",
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
        return ft.GestureDetector(on_tap=handler, content=ft.Row([ft.Icon(icon), ft.Text(text)], spacing=5))

    # ------------------------------------------------------------------ actions
    def _abrir_modal_fecha_periodo(self, e):
        self.date_selector_periodo.fecha_inicio = self.fecha_inicio_periodo
        self.date_selector_periodo.fecha_fin = self.fecha_fin_periodo
        self.date_selector_periodo.set_fechas_bloqueadas(
            self.assistance_model.get_fechas_generadas()
        )
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
                ft.DataColumn(label=ft.Text("Pago Depósito")),
                ft.DataColumn(label=ft.Text("Pago Efectivo")),
                ft.DataColumn(label=ft.Text("Descuentos")),
                ft.DataColumn(label=ft.Text("Total")),
                ft.DataColumn(label=ft.Text("Acciones")),
                ft.DataColumn(label=ft.Text("Estado")),
            ]
            self._extender_columnas_pagos()

            self.tabla_pagos.rows.clear()
            self.inputs_deposito.clear()
            self.labels_efectivo.clear()
            self.monto_base_map.clear()
            self.descuentos_map.clear()
            total_pagado = 0.0

            query = (
                "SELECT p.id_pago, p.numero_nomina, p.fecha_pago, p.total_horas_trabajadas, "
                "p.monto_base, p.pago_deposito, p.pago_efectivo, p.monto_total, p.estado, "
                "e.nombre_completo, e.sueldo_por_hora "
                "FROM pagos p JOIN empleados e ON p.numero_nomina = e.numero_nomina "
                "ORDER BY p.fecha_pago DESC"
            )
            pagos = self.payment_model.db.get_data_list(query, dictionary=True)

            if not pagos:
                self.tabla_pagos.rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text("-")) for _ in range(13)]))
            else:
                for p in pagos:
                    if not p:
                        continue
                    descuentos = self.discount_model.get_total_descuentos_por_pago(p["id_pago"])
                    estado = p["estado"]
                    self.monto_base_map[p["id_pago"]] = float(p["monto_base"])
                    self.descuentos_map[p["id_pago"]] = float(descuentos)

                    if estado == "pendiente":
                        valor_dep = self.depositos_temporales.get(
                            p["id_pago"], Decimal(str(p["pago_deposito"]))
                        )
                        input_dep = ft.TextField(
                            value=f"{valor_dep:.2f}",
                            width=90,
                            height=28,
                            dense=True,
                            text_align=ft.TextAlign.RIGHT,
                            keyboard_type=ft.KeyboardType.NUMBER,
                            on_change=lambda e, pid=p["id_pago"]: self._on_cambio_deposito(pid, e)
                        )
                        self.inputs_deposito[p["id_pago"]] = input_dep
                        deposito_cell = ft.DataCell(input_dep)
                        efectivo_val = Decimal(str(p["monto_base"])) - Decimal(str(descuentos)) - valor_dep
                        efectivo_label = ft.Text(f"${efectivo_val:.2f}")
                        self.labels_efectivo[p["id_pago"]] = efectivo_label
                        efectivo_cell = ft.DataCell(efectivo_label)
                    else:
                        deposito_cell = ft.DataCell(ft.Text(f"${p['pago_deposito']:.2f}"))
                        efectivo_cell = ft.DataCell(ft.Text(f"${p['pago_efectivo']:.2f}"))

                    if estado == "pagado":
                        acciones = ft.DataCell(ft.Text("✔️"))
                    else:
                        acciones = ft.DataCell(
                            ft.Row([
                                ft.IconButton(icon=ft.icons.CHECK, tooltip="Confirmar pago",
                                              on_click=lambda e, pid=p["id_pago"]: self._guardar_pago_confirmado(pid)),
                                ft.IconButton(icon=ft.icons.CANCEL, tooltip="Eliminar pago",
                                              on_click=lambda e, pid=p["id_pago"]: self._eliminar_pago(pid)),
                            ])
                        )

                    self.tabla_pagos.rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(str(p["id_pago"]))),
                                ft.DataCell(ft.Text(str(p["numero_nomina"]))),
                                ft.DataCell(ft.Text(p["nombre_completo"])),
                                ft.DataCell(ft.Text(str(p["fecha_pago"]))),
                                ft.DataCell(ft.Text(str(p["total_horas_trabajadas"]))),
                                ft.DataCell(ft.Text(f"${p['sueldo_por_hora']:.2f}")),
                                ft.DataCell(ft.Text(f"${p['monto_base']:.2f}")),
                                deposito_cell,
                                efectivo_cell,
                                ft.DataCell(
                                    ft.Row(
                                        [
                                            ft.Text(f"${descuentos:.2f}"),
                                            ft.IconButton(
                                                icon=ft.icons.EDIT_NOTE,
                                                tooltip="Editar descuentos",
                                                on_click=lambda e, pago=p: self._abrir_modal_descuentos(pago)
                                            ),
                                        ]
                                    )
                                ),
                                ft.DataCell(ft.Text(f"${p['monto_total']:.2f}")),
                                acciones,
                                ft.DataCell(ft.Text("Pagado" if estado == "pagado" else "Pendiente")),
                            ]
                        )
                    )

                    if estado == "pagado":
                        total_pagado += float(p["monto_total"])

            self.resumen_pagos.value = f"Total pagado: ${total_pagado:.2f}"
            fechas = self.assistance_model.get_fechas_generadas()
            self.date_selector_periodo.set_fechas_bloqueadas(fechas)
            self.page.update()
        except Exception as ex:
            ModalAlert.mostrar_info("Error al cargar pagos", str(ex))

    def _on_cambio_deposito(self, id_pago: int, e):
        campo = e.control
        valor = campo.value.strip()
        try:
            deposito = Decimal(valor) if valor else Decimal("0")
        except InvalidOperation:
            campo.error_text = "Formato inválido"
            self.page.update()
            return

        if self._validar_pago_deposito(id_pago, deposito, campo):
            self.depositos_temporales[id_pago] = deposito
        self._actualizar_pago_efectivo_en_tabla(id_pago, deposito)

    def _guardar_pago_confirmado(self, id_pago: int):
        def confirmar():
            try:
                pago = self.payment_model.get_by_id(id_pago)
                if pago["status"] != "success" or not pago["data"]:
                    ModalAlert.mostrar_info("Error", f"No se encontró el pago con ID {id_pago}")
                    return

                try:
                    monto_base = Decimal(str(pago["data"]["monto_base"]))
                    if id_pago in self.depositos_temporales:
                        deposito = self.depositos_temporales[id_pago]
                    else:
                        deposito_field = self.inputs_deposito.get(id_pago)
                        deposito = (
                            Decimal(deposito_field.value)
                            if deposito_field
                            else Decimal(str(pago["data"]["pago_deposito"]))
                        )
                except (InvalidOperation, ValueError):
                    ModalAlert.mostrar_info("Valor inválido", "Depósito debe ser numérico")
                    return

                if not self._validar_pago_deposito(id_pago, deposito, self.inputs_deposito.get(id_pago, ft.TextField())):
                    return

                descuentos = Decimal(str(self.descuentos_map.get(id_pago, self.discount_model.get_total_descuentos_por_pago(id_pago))))
                efectivo = monto_base - descuentos - deposito
                monto_total = max(Decimal("0.0"), efectivo + deposito - descuentos)

                campos = {
                    E_PAYMENT.PAGO_DEPOSITO.value: float(deposito),
                    E_PAYMENT.PAGO_EFECTIVO.value: float(efectivo),
                    E_PAYMENT.MONTO_TOTAL.value: float(monto_total),
                    E_PAYMENT.ESTADO.value: "pagado",
                    E_PAYMENT.FECHA_PAGO.value: datetime.today().strftime("%Y-%m-%d"),
                }
                result = self.payment_model.update_pago(id_pago, campos)
                if result["status"] == "success":
                    self.depositos_temporales.pop(id_pago, None)
                    self._cargar_pagos()
                else:
                    ModalAlert.mostrar_info("Error", result["message"])
            except Exception as ex:
                ModalAlert.mostrar_info("Error interno", str(ex))

        ModalAlert(
            title_text="Confirmar pago",
            message=f"¿Deseas confirmar el pago con ID {id_pago}?",
            on_confirm=confirmar,
        ).mostrar()

    def _eliminar_pago(self, id_pago: int):
        def eliminar():
            try:
                self.discount_model.eliminar_por_id_pago(id_pago)
                self.payment_model.db.run_query("DELETE FROM pagos WHERE id_pago = %s", (id_pago,))
                self.depositos_temporales.pop(id_pago, None)
                self._cargar_pagos()
            except Exception as ex:
                ModalAlert.mostrar_info("Error al eliminar", str(ex))

        ModalAlert(
            title_text="Eliminar Pago",
            message=f"¿Estás seguro de eliminar el pago con ID {id_pago}?",
            on_confirm=eliminar,
        ).mostrar()

    def _abrir_modal_descuentos(self, pago: dict):
        def on_confirmar(data):
            try:
                monto_transporte = float(data["monto_transporte"])
                descuento_extra = float(data["descuento_extra"])
            except (ValueError, TypeError):
                ModalAlert.mostrar_info("Valor inválido", "Los montos deben ser numéricos. Ejemplo: 120.00")
                return

            self.discount_model.guardar_descuentos_editables(
                id_pago=pago["id_pago"],
                aplicar_imss=data["aplicar_imss"],
                aplicar_transporte=data["aplicar_transporte"],
                monto_transporte=monto_transporte,
                aplicar_comida=data["aplicar_comida"],
                estado_comida=data["estado_comida"],
                descuento_extra=descuento_extra,
                descripcion_extra=data["descripcion_extra"],
                numero_nomina=pago["numero_nomina"],
            )
            self._cargar_pagos()

        ModalDescuentos(pago, on_confirmar).mostrar()

    def _validar_pago_deposito(self, id_pago: int, deposito: Decimal, campo: ft.TextField) -> bool:
        """Valida que el depósito sea numérico y no supere el monto base."""
        monto_base = Decimal(str(self.monto_base_map.get(id_pago, 0)))
        es_valido = True
        if deposito < 0:
            campo.error_text = "No negativo"
            campo.border_color = ft.colors.RED
            es_valido = False
        elif deposito > monto_base:
            campo.error_text = "Mayor al monto base"
            campo.border_color = ft.colors.RED
            es_valido = False
        else:
            campo.error_text = None
            campo.border_color = None
        return es_valido

    def _actualizar_pago_efectivo_en_tabla(self, id_pago: int, deposito: Decimal):
        monto_base = Decimal(str(self.monto_base_map.get(id_pago, 0)))
        descuentos = Decimal(str(self.descuentos_map.get(id_pago, 0)))
        efectivo = max(Decimal("0"), monto_base - descuentos - deposito)
        etiqueta = self.labels_efectivo.get(id_pago)
        if etiqueta:
            etiqueta.value = f"${efectivo:.2f}"
        self.page.update()

    def _extender_columnas_pagos(self):
        for col in self.tabla_pagos.columns:
            col.auto_resize = True

    # ------------------------------------------------------------------ util
    def _parse_fecha(self, fecha):
        if isinstance(fecha, str):
            return datetime.strptime(fecha, "%Y-%m-%d").date()
        return fecha
