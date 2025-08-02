# src/app/helpers/prestamos_helper/prestamos_validation_helper.py

import flet as ft
from datetime import datetime


class PrestamosValidationHelper:

    COLOR_ERROR = ft.colors.RED_400
    COLOR_OK = ft.colors.GREY_400

    @staticmethod
    def validar_numero_nomina(campo: ft.TextField) -> bool:
        valor = campo.value.strip()
        if not valor.isdigit():
            campo.border_color = PrestamosValidationHelper.COLOR_ERROR
            campo.update()
            return False
        campo.border_color = PrestamosValidationHelper.COLOR_OK
        campo.update()
        return True

    @staticmethod
    def validar_monto(campo: ft.TextField) -> bool:
        try:
            valor = float(campo.value.strip())
            if valor <= 0:
                raise ValueError("Monto inválido")
            campo.border_color = PrestamosValidationHelper.COLOR_OK
            campo.update()
            return True
        except:
            campo.border_color = PrestamosValidationHelper.COLOR_ERROR
            campo.update()
            return False

    @staticmethod
    def validar_fecha(campo: ft.TextField) -> bool:
        try:
            valor = campo.value.strip()
            datetime.strptime(valor, "%d/%m/%Y")
            campo.border_color = PrestamosValidationHelper.COLOR_OK
            campo.update()
            return True
        except:
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
