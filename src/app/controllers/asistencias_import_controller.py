import flet as ft
import pandas as pd
from datetime import datetime
from app.core.invokers.file_open_invoker import FileOpenInvoker
from app.core.interfaces.database_mysql import DatabaseMysql

class AsistenciasImportController:
    COLUMN_MAP = {
        "ID Checador": "numero_nomina",
        "Fecha": "fecha",
        "Turno": "turno",
        "Entrada Turno": "entrada_turno",
        "Salida Turno": "salida_turno",
        "Entrada": "hora_entrada",
        "Salida": "hora_salida",
        "Tiempo de trabajo": "tiempo_trabajo",
        "Tiempo de descanso": "tiempo_descanso",
        "Retardo": "retardo",
        "Estado": "estado"
    }

    def __init__(self, page: ft.Page, on_success: callable = None):
        self.page = page
        self.db = DatabaseMysql()
        self.on_success = on_success

        self.file_invoker = FileOpenInvoker(
            page=self.page,
            on_select=self._on_file_selected,
            dialog_title="Selecciona archivo de asistencias",
            allowed_extensions=["xlsx", "xls", "xlsb"]
        )

    def get_import_button(self, text="Importar Asistencias", icon_path="assets/buttons/import_asistencias-button.png"):
        return self.file_invoker.get_open_button(text, icon_path)

    def _on_file_selected(self, path: str):
        if not path:
            print("⚠️ No se seleccionó ningún archivo.")
            return

        df = self._cargar_excel(path)
        if df is not None:
            print(f"🧪 Columnas detectadas: {list(df.columns)}")

            faltantes = [col for col in self.COLUMN_MAP if col not in df.columns]
            if faltantes:
                print(f"❌ Columnas faltantes: {faltantes}")
                self.page.snack_bar = ft.SnackBar(
                    ft.Text(f"⚠️ Columnas faltantes en el archivo: {', '.join(faltantes)}"),
                    bgcolor=ft.colors.RED
                )
                self.page.snack_bar.open = True
                self.page.update()
                return

            asistencias = self._procesar_asistencias(df)
            if asistencias:
                print(f"\n🔎 Total de asistencias a procesar: {len(asistencias)}")
                self._insertar_asistencias(asistencias)

                if self.on_success:
                    self.on_success()  # ✅ Sin argumento para evitar error

                self.page.snack_bar = ft.SnackBar(
                    ft.Text("✅ Asistencias importadas correctamente."),
                    bgcolor=ft.colors.GREEN
                )
                self.page.snack_bar.open = True
                self.page.update()

    def _cargar_excel(self, path: str) -> pd.DataFrame | None:
        motores = ["openpyxl", "xlrd", "pyxlsb"]
        for motor in motores:
            try:
                df = pd.read_excel(path, engine=motor, header=5)
                print(f"📥 Archivo cargado con motor '{motor}'")
                return df
            except Exception as e:
                print(f"❌ Error con motor {motor}: {e}")
        return None

    def _procesar_asistencias(self, df: pd.DataFrame) -> list:
        asistencias = []

        for index, row in df.iterrows():
            try:
                data = {}
                for col_excel, campo in self.COLUMN_MAP.items():
                    valor = str(row.get(col_excel, "")).strip()

                    if campo == "fecha":
                        fecha_parseada = pd.to_datetime(valor, dayfirst=True, errors='coerce')
                        if pd.isna(fecha_parseada):
                            raise ValueError("Fecha inválida")
                        data[campo] = fecha_parseada.strftime("%Y-%m-%d")

                    elif "tiempo" in campo or campo in ["hora_entrada", "hora_salida", "retardo"]:
                        if valor in ["", "nan", "NaT"]:
                            valor = "00:00:00"
                        data[campo] = valor

                    elif campo == "numero_nomina":
                        if valor == "" or valor.lower() in ["nan", "none"]:
                            raise ValueError("ID Checador vacío")
                        data[campo] = int(valor)

                    else:
                        data[campo] = valor

                asistencias.append(data)

            except Exception as e:
                print(f"⚠️ Error procesando fila {index + 1}: {e}")

        return asistencias
    
    def _asistencia_existente(self, numero_nomina: int, fecha: str) -> bool:
        try:
            query = """
                SELECT COUNT(*) AS c FROM asistencias
                WHERE numero_nomina = %s AND fecha = %s
            """
            result = self.db.get_data(query, (numero_nomina, fecha), dictionary=True)
            return result.get("c", 0) > 0
        except Exception as e:
            print(f"❌ Error al verificar existencia de asistencia: {e}")
            return True  # Por seguridad, evitar insert si hay error


    def _insertar_asistencias(self, asistencias: list):
        for asistencia in asistencias:
            try:
                if not self._existe_empleado(asistencia["numero_nomina"]):
                    print(f"⚠️ Empleado {asistencia['numero_nomina']} no existe. Saltando...")
                    continue

                if self._asistencia_existente(asistencia["numero_nomina"], asistencia["fecha"]):
                    print(f"⛔ Ya existe asistencia para {asistencia['numero_nomina']} el {asistencia['fecha']}. Saltando...")
                    continue

                query = """
                    INSERT INTO asistencias (
                        numero_nomina, fecha, turno,
                        entrada_turno, salida_turno,
                        hora_entrada, hora_salida,
                        tiempo_trabajo, tiempo_descanso,
                        retardo, estado
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                valores = (
                    asistencia["numero_nomina"],
                    asistencia["fecha"],
                    asistencia["turno"],
                    asistencia["entrada_turno"],
                    asistencia["salida_turno"],
                    asistencia["hora_entrada"],
                    asistencia["hora_salida"],
                    asistencia["tiempo_trabajo"],
                    asistencia["tiempo_descanso"],
                    asistencia["retardo"],
                    asistencia["estado"]
                )

                self.db.run_query(query, valores)
                print(f"✅ Asistencia registrada: {valores}")
            except Exception as e:
                print(f"❌ Error insertando asistencia para {asistencia.get('numero_nomina')} el {asistencia.get('fecha')}: {e}")


    def _existe_empleado(self, numero_nomina: int) -> bool:
        try:
            result = self.db.get_data(
                "SELECT COUNT(*) AS c FROM empleados WHERE numero_nomina = %s",
                (numero_nomina,),
                dictionary=True
            )
            return result.get("c", 0) > 0
        except Exception as e:
            print(f"❌ Error al verificar existencia de empleado {numero_nomina}: {e}")
            return False
