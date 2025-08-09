import flet as ft
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
        self.datos_tabla: dict[str, list[ft.Control]] = {}   # filas temporales (ej. "prestamos_global")
        self._pending_scroll_key: str | None = None

        # Layout raíz del contenedor
        self.layout = ft.Column(expand=True)
        self._build()
        print("[PrestamosContainer] construido")
        self._actualizar_vista()

    # ---------------------------------------------------------------------
    # UI base
    # ---------------------------------------------------------------------
    def _build(self):
        # Column que SÍ está en el árbol visual; a este hay que asignarle .controls
        self.tiles_column = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

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
    # Render jerárquico (+ scroll post-refresh)
    # ---------------------------------------------------------------------
    def _actualizar_vista(self):
        print("[_actualizar_vista] reconstruyendo vista...")

        tiles: list[ft.Control] = []  # construimos una lista NUEVA cada vez

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

        for grupo in grupos:
            numero = grupo.get("numero_nomina")
            nombre = grupo.get("nombre_empleado", "")
            prestamos = grupo.get("prestamos", []) or []
            print(f"  - Empleado {numero} '{nombre}': {len(prestamos)} préstamo(s)")

            prestamos_tiles = []
            for prestamo in prestamos:
                pagos_res = self.loan_payment_model.get_by_id_prestamo(prestamo["id_prestamo"])
                pagos_filas = []
                if pagos_res.get("status") == "success":
                    for p in (pagos_res.get("data", []) or []):
                        pagos_filas.append(
                            self.pago_helper.build_fila_pago(
                                pago=p,
                                editable=(prestamo.get("estado", "").lower() != "terminado"),
                            )
                        )

                tabla_pagos = ft.DataTable(
                    columns=self.pago_helper.get_columnas(),
                    rows=pagos_filas,
                    expand=True,
                )

                fila_prestamo = self.row_helper.build_fila_lectura(
                    registro=prestamo,
                    on_edit=lambda p=prestamo: self._editar_prestamo(p),
                    on_delete=lambda p=prestamo: self._eliminar_prestamo(p["id_prestamo"]),
                    on_pagos=lambda p=prestamo: self._ver_pagos_de_prestamo(p),
                )

                hijos = [fila_prestamo, tabla_pagos]
                if prestamo.get("estado", "").lower() != "terminado":
                    hijos.append(
                        ft.ElevatedButton(
                            "Agregar pago",
                            icon=ft.icons.ADD,
                            on_click=lambda e, p=prestamo: self._agregar_pago(p),
                        )
                    )

                prestamos_tiles.append(
                    ft.ExpansionTile(
                        title=ft.Text(f"Préstamo ID {prestamo['id_prestamo']}"),
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

        # Sección de “préstamo global” en edición (si existe)
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

        # Asignamos la lista nueva al Column montado
        self.tiles_column.controls = tiles

        # Refresco + scroll
        self._safe_refresh()

        scroll_key = self._pending_scroll_key
        if not scroll_key and self.datos_tabla.get("prestamos_global"):
            scroll_key = "grupo_prestamos_global"
        if scroll_key:
            print(f"[_actualizar_vista] solicitando scroll a: {scroll_key}")
            PrestamosScrollHelper.scroll_to_group_after_build(self.page, scroll_key, delay=0.1, retries=30)
            self._pending_scroll_key = None

    # ---------------------------------------------------------------------
    # Crear / Guardar
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
            # "grupo_empleado": "GLOBAL",  # ya no se pinta; se calculará al guardar
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
        print("[_agregar_prestamo_global] tipo fila_nueva:", type(fila_nueva))

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
            # "grupo_empleado": str(numero_nomina),  # ya no se pinta; se calculará al guardar
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
        print("[_agregar_prestamo_a_empleado] tipo fila_nueva:", type(fila_nueva))

        # Inserta el tile temporal en el Column REAL que está montado
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

    # ---------------------------------------------------------------------
    # Guardado
    # ---------------------------------------------------------------------
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

        # 🔹 Calcular grupo_empleado automáticamente (ya no viene desde campos_ref)
        if grupo_key == "prestamos_global":
            grupo_empleado = "GLOBAL"
        elif grupo_key.startswith("nuevo_"):
            # cuando agregas para un empleado específico
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

    # ---------------------------------------------------------------------
    # Otras acciones
    # ---------------------------------------------------------------------
    def _editar_prestamo(self, prestamo: dict):
        ModalAlert.mostrar_info("Editar", "Edición no implementada aún en esta vista.")

    def _agregar_pago(self, prestamo: dict):
        ModalAlert.mostrar_info("Agregar pago", f"Agregar pago al préstamo {prestamo.get('id_prestamo')}")

    def _ver_pagos_de_prestamo(self, prestamo: dict):
        ModalAlert.mostrar_info("Pagos", f"Mostrando pagos del préstamo {prestamo.get('id_prestamo')}")

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


    def _insertar_prestamo(self, datos: dict) -> dict:
        """
        Compat layer para distintos nombres de método en LoanModel.
        Intenta varios candidatos y retorna {status, message, data?}.
        """
        candidatos = [
            "insert", "insert_prestamo",
            "create", "create_prestamo",
            "add", "add_prestamo",
            "save", "save_prestamo",
            "insert_one", "upsert",  # por si acaso
        ]

        for nombre in candidatos:
            metodo = getattr(self.loan_model, nombre, None)
            if callable(metodo):
                try:
                    # Preferimos pasar el dict completo
                    res = metodo(datos)
                except TypeError:
                    # Si el método espera kwargs
                    res = metodo(**datos)

                # Normalizamos respuestas "vacías"
                if res is None:
                    return {"status": "error", "message": f"LoanModel.{nombre} devolvió None"}
                if isinstance(res, dict) and "status" in res:
                    return res

                # Si devolvió algo distinto, lo convertimos
                return {"status": "success", "data": res}

        return {
            "status": "error",
            "message": (
                "LoanModel no expone un método de inserción compatible. "
                "Probados: " + ", ".join(candidatos)
            ),
        }
