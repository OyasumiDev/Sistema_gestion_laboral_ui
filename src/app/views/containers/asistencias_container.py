import flet as ft
from datetime import datetime, timedelta, date
import pandas as pd

from app.models.assistance_model import AssistanceModel
from app.controllers.asistencias_import_controller import AsistenciasImportController
from app.core.app_state import AppState
from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.views.containers.theme_controller import ThemeController
from app.views.containers.window_snackbar import WindowSnackbar
from app.views.containers.modal_alert import ModalAlert

from app.helpers.sort_helpers import SortHelper
from app.helpers.table_column_builder import TableColumnBuilder
from app.utils.table_action_buttons import crear_boton_editar


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
        self.sort_helper = SortHelper(default_key="numero_nomina")

        self.editando = {}
        self.datos_por_grupo = {}
        self.grupos_expandido = {}

        self.columnas_definidas = [
            ("Nómina", "numero_nomina"),
            ("Nombre", "nombre_completo"),
            ("Fecha", "fecha"),
            ("Hora Entrada", "hora_entrada"),
            ("Hora Salida", "hora_salida"),
            ("Descanso", "descanso"),
            ("Horas Trabajadas", "tiempo_trabajo"),
            ("Estado", "estado"),
        ]

        self.column_builder = TableColumnBuilder(
            sort_helper=self.sort_helper,
            on_edit=self.activar_edicion,
            on_delete=lambda reg: self._confirmar_eliminacion(reg["numero_nomina"], reg["fecha"])
        )

        self.import_controller = AsistenciasImportController(
            page=self.page,
            on_success=self._actualizar_tabla
        )

        self.save_invoker = FileSaveInvoker(
            page=self.page,
            on_save=self._exportar_asistencias,
            save_dialog_title="Exportar asistencias como Excel",
            file_name="asistencias_exportadas.xlsx",
            allowed_extensions=["xlsx"]
        )

        self.window_snackbar = WindowSnackbar(self.page)

        self.scroll_column = ft.Column(
            controls=[],
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

        self.new_column_button = None

        self.content = self._build_content()

        # ✅ Carga inmediata de asistencias al crear el contenedor
        self._actualizar_tabla()


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
                            controls=[self.import_button, self.export_button]
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
        self.page.add(self)
        return contenido

    def crear_columnas(self):
        return self.column_builder.build_columns(self.columnas_definidas)


    def _agrupar_por_grupo_importacion(self, datos: list) -> dict:
        agrupado = {}
        for reg in datos:
            grupo_fecha = reg.get("grupo_importacion")
            if not grupo_fecha:
                fecha_registro = reg.get("fecha")
                if isinstance(fecha_registro, str):
                    try:
                        fecha_registro = datetime.strptime(fecha_registro, "%Y-%m-%d").date()
                    except:
                        fecha_registro = date.today()
                grupo_fecha = f"GRUPO:{fecha_registro.strftime('%d/%m/%Y')}"
                reg["grupo_importacion"] = grupo_fecha  # solo si no existe

            if grupo_fecha not in agrupado:
                agrupado[grupo_fecha] = []
            agrupado[grupo_fecha].append(reg)
        return agrupado


    def _extraer_fecha_primer_registro(self, registros: list):
        try:
            primer_registro = registros[0]
            fecha_str = primer_registro.get("fecha", "")
            return datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except:
            return date.min


    def _actualizar_tabla(self):
        resultado = self.asistencia_model.get_all()
        if resultado["status"] != "success":
            self.window_snackbar.show_error("❌ No se pudieron cargar asistencias.")
            return

        datos = resultado["data"]
        self.datos_por_grupo = self._agrupar_por_grupo_importacion(datos)
        self.scroll_column.controls.clear()

        paneles = []

        # Ordenar por la fecha del primer registro de cada grupo, más recientes primero
        grupos_ordenados = sorted(
            self.datos_por_grupo.items(),
            key=lambda item: self._extraer_fecha_primer_registro(item[1]),
            reverse=True
        )

        # Mantener solo un grupo abierto
        self.grupos_expandido = {grupo: False for grupo, _ in grupos_ordenados}
        if grupos_ordenados:
            self.grupos_expandido[grupos_ordenados[0][0]] = True

        for grupo, registros in grupos_ordenados:
            expandido = self.grupos_expandido.get(grupo, False)

            tabla = ft.DataTable(
                columns=self.crear_columnas(),
                rows=[self._crear_fila(reg) for reg in registros]
            )

            encabezado = ft.Row([
                ft.Text(f"🗂 {grupo}", expand=True),
                ft.IconButton(
                    icon=ft.icons.ADD,
                    tooltip="Agregar asistencia",
                    on_click=lambda e, g=grupo: self._abrir_modal_agregar(g)
                )
            ])

            panel = ft.ExpansionPanel(
                header=encabezado,
                content=tabla,
                can_tap_header=True,
                expanded=expandido
            )

            def crear_toggle(grupo_local):
                return lambda e: self._toggle_expansion(grupo_local)

            panel.on_expansion_changed = crear_toggle(grupo)
            paneles.append(panel)

        self.scroll_column.controls.append(
            ft.ExpansionPanelList(
                expand=True,
                controls=paneles
            )
        )

        self.page.update()




    def _toggle_expansion(self, grupo):
        # ✅ Solo este grupo se expande, los demás se cierran
        self.grupos_expandido = {k: False for k in self.datos_por_grupo.keys()}
        self.grupos_expandido[grupo] = True
        self._actualizar_tabla()


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

    def _abrir_modal_agregar(self, grupo_importacion):
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

            numero_str = numero_input.value.strip()
            fecha_str = fecha_input.value.strip()
            entrada_str = entrada_input.value.strip()
            salida_str = salida_input.value.strip()

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
                hora_salida=salida_str,
                grupo_importacion=grupo_importacion  # 👈 clave para el requerimiento
            )

            if resultado["status"] == "success":
                self.window_snackbar.show_success("✅ Asistencia registrada correctamente.")
                self._actualizar_tabla()
            else:
                ModalAlert.mostrar_info("Error", "❌ " + resultado["message"])

        fila = ft.Row([
            numero_input,
            fecha_input,
            entrada_input,
            salida_input,
            ft.IconButton(icon=ft.icons.CHECK, icon_color=ft.colors.GREEN_600, on_click=on_guardar),
            ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.RED_600, on_click=lambda _: self._actualizar_tabla())
        ])

        self.page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Agregar asistencia a grupo: {grupo_importacion}"),
            content=fila,
            actions=[],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.page.dialog.open = True
        self.page.update()



    def _exportar_asistencias(self, ruta_guardado: str):
        try:
            resultado = self.asistencia_model.get_all()
            if resultado["status"] != "success":
                self.window_snackbar.show_error("❌ No se pudieron obtener los datos para exportar.")
                return

            df = pd.DataFrame(resultado["data"])
            df.to_excel(ruta_guardado, index=False)
            self.window_snackbar.show_success("✅ Asistencias exportadas correctamente.")

        except Exception as e:
            self.window_snackbar.show_error(f"❌ Error al exportar asistencias: {str(e)}")
