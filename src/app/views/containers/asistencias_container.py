# app/views/containers/asistencias_container.py

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

        self.table = self._build_table()

        self.snack_bar = ft.SnackBar(
            content=ft.Text(""),
            bgcolor=ft.colors.RED_200,
            behavior=ft.SnackBarBehavior.FLOATING,
            duration=3000
        )
        self.page.snack_bar = self.snack_bar

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
                    alignment=ft.alignment.center,
                    content=ft.Container(
                        expand=True,
                        alignment=ft.alignment.center,
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
                                                content=self.table
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

    def _confirmar_eliminacion(self, numero_nomina, fecha):
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
        fecha_input = ft.TextField(hint_text="Fecha (YYYY-MM-DD)", width=150)
        entrada_input = ft.TextField(hint_text="Entrada (HH:MM:SS)", width=120)
        salida_input = ft.TextField(hint_text="Salida (HH:MM:SS)", width=120)

        def on_guardar(_):
            try:
                if not numero_input.value or not fecha_input.value or not entrada_input.value or not salida_input.value:
                    raise ValueError("Todos los campos son obligatorios")

                resultado = self.asistencia_model.add_manual_assistance(
                    numero_nomina=int(numero_input.value),
                    fecha=fecha_input.value.strip(),
                    hora_entrada=entrada_input.value.strip(),
                    hora_salida=salida_input.value.strip()
                )

                if resultado["status"] == "success":
                    print("✅ Asistencia agregada correctamente.")
                    self._actualizar_tabla()
                else:
                    self.page.snack_bar = ft.SnackBar(content=ft.Text(f"❌ {resultado['message']}"))
                    self.page.snack_bar.open = True
                    self.page.update()

            except Exception as ex:
                print(f"⚠️ Error al agregar asistencia: {ex}")
                self.page.snack_bar = ft.SnackBar(content=ft.Text(f"⚠️ {ex}"))
                self.page.snack_bar.open = True
                self.page.update()

        def on_cancelar(_):
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
            
    def _actualizar_tabla(self, _=None):
            nueva_tabla = self._build_table()
            self.table.columns = nueva_tabla.columns
            self.table.rows = nueva_tabla.rows
            self.table.update()
            self.page.update()

    def _actualizar_tabla(self, _=None):
        nueva_tabla = self._build_table()
        self.table.columns = nueva_tabla.columns
        self.table.rows = nueva_tabla.rows
        self.table.update()
        self.page.update()

    def _editar_asistencia_incompleta(self, numero_nomina, fecha, e=None):
        print(f"🛠️ Editando asistencia - ID: {numero_nomina}, Fecha: {fecha}")
        entrada_input = ft.TextField(label="Nueva hora de entrada (HH:MM:SS)", value="06:00:00")
        salida_input = ft.TextField(label="Nueva hora de salida (HH:MM:SS)", value="16:00:00")

        def on_guardar(_):
            try:
                if not entrada_input.value or not salida_input.value:
                    raise ValueError("Ambas horas son requeridas")

                print(f"➡️ Nuevos valores: Entrada={entrada_input.value}, Salida={salida_input.value}")

                resultado = self.asistencia_model.actualizar_horas_manualmente(
                    numero_nomina=numero_nomina,
                    fecha=fecha,
                    hora_entrada=entrada_input.value.strip(),
                    hora_salida=salida_input.value.strip()
                )

                if resultado["status"] == "success":
                    print("✅ Asistencia actualizada correctamente.")
                    self._actualizar_tabla()
                else:
                    print("❌", resultado["message"])

            except Exception as ex:
                print(f"⚠️ Error al editar asistencia: {ex}")
            finally:
                dialog.open = False
                self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Editar asistencia {numero_nomina} - {fecha}"),
            content=ft.Column([
                entrada_input,
                salida_input
            ], tight=True),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: setattr(dialog, "open", False)),
                ft.ElevatedButton("Guardar", on_click=on_guardar)
            ]
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
