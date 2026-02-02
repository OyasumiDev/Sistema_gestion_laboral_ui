from __future__ import annotations

from datetime import datetime, date, time, timedelta
from typing import Dict, Tuple, List, Optional, Any
import re
import flet as ft


class CalculoHorasHelper:
    """
    Helper núcleo para:
    - Cálculo de horas trabajadas (neto y con descanso)
    - Validación segura (mientras se escribe)
    - Normalización de descanso (SN/MD/CMP) + soporte int 0/1/2
    - Validación de duplicados por (numero_nomina, fecha) dentro del grupo
    - Helpers visuales para TextField (errores sin romper el borde OUTLINE)

    Reglas acordadas en el chat:
    - Descanso default: MD
    - Si horas incompletas: NO marcar error duro (estado = 'incompleto')
    - Si salida <= entrada: estado = 'negativo'
    - Permitir recalcular descanso sin entrar a edición (depende solo de entrada/salida/descanso)
    """

    # -------------------------
    # Normalizaciones base
    # -------------------------
    @staticmethod
    def normalizar_descanso(v: Any) -> str:
        """
        Normaliza cualquier valor de descanso a: 'SN', 'MD', 'CMP'
        Acepta:
        - None, "", "NULL" -> MD
        - int/str "0" -> SN ; "1" -> MD ; "2" -> CMP
        - "SN/MD/CMP" (case-insensitive)
        """
        if v is None:
            return "MD"
        s = str(v).strip().upper()
        if s in ("", "NONE", "NULL"):
            return "MD"
        if s in ("0", "SN", "SIN"):
            return "SN"
        if s in ("1", "MD", "MEDIO"):
            return "MD"
        if s in ("2", "CMP", "COMIDA", "COMPLETO"):
            return "CMP"
        return "MD" if s not in ("SN", "MD", "CMP") else s

    @staticmethod
    def obtener_minutos_descanso(tipo: Any) -> int:
        """
        Regla del proyecto:
        - SN = 0
        - MD = 30 (default)
        - CMP = 60
        """
        t = CalculoHorasHelper.normalizar_descanso(tipo)
        return {"SN": 0, "MD": 30, "CMP": 60}[t]

    # -------------------------
    # Parseo robusto de hora
    # -------------------------
    @staticmethod
    def _is_hora_completa(v: str) -> bool:
        """
        True si es HH:MM o HH:MM:SS completo. (No acepta parciales tipo "6:" o "6:2")
        """
        if not v:
            return False
        s = str(v).strip()
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

    @staticmethod
    def entrada_completa(entrada: str, salida: str) -> bool:
        """
        Evita calcular mientras el usuario escribe horas parciales.
        """
        return CalculoHorasHelper._is_hora_completa(entrada) and CalculoHorasHelper._is_hora_completa(salida)

    @staticmethod
    def parse_time(value: Any) -> Optional[time]:
        """
        Convierte a time.
        - Acepta time/datetime/str
        - Rechaza timedelta
        - str: HH:MM o HH:MM:SS (completo)
        """
        if value is None:
            return None

        if isinstance(value, time):
            return value

        if isinstance(value, timedelta):
            # No es hora; es duración.
            return None

        if isinstance(value, datetime):
            return value.time()

        s = value if isinstance(value, str) else str(value)
        s = s.strip()
        if not s:
            return None

        # Normaliza "H:MM" -> "HH:MM"
        # (pero SOLO si ya es completo, no parcial)
        if not CalculoHorasHelper._is_hora_completa(s):
            return None

        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(s, fmt).time()
            except ValueError:
                continue
        return None

    @staticmethod
    def sanitizar_hora(valor: Any) -> str:
        """
        Devuelve string HH:MM (sin segundos en UI) si puede.
        Acepta time/datetime/timedelta/str.
        """
        if valor is None:
            return ""

        if isinstance(valor, time):
            return valor.strftime("%H:%M")

        if isinstance(valor, datetime):
            return valor.time().strftime("%H:%M")

        if isinstance(valor, timedelta):
            total_seconds = int(valor.total_seconds())
            h = total_seconds // 3600
            m = (total_seconds % 3600) // 60
            return f"{h:02}:{m:02}"

        s = valor if isinstance(valor, str) else str(valor)
        s = s.strip()
        if not s:
            return ""

        # Limpieza básica: "6:2" NO lo forzamos a completo, lo dejamos igual para que la validación lo trate como incompleto.
        # Solo normalizamos cuando ya es "completo" (H:MM / HH:MM / HH:MM:SS)
        m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?$", s)
        if not m:
            return s  # el RowHelper puede seguir editando; aquí no rompemos input

        hh = int(m.group(1))
        mm = int(m.group(2))
        # si trae segundos, los ignoramos para UI de campos hora
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return f"{hh:02}:{mm:02}"
        return s

    # -------------------------
    # Cálculo principal
    # -------------------------
    @staticmethod
    def recalcular_con_estado(entrada_str: str, salida_str: str, descanso: Any) -> dict:
        """
        Retorna:
        - tiempo_trabajo (neto, con descanso)
        - tiempo_trabajo_con_descanso (bruto, sin descanso)
        - estado: ok | incompleto | invalido | negativo
        - mensaje + errores
        """
        errores: List[str] = []

        # Normalizar descanso (MD default)
        descanso_norm = CalculoHorasHelper.normalizar_descanso(descanso)
        minutos_descanso = CalculoHorasHelper.obtener_minutos_descanso(descanso_norm)

        entrada_str = (entrada_str or "").strip()
        salida_str = (salida_str or "").strip()

        # Mientras se escribe (no bloqueo duro)
        if not CalculoHorasHelper.entrada_completa(entrada_str, salida_str):
            return {
                "tiempo_trabajo": "00:00:00",
                "tiempo_trabajo_con_descanso": "00:00:00",
                "estado": "incompleto",
                "mensaje": "⚠️ Horas incompletas o parcialmente escritas",
                "errores": ["Horas incompletas"],
                "descanso": descanso_norm,
                "minutos_descanso": minutos_descanso,
            }

        entrada = CalculoHorasHelper.parse_time(entrada_str)
        salida = CalculoHorasHelper.parse_time(salida_str)

        if not entrada or not salida:
            return {
                "tiempo_trabajo": "00:00:00",
                "tiempo_trabajo_con_descanso": "00:00:00",
                "estado": "invalido",
                "mensaje": "⚠️ Horas inválidas o vacías",
                "errores": ["Horas inválidas"],
                "descanso": descanso_norm,
                "minutos_descanso": minutos_descanso,
            }

        dt_entrada = datetime.combine(date.min, entrada)
        dt_salida = datetime.combine(date.min, salida)

        if dt_salida <= dt_entrada:
            return {
                "tiempo_trabajo": "00:00:00",
                "tiempo_trabajo_con_descanso": "00:00:00",
                "estado": "negativo",
                "mensaje": "⚠️ La hora de salida es menor o igual que la de entrada",
                "errores": ["Salida <= entrada"],
                "descanso": descanso_norm,
                "minutos_descanso": minutos_descanso,
            }

        duracion_total = dt_salida - dt_entrada
        tiempo_con_descanso = duracion_total - timedelta(minutes=minutos_descanso)
        if tiempo_con_descanso < timedelta(0):
            tiempo_con_descanso = timedelta(0)

        def _fmt(td: timedelta) -> str:
            total = int(td.total_seconds())
            h = total // 3600
            m = (total % 3600) // 60
            s = total % 60
            return f"{h:02}:{m:02}:{s:02}"

        return {
            "tiempo_trabajo": _fmt(tiempo_con_descanso),
            "tiempo_trabajo_con_descanso": _fmt(duracion_total),
            "estado": "ok",
            "mensaje": "✅ Horas calculadas correctamente",
            "errores": errores,
            "descanso": descanso_norm,
            "minutos_descanso": minutos_descanso,
        }

    # -------------------------
    # Fechas (para duplicados)
    # -------------------------
    @staticmethod
    def convertir_fecha_a_iso(fecha_str: Any) -> str:
        """
        Convierte DD/MM/YYYY o YYYY-MM-DD a ISO YYYY-MM-DD.
        Retorna "" si no es válido.
        """
        s = ("" if fecha_str is None else str(fecha_str)).strip()
        if not s:
            return ""

        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except Exception:
                continue

        return ""

    @staticmethod
    def parse_fecha_ddmmyyyy(fecha_str: str) -> datetime:
        """
        Necesario porque tu RowHelper lo usa.
        Lanza excepción si no puede parsear (así lo manejas arriba).
        """
        return datetime.strptime(str(fecha_str).strip(), "%d/%m/%Y")

    # -------------------------
    # Duplicados en grupo
    # -------------------------
    @staticmethod
    def validar_duplicado_en_grupo(
        grupo: List[dict],
        numero_nomina: str,
        fecha: str,
        registro_actual: dict = None
    ) -> dict:
        """
        Verifica duplicado por (numero_nomina, fecha ISO) en el mismo grupo.
        """
        numero_limpio = str(numero_nomina).strip()
        fecha_iso_obj = CalculoHorasHelper.convertir_fecha_a_iso(fecha)

        if not numero_limpio.isdigit() or not fecha_iso_obj:
            return {"duplicado": False, "mensaje": "⚠️ Datos incompletos", "estado": "incompleto"}

        for r in (grupo or []):
            if registro_actual is not None and r is registro_actual:
                continue

            num_r = str(r.get("numero_nomina", "")).strip()
            fecha_r = CalculoHorasHelper.convertir_fecha_a_iso(r.get("fecha", ""))

            if num_r == numero_limpio and fecha_r == fecha_iso_obj:
                return {
                    "duplicado": True,
                    "mensaje": "⚠️ Ya existe un registro con este número y fecha.",
                    "estado": "duplicado",
                }

        return {"duplicado": False, "mensaje": "✅ Número válido para esta fecha.", "estado": "ok"}

    @staticmethod
    def validar_numero_fecha_en_grupo(
        grupo: List[dict],
        numero_nomina: str,
        fecha: str,
        registro_actual: dict = None
    ) -> Tuple[bool, List[str]]:
        """
        Valida:
        - numero_nomina: dígitos
        - fecha: DD/MM/YYYY o YYYY-MM-DD
        - duplicado en grupo
        """
        errores: List[str] = []

        num = str(numero_nomina).strip()
        if not num.isdigit():
            errores.append("Número inválido")

        fecha_s = str(fecha).strip()
        fecha_iso = CalculoHorasHelper.convertir_fecha_a_iso(fecha_s)
        if not fecha_s:
            errores.append("Fecha incompleta")
        elif not fecha_iso:
            errores.append("Fecha inválida")

        if not errores:
            dup = CalculoHorasHelper.validar_duplicado_en_grupo(grupo, num, fecha_iso, registro_actual=registro_actual)
            if dup.get("duplicado"):
                errores.append("Duplicado")

        return (len(errores) == 0), errores

    @staticmethod
    def validar_fecha_y_numero(
        registro: dict,
        registros_del_grupo: List[dict],
        numero_field: ft.TextField,
        fecha_field: ft.TextField
    ):
        """
        Valida en blur (como acordamos).
        Marca visualmente SIN romper el borde outline.
        """
        numero = str(numero_field.value or "").strip()
        fecha_original = str(fecha_field.value or "").strip()

        # Persistir en registro antes de validar
        registro["numero_nomina"] = numero
        registro["fecha"] = fecha_original

        es_valido, errores = CalculoHorasHelper.validar_numero_fecha_en_grupo(
            registros_del_grupo, numero, fecha_original, registro_actual=registro
        )

        registro["errores"] = [] if es_valido else errores

        numero_tiene_error = any(("Número" in e) or ("Duplicado" in e) for e in errores)
        fecha_tiene_error = any(("Fecha" in e) or ("Duplicado" in e) for e in errores)

        # No uses TRANSPARENT como border_color cuando tienes OUTLINE:
        # mejor None para "volver a default"
        numero_field.border_color = ft.colors.RED_400 if numero_tiene_error else None
        numero_field.bgcolor = ft.colors.with_opacity(0.10, ft.colors.RED) if numero_tiene_error else None

        fecha_field.border_color = ft.colors.RED_400 if fecha_tiene_error else None
        fecha_field.bgcolor = ft.colors.with_opacity(0.10, ft.colors.RED) if fecha_tiene_error else None

        try:
            if numero_field.page:
                numero_field.update()
            if fecha_field.page:
                fecha_field.update()
        except Exception:
            pass

    # -------------------------
    # UI: actualización de cálculo en vivo
    # -------------------------
    def _actualizar_tiempo_trabajo(
        self,
        entrada_field: ft.TextField,
        salida_field: ft.TextField,
        descanso_tipo: Any,
        tiempo_field: ft.TextField,
        registro: Dict,
        fila_controls: list = None,
        boton_guardar: ft.IconButton = None
    ) -> bool:
        """
        Función usada por RowHelpers:
        - Recalcula
        - Actualiza registro
        - Aplica estilos (sin castigar cuando está incompleto)
        - Controla botón guardar
        Retorna True si está listo para guardar.
        """
        try:
            entrada_raw = (entrada_field.value or "").strip()
            salida_raw = (salida_field.value or "").strip()

            descanso_norm = self.normalizar_descanso(descanso_tipo)
            resultado = self.recalcular_con_estado(entrada_raw, salida_raw, descanso_norm)

            # Persistir
            registro["hora_entrada"] = entrada_raw
            registro["hora_salida"] = salida_raw
            registro["descanso"] = descanso_norm
            registro["tiempo_trabajo"] = resultado["tiempo_trabajo"]
            registro["tiempo_trabajo_con_descanso"] = resultado["tiempo_trabajo_con_descanso"]
            registro["errores"] = resultado.get("errores", [])

            # Flags útiles para tu flujo (fila nueva)
            registro["__horas_invalidas"] = resultado["estado"] != "ok"

            tiempo_field.value = resultado["tiempo_trabajo_con_descanso"]

            def _mark(tf: ft.TextField, err: bool, tooltip: str | None = None):
                tf.border_color = ft.colors.RED_400 if err else None
                tf.bgcolor = ft.colors.with_opacity(0.10, ft.colors.RED) if err else None
                tf.tooltip = tooltip if err else None
                self._actualizar_control_seguro(tf)

            estado = resultado["estado"]

            # Mientras escribes: no marcar error duro
            if estado == "incompleto":
                _mark(entrada_field, False)
                _mark(salida_field, False)
                _mark(tiempo_field, False)

                if boton_guardar:
                    boton_guardar.disabled = True
                    boton_guardar.tooltip = "Completa correctamente las horas"
                    self._actualizar_control_seguro(boton_guardar)
                return False

            # Errores duros
            hay_error = estado != "ok"
            tooltip = resultado.get("mensaje")

            _mark(entrada_field, hay_error and (estado in ("invalido", "negativo")), tooltip)
            _mark(salida_field, hay_error and (estado in ("invalido", "negativo")), tooltip)
            _mark(tiempo_field, hay_error, tooltip)

            if boton_guardar:
                boton_guardar.disabled = hay_error
                boton_guardar.tooltip = "Corregir errores para guardar" if hay_error else "Guardar"
                self._actualizar_control_seguro(boton_guardar)

            return not hay_error

        except Exception:
            # Fallback seguro
            for field in [entrada_field, salida_field, tiempo_field]:
                try:
                    field.border_color = ft.colors.RED_400
                    field.bgcolor = ft.colors.with_opacity(0.10, ft.colors.RED)
                    self._actualizar_control_seguro(field)
                except Exception:
                    pass

            if boton_guardar:
                try:
                    boton_guardar.disabled = True
                    boton_guardar.tooltip = "Error inesperado"
                    self._actualizar_control_seguro(boton_guardar)
                except Exception:
                    pass

            try:
                tiempo_field.value = "00:00:00"
                self._actualizar_control_seguro(tiempo_field)
            except Exception:
                pass

            registro["__horas_invalidas"] = True
            return False

    def _actualizar_control_seguro(self, control: ft.Control):
        try:
            if control and control.page:
                control.update()
        except Exception:
            pass
