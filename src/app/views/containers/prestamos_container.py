import flet as ft
from app.core.app_state import AppState
from app.models.loan_model import LoanModel
from app.models.payment_model import PaymentModel
from app.models.loan_payment_model import LoanPaymentModel
from app.views.containers.modal_alert import ModalAlert
from app.core.enums.e_prestamos_model import E_PRESTAMOS
from app.helpers.prestamos_helper.prestamos_row_helper import PrestamosRowHelper
from app.helpers.prestamos_helper.pagos_prestamos_row_helper import PagosPrestamosRowHelper
from app.helpers.boton_factory import crear_boton_importar, crear_boton_exportar, crear_boton_agregar


class PrestamosContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20)
        self.page = AppState().page
        self.loan_model = LoanModel()
        self.payment_model = PaymentModel()
        self.loan_payment_model = LoanPaymentModel()
        self.E = E_PRESTAMOS

        self.row_helper = PrestamosRowHelper(actualizar_callback=self._actualizar_vista)
        self.pago_helper = PagosPrestamosRowHelper()

        self.expand_tiles = []
        self.datos_tabla = {}  # Necesario para prestamos_global
        self.layout = ft.Column(expand=True)
        self._build()
        self._actualizar_vista()

    def _build(self):
        self.layout.controls = [
            ft.Text("Préstamos por empleado", style=ft.TextThemeStyle.TITLE_MEDIUM),
            ft.Row([
                crear_boton_importar(self._importar),
                crear_boton_exportar(self._exportar),
                crear_boton_agregar(self._agregar_prestamo_global)
            ], spacing=10),
            ft.Column(self.expand_tiles, expand=True, scroll=ft.ScrollMode.AUTO)
        ]
        self.content = self.layout


    def _actualizar_vista(self):
        self.expand_tiles.clear()

        # 🔁 Obtener datos agrupados por empleado
        resultado = self.loan_model.get_agrupado_por_empleado()
        if resultado["status"] != "success":
            ModalAlert.mostrar_info("Error", resultado["message"])
            return

        # 👥 Renderizar préstamos por empleado
        for grupo in resultado["data"]:
            numero = grupo["numero_nomina"]
            nombre = grupo["nombre_empleado"]
            prestamos = grupo["prestamos"]
            prestamos_tiles = []

            for prestamo in prestamos:
                pagos = self.loan_payment_model.get_by_id_prestamo(prestamo["id_prestamo"])
                pagos_filas = []
                if pagos["status"] == "success":
                    pagos_filas = [
                        self.pago_helper.build_fila_pago(
                            pago=p,
                            editable=(prestamo["estado"].lower() != "terminado")
                        ) for p in pagos["data"]
                    ]

                tabla_pagos = ft.DataTable(
                    columns=self.pago_helper.get_columnas(),
                    rows=pagos_filas,
                    expand=True
                )

                fila_prestamo = self.row_helper.build_fila_lectura(
                    registro=prestamo,
                    on_edit=lambda p=prestamo: self._editar_prestamo(p),
                    on_delete=lambda p=prestamo: self._eliminar_prestamo(p["id_prestamo"]),
                    on_pagos=None
                )

                hijos = [fila_prestamo, tabla_pagos]

                if prestamo["estado"].lower() != "terminado":
                    btn = ft.ElevatedButton(
                        "Agregar pago",
                        icon=ft.icons.ADD,
                        on_click=lambda e, p=prestamo: self._agregar_pago(p)
                    )
                    hijos.append(btn)

                prestamos_tiles.append(
                    ft.ExpansionTile(
                        title=ft.Text(f"Préstamo ID {prestamo['id_prestamo']}"),
                        maintain_state=True,
                        controls=hijos
                    )
                )

            btn_agregar_prestamo = ft.ElevatedButton(
                "Agregar préstamo",
                icon=ft.icons.ADD,
                on_click=lambda e, num=numero: self._agregar_prestamo_a_empleado(num)
            )

            self.expand_tiles.append(
                ft.ExpansionTile(
                    title=ft.Text(f"{nombre} - No. {numero}"),
                    maintain_state=True,
                    controls=[btn_agregar_prestamo] + prestamos_tiles
                )
            )

        # 📦 Renderizar fila de préstamos globales si existe
        if "prestamos_global" in self.datos_tabla and self.datos_tabla["prestamos_global"]:
            self.expand_tiles.append(
                ft.ExpansionTile(
                    title=ft.Text("Nuevo préstamo global"),
                    maintain_state=True,
                    initially_expanded=True,
                    controls=self.datos_tabla["prestamos_global"]
                )
            )

        self.page.update()


    def _agregar_prestamo_global(self, _=None):
        grupo = "prestamos_global"
        scroll_key = f"grupo_{grupo}"
        page = self.page

        if grupo not in self.datos_tabla:
            self.datos_tabla[grupo] = []

        registro = {
            "numero_nomina": "",
            "nombre_empleado": "",
            "monto": "",
            "saldo": "0.00",
            "pagado": "0.00",
            "estado": "pendiente",
            "grupo_empleado": "GLOBAL",
            "fecha_solicitud": "",
        }

        campos_ref = {}

        def on_save():
            self._guardar_fila_nueva(grupo, fila_nueva, campos_ref)

        def on_cancel():
            self.datos_tabla[grupo].remove(fila_nueva)
            self._actualizar_vista()

        fila_nueva = self.row_helper.build_fila_nueva(
            registro=registro,
            on_save=on_save,
            on_cancel=on_cancel,
            page=page,
            scroll_key=scroll_key,
            campos_ref=campos_ref,
            grupo_empleado="GLOBAL"
        )

        self.datos_tabla[grupo].append(fila_nueva)
        self._actualizar_vista()


    def _guardar_fila_nueva(self, grupo, fila_widget, campos_ref):
        numero = campos_ref["numero_nomina"].value.strip()
        monto = campos_ref["monto"].value.strip()
        fecha = campos_ref["fecha"].value.strip()
        grupo_empleado = campos_ref["grupo_empleado"].value.strip()

        if not numero.isdigit():
            ModalAlert.mostrar_info("Error", "El número de nómina no es válido.")
            return

        empleado = self.loan_model.get_empleado_por_numero(numero)
        if not empleado:
            ModalAlert.mostrar_info("Error", "Empleado no encontrado.")
            return

        datos = {
            "numero_nomina": int(numero),
            "monto": float(monto),
            "fecha_solicitud": fecha,
            "grupo_empleado": grupo_empleado
        }

        resultado = self.loan_model.insert(datos)
        if resultado["status"] == "success":
            ModalAlert.mostrar_info("Éxito", "Préstamo guardado correctamente.")
            self.datos_tabla[grupo].remove(fila_widget)
            self._actualizar_vista()
        else:
            ModalAlert.mostrar_info("Error", resultado["message"])

    def _editar_prestamo(self, prestamo):
        ModalAlert.mostrar_info("Edición", "Editar no implementado en esta versión jerárquica.")

    def _agregar_pago(self, prestamo):
        ModalAlert.mostrar_info("Agregar pago", f"Agregar pago al préstamo {prestamo['id_prestamo']}")

    def _agregar_prestamo_a_empleado(self, numero_nomina: int):
        fila_nueva = self.row_helper.build_fila_nueva(
            grupo_empleado=numero_nomina,
            registro={},
            on_save=self._guardar_nuevo_prestamo,
            on_cancel=self._actualizar_vista,
            page=self.page,
            scroll_key=f"prestamos_{numero_nomina}"
        )

        self.expand_tiles.append(
            ft.ExpansionTile(
                title=ft.Text(f"Nuevo préstamo para empleado {numero_nomina}"),
                maintain_state=True,
                initially_expanded=True,
                controls=[fila_nueva]
            )
        )
        self.page.update()

    def _guardar_nuevo_prestamo(self, datos: dict):
        resultado = self.loan_model.insert(datos)
        if resultado["status"] == "success":
            ModalAlert.mostrar_info("Éxito", "Préstamo guardado correctamente.")
        else:
            ModalAlert.mostrar_info("Error", resultado["message"])
        self._actualizar_vista()

    def _importar(self, _):
        ModalAlert.mostrar_info("Importar", "Importación no implementada.")

    def _exportar(self, _):
        ModalAlert.mostrar_info("Exportar", "Exportación no implementada.")

    def _eliminar_prestamo(self, id_prestamo):
        resultado = self.loan_model.delete_by_id_prestamo(id_prestamo)
        if resultado["status"] == "success":
            ModalAlert.mostrar_info("Eliminado", "Préstamo eliminado correctamente.")
        else:
            ModalAlert.mostrar_info("Error", resultado["message"])
        self._actualizar_vista()