import flet as ft
import pandas as pd
from datetime import datetime
from app.core.invokers.file_open_invoker import FileOpenInvoker
from app.core.interfaces.database_mysql import DatabaseMysql


class AsistenciasImportController:
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
            asistencias = self._procesar_asistencias(df)
            if asistencias:
                print(f"\n🔎 Total de asistencias a procesar: {len(asistencias)}")
                self._insertar_asistencias(asistencias)

                if self.on_success:
                    self.on_success(path)

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
                numero_nomina = int(str(row["ID Checador"]).strip())
                nombre = str(row["Nombre"]).strip()
                sucursal = str(row["Sucursal"]).strip()
                fecha_str = str(row["Fecha"]).strip()
                turno = str(row["Turno"]).strip()
                entrada_turno = str(row["Entrada Turno"]).strip()
                salida_turno = str(row["Salida Turno"]).strip()
                entrada = str(row["Entrada"]).strip()
                salida = str(row["Salida"]).strip()
                tiempo_trabajo = str(row["Tiempo de trabajo"]).strip()
                tiempo_descanso = str(row["Tiempo de descanso"]).strip()
                retardo = str(row["Retardo"]).strip()
                estado = str(row["Estado"]).strip()

                # Normalizar valores TIME
                def normalizar_tiempo(valor):
                    if pd.isna(valor) or valor in ["", "nan", "NaT"]:
                        return "00:00:00"
                    return str(valor).strip()

                entrada_turno = normalizar_tiempo(entrada_turno)
                salida_turno = normalizar_tiempo(salida_turno)
                entrada = normalizar_tiempo(entrada)
                salida = normalizar_tiempo(salida)
                tiempo_trabajo = normalizar_tiempo(tiempo_trabajo)
                tiempo_descanso = normalizar_tiempo(tiempo_descanso)
                retardo = normalizar_tiempo(retardo)

                fecha_parseada = pd.to_datetime(fecha_str, dayfirst=True, errors='coerce')
                if pd.isna(fecha_parseada):
                    raise ValueError("Fecha inválida")

                asistencia = {
                    "numero_nomina": numero_nomina,
                    "nombre": nombre,
                    "sucursal": sucursal,
                    "fecha": fecha_parseada.strftime("%Y-%m-%d"),
                    "turno": turno,
                    "entrada_turno": entrada_turno,
                    "salida_turno": salida_turno,
                    "entrada": entrada,
                    "salida": salida,
                    "tiempo_trabajo": tiempo_trabajo,
                    "tiempo_descanso": tiempo_descanso,
                    "retardo": retardo,
                    "estado": estado
                }
                asistencias.append(asistencia)
            except Exception as e:
                print(f"⚠️ Error procesando fila {index + 1}: {e}")

        return asistencias

    def _insertar_asistencias(self, asistencias: list):
        for asistencia in asistencias:
            try:
                query = """
                    INSERT INTO asistencias (
                        numero_nomina, nombre, sucursal, fecha, turno,
                        entrada_turno, salida_turno, entrada, salida,
                        tiempo_trabajo, tiempo_descanso, retardo, estado
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                valores = (
                    asistencia["numero_nomina"],
                    asistencia["nombre"],
                    asistencia["sucursal"],
                    asistencia["fecha"],
                    asistencia["turno"],
                    asistencia["entrada_turno"],
                    asistencia["salida_turno"],
                    asistencia["entrada"],
                    asistencia["salida"],
                    asistencia["tiempo_trabajo"],
                    asistencia["tiempo_descanso"],
                    asistencia["retardo"],
                    asistencia["estado"]
                )
                self.db.run_query(query, valores)
                print(f"✅ Asistencia registrada: {valores}")
            except Exception as e:
                print(f"❌ Error insertando asistencia para {asistencia.get('numero_nomina')} el {asistencia.get('fecha')}: {e}")