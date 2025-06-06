from datetime import datetime
from decimal import Decimal
import flet as ft

from app.core.app_state import AppState
from app.models.payment_model import PaymentModel
from app.models.discount_model import DiscountModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.assistance_model import AssistanceModel
from app.models.prestamo_detalles_model import PrestamoDetallesModel
from app.views.containers.modal_alert import ModalAlert
from app.views.containers.date_modal_selector import DateModalSelector
from app.views.containers.modal_descuentos import ModalDescuentos
from app.views.containers.modal_pago_prestamos import ModalPagoPrestamo
from app.models.descuento_detalles_model import DescuentoDetallesModel

class PagosContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20, alignment=ft.alignment.top_center)
        self.page = AppState().page

        self.payment_model = PaymentModel()
        self.payment_model.crear_sp_horas_trabajadas_para_pagos()
        self.discount_model = DiscountModel()
        self.detalles_model = DescuentoDetallesModel()
        self.assistance_model = AssistanceModel()
        self.loan_payment_model = LoanPaymentModel()
        self.prestamo_detalles_model = PrestamoDetallesModel()

        self.fecha_inicio_periodo = None
        self.fecha_fin_periodo = None

        self.date_selector_periodo = DateModalSelector(on_dates_confirmed=self._generar_por_periodo)
        self.tabla_pagos = ft.DataTable(columns=[], rows=[], expand=True)
        self.resumen_pagos = ft.Text(value="", weight=ft.FontWeight.BOLD, size=14)

        self._build()
        self._cargar_pagos()
        

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
                            ft.Container(content=self.resumen_pagos, padding=10, alignment=ft.alignment.center),
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
        return ft.GestureDetector(on_tap=handler, content=ft.Row([ft.Icon(icon), ft.Text(text)], spacing=5))

    # ------------------------------------------------------------------ actions
