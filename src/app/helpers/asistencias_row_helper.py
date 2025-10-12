import flet as ft
from typing import Callable, Dict
from app.helpers.calculo_horas_helper import CalculoHorasHelper
from app.core.app_state import AppState
import re
from datetime import datetime


class AsistenciasRowHelper:
    def __init__(self, recalcular_callback: Callable, actualizar_callback: Callable):
        self.recalcular_callback = recalcular_callback
        self.actualizar_callback = actualizar_callback
        self.calculo_helper = CalculoHorasHelper()
        self.page = AppState().page

    # ---------- util ----------
    def _wrap_cell(self, control, width: int) -> ft.Container:
        return ft.Container(
            content=control,
            width=width,
            alignment=ft.alignment.center,
            padding=ft.padding.symmetric(horizontal=2)
        )

    def _soft_update(self):
        if self.page:
            self.page.update()

    # ========== FILA NUEVA ==========
    def build_fila_nueva(
        self,
        grupo_importacion: str,
        registro: Dict,
        on_save: Callable,
        on_cancel: Callable,
        registros_del_grupo: list
    ) -> ft.DataRow:
        if not registro.get("descanso"):
            registro["descanso"] = "MD"
        if not registro.get("estado"):
            registro["estado"] = "PENDIENTE"

        # Widgets
        estado_text = ft.Text(
            registro.get("estado", "PENDIENTE").upper(),
            size=12,
            text_align=ft.TextAlign.CENTER,
            color=ft.colors.GREY
        )
        tiempo_field = ft.TextField(
            value=registro.get("tiempo_trabajo_con_descanso", "00:00:00"),
            width=100,
            read_only=True,
            text_align=ft.TextAlign.CENTER
        )

        entrada_field = ft.TextField(
            width=100,
            value=self.calculo_helper.sanitizar_hora(registro.get("hora_entrada", "")),
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.DATETIME,
            on_change=lambda e: self._on_change_hora(
                grupo_importacion, registro, "hora_entrada",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
            on_blur=lambda e: self._on_blur_hora(
                grupo_importacion, registro, "hora_entrada",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
        )
        salida_field = ft.TextField(
            width=100,
            value=self.calculo_helper.sanitizar_hora(registro.get("hora_salida", "")),
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.DATETIME,
            on_change=lambda e: self._on_change_hora(
                grupo_importacion, registro, "hora_salida",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
            on_blur=lambda e: self._on_blur_hora(
                grupo_importacion, registro, "hora_salida",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
        )

        # Validaciones extra
        def on_numero_blur(e):
            registro["numero_nomina"] = e.control.value
            self.actualizar_callback(grupo_importacion, "numero_nomina", e.control.value)
            self.calculo_helper.validar_fecha_y_numero(registro, registros_del_grupo, numero_field, fecha_field)
            self._soft_update()

        def on_fecha_blur(e):
            registro["fecha"] = e.control.value
            self.actualizar_callback(grupo_importacion, "fecha", e.control.value)
            self.calculo_helper.validar_fecha_y_numero(registro, registros_del_grupo, numero_field, fecha_field)
            self._soft_update()

        numero_field = ft.TextField(
            width=60,
            value=str(registro.get("numero_nomina", "")),
            on_blur=on_numero_blur,
            autofocus=True,
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        fecha_field = ft.TextField(
            width=150,
            value=str(registro.get("fecha", "")),
            on_blur=on_fecha_blur,
            text_align=ft.TextAlign.CENTER
        )

        descanso_widget = self._crear_botones_descanso(
            grupo_importacion, registro, tiempo_field, estado_text, entrada_field, salida_field
        )

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(numero_field, 60)),
            ft.DataCell(self._wrap_cell(ft.Text("-", overflow=ft.TextOverflow.ELLIPSIS, max_lines=1), 250)),
            ft.DataCell(self._wrap_cell(fecha_field, 150)),
            ft.DataCell(self._wrap_cell(entrada_field, 100)),
            ft.DataCell(self._wrap_cell(salida_field, 100)),
            ft.DataCell(self._wrap_cell(descanso_widget, 180)),
            ft.DataCell(self._wrap_cell(tiempo_field, 100)),
            ft.DataCell(self._wrap_cell(estado_text, 100)),
            ft.DataCell(self._wrap_cell(ft.Row([
                ft.IconButton(icon=ft.icons.SAVE, tooltip="Guardar", on_click=lambda e: on_save()),
                ft.IconButton(icon=ft.icons.CANCEL, tooltip="Cancelar", on_click=lambda e: on_cancel())
            ], spacing=5), 100))
        ])

    # ========== FILA EDICIÓN ==========
    def build_fila_edicion(self, registro: Dict, on_save: Callable, on_cancel: Callable) -> ft.DataRow:
        numero_nomina = registro["numero_nomina"]
        fecha = registro["fecha"]
        grupo = registro.get("grupo_importacion", "")

        if not registro.get("descanso"):
            registro["descanso"] = "MD"

        estado_text = ft.Text(
            registro.get("estado", "").upper(),
            size=12,
            text_align=ft.TextAlign.CENTER,
            color=ft.colors.RED if registro.get("estado") == "INCOMPLETO" else ft.colors.GREEN
        )
        tiempo_field = ft.TextField(
            value=registro.get("tiempo_trabajo_con_descanso", "00:00:00"),
            width=100,
            read_only=True,
            text_align=ft.TextAlign.CENTER
        )

        entrada_field = ft.TextField(
            value=self.calculo_helper.sanitizar_hora(registro.get("hora_entrada", "")),
            width=100,
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.DATETIME,
            on_change=lambda e: self._on_change_hora(
                grupo, registro, "hora_entrada",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
            on_blur=lambda e: self._on_blur_hora(
                grupo, registro, "hora_entrada",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
        )
        salida_field = ft.TextField(
            value=self.calculo_helper.sanitizar_hora(registro.get("hora_salida", "")),
            width=100,
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.DATETIME,
            on_change=lambda e: self._on_change_hora(
                grupo, registro, "hora_salida",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
            on_blur=lambda e: self._on_blur_hora(
                grupo, registro, "hora_salida",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
        )

        descanso_widget = self._crear_botones_descanso(
            grupo, registro, tiempo_field, estado_text, entrada_field, salida_field
        )

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(ft.Text(str(numero_nomina)), 60)),
            ft.DataCell(self._wrap_cell(ft.Text(
                registro.get("nombre_completo", ""),
                overflow=ft.TextOverflow.ELLIPSIS, max_lines=1, text_align=ft.TextAlign.LEFT
            ), 250)),
            ft.DataCell(self._wrap_cell(ft.Text(str(fecha)), 135)),
            ft.DataCell(self._wrap_cell(entrada_field, 100)),
            ft.DataCell(self._wrap_cell(salida_field, 100)),
            ft.DataCell(self._wrap_cell(descanso_widget, 180)),
            ft.DataCell(self._wrap_cell(tiempo_field, 100)),
            ft.DataCell(self._wrap_cell(estado_text, 100)),
            ft.DataCell(self._wrap_cell(ft.Row([
                ft.IconButton(icon=ft.icons.SAVE, tooltip="Guardar edición", on_click=lambda e: on_save()),
                ft.IconButton(icon=ft.icons.CANCEL, tooltip="Cancelar", on_click=lambda e: on_cancel())
            ], spacing=5), 100))
        ])

    # ========== FILA VISTA ==========
    def build_fila_vista(self, registro: dict, on_edit: Callable, on_delete: Callable = None) -> ft.DataRow:
        numero_nomina = registro["numero_nomina"]
        fecha = registro["fecha"]
        descanso = registro.get("descanso", "MD")
        descanso_texto = f"{descanso}: {self.calculo_helper.obtener_minutos_descanso(descanso)} min"
        tiempo_mostrar = registro.get("tiempo_trabajo_con_descanso", "00:00:00")

        estado_text = ft.Text(
            registro.get("estado", "").upper(),
            text_align=ft.TextAlign.CENTER,
            color=ft.colors.RED if registro.get("estado") == "INCOMPLETO" else ft.colors.GREEN
        )

        acciones = [ft.IconButton(icon=ft.icons.EDIT, tooltip="Editar", on_click=lambda e: on_edit(numero_nomina, fecha))]
        if on_delete:
            acciones.append(
                ft.IconButton(icon=ft.icons.DELETE_OUTLINE, tooltip="Eliminar", icon_color=ft.colors.RED_600,
                              on_click=lambda e: on_delete(registro))
            )

        return ft.DataRow(cells=[
            ft.DataCell(self._wrap_cell(ft.Text(str(numero_nomina)), 60)),
            ft.DataCell(self._wrap_cell(ft.Text(
                registro.get("nombre_completo", ""),
                overflow=ft.TextOverflow.ELLIPSIS, max_lines=1, text_align=ft.TextAlign.LEFT
            ), 250)),
            ft.DataCell(self._wrap_cell(ft.Text(str(fecha)), 135)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("hora_entrada", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(registro.get("hora_salida", "")), 100)),
            ft.DataCell(self._wrap_cell(ft.Text(descanso_texto), 180)),
            ft.DataCell(self._wrap_cell(ft.Text(str(tiempo_mostrar)), 100)),
            ft.DataCell(self._wrap_cell(estado_text, 100)),
            ft.DataCell(self._wrap_cell(ft.Row(acciones, spacing=5), 100))
        ])

    # ========== HANDLERS ==========
    def _on_change_hora(self, grupo, registro, campo, entrada_field, salida_field, tiempo_field, estado_text):
        valor = entrada_field.value if campo == "hora_entrada" else salida_field.value
        registro[campo] = valor
        self.actualizar_callback(grupo, campo, valor)

        res = self.calculo_helper.recalcular_con_estado(
            entrada_field.value, salida_field.value, registro.get("descanso", "MD")
        )
        tiempo_field.value = res.get("tiempo_trabajo_con_descanso", "00:00:00")
        registro["tiempo_trabajo"] = res.get("tiempo_trabajo", "00:00:00")
        registro["tiempo_trabajo_con_descanso"] = tiempo_field.value

        nuevo_estado = "COMPLETO" if res.get("estado") == "ok" else "INCOMPLETO"
        registro["estado"] = nuevo_estado
        estado_text.value = nuevo_estado
        estado_text.color = ft.colors.GREEN if nuevo_estado == "COMPLETO" else ft.colors.RED

        self._soft_update()

    def _on_blur_hora(self, grupo, registro, campo, entrada_field, salida_field, tiempo_field, estado_text):
        valor = entrada_field.value if campo == "hora_entrada" else salida_field.value
        registro[campo] = valor
        self.actualizar_callback(grupo, campo, valor)
        self._soft_update()

    def _crear_botones_descanso(self, grupo, registro, tiempo_field, estado_text, entrada_field=None, salida_field=None):
        opciones = ["SN", "MD", "CMP"]
        botones = []

        def seleccionar(opcion):
            registro["descanso"] = opcion
            self.actualizar_callback(grupo, "descanso", opcion)

            res = self.calculo_helper.recalcular_con_estado(
                entrada_field.value if entrada_field else registro.get("hora_entrada", ""),
                salida_field.value if salida_field else registro.get("hora_salida", ""),
                opcion
            )
            tiempo_field.value = res.get("tiempo_trabajo_con_descanso", "00:00:00")
            registro["tiempo_trabajo"] = res.get("tiempo_trabajo", "00:00:00")
            registro["tiempo_trabajo_con_descanso"] = tiempo_field.value

            nuevo_estado = "COMPLETO" if res.get("estado") == "ok" else "INCOMPLETO"
            registro["estado"] = nuevo_estado
            estado_text.value = nuevo_estado
            estado_text.color = ft.colors.GREEN if nuevo_estado == "COMPLETO" else ft.colors.RED

            for btn in botones:
                is_on = btn.data == opcion
                btn.bgcolor = ft.colors.BLUE if is_on else ft.colors.WHITE
                btn.content.color = ft.colors.WHITE if is_on else ft.colors.BLACK

            self._soft_update()

        for tipo in opciones:
            is_on = registro.get("descanso") == tipo
            btn = ft.Container(
                content=ft.Text(tipo, size=12, color=ft.colors.WHITE if is_on else ft.colors.BLACK),
                bgcolor=ft.colors.BLUE if is_on else ft.colors.WHITE,
                border=ft.border.all(1, ft.colors.GREY_400),
                border_radius=5,
                alignment=ft.alignment.center,
                height=30,
                expand=True,
                data=tipo,
                on_click=lambda e, t=tipo: seleccionar(t)
            )
            botones.append(btn)

        return ft.Container(
            content=ft.Row(controls=botones, spacing=3, alignment=ft.MainAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            width=180
        )

    def build_fila_agregar_por_id(
        self,
        grupo_importacion: str,
        registro: dict,
        on_save: Callable,
        on_cancel: Callable,
        registros_del_grupo: list,
        resolver_nombre: Callable[[int], str],
    ) -> ft.DataRow:
        import re
        from datetime import datetime

        # Defaults / flags
        registro.setdefault("descanso", "MD")
        registro.setdefault("estado", "PENDIENTE")
        registro.setdefault("__duplicado", False)
        registro.setdefault("__horas_invalidas", True)

        estado_text = ft.Text(
            (registro.get("estado") or "PENDIENTE").upper(),
            size=12,
            text_align=ft.TextAlign.CENTER,
            color=ft.colors.GREY,
            no_wrap=True,
            max_lines=1,
        )

        tiempo_field = ft.TextField(
            value=registro.get("tiempo_trabajo_con_descanso", "00:00:00"),
            width=100,
            read_only=True,
            text_align=ft.TextAlign.CENTER,
            border=ft.InputBorder.OUTLINE,           # ✅ bordes oscuros visibles
            border_color=ft.colors.GREY_700,
            content_padding=ft.padding.symmetric(6, 6),
            height=34,
        )

        # ------- validaciones "suaves" (no molestan mientras escribes) -------
        def _is_fecha_completa(v: str) -> bool:
            if not v:
                return False
            s = v.strip()
            m = re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})', s)
            if m:
                d, mth, y = map(int, m.groups())
                try:
                    datetime(year=y, month=mth, day=d)
                    return True
                except ValueError:
                    return False
            m = re.fullmatch(r'(\d{4})-(\d{1,2})-(\d{1,2})', s)
            if m:
                y, mth, d = map(int, m.groups())
                try:
                    datetime(year=y, month=mth, day=d)
                    return True
                except ValueError:
                    return False
            return False

        def _is_hora_completa(v: str) -> bool:
            if not v:
                return False
            s = v.strip()
            m = re.fullmatch(r'(\d{1,2}):(\d{2})(?::(\d{2}))?$', s)
            if not m:
                return False
            try:
                h = int(m.group(1)); mi = int(m.group(2))
                se = int(m.group(3)) if m.group(3) else 0
                return 0 <= h <= 23 and 0 <= mi <= 59 and 0 <= se <= 59
            except Exception:
                return False

        # ------- horas (colorea solo cuando ambas están completas) -------
        def _validar_y_pintar_horas():
            e_ok = _is_hora_completa(entrada_field.value or "")
            s_ok = _is_hora_completa(salida_field.value or "")

            if e_ok and s_ok:
                res = self.calculo_helper.recalcular_con_estado(
                    entrada_field.value, salida_field.value, registro.get("descanso", "MD")
                )
                tiempo_field.value = res.get("tiempo_trabajo_con_descanso", "00:00:00")
                registro["tiempo_trabajo"] = res.get("tiempo_trabajo", "00:00:00")
                registro["tiempo_trabajo_con_descanso"] = tiempo_field.value

                if res.get("estado") == "ok":
                    registro["__horas_invalidas"] = False
                    registro["estado"] = "COMPLETO"
                    # Solo cambiamos estado si no está marcado como DUPLICADO
                    if estado_text.value != "DUPLICADO":
                        estado_text.value = "COMPLETO"
                        estado_text.color = ft.colors.GREEN
                        estado_text.tooltip = None
                    self._clear_field_error(entrada_field)
                    self._clear_field_error(salida_field)
                else:
                    registro["__horas_invalidas"] = True
                    registro["estado"] = "INCOMPLETO"
                    if estado_text.value != "DUPLICADO":  # no pisar DUPLICADO
                        estado_text.value = "HORAS INVÁLIDAS"
                        estado_text.color = ft.colors.RED
                        estado_text.tooltip = res.get("mensaje") or "Formato HH:MM y salida > entrada."
                    self._set_field_error(entrada_field, estado_text.tooltip)
                    self._set_field_error(salida_field, estado_text.tooltip)
            else:
                # Aún escribiendo → no marcar error
                registro["__horas_invalidas"] = True
                if estado_text.value not in ("DUPLICADO",):
                    estado_text.value = "PENDIENTE"
                    estado_text.color = ft.colors.GREY
                    estado_text.tooltip = None
                self._clear_field_error(entrada_field)
                self._clear_field_error(salida_field)

            if "__btn_save" in registro and isinstance(registro["__btn_save"], ft.IconButton):
                self._update_save_btn_state(registro, registro["__btn_save"])
            self._soft_update()

        # ------- campos -------
        common_tf = dict(
            text_align=ft.TextAlign.CENTER,
            border=ft.InputBorder.OUTLINE,           # ✅ bordes oscuros
            border_color=ft.colors.GREY_700,
            content_padding=ft.padding.symmetric(6, 6),
            height=34,
        )

        entrada_field = ft.TextField(
            width=100,
            value=self.calculo_helper.sanitizar_hora(registro.get("hora_entrada", "")),
            keyboard_type=ft.KeyboardType.DATETIME,
            on_change=lambda e: _validar_y_pintar_horas(),
            on_blur=lambda e: self._on_blur_hora(
                grupo_importacion, registro, "hora_entrada",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
            **common_tf,
        )
        salida_field = ft.TextField(
            width=100,
            value=self.calculo_helper.sanitizar_hora(registro.get("hora_salida", "")),
            keyboard_type=ft.KeyboardType.DATETIME,
            on_change=lambda e: _validar_y_pintar_horas(),
            on_blur=lambda e: self._on_blur_hora(
                grupo_importacion, registro, "hora_salida",
                entrada_field, salida_field, tiempo_field, estado_text
            ),
            **common_tf,
        )

        # Nombre (no editable)
        nombre_text = ft.Text(
            (registro.get("nombre_completo") or "—"),
            overflow=ft.TextOverflow.ELLIPSIS,
            max_lines=1,
            text_align=ft.TextAlign.LEFT,
            size=12,
        )

        # Resolver nombre en vivo al tipear nómina
        def _resolver_nombre_en_vivo():
            val = (numero_field.value or "").strip()
            nombre = ""
            try:
                if val.isdigit():
                    nombre = resolver_nombre(int(val)) or ""
            except Exception:
                nombre = ""
            registro["nombre_completo"] = nombre
            nombre_text.value = nombre if nombre else "—"
            self._soft_update()

        # Duplicado: recolorea y limpia cuando cambia a válido
        def _validar_duplicado_en_vivo():
            num_ok = (numero_field.value or "").strip().isdigit()
            fec_ok = _is_fecha_completa(fecha_field.value or "")
            if num_ok and fec_ok:
                self.validar_duplicado_y_colorear(
                    registros_del_grupo, registro, numero_field, fecha_field, estado_text
                )
            else:
                registro["__duplicado"] = False
                self._clear_field_error(numero_field)
                self._clear_field_error(fecha_field)
                if estado_text.value == "DUPLICADO":
                    estado_text.value = "PENDIENTE" if registro.get("__horas_invalidas", True) else "COMPLETO"
                    estado_text.color = ft.colors.GREY if registro.get("__horas_invalidas", True) else ft.colors.GREEN
                    estado_text.tooltip = None

            if "__btn_save" in registro and isinstance(registro["__btn_save"], ft.IconButton):
                self._update_save_btn_state(registro, registro["__btn_save"])
            self._soft_update()

        def _on_numero_change(e):
            registro["numero_nomina"] = e.control.value
            self.actualizar_callback(grupo_importacion, "numero_nomina", e.control.value)
            _resolver_nombre_en_vivo()
            _validar_duplicado_en_vivo()

        def _on_fecha_change(e):
            registro["fecha"] = e.control.value
            self.actualizar_callback(grupo_importacion, "fecha", e.control.value)
            _validar_duplicado_en_vivo()

        numero_field = ft.TextField(
            width=60,
            value=str(registro.get("numero_nomina", "")),
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=_on_numero_change,
            on_blur=lambda e: (
                self.calculo_helper.validar_fecha_y_numero(registro, registros_del_grupo, numero_field, fecha_field),
                _validar_duplicado_en_vivo()
            ),
            **common_tf,
        )

        fecha_field = ft.TextField(
            width=150,
            value=str(registro.get("fecha", "")),
            on_change=_on_fecha_change,
            on_blur=lambda e: (
                self.calculo_helper.validar_fecha_y_numero(registro, registros_del_grupo, numero_field, fecha_field),
                _validar_duplicado_en_vivo()
            ),
            **common_tf,
        )

        descanso_widget = self._crear_botones_descanso(
            grupo_importacion, registro, tiempo_field, estado_text, entrada_field, salida_field
        )

        # Botones
        save_btn = ft.IconButton(icon=ft.icons.SAVE, tooltip="Guardar")
        cancel_btn = ft.IconButton(icon=ft.icons.CANCEL, tooltip="Cancelar", on_click=lambda e: on_cancel())
        registro["__btn_save"] = save_btn

        def _intentar_guardar(_e):
            self._update_save_btn_state(registro, save_btn)
            if save_btn.disabled:
                motivo = None
                if registro.get("__duplicado", False):
                    motivo = "Este número de nómina ya existe para la fecha indicada."
                elif registro.get("__horas_invalidas", True):
                    motivo = "Las horas son inválidas. Verifica formato y que la salida sea mayor a la entrada."
                else:
                    motivo = "Completa los campos requeridos."
                from app.views.containers.modal_alert import ModalAlert
                ModalAlert(title_text="No se puede guardar", message=f"❌ {motivo}").mostrar()
                return
            on_save()

        save_btn.on_click = _intentar_guardar
        self._update_save_btn_state(registro, save_btn)

        acciones = ft.Row([save_btn, cancel_btn], spacing=5)

        # Validación inicial (no marca error hasta estar completas)
        _validar_y_pintar_horas()

        return ft.DataRow(
            cells=[
                ft.DataCell(self._wrap_cell(numero_field, 60)),
                ft.DataCell(self._wrap_cell(nombre_text, 260)),
                ft.DataCell(self._wrap_cell(fecha_field, 150)),
                ft.DataCell(self._wrap_cell(entrada_field, 120)),
                ft.DataCell(self._wrap_cell(salida_field, 120)),
                ft.DataCell(self._wrap_cell(descanso_widget, 140)),
                ft.DataCell(self._wrap_cell(tiempo_field, 160)),
                ft.DataCell(self._wrap_cell(estado_text, 220)),
                ft.DataCell(self._wrap_cell(acciones, 100)),
            ]
        )

    def validar_duplicado_y_colorear(
        self,
        registros_del_grupo: list,
        registro: dict,
        numero_field: ft.TextField,
        fecha_field: ft.TextField,
        estado_text: ft.Text,
    ) -> bool:
        """Colorea rojo si hay duplicado y limpia cuando deja de serlo."""
        num = (numero_field.value or "").strip()
        fecha = (fecha_field.value or "").strip()
        duplicado = False

        # Normaliza fecha a YYYY-MM-DD para comparar
        fecha_norm = fecha
        try:
            if "/" in fecha and len(fecha.split("/")) == 3:
                dt = self.calculo_helper.parse_fecha_ddmmyyyy(fecha)
                fecha_norm = dt.strftime("%Y-%m-%d")
        except Exception:
            pass

        if num.isdigit() and fecha_norm:
            duplicado = any(
                str(r.get("numero_nomina")) == num and str(r.get("fecha")) == fecha_norm
                for r in registros_del_grupo
            )

        registro["__duplicado"] = duplicado

        if duplicado:
            self._set_field_error(numero_field, "ID duplicado en la fecha")
            self._set_field_error(fecha_field, "ID duplicado en la fecha")
            estado_text.value = "DUPLICADO"
            estado_text.color = ft.colors.RED_600
            estado_text.tooltip = "Este número ya existe para esa fecha."
        else:
            # 🔄 limpiar coloreado y tooltip cuando deja de ser duplicado
            self._clear_field_error(numero_field)
            self._clear_field_error(fecha_field)
            if estado_text.value == "DUPLICADO":
                # Volver a estado coherente con las horas actuales
                if registro.get("__horas_invalidas", True):
                    estado_text.value = "PENDIENTE"
                    estado_text.color = ft.colors.GREY
                else:
                    estado_text.value = "COMPLETO"
                    estado_text.color = ft.colors.GREEN
                estado_text.tooltip = None

        # Actualiza botón guardar si está disponible
        if "__btn_save" in registro and isinstance(registro["__btn_save"], ft.IconButton):
            self._update_save_btn_state(registro, registro["__btn_save"])

        self._soft_update()
        return duplicado

    # Solo color + tooltip (sin tocar bordes)
    def _set_field_error(self, tf: ft.TextField, msg: str | None = None):
        tf.color = ft.colors.RED_400
        tf.tooltip = msg or "Dato inválido"

    def _clear_field_error(self, tf: ft.TextField):
        tf.color = None
        tf.tooltip = None

    def _update_save_btn_state(self, registro: dict, save_btn: ft.IconButton):
        ok = True
        if not str(registro.get("numero_nomina", "")).strip().isdigit():
            ok = False
        if not str(registro.get("fecha", "")).strip():
            ok = False
        if registro.get("__duplicado", False):
            ok = False
        if registro.get("__horas_invalidas", True):
            ok = False
        save_btn.disabled = not ok
