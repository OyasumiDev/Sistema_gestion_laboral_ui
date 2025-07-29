from datetime import datetime, date, time, timedelta
import flet as ft 
from typing import Dict

class CalculoHorasHelper:

    @staticmethod
    def recalcular_con_estado(entrada_str: str, salida_str: str, descanso: str) -> dict:
        print(f"🔧 recalcular_con_estado - Entrada: {entrada_str}, Salida: {salida_str}, Descanso: {descanso}")
        errores = []

        # Proteger cálculo si entrada/salida no están completas aún
        if not CalculoHorasHelper.entrada_completa(entrada_str, salida_str):
            errores.append("⚠️ Horas incompletas o parcialmente escritas")
            return {
                "tiempo_trabajo": "00:00:00",
                "tiempo_trabajo_con_descanso": "00:00:00",
                "estado": "incompleto",
                "mensaje": "⚠️ Horas incompletas o parcialmente escritas",
                "errores": errores
            }

        entrada = CalculoHorasHelper.parse_time(entrada_str)
        salida = CalculoHorasHelper.parse_time(salida_str)
        minutos_descanso = CalculoHorasHelper.obtener_minutos_descanso(descanso)

        if not entrada or not salida:
            errores.append("⚠️ Horas inválidas o vacías")
            return {
                "tiempo_trabajo": "00:00:00",
                "tiempo_trabajo_con_descanso": "00:00:00",
                "estado": "invalido",
                "mensaje": "⚠️ Horas inválidas o vacías",
                "errores": errores
            }

        dt_entrada = datetime.combine(date.min, entrada)
        dt_salida = datetime.combine(date.min, salida)

        if dt_salida <= dt_entrada:
            errores.append("⚠️ La hora de salida es menor o igual que la de entrada")
            return {
                "tiempo_trabajo": "00:00:00",
                "tiempo_trabajo_con_descanso": "00:00:00",
                "estado": "negativo",
                "mensaje": "⚠️ La hora de salida es menor o igual que la de entrada",
                "errores": errores
            }

        duracion_total = dt_salida - dt_entrada
        tiempo_trabajo = duracion_total
        tiempo_con_descanso = max(duracion_total - timedelta(minutes=minutos_descanso), timedelta(0))

        def formatear(tiempo: timedelta):
            horas = int(tiempo.total_seconds()) // 3600
            minutos = (int(tiempo.total_seconds()) % 3600) // 60
            segundos = int(tiempo.total_seconds()) % 60
            return f"{horas:02}:{minutos:02}:{segundos:02}"

        return {
            "tiempo_trabajo": formatear(tiempo_trabajo),
            "tiempo_trabajo_con_descanso": formatear(tiempo_con_descanso),
            "estado": "ok",
            "mensaje": "✅ Horas calculadas correctamente",
            "errores": []
        }


    @staticmethod
    def obtener_minutos_descanso(tipo: str) -> int:
        print(f"🔧 obtener_minutos_descanso - Tipo: {tipo}")
        return {"MD": 30, "CMP": 60, "SN": 0}.get(tipo.strip().upper(), 0)

    @staticmethod
    def parse_time(value) -> time | None:
        if not value:
            return None

        # Si ya es objeto time, regresarlo
        if isinstance(value, time):
            return value

        # Si es timedelta, no se puede convertir
        if isinstance(value, timedelta):
            print(f"❗ parse_time: recibido timedelta, inválido → {value}")
            return None

        # Si es datetime completo, tomar solo la hora
        if isinstance(value, datetime):
            return value.time()

        # Si no es string, convertirlo
        if not isinstance(value, str):
            value = str(value)

        value = value.strip()

        formatos_posibles = ["%H:%M", "%H:%M:%S"]

        for fmt in formatos_posibles:
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue

        print(f"❗ Error parseando hora '{value}': no coincide con formatos válidos")
        return None

    @staticmethod
    def validar_duplicado_en_grupo(
        grupo: list[dict],
        numero_nomina: str,
        fecha: str,
        registro_actual: dict = None
    ) -> dict:
        """
        Verifica si existe un número de nómina duplicado en la misma fecha dentro del grupo.
        Convierte todas las fechas a formato ISO antes de comparar.
        """
        print(f"🔍 validar_duplicado_en_grupo - Número: {numero_nomina}, Fecha: {fecha}")

        numero_limpio = str(numero_nomina).strip()
        fecha_iso_objetivo = CalculoHorasHelper.convertir_fecha_a_iso(fecha)

        for registro in grupo:
            if registro_actual is not None and registro is registro_actual:
                continue  # omitir el mismo objeto si se edita

            num_reg = str(registro.get("numero_nomina", "")).strip()
            fecha_reg = CalculoHorasHelper.convertir_fecha_a_iso(registro.get("fecha", ""))

            if num_reg == numero_limpio and fecha_reg == fecha_iso_objetivo:
                return {
                    "duplicado": True,
                    "mensaje": "⚠️ Ya existe un registro con este número y fecha.",
                    "estado": "duplicado"
                }

        return {
            "duplicado": False,
            "mensaje": "✅ Número válido para esta fecha.",
            "estado": "ok"
        }



    @staticmethod
    def validar_numero_fecha_en_grupo(
        grupo: list[dict],
        numero_nomina: str,
        fecha: str,
        registro_actual: dict = None
    ) -> tuple[bool, list[str]]:
        """
        Valida número de nómina y fecha, detectando errores de formato, entrada incompleta
        y duplicados dentro del grupo. Siempre responde de forma segura incluso con entradas mal escritas.
        """
        errores = []

        # Limpiar número
        numero_limpio = str(numero_nomina).strip()
        if not numero_limpio or not numero_limpio.isdigit():
            errores.append("Número inválido")

        # Validar fecha
        fecha_limpia = str(fecha).strip()
        fecha_iso = None

        if not fecha_limpia:
            errores.append("Fecha incompleta")
        elif fecha_limpia.count("/") != 2 or len(fecha_limpia) < 10:
            errores.append("Fecha incompleta")
        else:
            try:
                fecha_iso = datetime.strptime(fecha_limpia, "%d/%m/%Y").strftime("%Y-%m-%d")
            except Exception:
                errores.append("Fecha inválida")

        # Validar duplicado
        if not errores and fecha_iso:
            resultado = CalculoHorasHelper.validar_duplicado_en_grupo(
                grupo, numero_limpio, fecha_iso, registro_actual
            )
            if resultado["duplicado"]:
                errores.append("Duplicado")

        return (len(errores) == 0), errores


    @staticmethod
    def validar_fecha_y_numero(
        registro: dict,
        registros_del_grupo: list[dict],
        numero_field: ft.TextField,
        fecha_field: ft.TextField
    ):
        # Obtener valores actuales de los campos
        numero = str(numero_field.value).strip()
        fecha_original = str(fecha_field.value).strip()

        print(f"🔍 validar_fecha_y_numero - Número: '{numero}', Fecha original: '{fecha_original}'")

        # Actualizar en el registro antes de validar
        registro["numero_nomina"] = numero
        registro["fecha"] = fecha_original

        # Ejecutar validación
        es_valido, errores = CalculoHorasHelper.validar_numero_fecha_en_grupo(
            registros_del_grupo, numero, fecha_original, registro_actual=registro
        )

        registro["errores"] = errores if not es_valido else []

        # Detectar errores por campo
        numero_tiene_error = any("Número" in err or "Duplicado" in err for err in errores)
        fecha_tiene_error = any("Fecha" in err or "Duplicado" in err for err in errores)

        # Visual para número de nómina
        numero_field.border_color = ft.colors.RED_400 if numero_tiene_error else ft.colors.TRANSPARENT
        numero_field.bgcolor = ft.colors.RED_50 if numero_tiene_error else ft.colors.TRANSPARENT

        # Visual para fecha
        fecha_field.border_color = ft.colors.RED_400 if fecha_tiene_error else ft.colors.TRANSPARENT
        fecha_field.bgcolor = ft.colors.RED_50 if fecha_tiene_error else ft.colors.TRANSPARENT

        # Forzar actualización visual robusta
        try:
            if numero_field.page:
                numero_field.update()
            if fecha_field.page:
                fecha_field.update()
        except Exception as e:
            print(f"⚠️ Error actualizando campos visuales: {e}")

    @staticmethod
    def sanitizar_hora(valor) -> str:
        if isinstance(valor, time):
            return valor.strftime("%H:%M:%S")
        elif isinstance(valor, timedelta):
            total_seconds = int(valor.total_seconds())
            horas = total_seconds // 3600
            minutos = (total_seconds % 3600) // 60
            segundos = total_seconds % 60
            return f"{horas:02}:{minutos:02}:{segundos:02}"
        elif isinstance(valor, datetime):
            return valor.time().strftime("%H:%M:%S")
        elif isinstance(valor, str):
            partes = valor.strip().split(":")
            if len(partes) == 2:
                return f"{partes[0]:0>2}:{partes[1]:0>2}:00"
            elif len(partes) == 3:
                return f"{partes[0]:0>2}:{partes[1]:0>2}:{partes[2]:0>2}"
            else:
                return ""
        else:
            return ""


    @staticmethod
    def convertir_fecha_a_iso(fecha_str: str) -> str:
        """
        Convierte fechas en formato DD/MM/YYYY o YYYY-MM-DD a ISO (YYYY-MM-DD).
        Devuelve "" si el formato no es válido.
        """
        fecha_str = str(fecha_str).strip()
        formatos_validos = ["%d/%m/%Y", "%Y-%m-%d"]

        for fmt in formatos_validos:
            try:
                return datetime.strptime(fecha_str, fmt).strftime("%Y-%m-%d")
            except Exception:
                continue

        print(f"❗ Error convirtiendo fecha: {fecha_str} → formato no reconocido")
        return ""


    def _actualizar_tiempo_trabajo(
        self,
        entrada_field: ft.TextField,
        salida_field: ft.TextField,
        descanso_tipo: str,
        tiempo_field: ft.TextField,
        registro: Dict,
        fila_controls: list = None,
        boton_guardar: ft.IconButton = None
    ) -> bool:
        try:
            entrada = entrada_field.value.strip()
            salida = salida_field.value.strip()

            resultado = self.recalcular_con_estado(entrada, salida, descanso_tipo)

            registro["hora_entrada"] = entrada
            registro["hora_salida"] = salida
            registro["tiempo_trabajo"] = resultado["tiempo_trabajo"]
            registro["tiempo_trabajo_con_descanso"] = resultado["tiempo_trabajo_con_descanso"]
            registro["errores"] = resultado["errores"]

            tiempo_field.value = resultado["tiempo_trabajo_con_descanso"]

            def marcar_error(field: ft.TextField, hay_error: bool):
                field.border_color = ft.colors.RED_400 if hay_error else ft.colors.TRANSPARENT
                field.bgcolor = ft.colors.RED_50 if hay_error else ft.colors.TRANSPARENT
                self._actualizar_control_seguro(field)

            estado = resultado["estado"]

            if estado == "incompleto":
                # Si está incompleto, no aplicar estilos de error ni bloquear
                marcar_error(entrada_field, False)
                marcar_error(salida_field, False)
                marcar_error(tiempo_field, False)

                if boton_guardar:
                    boton_guardar.disabled = True
                    boton_guardar.icon_color = ft.colors.GREY
                    boton_guardar.tooltip = "Completa correctamente las horas"
                    self._actualizar_control_seguro(boton_guardar)

                return False

            hay_error = len(resultado["errores"]) > 0
            marcar_error(entrada_field, not entrada or estado == "invalido")
            marcar_error(salida_field, not salida or estado in ["invalido", "negativo"])
            marcar_error(tiempo_field, hay_error)

            if boton_guardar:
                boton_guardar.disabled = hay_error
                boton_guardar.icon_color = ft.colors.GREY if hay_error else None
                boton_guardar.tooltip = "Corregir errores para guardar" if hay_error else "Guardar"
                self._actualizar_control_seguro(boton_guardar)

            return not hay_error

        except Exception as e:
            print(f"❌ Error en _actualizar_tiempo_trabajo: {e}")
            for field in [entrada_field, salida_field, tiempo_field]:
                field.border_color = ft.colors.RED_400
                field.bgcolor = ft.colors.RED_50
                self._actualizar_control_seguro(field)

            if boton_guardar:
                boton_guardar.disabled = True
                boton_guardar.icon_color = ft.colors.GREY
                boton_guardar.tooltip = "Error inesperado"
                self._actualizar_control_seguro(boton_guardar)

            tiempo_field.value = "0.00"
            self._actualizar_control_seguro(tiempo_field)
            return False




    def _actualizar_control_seguro(self, control: ft.Control):
        try:
            if control.page:
                control.update()
        except Exception as e:
            print(f"⚠️ No se pudo actualizar control: {control}, error: {e}")


    @staticmethod
    def entrada_completa(entrada: str, salida: str) -> bool:
        """
        Devuelve True si ambos campos tienen formato válido y completo.
        Evita calcular mientras el usuario escribe horas parciales.
        """
        if not entrada or not salida:
            return False

        formatos = ["%H:%M", "%H:%M:%S"]
        for fmt in formatos:
            try:
                datetime.strptime(entrada.strip(), fmt)
                datetime.strptime(salida.strip(), fmt)
                return True
            except Exception:
                continue
        return False

