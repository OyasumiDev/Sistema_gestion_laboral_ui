from datetime import datetime, date


class CalculoHorasHelper:

    @staticmethod
    def recalcular_con_estado(entrada_str: str, salida_str: str, descanso: str) -> dict:
        """
        Retorna:
        {
            "horas": "0.00",
            "estado": "ok" | "invalido" | "negativo",
            "mensaje": str
        }
        """
        print(f"🔧 recalcular_con_estado - Entrada: {entrada_str}, Salida: {salida_str}, Descanso: {descanso}")

        entrada = CalculoHorasHelper.parse_time(entrada_str)
        salida = CalculoHorasHelper.parse_time(salida_str)
        minutos_descanso = CalculoHorasHelper.obtener_minutos_descanso(descanso)

        if not entrada or not salida:
            print("⚠️ Horas inválidas o incompletas")
            return {
                "horas": "0.00",
                "estado": "invalido",
                "mensaje": "⚠️ Horas inválidas o incompletas"
            }

        total = (datetime.combine(date.min, salida) - datetime.combine(date.min, entrada)).total_seconds() / 3600
        total -= minutos_descanso / 60

        if total < 0:
            print("⚠️ La hora de salida es menor que la de entrada")
            return {
                "horas": "0.00",
                "estado": "negativo",
                "mensaje": "⚠️ La hora de salida es menor que la de entrada"
            }

        print(f"✅ Total horas calculadas: {total:.2f}")
        return {
            "horas": f"{total:.2f}",
            "estado": "ok",
            "mensaje": "✅ Horas calculadas correctamente"
        }

    @staticmethod
    def obtener_minutos_descanso(tipo: str) -> int:
        print(f"🔧 obtener_minutos_descanso - Tipo: {tipo}")
        return {"MD": 30, "CMP": 60, "SN": 0}.get(tipo, 0)

    @staticmethod
    def parse_time(value: str):
        try:
            return datetime.strptime(value.strip(), "%H:%M").time()
        except Exception as e:
            print(f"❗ Error parseando hora '{value}': {e}")
            return None
