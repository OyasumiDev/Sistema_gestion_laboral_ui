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
            columnas = list(df.columns)

            if columnas == ["numero_nomina", "nombre_completo", "sueldo_diario"]:
                df = df.rename(columns={"sueldo_diario": "sueldo_por_hora"})
                empleados = df.to_dict(orient="records")
            else:
                raise ValueError("❌ Formato de columnas no válido. Se esperaban: numero_nomina, nombre_completo, sueldo_diario")

            return empleados

        except Exception as e:
            print(f"❌ Error procesando empleados: {e}")
            return []

    def _insertar_empleados(self, empleados: list):
        for emp in empleados:
            try:
                numero = emp.get("numero_nomina")

                if not numero or not isinstance(numero, int):
                    print(f"⚠️ Número de nómina inválido (omitido): {numero}")
                    continue

                if self._existe_empleado(numero):
                    print(f"⚠️ Empleado con número de nómina {numero} ya existe. No se reemplaza.")
                    continue

                nombre = emp.get("nombre_completo", f"Empleado {numero}").strip()
                sueldo = emp.get("sueldo_por_hora", 0.00)

                query = """
                    INSERT INTO empleados (numero_nomina, nombre_completo, sueldo_por_hora)
                    VALUES (%s, %s, %s)
                """
                valores = (numero, nombre, sueldo)
                self.db.run_query(query, valores)
                print(f"✅ Empleado registrado: {valores}")

            except Exception as e:
                print(f"❌ Error insertando empleado {emp.get('numero_nomina')}: {e}")

    def _existe_empleado(self, numero_nomina: int) -> bool:
        query = "SELECT 1 FROM empleados WHERE numero_nomina = %s LIMIT 1"
        try:
            resultado = self.db.get_data(query, (numero_nomina,), dictionary=True)
            return bool(resultado)
        except Exception as e:
            print(f"⚠️ Error verificando existencia del empleado {numero_nomina}: {e}")
            return False
