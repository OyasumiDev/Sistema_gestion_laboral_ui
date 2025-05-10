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
        super().__init__(expand=True, padding=20)

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

        self.scroll_column = ft.Column(
            controls=[],  # aquí se inyectan las filas
            scroll=ft.ScrollMode.ALWAYS,
            expand=True
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

        self.content = ft.Column(
            controls=[
                ft.Text("Registro de Asistencias", size=24, weight="bold", text_align=ft.TextAlign.CENTER),
                ft.Container(
                    alignment=ft.alignment.center_right,
                    padding=ft.padding.only(right=60, bottom=10),
                    content=ft.Row(
                        spacing=10,
                        controls=[
                            self.import_button,
                            self.export_button,
                            self.new_column_button
                        ]
                    )
                ),
                ft.Container(
                    alignment=ft.alignment.center,
                    expand=True,
                    padding=ft.padding.symmetric(horizontal=20, vertical=30),
                    content=ft.Container(
                        width=1500,
                        expand=True,
                        content=ft.Column(
                            controls=[self.scroll_column],
                            scroll=ft.ScrollMode.AUTO,
                            expand=True
                        )
                    )
                )
            ],
            spacing=20,
            expand=True
        )


        self._actualizar_tabla()
        self.page.update()


    def _get_sort_icon(self, key):
        if self.sort_key == key:
            return ft.icons.ARROW_UPWARD if self.sort_asc else ft.icons.ARROW_DOWNWARD
        return ft.icons.UNFOLD_MORE

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

        def build_col(label, key, width=140):
            return ft.DataColumn(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(label, weight=ft.FontWeight.BOLD),
                            ft.IconButton(
                                icon=self._get_sort_icon(key),
                                icon_size=16,
                                tooltip=f"Ordenar por {label}",
                                on_click=lambda e, k=key: self._sort_by(k)
                            )
                        ],
                        alignment=ft.MainAxisAlignment.START
                    ),
                    alignment=ft.alignment.center_left,
                    width=width
                )
            )

        columnas = [
            build_col("ID Empleado", "numero_nomina", width=110),
            ft.DataColumn(ft.Container(ft.Text("Empleado", weight="bold"), width=220)),
            build_col("Fecha", "fecha", width=130),
            ft.DataColumn(ft.Container(ft.Text("Entrada", weight="bold"), width=110)),
            ft.DataColumn(ft.Container(ft.Text("Salida", weight="bold"), width=110)),
            ft.DataColumn(ft.Container(ft.Text("Retardo", weight="bold"), width=110)),
            build_col("Estado", "estado", width=130),
            ft.DataColumn(ft.Container(ft.Text("Horas Trabajadas", weight="bold"), width=150)),
            ft.DataColumn(ft.Container(ft.Text("Acciones", weight="bold"), width=120))
        ]



        filas = []
        for reg in datos:
            estilo = ft.TextStyle(color=ft.colors.RED) if reg.get("estado") == "incompleto" else None
            numero = reg.get("numero_nomina")
            fecha = reg.get("fecha")

            eliminar_btn = ft.IconButton(
                icon=ft.icons.DELETE_OUTLINE,
                icon_size=20,
                icon_color=ft.colors.RED_600,
                tooltip="Eliminar registro",
                on_click=functools.partial(self._confirmar_eliminacion, numero, fecha)
            )

            editar_btn = ft.IconButton(
                icon=ft.icons.EDIT,
                icon_size=20,
                icon_color=ft.colors.BLUE,
                tooltip="Editar asistencia",
                on_click=functools.partial(self._editar_asistencia, numero, fecha)
            )

            def limpiar(campo):
                return str(reg.get(campo)) if reg.get(campo) not in [None, ""] else "-"

            fila = ft.DataRow(cells=[
                ft.DataCell(ft.Text(limpiar("numero_nomina"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("nombre"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("fecha"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("hora_entrada"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("hora_salida"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("retardo"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("estado"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("tiempo_trabajo"), style=estilo)),
                ft.DataCell(ft.Row([editar_btn, eliminar_btn], spacing=5))
            ])
            filas.append(fila)

        self.table = ft.DataTable(
            expand=True,
            columns=columnas,
            rows=filas,
            column_spacing=25,
            horizontal_lines=ft.BorderSide(1)
        )

        self.scroll_column.controls.clear()
        self.scroll_column.controls.append(self.table)
        self.page.update()


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

    def _insertar_asistencia_desde_columna(self, _):
        numero_input = ft.TextField(hint_text="ID Empleado", width=120)
        fecha_input = ft.TextField(hint_text="Fecha (YYYY-MM-DD)", width=160)
        entrada_input = ft.TextField(hint_text="Entrada (HH:MM:SS)", width=140)
        salida_input = ft.TextField(hint_text="Salida (HH:MM:SS)", width=140)

        fila = ft.DataRow(cells=[
            ft.DataCell(numero_input),
            ft.DataCell(ft.Text("-")),  # Nombre (no editable desde aquí)
            ft.DataCell(fecha_input),
            ft.DataCell(entrada_input),
            ft.DataCell(salida_input),
            ft.DataCell(ft.Text("00:00:00")),  # Retardo (calculado por trigger)
            ft.DataCell(ft.Text("completo")),  # Estado (calculado por trigger)
            ft.DataCell(ft.Text("00:00:00")),  # Tiempo trabajado (calculado por trigger)
            ft.DataCell(ft.Row([
                ft.IconButton(
                    icon=ft.icons.CHECK,
                    icon_color=ft.colors.GREEN_600,
                    on_click=lambda _: self._confirmar_insertar_asistencia(
                        numero_input, fecha_input, entrada_input, salida_input
                    )
                ),
                ft.IconButton(
                    icon=ft.icons.CLOSE,
                    icon_color=ft.colors.RED_600,
                    on_click=self._actualizar_tabla
                )
            ]))
        ])

        if self.table:
            self.table.rows.append(fila)
            self.table.update()
        self.page.update()


    def _confirmar_insertar_asistencia(self, numero_input, fecha_input, entrada_input, salida_input):
        ModalAlert(
            title_text="¿Insertar asistencia?",
            message="¿Deseas registrar esta asistencia en la base de datos?",
            on_confirm=lambda: self._guardar_asistencia_desde_columna(numero_input, fecha_input, entrada_input, salida_input),
            on_cancel=self._actualizar_tabla
        ).mostrar()


    def _guardar_asistencia_desde_columna(self, numero_input, fecha_input, entrada_input, salida_input):
        try:
            numero_str = numero_input.value.strip()
            fecha_str = fecha_input.value.strip()
            entrada_str = entrada_input.value.strip()
            salida_str = salida_input.value.strip()

            if not numero_str or not fecha_str:
                ModalAlert.mostrar_info("Validación", "El ID de empleado y la fecha son obligatorios")
                return

            try:
                numero = int(numero_str)
            except ValueError:
                ModalAlert.mostrar_info("Error", "El ID debe ser un número entero válido")
                return

            try:
                fecha_sql = datetime.strptime(fecha_str, "%d/%m/%Y").strftime("%Y-%m-%d")
            except ValueError:
                ModalAlert.mostrar_info("Error", "Formato de fecha inválido. Usa DD/MM/YYYY")
                return

            if self.asistencia_model.get_by_empleado_fecha(numero, fecha_sql):
                ModalAlert.mostrar_info("Advertencia", "Ya existe una asistencia para este empleado en esta fecha")
                return

            if not entrada_str or not salida_str:
                entrada_str = "00:00:00"
                salida_str = "00:00:00"
            else:
                try:
                    h_ent = datetime.strptime(entrada_str, "%H:%M:%S")
                    h_sal = datetime.strptime(salida_str, "%H:%M:%S")
                    if h_sal <= h_ent:
                        ModalAlert.mostrar_info("Error", "La hora de salida debe ser mayor que la de entrada")
                        return
                except ValueError:
                    ModalAlert.mostrar_info("Error", "Formato de hora inválido. Usa HH:MM:SS")
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

        except Exception as e:
            print(f"⚠️ Error en _guardar_asistencia_desde_columna: {e}")
            ModalAlert.mostrar_info("Excepción", str(e))

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
            

    def _insertar_fila_editable(self, e=None):
        numero_input = ft.TextField(hint_text="ID Empleado", width=100, keyboard_type=ft.KeyboardType.NUMBER)
        fecha_input = ft.TextField(hint_text="Fecha (DD/MM/YYYY)", width=150)
        entrada_input = ft.TextField(hint_text="Entrada (HH:MM:SS)", width=120)
        salida_input = ft.TextField(hint_text="Salida (HH:MM:SS)", width=120)

        def on_guardar(_):
            print("➡️ Guardar asistencia manual presionado")
            try:
                numero_str = numero_input.value.strip()
                fecha_str = fecha_input.value.strip()
                entrada = entrada_input.value.strip()
                salida = salida_input.value.strip()

                print(f"📥 Datos recibidos → ID: {numero_str}, Fecha: {fecha_str}, Entrada: {entrada}, Salida: {salida}")

                if not numero_str or not fecha_str:
                    raise ValueError("El ID de empleado y la fecha son obligatorios.")

                try:
                    numero = int(numero_str)
                    print(f"✅ ID convertido correctamente: {numero}")
                except ValueError:
                    raise ValueError("El ID debe ser un número entero válido.")

                try:
                    fecha_sql = datetime.strptime(fecha_str, "%d/%m/%Y").strftime("%Y-%m-%d")
                    print(f"✅ Fecha convertida a SQL: {fecha_sql}")
                except ValueError:
                    raise ValueError("Formato de fecha inválido. Usa DD/MM/YYYY.")

                estado = "completo"
                if not entrada or not salida:
                    print("⚠️ Faltan horas. Se asigna 'incompleto' y se usa 00:00:00.")
                    estado = "incompleto"
                    entrada = "00:00:00"
                    salida = "00:00:00"
                else:
                    try:
                        h_ent = datetime.strptime(entrada, "%H:%M:%S")
                        h_sal = datetime.strptime(salida, "%H:%M:%S")
                        if h_sal <= h_ent:
                            raise ValueError("La hora de salida debe ser mayor que la de entrada.")
                    except ValueError:
                        raise ValueError("Formato de hora inválido. Usa HH:MM:SS")

                resultado = self.asistencia_model.add_manual_assistance(
                    numero_nomina=numero,
                    fecha=fecha_sql,
                    hora_entrada=entrada,
                    hora_salida=salida,
                    estado=estado
                )

                print("🗃️ Resultado:", resultado)
                if resultado["status"] == "success":
                    self.window_snackbar.show_success("✅ Asistencia agregada correctamente.")
                    self._actualizar_tabla()
                else:
                    ModalAlert.mostrar_info("Error", f"❌ {resultado['message']}")

            except Exception as ex:
                print(f"❌ Excepción atrapada: {ex}")
                ModalAlert.mostrar_info("Error de validación", str(ex))

            self.page.update()

        def on_cancelar(_):
            print("❌ Cancelación de fila manual")
            self.table.rows.pop()
            self.page.update()

        nueva_fila = ft.DataRow(cells=[
            ft.DataCell(numero_input),
            ft.DataCell(ft.Text("-")),  # nombre
            ft.DataCell(fecha_input),
            ft.DataCell(entrada_input),
            ft.DataCell(salida_input),
            ft.DataCell(ft.Text("-")),  # retardo
            ft.DataCell(ft.Text("-")),  # estado
            ft.DataCell(ft.Text("-")),  # tiempo_trabajo
            ft.DataCell(ft.Row([
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, on_click=on_guardar),
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600, on_click=on_cancelar)
            ]))
        ])

        self.table.rows.append(nueva_fila)
        self.page.update()



    def _editar_asistencia(self, numero_nomina, fecha, e=None):
        registro = next((r for r in self.asistencia_model.get_all()["data"]
                        if r["numero_nomina"] == numero_nomina and r["fecha"] == fecha), None)

        if not registro:
            self.window_snackbar.show_error("Registro no encontrado.")
            return

        entrada_input = ft.TextField(value=str(registro.get("hora_entrada", "")), width=130)
        salida_input = ft.TextField(value=str(registro.get("hora_salida", "")), width=130)
        estado_dropdown = ft.Dropdown(
            value=registro.get("estado", "incompleto"),
            options=[ft.dropdown.Option("completo"), ft.dropdown.Option("incompleto")],
            width=130
        )

        def on_guardar(_):
            print("✏️ Guardar edición de asistencia")
            try:
                entrada = entrada_input.value.strip()
                salida = salida_input.value.strip()
                estado = estado_dropdown.value

                if not entrada or not salida:
                    raise ValueError("Hora de entrada y salida son obligatorias.")

                try:
                    print(f"⏰ Entrada: '{entrada}', Salida: '{salida}'")
                    h_ent = datetime.strptime(entrada, "%H:%M:%S")
                    h_sal = datetime.strptime(salida, "%H:%M:%S")
                    if h_sal <= h_ent:
                        raise ValueError("La hora de salida debe ser mayor que la de entrada.")
                except ValueError as ve:
                    raise ValueError(f"Formato de hora inválido. Usa HH:MM:SS — {ve}")

                # Se asume que la fecha ya viene en formato YYYY-MM-DD
                fecha_sql = fecha

                resultado = self.asistencia_model.actualizar_asistencia_completa(
                    numero_nomina=numero_nomina,
                    fecha=fecha_sql,
                    hora_entrada=h_ent.strftime("%H:%M:%S"),
                    hora_salida=h_sal.strftime("%H:%M:%S"),
                    estado=estado
                )

                print("📝 Resultado edición:", resultado)
                if resultado["status"] == "success":
                    self.window_snackbar.show_success("✅ Asistencia actualizada correctamente.")
                else:
                    ModalAlert.mostrar_info("Error", f"❌ {resultado['message']}")

            except Exception as ex:
                print(f"❌ Excepción: {ex}")
                ModalAlert.mostrar_info("Error de edición", str(ex))

            self._actualizar_tabla()

        def on_cancelar(_):
            print("❌ Cancelación de edición de asistencia")
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
