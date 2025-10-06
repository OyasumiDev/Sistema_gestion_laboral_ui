import flet as ft
import pandas as pd
from app.core.invokers.file_open_invoker import FileOpenInvoker
from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.core.interfaces.database_mysql import DatabaseMysql


class EmpleadosImportController:
    def __init__(self, page: ft.Page, on_success: callable = None, on_export: callable = None):
        self.page = page
        self.db = DatabaseMysql()
        self.on_success = on_success
        self.on_export = on_export

        # ---- Importador
        self.file_invoker = FileOpenInvoker(
            page=self.page,
            on_select=self._on_file_selected,
            dialog_title="Selecciona archivo de empleados",
            allowed_extensions=["xlsx", "xls", "xlsb"]
        )

        # ---- Exportador
        self.save_invoker = FileSaveInvoker(
            page=self.page,
            on_save=self._on_file_export,
            save_dialog_title="Exportar empleados",
            file_name="empleados.xlsx",
            allowed_extensions=["xlsx"]
        )

    # -----------------------------
    # BOTONES
    # -----------------------------
    def get_import_button(self, text="Importar", icon=ft.icons.FILE_DOWNLOAD_OUTLINED):
        return ft.GestureDetector(
            on_tap=lambda e: self.file_invoker.open(),
            content=ft.Container(
                padding=10,
                border_radius=20,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=ft.Row(
                    [
                        ft.Icon(name=icon, size=18),
                        ft.Text(text, size=12, weight="bold"),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=6,
                ),
            ),
        )

    def get_export_button(self, text="Exportar", icon=ft.icons.FILE_UPLOAD_OUTLINED):
        return ft.GestureDetector(
            on_tap=lambda e: self.save_invoker.open_save(),
            content=ft.Container(
                padding=10,
                border_radius=20,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=ft.Row(
                    [
                        ft.Icon(name=icon, size=18),
                        ft.Text(text, size=12, weight="bold"),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=6,
                ),
            ),
        )

    # -----------------------------
    # IMPORTACIÓN
    # -----------------------------
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
            elif set(["numero_nomina", "nombre_completo", "sueldo_por_hora"]).issubset(columnas):
                empleados = df.to_dict(orient="records")
            else:
                raise ValueError("❌ Formato de columnas no válido. Se esperaban: numero_nomina, nombre_completo, sueldo_diario/sueldo_por_hora")

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

    # -----------------------------
    # EXPORTACIÓN
    # -----------------------------
    def _on_file_export(self, ruta: str):
        try:
            query = "SELECT numero_nomina, nombre_completo, sueldo_por_hora FROM empleados"
            empleados = self.db.get_data_list(query, dictionary=True)

            if not empleados:
                self.page.snack_bar = ft.SnackBar(
                    ft.Text("⚠️ No hay empleados para exportar."),
                    bgcolor=ft.colors.ORANGE
                )
                self.page.snack_bar.open = True
                self.page.update()
                return

            df = pd.DataFrame(empleados)
            df.to_excel(ruta, index=False)

            if self.on_export:
                self.on_export(ruta)

            self.page.snack_bar = ft.SnackBar(
                ft.Text(f"✅ Empleados exportados correctamente en {ruta}"),
                bgcolor=ft.colors.GREEN
            )
            self.page.snack_bar.open = True
            self.page.update()

        except Exception as e:
            self.page.snack_bar = ft.SnackBar(
                ft.Text(f"❌ Error exportando empleados: {e}"),
                bgcolor=ft.colors.RED
            )
            self.page.snack_bar.open = True
            self.page.update()
