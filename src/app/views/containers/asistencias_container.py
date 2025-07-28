import flet as ft
from datetime import datetime, timedelta, date
import pandas as pd
import asyncio

from app.models.assistance_model import AssistanceModel
from app.controllers.asistencias_import_controller import AsistenciasImportController
from app.core.app_state import AppState
from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.views.containers.theme_controller import ThemeController
from app.views.containers.window_snackbar import WindowSnackbar
from app.views.containers.modal_alert import ModalAlert

from app.helpers.sort_helpers import SortHelper
from app.helpers.table_column_builder import TableColumnBuilder
from app.helpers.asistencias_scroll_helper import AsistenciasScrollHelper
from app.helpers.asistencias_row_helper import AsistenciasRowHelper
from app.helpers.boton_factory import (
    crear_boton_importar,
    crear_boton_exportar
)


class AsistenciasContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20, alignment=ft.alignment.top_center)
        self.page = AppState().page
        self.asistencia_model = AssistanceModel()
        self.theme_ctrl = ThemeController()
        self.sort_helper = SortHelper(default_key="numero_nomina")
        self.row_helper = AsistenciasRowHelper(
            recalcular_callback=self._recalcular_horas_fila,
            actualizar_callback=self._actualizar_valor_fila
        )
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

        # ✅ Ancla de scroll al final
        self.scroll_anchor = ft.Container(height=1, key="bottom-anchor")

        # ✅ Scroll Column incluye el anchor al final
        self.scroll_column = ft.Column(
            controls=[],
            expand=True,
            scroll=ft.ScrollMode.ALWAYS,
            spacing=10,
            alignment=ft.MainAxisAlignment.START
        )

        # ✅ Botones de acción (Importar y Exportar) usando BotonFactory
        self.import_button = crear_boton_importar(
            on_click=lambda: self.import_controller.file_invoker.open()
        )

        self.export_button = crear_boton_exportar(
            on_click=lambda: self.save_invoker.open_save()
        )


        self.content = self._build_content()
        self._actualizar_tabla()



    def _recalcular_horas_fila(self, grupo):
        print(f"🔄 Recalculando horas para el grupo '{grupo}'")
        # Si es nueva fila en edición, simplemente actualizamos la tabla (como ya haces)
        if ("nuevo", grupo) in self.editando:
            self._actualizar_tabla()
            return

        # Si hay alguna edición activa en ese grupo, actualiza la tabla
        for (numero_nomina, fecha), edit_flag in self.editando.items():
            if edit_flag is True:
                for registros in self.datos_por_grupo.get(grupo, []):
                    if registros["numero_nomina"] == numero_nomina and str(registros["fecha"]) == str(fecha):
                        self._actualizar_tabla()
                        return


    def _on_click_editar(self, numero_nomina, fecha):
        self.activar_edicion(numero_nomina, fecha)
        self._actualizar_tabla()

    def _actualizar_valor_fila(self, grupo, campo, valor):
        # Si es nueva fila
        if ("nuevo", grupo) in self.editando:
            self.editando[("nuevo", grupo)][campo] = valor
            print(f"📝 Actualizado campo '{campo}' para NUEVA fila en grupo '{grupo}' con valor: {valor}")
            return

        # Si hay edición activa (solo uno activo a la vez)
        for (numero_nomina, fecha), edit_flag in self.editando.items():
            if edit_flag is True:
                for registros in self.datos_por_grupo.get(grupo, []):
                    if registros["numero_nomina"] == numero_nomina and str(registros["fecha"]) == str(fecha):
                        registros[campo] = valor
                        print(f"📝 Actualizado campo '{campo}' en edición activa ({numero_nomina}, {fecha}) con valor: {valor}")
                        return



    def _build_content(self):
        return ft.Container(
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


    def crear_columnas(self):
        return self.column_builder.build_columns(self.columnas_definidas)


    def _agregar_fila_en_grupo(self, grupo_importacion):
        print(f"➕ Agregando fila nueva en grupo '{grupo_importacion}'")
        self.editando[("nuevo", grupo_importacion)] = {
            "numero_nomina": "",
            "fecha": "",
            "hora_entrada": "",
            "hora_salida": "",
            "descanso": "SN",
            "tiempo_trabajo": "0.00",
            "estado": "PENDIENTE"
        }

        self.grupos_expandido = {k: False for k in self.datos_por_grupo.keys()}
        self.grupos_expandido[grupo_importacion] = True

        self._actualizar_tabla()
        self.page.update()

        # 🔥 Usamos el scroll_to propio del Column para ir a la fila nueva agregada
        if self.scroll_column:
            print(f"🔧 Scroll automático al nuevo registro '{grupo_importacion}'")
            self.scroll_column.scroll_to(
                key=f"nuevo-{grupo_importacion}",
                duration=300
            )


    def _guardar_fila_nueva(self, grupo: str):
        datos = self.editando.get(("nuevo", grupo), None)
        if not datos:
            self.window_snackbar.show_error("❌ No hay datos para guardar.")
            return

        numero = str(datos.get("numero_nomina", "")).strip()
        fecha = str(datos.get("fecha", "")).strip()

        errores = []

        # ❌ Validar existencia de campos
        if not numero:
            errores.append("Número de nómina requerido.")
        elif not numero.isdigit():
            errores.append("Número de nómina inválido.")

        if not fecha:
            errores.append("Fecha requerida.")
        else:
            try:
                datetime.strptime(fecha, "%Y-%m-%d")
            except Exception:
                errores.append("Fecha inválida. Usa el formato YYYY-MM-DD.")

        # ❌ Validar duplicado dentro del grupo actual
        grupo_actual = self.datos_por_grupo.get(grupo, [])
        validacion = self.row_helper.calculo_helper.validar_duplicado_en_grupo(
            grupo_actual, numero, fecha
        )
        if validacion["duplicado"]:
            errores.append(validacion["mensaje"])

        # ❌ Validar tiempo trabajado
        resultado = self.row_helper.calculo_helper.recalcular_con_estado(
            datos.get("hora_entrada", ""),
            datos.get("hora_salida", ""),
            datos.get("descanso", "SN")
        )
        if resultado["estado"] != "ok":
            errores.append(resultado["mensaje"] or "Error en el cálculo de tiempo trabajado.")

        if errores:
            self.window_snackbar.show_error("❌ " + "\n".join(errores))
            return

        # ✅ Preparar datos para guardar
        datos["numero_nomina"] = numero
        datos["fecha"] = fecha
        datos["tiempo_trabajo"] = resultado["tiempo_trabajo"]
        datos["tiempo_trabajo_con_descanso"] = resultado["tiempo_trabajo_con_descanso"]

        # ✅ Guardar en base de datos
        resultado_db = self.asistencia_model.create_asistencia(datos)
        if resultado_db["status"] == "success":
            self.window_snackbar.show_success("✅ Asistencia registrada correctamente.")
        else:
            self.window_snackbar.show_error(f"❌ {resultado_db.get('message', 'Error al guardar la asistencia.')}")

        self.editando.pop(("nuevo", grupo), None)
        self._actualizar_tabla()


    def _cancelar_fila_nueva(self, grupo):
        if ("nuevo", grupo) in self.editando:
            self.editando.pop(("nuevo", grupo))
            self._actualizar_tabla()
            self.window_snackbar.show_success("ℹ️ Registro cancelado.")

    def _toggle_expansion(self, grupo):
        print(f"🔽 Toggling expansión del grupo '{grupo}'")
        self.grupos_expandido = {k: False for k in self.datos_por_grupo.keys()}
        self.grupos_expandido[grupo] = True
        self._actualizar_tabla()
        self.page.update()
        print(f"🔧 Registrando scroll tras toggle para grupo '{grupo}'")
        AsistenciasScrollHelper.scroll_to_group_after_build(self.page, group_id=grupo)


    def _actualizar_tabla(self):
        resultado = self.asistencia_model.get_all()
        if resultado["status"] != "success":
            self.window_snackbar.show_error("❌ No se pudieron cargar asistencias.")
            return

        datos = resultado["data"]
        self.datos_por_grupo = self._agrupar_por_grupo_importacion(datos)
        self.scroll_column.controls.clear()

        if not self.datos_por_grupo:
            self.scroll_column.controls.append(ft.Text("No hay asistencias registradas."))
            self.scroll_column.controls.append(self.scroll_anchor)
            self.page.update()
            return

        paneles = []
        grupos_ordenados = sorted(
            self.datos_por_grupo.items(),
            key=lambda item: self._extraer_fecha_primer_registro(item[1]),
            reverse=True
        )

        if not self.grupos_expandido and grupos_ordenados:
            self.grupos_expandido = {g: False for g, _ in grupos_ordenados}
            self.grupos_expandido[grupos_ordenados[0][0]] = True

        for grupo, registros in grupos_ordenados:
            expandido = self.grupos_expandido.get(grupo, False)
            filas = []

            for reg in registros:
                # ⚠️ Marcar errores visuales
                if reg.get("__error_horas", False):
                    reg["estado"] = "ERROR"

                if self._es_editando(reg):
                    filas.append(self.row_helper.build_fila_edicion(
                        registro=reg,
                        on_save=lambda g=grupo, r=reg: self._guardar_edicion(r["numero_nomina"], r["fecha"]),
                        on_cancel=lambda g=grupo, r=reg: self._cancelar_edicion(r["numero_nomina"], r["fecha"])
                    ))
                else:
                    filas.append(self.row_helper.build_fila_vista(
                        registro=reg,
                        on_edit=self._on_click_editar,
                        on_delete=lambda r=reg: self._confirmar_eliminacion(r["numero_nomina"], r["fecha"])
                    ))

            # ✅ Agregar fila nueva si corresponde
            if ("nuevo", grupo) in self.editando:
                nueva_fila = self.row_helper.build_fila_nueva(
                    grupo_importacion=grupo,
                    registro=self.editando[("nuevo", grupo)],
                    on_save=lambda g=grupo: self._guardar_fila_nueva(g),
                    on_cancel=lambda g=grupo: self._cancelar_fila_nueva(g),
                    registros_del_grupo=registros  # ✅ Corrección: este parámetro es obligatorio ahora
                )

                if nueva_fila.cells and nueva_fila.cells[0].content:
                    nueva_fila.cells[0].content.key = f"nuevo-{grupo}"

                filas.append(nueva_fila)

            tabla = ft.DataTable(columns=self.crear_columnas(), rows=filas)

            encabezado = ft.Row([
                ft.Text(f"🗂 {grupo}", expand=True),
                ft.IconButton(icon=ft.icons.ADD, tooltip="Agregar asistencia", on_click=lambda e, g=grupo: self._agregar_fila_en_grupo(g)),
                ft.IconButton(icon=ft.icons.DELETE_OUTLINE, tooltip="Eliminar grupo", icon_color=ft.colors.RED_600, on_click=lambda e, g=grupo: self._eliminar_grupo(g))
            ])

            panel = ft.ExpansionPanel(
                header=encabezado,
                content=ft.Column([ft.Container(key=grupo), tabla]),
                can_tap_header=True,
                expanded=expandido
            )

            panel.on_expansion_changed = lambda e, g=grupo: self._toggle_expansion(g)
            paneles.append(panel)

        self.scroll_column.controls.append(ft.ExpansionPanelList(expand=True, controls=paneles))
        self.scroll_column.controls.append(self.scroll_anchor)

        if self.page:
            grupo_expandido = next((g for g, exp in self.grupos_expandido.items() if exp), None)
            if grupo_expandido:
                AsistenciasScrollHelper.scroll_to_group_after_build(self.page, group_id=grupo_expandido)
            self.page.update()



    def _es_editando(self, registro):
        return self.editando.get((registro["numero_nomina"], str(registro["fecha"])), False)

    def _guardar_edicion(self, numero_nomina, fecha):
        print(f"💾 [GUARDAR EDICIÓN] Iniciando para: (Nómina: {numero_nomina}, Fecha: {fecha})")

        registro_actualizado = None
        for grupo, registros in self.datos_por_grupo.items():
            for reg in registros:
                if reg["numero_nomina"] == numero_nomina and str(reg["fecha"]) == str(fecha):
                    registro_actualizado = reg
                    print(f"🔎 Registro encontrado en grupo '{grupo}': {reg}")
                    break
            if registro_actualizado:
                break

        if not registro_actualizado:
            self.window_snackbar.show_error("❌ No se encontró el registro a actualizar.")
            return

        fecha_valor = str(registro_actualizado.get("fecha", "")).strip()
        try:
            fecha_obj = datetime.strptime(fecha_valor, "%d/%m/%Y") if "/" in fecha_valor else datetime.strptime(fecha_valor, "%Y-%m-%d")
            registro_actualizado["fecha"] = fecha_obj.strftime("%Y-%m-%d")
        except Exception as e:
            self.window_snackbar.show_error("⚠️ Fecha inválida. Usa el formato YYYY-MM-DD.")
            return

        def convertir(t):
            if isinstance(t, timedelta):
                return (datetime.min + t).time().strftime("%H:%M:%S")
            return str(t).strip()

        registro_actualizado["hora_entrada"] = convertir(registro_actualizado.get("hora_entrada"))
        registro_actualizado["hora_salida"] = convertir(registro_actualizado.get("hora_salida"))

        # ✅ Validar y calcular tiempo con helper unificado
        resultado = self.row_helper.calculo_helper.recalcular_con_estado(
            registro_actualizado["hora_entrada"],
            registro_actualizado["hora_salida"],
            registro_actualizado.get("descanso", "SN")
        )

        if resultado["estado"] != "ok":
            self.window_snackbar.show_error("❌ " + (resultado["mensaje"] or "Error al calcular tiempo trabajado."))
            return

        registro_actualizado["tiempo_trabajo"] = resultado["tiempo_trabajo"]
        registro_actualizado["tiempo_trabajo_con_descanso"] = resultado["tiempo_trabajo_con_descanso"]

        resultado_db = self.asistencia_model.update_asistencia(registro_actualizado)
        if resultado_db["status"] == "success":
            self.window_snackbar.show_success("✅ Asistencia actualizada correctamente.")
        else:
            self.window_snackbar.show_error(f"❌ {resultado_db.get('message', 'Error al actualizar la asistencia.')}")

        self.editando.clear()
        self._actualizar_tabla()

    def _cancelar_edicion(self, numero_nomina, fecha):
        print(f"❌ Cancelando edición para: ({numero_nomina}, {fecha}) — Limpieza de estado de edición")
        self.editando.clear()
        self._actualizar_tabla()
        self.window_snackbar.show_success("ℹ️ Edición cancelada.")


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
                reg["grupo_importacion"] = grupo_fecha

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
            # ✅ Solo actualizas la tabla una vez
            self._actualizar_tabla()
            self.page.update()
            AsistenciasScrollHelper.scroll_to_group_after_build(self.page, group_id=grupo_encontrado)
        else:
            print("⚠️ Grupo NO encontrado para este registro")
            self._actualizar_tabla()

        print(f"📋 Estado 'editando' actualizado: {self.editando}")


    def _eliminar_grupo(self, grupo):
        confirmacion = ModalAlert(
            title_text="¿Eliminar grupo?",
            message=f"¿Deseas eliminar todas las asistencias del grupo '{grupo}'?",
            on_confirm=lambda: self._confirmar_eliminar_grupo(grupo),
            on_cancel=self._actualizar_tabla
        )
        confirmacion.mostrar()

    def _confirmar_eliminar_grupo(self, grupo):
        try:
            registros = self.datos_por_grupo.get(grupo, [])
            for reg in registros:
                self.asistencia_model.delete_by_numero_nomina_and_fecha(reg["numero_nomina"], reg["fecha"])
            self.window_snackbar.show_success(f"✅ Grupo '{grupo}' eliminado.")
        except Exception as e:
            self.window_snackbar.show_error(f"❌ Error eliminando grupo: {str(e)}")
        self._actualizar_tabla()


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
                self.window_snackbar.show_error(f"❌ {resultado['message']}")
        except Exception as e:
            self.window_snackbar.show_error(f"⚠️ {str(e)}")

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