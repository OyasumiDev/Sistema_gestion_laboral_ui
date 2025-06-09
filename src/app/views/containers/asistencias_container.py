import flet as ft
import pandas as pd
from datetime import datetime, timedelta
import functools
from app.models.assistance_model import AssistanceModel
from app.core.enums.e_assistance_model import E_ASSISTANCE
from app.controllers.asistencias_import_controller import AsistenciasImportController
from app.core.app_state import AppState
from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.views.containers.theme_controller import ThemeController
from app.views.containers.modal_alert import ModalAlert
from app.views.containers.window_snackbar import WindowSnackbar
from tabulate import tabulate


class AsistenciasContainer(ft.Container):
    def __init__(self):
        super().__init__(
            expand=True,
            padding=20,
            alignment=ft.alignment.top_center
        )

        self.page = AppState().page
        self.asistencia_model = AssistanceModel()
        self.theme_ctrl = ThemeController()

        self.sort_key = "numero_nomina"
        self.sort_asc = True

        self.import_controller = AsistenciasImportController(
            page=self.page,
            on_success=self._actualizar_tabla
        )

        self.save_invoker = FileSaveInvoker(
            page=self.page,
            on_save=self._exportar_asistencias,
            save_dialog_title="Exportar asistencias como Excel",
            file_name="asistencias_exportadas.xlsx",
            allowed_extensions=["xlsx"]
        )

        self.window_snackbar = WindowSnackbar(self.page)
        self.table = None
        self.tabla_vacia = True

        self.scroll_column = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.ALWAYS,
            expand=True,
            alignment=ft.MainAxisAlignment.START
        )

        self.import_button = self._build_action_button(
            label="Importar",
            icon_path="assets/buttons/import-button.png",
            on_tap=lambda _: self.import_controller.file_invoker.open()
        )

        self.export_button = self._build_action_button(
            label="Exportar",
            icon_path="assets/buttons/export-button.png",
            on_tap=lambda _: self.save_invoker.open_save()
        )

        self.new_column_button = self._build_action_button(
            label="Agregar Columna",
            icon=ft.icons.PERSON_ADD_ALT_1_OUTLINED,
            on_tap=self._insertar_asistencia_desde_columna
        )

        self.content = self._build_content()
        self._actualizar_tabla()
        self.page.update()



    def _icono_orden(self, columna):
        if self.sort_key == columna:
            return "▲" if self.sort_asc else "▼"
        return "⇅"


    def _sort_by(self, key):
        if self.sort_key == key:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_key = key
            self.sort_asc = True
        self._actualizar_tabla()


    def _actualizar_tabla(self, _=None):
        datos = self.asistencia_model.get_all()["data"]
        datos.sort(key=lambda x: x.get(self.sort_key, 0), reverse=not self.sort_asc)

        columnas = [
            self._build_col("ID Empleado", "numero_nomina", width=110),
            ft.DataColumn(ft.Container(ft.Text("Empleado"), width=220)),
            self._build_col("Fecha", "fecha", width=130),
            ft.DataColumn(ft.Container(ft.Text("Entrada"), width=110)),
            ft.DataColumn(ft.Container(ft.Text("Salida"), width=110)),
            ft.DataColumn(ft.Container(ft.Text("Retardo"), width=110)),
            self._build_col("Estado", "estado", width=130),
            ft.DataColumn(ft.Container(ft.Text("Horas Trabajadas"), width=150)),
            ft.DataColumn(ft.Container(ft.Text("Acciones"), width=120)),
        ]

        filas = []
        for reg in datos:
            try:
                numero = reg.get("numero_nomina")
                fecha = reg.get("fecha")

                eliminar_btn = ft.IconButton(
                    icon=ft.icons.DELETE_OUTLINE,
                    icon_size=20,
                    icon_color=ft.colors.RED_600,
                    tooltip="Eliminar registro",
                    on_click=lambda e, n=numero, f=fecha: self._confirmar_eliminacion(n, f)
                )

                editar_btn = ft.IconButton(
                    icon=ft.icons.EDIT,
                    icon_size=20,
                    icon_color=ft.colors.BLUE_600,
                    tooltip="Editar asistencia",
                    on_click=lambda e, n=numero, f=fecha: self._editar_asistencia(n, f)
                )


                def limpiar(campo):
                    return str(reg.get(campo)) if reg.get(campo) not in [None, ""] else "-"

                fila = ft.DataRow(cells=[
                    ft.DataCell(ft.Text(limpiar("numero_nomina"))),
                    ft.DataCell(ft.Text(limpiar("nombre"))),
                    ft.DataCell(ft.Text(limpiar("fecha"))),
                    ft.DataCell(ft.Text(limpiar("hora_entrada"))),
                    ft.DataCell(ft.Text(limpiar("hora_salida"))),
                    ft.DataCell(ft.Text(limpiar("retardo"))),
                    ft.DataCell(ft.Text(limpiar("estado"))),
                    ft.DataCell(ft.Text(limpiar("tiempo_trabajo"))),
                    ft.DataCell(ft.Row([editar_btn, eliminar_btn], spacing=5)),
                ])
                filas.append(fila)
            except Exception as e:
                print(f"❌ Error al construir fila (Empleado {reg.get('numero_nomina')}, Fecha {reg.get('fecha')}): {e}")

        self.scroll_column.controls.clear()

        self.table = ft.DataTable(
            expand=True,
            columns=columnas,
            rows=filas if filas else [
                ft.DataRow(
                    cells=[ft.DataCell(ft.Text("-", color=ft.colors.GREY_500)) for _ in columnas]
                )
            ],
            column_spacing=25,
            horizontal_lines=None,
        )

        self.scroll_column.controls.append(
            ft.Container(
                alignment=ft.alignment.center,
                expand=True,
                content=self.table
            )
        )

        if not filas:
            self.scroll_column.controls.append(
                ft.Container(
                    alignment=ft.alignment.top_center,
                    padding=ft.padding.only(top=20),
                    content=ft.Text(
                        "No hay asistencias registradas.",
                        size=16,
                        color=ft.colors.GREY
                    ),
                )
            )

        self.page.update()


    def _build_content(self):
        return ft.Container(
            expand=True,
            content=ft.Column(
                scroll=ft.ScrollMode.ALWAYS,  # ✅ Scroll vertical siempre visible
                alignment=ft.MainAxisAlignment.START,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20,
                controls=[
                    ft.Text(
                        "Registro de Asistencias",
                        size=24,
                        weight="bold",
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Container(
                        alignment=ft.alignment.center_left,
                        padding=ft.padding.only(left=60),
                        content=ft.Row(
                            spacing=10,
                            alignment=ft.MainAxisAlignment.START,
                            controls=[
                                self.import_button,
                                self.export_button,
                                self.new_column_button
                            ]
                        )
                    ),
                    ft.Container(
                        alignment=ft.alignment.center,
                        padding=ft.padding.symmetric(horizontal=20),
                        content=ft.Container(
                            content=self.scroll_column,
                            alignment=ft.alignment.center,
                            margin=ft.margin.symmetric(horizontal="auto"),
                        )
                    )
                ]
            )
        )




    def _confirmar_eliminacion(self, numero, fecha, e=None):
        ModalAlert(
            title_text="¿Eliminar asistencia?",
            message=f"¿Deseas eliminar el registro del empleado {numero} el día {fecha}?",
            on_confirm=lambda: self._eliminar_asistencia(numero, fecha),
            on_cancel=self._actualizar_tabla
        ).mostrar()

    def _eliminar_asistencia(self, numero, fecha):
        try:
            resultado = self.asistencia_model.delete_by_numero_nomina_and_fecha(numero, fecha)
            if resultado["status"] == "success":
                self.window_snackbar.show_success("✅ Asistencia eliminada correctamente.")
            else:
                self.window_snackbar.show_error("❌ " + resultado["message"])
        except Exception as e:
            self.window_snackbar.show_error("⚠️ " + str(e))

        self._actualizar_tabla()


    def _build_action_button(self, label, icon_path=None, icon=None, on_tap=None):
        content = ft.Row(spacing=5, alignment=ft.MainAxisAlignment.CENTER)
        if icon_path:
            content.controls.append(ft.Image(src=icon_path, width=20, height=20))
        elif icon:
            content.controls.append(ft.Icon(name=icon, size=20))
        content.controls.append(ft.Text(label, size=11, weight="bold"))

        return ft.GestureDetector(
            on_tap=on_tap,
            content=ft.Container(
                padding=8,
                border_radius=12,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=content
            )
        )


    def _exportar_asistencias(self, path: str):
        try:
            resultado = self.asistencia_model.get_all()
            if resultado["status"] != "success":
                print("❌ Error al obtener asistencias:", resultado["message"])
                return

            datos = resultado["data"]

            columnas = [
                ("numero_nomina", "ID Checador"),
                ("nombre", "Nombre"),
                ("fecha", "Fecha"),
                ("hora_entrada", "Entrada"),
                ("hora_salida", "Salida"),
                ("retardo", "Retardo"),
                ("estado", "Estado"),
                ("tiempo_trabajo", "Tiempo de trabajo")
            ]

            encabezado = [
                ["CONTROL de Mexico"],
                ["Entradas y Salidas"],
                [f"Periodo: {datos[0]['fecha']} al {datos[-1]['fecha']}"] if datos else [""],
                ["Sucursales: Sucursal Matriz,Soriana,Mattel"],
                []
            ]

            cuerpo = []
            for reg in datos:
                fila = []
                for clave, _ in columnas:
                    valor = reg.get(clave)
                    if isinstance(valor, (datetime, pd.Timestamp)):
                        fila.append(valor.strftime("%H:%M:%S"))
                    elif isinstance(valor, str) and ":" in valor:
                        fila.append(valor)
                    elif valor in [None, ""]:
                        fila.append("00:00:00" if "hora" in clave or "tiempo" in clave or clave in ["retardo"] else "")
                    else:
                        fila.append(str(valor))
                cuerpo.append(fila)

            df = pd.DataFrame(cuerpo, columns=[n for _, n in columnas])
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                df.to_excel(writer, startrow=5, index=False, sheet_name="Asistencias")
                for idx, fila in enumerate(encabezado, 1):
                    for col_idx, val in enumerate(fila, 1):
                        writer.sheets["Asistencias"].cell(row=idx, column=col_idx, value=val)

            print(f"✅ Asistencias exportadas a: {path}")
        except Exception as e:
            print(f"❌ Error al exportar: {e}")


    def depurar_asistencias(self):
        resultado = self.asistencia_model.get_all()
        if resultado["status"] != "success":
            print("❌ Error al obtener asistencias:", resultado["message"])
            return

        datos = resultado["data"]
        if not datos:
            print("⚠️ No hay asistencias registradas.")
            return

        columnas = [e.value for e in E_ASSISTANCE]
        tabla = [[registro.get(col) for col in columnas] for registro in datos]
        print("\n📋 Asistencias registradas en la base de datos:")
        print(tabulate(tabla, headers=columnas, tablefmt="grid"))

    def _insertar_asistencia_desde_columna(self, _):
        numero_input = ft.TextField(hint_text="ID Empleado", width=120, keyboard_type=ft.KeyboardType.NUMBER)
        fecha_input = ft.TextField(hint_text="Fecha (DD/MM/YYYY)", width=160)
        entrada_input = ft.TextField(hint_text="Entrada (HH:MM:SS)", width=140)
        salida_input = ft.TextField(hint_text="Salida (HH:MM:SS)", width=140)

        def validar_en_tiempo_real(_=None):
            numero_input.border_color = None
            fecha_input.border_color = None
            entrada_input.border_color = None
            salida_input.border_color = None

            h_ent = h_sal = None

            try:
                numero = int(numero_input.value.strip())
                if numero <= 0:
                    raise ValueError
            except:
                numero_input.border_color = ft.colors.RED

            try:
                fecha_sql = datetime.strptime(fecha_input.value.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
                if self.asistencia_model.get_by_empleado_fecha(numero, fecha_sql):
                    fecha_input.border_color = ft.colors.RED
            except:
                fecha_input.border_color = ft.colors.RED

            try:
                h_ent = datetime.strptime(entrada_input.value.strip(), "%H:%M:%S")
            except:
                entrada_input.border_color = ft.colors.RED

            try:
                h_sal = datetime.strptime(salida_input.value.strip(), "%H:%M:%S")
            except:
                salida_input.border_color = ft.colors.RED

            if h_ent and h_sal and h_sal <= h_ent:
                salida_input.border_color = ft.colors.RED

            self.page.update()

        numero_input.on_change = validar_en_tiempo_real
        fecha_input.on_change = validar_en_tiempo_real
        entrada_input.on_change = validar_en_tiempo_real
        salida_input.on_change = validar_en_tiempo_real

        def on_guardar(_):
            errores = []
            numero_input.border_color = None
            fecha_input.border_color = None
            entrada_input.border_color = None
            salida_input.border_color = None

            numero_str = str(numero_input.value).strip()
            fecha_str = str(fecha_input.value).strip()
            entrada_str = str(entrada_input.value).strip()
            salida_str = str(salida_input.value).strip()

            try:
                numero = int(numero_str)
                if numero <= 0:
                    raise ValueError
            except:
                errores.append("🟥 El ID de empleado debe ser un número entero positivo.")
                numero_input.border_color = ft.colors.RED

            try:
                fecha_sql = datetime.strptime(fecha_str, "%d/%m/%Y").strftime("%Y-%m-%d")
            except:
                errores.append("🟥 Fecha inválida. Usa el formato DD/MM/YYYY.")
                fecha_input.border_color = ft.colors.RED

            if not errores and self.asistencia_model.get_by_empleado_fecha(numero, fecha_sql):
                errores.append("🟥 Ya existe una asistencia para este empleado en esa fecha.")
                fecha_input.border_color = ft.colors.RED

            try:
                h_ent = datetime.strptime(entrada_str, "%H:%M:%S")
            except:
                errores.append("🟥 La hora de entrada debe tener el formato HH:MM:SS.")
                entrada_input.border_color = ft.colors.RED

            try:
                h_sal = datetime.strptime(salida_str, "%H:%M:%S")
            except:
                errores.append("🟥 La hora de salida debe tener el formato HH:MM:SS.")
                salida_input.border_color = ft.colors.RED

            if "h_ent" in locals() and "h_sal" in locals():
                if h_sal <= h_ent:
                    errores.append("🟥 La hora de salida debe ser mayor que la de entrada.")
                    salida_input.border_color = ft.colors.RED

            self.page.update()

            if errores:
                ModalAlert.mostrar_info("Errores encontrados", "\n".join(errores))
                return

            resultado = self.asistencia_model.add_manual_assistance(
                numero_nomina=numero,
                fecha=fecha_sql,
                hora_entrada=entrada_str,
                hora_salida=salida_str
            )

            if resultado["status"] == "success":
                self.window_snackbar.show_success("✅ Asistencia registrada correctamente.")
                self.depurar_asistencias()
            else:
                ModalAlert.mostrar_info("Error", "❌ " + resultado["message"])

            self._actualizar_tabla()

        fila = ft.DataRow(cells=[
            ft.DataCell(numero_input),
            ft.DataCell(ft.Text("-")),
            ft.DataCell(fecha_input),
            ft.DataCell(entrada_input),
            ft.DataCell(salida_input),
            ft.DataCell(ft.Text("00:00:00")),
            ft.DataCell(ft.Text("completo")),
            ft.DataCell(ft.Text("00:00:00")),
            ft.DataCell(ft.Row([
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, on_click=on_guardar),
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600, on_click=self._actualizar_tabla)
            ]))
        ])

        if self.table:
            self.table.rows.append(fila)
            self.table.update()
        self.page.update()

    def _editar_asistencia(self, numero_nomina, fecha, e=None):
        registro = next((r for r in self.asistencia_model.get_all()["data"]
                        if r["numero_nomina"] == numero_nomina and r["fecha"] == fecha), None)

        if not registro:
            self.window_snackbar.show_error("Registro no encontrado.")
            return

        entrada_input = ft.TextField(value=registro.get("hora_entrada", ""), width=130)
        salida_input = ft.TextField(value=registro.get("hora_salida", ""), width=130)
        estado_dropdown = ft.Dropdown(
            value=registro.get("estado", "incompleto"),
            options=[ft.dropdown.Option("completo"), ft.dropdown.Option("incompleto")],
            width=130
        )

        def validar_en_tiempo_real(_=None):
            entrada_input.border_color = None
            salida_input.border_color = None
            estado_dropdown.border_color = None

            h_ent = h_sal = None

            try:
                h_ent = datetime.strptime(entrada_input.value.strip(), "%H:%M:%S")
            except:
                entrada_input.border_color = ft.colors.RED

            try:
                h_sal = datetime.strptime(salida_input.value.strip(), "%H:%M:%S")
            except:
                salida_input.border_color = ft.colors.RED

            if h_ent and h_sal:
                if h_sal <= h_ent:
                    salida_input.border_color = ft.colors.RED
                if estado_dropdown.value == "incompleto":
                    estado_dropdown.border_color = ft.colors.RED
            self.page.update()

        entrada_input.on_change = validar_en_tiempo_real
        salida_input.on_change = validar_en_tiempo_real
        estado_dropdown.on_change = validar_en_tiempo_real

        def on_guardar(_):
            errores = []

            entrada_input.border_color = None
            salida_input.border_color = None
            estado_dropdown.border_color = None

            entrada_str = str(entrada_input.value).strip()
            salida_str = str(salida_input.value).strip()
            estado = estado_dropdown.value.strip()

            h_ent = h_sal = None

            try:
                h_ent = datetime.strptime(entrada_str, "%H:%M:%S")
            except:
                entrada_input.border_color = ft.colors.RED
                errores.append("🟥 Hora de entrada inválida (formato HH:MM:SS)")

            try:
                h_sal = datetime.strptime(salida_str, "%H:%M:%S")
            except:
                salida_input.border_color = ft.colors.RED
                errores.append("🟥 Hora de salida inválida (formato HH:MM:SS)")

            if h_ent and h_sal:
                if h_sal <= h_ent:
                    salida_input.border_color = ft.colors.RED
                    errores.append("🟥 La hora de salida debe ser mayor que la de entrada")
                if estado == "incompleto":
                    estado_dropdown.border_color = ft.colors.RED
                    errores.append("🟥 El estado no puede ser 'incompleto' si las horas están completas")

            self.page.update()

            if errores:
                ModalAlert.mostrar_info("Errores al guardar", "\n".join(errores))
                return

            resultado = self.asistencia_model.actualizar_asistencia_completa(
                numero_nomina=numero_nomina,
                fecha=fecha,
                hora_entrada=h_ent.strftime("%H:%M:%S"),
                hora_salida=h_sal.strftime("%H:%M:%S"),
                estado=estado
            )

            if resultado["status"] == "success":
                self.window_snackbar.show_success("✅ Asistencia actualizada correctamente.")
            else:
                ModalAlert.mostrar_info("Error", f"❌ {resultado['message']}")

            self._actualizar_tabla()

        def on_cancelar(_):
            self._actualizar_tabla()

        nueva_fila = ft.DataRow(cells=[
            ft.DataCell(ft.Text(str(numero_nomina))),
            ft.DataCell(ft.Text(registro.get("nombre", "-"))),
            ft.DataCell(ft.Text(fecha)),
            ft.DataCell(entrada_input),
            ft.DataCell(salida_input),
            ft.DataCell(ft.Text(registro.get("retardo", "-"))),
            ft.DataCell(estado_dropdown),
            ft.DataCell(ft.Text(registro.get("tiempo_trabajo", "-"))),
            ft.DataCell(ft.Row([
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, on_click=on_guardar),
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600, on_click=on_cancelar)
            ]))
        ])

        for i, row in enumerate(self.table.rows):
            if isinstance(row.cells[0].content, ft.Text) and \
            row.cells[0].content.value == str(numero_nomina) and \
            row.cells[2].content.value == fecha:
                self.table.rows[i] = nueva_fila
                break

        self.table.update()
        self.page.update()

    def _build_col(self, label, key, width=140):
        return ft.DataColumn(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Text(label),
                        ft.TextButton(
                            content=ft.Text(self._icono_orden(key), size=12),
                            style=ft.ButtonStyle(
                                padding=0,
                                overlay_color=ft.colors.TRANSPARENT,
                                shape=ft.RoundedRectangleBorder(radius=0),
                                color=ft.colors.GREY_600
                            ),
                            on_click=lambda e, k=key: self._sort_by(k)
                        )
                    ],
                    alignment=ft.MainAxisAlignment.START
                ),
                alignment=ft.alignment.center_left,
                width=width
            )
        )


