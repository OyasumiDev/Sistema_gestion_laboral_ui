import flet as ft
from app.core.app_state import AppState
from app.models.loan_model import LoanModel
from app.views.containers.modal_alert import ModalAlert
from datetime import datetime


class PrestamosContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20)
        self.page = AppState().page
        self.loan_model = LoanModel()
        self.tabla_prestamos = ft.DataTable(columns=[], rows=[], expand=True)
        self.layout_tabla_prestamos = ft.Column(
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
        self._build()
        self._actualizar_vista_prestamos()

    def _build(self):
        self.layout_tabla_prestamos.controls = [
            ft.Text("Área actual: Préstamos", style=ft.TextThemeStyle.TITLE_MEDIUM),
            self._build_buttons_area(),
            self.tabla_prestamos
        ]
        self._actualizar_vista_prestamos()

    def _build_buttons_area(self):
        return ft.Row([
            self._build_icon_button("Importar", ft.icons.FILE_DOWNLOAD, self._importar),
            self._build_icon_button("Exportar", ft.icons.FILE_UPLOAD, self._exportar),
            self._build_icon_button("Agregar", ft.icons.ADD, self._insertar_fila_prestamo)
        ], spacing=15)

    def _build_icon_button(self, text, icon, handler):
        return ft.ElevatedButton(
            icon=ft.Icon(name=icon),
            text=text,
            on_click=handler,
            style=ft.ButtonStyle(padding=10, shape=ft.RoundedRectangleBorder(radius=6))
        )

    def _actualizar_vista_prestamos(self):
        self._cargar_tabla_prestamos()
        self.content = ft.Column(expand=True, controls=[self.layout_tabla_prestamos])
        self.page.update()

    def _cargar_tabla_prestamos(self):
        self.tabla_prestamos.columns = [
            ft.DataColumn(label=ft.Text("ID Préstamo")),
            ft.DataColumn(label=ft.Text("ID Empleado")),
            ft.DataColumn(label=ft.Text("Monto")),
            ft.DataColumn(label=ft.Text("Saldo")),
            ft.DataColumn(label=ft.Text("Dinero Pagado")),
            ft.DataColumn(label=ft.Text("Estado")),
            ft.DataColumn(label=ft.Text("Fecha Solicitud")),
            ft.DataColumn(label=ft.Text("Acciones"))
        ]

        resultado = self.loan_model.get_all()
        if resultado["status"] != "success":
            ModalAlert.mostrar_info("Error", resultado["message"])
            return

        self.tabla_prestamos.rows.clear()
        for p in resultado["data"]:
            dinero_pagado = float(p["monto"]) - float(p["saldo_prestamo"])
            self.tabla_prestamos.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(p["id_prestamo"])),
                ft.DataCell(ft.Text(p["numero_nomina"])),
                ft.DataCell(ft.Text(f"${p['monto']:.2f}")),
                ft.DataCell(ft.Text(f"${p['saldo_prestamo']:.2f}")),
                ft.DataCell(ft.Text(f"${dinero_pagado:.2f}")),
                ft.DataCell(ft.Text(p["estado"])),
                ft.DataCell(ft.Text(p["fecha_solicitud"])),
                ft.DataCell(self._build_acciones_cell(p))
            ]))

    def _build_acciones_cell(self, prestamo):
        def on_guardar_edicion(_):
            nuevo_monto_str = monto_input.value.strip()
            nuevo_estado = estado_dropdown.value

            if not nuevo_monto_str:
                ModalAlert("Monto requerido", "El campo de monto no puede estar vacío.").mostrar()
                return

            try:
                nuevo_monto = float(nuevo_monto_str)
            except ValueError:
                ModalAlert("Monto inválido", "Debe ingresar un monto válido.").mostrar()
                return

            resultado = self.loan_model.update_by_id_prestamo(prestamo["id_prestamo"], {
                self.loan_model.E.PRESTAMO_MONTO: nuevo_monto,
                self.loan_model.E.PRESTAMO_ESTADO: nuevo_estado
            })

            if resultado["status"] == "success":
                ModalAlert.mostrar_info("Éxito", "Préstamo editado correctamente.")
            else:
                ModalAlert.mostrar_info("Error", resultado["message"])
            self._actualizar_vista_prestamos()

        def on_cancelar_edicion(_):
            self._actualizar_vista_prestamos()

        monto_input = ft.TextField(value=str(prestamo["monto"]), width=100)
        estado_dropdown = ft.Dropdown(
            value=prestamo["estado"],
            options=[ft.dropdown.Option("pagando"), ft.dropdown.Option("terminado")],
            width=120
        )

        editar_btn = ft.IconButton(
            icon=ft.icons.EDIT,
            tooltip="Editar préstamo",
            on_click=lambda _: self._reemplazar_fila_con_edicion(
                prestamo, monto_input, estado_dropdown, on_guardar_edicion, on_cancelar_edicion
            )
        )

        borrar_btn = ft.IconButton(
            icon=ft.icons.DELETE,
            tooltip="Eliminar préstamo",
            on_click=lambda _: ModalAlert(
                title_text="¿Eliminar préstamo?",
                message="Esta acción no se puede deshacer.",
                on_confirm=lambda: self._eliminar_prestamo(prestamo["id_prestamo"]),
                on_cancel=lambda: self.page.update()
            ).mostrar()
        )

        ver_pagos_btn = ft.IconButton(
            icon=ft.icons.LIST_ALT,
            tooltip="Ver pagos del préstamo",
            on_click=lambda _: self.page.go(
                f"/home/prestamos/pagosprestamos?id_prestamo={prestamo['id_prestamo']}"
            )
        )

        return ft.Row([editar_btn, borrar_btn, ver_pagos_btn], spacing=5)

    def _reemplazar_fila_con_edicion(self, prestamo, monto_input, estado_dropdown, on_guardar, on_cancelar):
        id_editando = str(prestamo["id_prestamo"])

        for i, row in enumerate(self.tabla_prestamos.rows):
            id_fila = str(row.cells[0].content.value).strip()
            if id_fila == id_editando:
                self.tabla_prestamos.rows[i] = ft.DataRow(cells=[
                    ft.DataCell(ft.Text(id_editando)),
                    ft.DataCell(ft.Text(str(prestamo["numero_nomina"]))),
                    ft.DataCell(monto_input),
                    ft.DataCell(ft.Text(f"${prestamo['saldo_prestamo']:.2f}")),
                    ft.DataCell(ft.Text("Auto")),  # Dinero pagado no editable aquí
                    ft.DataCell(estado_dropdown),
                    ft.DataCell(ft.Text(prestamo["fecha_solicitud"])),
                    ft.DataCell(ft.Row([
                        ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, on_click=on_guardar),
                        ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600, on_click=on_cancelar)
                    ]))
                ])
                break
        self.page.update()

    def _insertar_fila_prestamo(self, e=None):
        numero_input = ft.TextField(hint_text="ID Empleado", width=120)
        monto_input = ft.TextField(hint_text="Monto", width=120)
        hoy = datetime.today().strftime("%Y-%m-%d")
        nuevo_id = self.loan_model.get_next_id_prestamo() or "?"

        def on_guardar(_):
            numero_nomina = numero_input.value.strip()
            monto_str = monto_input.value.strip()

            if not numero_nomina.isdigit():
                ModalAlert("ID inválido", "El número de empleado debe ser un entero.").mostrar()
                return
            if not monto_str:
                ModalAlert("Falta monto", "El campo de monto no puede estar vacío.").mostrar()
                return
            try:
                monto = float(monto_str)
            except ValueError:
                ModalAlert("Monto inválido", "Debe ingresar un monto válido.").mostrar()
                return

            resultado = self.loan_model.add(
                numero_nomina=int(numero_nomina),
                monto=monto,
                saldo_prestamo=monto,
                estado="pagando",
                fecha_solicitud=hoy
            )

            if resultado["status"] == "success":
                ModalAlert.mostrar_info("Éxito", "Préstamo agregado correctamente.")
                self._actualizar_vista_prestamos()
            else:
                ModalAlert.mostrar_info("Error", resultado["message"])

        def on_cancelar(_):
            self._actualizar_vista_prestamos()

        nueva_fila = ft.DataRow(cells=[
            ft.DataCell(ft.Text(str(nuevo_id))),
            ft.DataCell(numero_input),
            ft.DataCell(monto_input),
            ft.DataCell(ft.Text("Auto")),
            ft.DataCell(ft.Text("Auto")),
            ft.DataCell(ft.Text("pagando")),
            ft.DataCell(ft.Text(hoy)),
            ft.DataCell(ft.Row([
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, on_click=on_guardar),
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600, on_click=on_cancelar)
            ]))
        ])
        self.tabla_prestamos.rows.append(nueva_fila)
        self.page.update()

    def _importar(self, e=None):
        ModalAlert.mostrar_info("Importar", "Función aún no implementada")

    def _exportar(self, e=None):
        ModalAlert.mostrar_info("Exportar", "Función aún no implementada")

    def _eliminar_prestamo(self, id_prestamo: int):
        try:
            resultado = self.loan_model.delete_by_id_prestamo(id_prestamo)
            if resultado["status"] == "success":
                ModalAlert.mostrar_info("Eliminado", "El préstamo fue eliminado correctamente.")
                self._actualizar_vista_prestamos()
            else:
                ModalAlert.mostrar_info("Error", resultado["message"])
        except Exception as ex:
            ModalAlert.mostrar_info("Error", str(ex))
