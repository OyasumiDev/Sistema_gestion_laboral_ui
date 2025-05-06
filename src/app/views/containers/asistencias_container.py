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


class AsistenciasContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20)

        self.page = AppState().page
        self.asistencia_model = AssistanceModel()
        self.theme_ctrl = ThemeController()
        colors = self.theme_ctrl.get_colors()

        # Color personalizado para los botones en esta vista
        button_bg_color = ft.colors.GREY_700
        text_color = ft.colors.WHITE

        self.import_controller = AsistenciasImportController(
            page=self.page,
            on_success=self._actualizar_tabla
        )

        # Asegurar que el controlador tenga el método mostrar_selector
        if not hasattr(self.import_controller, "mostrar_selector"):
            def mostrar_selector():
                if hasattr(self.import_controller, "file_invoker") and self.import_controller.file_invoker:
                    self.import_controller.file_invoker.open()
            self.import_controller.mostrar_selector = mostrar_selector

        # Obtener botón de importación
        if hasattr(self.import_controller, "get_import_button"):
            self.import_button = self.import_controller.get_import_button(
                text="Importar Asistencias",
                icon_path="assets/buttons/import-button.png"
            )
            self.import_button.style = ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=0),
                bgcolor=button_bg_color,
                color=text_color
            )
        else:
            self.import_button = ft.FilledButton(
                content=ft.Row([
                    ft.Image(src="assets/buttons/import-button.png", width=20, height=20),
                    ft.Text("Importar Asistencias", color=text_color)
                ], spacing=10),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=0),
                    bgcolor=button_bg_color
                ),
                on_click=lambda _: self.import_controller.mostrar_selector()
            )

        self.save_invoker = FileSaveInvoker(
            page=self.page,
            on_save=self._exportar_asistencias,
            save_dialog_title="Exportar asistencias como Excel",
            file_name="asistencias_exportadas.xlsx",
            allowed_extensions=["xlsx"]
        )
        self.export_button = self.save_invoker.get_save_button(
            text="Exportar asistencias",
            icon_path="assets/buttons/export-button.png"
        )
        self.export_button.style = ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=0),
            bgcolor=button_bg_color,
            color=text_color
        )

        self.table = self._build_table()

        self.content = ft.Column(
            controls=[
                ft.Text("Registro de Asistencias", size=24, weight="bold"),
                ft.Row(controls=[self.import_button, self.export_button], spacing=10),
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        scroll=ft.ScrollMode.ALWAYS,
                        controls=[self.table],
                        expand=True
                    )
                )
            ],
            spacing=20,
            expand=True
        )

        self.depurar_asistencias()

    # ... el resto del código permanece igual ...


    def _build_table(self) -> ft.DataTable:
        resultado = self.asistencia_model.get_all()
        datos = resultado["data"] if resultado["status"] == "success" else []

        datos.sort(key=lambda x: (x.get("estado") != "incompleto", x.get("numero_nomina", 0)))

        columnas = [
            ft.DataColumn(ft.Text("ID Empleado")),
            ft.DataColumn(ft.Text("Empleado")),
            ft.DataColumn(ft.Text("Fecha")),
            ft.DataColumn(ft.Text("Turno")),
            ft.DataColumn(ft.Text("Entrada Turno")),
            ft.DataColumn(ft.Text("Salida Turno")),
            ft.DataColumn(ft.Text("Entrada")),
            ft.DataColumn(ft.Text("Salida")),
            ft.DataColumn(ft.Text("Descanso")),
            ft.DataColumn(ft.Text("Retardo")),
            ft.DataColumn(ft.Text("Estado")),
            ft.DataColumn(ft.Text("Horas Trabajadas")),
            ft.DataColumn(ft.Text("Total Horas")),
        ]

        filas = []

        for reg in datos:
            def limpiar(campo):
                return str(reg.get(campo)) if reg.get(campo) not in [None, ""] else "-"

            estilo = ft.TextStyle(color=ft.colors.RED) if reg.get("estado") == "incompleto" else None

            fila = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(reg.get("numero_nomina")), style=estilo)),
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
                ]
            )
            filas.append(fila)

        if not filas:
            filas.append(ft.DataRow(
                cells=[ft.DataCell(ft.Text("Sin registros"))] + [ft.DataCell(ft.Text("-")) for _ in range(len(columnas) - 1)]
            ))

        return ft.DataTable(
            expand=True,
            columns=columnas,
            rows=filas,
            column_spacing=20,
            horizontal_lines=ft.BorderSide(1),
        )

    def _actualizar_tabla(self, _=None):
        nuevas_filas = self._build_table().rows
        self.table.rows.clear()
        self.table.rows.extend(nuevas_filas)
        self.table.update()
        self.page.update()

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

            encabezado_superior = [
                ["CONTROL de Mexico"],
                ["Entradas y Salidas"],
                [f"Periodo: {datos[0]['fecha']} al {datos[-1]['fecha']}"] if datos else [""],
                ["Sucursales: Sucursal Matriz,Soriana,Mattel"],
                []
            ]

            cuerpo_tabla = []
            for reg in datos:
                fila = []
                for clave, _ in columnas:
                    valor = reg.get(clave)
                    if isinstance(valor, (datetime, pd.Timestamp)):
                        fila.append(valor.strftime("%H:%M:%S"))
                    elif isinstance(valor, str) and ":" in valor:
                        fila.append(valor)
                    elif valor in [None, ""]:
                        fila.append("00:00:00" if "hora" in clave or "tiempo" in clave or clave in ["retardo", "entrada_turno", "salida_turno"] else "")
                    else:
                        fila.append(str(valor))
                cuerpo_tabla.append(fila)

            encabezados = [nombre for _, nombre in columnas]
            df = pd.DataFrame(cuerpo_tabla, columns=encabezados)

            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                df.to_excel(writer, startrow=5, index=False, sheet_name="Asistencias")
                workbook = writer.book
                sheet = writer.sheets["Asistencias"]
                for idx, fila in enumerate(encabezado_superior, 1):
                    for col_idx, valor in enumerate(fila, 1):
                        sheet.cell(row=idx, column=col_idx, value=valor)

            print(f"✅ Asistencias exportadas exitosamente a: {path}")

        except PermissionError:
            print(f"❌ Error al exportar asistencias: El archivo está en uso o no tienes permisos para sobrescribirlo: {path}")
        except Exception as e:
            print(f"❌ Error al exportar asistencias: {e}")

    def depurar_asistencias(self):
        resultado = self.asistencia_model.get_all()
        if resultado["status"] != "success":
            print("❌ Error al obtener asistencias:", resultado["message"])
            return

        datos = resultado["data"]
        if not datos:
            print("⚠️ No hay asistencias registradas en la base de datos.")
            return

        columnas = [
            E_ASSISTANCE.ID.value,
            E_ASSISTANCE.NUMERO_NOMINA.value,
            E_ASSISTANCE.NOMBRE.value,
            E_ASSISTANCE.FECHA.value,
            E_ASSISTANCE.HORA_ENTRADA.value,
            E_ASSISTANCE.HORA_SALIDA.value,
            E_ASSISTANCE.DURACION_COMIDA.value,
            E_ASSISTANCE.TIPO_REGISTRO.value,
            E_ASSISTANCE.HORAS_TRABAJADAS.value,
            E_ASSISTANCE.TOTAL_HORAS_TRABAJADAS.value,
            E_ASSISTANCE.ENTRADA_TURNO.value,
            E_ASSISTANCE.SALIDA_TURNO.value,
            E_ASSISTANCE.TIEMPO_TRABAJO.value,
            E_ASSISTANCE.TIEMPO_DESCANSO.value,
            E_ASSISTANCE.RETARDO.value,
            E_ASSISTANCE.ESTADO.value,
            E_ASSISTANCE.TURNO.value
        ]

        tabla = [[registro.get(col) for col in columnas] for registro in datos]
        print("\n📋 Asistencias registradas en la base de datos:")
        print(tabulate(tabla, headers=columnas, tablefmt="grid"))
