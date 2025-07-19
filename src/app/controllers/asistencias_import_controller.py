import flet as ft
import pandas as pd
from datetime import datetime

from app.core.invokers.file_open_invoker import FileOpenInvoker
from app.core.interfaces.database_mysql import DatabaseMysql
from app.models.assistance_model import AssistanceModel
from app.core.enums.e_assistance_model import E_ASSISTANCE


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
        self.asistencia_model = AssistanceModel()
        self.e_asistencia_model = E_ASSISTANCE  # ✅ Corrección aquí (sin paréntesis)
        self.ultimo_grupo_importado = None
        

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

        self.file_invoker.selected_path = path  # ✅ Guardar la ruta del archivo seleccionado

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
                    self.on_success()

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
                columnas = list(df.columns)
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
                entrada_raw = row.get("Entrada")
                salida_raw = row.get("Salida")

                if not numero_nomina_str.isdigit():
                    raise ValueError("ID Checador inválido")

                numero_nomina = int(numero_nomina_str)
                fecha = pd.to_datetime(fecha_str, dayfirst=True, errors='coerce')
                if pd.isna(fecha):
                    raise ValueError("Fecha inválida")

                def limpiar_hora(hora, campo):
                    if pd.isna(hora) or str(hora).strip().lower() in ["", "nan", "none"]:
                        print(f"⚠️ Hora vacía detectada en fila {index + 1} ({campo}). Se asigna '00:00:00'")
                        return "00:00:00"
                    return str(hora).strip()

                hora_entrada = limpiar_hora(entrada_raw, "Entrada")
                hora_salida = limpiar_hora(salida_raw, "Salida")

                asistencia = {
                    E_ASSISTANCE.NUMERO_NOMINA.value: numero_nomina,
                    E_ASSISTANCE.FECHA.value: fecha.strftime("%Y-%m-%d"),
                    E_ASSISTANCE.HORA_ENTRADA.value: hora_entrada,
                    E_ASSISTANCE.HORA_SALIDA.value: hora_salida,
                    E_ASSISTANCE.DESCANSO.value: 0  # Se calculará luego o en UI
                }

                asistencias.append(asistencia)

            except Exception as e:
                print(f"⚠️ Error procesando fila {index + 1}: {e}")

        return asistencias


    def _insertar_asistencias(self, asistencias: list):
        import os
        nombre_archivo = os.path.splitext(os.path.basename(self.file_invoker.selected_path))[0]
        grupo_importacion = f"Asistencias importadas {nombre_archivo}"
        self.ultimo_grupo_importado = grupo_importacion

        for asistencia in asistencias:
            try:
                if not self._existe_empleado(asistencia[E_ASSISTANCE.NUMERO_NOMINA.value]):
                    print(f"⚠️ Empleado {asistencia[E_ASSISTANCE.NUMERO_NOMINA.value]} no existe. Saltando...")
                    continue

                if self._asistencia_existente(asistencia[E_ASSISTANCE.NUMERO_NOMINA.value], asistencia[E_ASSISTANCE.FECHA.value]):
                    print(f"⛔ Ya existe asistencia para {asistencia[E_ASSISTANCE.NUMERO_NOMINA.value]} el {asistencia[E_ASSISTANCE.FECHA.value]}. Saltando...")
                    continue

                query = f"""
                    INSERT INTO {E_ASSISTANCE.TABLE.value} (
                        {E_ASSISTANCE.NUMERO_NOMINA.value},
                        {E_ASSISTANCE.FECHA.value},
                        {E_ASSISTANCE.HORA_ENTRADA.value},
                        {E_ASSISTANCE.HORA_SALIDA.value},
                        {E_ASSISTANCE.DESCANSO.value},
                        {E_ASSISTANCE.GRUPO_IMPORTACION.value}
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """
                valores = (
                    asistencia[E_ASSISTANCE.NUMERO_NOMINA.value],
                    asistencia[E_ASSISTANCE.FECHA.value],
                    asistencia[E_ASSISTANCE.HORA_ENTRADA.value],
                    asistencia[E_ASSISTANCE.HORA_SALIDA.value],
                    asistencia[E_ASSISTANCE.DESCANSO.value],
                    grupo_importacion
                )

                self.db.run_query(query, valores)
                print(f"✅ Asistencia registrada: {valores}")

            except Exception as e:
                print(f"❌ Error insertando asistencia para {asistencia.get(E_ASSISTANCE.NUMERO_NOMINA.value)} el {asistencia.get(E_ASSISTANCE.FECHA.value)}: {e}")


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
            return True
