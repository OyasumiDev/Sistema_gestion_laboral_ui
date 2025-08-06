import flet as ft
from datetime import datetime
from app.models.employes_model import EmployesModel


class PrestamosValidationHelper:

    COLOR_ERROR = ft.colors.RED_400
    COLOR_OK = ft.colors.GREY_400

    @staticmethod
    def validar_numero_nomina(campo: ft.TextField) -> bool:
        valor = campo.value.strip()
        if not valor.isdigit() or int(valor) <= 0:
            campo.border_color = PrestamosValidationHelper.COLOR_ERROR
            campo.update()
            return False

        empleado = EmployesModel().get_by_numero_nomina(int(valor))
        if not empleado:
            campo.border_color = PrestamosValidationHelper.COLOR_ERROR
            campo.update()
            return False

        campo.border_color = PrestamosValidationHelper.COLOR_OK
        campo.update()
        return True

    @staticmethod
    def validar_monto(campo: ft.TextField, limite: float = 10000.0) -> bool:
        try:
            valor = float(campo.value.strip().replace(",", "."))
            if valor <= 0 or valor > limite:
                raise ValueError
            campo.border_color = PrestamosValidationHelper.COLOR_OK
            campo.update()
            return True
        except:
            campo.border_color = PrestamosValidationHelper.COLOR_ERROR
            campo.update()
            return False


    @staticmethod
    def validar_fecha(campo: ft.TextField) -> bool:
        valor = campo.value.strip()
        try:
            datetime.strptime(valor, "%d/%m/%Y")
            campo.border_color = PrestamosValidationHelper.COLOR_OK
            campo.update()
            return True
        except ValueError:
            campo.border_color = PrestamosValidationHelper.COLOR_ERROR
            campo.update()
            return False

    @staticmethod
    def validar_texto(campo: ft.TextField, obligatorio: bool = True) -> bool:
        texto = campo.value.strip()
        if obligatorio and not texto:
            campo.border_color = PrestamosValidationHelper.COLOR_ERROR
            campo.update()
            return False
        campo.border_color = PrestamosValidationHelper.COLOR_OK
        campo.update()
        return True

    @staticmethod
    def resetear_color(campo: ft.TextField):
        campo.border_color = PrestamosValidationHelper.COLOR_OK
        campo.update()

    @staticmethod
    def establecer_fecha_actual_si_vacia(campo: ft.TextField):
        if not campo.value.strip():
            campo.value = datetime.today().strftime("%d/%m/%Y")
            campo.update()

    @staticmethod
    def validar_campos_completos(numero: ft.TextField, monto: ft.TextField, fecha: ft.TextField) -> bool:
        valido_id = PrestamosValidationHelper.validar_numero_nomina(numero)
        valido_monto = PrestamosValidationHelper.validar_monto(monto)
        PrestamosValidationHelper.establecer_fecha_actual_si_vacia(fecha)
        valido_fecha = PrestamosValidationHelper.validar_fecha(fecha)
        return valido_id and valido_monto and valido_fecha

    @staticmethod
    def validar_existencia_empleado(numero_nomina: str) -> bool:
        if not numero_nomina.isdigit():
            return False
        empleado = EmployesModel().get_by_numero_nomina(int(numero_nomina))
        return bool(empleado)

    def convertir_fecha_mysql(self, fecha_texto: str) -> str:
        try:
            fecha_obj = datetime.strptime(fecha_texto.strip(), "%d/%m/%Y")
            return fecha_obj.strftime("%Y-%m-%d")
        except Exception as e:
            print(f"❌ Error al convertir fecha: {fecha_texto} → {e}")
            return fecha_texto  # retorna el texto original si falla