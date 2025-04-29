# app/views/containers/asistencias_container.py

import flet as ft
import pandas as pd
from datetime import datetime
from app.models.assistance_model import AssistanceModel
from app.core.enums.e_assistance_model import E_ASSISTANCE
from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.core.app_state import AppState

class AsistenciasContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20)

        self.page = AppState().page  # ✅ Correctamente inicializado
        self.asistencia_model = AssistanceModel()

# Al crear el importer en AsistenciasContainer
        self.importer = FileSaveInvoker(
            page=self.page,
            on_save=self._dummy_save,
            on_import=self._on_file_selected,
            import_dialog_title="Importar asistencias desde Excel",
            import_extensions=["xlsx", "xls", "xlsb"]
        )



        self.import_button = self.importer.get_import_button(
            text="Importar Asistencias",
            icon_path="assets/buttons/import_asistencias-button.png"
        )

        self.data_table = self.crear_tabla_asistencias()

        self.content = ft.Column(
            controls=[
                ft.Text("Registro de Asistencias", size=24, weight="bold"),
                self.import_button,
                self.data_table
            ],
            spacing=20
        )

    def _dummy_save(self, path: str):
        pass

    def _on_file_selected(self, path: str):
        """Carga asistencias desde un archivo Excel."""
        if not path:
            print("No se seleccionó archivo.")
            return

        df = self._load_excel_file(path)
        if df is not None:
            asistencias = self._procesar_asistencias(df)
            if asistencias:
                self._subir_asistencias(asistencias)
                # Refrescar la tabla después de importar
                self.data_table.rows.clear()
                nueva_tabla = self.crear_tabla_asistencias()
                self.data_table.columns = nueva_tabla.columns
                self.data_table.rows.extend(nueva_tabla.rows)
                self.page.snack_bar = ft.SnackBar(
                    ft.Text("✅ Asistencias importadas exitosamente."),
                    bgcolor=ft.colors.GREEN
                )
                self.page.snack_bar.open = True
                self.page.update()

    def _load_excel_file(self, path: str):
        motores = ["openpyxl", "xlrd", "pyxlsb"]
        for motor in motores:
            try:
                df = pd.read_excel(path, engine=motor, header=0)
                print(f"Archivo '{path}' cargado correctamente con '{motor}'.")
                return df
            except Exception as e:
                print(f"Error con motor '{motor}': {e}")
        print("Error: No se pudo cargar el archivo con ningún motor disponible.")
        return None

    def _procesar_asistencias(self, df: pd.DataFrame):
        """Procesa el Excel de asistencias."""
        if df is None or df.empty:
            print("DataFrame vacío o inválido.")
            return None

        if len(df.columns) != 7:
            print("Error: El archivo Excel debe tener exactamente 7 columnas.")
            self.page.snack_bar = ft.SnackBar(
                ft.Text("⚠️ Error: El archivo debe tener 7 columnas."),
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
        asistencias = df.to_dict(orient="records")
        return asistencias

    def _subir_asistencias(self, asistencias: list):
        """Inserta asistencias usando AssistanceModel."""
        for asistencia in asistencias:
            self.asistencia_model.add(
                numero_nomina=asistencia['numero_nomina'],
                fecha=asistencia['fecha'],
                hora_entrada=asistencia['hora_entrada'],
                hora_salida=asistencia['hora_salida'],
                duracion_comida=asistencia['duracion_comida'],
                tipo_registro=asistencia['tipo_registro'],
                horas_trabajadas=asistencia['horas_trabajadas']
            )

    def crear_tabla_asistencias(self):
        resultado = self.asistencia_model.get_all()

        datos = []
        if resultado["status"] == "success":
            datos = resultado["data"]

        agrupadas = {}
        if datos:
            for reg in datos:
                numero = reg[E_ASSISTANCE.NUMERO_NOMINA.value]
                nombre = reg.get("nombre", "Empleado")
                fecha = reg[E_ASSISTANCE.FECHA.value]
                dia = datetime.strptime(fecha, "%Y-%m-%d").strftime("%A")

                if numero not in agrupadas:
                    agrupadas[numero] = {
                        "nombre": nombre,
                        "dias": {
                            "Monday": None,
                            "Tuesday": None,
                            "Wednesday": None,
                            "Thursday": None,
                            "Friday": None,
                            "Saturday": None,
                            "Sunday": None,
                        }
                    }

                agrupadas[numero]["dias"][dia] = True

        columnas = [
            ft.DataColumn(ft.Text("Empleado")),
            *[ft.DataColumn(ft.Text(dia)) for dia in ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]]
        ]

        filas = []
        if agrupadas:
            for num, info in agrupadas.items():
                dias = info["dias"]
                fila = ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Row(
                                controls=[
                                    ft.CircleAvatar(content=ft.Text(info["nombre"][0]), radius=20),
                                    ft.Text(info["nombre"], size=16)
                                ],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER
                            )
                        ),
                        ft.DataCell(self.icono_asistencia(dias["Monday"])),
                        ft.DataCell(self.icono_asistencia(dias["Tuesday"])),
                        ft.DataCell(self.icono_asistencia(dias["Wednesday"])),
                        ft.DataCell(self.icono_asistencia(dias["Thursday"])),
                        ft.DataCell(self.icono_asistencia(dias["Friday"])),
                        ft.DataCell(self.icono_asistencia(dias["Saturday"])),
                        ft.DataCell(self.icono_asistencia(dias["Sunday"])),
                    ]
                )
                filas.append(fila)
        else:
            fila_vacio = ft.DataRow(
                cells=[
                    ft.DataCell(
                        ft.Row(
                            controls=[
                                ft.CircleAvatar(content=ft.Text("-"), radius=20),
                                ft.Text("Sin registros", size=16)
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER
                        )
                    ),
                    *[ft.DataCell(self.icono_asistencia(None)) for _ in range(7)]
                ]
            )
            filas.append(fila_vacio)

        return ft.DataTable(columns=columnas, rows=filas)

    def icono_asistencia(self, asistencia):
        if asistencia is True:
            return ft.Icon(name=ft.icons.CHECK_CIRCLE, color=ft.colors.GREEN)
        elif asistencia is False:
            return ft.Icon(name=ft.icons.CANCEL, color=ft.colors.RED)
        else:
            return ft.Icon(name=ft.icons.HELP, color=ft.colors.AMBER)
