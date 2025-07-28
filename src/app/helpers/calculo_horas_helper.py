from datetime import datetime, date, time, timedelta

class CalculoHorasHelper:

    @staticmethod
    def recalcular_con_estado(entrada_str: str, salida_str: str, descanso: str) -> dict:
        """
        Retorna:
        {
            "tiempo_trabajo": "00:00:00",                   # Tiempo neto sin descanso
            "tiempo_trabajo_con_descanso": "00:00:00",      # Tiempo real visible
            "estado": "ok" | "invalido" | "negativo",
            "mensaje": str,
            "errores": [str]
        }
        """
        print(f"🔧 recalcular_con_estado - Entrada: {entrada_str}, Salida: {salida_str}, Descanso: {descanso}")
        errores = []
        entrada = CalculoHorasHelper.parse_time(entrada_str)
        salida = CalculoHorasHelper.parse_time(salida_str)
        minutos_descanso = CalculoHorasHelper.obtener_minutos_descanso(descanso)

        if not entrada or not salida:
            errores.append("⚠️ Horas inválidas o incompletas")
            return {
                "tiempo_trabajo": "00:00:00",
                "tiempo_trabajo_con_descanso": "00:00:00",
                "estado": "invalido",
                "mensaje": "⚠️ Horas inválidas o incompletas",
                "errores": errores
            }

        dt_entrada = datetime.combine(date.min, entrada)
        dt_salida = datetime.combine(date.min, salida)

        if dt_salida <= dt_entrada:
            errores.append("⚠️ La hora de salida es menor que la de entrada")
            return {
                "tiempo_trabajo": "00:00:00",
                "tiempo_trabajo_con_descanso": "00:00:00",
                "estado": "negativo",
                "mensaje": "⚠️ La hora de salida es menor que la de entrada",
                "errores": errores
            }

        # Tiempo neto sin descanso
        duracion_total = dt_salida - dt_entrada
        tiempo_trabajo = duracion_total

        # Tiempo restando el descanso
        tiempo_con_descanso = duracion_total - timedelta(minutes=minutos_descanso)
        tiempo_con_descanso = max(tiempo_con_descanso, timedelta(0))

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
        fecha: str
    ) -> dict:
        """
        Verifica si existe un número de nómina duplicado en la misma fecha dentro del grupo.
        Retorna dict con:
        - 'duplicado': True/False
        - 'mensaje': str descriptivo
        - 'estado': 'duplicado' | 'ok'
        """
        print(f"🔍 validar_duplicado_en_grupo - Número: {numero_nomina}, Fecha: {fecha}")
        for registro in grupo:
            if (
                str(registro.get("numero_nomina", "")).strip() == str(numero_nomina).strip()
                and str(registro.get("fecha", "")).strip() == str(fecha).strip()
            ):
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
    def validar_numero_fecha_en_grupo(grupo: list[dict], numero_nomina: str, fecha: str) -> tuple[bool, list[str]]:
        """
        Valida número y fecha con lógica de duplicado incluida.

        Retorna:
        - bool: True si es válido
        - list[str]: Lista de errores ("Número inválido", "Fecha inválida", "Duplicado")
        """
        errores = []

        if not numero_nomina or not numero_nomina.strip().isdigit():
            errores.append("Número inválido")

        try:
            datetime.strptime(fecha, "%Y-%m-%d")
        except Exception:
            errores.append("Fecha inválida")

        if not errores:
            resultado = CalculoHorasHelper.validar_duplicado_en_grupo(grupo, numero_nomina, fecha)
            if resultado["duplicado"]:
                errores.append("Duplicado")

        return (len(errores) == 0), errores
