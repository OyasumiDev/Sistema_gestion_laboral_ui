import flet as ft
import pandas as pd
from datetime import datetime
from app.models.assistance_model import AssistanceModel
from app.core.enums.e_assistance_model import E_ASSISTANCE
from app.controllers.asistencias_import_controller import AsistenciasImportController
from app.core.app_state import AppState
from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.views.containers.theme_controller import ThemeController
from tabulate import tabulate
from app.views.containers.modal_alert import ModalAlert 
import functools
from app.views.containers.window_snackbar import WindowSnackbar
from datetime import datetime, timedelta


class AsistenciasContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20)

        self.page = AppState().page
        self.asistencia_model = AssistanceModel()
        self.theme_ctrl = ThemeController()

        self.sort_key = "numero_nomina"
        self._tabla_vacia = True
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

        self.table = self._build_table()

        self.window_snackbar = WindowSnackbar(self.page)

        self.import_button = ft.GestureDetector(
            on_tap=lambda _: self.import_controller.file_invoker.open(),
            content=ft.Container(
                padding=8,
                border_radius=12,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=ft.Row([
                    ft.Image(src="assets/buttons/import-button.png", width=20, height=20),
                    ft.Text("Importar", size=11, weight="bold")
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=5)
            )
        )

        self.export_button = ft.GestureDetector(
            on_tap=lambda _: self.save_invoker.open_save(),
            content=ft.Container(
                padding=8,
                border_radius=12,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=ft.Row([
                    ft.Image(src="assets/buttons/export-button.png", width=20, height=20),
                    ft.Text("Exportar", size=11, weight="bold")
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=5)
            )
        )

        self.add_button = ft.GestureDetector(
            on_tap=self._insertar_fila_editable,
            content=ft.Container(
                padding=8,
                border_radius=12,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=ft.Row([
                    ft.Icon(name=ft.icons.ADD, size=20),
                    ft.Text("Agregar", size=11, weight="bold")
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=5)
            )
        )
        
        self.table = self._build_table()
        
        self.content = ft.Column(
            controls=[
                ft.Text("Registro de Asistencias", size=24, weight="bold"),
                ft.Container(
                    alignment=ft.alignment.center_right,
                    padding=ft.padding.only(right=60, bottom=10),
                    content=ft.Row(
                        spacing=10,
                        controls=[
                            self.import_button,
                            self.export_button,
                            self.add_button
                        ]
                    )
                ),
                ft.Container(
                    expand=True,
                    padding=ft.padding.only(top=40 if self._tabla_vacia else 120),
                    alignment=ft.alignment.top_center,
                    content=ft.Container(
                        expand=True,
                        alignment=ft.alignment.top_center,
                        content=ft.Column(
                            expand=True,
                            alignment=ft.MainAxisAlignment.START,
                            scroll=ft.ScrollMode.ALWAYS,
                            controls=[
                                ft.Container(
                                    expand=True,
                                    content=ft.Row(
                                        controls=[
                                            ft.Container(
                                                expand=True,
                                                content=self.table  # Tabla ya insertada
                                            )
                                        ]
                                    )
                                )
                            ]
                        )
                    )
                )
            ],
            spacing=20,
            expand=True
        )

        self.depurar_asistencias()
        self.page.update()


    def _get_sort_icon(self, key):
        if self.sort_key == key:
            return ft.Icon(ft.icons.ARROW_UPWARD if self.sort_asc else ft.icons.ARROW_DOWNWARD, size=14)
        return ft.Container()

    def _sort_by(self, key):
        if self.sort_key == key:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_key = key
            self.sort_asc = True
        self._actualizar_tabla()

    def _build_table(self) -> ft.DataTable:
        resultado = self.asistencia_model.get_all()
        datos = resultado["data"] if resultado["status"] == "success" else []

        datos.sort(key=lambda x: x.get(self.sort_key, 0), reverse=not self.sort_asc)

        columnas = [
            ft.DataColumn(
                ft.Row([
                    ft.Text("ID Empleado"),
                    ft.IconButton(
                        icon=ft.icons.ARROW_UPWARD if self.sort_key == "numero_nomina" and self.sort_asc else
                            ft.icons.ARROW_DOWNWARD if self.sort_key == "numero_nomina" else
                            ft.icons.UNFOLD_MORE,
                        icon_size=16,
                        tooltip="Ordenar por ID",
                        on_click=lambda _: self._sort_by("numero_nomina")
                    )
                ])
            ),
            ft.DataColumn(ft.Text("Empleado")),
            ft.DataColumn(
                ft.Row([
                    ft.Text("Fecha"),
                    ft.IconButton(
                        icon=ft.icons.ARROW_UPWARD if self.sort_key == "fecha" and self.sort_asc else
                            ft.icons.ARROW_DOWNWARD if self.sort_key == "fecha" else
                            ft.icons.UNFOLD_MORE,
                        icon_size=16,
                        tooltip="Ordenar por Fecha",
                        on_click=lambda _: self._sort_by("fecha")
                    )
                ])
            ),
            ft.DataColumn(ft.Text("Turno")),
            ft.DataColumn(ft.Text("Entrada Turno")),
            ft.DataColumn(ft.Text("Salida Turno")),
            ft.DataColumn(ft.Text("Entrada")),
            ft.DataColumn(ft.Text("Salida")),
            ft.DataColumn(ft.Text("Descanso")),
            ft.DataColumn(ft.Text("Retardo")),
            ft.DataColumn(
                ft.Row([
                    ft.Text("Estado"),
                    ft.IconButton(
                        icon=ft.icons.ARROW_UPWARD if self.sort_key == "estado" and self.sort_asc else
                            ft.icons.ARROW_DOWNWARD if self.sort_key == "estado" else
                            ft.icons.UNFOLD_MORE,
                        icon_size=16,
                        tooltip="Ordenar por Estado",
                        on_click=lambda _: self._sort_by("estado")
                    )
                ])
            ),
            ft.DataColumn(ft.Text("Horas Trabajadas")),
            ft.DataColumn(ft.Text("Total Horas")),
            ft.DataColumn(ft.Text("Acciones"))
        ]

        filas = []
        for reg in datos:
            def limpiar(campo):
                return str(reg.get(campo)) if reg.get(campo) not in [None, ""] else "-"

            estilo = ft.TextStyle(color=ft.colors.RED) if reg.get("estado") == "incompleto" else None
            numero = reg.get("numero_nomina")
            fecha = reg.get("fecha")

            eliminar_btn = ft.IconButton(
                icon=ft.icons.DELETE_FOREVER,
                icon_size=20,
                icon_color=ft.colors.RED,
                tooltip="Eliminar registro",
                on_click=functools.partial(self._confirmar_eliminacion, numero, fecha)
            )

            editar_btn = ft.IconButton(
                icon=ft.icons.EDIT_NOTE,
                icon_size=20,
                icon_color=ft.colors.BLUE,
                tooltip="Editar asistencia",
                on_click=functools.partial(self._editar_asistencia_incompleta, numero, fecha)
            ) if reg.get("estado") == "incompleto" else ft.Container()

            fila = ft.DataRow(cells=[
                ft.DataCell(ft.Text(limpiar("numero_nomina"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("nombre"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("fecha"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("turno"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("entrada_turno"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("salida_turno"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("hora_entrada"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("hora_salida"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("tiempo_descanso"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("retardo"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("estado"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("tiempo_trabajo"), style=estilo)),
                ft.DataCell(ft.Text(limpiar("total_horas_trabajadas"), style=estilo)),
                ft.DataCell(ft.Row([editar_btn, eliminar_btn], spacing=5))
            ])
            filas.append(fila)

        if not filas:
            filas.append(ft.DataRow(
                cells=[ft.DataCell(ft.Text("Sin registros"))] + [ft.DataCell(ft.Text("-")) for _ in range(len(columnas) - 1)]
            ))

        return ft.DataTable(
            expand=True,
            columns=columnas,
            rows=filas,
            column_spacing=25,
            horizontal_lines=ft.BorderSide(1),
        )

    def _confirmar_eliminacion(self, numero_nomina, fecha, e=None):

        modal = ModalAlert(
            title_text="Confirmar eliminación",
            message=f"¿Deseas eliminar la asistencia del empleado {numero_nomina} en {fecha}?",
            on_confirm=lambda: self._eliminar_asistencia(numero_nomina, fecha),
            on_cancel=lambda: print("❌ Eliminación cancelada.")
        )
        modal.mostrar()


    def _eliminar_asistencia(self, numero_nomina, fecha):
        try:
            resultado = self.asistencia_model.delete_by_numero_nomina_and_fecha(numero_nomina, fecha)
            if resultado["status"] == "success":
                print(f"✅ Asistencia del empleado {numero_nomina} en {fecha} eliminada correctamente.")
            else:
                print("❌", resultado["message"])
        except Exception as e:
            print("❌ Error al eliminar:", e)
        self._actualizar_tabla()


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
                ("turno", "Turno"),
                ("entrada_turno", "Entrada Turno"),
                ("salida_turno", "Salida Turno"),
                ("hora_entrada", "Entrada"),
                ("hora_salida", "Salida"),
                ("tiempo_trabajo", "Tiempo de trabajo"),
                ("tiempo_descanso", "Tiempo de descanso"),
                ("retardo", "Retardo"),
                ("estado", "Estado"),
                ("total_horas_trabajadas", "Total de horas")
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

        snackbar = self.window_snackbar

        def on_guardar(_):
            print("➡️ Guardar asistencia manual presionado")
            try:
                numero = numero_input.value.strip()
                fecha = fecha_input.value.strip()
                entrada = entrada_input.value.strip()
                salida = salida_input.value.strip()

                if not numero or not fecha or not entrada or not salida:
                    raise ValueError("Todos los campos son obligatorios")

                try:
                    datetime.strptime(fecha, "%d/%m/%Y")
                except ValueError:
                    raise ValueError("Formato de fecha inválido. Usa DD/MM/YYYY")

                try:
                    hora_entrada = datetime.strptime(entrada, "%H:%M:%S")
                    hora_salida = datetime.strptime(salida, "%H:%M:%S")
                except ValueError:
                    raise ValueError("Formato de hora inválido. Usa HH:MM:SS")

                if hora_salida <= hora_entrada:
                    raise ValueError("La hora de salida debe ser mayor que la de entrada")

                fecha_sql = datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")

                resultado = self.asistencia_model.add_manual_assistance(
                    numero_nomina=int(numero),
                    fecha=fecha_sql,
                    hora_entrada=hora_entrada.strftime("%H:%M:%S"),
                    hora_salida=hora_salida.strftime("%H:%M:%S")
                )

                print("🗃️ Resultado:", resultado)
                if resultado["status"] == "success":
                    snackbar.show_success("✅ Asistencia agregada correctamente.")
                    self._actualizar_tabla()
                else:
                    snackbar.show_error(f"❌ {resultado['message']}")

            except Exception as ex:
                print(f"❌ Excepción: {ex}")
                snackbar.show_error(f"⚠️ {ex}")

            self.page.update()

        def on_cancelar(_):
            print("❌ Cancelación de fila manual")
            self.table.rows.pop()
            self.page.update()

        nueva_fila = ft.DataRow(cells=[
            ft.DataCell(numero_input),
            ft.DataCell(ft.Text("")),
            ft.DataCell(fecha_input),
            ft.DataCell(ft.Text("Turno General")),
            ft.DataCell(ft.Text("-")),
            ft.DataCell(ft.Text("-")),
            ft.DataCell(entrada_input),
            ft.DataCell(salida_input),
            ft.DataCell(ft.Text("-")),
            ft.DataCell(ft.Text("-")),
            ft.DataCell(ft.Text("-")),
            ft.DataCell(ft.Text("-")),
            ft.DataCell(ft.Text("-")),
            ft.DataCell(ft.Row([
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, on_click=on_guardar),
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600, on_click=on_cancelar)
            ]))
        ])

        self.table.rows.append(nueva_fila)
        self.page.update()

    def _editar_asistencia_incompleta(self, numero_nomina, fecha, e=None):
        print(f"🛠️ Editando asistencia - ID: {numero_nomina}, Fecha: {fecha}")

        registro = next((r for r in self.asistencia_model.get_all()["data"]
                        if r["numero_nomina"] == numero_nomina and r["fecha"] == fecha), None)

        if not registro:
            print("❌ Registro no encontrado.")
            return

        def convertir_a_str(valor):
            if isinstance(valor, timedelta):
                total_seconds = int(valor.total_seconds())
                horas = total_seconds // 3600
                minutos = (total_seconds % 3600) // 60
                segundos = total_seconds % 60
                return f"{horas:02}:{minutos:02}:{segundos:02}"
            return str(valor) if valor is not None else ""

        entrada_input = ft.TextField(
            value=convertir_a_str(registro.get("hora_entrada")),
            width=250
        )

        salida_input = ft.TextField(
            value=convertir_a_str(registro.get("hora_salida")),
            width=250
        )

        snackbar = self.window_snackbar

        def on_guardar(_):
            print("➡️ Guardar edición presionado")
            try:
                entrada_val = entrada_input.value
                salida_val = salida_input.value

                if not isinstance(entrada_val, str) or not isinstance(salida_val, str):
                    raise ValueError("Las horas deben ser texto en formato HH:MM:SS")

                entrada = entrada_val.strip()
                salida = salida_val.strip()

                if not entrada or not salida:
                    raise ValueError("Ambas horas son requeridas")

                hora_ent = datetime.strptime(entrada, "%H:%M:%S")
                hora_sal = datetime.strptime(salida, "%H:%M:%S")

                if hora_sal <= hora_ent:
                    raise ValueError("La hora de salida debe ser mayor que la de entrada")

                fecha_sql = datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")

                resultado = self.asistencia_model.actualizar_horas_manualmente(
                    numero_nomina=numero_nomina,
                    fecha=fecha_sql,
                    hora_entrada=hora_ent.strftime("%H:%M:%S"),
                    hora_salida=hora_sal.strftime("%H:%M:%S")
                )

                print("🗃️ Resultado:", resultado)
                if resultado["status"] == "success":
                    self.asistencia_model.actualizar_estado_asistencia(
                        numero_nomina=numero_nomina,
                        fecha=fecha_sql
                    )
                    snackbar.show_success("✅ Asistencia actualizada correctamente.")
                    self._actualizar_tabla()

                else:
                    snackbar.show_error(f"❌ {resultado['message']}")

            except Exception as ex:
                print(f"❌ Excepción capturada: {ex}")
                snackbar.show_error(f"⚠️ {ex}")

            finally:
                self.page.update()

        def on_cancelar(_):
            print("❌ Edición cancelada.")
            self._actualizar_tabla()

        nueva_fila = ft.DataRow(cells=[
            ft.DataCell(ft.Text(str(registro.get("numero_nomina")))),
            ft.DataCell(ft.Text(registro.get("nombre", "-"))),
            ft.DataCell(ft.Text(registro.get("fecha", "-"))),
            ft.DataCell(ft.Text(registro.get("turno", "-"))),
            ft.DataCell(ft.Text(registro.get("entrada_turno", "-"))),
            ft.DataCell(ft.Text(registro.get("salida_turno", "-"))),
            ft.DataCell(entrada_input),
            ft.DataCell(salida_input),
            ft.DataCell(ft.Text(registro.get("tiempo_descanso", "-"))),
            ft.DataCell(ft.Text(registro.get("retardo", "-"))),
            ft.DataCell(ft.Text(registro.get("estado", "-"))),
            ft.DataCell(ft.Text(registro.get("tiempo_trabajo", "-"))),
            ft.DataCell(ft.Text(registro.get("total_horas_trabajadas", "-"))),
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



        def on_cancelar(_):
            print("❌ Edición cancelada.")
            self._actualizar_tabla()

        nueva_fila = ft.DataRow(cells=[
            ft.DataCell(ft.Text(str(registro.get("numero_nomina")))),
            ft.DataCell(ft.Text(registro.get("nombre", "-"))),
            ft.DataCell(ft.Text(registro.get("fecha", "-"))),
            ft.DataCell(ft.Text(registro.get("turno", "-"))),
            ft.DataCell(ft.Text(registro.get("entrada_turno", "-"))),
            ft.DataCell(ft.Text(registro.get("salida_turno", "-"))),
            ft.DataCell(entrada_input),
            ft.DataCell(salida_input),
            ft.DataCell(ft.Text(registro.get("tiempo_descanso", "-"))),
            ft.DataCell(ft.Text(registro.get("retardo", "-"))),
            ft.DataCell(ft.Text(registro.get("estado", "-"))),
            ft.DataCell(ft.Text(registro.get("tiempo_trabajo", "-"))),
            ft.DataCell(ft.Text(registro.get("total_horas_trabajadas", "-"))),
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

    def _actualizar_tabla(self, _=None):
        nueva_tabla = self._build_table()
        self.table.columns = nueva_tabla.columns
        self.table.rows = nueva_tabla.rows
        self.table.update()