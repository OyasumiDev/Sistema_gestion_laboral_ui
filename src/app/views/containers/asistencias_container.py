import flet as ft
import pandas as pd
from datetime import datetime, timedelta, date
import functools
from app.models.assistance_model import AssistanceModel
from app.core.enums.e_assistance_model import E_ASSISTANCE
from app.controllers.asistencias_import_controller import AsistenciasImportController
from app.core.app_state import AppState
from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.views.containers.theme_controller import ThemeController
from app.views.containers.modal_alert import ModalAlert
from app.views.containers.window_snackbar import WindowSnackbar
from tabulate import tabulate
from app.utils.table_action_buttons import crear_boton_editar, crear_boton_eliminar


class AsistenciasContainer(ft.Container):
    def __init__(self):
        super().__init__(
            expand=True,
            padding=20,
            alignment=ft.alignment.top_center
        )

        self.page = AppState().page
        self.asistencia_model = AssistanceModel()
        self.theme_ctrl = ThemeController()

        self.sort_key = "numero_nomina"
        self.sort_asc = True

        # NUEVAS estructuras
        self.editando = {}  # Clave: (numero_nomina, fecha)
        self.datos_por_periodo = {}  # Agrupaciones por periodos de fechas
        self.periodos_expandido = {}  # Controla expansión de cada periodo

        self.import_controller = AsistenciasImportController(
            page=self.page,
            on_success=self._actualizar_tabla  # Este método debe llamarse igual que el nuevo `actualizar_tabla`
        )

        self.save_invoker = FileSaveInvoker(
            page=self.page,
            on_save=self._exportar_asistencias,
            save_dialog_title="Exportar asistencias como Excel",
            file_name="asistencias_exportadas.xlsx",
            allowed_extensions=["xlsx"]
        )

        self.window_snackbar = WindowSnackbar(self.page)

        # TABLA con columnas personalizadas y sin filas iniciales
        self.table = ft.DataTable(
            columns=self.crear_columnas(),
            rows=[]
        )

        self.scroll_column = ft.Column(
            controls=[self.table],
            scroll=ft.ScrollMode.ALWAYS,
            expand=True,
            alignment=ft.MainAxisAlignment.START
        )

        self.import_button = self._build_action_button(
            label="Importar",
            icon_path="assets/buttons/import-button.png",
            on_tap=lambda _: self.import_controller.file_invoker.open()
        )

        self.export_button = self._build_action_button(
            label="Exportar",
            icon_path="assets/buttons/export-button.png",
            on_tap=lambda _: self.save_invoker.open_save()
        )

        self.new_column_button = self._build_action_button(
            label="Agregar Columna",
            icon=ft.icons.PERSON_ADD_ALT_1_OUTLINED,
            on_tap=self._insertar_asistencia_desde_columna
        )

        self.content = self._build_content()
        self._actualizar_tabla()
        self.page.update()


    def _build_content(self):
        contenido = ft.Container(
            expand=True,
            content=ft.Column(
                scroll=ft.ScrollMode.ALWAYS,
                alignment=ft.MainAxisAlignment.START,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20,
                controls=[
                    ft.Text("Registro de Asistencias", size=24, weight="bold", text_align=ft.TextAlign.CENTER),
                    ft.Container(
                        alignment=ft.alignment.center_left,
                        padding=ft.padding.only(left=60),
                        content=ft.Row(
                            spacing=10,
                            alignment=ft.MainAxisAlignment.START,
                            controls=[self.import_button, self.export_button, self.new_column_button]
                        )
                    ),
                    ft.Container(
                        alignment=ft.alignment.center,
                        padding=ft.padding.symmetric(horizontal=20),
                        content=ft.Container(
                            content=self.scroll_column,
                            alignment=ft.alignment.center,
                            margin=ft.margin.symmetric(horizontal="auto"),
                        )
                    )
                ]
            )
        )

        # ⚠️ Asegúrate que la tabla ya esté agregada al layout antes de actualizar
        self.page.add(self)
        self._actualizar_tabla()
        return contenido

    def _icono_orden(self, columna):
        if self.sort_key == columna:
            return "▲" if self.sort_asc else "▼"
        return "⇅"


    def _sort_by(self, key):
        if self.sort_key == key:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_key = key
            self.sort_asc = True
        self._actualizar_tabla()


    def _actualizar_tabla(self):
        resultado = self.asistencia_model.get_all()
        if resultado["status"] != "success":
            self.window_snackbar.show_error("❌ No se pudieron cargar asistencias.")
            return

        datos = resultado["data"]
        self.datos_por_periodo = self._agrupar_por_periodo(datos)

        self.table.rows.clear()
        for periodo, registros in self.datos_por_periodo.items():
            expandido = self.periodos_expandido.get(periodo, True)
            self.table.rows.append(
                ft.DataRow(
                    cells=[ft.DataCell(ft.Text(f"📆 {periodo}"))],
                    selected=expandido,
                    on_select_changed=lambda e, p=periodo: self.toggle_periodo(p),
                    color=ft.colors.SURFACE_VARIANT,
                )
            )
            if expandido:
                for reg in registros:
                    self.table.rows.append(self._crear_fila(reg))

        self.table.update()
        self.page.update()


    def _agrupar_por_periodo(self, datos: list) -> dict:
        agrupado = {}

        for reg in datos:
            fecha = reg.get("fecha")
            if not fecha:
                continue

            if isinstance(fecha, str):
                try:
                    if "/" in fecha:
                        fecha = datetime.strptime(fecha, "%d/%m/%Y").date()
                    else:
                        fecha = datetime.strptime(fecha, "%Y-%m-%d").date()
                except Exception as e:
                    print(f"❌ Error parseando fecha: {fecha} -> {e}")
                    continue
            elif isinstance(fecha, datetime):
                fecha = fecha.date()

            inicio_semana = fecha - timedelta(days=fecha.weekday())
            fin_semana = inicio_semana + timedelta(days=6)
            periodo_str = f"{inicio_semana.strftime('%d/%m/%Y')} - {fin_semana.strftime('%d/%m/%Y')}"

            if periodo_str not in agrupado:
                agrupado[periodo_str] = []

            agrupado[periodo_str].append(reg)

        return agrupado


    def crear_columnas(self):
        return [
            ft.DataColumn(ft.Text("Nómina")),
            ft.DataColumn(ft.Text("Nombre")),
            ft.DataColumn(ft.Text("Fecha")),
            ft.DataColumn(ft.Text("Hora Entrada")),
            ft.DataColumn(ft.Text("Hora Salida")),
            ft.DataColumn(ft.Text("Descanso")),
            ft.DataColumn(ft.Text("Horas Trabajadas")),
            ft.DataColumn(ft.Text("Estado")),
            ft.DataColumn(ft.Text("Acciones")),
        ]

    def activar_edicion(self, numero_nomina, fecha):
        self.editando.clear()  # Solo una fila editable a la vez
        self.editando[(numero_nomina, fecha)] = True
        self._actualizar_tabla()

    def _descanso_a_minutos(self, tipo):
        if tipo == "MD":
            return 30
        elif tipo == "CMP":
            return 60
        return 0



    def _crear_fila(self, registro):
        numero_nomina = registro["numero_nomina"]
        fecha = registro["fecha"]
        editable = self.editando.get((numero_nomina, fecha), False)

        def actualizar_horas(_):
            entrada = self._parse_time(campo_entrada.value)
            salida = self._parse_time(campo_salida.value)
            descanso = self._descanso_a_minutos()
            if entrada and salida:
                total = (datetime.combine(date.min, salida) - datetime.combine(date.min, entrada)).total_seconds() / 3600
                total -= descanso / 60
                campo_horas.value = f"{total:.2f}"
                self.update()

        def seleccionar_descanso(tipo):
            for clave, boton in botones_descanso.items():
                boton.style = ft.ButtonStyle(shape=ft.BoxShape.RECTANGLE, bgcolor=ft.colors.SURFACE_VARIANT if clave == tipo else ft.colors.TRANSPARENT)
            campo_descanso.value = tipo
            actualizar_horas()

        campo_entrada = ft.TextField(
            value=registro.get("hora_entrada", ""),
            on_change=actualizar_horas,
            read_only=not editable,
            width=100,
        )
        campo_salida = ft.TextField(
            value=registro.get("hora_salida", ""),
            on_change=actualizar_horas,
            read_only=not editable,
            width=100,
        )

        campo_descanso = ft.TextField(value=registro.get("descanso", ""), visible=False)

        botones_descanso = {
            "SN": ft.OutlinedButton("SN", on_click=lambda _: seleccionar_descanso("SN")),
            "MD": ft.OutlinedButton("MD", on_click=lambda _: seleccionar_descanso("MD")),
            "CMP": ft.OutlinedButton("CMP", on_click=lambda _: seleccionar_descanso("CMP")),
        }

        descanso_widget = ft.Row([*botones_descanso.values()], spacing=5)

        campo_horas = ft.TextField(
            value=str(registro.get("tiempo_trabajo", "0.00")),
            read_only=True,
            width=80,
        )

        acciones = crear_boton_editar(lambda: self.activar_edicion(numero_nomina, fecha))

        return ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(str(numero_nomina))),
                ft.DataCell(ft.Text(registro.get("nombre_completo", ""))),
                ft.DataCell(ft.Text(str(fecha))),
                ft.DataCell(campo_entrada),
                ft.DataCell(campo_salida),
                ft.DataCell(descanso_widget),
                ft.DataCell(campo_horas),
                ft.DataCell(ft.Text(registro.get("estado", ""))),
                ft.DataCell(acciones),
            ]
        )


    def toggle_periodo(self, periodo):
        self.periodos_expandido[periodo] = not self.periodos_expandido.get(periodo, True)
        self.actualizar_tabla()

    def _parse_time(self, value: str):
        try:
            return datetime.strptime(value, "%H:%M").time()
        except Exception:
            return None


    def _confirmar_eliminacion(self, numero, fecha, e=None):
        ModalAlert(
            title_text="¿Eliminar asistencia?",
            message=f"¿Deseas eliminar el registro del empleado {numero} el día {fecha}?",
            on_confirm=lambda: self._eliminar_asistencia(numero, fecha),
            on_cancel=self._actualizar_tabla
        ).mostrar()

    def _eliminar_asistencia(self, numero, fecha):
        try:
            resultado = self.asistencia_model.delete_by_numero_nomina_and_fecha(numero, fecha)
            if resultado["status"] == "success":
                self.window_snackbar.show_success("✅ Asistencia eliminada correctamente.")
            else:
                self.window_snackbar.show_error("❌ " + resultado["message"])
        except Exception as e:
            self.window_snackbar.show_error("⚠️ " + str(e))

        self._actualizar_tabla()


    def _build_action_button(self, label, icon_path=None, icon=None, on_tap=None):
        content = ft.Row(spacing=5, alignment=ft.MainAxisAlignment.CENTER)
        if icon_path:
            content.controls.append(ft.Image(src=icon_path, width=20, height=20))
        elif icon:
            content.controls.append(ft.Icon(name=icon, size=20))
        content.controls.append(ft.Text(label, size=11, weight="bold"))

        return ft.GestureDetector(
            on_tap=on_tap,
            content=ft.Container(
                padding=8,
                border_radius=12,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=content
            )
        )


    def _exportar_asistencias(self, path: str):
        try:
            resultado = self.asistencia_model.get_all()
            if resultado["status"] != "success":
                print("❌ Error al obtener asistencias:", resultado["message"])
                return

            datos = resultado["data"]

            columnas = [
                ("numero_nomina", "ID Checador"),
                ("nombre", "Nombre"),
                ("fecha", "Fecha"),
                ("hora_entrada", "Entrada"),
                ("hora_salida", "Salida"),
                ("retardo", "Retardo"),
                ("estado", "Estado"),
                ("tiempo_trabajo", "Tiempo de trabajo")
            ]

            encabezado = [
                ["CONTROL de Mexico"],
                ["Entradas y Salidas"],
                [f"Periodo: {datos[0]['fecha']} al {datos[-1]['fecha']}"] if datos else [""],
                ["Sucursales: Sucursal Matriz,Soriana,Mattel"],
                []
            ]

            cuerpo = []
            for reg in datos:
                fila = []
                for clave, _ in columnas:
                    valor = reg.get(clave)
                    if isinstance(valor, (datetime, pd.Timestamp)):
                        fila.append(valor.strftime("%H:%M:%S"))
                    elif isinstance(valor, str) and ":" in valor:
                        fila.append(valor)
                    elif valor in [None, ""]:
                        fila.append("00:00:00" if "hora" in clave or "tiempo" in clave or clave in ["retardo"] else "")
                    else:
                        fila.append(str(valor))
                cuerpo.append(fila)

            df = pd.DataFrame(cuerpo, columns=[n for _, n in columnas])
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                df.to_excel(writer, startrow=5, index=False, sheet_name="Asistencias")
                for idx, fila in enumerate(encabezado, 1):
                    for col_idx, val in enumerate(fila, 1):
                        writer.sheets["Asistencias"].cell(row=idx, column=col_idx, value=val)

            print(f"✅ Asistencias exportadas a: {path}")
        except Exception as e:
            print(f"❌ Error al exportar: {e}")


    def depurar_asistencias(self):
        resultado = self.asistencia_model.get_all()
        if resultado["status"] != "success":
            print("❌ Error al obtener asistencias:", resultado["message"])
            return

        datos = resultado["data"]
        if not datos:
            print("⚠️ No hay asistencias registradas.")
            return

        columnas = [e.value for e in E_ASSISTANCE]
        tabla = [[registro.get(col) for col in columnas] for registro in datos]
        print("\n📋 Asistencias registradas en la base de datos:")
        print(tabulate(tabla, headers=columnas, tablefmt="grid"))

    def _insertar_asistencia_desde_columna(self, _):
        numero_input = ft.TextField(hint_text="ID Empleado", width=120, keyboard_type=ft.KeyboardType.NUMBER)
        fecha_input = ft.TextField(hint_text="Fecha (DD/MM/YYYY)", width=160)
        entrada_input = ft.TextField(hint_text="Entrada (HH:MM:SS)", width=140)
        salida_input = ft.TextField(hint_text="Salida (HH:MM:SS)", width=140)

        def validar_en_tiempo_real(_=None):
            numero_input.border_color = None
            fecha_input.border_color = None
            entrada_input.border_color = None
            salida_input.border_color = None

            h_ent = h_sal = None

            try:
                numero = int(numero_input.value.strip())
                if numero <= 0:
                    raise ValueError
            except:
                numero_input.border_color = ft.colors.RED

            try:
                fecha_sql = datetime.strptime(fecha_input.value.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
                if self.asistencia_model.get_by_empleado_fecha(numero, fecha_sql):
                    fecha_input.border_color = ft.colors.RED
            except:
                fecha_input.border_color = ft.colors.RED

            try:
                h_ent = datetime.strptime(entrada_input.value.strip(), "%H:%M:%S")
            except:
                entrada_input.border_color = ft.colors.RED

            try:
                h_sal = datetime.strptime(salida_input.value.strip(), "%H:%M:%S")
            except:
                salida_input.border_color = ft.colors.RED

            if h_ent and h_sal and h_sal <= h_ent:
                salida_input.border_color = ft.colors.RED

            self.page.update()

        numero_input.on_change = validar_en_tiempo_real
        fecha_input.on_change = validar_en_tiempo_real
        entrada_input.on_change = validar_en_tiempo_real
        salida_input.on_change = validar_en_tiempo_real

        def on_guardar(_):
            errores = []
            numero_input.border_color = None
            fecha_input.border_color = None
            entrada_input.border_color = None
            salida_input.border_color = None

            numero_str = str(numero_input.value).strip()
            fecha_str = str(fecha_input.value).strip()
            entrada_str = str(entrada_input.value).strip()
            salida_str = str(salida_input.value).strip()

            try:
                numero = int(numero_str)
                if numero <= 0:
                    raise ValueError
            except:
                errores.append("🟥 El ID de empleado debe ser un número entero positivo.")
                numero_input.border_color = ft.colors.RED

            try:
                fecha_sql = datetime.strptime(fecha_str, "%d/%m/%Y").strftime("%Y-%m-%d")
            except:
                errores.append("🟥 Fecha inválida. Usa el formato DD/MM/YYYY.")
                fecha_input.border_color = ft.colors.RED

            if not errores and self.asistencia_model.get_by_empleado_fecha(numero, fecha_sql):
                errores.append("🟥 Ya existe una asistencia para este empleado en esa fecha.")
                fecha_input.border_color = ft.colors.RED

            try:
                h_ent = datetime.strptime(entrada_str, "%H:%M:%S")
            except:
                errores.append("🟥 La hora de entrada debe tener el formato HH:MM:SS.")
                entrada_input.border_color = ft.colors.RED

            try:
                h_sal = datetime.strptime(salida_str, "%H:%M:%S")
            except:
                errores.append("🟥 La hora de salida debe tener el formato HH:MM:SS.")
                salida_input.border_color = ft.colors.RED

            if "h_ent" in locals() and "h_sal" in locals():
                if h_sal <= h_ent:
                    errores.append("🟥 La hora de salida debe ser mayor que la de entrada.")
                    salida_input.border_color = ft.colors.RED

            self.page.update()

            if errores:
                ModalAlert.mostrar_info("Errores encontrados", "\n".join(errores))
                return

            resultado = self.asistencia_model.add_manual_assistance(
                numero_nomina=numero,
                fecha=fecha_sql,
                hora_entrada=entrada_str,
                hora_salida=salida_str
            )

            if resultado["status"] == "success":
                self.window_snackbar.show_success("✅ Asistencia registrada correctamente.")
                self.depurar_asistencias()
            else:
                ModalAlert.mostrar_info("Error", "❌ " + resultado["message"])

            self._actualizar_tabla()

        fila = ft.DataRow(cells=[
            ft.DataCell(numero_input),
            ft.DataCell(ft.Text("-")),
            ft.DataCell(fecha_input),
            ft.DataCell(entrada_input),
            ft.DataCell(salida_input),
            ft.DataCell(ft.Text("00:00:00")),
            ft.DataCell(ft.Text("completo")),
            ft.DataCell(ft.Text("00:00:00")),
            ft.DataCell(ft.Row([
                ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, on_click=on_guardar),
                ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600, on_click=self._actualizar_tabla)
            ]))
        ])

        if self.table:
            self.table.rows.append(fila)
            self.table.update()
        self.page.update()



