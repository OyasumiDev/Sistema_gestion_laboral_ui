import flet as ft
import pandas as pd
from datetime import datetime
from app.models.assistance_model import AssistanceModel
from app.core.enums.e_assistance_model import E_ASSISTANCE
from app.controllers.asistencias_import_controller import AsistenciasImportController
from app.core.app_state import AppState
from tabulate import tabulate


class AsistenciasContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20)

        self.page = AppState().page
        self.asistencia_model = AssistanceModel()

        self.import_controller = AsistenciasImportController(
            page=self.page,
            on_success=self._on_file_selected
        )
        self.import_button = self.import_controller.get_import_button()

        self.data_table = self.crear_tabla_asistencias()

        self.content = ft.Column(
            controls=[
                ft.Text("Registro de Asistencias", size=24, weight="bold"),
                self.import_button,
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        scroll=ft.ScrollMode.ALWAYS,
                        controls=[self.data_table],
                        expand=True
                    )
                )
            ],
            spacing=20,
            expand=True
        )

        self.depurar_asistencias()

    def _on_file_selected(self, path: str):
        if not path:
            print("⚠️ No se seleccionó ningún archivo.")
            return

        df = self._load_excel_file(path)
        if df is not None:
            asistencias = self._procesar_asistencias(df)
            if asistencias:
                nuevas, duplicadas = self._subir_asistencias(asistencias)
                self._actualizar_tabla()

                self.page.snack_bar = ft.SnackBar(
                    ft.Text(f"✅ {nuevas} nuevas asistencias importadas. {duplicadas} ya existían."),
                    bgcolor=ft.colors.GREEN
                )
                self.page.snack_bar.open = True
                self.page.update()

    def _load_excel_file(self, path: str):
        motores = ["openpyxl", "xlrd", "pyxlsb"]
        for motor in motores:
            try:
                df = pd.read_excel(path, engine=motor, header=0)
                print(f"📥 Archivo '{path}' cargado con motor '{motor}'.")
                return df
            except Exception as e:
                print(f"❌ Error con motor '{motor}': {e}")
        print("⚠️ No se pudo cargar el archivo con ningún motor disponible.")
        return None

    def _procesar_asistencias(self, df: pd.DataFrame):
        if df.empty or df is None:
            print("⚠️ DataFrame vacío o inválido.")
            return None

        if len(df.columns) != 7:
            self.page.snack_bar = ft.SnackBar(
                ft.Text("⚠️ El archivo debe tener exactamente 7 columnas."),
                bgcolor=ft.colors.RED
            )
            self.page.snack_bar.open = True
            self.page.update()
            return None

        df.columns = [
            'numero_nomina',
            'fecha',
            'hora_entrada',
            'hora_salida',
            'duracion_comida',
            'tipo_registro',
            'horas_trabajadas'
        ]
        return df.to_dict(orient="records")

    def _subir_asistencias(self, asistencias: list) -> tuple[int, int]:
        nuevas, duplicadas = 0, 0

        for asistencia in asistencias:
            numero_nomina = asistencia['numero_nomina']
            fecha = asistencia['fecha']

            if self.asistencia_model.get_by_empleado_fecha(numero_nomina, fecha):
                duplicadas += 1
                continue

            tipo_registro = asistencia.get('tipo_registro', 'manual')
            if tipo_registro not in ['automático', 'manual']:
                print(f"⚠️ tipo_registro inválido para {numero_nomina} el {fecha}: '{tipo_registro}' -> Se usará 'manual'")
                tipo_registro = 'manual'

            hora_salida = asistencia['hora_salida'] or None

            resultado = self.asistencia_model.add(
                numero_nomina=numero_nomina,
                fecha=fecha,
                hora_entrada=asistencia['hora_entrada'],
                hora_salida=hora_salida,
                duracion_comida=asistencia['duracion_comida'],
                tipo_registro=tipo_registro,
                horas_trabajadas=asistencia['horas_trabajadas']
            )
            if resultado["status"] == "success":
                nuevas += 1
            else:
                print(f"❌ Falló al insertar asistencia de {numero_nomina} el {fecha}: {resultado['message']}")

        return nuevas, duplicadas

    def _actualizar_tabla(self):
        self.data_table.content.rows.clear()
        nueva_tabla = self.crear_tabla_asistencias()
        self.data_table.content.columns = nueva_tabla.content.columns
        self.data_table.content.rows.extend(nueva_tabla.content.rows)
        self.page.update()

    def crear_tabla_asistencias(self):
        resultado = self.asistencia_model.get_all()
        datos = resultado["data"] if resultado["status"] == "success" else []

        # Ordenar por ID de empleado (numero_nomina)
        datos.sort(key=lambda x: x.get("numero_nomina", 0))

        columnas = [
            ft.DataColumn(ft.Text("ID Empleado")),
            ft.DataColumn(ft.Text("Empleado")),
            ft.DataColumn(ft.Text("Sucursal")),
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

            fila = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(reg.get("numero_nomina")))),
                    ft.DataCell(ft.Text(limpiar("nombre"))),
                    ft.DataCell(ft.Text(limpiar("sucursal"))),
                    ft.DataCell(ft.Text(limpiar("fecha"))),
                    ft.DataCell(ft.Text(limpiar("turno"))),
                    ft.DataCell(ft.Text(limpiar("entrada_turno"))),
                    ft.DataCell(ft.Text(limpiar("salida_turno"))),
                    ft.DataCell(ft.Text(limpiar("entrada"))),
                    ft.DataCell(ft.Text(limpiar("salida"))),
                    ft.DataCell(ft.Text(limpiar("tiempo_descanso"))),
                    ft.DataCell(ft.Text(limpiar("retardo"))),
                    ft.DataCell(ft.Text(limpiar("estado"))),
                    ft.DataCell(ft.Text(limpiar("tiempo_trabajo"))),
                    ft.DataCell(ft.Text(limpiar("total_horas_trabajadas"))),
                ]
            )
            filas.append(fila)

        if not filas:
            filas.append(ft.DataRow(
                cells=[ft.DataCell(ft.Text("Sin registros"))] + [ft.DataCell(ft.Text("-")) for _ in range(len(columnas) - 1)]
            ))

        return ft.Container(
            content=ft.DataTable(
                columns=columnas,
                rows=filas,
                column_spacing=20,
                horizontal_lines=ft.BorderSide(1),
                expand=True
            ),
            expand=True,
            border=ft.border.all(1),
            padding=10,
            bgcolor=ft.colors.BACKGROUND
        )

    def icono_asistencia(self, asistencia):
        if asistencia is True:
            return ft.Icon(name=ft.icons.CHECK_CIRCLE, color=ft.colors.GREEN)
        elif asistencia is False:
            return ft.Icon(name=ft.icons.CANCEL, color=ft.colors.RED)
        else:
            return ft.Icon(name=ft.icons.HELP, color=ft.colors.AMBER)

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
            E_ASSISTANCE.FECHA.value,
            E_ASSISTANCE.HORA_ENTRADA.value,
            E_ASSISTANCE.HORA_SALIDA.value,
            E_ASSISTANCE.DURACION_COMIDA.value,
            E_ASSISTANCE.TIPO_REGISTRO.value,
            E_ASSISTANCE.HORAS_TRABAJADAS.value,
            E_ASSISTANCE.TOTAL_HORAS_TRABAJADAS.value
        ]

        tabla = [[registro.get(col) for col in columnas] for registro in datos]
        print("\n📋 Asistencias registradas en la base de datos:")
        print(tabulate(tabla, headers=columnas, tablefmt="grid"))
