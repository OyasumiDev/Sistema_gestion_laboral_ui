# views/containers/pagos_container.py
from __future__ import annotations

from datetime import datetime, date
from typing import List, Dict, Any
import flet as ft

# Core / Models
from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert
from app.views.containers.modal_descuentos import ModalDescuentos
from app.views.containers.date_modal_selector import DateModalSelector

# Modal de préstamos para NÓMINA (multi-préstamo, auto-save)
from app.views.containers.modal_prestamos_nomina import ModalPrestamosNomina

from app.models.payment_model import PaymentModel
from app.models.discount_model import DiscountModel
from app.models.assistance_model import AssistanceModel
from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.descuento_detalles_model import DescuentoDetallesModel
from app.models.detalles_pagos_prestamo_model import DetallesPagosPrestamoModel

# Helpers
from app.helpers.pagos.payment_view_math import PaymentViewMath
from app.helpers.pagos.pagos_repo import PagosRepo

# Row helper (con fallback)
try:
    from app.helpers.pagos.row_refresh import PaymentRowRefresh
except ModuleNotFoundError:
    from app.helpers.pagos.row_refresh import PaymentRowRefresh  # fallback

# Scroll helper
from app.helpers.pagos.scroll_pagos_helper import PagosScrollHelper

# Botones header (fábrica)
from app.helpers.boton_factory import (
    crear_boton_importar,
    crear_boton_exportar,
    crear_boton_agregar,
)


class PagosContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=0, alignment=ft.alignment.top_center)
        self.page = AppState().page

        # Modelos
        self.payment_model = PaymentModel()
        self.payment_model.crear_sp_horas_trabajadas_para_pagos()
        self.discount_model = DiscountModel()
        self.assistance_model = AssistanceModel()
        self.loan_model = LoanModel()
        self.loan_payment_model = LoanPaymentModel()
        self.detalles_desc_model = DescuentoDetallesModel()
        self.detalles_prestamo_model = DetallesPagosPrestamoModel()

        # Helpers
        self.repo = PagosRepo(payment_model=self.payment_model)
        self.math = PaymentViewMath(
            discount_model=self.discount_model,
            detalles_desc_model=self.detalles_desc_model,
            loan_payment_model=self.loan_payment_model,
            detalles_prestamo_model=self.detalles_prestamo_model,
        )
        self.rowui = PaymentRowRefresh()           # fila con Text + TextField depósito
        self.scroll = PagosScrollHelper()          # scroll robusto

        # Estado UI
        self.depositos_temporales: dict[int, float] = {}
        self._deposito_buffer: dict[int, str] = {}

        # Selector de fechas
        self.selector_fechas = DateModalSelector(on_dates_confirmed=self._generar_por_fechas)

        # Controles UI
        self.input_id = ft.TextField(
            label="ID Empleado",
            width=150,
            height=40,
            border_color=ft.colors.OUTLINE,
            on_change=self._validar_input_id,
        )

        self.tabla_pagos = ft.DataTable(columns=[], rows=[], expand=False)  # no expand -> overflow H real
        self.resumen_pagos = ft.Text(value="", weight=ft.FontWeight.BOLD, size=14)

        self._build()
        self._cargar_pagos()

    # ---------------- UI ----------------
    def _build(self):
        # DataTable medidas
        self.tabla_pagos.expand = False
        self.tabla_pagos.column_spacing = 12
        self.tabla_pagos.heading_row_height = 40
        self.tabla_pagos.data_row_min_height = 38
        self.tabla_pagos.data_row_max_height = 42

        def H(text: str, w: int) -> ft.DataColumn:
            return ft.DataColumn(label=ft.Container(ft.Text(text), width=w))

        # Orden de columnas (usamos el índice 14 para reemplazar Acciones)
        self.tabla_pagos.columns = [
            H("ID Pago",       70),   # 0
            H("ID Empleado",   90),   # 1
            H("Nombre",       150),   # 2
            H("Fecha Pago",   110),   # 3
            H("Horas",         70),   # 4
            H("Sueldo/Hora",  100),   # 5
            H("Monto Base",   110),   # 6
            H("Descuentos",   120),   # 7
            H("Préstamos",    110),   # 8
            H("Saldo",        100),   # 9
            H("Depósito",     120),   # 10
            H("Efectivo",     110),   # 11
            H("Total",        110),   # 12
            H("Ediciones",    100),   # 13
            H("Acciones",     120),   # 14  ← **Reemplazamos aquí**
            H("Estado",        90),   # 15
        ]

        # Header / Footer
        header_bar = ft.Row(
            controls=[
                crear_boton_importar(lambda: self._no_impl("Importar")),
                crear_boton_exportar(lambda: self._no_impl("Exportar")),
                crear_boton_agregar(self._abrir_modal_fechas_disponibles),
            ],
            spacing=10,
            alignment=ft.MainAxisAlignment.START,
        )
        header = ft.Column(
            spacing=8,
            controls=[
                ft.Text("ÁREA DE PAGOS", style=ft.TextThemeStyle.TITLE_MEDIUM),
                header_bar,
            ],
        )
        footer = ft.Container(self.resumen_pagos, padding=10, alignment=ft.alignment.center)

        # Scaffold con scroll ALWAYS
        self.content = self.scroll.build_scaffold(
            page=self.page,
            datatable=self.tabla_pagos,
            header=header,
            footer=footer,
            required_min_width=1820,
        )

    def _no_impl(self, what: str):
        ModalAlert.mostrar_info("Próximamente", f"La acción '{what}' se implementará más adelante.")

    # ------------- Carga / Tabla -------------
    def _cargar_pagos(self):
        try:
            self.tabla_pagos.rows.clear()
            pagos = self.repo.listar_pagos(order_desc=True)

            if not pagos:
                self.tabla_pagos.rows.append(
                    ft.DataRow(cells=[ft.DataCell(ft.Text("-")) for _ in range(len(self.tabla_pagos.columns))])
                )
                self.resumen_pagos.value = "Total pagado: $0.00"
                if self.page:
                    self.page.update()
                return

            for p in pagos:
                id_pago = int(p.get("id_pago_nomina") or p.get("id_pago"))

                # Depósito visible: buffer si existe; si no, temporal/DB
                if id_pago in self._deposito_buffer:
                    try:
                        deposito_ui = float(self._deposito_buffer[id_pago])
                    except Exception:
                        deposito_ui = float(self.depositos_temporales.get(id_pago, p.get("pago_deposito", 0.0) or 0.0))
                else:
                    deposito_ui = float(self.depositos_temporales.get(id_pago, p.get("pago_deposito", 0.0) or 0.0))

                calc = self.math.recalc_from_pago_row(p, deposito_ui)

                # Handlers del Depósito (buffer + commit en blur/submit)
                def _make_on_change(pid: int):
                    def _handler(value: str):
                        self._deposito_buffer[pid] = value or ""
                    return _handler

                def _make_on_commit(pid: int):
                    def _handler():
                        txt = self._deposito_buffer.get(pid, "")
                        try:
                            val = float(txt)
                        except Exception:
                            val = 0.0
                        self.depositos_temporales[pid] = val
                        self._actualizar_fila_pago(pid)
                    return _handler

                # Señal rápida de préstamo activo para habilitar botón en la fila
                tiene_prestamo_activo = bool(
                    self.loan_model.get_prestamo_activo_por_empleado(int(p["numero_nomina"]))
                )

                esta_pagado = (str(p.get("estado", "")).lower() == "pagado")

                # Fila base renderizada por el helper
                row = self.rowui.build_row(
                    p,
                    descuentos_value=calc["descuentos_view"],
                    prestamos_value=calc["prestamos_view"],
                    saldo_value=calc["saldo_ajuste"],
                    deposito_value=deposito_ui,
                    efectivo_value=calc["efectivo"],
                    total_value=calc["total_vista"],
                    esta_pagado=esta_pagado,
                    # EDICIONES (modales)
                    on_editar_descuentos=self._abrir_modal_descuentos,
                    on_editar_prestamos=self._abrir_modal_prestamos,
                    tiene_prestamo_activo=tiene_prestamo_activo,
                    # ACCIONES (callbacks – el UI lo reemplazamos abajo)
                    on_confirmar=self._guardar_pago_confirmado,
                    on_eliminar=self._eliminar_pago,
                    # Depósito buffer
                    on_deposito_change=_make_on_change(id_pago),
                    on_deposito_blur=_make_on_commit(id_pago),
                    on_deposito_submit=_make_on_commit(id_pago),
                )

                # --- Reemplazo de la celda "Acciones" (col idx 14) por tu UI con CHECK ---
                try:
                    acciones_idx = 14
                    if len(row.cells) > acciones_idx:
                        # Botón CONFIRMAR (check)
                        btn_confirmar = ft.IconButton(
                            icon=ft.icons.CHECK,
                            icon_color=ft.colors.GREEN_600,
                            tooltip="Guardar",
                            disabled=esta_pagado,  # deshabilitar si ya está pagado
                            on_click=(lambda _, pid=id_pago: self._guardar_pago_confirmado(pid)),
                        )
                        # Botón ELIMINAR (trash)
                        btn_eliminar = ft.IconButton(
                            icon=ft.icons.DELETE_OUTLINE,
                            icon_color=ft.colors.RED_500,
                            tooltip="Eliminar pago",
                            on_click=(lambda _, pid=id_pago: self._eliminar_pago(pid)),
                        )
                        row.cells[acciones_idx] = ft.DataCell(
                            ft.Row([btn_confirmar, btn_eliminar], spacing=6, alignment=ft.MainAxisAlignment.START)
                        )
                except Exception:
                    # si por alguna razón cambia la forma del helper, no rompemos la fila
                    pass

                self.tabla_pagos.rows.append(row)

            total_pagado = self.repo.total_pagado_confirmado()
            self.resumen_pagos.value = f"Total pagado: ${float(total_pagado):.2f}"
            if self.page:
                self.page.update()

        except Exception as ex:
            ModalAlert.mostrar_info("Error al cargar pagos", str(ex))

    # ------------- Recalculo por fila -------------
    def _actualizar_fila_pago(self, id_pago_nomina: int):
        try:
            row = self.rowui.get_row(self.tabla_pagos, id_pago_nomina)
            if not row:
                return

            p_db = self.repo.obtener_pago(id_pago_nomina)
            if not p_db:
                return

            buf = self._deposito_buffer.get(id_pago_nomina, None)
            if buf is not None:
                try:
                    deposito_ui = float(buf)
                except Exception:
                    deposito_ui = 0.0
            else:
                deposito_ui = float(
                    self.depositos_temporales.get(id_pago_nomina, p_db.get("pago_deposito", 0.0) or 0.0)
                )

            calc = self.math.recalc_from_pago_row(p_db, deposito_ui)

            # Pintar sólo la fila (mantiene foco en Depósito)
            self.rowui.set_descuentos(row, calc["descuentos_view"])
            self.rowui.set_prestamos(row, calc["prestamos_view"])
            self.rowui.set_saldo(row, calc["saldo_ajuste"])
            self.rowui.set_efectivo(row, calc["efectivo"])
            self.rowui.set_total(row, calc["total_vista"])
            # feedback visual depósito
            self.rowui.set_deposito_border_color(
                row, ft.colors.RED if deposito_ui > calc["total_vista"] + 1e-9 else None
            )

            row.update()
        except Exception as ex:
            print(f"❌ Error al actualizar fila: {ex}")

    # ------------- Acciones -------------
    def _guardar_pago_confirmado(self, id_pago_nomina: int):
        try:
            res = self.repo.confirmar_pago(id_pago_nomina)
            if res.get("status") != "success" and hasattr(self.payment_model, "update_pago_completo"):
                detalles_desc = self.detalles_desc_model.obtener_por_id_pago(id_pago_nomina) or {}
                res = self.payment_model.update_pago_completo(
                    id_pago=id_pago_nomina, descuentos=detalles_desc, estado="pagado"
                )

            if res.get("status") == "success":
                row = self.rowui.get_row(self.tabla_pagos, id_pago_nomina)
                if row:
                    self.rowui.set_estado_pagado(row)
                    # Deshabilitar botón CHECK tras confirmar
                    try:
                        acciones_idx = 14
                        if len(row.cells) > acciones_idx:
                            acciones_row = row.cells[acciones_idx].content
                            if isinstance(acciones_row, ft.Row) and acciones_row.controls:
                                # primer control es el check
                                acciones_row.controls[0].disabled = True
                                row.cells[acciones_idx].content = acciones_row
                    except Exception:
                        pass
                    row.update()

                total_pagado = self.repo.total_pagado_confirmado()
                self.resumen_pagos.value = f"Total pagado: ${float(total_pagado):.2f}"
                ModalAlert.mostrar_info("Éxito", res.get("message", "Pago confirmado."))
                if self.page:
                    self.page.update()
            else:
                ModalAlert.mostrar_info("Error", res.get("message", "No fue posible confirmar el pago."))
        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo confirmar el pago: {str(ex)}")

    def _eliminar_pago(self, id_pago_nomina: int):
        def eliminar():
            try:
                res = self.repo.eliminar_pago(id_pago_nomina)
                if res.get("status") == "success":
                    self.depositos_temporales.pop(id_pago_nomina, None)
                    self._deposito_buffer.pop(id_pago_nomina, None)
                    self._cargar_pagos()
                else:
                    ModalAlert.mostrar_info("Error", res.get("message", "No se pudo eliminar."))
            except Exception as ex:
                ModalAlert.mostrar_info("Error al eliminar", str(ex))

        ModalAlert(
            title_text="Eliminar Pago",
            message=f"¿Eliminar el pago #{id_pago_nomina}?",
            on_confirm=eliminar,
        ).mostrar()

    # ------------- Modales -------------
    def _abrir_modal_descuentos(self, pago_row: Dict[str, Any]):
        p = {
            "id_pago": int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago")),
            "numero_nomina": int(pago_row["numero_nomina"]),
            "estado": pago_row.get("estado"),
        }

        def on_ok(_):
            self._actualizar_fila_pago(p["id_pago"])

        ModalDescuentos(pago_data=p, on_confirmar=on_ok).mostrar()

    def _abrir_modal_prestamos(self, pago_row: Dict[str, Any]):
        """
        Abre el modal de PRÉSTAMOS para NÓMINA (multi-préstamo, auto-save),
        sincronizado con el módulo de Préstamos.
        """
        num = int(pago_row["numero_nomina"])
        pago_id = int(pago_row.get("id_pago_nomina") or pago_row.get("id_pago"))

        # Verificación en caliente
        prestamo_activo = self.loan_model.get_prestamo_activo_por_empleado(num)
        if not prestamo_activo:
            ModalAlert.mostrar_info("Sin préstamo", f"El empleado {num} no tiene préstamos activos.")
            return

        p = {"id_pago": pago_id, "numero_nomina": num, "estado": pago_row.get("estado")}

        def on_ok(_):
            # refresca SOLO esta fila (suma de detalles de préstamos)
            self._actualizar_fila_pago(pago_id)

        ModalPrestamosNomina(pago_data=p, on_confirmar=on_ok).mostrar()


    def _get_fechas_disponibles_para_pago(self) -> List[date]:
        """
        Devuelve la lista de fechas disponibles para generar pagos,
        considerando las asistencias completas y no utilizadas.
        """
        try:
            if hasattr(self.assistance_model, "get_fechas_disponibles_para_pago"):
                return self.assistance_model.get_fechas_disponibles_para_pago() or []

            # Si no existe el método en AssistanceModel, calculamos desde min/max
            fi = self.assistance_model.get_fecha_minima_asistencia()
            ff = self.assistance_model.get_fecha_maxima_asistencia()
            if not fi or not ff:
                return []

            cur, out = fi, []
            while cur <= ff:
                out.append(cur)
                cur = date.fromordinal(cur.toordinal() + 1)
            return out

        except Exception as ex:
            print(f"❌ Error al obtener fechas disponibles para pago: {ex}")
            return []


    # ------------- Calendario -------------
    def _abrir_modal_fechas_disponibles(self):
        try:
            # 1) Fechas ya utilizadas (bloqueadas)
            bloqueadas = self.payment_model.get_fechas_utilizadas() or []
            bloqueadas = [
                datetime.strptime(f, "%Y-%m-%d").date() if isinstance(f, str) else f
                for f in bloqueadas
            ]

            self.selector_fechas.set_fechas_bloqueadas(bloqueadas)

            # 2) Fechas disponibles normales (asistencias completas y no usadas)
            disponibles = self._get_fechas_disponibles_para_pago()
            disponibles = [d for d in disponibles if d not in bloqueadas]

            # 3) Fechas totalmente vacías (sin asistencias registradas)
            fi = self.assistance_model.get_fecha_minima_asistencia()
            ff = self.assistance_model.get_fecha_maxima_asistencia()
            if fi and ff:
                vacias = self.assistance_model.get_fechas_vacias(fi, ff)
                disponibles.extend(vacias)

            # 4) Elimina duplicados y ordena
            disponibles = sorted(set(disponibles))

            # 5) Enviar al selector
            self.selector_fechas.set_fechas_disponibles(disponibles)
            self.selector_fechas.abrir_dialogo(reset_selection=True)

        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo abrir el calendario: {str(ex)}")


    # ------------- Generación por fechas -------------
    def _generar_por_fechas(self, fechas: List[date]):
        if not fechas:
            ModalAlert.mostrar_info("Fechas", "Selecciona al menos una fecha.")
            return

        fi = min(fechas)
        ff = max(fechas)

        fi_s = fi.strftime("%Y-%m-%d")
        ff_s = ff.strftime("%Y-%m-%d")

        try:
            res = self.payment_model.generar_pagos_por_rango(fecha_inicio=fi_s, fecha_fin=ff_s)

            try:
                self.assistance_model.marcar_asistencias_como_generadas(fecha_inicio=fi_s, fecha_fin=ff_s)
            except Exception:
                pass

            if res.get("status") == "success":
                ModalAlert.mostrar_info("Nómina por rango", res.get("message", "Pagos generados."))
            else:
                ModalAlert.mostrar_info("Nómina por rango", res.get("message", "Ocurrió un problema."))

        except Exception as ex:
            ModalAlert.mostrar_info("Error", f"No se pudo generar la nómina: {str(ex)}")

        self._cargar_pagos()

    # ------------- Utils -------------
    def _validar_input_id(self, _):
        texto = self.input_id.value.strip()
        self.input_id.border_color = ft.colors.OUTLINE if not texto or texto.isdigit() else ft.colors.RED_400
        if self.page:
            self.page.update()