# ... todo el código anterior igual ...

    def _abrir_modal_fecha_periodo(self, e):
        fechas_bloqueadas = self.assistance_model.get_fechas_generadas()
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

    def _cargar_pagos(self):
        try:
            from functools import partial

            self.tabla_pagos.columns = [
                ft.DataColumn(label=ft.Text("ID Pago")),
                ft.DataColumn(label=ft.Text("ID Empleado")),
                ft.DataColumn(label=ft.Text("Nombre")),
                ft.DataColumn(label=ft.Text("Fecha Pago")),
                ft.DataColumn(label=ft.Text("Horas")),
                ft.DataColumn(label=ft.Text("Sueldo/Hora")),
                ft.DataColumn(label=ft.Text("Monto Base")),
                ft.DataColumn(label=ft.Text("Descuentos")),
                ft.DataColumn(label=ft.Text("Préstamo")),
                ft.DataColumn(label=ft.Text("Total")),
                ft.DataColumn(label=ft.Text("Depósito")),
                ft.DataColumn(label=ft.Text("Efectivo")),
                ft.DataColumn(label=ft.Text("Saldo")),
                ft.DataColumn(label=ft.Text("Acciones")),
                ft.DataColumn(label=ft.Text("Estado")),
            ]

            self.tabla_pagos.rows.clear()
            total_pagado = 0.0

            query = (
                "SELECT "
                "p.id_pago, p.numero_nomina, p.fecha_pago, "
                "p.monto_base, p.monto_total, p.estado, "
                "p.pago_deposito, p.pago_efectivo, p.saldo, "
                "e.nombre_completo, e.sueldo_por_hora "
                "FROM pagos p "
                "JOIN empleados e ON p.numero_nomina = e.numero_nomina "
                "ORDER BY p.fecha_pago DESC"
            )

            pagos = self.payment_model.db.get_data_list(query, dictionary=True)

            if not pagos:
                self.tabla_pagos.rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text("-")) for _ in range(15)]))
            else:
                for p in pagos:
                    id_pago = p["id_pago"]
                    numero_nomina = p["numero_nomina"]
                    estado = p["estado"]

                    # ✅ Obtener horas trabajadas para la fecha específica
                    horas_str = "00:00:00"
                    resp_horas = self.payment_model.get_total_horas_trabajadas(
                        fecha_inicio=p["fecha_pago"],
                        fecha_fin=p["fecha_pago"],
                        numero_nomina=numero_nomina
                    )
                    if resp_horas["status"] == "success" and resp_horas["data"]:
                        horas_str = resp_horas["data"][0].get("total_horas_trabajadas", "00:00:00")

                    descuentos = self.discount_model.get_total_descuentos_por_pago(id_pago)
                    pago_prestamo = self.loan_payment_model.get_pago_prestamo_asociado(id_pago)
                    monto_total = max(0.0, float(p["monto_base"]) - descuentos - pago_prestamo)
                    pago_deposito = float(p["pago_deposito"] or 0)
                    pago_efectivo = monto_total - pago_deposito
                    saldo = 0.0

                    if estado == "pendiente":
                        if pago_efectivo < 25:
                            saldo = round(25 - pago_efectivo, 2)
                            pago_efectivo = 0
                        else:
                            saldo = round(pago_efectivo - 50, 2)
                            pago_efectivo = 50
                        if saldo < -25:
                            saldo = -25

                    acciones = ft.DataCell(ft.Text("✔️")) if estado == "pagado" else ft.DataCell(
                        ft.Row([
                            ft.IconButton(icon=ft.icons.CHECK, tooltip="Confirmar pago",
                                        on_click=partial(self._guardar_pago_confirmado, id_pago)),
                            ft.IconButton(icon=ft.icons.CANCEL, tooltip="Eliminar pago",
                                        on_click=partial(self._eliminar_pago, id_pago)),
                        ])
                    )

                    tiene_prestamo = self.loan_payment_model.tiene_prestamo_activo(numero_nomina)
                    icono_prestamo = ft.IconButton(
                        icon=ft.icons.PAID,
                        tooltip="Gestionar préstamo desde nómina",
                        on_click=lambda _, pago=p: ModalPagoPrestamo(pago, on_success=self._cargar_pagos).mostrar()
                    ) if tiene_prestamo else ft.IconButton(
                        icon=ft.icons.PAID,
                        tooltip="Sin préstamo activo",
                        disabled=True
                    )

                    cell_efectivo = ft.DataCell(ft.Text(f"${pago_efectivo:.2f}"))
                    cell_saldo = ft.DataCell(ft.Text(f"${saldo:.2f}"))

                    input_deposito = ft.TextField(
                        value=f"{pago_deposito:.2f}",
                        width=100,
                        height=35
                    )

                    if estado == "pendiente":
                        input_deposito.on_change = self._actualizar_pago_en_tiempo_real(
                            id_pago,
                            input_deposito,
                            cell_efectivo,
                            cell_saldo,
                            p["monto_base"]
                        )

                    self.tabla_pagos.rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(str(id_pago))),
                                ft.DataCell(ft.Text(str(numero_nomina))),
                                ft.DataCell(ft.Text(p["nombre_completo"])),
                                ft.DataCell(ft.Text(str(p["fecha_pago"]))),
                                ft.DataCell(ft.Text(horas_str)),
                                ft.DataCell(ft.Text(f"${p['sueldo_por_hora']:.2f}")),
                                ft.DataCell(ft.Text(f"${p['monto_base']:.2f}")),
                                ft.DataCell(
                                    ft.Row([
                                        ft.Text(f"${descuentos:.2f}"),
                                        ft.IconButton(icon=ft.icons.EDIT_NOTE, tooltip="Editar descuentos",
                                                    on_click=partial(self._abrir_modal_descuentos, p)),
                                    ])
                                ),
                                ft.DataCell(
                                    ft.Row([
                                        ft.Text(f"${pago_prestamo:.2f}"),
                                        icono_prestamo
                                    ])
                                ),
                                ft.DataCell(ft.Text(f"${monto_total:.2f}")),
                                ft.DataCell(input_deposito) if estado == "pendiente" else ft.DataCell(ft.Text(f"${pago_deposito:.2f}")),
                                cell_efectivo,
                                cell_saldo,
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





    def _guardar_pago_confirmado(self, id_pago: int):
        def confirmar():
            try:
                pago = self.payment_model.get_by_id(id_pago)
                if pago["status"] != "success" or not pago["data"]:
                    ModalAlert.mostrar_info("Error", f"No se encontró el pago con ID {id_pago}")
                    return

                pago_data = pago["data"]
                monto_base = Decimal(str(pago_data["monto_base"]))
                deposito = Decimal(str(pago_data["pago_deposito"]))
                total_descuentos = Decimal(str(self.discount_model.get_total_descuentos_por_pago(id_pago)))
                pago_prestamo = Decimal(str(self.loan_payment_model.get_pago_prestamo_asociado(id_pago)))

                monto_total = max(Decimal("0.0"), monto_base - total_descuentos - pago_prestamo)
                efectivo = max(Decimal("0.0"), monto_total - deposito)

                if efectivo > 25:
                    efectivo_redondeado = Decimal("50.0")
                    saldo = efectivo - efectivo_redondeado
                else:
                    efectivo_redondeado = Decimal("0.0")
                    saldo = -efectivo

                if saldo < -25:
                    saldo = Decimal("-25.0")
                    efectivo_redondeado = max(Decimal("0.0"), monto_total - deposito + Decimal("25.0"))

                campos = {
                    "estado": "pagado",
                    "monto_total": float(monto_total),
                    "pago_efectivo": float(efectivo_redondeado),
                    "saldo": float(saldo),
                    "fecha_pago": datetime.today().strftime("%Y-%m-%d"),
                }

                result = self.payment_model.update_pago(id_pago, campos)

                # Marcar préstamo como pagado desde nómina si aplica
                if float(pago_prestamo) > 0:
                    self.loan_payment_model.marcar_pago_como_desde_nomina(pago_data["numero_nomina"], id_pago)

                if result["status"] == "success":
                    self._cargar_pagos()
                else:
                    ModalAlert.mostrar_info("Error", result["message"])
            except Exception as ex:
                ModalAlert.mostrar_info("Error interno", str(ex))

        ModalAlert(
            title_text="Confirmar pago",
            message=f"¿Deseas confirmar el pago con ID {id_pago}?\nUna vez confirmado no podrá editarse.",
            on_confirm=confirmar,
        ).mostrar()


    def _agregar_pago_manual(self, numero_nomina, fecha, horas, sueldo_hora):
        try:
            monto_base = horas * sueldo_hora
            self.payment_model.insert_pago({
                "numero_nomina": numero_nomina,
                "fecha_pago": fecha,
                "total_horas_trabajadas": horas,
                "monto_base": monto_base,
                "estado": "pendiente",
                "pago_deposito": 0.0,
                "pago_efectivo": 0.0,
                "saldo": 0.0
            })
            self._cargar_pagos()
        except Exception as ex:
            ModalAlert.mostrar_info("Error al agregar pago", str(ex))


    def _eliminar_pago(self, id_pago: int):
        def eliminar():
            try:
                self.discount_model.eliminar_por_id_pago(id_pago)
                self.payment_model.db.run_query("DELETE FROM pagos WHERE id_pago = %s", (id_pago,))
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
                monto_transporte = float(data.get("monto_transporte", 0.0))
                monto_comida = float(data.get("monto_comida", 0.0))
                monto_extra = float(data.get("monto_extra", 0.0))
            except (ValueError, TypeError):
                ModalAlert.mostrar_info("Valor inválido", "Los montos deben ser numéricos. Ejemplo: 120.00")
                return

            self.discount_model.guardar_descuentos(
                id_pago=pago["id_pago"],
                numero_nomina=pago["numero_nomina"],
                descuentos=[
                    {
                        "tipo": "retenciones_imss",
                        "descripcion": "Cuota IMSS",
                        "monto": float(data.get("monto_imss", 0.0))
                    } if data.get("aplicar_imss") else None,
                    {
                        "tipo": "transporte",
                        "descripcion": "",
                        "monto": monto_transporte
                    } if data.get("aplicar_transporte") else None,
                    {
                        "tipo": "comida",
                        "descripcion": "",
                        "monto": monto_comida
                    } if data.get("aplicar_comida") else None,
                    {
                        "tipo": "descuento_extra",
                        "descripcion": data.get("descripcion_extra", "").strip(),
                        "monto": monto_extra
                    } if data.get("aplicar_extra") else None
                ]
            )

            self.detalles_model.guardar_detalles(
                id_pago=pago["id_pago"],
                detalles={
                    "aplicar_imss": data.get("aplicar_imss", False),
                    "monto_imss": float(data.get("monto_imss", 0.0)),
                    "aplicar_transporte": data.get("aplicar_transporte", False),
                    "monto_transporte": monto_transporte,
                    "aplicar_comida": data.get("aplicar_comida", False),
                    "monto_comida": monto_comida,
                    "aplicar_extra": data.get("aplicar_extra", False),
                    "monto_extra": monto_extra,
                    "descripcion_extra": data.get("descripcion_extra", "").strip()
                }
            )

            self._cargar_pagos()

        ModalDescuentos(pago, on_confirmar).mostrar()

    # ------------------------------------------------------------------ util

    def _parse_fecha(self, fecha):
        if isinstance(fecha, str):
            return datetime.strptime(fecha, "%Y-%m-%d").date()
        return fecha

    def _actualizar_pago_en_tiempo_real(self, id_pago, input_deposito, cell_pago_efectivo, cell_saldo, monto_base):
        def actualizar(_):
            try:
                deposito = float(input_deposito.value.strip() or 0.0)
                if deposito < 0:
                    raise ValueError("El depósito no puede ser negativo.")

                total_descuentos = self.discount_model.get_total_descuentos_por_pago(id_pago)
                pago_prestamo = self.loan_payment_model.get_pago_prestamo_asociado(id_pago) or 0.0

                monto_total_neto = monto_base - total_descuentos - pago_prestamo
                if monto_total_neto < 0:
                    monto_total_neto = 0.0

                max_deposito_permitido = monto_total_neto + 25
                if deposito > max_deposito_permitido:
                    deposito = max_deposito_permitido
                    input_deposito.value = f"{deposito:.2f}"
                    self.page.update()

                restante = monto_total_neto - deposito

                if restante >= 25:
                    pago_efectivo = 50.0
                    saldo = round(restante - pago_efectivo, 2)
                else:
                    pago_efectivo = 0.0
                    saldo = round(-restante, 2)

                if saldo < -25:
                    saldo = -25.0
                    pago_efectivo = max(0.0, monto_total_neto - deposito + 25)

                if pago_efectivo < 0:
                    pago_efectivo = 0.0
                    saldo = 0.0

                cell_pago_efectivo.content.value = f"${pago_efectivo:.2f}"
                cell_saldo.content.value = f"${saldo:.2f}"
                self.page.update()

                self.payment_model.update_pago(id_pago, {
                    "pago_deposito": deposito,
                    "pago_efectivo": pago_efectivo,
                    "saldo": saldo
                })

            except ValueError:
                ModalAlert.mostrar_info("Valor inválido", "Ingresa un valor numérico válido para el depósito.")

        return actualizar

    def _abrir_modal_prestamo(self, numero_nomina, e=None):
        ModalPagoPrestamo(numero_nomina, on_success=self._cargar_pagos).mostrar()
