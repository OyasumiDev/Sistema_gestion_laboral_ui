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
from app.helpers.calculo_horas_helper import CalculoHorasHelper
from app.helpers.boton_factory import (
    crear_boton_importar,
    crear_boton_exportar
)


class AsistenciasContainer(ft.Container):
    """
    Área de asistencias con:
      - Scroll vertical (ya existente vía self.scroll_column).
      - Scroll horizontal para pantallas pequeñas (wrapper con Row(scroll=ALWAYS)).
      - Ancho dinámico del lienzo interno para maximizar lectura en pantallas grandes,
        pero conservar un mínimo que habilite el scroll lateral en pantallas pequeñas.
    """

    def __init__(self):
        super().__init__(expand=True, padding=20, alignment=ft.alignment.top_center)
        self.page = AppState().page
        self.asistencia_model = AssistanceModel()
        self.theme_ctrl = ThemeController()
        self.sort_helper = SortHelper(default_key="numero_nomina")
        self.calculo_helper = CalculoHorasHelper()
        self.row_helper = AsistenciasRowHelper(
            recalcular_callback=self._recalcular_horas_fila,
            actualizar_callback=self._actualizar_valor_fila
        )
        self.editando = {}
        self.datos_por_grupo = {}
        self.grupos_expandido = {}

        # ≈ Columnas visibles (no se fija ancho por columna; el ancho total lo maneja el wrapper)
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

        # ===== Scroll vertical (contenido)
        self.scroll_anchor = ft.Container(height=1, key="bottom-anchor")
        self.scroll_column = ft.Column(
            controls=[],
            expand=True,
            scroll=ft.ScrollMode.ALWAYS,
            spacing=10,
            alignment=ft.MainAxisAlignment.START,
        )

        # ===== Acciones (Importar / Exportar)
        self.import_button = crear_boton_importar(
            on_click=lambda: self.import_controller.file_invoker.open()
        )
        self.export_button = crear_boton_exportar(
            on_click=lambda: self.save_invoker.open_save()
        )

        # ===== Scroll horizontal (nuevo)
        # Base mínima que asegura scroll lateral en pantallas chicas.
        # Puedes ajustar este número si tu tabla crece.
        self._base_min_width = 1280
        self._current_scroll_width = self._base_min_width

        # Contenedor interno que se ensancha/encoge dinámicamente
        self._hscroll_inner = ft.Container(
            content=self.scroll_column,
            width=self._current_scroll_width,
            alignment=ft.alignment.top_center,
        )

        # Row con scroll horizontal que envuelve todo el contenido "ancho"
        self._hscroll_row = ft.Row(
            controls=[self._hscroll_inner],
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.START,
            alignment=ft.MainAxisAlignment.START,
            scroll=ft.ScrollMode.ALWAYS,  # ← clave para scroll lateral
        )

        # Build UI
        self.content = self._build_content()

        # Suscribir a resize para ajustar ancho dinámico
        if self.page:
            self.page.on_resize = self._on_page_resize

        # Cargar datos
        self._actualizar_tabla()
        # Ajuste inicial
        self._update_scroll_area_width()

    # ---------------- UI ----------------
    def _build_content(self) -> ft.Control:
        return ft.Container(
            expand=True,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                alignment=ft.MainAxisAlignment.START,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20,
                controls=[
                    ft.Text(
                        "Registro de Asistencias",
                        size=24,
                        weight="bold",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(
                        alignment=ft.alignment.center_left,
                        padding=ft.padding.only(left=60),
                        content=ft.Row(
                            spacing=10,
                            alignment=ft.MainAxisAlignment.START,
                            controls=[self.import_button, self.export_button],
                        ),
                    ),
                    # ====== Aquí va el wrapper con scroll horizontal ======
                    ft.Container(
                        alignment=ft.alignment.top_center,
                        padding=ft.padding.symmetric(horizontal=10),
                        content=self._hscroll_row,
                    ),
                ],
            ),
        )

    def _on_page_resize(self, e: ft.ControlEvent | None):
        self._update_scroll_area_width()

    def _update_scroll_area_width(self):
        """
        Ajusta el ancho del lienzo interno para:
          - No bajar de _base_min_width (para forzar scroll lateral en pantallas pequeñas).
          - Usar el ancho disponible en pantallas grandes (evitar márgenes vacíos grandes).
        """
        try:
            page_w = int(self.page.width or 0) if self.page else 0
            # margen lateral estimado (botones / padding); ajusta si lo deseas
            margin = 80
            target = max(self._base_min_width, (page_w - margin) if page_w > 0 else self._base_min_width)
            if abs(target - self._current_scroll_width) >= 8:
                self._current_scroll_width = target
                self._hscroll_inner.width = self._current_scroll_width
                if self.page:
                    self.page.update()
        except Exception:
            pass

    # ---------------- Helpers de tabla ----------------
    def crear_columnas(self):
        return self.column_builder.build_columns(self.columnas_definidas)

    # ------------- Acciones de UI -------------
    def _recalcular_horas_fila(self, grupo):
        # Si es nueva fila en edición -> refresca
        if ("nuevo", grupo) in self.editando:
            self._actualizar_tabla()
            return

        # Si hay edición activa en ese grupo -> refresca
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
        # Nueva fila
        if ("nuevo", grupo) in self.editando:
            self.editando[("nuevo", grupo)][campo] = valor
            return

        # Edición activa
        for (numero_nomina, fecha), edit_flag in self.editando.items():
            if edit_flag is True:
                for registros in self.datos_por_grupo.get(grupo, []):
                    if registros["numero_nomina"] == numero_nomina and str(registros["fecha"]) == str(fecha):
                        registros[campo] = valor
                        return

    # ---------------- Construcción dinámica ----------------
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
            if self.page:
                self.page.update()
            return

        paneles = []
        grupos_ordenados = sorted(
            self.datos_por_grupo.items(),
            key=lambda item: self._extraer_fecha_primer_registro(item[1]),
            reverse=True,
        )

        if not self.grupos_expandido and grupos_ordenados:
            self.grupos_expandido = {g: False for g, _ in grupos_ordenados}
            self.grupos_expandido[grupos_ordenados[0][0]] = True

        for grupo, registros in grupos_ordenados:
            expandido = self.grupos_expandido.get(grupo, False)
            filas = []

            for reg in registros:
                if reg.get("__error_horas", False):
                    reg["estado"] = "ERROR"

                if self._es_editando(reg):
                    filas.append(
                        self.row_helper.build_fila_edicion(
                            registro=reg,
                            on_save=lambda g=grupo, r=reg: self._guardar_edicion(r["numero_nomina"], r["fecha"]),
                            on_cancel=lambda g=grupo, r=reg: self._cancelar_edicion(r["numero_nomina"], r["fecha"]),
                        )
                    )
                else:
                    filas.append(
                        self.row_helper.build_fila_vista(
                            registro=reg,
                            on_edit=self._on_click_editar,
                            on_delete=lambda r=reg: self._confirmar_eliminacion(r["numero_nomina"], r["fecha"]),
                        )
                    )

            # Fila nueva (si corresponde)
            if ("nuevo", grupo) in self.editando:
                nueva_fila = self.row_helper.build_fila_nueva(
                    grupo_importacion=grupo,
                    registro=self.editando[("nuevo", grupo)],
                    on_save=lambda g=grupo: self._guardar_fila_nueva(g),
                    on_cancel=lambda g=grupo: self._cancelar_fila_nueva(g),
                    registros_del_grupo=registros,
                )
                if getattr(nueva_fila, "cells", None) and nueva_fila.cells and nueva_fila.cells[0].content:
                    nueva_fila.cells[0].content.key = f"nuevo-{grupo}"
                filas.append(nueva_fila)

            tabla = ft.DataTable(columns=self.crear_columnas(), rows=filas)

            encabezado = ft.Row(
                [
                    ft.Text(f"🗂 {grupo}", expand=True),
                    ft.IconButton(
                        icon=ft.icons.ADD,
                        tooltip="Agregar asistencia",
                        on_click=lambda e, g=grupo: self._agregar_fila_en_grupo(g),
                    ),
                    ft.IconButton(
                        icon=ft.icons.DELETE_OUTLINE,
                        tooltip="Eliminar grupo",
                        icon_color=ft.colors.RED_600,
                        on_click=lambda e, g=grupo: self._eliminar_grupo(g),
                    ),
                ]
            )

            panel = ft.ExpansionPanel(
                header=encabezado,
                content=ft.Column([ft.Container(key=grupo), tabla]),
                can_tap_header=True,
                expanded=expandido,
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

    # ------ Nueva fila / edición / eliminación ------
    def _agregar_fila_en_grupo(self, grupo_importacion):
        self.editando[("nuevo", grupo_importacion)] = {
            "numero_nomina": "",
            "fecha": "",
            "hora_entrada": "",
            "hora_salida": "",
            "descanso": "SN",
            "tiempo_trabajo": "0.00",
            "estado": "PENDIENTE",
        }

        self.grupos_expandido = {k: False for k in self.datos_por_grupo.keys()}
        self.grupos_expandido[grupo_importacion] = True

        self._actualizar_tabla()
        if self.page and self.scroll_column:
            self.scroll_column.scroll_to(key=f"nuevo-{grupo_importacion}", duration=300)

    def _guardar_fila_nueva(self, grupo: str):
        try:
            fila = self.editando.get(("nuevo", grupo), {})

            numero = str(fila.get("numero_nomina", "")).strip()
            if not numero.isdigit():
                self.window_snackbar.show_error("❌ Número de nómina inválido.")
                return
            numero = int(numero)

            fecha_str = str(fila.get("fecha", "")).strip()
            try:
                fecha_dt = datetime.strptime(fecha_str, "%d/%m/%Y")
                fecha_iso = fecha_dt.strftime("%Y-%m-%d")
            except Exception:
                self.window_snackbar.show_error("❌ Formato de fecha inválido. Usa DD/MM/AAAA.")
                return

            hora_entrada = self.calculo_helper.sanitizar_hora(fila.get("hora_entrada"))
            hora_salida = self.calculo_helper.sanitizar_hora(fila.get("hora_salida"))
            descanso = fila.get("descanso", "SN")

            resultado = self.calculo_helper.recalcular_con_estado(hora_entrada, hora_salida, descanso)
            if resultado["estado"] != "ok":
                self.window_snackbar.show_error(f"❌ {resultado.get('mensaje', 'Error en tiempo trabajado.')}")
                return

            registros_del_grupo = self.datos_por_grupo.get(grupo, [])
            valido, errores = self.calculo_helper.validar_numero_fecha_en_grupo(
                registros_del_grupo, numero, fecha_str, registro_actual=fila
            )
            if not valido:
                self.window_snackbar.show_error("❌ " + " ".join(errores))
                return

            resultado_db = self.asistencia_model.add(
                numero_nomina=numero,
                fecha=fecha_iso,
                hora_entrada=hora_entrada,
                hora_salida=hora_salida,
                descanso={"SN": 0, "MD": 1, "CMP": 2}.get(descanso, 0),
                grupo_importacion=grupo,
            )

            if not resultado_db or resultado_db.get("status") != "success":
                self.window_snackbar.show_error("❌ Error al guardar en la base de datos.")
                return

            self.window_snackbar.show_success("✅ Asistencia guardada correctamente.")
            self.editando.pop(("nuevo", grupo), None)
            self._actualizar_tabla()

        except Exception as e:
            self.window_snackbar.show_error("⚠️ Error inesperado al guardar.")

    def _cancelar_fila_nueva(self, grupo):
        if ("nuevo", grupo) in self.editando:
            self.editando.pop(("nuevo", grupo))
            self._actualizar_tabla()
            self.window_snackbar.show_success("ℹ️ Registro cancelado.")

    def _toggle_expansion(self, grupo):
        self.grupos_expandido = {k: False for k in self.datos_por_grupo.keys()}
        self.grupos_expandido[grupo] = True
        self._actualizar_tabla()
        if self.page:
            AsistenciasScrollHelper.scroll_to_group_after_build(self.page, group_id=grupo)

    def _es_editando(self, registro):
        return self.editando.get((registro["numero_nomina"], str(registro["fecha"])), False)

    def _guardar_edicion(self, numero_nomina, fecha):
        registro_actualizado = None
        for grupo, registros in self.datos_por_grupo.items():
            for reg in registros:
                if reg["numero_nomina"] == numero_nomina and str(reg["fecha"]) == str(fecha):
                    registro_actualizado = reg
                    break
            if registro_actualizado:
                break

        if not registro_actualizado:
            self.window_snackbar.show_error("❌ No se encontró el registro a actualizar.")
            return

        fecha_valor = str(registro_actualizado.get("fecha", "")).strip()
        try:
            fecha_obj = (
                datetime.strptime(fecha_valor, "%d/%m/%Y")
                if "/" in fecha_valor
                else datetime.strptime(fecha_valor, "%Y-%m-%d")
            )
            registro_actualizado["fecha"] = fecha_obj.strftime("%Y-%m-%d")
        except Exception:
            self.window_snackbar.show_error("⚠️ Fecha inválida. Usa el formato YYYY-MM-DD.")
        # Convertir horas
        def convertir(t):
            if isinstance(t, timedelta):
                return (datetime.min + t).time().strftime("%H:%M:%S")
            return str(t).strip()

        registro_actualizado["hora_entrada"] = convertir(registro_actualizado.get("hora_entrada"))
        registro_actualizado["hora_salida"] = convertir(registro_actualizado.get("hora_salida"))

        resultado = self.row_helper.calculo_helper.recalcular_con_estado(
            registro_actualizado["hora_entrada"],
            registro_actualizado["hora_salida"],
            registro_actualizado.get("descanso", "SN"),
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
        self.editando.clear()
        self._actualizar_tabla()
        self.window_snackbar.show_success("ℹ️ Edición cancelada.")

    # --------- Agrupaciones ---------
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

    # --------- Eliminación ---------
    def _eliminar_grupo(self, grupo):
        confirmacion = ModalAlert(
            title_text="¿Eliminar grupo?",
            message=f"¿Deseas eliminar todas las asistencias del grupo '{grupo}'?",
            on_confirm=lambda: self._confirmar_eliminar_grupo(grupo),
            on_cancel=self._actualizar_tabla,
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
            on_cancel=self._actualizar_tabla,
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

    # --------- Exportación ---------
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

    # --------- Agrupación semanal (no usada directamente en UI principal) ---------
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
                except Exception:
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
