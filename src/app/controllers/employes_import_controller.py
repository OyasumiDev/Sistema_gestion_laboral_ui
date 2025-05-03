import flet as ft
import pandas as pd
from app.core.invokers.file_open_invoker import FileOpenInvoker
from app.core.interfaces.database_mysql import DatabaseMysql


class EmpleadosImportController:
    def __init__(self, page: ft.Page, on_success: callable = None):
        self.page = page
        self.db = DatabaseMysql()
        self.on_success = on_success

        self.file_invoker = FileOpenInvoker(
            page=self.page,
            on_select=self._on_file_selected,
            dialog_title="Selecciona archivo de empleados",
            allowed_extensions=["xlsx", "xls", "xlsb"]
        )

    def get_import_button(self, text="Importar Empleados", icon_path="assets/buttons/import_empleados-button.png"):
        return self.file_invoker.get_open_button(text, icon_path)

    def _on_file_selected(self, path: str):
        if not path:
            print("⚠️ No se seleccionó ningún archivo.")
            return

        df = self._cargar_excel(path)
        if df is not None:
            print(f"🧪 Columnas detectadas: {list(df.columns)}")
            empleados = self._procesar_empleados(df)
            if empleados:
                print(f"\n🔎 Total de empleados a procesar: {len(empleados)}")
                self._insertar_empleados(empleados)

                if self.on_success:
                    self.on_success(path)

                self.page.snack_bar = ft.SnackBar(
                    ft.Text("✅ Empleados importados correctamente."),
                    bgcolor=ft.colors.GREEN
                )
                self.page.snack_bar.open = True
                self.page.update()

    def _cargar_excel(self, path: str) -> pd.DataFrame | None:
        motores = ["openpyxl", "xlrd", "pyxlsb"]
        for motor in motores:
            try:
                df = pd.read_excel(path, engine=motor, header=0)
                print(f"📥 Archivo cargado con motor '{motor}'")
                return df
            except Exception as e:
                print(f"❌ Error con motor {motor}: {e}")
        return None

    def _procesar_empleados(self, df: pd.DataFrame) -> list:
        try:
            df = df.iloc[1:].reset_index(drop=True)
            columnas = ['No', 'NSS', 'Nombre(s)', 'Apellido Paterno', 'Apellido Materno',
                        'CURP', 'SD 2024', 'SDI 2024', 'SD 2025', 'SDI 2025', 'Puesto', 'RFC', 'Estado']
            df.columns = columnas
            df['No'] = pd.to_numeric(df['No'], errors='coerce').fillna(0).astype(int)
            df['Estado'] = df['Estado'].str.strip().replace({'Activo ': 'Activo', 'Inactivo ': 'Inactivo'})
            df['nombre_completo'] = df['Nombre(s)'] + ' ' + df['Apellido Paterno'] + ' ' + df['Apellido Materno']
            df['sueldo_diario'] = df.apply(lambda row: 0 if row['Estado'] == 'Inactivo' else row['SD 2024'], axis=1)
            df['tipo_trabajador'] = 'no definido'

            empleados = []
            for _, row in df.iterrows():
                empleados.append({
                    "numero_nomina": row['No'],
                    "nombre_completo": row['nombre_completo'],
                    "estado": row['Estado'],
                    "sueldo_diario": row['sueldo_diario'],
                    "tipo_trabajador": row['tipo_trabajador']
                })
            return empleados
        except Exception as e:
            print(f"❌ Error procesando empleados: {e}")
            return []

    def _insertar_empleados(self, empleados: list):
        for emp in empleados:
            try:
                query = """
                    INSERT INTO empleados (numero_nomina, nombre_completo, estado, tipo_trabajador, sueldo_diario)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        nombre_completo=VALUES(nombre_completo),
                        estado=VALUES(estado),
                        tipo_trabajador=VALUES(tipo_trabajador),
                        sueldo_diario=VALUES(sueldo_diario);
                """
                valores = (
                    emp["numero_nomina"],
                    emp["nombre_completo"],
                    emp["estado"],
                    emp["tipo_trabajador"],
                    emp["sueldo_diario"]
                )
                self.db.run_query(query, valores)
                print(f"✅ Empleado registrado: {valores}")
            except Exception as e:
                print(f"❌ Error insertando empleado {emp.get('numero_nomina')}: {e}")