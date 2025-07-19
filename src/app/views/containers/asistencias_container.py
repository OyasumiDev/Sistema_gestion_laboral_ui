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
from app.core.invokers.safe_scroll_invoker import SafeScrollInvoker


class AsistenciasContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20, alignment=ft.alignment.top_center)
        self.page = AppState().page
        self.asistencia_model = AssistanceModel()
        self.theme_ctrl = ThemeController()
        self.sort_helper = SortHelper(default_key="numero_nomina")
        self.editando = {}
        self.datos_por_grupo = {}
        self.grupos_expandido = {}
        self.safe_scroll = SafeScrollInvoker

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


    def _on_click_editar(self, numero_nomina, fecha):
        self.activar_edicion(numero_nomina, fecha)
        self._redibujar_tabla_sin_consultar_db()



    def crear_columnas(self):
        return self.column_builder.build_columns(self.columnas_definidas)


    def _agregar_fila_en_grupo(self, grupo_importacion):
        self.editando[("nuevo", grupo_importacion)] = {
            "numero_nomina": "",
            "fecha": "",
            "hora_entrada": "",
            "hora_salida": ""
        }
        self.grupos_expandido = {k: False for k in self.datos_por_grupo.keys()}
        self.grupos_expandido[grupo_importacion] = True
        self._actualizar_tabla()

        if self.page:
            self.safe_scroll.scroll_to_bottom(self.page)



    def _actualizar_tabla(self):
        resultado = self.asistencia_model.get_all()
        if resultado["status"] != "success":
            self.window_snackbar.show_error("❌ No se pudieron cargar asistencias.")
            return

        datos = resultado["data"]
        self.datos_por_grupo = self._agrupar_por_grupo_importacion(datos)
        self.scroll_column.controls.clear()

        paneles = []

        grupos_ordenados = sorted(
            self.datos_por_grupo.items(),
            key=lambda item: self._extraer_fecha_primer_registro(item[1]),
            reverse=True
        )

        if not self.grupos_expandido:
            self.grupos_expandido = {grupo: False for grupo, _ in grupos_ordenados}
            if grupos_ordenados:
                self.grupos_expandido[grupos_ordenados[0][0]] = True

        for grupo, registros in grupos_ordenados:
            expandido = self.grupos_expandido.get(grupo, False)

            filas = [self._crear_fila(reg) for reg in registros]

            if ("nuevo", grupo) in self.editando:
                filas.append(self._crear_fila_nueva(grupo))

            tabla = ft.DataTable(
                columns=self.crear_columnas(),
                rows=filas
            )

            encabezado = ft.Row([
                ft.Text(f"🗂 {grupo}", expand=True),
                ft.IconButton(
                    icon=ft.icons.ADD,
                    tooltip="Agregar asistencia",
                    on_click=lambda e, g=grupo: self._agregar_fila_en_grupo(g)
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

        if self.page:
            self.page.update()



    def _crear_fila_nueva(self, grupo_importacion):
        registro = self.editando.get(("nuevo", grupo_importacion), {
            "numero_nomina": "",
            "nombre_completo": "",
            "fecha": "",
            "hora_entrada": "",
            "hora_salida": "",
            "descanso": "SN",
            "tiempo_trabajo": "0.00",
            "estado": "PENDIENTE"
        })

        campo_nomina = ft.TextField(
            value=registro.get("numero_nomina", ""),
            width=100,
            on_change=lambda e: self._actualizar_valor_fila_nueva(grupo_importacion, "numero_nomina", e.control.value)
        )

        campo_fecha = ft.TextField(
            value=registro.get("fecha", ""),
            width=100,
            on_change=lambda e: self._actualizar_valor_fila_nueva(grupo_importacion, "fecha", e.control.value)
        )

        campo_entrada = ft.TextField(
            value=registro.get("hora_entrada", ""),
            width=100,
            on_change=lambda e: self._actualizar_valor_fila_nueva(grupo_importacion, "hora_entrada", e.control.value)
        )

        campo_salida = ft.TextField(
            value=registro.get("hora_salida", ""),
            width=100,
            on_change=lambda e: self._actualizar_valor_fila_nueva(grupo_importacion, "hora_salida", e.control.value)
        )

        botones_descanso = {
            "SN": ft.FilledButton("SN", on_click=lambda e, t="SN": self._actualizar_valor_fila_nueva(grupo_importacion, "descanso", t)),
            "MD": ft.FilledButton("MD", on_click=lambda e, t="MD": self._actualizar_valor_fila_nueva(grupo_importacion, "descanso", t)),
            "CMP": ft.FilledButton("CMP", on_click=lambda e, t="CMP": self._actualizar_valor_fila_nueva(grupo_importacion, "descanso", t)),
        }

        descanso_widget = ft.Row([*botones_descanso.values()], spacing=5)

        campo_horas = ft.TextField(
            value=registro.get("tiempo_trabajo", "0.00"),
            width=80,
            read_only=True
        )

        acciones = ft.Row([
            ft.IconButton(
                icon=ft.icons.SAVE,
                tooltip="Guardar",
                on_click=lambda e: self._guardar_fila_nueva(grupo_importacion)
            ),
            ft.IconButton(
                icon=ft.icons.CANCEL,
                tooltip="Cancelar",
                on_click=lambda e: self._cancelar_fila_nueva(grupo_importacion)
            )
        ])

        return ft.DataRow(
            cells=[
                ft.DataCell(campo_nomina),
                ft.DataCell(ft.Text("-")),
                ft.DataCell(campo_fecha),
                ft.DataCell(campo_entrada),
                ft.DataCell(campo_salida),
                ft.DataCell(descanso_widget),
                ft.DataCell(campo_horas),
                ft.DataCell(ft.Text("PENDIENTE")),
                ft.DataCell(acciones),
            ]
        )



    def _actualizar_valor_fila_nueva(self, grupo_importacion, campo, valor):
        if ("nuevo", grupo_importacion) not in self.editando:
            self.editando[("nuevo", grupo_importacion)] = {}

        self.editando[("nuevo", grupo_importacion)][campo] = valor

        # Si es hora_entrada, hora_salida o descanso, recalcular las horas trabajadas
        if campo in ("hora_entrada", "hora_salida", "descanso"):
            self._recalcular_horas_trabajadas(grupo_importacion)
        if self.page:
            self.page.update()


    def _recalcular_horas_edicion(self, numero_nomina, fecha):
        datos = self.editando.get((numero_nomina, str(fecha)), {})
        entrada = self._parse_time(datos.get("hora_entrada", ""))
        salida = self._parse_time(datos.get("hora_salida", ""))
        descanso = self._descanso_a_minutos(datos.get("descanso", "SN"))
        if entrada and salida:
            total = (datetime.combine(date.min, salida) - datetime.combine(date.min, entrada)).total_seconds() / 3600
            total -= descanso / 60
            total = max(total, 0)
            datos["tiempo_trabajo"] = f"{total:.2f}"
        else:
            datos["tiempo_trabajo"] = "0.00"

    def _recalcular_horas_trabajadas(self, grupo_importacion):
        datos = self.editando.get(("nuevo", grupo_importacion), {})
        entrada = self._parse_time(datos.get("hora_entrada", ""))
        salida = self._parse_time(datos.get("hora_salida", ""))
        descanso = self._descanso_a_minutos(datos.get("descanso", "SN"))

        if entrada and salida:
            total = (datetime.combine(date.min, salida) - datetime.combine(date.min, entrada)).total_seconds() / 3600
            total -= descanso / 60
            total = max(total, 0)
            datos["tiempo_trabajo"] = f"{total:.2f}"
        else:
            datos["tiempo_trabajo"] = "0.00"


    def _guardar_fila_nueva(self, grupo_importacion):
        datos = self.editando.get(("nuevo", grupo_importacion), {})
        if not datos:
            self.window_snackbar.show_error("❌ No se encontraron datos para guardar.")
            return

        try:
            resultado = self.asistencia_model.create(datos)
            if resultado["status"] == "success":
                self.window_snackbar.show_success("✅ Asistencia registrada correctamente.")
            else:
                self.window_snackbar.show_error("❌ " + resultado["message"])
        except Exception as e:
            self.window_snackbar.show_error("⚠️ " + str(e))

        self.editando.pop(("nuevo", grupo_importacion), None)
        self._actualizar_tabla()


    def _cancelar_fila_nueva(self, grupo_importacion):
        self.editando.pop(("nuevo", grupo_importacion), None)
        self._redibujar_tabla_sin_consultar_db()


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


    def _toggle_expansion(self, grupo):
        self.grupos_expandido = {k: False for k in self.datos_por_grupo.keys()}
        self.grupos_expandido[grupo] = True
        self._redibujar_tabla_sin_consultar_db()



    def activar_edicion(self, numero_nomina, fecha):
        print(f"🔧 Activando edición para: ({numero_nomina}, {fecha})")
        self.editando.clear()
        self.editando[(numero_nomina, str(fecha))] = True

        grupo_encontrado = None
        for grupo, registros in self.datos_por_grupo.items():
            if any(reg["numero_nomina"] == numero_nomina and str(reg["fecha"]) == str(fecha) for reg in registros):
                grupo_encontrado = grupo
                break

        if grupo_encontrado:
            print(f"✅ Grupo encontrado: {grupo_encontrado}")
            self.grupos_expandido = {k: False for k in self.datos_por_grupo.keys()}
            self.grupos_expandido[grupo_encontrado] = True
        else:
            print("⚠️ Grupo NO encontrado para este registro")

        print(f"📋 Estado 'editando' actualizado: {self.editando}")
        self._redibujar_tabla_sin_consultar_db()



    def _redibujar_tabla_sin_consultar_db(self):
        self.scroll_column.controls.clear()
        paneles = []

        grupos_ordenados = sorted(
            self.datos_por_grupo.items(),
            key=lambda item: self._extraer_fecha_primer_registro(item[1]),
            reverse=True
        )

        for grupo, registros in grupos_ordenados:
            expandido = self.grupos_expandido.get(grupo, False)
            filas = [self._crear_fila(reg) for reg in registros]

            if ("nuevo", grupo) in self.editando:
                filas.append(self._crear_fila_nueva(grupo))

            tabla = ft.DataTable(
                columns=self.crear_columnas(),
                rows=filas
            )

            encabezado = ft.Row([
                ft.Text(f"🗂 {grupo}", expand=True),
                ft.IconButton(
                    icon=ft.icons.ADD,
                    tooltip="Agregar asistencia",
                    on_click=lambda e, g=grupo: self._agregar_fila_en_grupo(g)
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

        if self.page:
            self.page.update()


    def _crear_fila(self, registro):
        numero_nomina = registro["numero_nomina"]
        fecha = registro["fecha"]
        editable = self.editando.get((numero_nomina, str(fecha)), False)

        print(f"👀 Renderizando fila: ({numero_nomina}, {fecha}) — Editable: {editable}")

        descanso_valor = registro.get("descanso", "SN")
        descanso_texto = f"{descanso_valor}: {self._descanso_a_minutos(descanso_valor)} min"

        if editable:
            campo_entrada = ft.TextField(
                value=registro.get("hora_entrada", ""),
                width=100,
                on_change=lambda e: self._actualizar_campo_edicion(numero_nomina, fecha, "hora_entrada", e.control.value)
            )
            campo_salida = ft.TextField(
                value=registro.get("hora_salida", ""),
                width=100,
                on_change=lambda e: self._actualizar_campo_edicion(numero_nomina, fecha, "hora_salida", e.control.value)
            )
            botones_descanso = {}
            for tipo in ["SN", "MD", "CMP"]:
                botones_descanso[tipo] = ft.FilledButton(
                    tipo,
                    on_click=lambda e, t=tipo: self._actualizar_campo_edicion(numero_nomina, fecha, "descanso", t)
                )
            descanso_widget = ft.Row(list(botones_descanso.values()), spacing=5)

            campo_horas = ft.TextField(
                value=registro.get("tiempo_trabajo", "0.00"),
                width=80,
                read_only=True
            )

            acciones = ft.Row([
                ft.IconButton(
                    icon=ft.icons.SAVE,
                    tooltip="Guardar edición",
                    on_click=lambda e: self._guardar_edicion(numero_nomina, fecha)
                ),
                ft.IconButton(
                    icon=ft.icons.CANCEL,
                    tooltip="Cancelar",
                    on_click=lambda e: self._cancelar_edicion(numero_nomina, fecha)
                )
            ])
        else:
            campo_entrada = ft.Text(registro.get("hora_entrada", ""))
            campo_salida = ft.Text(registro.get("hora_salida", ""))
            descanso_widget = ft.Text(descanso_texto)
            campo_horas = ft.Text(str(registro.get("tiempo_trabajo", "0.00")))
            acciones = ft.Row([
                ft.IconButton(
                    icon=ft.icons.EDIT,
                    tooltip="Editar",
                    on_click=lambda e: self._on_click_editar(numero_nomina, fecha)
                )
            ])

        return ft.DataRow(cells=[
            ft.DataCell(ft.Text(str(numero_nomina))),
            ft.DataCell(ft.Text(registro.get("nombre_completo", ""))),
            ft.DataCell(ft.Text(str(fecha))),
            ft.DataCell(campo_entrada),
            ft.DataCell(campo_salida),
            ft.DataCell(descanso_widget),
            ft.DataCell(campo_horas),
            ft.DataCell(ft.Text(registro.get("estado", ""))),
            ft.DataCell(acciones),
        ])


    def _guardar_edicion(self, numero_nomina, fecha):
        datos = self.editando.get((numero_nomina, str(fecha)), {})
        if not datos:
            self.window_snackbar.show_error("❌ No hay cambios para guardar.")
            return

        datos_actualizados = {
            "numero_nomina": numero_nomina,
            "fecha": fecha,
            "hora_entrada": datos.get("hora_entrada", ""),
            "hora_salida": datos.get("hora_salida", ""),
            "descanso": datos.get("descanso", "SN")
        }

        try:
            resultado = self.asistencia_model.update(datos_actualizados)
            if resultado["status"] == "success":
                self.window_snackbar.show_success("✅ Asistencia actualizada correctamente.")
            else:
                self.window_snackbar.show_error("❌ " + resultado["message"])
        except Exception as e:
            self.window_snackbar.show_error("⚠️ " + str(e))

        self._cancelar_edicion(numero_nomina, fecha)
        self._actualizar_tabla()


    def _actualizar_campo_edicion(self, numero_nomina, fecha, campo, valor):
        key = (numero_nomina, str(fecha))
        if key not in self.editando:
            self.editando[key] = {}
        self.editando[key][campo] = valor
        if campo in ("hora_entrada", "hora_salida", "descanso"):
            self._recalcular_horas_edicion(numero_nomina, fecha)
        if self.page:
            self.page.update()


    def _cancelar_edicion(self, numero_nomina, fecha):
        self.editando.pop((numero_nomina, str(fecha)), None)
        self._redibujar_tabla_sin_consultar_db()


    def _descanso_a_minutos(self, tipo):
        if tipo == "MD":
            return 30
        elif tipo == "CMP":
            return 60
        elif tipo == "SN":
            return 0
        return 0


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