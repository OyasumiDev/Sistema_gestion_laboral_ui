import os
import flet as ft
import pandas as pd
from datetime import datetime, time, timedelta
from typing import Optional

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

    # ✅ Descanso default buscado: MD = 1
    DESCANSO_DEFAULT = 1

    def __init__(self, page: ft.Page, on_success: callable = None):
        self.page = page
        self.db = DatabaseMysql()
        self.on_success = on_success
        self.asistencia_model = AssistanceModel()
        self.e_asistencia_model = E_ASSISTANCE
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

        self.file_invoker.selected_path = path

        df = self._cargar_excel(path)
        if df is None:
            self._snack("❌ No se pudo leer el archivo.", ft.colors.RED)
            return

        print(f"🧪 Columnas detectadas: {list(df.columns)}")

        faltantes = [col for col in self.COLUMN_MAP if col not in df.columns]
        if faltantes:
            print(f"❌ Columnas faltantes: {faltantes}")
            self._snack(f"⚠️ Columnas faltantes en el archivo: {', '.join(faltantes)}", ft.colors.RED)
            return

        asistencias = self._procesar_asistencias(df)
        if asistencias:
            print(f"\n🔎 Total de asistencias a procesar: {len(asistencias)}")
            self._insertar_asistencias(asistencias)

            if self.on_success:
                self.on_success()

            self._snack("✅ Asistencias importadas correctamente.", ft.colors.GREEN)

    # --------------------- Excel ---------------------
    def _cargar_excel(self, path: str) -> pd.DataFrame | None:
        motores = ["openpyxl", "xlrd", "pyxlsb"]
        for motor in motores:
            try:
                # Mantengo tu header=5, pero con fallback por si cambia
                df = pd.read_excel(path, engine=motor, header=5)
                columnas = list(df.columns)
                if "ID Checador" not in columnas:
                    # fallback header=0
                    df2 = pd.read_excel(path, engine=motor, header=0)
                    if "ID Checador" not in list(df2.columns):
                        print(f"❌ Encabezados inválidos detectados: {columnas}")
                        continue
                    df = df2
                    columnas = list(df.columns)

                print(f"📥 Archivo cargado con motor '{motor}'")
                print(f"🧪 Columnas detectadas: {columnas}")
                return df
            except Exception as e:
                print(f"❌ Error con motor {motor}: {e}")
        return None

    # --------------------- Normalización fuerte de hora ---------------------
    def _hora_a_hhmmss(self, hora, index: int, campo: str) -> str:
        """
        Normaliza Entrada/Salida a 'HH:MM:SS' para que MySQL TIME y triggers calculen en INSERT.
        """
        try:
            if hora is None or (isinstance(hora, float) and pd.isna(hora)):
                print(f"⚠️ Hora vacía detectada en fila {index + 1} ({campo}). Se asigna '00:00:00'")
                return "00:00:00"

            # pandas Timestamp / datetime
            if isinstance(hora, datetime):
                return hora.strftime("%H:%M:%S")

            # time
            if isinstance(hora, time):
                return hora.strftime("%H:%M:%S")

            # timedelta (MUY común en Excel)
            if isinstance(hora, timedelta):
                total = int(hora.total_seconds())
                hh = (total // 3600) % 24
                mm = (total % 3600) // 60
                ss = total % 60
                return f"{hh:02}:{mm:02}:{ss:02}"

            s = str(hora).strip()
            if not s or s.lower() in ["nan", "none"]:
                print(f"⚠️ Hora vacía detectada en fila {index + 1} ({campo}). Se asigna '00:00:00'")
                return "00:00:00"

            # Si viene como "0 days 06:24:00"
            if "day" in s and ":" in s:
                # tomar la parte final después del espacio
                parts = s.split()
                for p in reversed(parts):
                    if ":" in p:
                        s = p
                        break

            # Decimal fracción de día (0.25=06:00)
            try:
                if s.replace(".", "", 1).isdigit():
                    f = float(s)
                    if 0 <= f < 1:
                        total_seconds = int(round(f * 24 * 3600))
                        hh = total_seconds // 3600
                        mm = (total_seconds % 3600) // 60
                        ss = total_seconds % 60
                        return f"{hh:02}:{mm:02}:{ss:02}"
            except Exception:
                pass

            # HH:MM o HH:MM:SS
            parts = s.split(":")
            if len(parts) == 2:
                hh = int(parts[0])
                mm = int(parts[1])
                return f"{hh:02}:{mm:02}:00"
            if len(parts) >= 3:
                hh = int(parts[0])
                mm = int(parts[1])
                ss = int(parts[2])
                return f"{hh:02}:{mm:02}:{ss:02}"

            # Si no se pudo, devolver raw (último recurso)
            return s

        except Exception:
            return "00:00:00"

    # --------------------- Procesamiento ---------------------
    def _procesar_asistencias(self, df: pd.DataFrame) -> list:
        asistencias = []

        for index, row in df.iterrows():
            try:
                numero_nomina_str = str(row.get("ID Checador", "")).strip()

                # Excel a veces lo trae como 87.0
                if numero_nomina_str.endswith(".0") and numero_nomina_str.replace(".0", "").isdigit():
                    numero_nomina_str = numero_nomina_str.replace(".0", "")

                if not numero_nomina_str.isdigit():
                    raise ValueError("ID Checador inválido")

                numero_nomina = int(numero_nomina_str)

                fecha_raw = row.get("Fecha")
                fecha = pd.to_datetime(fecha_raw, dayfirst=True, errors="coerce")
                if pd.isna(fecha):
                    # intentar con string
                    fecha_str = str(fecha_raw).strip()
                    fecha = pd.to_datetime(fecha_str, dayfirst=True, errors="coerce")
                if pd.isna(fecha):
                    raise ValueError("Fecha inválida")

                entrada_raw = row.get("Entrada")
                salida_raw = row.get("Salida")

                # ✅ Normaliza a HH:MM:SS
                hora_entrada = self._hora_a_hhmmss(entrada_raw, index=index, campo="Entrada")
                hora_salida = self._hora_a_hhmmss(salida_raw, index=index, campo="Salida")

                asistencia = {
                    E_ASSISTANCE.NUMERO_NOMINA.value: numero_nomina,
                    E_ASSISTANCE.FECHA.value: fecha.strftime("%Y-%m-%d"),
                    E_ASSISTANCE.HORA_ENTRADA.value: hora_entrada,
                    E_ASSISTANCE.HORA_SALIDA.value: hora_salida,
                    # ✅ MD por default
                    E_ASSISTANCE.DESCANSO.value: self.DESCANSO_DEFAULT
                }

                asistencias.append(asistencia)

            except Exception as e:
                print(f"⚠️ Error procesando fila {index + 1}: {e}")

        return asistencias

    # --------------------- Inserción (tu lógica original, que sí validaba bien) ---------------------
    def _insertar_asistencias(self, asistencias: list):
        nombre_archivo = os.path.splitext(os.path.basename(self.file_invoker.selected_path))[0]
        grupo_importacion = f"Asistencias importadas {nombre_archivo}"
        self.ultimo_grupo_importado = grupo_importacion

        for asistencia in asistencias:
            try:
                num = asistencia[E_ASSISTANCE.NUMERO_NOMINA.value]
                fec = asistencia[E_ASSISTANCE.FECHA.value]

                if not self._existe_empleado(num):
                    print(f"⚠️ Empleado {num} no existe. Saltando...")
                    continue

                if self._asistencia_existente(num, fec):
                    print(f"⛔ Ya existe asistencia para {num} el {fec}. Saltando...")
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
                # Forzar MD en importación, ignorando cualquier valor en el archivo
                descanso_forzado = self.DESCANSO_DEFAULT
                asistencia[E_ASSISTANCE.DESCANSO.value] = descanso_forzado
                valores = (
                    num,
                    fec,
                    asistencia[E_ASSISTANCE.HORA_ENTRADA.value],
                    asistencia[E_ASSISTANCE.HORA_SALIDA.value],
                    descanso_forzado,  # ✅ MD=1
                    grupo_importacion
                )

                self.db.run_query(query, valores)
                print(f"✅ Asistencia registrada: {valores}")

            except Exception as e:
                print(f"❌ Error insertando asistencia para {asistencia.get(E_ASSISTANCE.NUMERO_NOMINA.value)} el {asistencia.get(E_ASSISTANCE.FECHA.value)}: {e}")

    # --------------------- Validaciones (igual que tu versión que funcionaba) ---------------------
    def _existe_empleado(self, numero_nomina: int) -> bool:
        try:
            result = self.db.get_data(
                "SELECT COUNT(*) AS c FROM empleados WHERE numero_nomina = %s",
                (numero_nomina,),
                dictionary=True
            )
            return (result or {}).get("c", 0) > 0
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
            existe = (result or {}).get("c", 0) > 0

            if existe:
                print(f"⛔ Duplicado detectado: asistencia ya existe para empleado {numero_nomina} en fecha {fecha}")

            return existe

        except Exception as e:
            print(f"❌ Error al verificar existencia de asistencia: {e}")
            # por seguridad: si no puedo verificar, mejor no insertar duplicados
            return True

    # --------------------- UI Snack ---------------------
    def _snack(self, texto: str, color):
        try:
            if not self.page:
                return
            self.page.snack_bar = ft.SnackBar(ft.Text(texto), bgcolor=color)
            self.page.snack_bar.open = True
            self.page.update()
        except Exception:
            pass
