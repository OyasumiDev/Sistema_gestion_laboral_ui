# app/views/containers/prestamos_container.py
import flet as ft
from datetime import date
from typing import List

from app.core.app_state import AppState
from app.models.loan_model import LoanModel
from app.models.payment_model import PaymentModel
from app.models.loan_payment_model import LoanPaymentModel
from app.views.containers.modal_alert import ModalAlert
from app.core.enums.e_prestamos_model import E_PRESTAMOS
from app.core.enums.e_pagos_prestamos import E_PAGOS_PRESTAMO as EP

from app.helpers.prestamos_helper.prestamos_row_helper import PrestamosRowHelper
from app.helpers.prestamos_helper.pagos_prestamos_row_helper import PagosPrestamosRowHelper
from app.helpers.prestamos_helper.prestamos_validation_helper import PrestamosValidationHelper
from app.helpers.prestamos_helper.prestamos_scroll_helper import PrestamosScrollHelper

# BotonFactory (uniformidad con Empleados)
from app.helpers.boton_factory import (
    crear_boton_importar,
    crear_boton_exportar,
)

# Modal universal de préstamos
from app.views.containers.modal_pagos_prestamos import ModalPrestamos


class PrestamosContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20)

        # Estado / modelos
        self.page = AppState().page
        self.loan_model = LoanModel()
        self.payment_model = PaymentModel()
        self.loan_payment_model = LoanPaymentModel()
        self.E = E_PRESTAMOS

        # Helpers
        self.validador = PrestamosValidationHelper()
        self.row_helper = PrestamosRowHelper(actualizar_callback=self._actualizar_vista)
        self.pago_helper = PagosPrestamosRowHelper()

        # Estado UI
        self.datos_tabla: dict[str, List[ft.Control]] = {}   # filas temporales (ej. "prestamos_global")
        self._pending_scroll_key: str | None = None

        # Layout raíz
        self.layout = ft.Column(expand=True)
        self._build()
        self._actualizar_vista()

    # ---------------------------------------------------------------------
    # UI base
    # ---------------------------------------------------------------------
    def _build(self):
        # Columna scrollable donde se insertan los tiles
        self.tiles_column = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

        # Barra superior (uniforme con Empleados)
        top_bar = ft.Row(
            spacing=10,
            alignment=ft.MainAxisAlignment.START,
            controls=[
                crear_boton_importar(self._importar),
                crear_boton_exportar(self._exportar),
                self._build_add_global_button(),
            ],
        )

        self.layout.controls = [
            ft.Text("ÁREA DE PRÉSTAMOS", style=ft.TextThemeStyle.TITLE_MEDIUM),
            top_bar,
            ft.Divider(height=1),
            self.tiles_column,
        ]
        self.content = self.layout

    def _build_add_global_button(self) -> ft.GestureDetector:
        return ft.GestureDetector(
            on_tap=lambda _: self._agregar_prestamo_global(),
            content=ft.Container(
                padding=8,
                border_radius=12,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=ft.Row(
                    [
                        ft.Icon(ft.icons.ADD_CIRCLE_OUTLINED, size=20),
                        ft.Text("Agregar préstamo global", size=11, weight="bold"),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=5,
                ),
            ),
        )

    def _safe_refresh(self):
        try:
            if getattr(self.layout, "page", None) is not None:
                self.layout.update()
        except Exception:
            pass
        try:
            if self.page is not None:
                self.page.update()
        except Exception:
            pass

    # ---------------------------------------------------------------------
    # Render jerárquico
    # ---------------------------------------------------------------------
    def _actualizar_vista(self):
        tiles: List[ft.Control] = []

        resultado = self.loan_model.get_agrupado_por_empleado()
        if resultado.get("status") != "success":
            ModalAlert.mostrar_info("Error", resultado.get("message", "No se pudieron cargar los préstamos"))
            self._safe_refresh()
            return

        grupos = resultado.get("data", []) or []

        if not grupos:
            tiles.append(
                ft.Container(
                    content=ft.Text(
                        "No hay préstamos registrados. Usa 'Agregar préstamo global' o agrega desde el empleado.",
                        size=12,
                        color=ft.colors.GREY_700,
                    ),
                    padding=10,
                )
            )

        # Aliases del enum
        P = self.E
        K_ID = P.PRESTAMO_ID.value
        K_NUM = P.PRESTAMO_NUMERO_NOMINA.value
        K_NOM = P.PRESTAMO_NOMBRE_EMPLEADO.value
        K_MONTO = P.PRESTAMO_MONTO.value
        K_SALDO = P.PRESTAMO_SALDO.value
        K_ESTADO = P.PRESTAMO_ESTADO.value
        K_FECHA = P.PRESTAMO_FECHA_SOLICITUD.value

        for grupo in grupos:
            numero = grupo.get("numero_nomina")
            nombre = grupo.get("nombre_empleado", "")
            prestamos = grupo.get("prestamos", []) or []

            prestamos_tiles: List[ft.Control] = []
            for p in prestamos:
                id_prestamo = p.get(K_ID)

                # Historial de pagos del préstamo
                pagos_res = self.loan_payment_model.get_by_prestamo(id_prestamo)
                pagos = pagos_res.get("data", []) if (isinstance(pagos_res, dict) and pagos_res.get("status") == "success") else []
                total_pagado = 0.0
                for row in pagos:
                    try:
                        total_pagado += float(row.get(EP.PAGO_MONTO_PAGADO.value, row.get("monto_pagado", 0)) or 0)
                    except Exception:
                        pass

                editable_pagos = (str(p.get(K_ESTADO, "")).lower() != "terminado")

                # Lista estable (sin DataTable)
                lista_pagos = self.pago_helper.build_list(
                    pagos=pagos,
                    editable=editable_pagos,
                    on_edit=None,  # no se edita historial por ahora
                    on_delete=lambda pago, pid=id_prestamo, num=numero: self._confirmar_eliminar_pago(pago, pid, num),
                    max_height=260,
                )

                # Registro para la fila resumen del préstamo
                registro_ui = {
                    "id_prestamo": id_prestamo,
                    "numero_nomina": p.get(K_NUM),
                    "nombre_empleado": p.get(K_NOM, nombre) or nombre,
                    "monto": p.get(K_MONTO, ""),
                    "saldo": p.get(K_SALDO, "0.00"),
                    "pagado": f"{total_pagado:.2f}",
                    "estado": p.get(K_ESTADO, ""),
                    "fecha_solicitud": p.get(K_FECHA, ""),
                }

                fila_prestamo = self.row_helper.build_fila_lectura(
                    registro=registro_ui,
                    on_edit=(lambda pr=p: self._editar_prestamo(pr)),
                    on_delete=(lambda pr=p: self._eliminar_prestamo(pr[K_ID])),
                    # Abrimos el modal desde “Ver pagos”
                    on_pagos=(lambda pr=p, num=numero: self._ver_pagos_de_prestamo(pr, num)),
                )

                prestamos_tiles.append(
                    ft.ExpansionTile(
                        title=ft.Text(f"Préstamo ID {id_prestamo}"),
                        maintain_state=True,
                        controls=[fila_prestamo, lista_pagos],
                    )
                )

            # Acción “Agregar préstamo” para el empleado
            btn_agregar_prestamo = ft.GestureDetector(
                on_tap=lambda _, num=numero: self._agregar_prestamo_a_empleado(num),
                content=ft.Container(
                    padding=6,
                    border_radius=10,
                    bgcolor=ft.colors.SURFACE_VARIANT,
                    content=ft.Row(
                        [ft.Icon(ft.icons.ADD, size=18), ft.Text("Agregar préstamo", size=11, weight="bold")],
                        spacing=6,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ),
            )

            tiles.append(
                ft.ExpansionTile(
                    title=ft.Text(f"{nombre} - No. {numero}"),
                    maintain_state=True,
                    controls=[btn_agregar_prestamo] + prestamos_tiles,
                )
            )

        # Tile temporal de “préstamo global”
        if self.datos_tabla.get("prestamos_global"):
            tiles.append(
                ft.ExpansionTile(
                    title=ft.Text("Nuevo préstamo global"),
                    maintain_state=True,
                    initially_expanded=True,
                    controls=self.datos_tabla["prestamos_global"],
                )
            )

        self.tiles_column.controls = tiles
        self._safe_refresh()

        # Scroll post-refresh
        scroll_key = self._pending_scroll_key
        if not scroll_key and self.datos_tabla.get("prestamos_global"):
            scroll_key = "grupo_prestamos_global"
        if scroll_key:
            PrestamosScrollHelper.scroll_to_group_after_build(self.page, scroll_key, delay=0.1, retries=30)
            self._pending_scroll_key = None

    # ---------------------------------------------------------------------
    # Crear / Guardar préstamo
    # ---------------------------------------------------------------------
    def _agregar_prestamo_global(self, _=None):
        grupo = "prestamos_global"
        scroll_key = f"grupo_{grupo}"
        page = self.page

        self.datos_tabla.setdefault(grupo, [])

        registro = {
            "numero_nomina": "",
            "nombre_empleado": "",
            "monto": "",
            "saldo": "0.00",
            "pagado": "0.00",
            "estado": "pendiente",
            "fecha_solicitud": "",
        }

        campos_ref = {}

        def on_save():
            self._guardar_fila_desde_campos(grupo, fila_nueva, campos_ref)

        def on_cancel():
            try:
                self.datos_tabla[grupo].remove(fila_nueva)
            except ValueError:
                pass
            self._actualizar_vista()

        fila_nueva = self.row_helper.build_fila_nueva(
            registro=registro,
            on_save=on_save,
            on_cancel=on_cancel,
            page=page,
            scroll_key=scroll_key,
            campos_ref=campos_ref,
            grupo_empleado=None,
        )

        self.datos_tabla[grupo].append(fila_nueva)
        self._pending_scroll_key = scroll_key
        self._actualizar_vista()

    def _agregar_prestamo_a_empleado(self, numero_nomina: int):
        scroll_key = f"prestamos_{numero_nomina}"
        page = self.page
        campos_ref = {}

        registro = {
            "numero_nomina": str(numero_nomina),
            "nombre_empleado": "",
            "monto": "",
            "saldo": "0.00",
            "pagado": "0.00",
            "estado": "pendiente",
            "fecha_solicitud": "",
        }

        def on_save():
            self._guardar_fila_desde_campos(f"nuevo_{numero_nomina}", fila_nueva, campos_ref)

        def on_cancel():
            self._actualizar_vista()

        fila_nueva = self.row_helper.build_fila_nueva(
            registro=registro,
            on_save=on_save,
            on_cancel=on_cancel,
            page=page,
            scroll_key=scroll_key,
            campos_ref=campos_ref,
            grupo_empleado=None,
        )

        # Insertamos arriba para que sea visible inmediato
        self.tiles_column.controls.insert(
            0,
            ft.ExpansionTile(
                title=ft.Text(f"Nuevo préstamo para empleado {numero_nomina}"),
                maintain_state=True,
                initially_expanded=True,
                controls=[fila_nueva],
            ),
        )
        self._pending_scroll_key = scroll_key
        self._safe_refresh()

    def _guardar_fila_desde_campos(self, grupo_key: str, fila_widget: ft.Control, campos_ref: dict):
        numero = (campos_ref.get("numero_nomina").value or "").strip()
        monto_txt = (campos_ref.get("monto").value or "").strip().replace(",", ".")
        fecha_txt = (campos_ref.get("fecha").value or "").strip()

        ok_numero = self.validador.validar_numero_nomina(campos_ref["numero_nomina"])
        ok_monto = self.validador.validar_monto(campos_ref["monto"], limite=10000.0)
        ok_fecha = self.validador.validar_fecha(campos_ref["fecha"])

        if not (ok_numero and ok_monto and ok_fecha):
            ModalAlert.mostrar_info("Error", "Corrige los campos marcados en rojo.")
            return

        try:
            monto = float(monto_txt)
        except Exception:
            ModalAlert.mostrar_info("Error", "Monto inválido.")
            return

        fecha_sql = self.validador.convertir_fecha_mysql(fecha_txt)

        # grupo_empleado automático
        if grupo_key == "prestamos_global":
            grupo_empleado = "GLOBAL"
        elif grupo_key.startswith("nuevo_"):
            grupo_empleado = numero
        else:
            grupo_empleado = numero or "GLOBAL"

        datos = {
            "numero_nomina": int(numero),
            "monto": monto,
            "fecha_solicitud": fecha_sql,
            "grupo_empleado": grupo_empleado,
        }

        res = self._insertar_prestamo(datos)

        if res.get("status") == "success":
            ModalAlert.mostrar_info("Éxito", "Préstamo guardado correctamente.")
            try:
                if grupo_key in self.datos_tabla:
                    self.datos_tabla[grupo_key].remove(fila_widget)
            except ValueError:
                pass
            self._actualizar_vista()
        else:
            ModalAlert.mostrar_info("Error", res.get("message", "No se pudo guardar."))

    def _insertar_prestamo(self, datos: dict) -> dict:
        try:
            numero = int(datos["numero_nomina"])
            monto = float(datos["monto"])
            fecha = datos.get("fecha_solicitud")

            res = self.loan_model.add(
                numero_nomina=numero,
                monto_prestamo=monto,
                saldo_prestamo=None,
                estado="pagando",
                fecha_solicitud=fecha,
            )
            return res if isinstance(res, dict) else {"status": "success", "data": res}
        except Exception as ex:
            return {"status": "error", "message": f"Error al insertar préstamo: {ex}"}

    # ---------------------------------------------------------------------
    # Otras acciones
    # ---------------------------------------------------------------------
    def _editar_prestamo(self, prestamo: dict):
        ModalAlert.mostrar_info("Editar", "Edición no implementada aún en esta vista.")

    def _ver_pagos_de_prestamo(self, prestamo: dict, numero_nomina: int):
        pid = prestamo.get("id_prestamo") or prestamo.get(self.E.PRESTAMO_ID.value)
        if not pid:
            ModalAlert.mostrar_info("Error", "Préstamo inválido.")
            return

        hoy = date.today().strftime("%Y-%m-%d")
        pago_data = {
            "numero_nomina": int(numero_nomina),
            "id_pago": None,                 # el modal creará un pago de nómina si es necesario
            "estado": "pendiente",
            "fecha_generacion": hoy,
            "fecha_pago": hoy,
            "contexto": "prestamos",
            "id_prestamo": int(pid),
        }

        def on_confirmar(_):
            self._actualizar_vista()

        modal = ModalPrestamos(pago_data=pago_data, on_confirmar=on_confirmar)
        modal.mostrar()

    def _confirmar_eliminar_pago(self, pago: dict, id_prestamo: int, numero_nomina: int):
        pid = pago.get(EP.ID_PAGO_PRESTAMO.value) or pago.get("id_pago_prestamo")
        if not pid:
            ModalAlert.mostrar_info("Error", "No se pudo determinar el ID del pago.")
            return

        def on_confirm():
            res = self.loan_payment_model.delete_by_id_pago(int(pid))
            if res.get("status") == "success":
                ModalAlert.mostrar_info("Eliminado", f"Pago ID {pid} eliminado correctamente.")
                self._actualizar_vista()
            else:
                ModalAlert.mostrar_info("Error", res.get("message", "No se pudo eliminar el pago."))

        ModalAlert(
            title_text="¿Eliminar pago?",
            message=f"Esta acción no se puede deshacer.\nPago ID: {pid}",
            on_confirm=on_confirm,
        ).mostrar()

    def _importar(self, _):
        ModalAlert.mostrar_info("Importar", "Importación no implementada.")

    def _exportar(self, _):
        ModalAlert.mostrar_info("Exportación", "Exportación no implementada.")

    def _eliminar_prestamo(self, id_prestamo: int):
        res = self.loan_model.delete_by_id_prestamo(id_prestamo)
        if res.get("status") == "success":
            ModalAlert.mostrar_info("Eliminado", "Préstamo eliminado correctamente.")
        else:
            ModalAlert.mostrar_info("Error", res.get("message", "No se pudo eliminar."))
        self._actualizar_vista()
