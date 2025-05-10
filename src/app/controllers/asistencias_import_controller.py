import flet as ft
import pandas as pd
from datetime import datetime
from app.core.invokers.file_open_invoker import FileOpenInvoker
from app.core.interfaces.database_mysql import DatabaseMysql

class AsistenciasImportController:
    COLUMN_MAP = {
        "ID Checador": "numero_nomina",
        "Fecha": "fecha",
        "Entrada": "hora_entrada",
        "Salida": "hora_salida"
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
                # Prueba con fila 6 como encabezado
                df = pd.read_excel(path, engine=motor, header=5)
                columnas = list(df.columns)

                # Validar si se detectó realmente la columna "ID Checador"
                if "ID Checador" not in columnas:
                    print(f"❌ Encabezados inválidos detectados: {columnas}")
                    continue

                print(f"📥 Archivo cargado con motor '{motor}'")
                print(f"🧪 Columnas detectadas: {columnas}")
                return df

            except Exception as e:
                print(f"❌ Error con motor {motor}: {e}")
        return None


    def _procesar_asistencias(self, df: pd.DataFrame) -> list:
        asistencias = []

        for index, row in df.iterrows():
            try:
                numero_nomina_str = str(row.get("ID Checador", "")).strip()
                fecha_str = str(row.get("Fecha", "")).strip()
                entrada_str = str(row.get("Entrada", "")).strip()
                salida_str = str(row.get("Salida", "")).strip()

                if not numero_nomina_str.isdigit():
                    raise ValueError("ID Checador inválido")

                numero_nomina = int(numero_nomina_str)
                fecha = pd.to_datetime(fecha_str, dayfirst=True, errors='coerce')
                if pd.isna(fecha):
                    raise ValueError("Fecha inválida")

                hora_entrada = entrada_str if entrada_str else "00:00:00"
                hora_salida = salida_str if salida_str else "00:00:00"

                asistencia = {
                    "numero_nomina": numero_nomina,
                    "fecha": fecha.strftime("%Y-%m-%d"),
                    "hora_entrada": hora_entrada,
                    "hora_salida": hora_salida,
                    "retardo": "00:00:00",
                    "estado": "incompleto" if hora_entrada == "00:00:00" or hora_salida == "00:00:00" else "completo",
                    "tiempo_trabajo": "00:00:00",
                    "total_horas_trabajadas": "00:00:00"
                }

                asistencias.append(asistencia)

            except Exception as e:
                print(f"⚠️ Error procesando fila {index + 1}: {e}")

        return asistencias

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
                        numero_nomina,
                        fecha,
                        hora_entrada,
                        hora_salida
                    ) VALUES (%s, %s, %s, %s)
                """
                valores = (
                    asistencia["numero_nomina"],
                    asistencia["fecha"],
                    asistencia["hora_entrada"],
                    asistencia["hora_salida"]
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

    def _asistencia_existente(self, numero_nomina: int, fecha: str) -> bool:
        try:
            query = """
                SELECT COUNT(*) AS c FROM asistencias
                WHERE numero_nomina = %s AND fecha = %s
            """
            result = self.db.get_data(query, (numero_nomina, fecha), dictionary=True)
            existe = result.get("c", 0) > 0

            if existe:
                print(f"⛔ Duplicado detectado: asistencia ya existe para empleado {numero_nomina} en fecha {fecha}")

            return existe

        except Exception as e:
            print(f"❌ Error al verificar existencia de asistencia: {e}")
            return True  # Asumir duplicado si ocurre error

