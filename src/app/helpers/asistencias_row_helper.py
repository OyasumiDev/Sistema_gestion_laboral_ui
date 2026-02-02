import flet as ft
from typing import Callable, Dict, Optional, Any
from datetime import datetime
import re

from app.helpers.calculo_horas_helper import CalculoHorasHelper
from app.core.app_state import AppState


class AsistenciasRowHelper:
    """
    Objetivo del módulo:
    - Orden de celdas fijo (NO negociable) para que siempre cuadre con el DataTable:
      [numero_nomina, nombre_completo, fecha, hora_entrada, hora_salida, descanso, tiempo_trabajo, estado, acciones]
    - Descanso default = MD (cuando venga vacío)
    - ✅ Horas trabajadas: mostrar NETO (tiempo_trabajo) por default; bruto queda como respaldo
    - ✅ Validación suave al escribir; fuerte en blur/guardar
    - ✅ Autosave descanso: intenta re-leer snapshot desde DB vía commit_descanso_callback
    """

    _W = {
        "numero_nomina": 100,
        "nombre_completo": 260,
        "fecha": 150,
        "hora_entrada": 120,
        "hora_salida": 120,
        "descanso": 140,
        "tiempo_trabajo": 160,
        "estado": 220,
        "acciones": 100,
    }

    def __init__(
        self,
        recalcular_callback: Callable,
        actualizar_callback: Callable,
        commit_descanso_callback: Optional[Callable[[Dict], Any]] = None,
    ):
        """
        commit_descanso_callback (opcional):
          - Si lo pasas desde el Container, aquí lo llamamos al cambiar descanso para persistir inmediato.
          - Ideal: que RETORNE la fila actualizada (dict) o {"data": dict} tras tocar DB.
        """
        self.recalcular_callback = recalcular_callback
        self.actualizar_callback = actualizar_callback
        self.commit_descanso_callback = commit_descanso_callback

        self.calculo_helper = CalculoHorasHelper()
        self.page = AppState().page

        # Debounce de update para no matar rendimiento
        self._last_update_ts = 0.0
        self._update_min_interval = 0.05  # 50ms

    # ------------------ util UI ------------------
    def _wrap_cell(self, control: ft.Control, width: int, align_center: bool = True) -> ft.Container:
        return ft.Container(
            content=control,
            width=width,
            alignment=ft.alignment.center if align_center else ft.alignment.center_left,
            padding=ft.padding.symmetric(horizontal=2),
        )

    def _soft_update(self, force: bool = False):
        if not self.page:
            return
        now = datetime.now().timestamp()
        if force or (now - self._last_update_ts) >= self._update_min_interval:
            self._last_update_ts = now
            try:
                self.page.update()
            except Exception:
                pass

    # ------------------ callbacks blindados ------------------
    def _call_actualizar(self, grupo: Optional[str], campo: str, valor: Any):
        cb = self.actualizar_callback
        if not callable(cb):
            return

        # 1) kwargs
        try:
            cb(grupo=grupo, campo=campo, valor=valor)
            return
        except Exception:
            pass

        # 2) 3 args
        try:
            cb(grupo, campo, valor)
            return
        except Exception:
            pass

        # 3) 2 args
        try:
            cb(campo, valor)
        except Exception:
            pass

    def _call_recalcular(self, grupo: Optional[str] = None, registro: Optional[dict] = None):
        cb = self.recalcular_callback
        if not callable(cb):
            return

        try:
            cb(grupo=grupo, registro=registro)
            return
        except Exception:
            pass

        try:
            cb(grupo, registro)
            return
        except Exception:
            pass

        try:
            cb(registro)
            return
        except Exception:
            pass

        try:
            cb()
        except Exception:
            pass

    # ------------------ normalización ------------------
    def _default_descanso(self, registro: dict) -> str:
        """
        Default del módulo: MD.
        - None / "" / "NULL" -> MD
        - "SN"/"MD"/"CMP" -> respeta
        - 0/1/2 -> etiqueta
        """
        v = registro.get("descanso", None)
        if v is None:
            return "MD"
        s = str(v).strip().upper()
        if s in ("", "NONE", "NULL"):
            return "MD"
        if s in ("SN", "MD", "CMP"):
            return s
        if s in ("0", "1", "2"):
            return {"0": "SN", "1": "MD", "2": "CMP"}[s]
        return "MD"

    def _solo_horas(self, v: Any) -> str:
        """
        En la columna de horas SOLO mostrar HH:MM[:SS].
        Si viene 'MD 00:00:00' o 'SN 09:59:00', lo limpia.
        """
        s = str(v or "").strip()
        if not s:
            return ""
        parts = s.split()
        if len(parts) >= 2 and parts[0].upper() in ("SN", "MD", "CMP"):
            return parts[1].strip()
        return s

    def _estado_color(self, estado: str) -> str:
        e = (estado or "").strip().upper()
        if e == "INCOMPLETO" or e.startswith("HORAS"):
            return ft.colors.RED
        if e == "COMPLETO":
            return ft.colors.GREEN
        if e == "DUPLICADO":
            return ft.colors.RED_600
        if e == "PENDIENTE":
            return ft.colors.GREY
        return ft.colors.GREY

    def _set_field_error(self, tf: ft.TextField, msg: str | None = None):
        tf.color = ft.colors.RED_400
        tf.tooltip = msg or "Dato inválido"

    def _clear_field_error(self, tf: ft.TextField):
        tf.color = None
        tf.tooltip = None

    def _set_border_error(self, tf: ft.TextField, msg: str | None = None):
        tf.border_color = ft.colors.RED
        tf.tooltip = msg or "Dato inválido"

    def _clear_border_error(self, tf: ft.TextField):
        tf.border_color = None
        tf.tooltip = None

    def _is_hora_completa(self, v: str) -> bool:
        if not v:
            return False
        s = v.strip()
        m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?$", s)
        if not m:
            return False
        try:
            h = int(m.group(1))
            mi = int(m.group(2))
            se = int(m.group(3)) if m.group(3) else 0
            return 0 <= h <= 23 and 0 <= mi <= 59 and 0 <= se <= 59
        except Exception:
            return False

    def _norm_fecha(self, fecha: str) -> str:
        """
        Normaliza fecha a 'YYYY-MM-DD' si es posible.
        Soporta 'DD/MM/YYYY' y 'YYYY-MM-DD'.
        """
        s = (fecha or "").strip()
        if not s:
            return ""
        try:
            if "/" in s:
                dt = self.calculo_helper.parse_fecha_ddmmyyyy(s)
                return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
        return s

    # ------------------ DB snapshot merge ------------------
    def _merge_snapshot(self, registro: dict, snapshot: dict) -> None:
        """
        Mezcla snapshot de DB dentro de registro, normalizando descanso a etiqueta.
        """
        if not isinstance(snapshot, dict):
            return

        # Merge crudo
        for k, v in snapshot.items():
            registro[k] = v

        # Normaliza descanso a SN/MD/CMP para la UI
        registro["descanso"] = self._default_descanso(registro)

        # Normaliza horas mostrables
        if "tiempo_trabajo" in registro:
            registro["tiempo_trabajo"] = self._solo_horas(registro.get("tiempo_trabajo"))
        if "tiempo_trabajo_con_descanso" in registro:
            registro["tiempo_trabajo_con_descanso"] = self._solo_horas(registro.get("tiempo_trabajo_con_descanso"))

        # Normaliza estado
        if "estado" in registro and registro["estado"] is not None:
            registro["estado"] = str(registro["estado"]).strip().upper()

    def _extract_snapshot(self, ret: Any) -> Optional[dict]:
        """
        Acepta retornos comunes:
        - dict fila directa
        - {"data": {...}}
        - {"status":"success","data": {...}}
        """
        if isinstance(ret, dict):
            if "data" in ret and isinstance(ret["data"], dict):
                return ret["data"]
            # Si parece fila
            if any(k in ret for k in ("numero_nomina", "fecha", "hora_entrada", "hora_salida", "tiempo_trabajo", "descanso")):
                return ret
        return None

    def _call_commit_descanso_and_refresh(
        self,
        grupo: Optional[str],
        registro: dict,
        tiempo_field: Optional[ft.TextField],
        estado_text: Optional[ft.Text],
    ):
        """
        Llama commit_descanso_callback y, si regresa snapshot, lo aplica y repinta.
        """
        cb = self.commit_descanso_callback
        if not callable(cb):
            return

        # payload minimal (por si tu container prefiere eso)
        payload = {
            "numero_nomina": registro.get("numero_nomina"),
            "fecha": registro.get("fecha"),
            "descanso": registro.get("descanso"),
            "grupo_importacion": registro.get("grupo_importacion"),
        }

        ret = None

        # 1) intento clásico: cb(registro)
        try:
            ret = cb(registro)
        except Exception:
            # 2) kwargs
            try:
                ret = cb(grupo=grupo, registro=registro, payload=payload)
            except Exception:
                # 3) payload
                try:
                    ret = cb(payload)
                except Exception:
                    ret = None

        snap = self._extract_snapshot(ret)
        if not snap:
            return

        # aplica snapshot DB
        self._merge_snapshot(registro, snap)

        # repinta descanso/estado/tiempo desde DB
        if tiempo_field is not None:
            # ✅ la columna debe mostrar NETO
            tiempo_field.value = self._solo_horas(registro.get("tiempo_trabajo") or "00:00:00")

        if estado_text is not None:
            est = (registro.get("estado") or "PENDIENTE").strip().upper()
            if estado_text.value != "DUPLICADO":
                estado_text.value = est
                estado_text.color = self._estado_color(est)

        self._soft_update(force=True)

    def _apply_recalc_result(self, registro: dict, tiempo_field: ft.TextField, estado_text: ft.Text, res: dict):
        """
        Aplica resultado de recalculo.
        ✅ IMPORTANTE: el campo mostrado en la columna debe ser NETO (tiempo_trabajo),
           porque eso es lo que cambia con descanso.
        """
        manual_activo = bool(registro.get("__tiempo_manual"))
        if not manual_activo:
            neto = self._solo_horas(res.get("tiempo_trabajo", "00:00:00"))
            bruto = self._solo_horas(res.get("tiempo_trabajo_con_descanso", "00:00:00"))

            # ✅ Mostrar NETO en el TextField/columna
            tiempo_field.value = neto

            # Guardamos ambos en registro por si luego quieres mostrar ambos
            registro["tiempo_trabajo"] = neto
            registro["tiempo_trabajo_con_descanso"] = bruto

        nuevo_estado = "COMPLETO" if res.get("estado") == "ok" else "INCOMPLETO"
        registro["estado"] = nuevo_estado
        if estado_text.value != "DUPLICADO":
            estado_text.value = nuevo_estado
            estado_text.color = self._estado_color(nuevo_estado)

    # ------------------ FILA VISTA ------------------
    def build_fila_vista(self, registro: dict, on_edit: Callable, on_delete: Callable = None) -> ft.DataRow:
        numero_nomina = registro.get("numero_nomina", "")
        fecha = registro.get("fecha", "")

        descanso = self._default_descanso(registro)
        registro["descanso"] = descanso
        descanso_texto = f"{descanso}: {self.calculo_helper.obtener_minutos_descanso(descanso)} min"

        # ✅ Horas trabajadas (NETO) primero. Si no hay, usa bruto. Si no hay, recalcula.
        tiempo_mostrar = self._solo_horas(str(registro.get("tiempo_trabajo") or "").strip())
        if not tiempo_mostrar:
            tiempo_mostrar = self._solo_horas(str(registro.get("tiempo_trabajo_con_descanso") or "").strip())

        if not tiempo_mostrar:
            res = self.calculo_helper.recalcular_con_estado(
                self.calculo_helper.sanitizar_hora(registro.get("hora_entrada", "")),
                self.calculo_helper.sanitizar_hora(registro.get("hora_salida", "")),
                descanso,
            )
            tiempo_mostrar = self._solo_horas(res.get("tiempo_trabajo", "00:00:00"))

        estado_val = (registro.get("estado") or "").strip().upper() or "PENDIENTE"
        estado_text = ft.Text(
            estado_val,
            text_align=ft.TextAlign.CENTER,
            color=self._estado_color(estado_val),
            no_wrap=True,
            max_lines=1,
        )
        tiempo_text = ft.Text(str(tiempo_mostrar))
        # referencias para refresco puntual sin reconstruir filas
        registro["__tiempo_text"] = tiempo_text
        registro["__estado_text"] = estado_text

        acciones = [
            ft.IconButton(icon=ft.icons.EDIT, tooltip="Editar", on_click=lambda e: on_edit(numero_nomina, fecha))
        ]
        if on_delete:
            acciones.append(
                ft.IconButton(
                    icon=ft.icons.DELETE_OUTLINE,
                    tooltip="Eliminar",
                    icon_color=ft.colors.RED_600,
                    on_click=lambda e: on_delete(registro),
                )
            )

        return ft.DataRow(
            cells=[
                ft.DataCell(self._wrap_cell(ft.Text(str(numero_nomina)), self._W["numero_nomina"])),
                ft.DataCell(
                    self._wrap_cell(
                        ft.Text(
                            registro.get("nombre_completo", ""),
                            overflow=ft.TextOverflow.ELLIPSIS,
                            max_lines=1,
                            text_align=ft.TextAlign.LEFT,
                        ),
                        self._W["nombre_completo"],
                        align_center=False,
                    )
                ),
                ft.DataCell(self._wrap_cell(ft.Text(str(fecha)), self._W["fecha"])),
                ft.DataCell(self._wrap_cell(ft.Text(str(registro.get("hora_entrada", ""))), self._W["hora_entrada"])),
                ft.DataCell(self._wrap_cell(ft.Text(str(registro.get("hora_salida", ""))), self._W["hora_salida"])),
                ft.DataCell(self._wrap_cell(ft.Text(descanso_texto), self._W["descanso"])),
                ft.DataCell(self._wrap_cell(tiempo_text, self._W["tiempo_trabajo"])),
                ft.DataCell(self._wrap_cell(estado_text, self._W["estado"])),
                ft.DataCell(self._wrap_cell(ft.Row(acciones, spacing=5), self._W["acciones"])),
            ]
        )

    # ------------------ FILA EDICIÓN ------------------
    def build_fila_edicion(self, registro: Dict, on_save: Callable, on_cancel: Callable) -> ft.DataRow:
        numero_nomina = registro.get("numero_nomina", "")
        fecha = registro.get("fecha", "")
        grupo = registro.get("grupo_importacion", "")

        registro.setdefault("__tiempo_manual", False)
        registro["descanso"] = self._default_descanso(registro)

        estado_val = (registro.get("estado") or "").strip().upper() or "PENDIENTE"
        estado_text = ft.Text(
            estado_val,
            size=12,
            text_align=ft.TextAlign.CENTER,
            color=self._estado_color(estado_val),
            no_wrap=True,
            max_lines=1,
        )

        # ✅ Mostrar NETO por default en edición
        tiempo_field = ft.TextField(
            value=self._solo_horas(
                registro.get("tiempo_trabajo") or registro.get("tiempo_trabajo_con_descanso") or "00:00:00"
            ),
            width=self._W["tiempo_trabajo"],
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.DATETIME,
            hint_text="HH:MM[:SS] o decimal",
        )
        tiempo_field.on_change = lambda e: self._on_change_tiempo_manual(grupo, registro, tiempo_field)

        entrada_field = ft.TextField(
            value=self.calculo_helper.sanitizar_hora(registro.get("hora_entrada", "")),
            width=self._W["hora_entrada"],
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.DATETIME,
        )
        salida_field = ft.TextField(
            value=self.calculo_helper.sanitizar_hora(registro.get("hora_salida", "")),
            width=self._W["hora_salida"],
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.DATETIME,
        )

        entrada_field.on_change = lambda e: self._on_change_hora(
            grupo, registro, "hora_entrada", entrada_field, salida_field, tiempo_field, estado_text
        )
        salida_field.on_change = lambda e: self._on_change_hora(
            grupo, registro, "hora_salida", entrada_field, salida_field, tiempo_field, estado_text
        )

        entrada_field.on_blur = lambda e: self._on_blur_hora(
            grupo, registro, "hora_entrada", entrada_field, salida_field, tiempo_field, estado_text
        )
        salida_field.on_blur = lambda e: self._on_blur_hora(
            grupo, registro, "hora_salida", entrada_field, salida_field, tiempo_field, estado_text
        )

        descanso_sel = self._default_descanso(registro)
        registro["descanso"] = descanso_sel
        descanso_widget = ft.Text(descanso_sel)

        acciones = ft.Row(
            [
                ft.IconButton(icon=ft.icons.SAVE, tooltip="Guardar edición", on_click=lambda e: on_save()),
                ft.IconButton(icon=ft.icons.CANCEL, tooltip="Cancelar", on_click=lambda e: on_cancel()),
            ],
            spacing=5,
        )

        return ft.DataRow(
            cells=[
                ft.DataCell(self._wrap_cell(ft.Text(str(numero_nomina)), self._W["numero_nomina"])),
                ft.DataCell(
                    self._wrap_cell(
                        ft.Text(
                            registro.get("nombre_completo", ""),
                            overflow=ft.TextOverflow.ELLIPSIS,
                            max_lines=1,
                            text_align=ft.TextAlign.LEFT,
                        ),
                        self._W["nombre_completo"],
                        align_center=False,
                    )
                ),
                ft.DataCell(self._wrap_cell(ft.Text(str(fecha)), self._W["fecha"])),
                ft.DataCell(self._wrap_cell(entrada_field, self._W["hora_entrada"])),
                ft.DataCell(self._wrap_cell(salida_field, self._W["hora_salida"])),
                ft.DataCell(self._wrap_cell(descanso_widget, self._W["descanso"])),
                ft.DataCell(self._wrap_cell(tiempo_field, self._W["tiempo_trabajo"])),
                ft.DataCell(self._wrap_cell(estado_text, self._W["estado"])),
                ft.DataCell(self._wrap_cell(acciones, self._W["acciones"])),
            ]
        )

    # ------------------ FILA NUEVA ------------------
    def build_fila_nueva(
        self,
        grupo_importacion: str,
        registro: Dict,
        on_save: Callable,
        on_cancel: Callable,
        registros_del_grupo: list,
    ) -> ft.DataRow:
        registro["descanso"] = self._default_descanso(registro)
        registro.setdefault("estado", "PENDIENTE")
        registro.setdefault("__duplicado", False)
        registro.setdefault("__horas_invalidas", True)

        estado_text = ft.Text(
            (registro.get("estado") or "PENDIENTE").upper(),
            size=12,
            text_align=ft.TextAlign.CENTER,
            color=self._estado_color(registro.get("estado")),
            no_wrap=True,
            max_lines=1,
        )

        # ✅ NETO por default en nueva fila también (aunque sea read-only)
        tiempo_field = ft.TextField(
            value=self._solo_horas(
                str(registro.get("tiempo_trabajo") or registro.get("tiempo_trabajo_con_descanso") or "00:00:00")
            ),
            width=self._W["tiempo_trabajo"],
            read_only=True,
            text_align=ft.TextAlign.CENTER,
        )

        common_tf = dict(
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.DATETIME,
        )

        salida_field = ft.TextField(
            width=self._W["hora_salida"],
            value=self.calculo_helper.sanitizar_hora(registro.get("hora_salida", "")),
            **common_tf,
        )
        entrada_field = ft.TextField(
            width=self._W["hora_entrada"],
            value=self.calculo_helper.sanitizar_hora(registro.get("hora_entrada", "")),
            **common_tf,
        )

        entrada_field.on_change = lambda e: self._on_change_hora(
            grupo_importacion, registro, "hora_entrada", entrada_field, salida_field, tiempo_field, estado_text
        )
        salida_field.on_change = lambda e: self._on_change_hora(
            grupo_importacion, registro, "hora_salida", entrada_field, salida_field, tiempo_field, estado_text
        )

        entrada_field.on_blur = lambda e: self._on_blur_hora(
            grupo_importacion, registro, "hora_entrada", entrada_field, salida_field, tiempo_field, estado_text
        )
        salida_field.on_blur = lambda e: self._on_blur_hora(
            grupo_importacion, registro, "hora_salida", entrada_field, salida_field, tiempo_field, estado_text
        )

        numero_field = ft.TextField(
            width=self._W["numero_nomina"],
            value=str(registro.get("numero_nomina", "")),
            keyboard_type=ft.KeyboardType.NUMBER,
            text_align=ft.TextAlign.CENTER,
        )
        fecha_field = ft.TextField(
            width=self._W["fecha"],
            value=str(registro.get("fecha", "")),
            text_align=ft.TextAlign.CENTER,
        )

        def _revalidar_duplicado():
            try:
                self.validar_duplicado_y_colorear(registros_del_grupo, registro, numero_field, fecha_field, estado_text)
            except Exception:
                pass

        def on_numero_blur(e):
            registro["numero_nomina"] = e.control.value
            self._call_actualizar(grupo_importacion, "numero_nomina", e.control.value)
            _revalidar_duplicado()
            try:
                self.calculo_helper.validar_fecha_y_numero(registro, registros_del_grupo, numero_field, fecha_field)
            except Exception:
                pass
            self._soft_update(force=True)

        def on_fecha_blur(e):
            registro["fecha"] = e.control.value
            self._call_actualizar(grupo_importacion, "fecha", e.control.value)
            _revalidar_duplicado()
            try:
                self.calculo_helper.validar_fecha_y_numero(registro, registros_del_grupo, numero_field, fecha_field)
            except Exception:
                pass
            self._soft_update(force=True)

        numero_field.on_blur = on_numero_blur
        fecha_field.on_blur = on_fecha_blur

        descanso_widget = self._crear_botones_descanso(
            grupo_importacion, registro, tiempo_field, estado_text, entrada_field, salida_field
        )

        acciones = ft.Row(
            [
                ft.IconButton(icon=ft.icons.SAVE, tooltip="Guardar", on_click=lambda e: on_save()),
                ft.IconButton(icon=ft.icons.CANCEL, tooltip="Cancelar", on_click=lambda e: on_cancel()),
            ],
            spacing=5,
        )

        return ft.DataRow(
            cells=[
                ft.DataCell(self._wrap_cell(numero_field, self._W["numero_nomina"])),
                ft.DataCell(self._wrap_cell(ft.Text("—"), self._W["nombre_completo"], align_center=False)),
                ft.DataCell(self._wrap_cell(fecha_field, self._W["fecha"])),
                ft.DataCell(self._wrap_cell(entrada_field, self._W["hora_entrada"])),
                ft.DataCell(self._wrap_cell(salida_field, self._W["hora_salida"])),
                ft.DataCell(self._wrap_cell(descanso_widget, self._W["descanso"])),
                ft.DataCell(self._wrap_cell(tiempo_field, self._W["tiempo_trabajo"])),
                ft.DataCell(self._wrap_cell(estado_text, self._W["estado"])),
                ft.DataCell(self._wrap_cell(acciones, self._W["acciones"])),
            ]
        )

    # ------------------ HANDLERS ------------------
    def _on_change_hora(self, grupo, registro, campo, entrada_field, salida_field, tiempo_field, estado_text):
        valor = entrada_field.value if campo == "hora_entrada" else salida_field.value
        registro[campo] = valor
        self._call_actualizar(grupo, campo, valor)

        ent_ok = self._is_hora_completa((entrada_field.value or "").strip())
        sal_ok = self._is_hora_completa((salida_field.value or "").strip())

        if not (ent_ok and sal_ok):
            registro["__horas_invalidas"] = True
            if estado_text.value not in ("DUPLICADO",):
                estado_text.value = "PENDIENTE"
                estado_text.color = self._estado_color("PENDIENTE")
            self._soft_update()
            return

        self._clear_border_error(entrada_field)
        self._clear_border_error(salida_field)

        res = self.calculo_helper.recalcular_con_estado(
            entrada_field.value, salida_field.value, registro.get("descanso", "MD")
        )

        self._apply_recalc_result(registro, tiempo_field, estado_text, res)
        registro["__horas_invalidas"] = (res.get("estado") != "ok")

        self._call_recalcular(grupo=grupo, registro=registro)
        self._soft_update()

    def _on_blur_hora(self, grupo, registro, campo, entrada_field, salida_field, tiempo_field, estado_text):
        valor = entrada_field.value if campo == "hora_entrada" else salida_field.value
        registro[campo] = valor
        self._call_actualizar(grupo, campo, valor)

        ent_ok = self._is_hora_completa((entrada_field.value or "").strip())
        sal_ok = self._is_hora_completa((salida_field.value or "").strip())

        if not ent_ok:
            self._set_border_error(entrada_field, "Hora inválida. Usa HH:MM o HH:MM:SS")
        else:
            self._clear_border_error(entrada_field)

        if not sal_ok:
            self._set_border_error(salida_field, "Hora inválida. Usa HH:MM o HH:MM:SS")
        else:
            self._clear_border_error(salida_field)

        if ent_ok and sal_ok:
            res = self.calculo_helper.recalcular_con_estado(
                entrada_field.value, salida_field.value, registro.get("descanso", "MD")
            )
            self._apply_recalc_result(registro, tiempo_field, estado_text, res)
            registro["__horas_invalidas"] = (res.get("estado") != "ok")
            self._call_recalcular(grupo=grupo, registro=registro)

        self._soft_update(force=True)

    def _on_change_tiempo_manual(self, grupo, registro, tiempo_field):
        valor = str(tiempo_field.value or "").strip()
        registro["tiempo_trabajo_manual"] = valor
        registro["__tiempo_manual"] = bool(valor)
        tiempo_field.border_color = None
        self._call_actualizar(grupo, "tiempo_trabajo_manual", valor)

        if not valor:
            registro["__tiempo_manual"] = False
            registro.pop("tiempo_trabajo_manual", None)
            self._soft_update()
            return

        try:
            if ":" in valor:
                try:
                    datetime.strptime(valor, "%H:%M:%S")
                except ValueError:
                    datetime.strptime(valor, "%H:%M")
            else:
                float(valor)
        except Exception:
            tiempo_field.border_color = ft.colors.RED
            tiempo_field.tooltip = "Formato inválido. Usa HH:MM, HH:MM:SS o decimal."
            self._soft_update()
            return

        tiempo_field.tooltip = None
        # manual override pisa ambos (como “valor mostrado”), pero NO afecta DB si no guardas
        registro["tiempo_trabajo"] = valor
        registro["tiempo_trabajo_con_descanso"] = valor
        self._call_recalcular(grupo=grupo, registro=registro)
        self._soft_update()

    def _crear_botones_descanso(self, grupo, registro, tiempo_field, estado_text, entrada_field=None, salida_field=None):
        """
        Botones exclusivos SN / MD / CMP.
        ✅ al recalcular, 'tiempo_field' se pinta con NETO (tiempo_trabajo).
        ✅ autosave: llama commit_descanso_callback y aplica snapshot DB si regresa uno.
        """
        opciones = ["SN", "MD", "CMP"]
        botones = []

        registro["descanso"] = self._default_descanso(registro)

        def seleccionar(opcion: str):
            registro["descanso"] = opcion
            self._call_actualizar(grupo, "descanso", opcion)

            entrada_val = (entrada_field.value if entrada_field else registro.get("hora_entrada", "")) or ""
            salida_val = (salida_field.value if salida_field else registro.get("hora_salida", "")) or ""

            ent_ok = self._is_hora_completa(entrada_val.strip())
            sal_ok = self._is_hora_completa(salida_val.strip())

            if ent_ok and sal_ok:
                res = self.calculo_helper.recalcular_con_estado(entrada_val, salida_val, opcion)
                self._apply_recalc_result(registro, tiempo_field, estado_text, res)
                registro["__horas_invalidas"] = (res.get("estado") != "ok")
                self._call_recalcular(grupo=grupo, registro=registro)
            else:
                registro["__horas_invalidas"] = True
                if estado_text.value not in ("DUPLICADO",):
                    estado_text.value = "PENDIENTE"
                    estado_text.color = self._estado_color("PENDIENTE")

            # pintar selección
            for btn in botones:
                is_on = btn.data == opcion
                btn.bgcolor = ft.colors.BLUE if is_on else ft.colors.WHITE
                btn.content.color = ft.colors.WHITE if is_on else ft.colors.BLACK

            self._soft_update()

            # ✅ autosave + refresh DB snapshot si aplica
            if callable(self.commit_descanso_callback):
                try:
                    if str(registro.get("numero_nomina", "")).strip() and str(registro.get("fecha", "")).strip():
                        self._call_commit_descanso_and_refresh(
                            grupo=grupo,
                            registro=registro,
                            tiempo_field=tiempo_field,
                            estado_text=estado_text,
                        )
                except Exception:
                    pass

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
                on_click=lambda e, t=tipo: seleccionar(t),
            )
            botones.append(btn)

        return ft.Container(
            content=ft.Row(controls=botones, spacing=3, alignment=ft.MainAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            width=self._W["descanso"],
        )

    def validar_duplicado_y_colorear(
        self,
        registros_del_grupo: list,
        registro: dict,
        numero_field: ft.TextField,
        fecha_field: ft.TextField,
        estado_text: ft.Text,
    ) -> bool:
        num = (numero_field.value or "").strip()
        fecha = (fecha_field.value or "").strip()

        duplicado = False
        fecha_norm = self._norm_fecha(fecha)

        if num.isdigit() and fecha_norm:
            for r in registros_del_grupo:
                try:
                    rn = str(r.get("numero_nomina") or "").strip()
                    rf = self._norm_fecha(str(r.get("fecha") or "").strip())
                    if rn == num and rf == fecha_norm:
                        if r is registro:
                            continue
                        duplicado = True
                        break
                except Exception:
                    continue

        registro["__duplicado"] = duplicado

        if duplicado:
            self._set_field_error(numero_field, "ID duplicado en la fecha")
            self._set_field_error(fecha_field, "ID duplicado en la fecha")
            estado_text.value = "DUPLICADO"
            estado_text.color = ft.colors.RED_600
            estado_text.tooltip = "Este número ya existe para esa fecha."
        else:
            self._clear_field_error(numero_field)
            self._clear_field_error(fecha_field)
            if estado_text.value == "DUPLICADO":
                if registro.get("__horas_invalidas", True):
                    estado_text.value = "PENDIENTE"
                    estado_text.color = ft.colors.GREY
                else:
                    estado_text.value = "COMPLETO"
                    estado_text.color = ft.colors.GREEN
                estado_text.tooltip = None

        self._soft_update()
        return duplicado
