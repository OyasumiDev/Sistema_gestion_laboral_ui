import flet as ft
from datetime import date
from app.core.app_state import AppState
from app.models.loan_model import LoanModel
from app.models.payment_model import PaymentModel
from app.models.loan_payment_model import LoanPaymentModel
from app.views.containers.modal_alert import ModalAlert
from app.core.enums.e_prestamos_model import E_PRESTAMOS

from app.helpers.prestamos_helper.prestamos_row_helper import PrestamosRowHelper
from app.helpers.prestamos_helper.pagos_prestamos_row_helper import PagosPrestamosRowHelper
from app.helpers.prestamos_helper.prestamos_validation_helper import PrestamosValidationHelper
from app.helpers.prestamos_helper.prestamos_scroll_helper import PrestamosScrollHelper

# 👇 modal nuevo
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
        self.datos_tabla: dict[str, list[ft.Control]] = {}
        self._pending_scroll_key: str | None = None

        # Layout raíz
        self.layout = ft.Column(expand=True)
        self._build()
        print("[PrestamosContainer] construido")
        self._actualizar_vista()

    # ---------------------------------------------------------------------
    # UI base
    # ---------------------------------------------------------------------
    def _build(self):
        self.tiles_column = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

        self.layout.controls = [
            ft.Text("Préstamos por empleado", style=ft.TextThemeStyle.TITLE_MEDIUM),
            ft.Row(
                [
                    ft.ElevatedButton("Importar", icon=ft.icons.FILE_UPLOAD, on_click=self._importar),
                    ft.ElevatedButton("Exportar", icon=ft.icons.FILE_DOWNLOAD, on_click=self._exportar),
                    ft.ElevatedButton("Agregar préstamo global", icon=ft.icons.ADD, on_click=self._agregar_prestamo_global),
                ],
                spacing=10,
            ),
            self.tiles_column,
        ]
        self.content = self.layout

    def _safe_refresh(self):
        try:
            if getattr(self.layout, "page", None) is not None:
                self.layout.update()
        except Exception as ex:
            print(f"[PrestamosContainer._safe_refresh] layout.update error: {ex}")
        try:
            if self.page is not None:
                self.page.update()
        except Exception as ex:
            print(f"[PrestamosContainer._safe_refresh] page.update error: {ex}")

    # ---------------------------------------------------------------------
    # Render jerárquico
    # ---------------------------------------------------------------------
    def _actualizar_vista(self):
        print("[_actualizar_vista] reconstruyendo vista...")

        tiles: list[ft.Control] = []

        resultado = self.loan_model.get_agrupado_por_empleado()
        print("[_actualizar_vista] status:", resultado.get("status"))
        if resultado.get("status") != "success":
            ModalAlert.mostrar_info("Error", resultado.get("message", "No se pudieron cargar los préstamos"))
            self._safe_refresh()
            return

        grupos = resultado.get("data", []) or []
        print("[_actualizar_vista] grupos recibidos:", len(grupos))

        if not grupos:
            tiles.append(
                ft.Container(
                    content=ft.Text(
                        "No hay préstamos registrados. Usa el botón 'Agregar préstamo global' o agrega por empleado.",
                        size=12,
                        color=ft.colors.GREY_700,
                    ),
                    padding=10,
                )
            )

        # Atajos enumerados
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
            print(f"  - Empleado {numero} '{nombre}': {len(prestamos)} préstamo(s)")

            prestamos_tiles = []
            for p in prestamos:
                id_prestamo = p.get(K_ID)

                # Pagos del préstamo
                pagos_res = self.loan_payment_model.get_by_prestamo(id_prestamo)
                pagos_filas = []
                total_pagado = 0.0
                if pagos_res.get("status") == "success":
                    pagos_raw = pagos_res.get("data", []) or []
                    for row in pagos_raw:
                        try:
                            # si quieres solo aplicados, descomenta la siguiente línea y usa "if row.get('aplicado')"
                            # if not row.get('aplicado'): continue
                            total_pagado += float(row.get("monto_pagado", 0) or 0)
                        except Exception:
                            pass
                        pagos_filas.append(
                            self.pago_helper.build_fila_pago(
                                pago=row,
                                editable=(str(p.get(K_ESTADO, "")).lower() != "terminado"),
                            )
                        )

                tabla_pagos = ft.DataTable(
                    columns=self.pago_helper.get_columnas(),
                    rows=pagos_filas,
                )
                tabla_wrap = ft.Container(
                    content=tabla_pagos,
                    border=ft.border.all(1, ft.colors.GREY_200),
                    border_radius=8,
                    padding=10,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                )

                # Registro normalizado para row_helper
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
                    on_edit=lambda pr=p: self._editar_prestamo(pr),
                    on_delete=lambda pr=p: self._eliminar_prestamo(pr[K_ID]),
                    # 👇 Ahora abrimos SIEMPRE el modal desde aquí
                    on_pagos=lambda pr=p, num=numero: self._ver_pagos_de_prestamo(pr, num),
                )

                # 👇 Eliminamos el botón "Agregar pago"; el acceso será por "Ver pagos"
                hijos = [fila_prestamo, tabla_wrap]

                prestamos_tiles.append(
                    ft.ExpansionTile(
                        title=ft.Text(f"Préstamo ID {id_prestamo}"),
                        maintain_state=True,
                        controls=hijos,
                    )
                )

            btn_agregar_prestamo = ft.ElevatedButton(
                "Agregar préstamo",
                icon=ft.icons.ADD,
                on_click=lambda e, num=numero: self._agregar_prestamo_a_empleado(num),
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
            print("[_actualizar_vista] filas en prestamos_global:", len(self.datos_tabla["prestamos_global"]))
            tiles.append(
                ft.ExpansionTile(
                    title=ft.Text("Nuevo préstamo global"),
                    maintain_state=True,
                    initially_expanded=True,
                    controls=self.datos_tabla["prestamos_global"],
                )
            )
        else:
            print("[_actualizar_vista] no hay filas temporales en prestamos_global")

        self.tiles_column.controls = tiles
        self._safe_refresh()

        scroll_key = self._pending_scroll_key
        if not scroll_key and self.datos_tabla.get("prestamos_global"):
            scroll_key = "grupo_prestamos_global"
        if scroll_key:
            print(f"[_actualizar_vista] solicitando scroll a: {scroll_key}")
            PrestamosScrollHelper.scroll_to_group_after_build(self.page, scroll_key, delay=0.1, retries=30)
            self._pending_scroll_key = None

    # ---------------------------------------------------------------------
    # Crear / Guardar préstamo
    # ---------------------------------------------------------------------
    def _agregar_prestamo_global(self, _=None):
        print("[_agregar_prestamo_global] click")
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
            print("[_agregar_prestamo_global.on_save] guardando...")
            self._guardar_fila_desde_campos(grupo, fila_nueva, campos_ref)

        def on_cancel():
            print("[_agregar_prestamo_global.on_cancel] cancelado")
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
        print(f"[_agregar_prestamo_a_empleado] click empleado {numero_nomina}")
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
            print(f"[_agregar_prestamo_a_empleado.on_save] guardando prestamo de {numero_nomina}...")
            self._guardar_fila_desde_campos(f"nuevo_{numero_nomina}", fila_nueva, campos_ref)

        def on_cancel():
            print(f"[_agregar_prestamo_a_empleado.on_cancel] cancelado prestamo de {numero_nomina}")
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

        print("[_guardar_fila_desde_campos] insertando:", datos)
        res = self._insertar_prestamo(datos)
        print("[_guardar_fila_desde_campos] resultado insert:", res)

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
        # si quieres modo simulación (sin guardar real):
        pago_data = {
            "numero_nomina": int(numero_nomina),
            "id_pago": None,                  # ← None => simulación (no guarda en BD)
            "estado": "pendiente",
            "fecha_generacion": date.today().strftime("%Y-%m-%d"),
            "fecha_pago": date.today().strftime("%Y-%m-%d"),
            "contexto": "prestamos",
            "id_prestamo": int(prestamo.get("id_prestamo")),
        }

        # si quieres que GUARDE realmente desde préstamos:
        # pago_data["id_pago"] = <id_pago_nomina_valido>

        def on_confirmar(_):
            self._actualizar_vista()

        modal = ModalPrestamos(pago_data=pago_data, on_confirmar=on_confirmar)
        modal.mostrar()


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
