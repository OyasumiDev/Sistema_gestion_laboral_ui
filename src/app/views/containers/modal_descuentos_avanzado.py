import flet as ft
from datetime import datetime


class ModalDescuentosAvanzado(ft.AlertDialog):
    def __init__(self, on_confirmar, numero_nomina: int, loan_model):
        super().__init__()
        self.on_confirmar = on_confirmar
        self.numero_nomina = numero_nomina
        self.loan_model = loan_model

        # Estado visual
        self.aplicar_prestamo = False
        self.prestamo_actual = self.loan_model.get_prestamo_activo_por_empleado(self.numero_nomina)
        self.monto_prestamo_otro = ft.TextField(label="Monto a pagar", width=120, visible=False)
        self.opcion_prestamo = ft.Dropdown(
            label="Pago préstamo",
            options=[
                ft.dropdown.Option("50"),
                ft.dropdown.Option("Otro")
            ],
            visible=False,
            on_change=self._toggle_otro_prestamo
        )

        # Campos de descuentos
        self.imss = ft.TextField(label="IMSS", value="50.0", width=100)
        self.transporte = ft.TextField(label="Transporte", value="0.0", width=100)
        self.comida = ft.TextField(label="Comida", value="0.0", width=100)
        self.extra = ft.TextField(label="Extra", value="0.0", width=100)
        self.descripcion_extra = ft.TextField(label="Descripción Extra", width=150)

        # Validaciones visuales
        self._validaciones = [self.imss, self.transporte, self.comida, self.extra, self.monto_prestamo_otro]

        self.content = ft.Column([
            ft.Text("Selecciona y personaliza los descuentos a aplicar", weight="bold"),
            ft.Row([self.imss, self.transporte, self.comida]),
            ft.Row([self.extra, self.descripcion_extra]),
        ])

        if self.prestamo_actual:
            self.aplicar_prestamo = True
            self.opcion_prestamo.visible = True
            self.content.controls.append(ft.Row([self.opcion_prestamo, self.monto_prestamo_otro]))

        self.actions = [
            ft.TextButton("Cancelar", on_click=lambda _: self.close()),
            ft.ElevatedButton("Aceptar", on_click=self._confirmar)
        ]

    def _toggle_otro_prestamo(self, e):
        self.monto_prestamo_otro.visible = self.opcion_prestamo.value == "Otro"
        self.update()

    def _confirmar(self, e):
        errores = False
        for campo in self._validaciones:
            if campo.visible:
                try:
                    val = float(campo.value.strip())
                    if val < 0:
                        campo.border_color = ft.colors.RED
                        errores = True
                    else:
                        campo.border_color = None
                except:
                    campo.border_color = ft.colors.RED
                    errores = True
        if errores:
            self.update()
            return

        montos = {
            "retenciones_imss": float(self.imss.value),
            "transporte": float(self.transporte.value),
            "comida": float(self.comida.value),
            "descuento_extra": float(self.extra.value)
        }

        pago_prestamo = 0
        if self.aplicar_prestamo:
            if self.opcion_prestamo.value == "50":
                pago_prestamo = 50
            elif self.opcion_prestamo.value == "Otro":
                pago_prestamo = float(self.monto_prestamo_otro.value.strip())

        self.on_confirmar({
            "montos": montos,
            "descripcion_extra": self.descripcion_extra.value.strip(),
            "pago_prestamo": pago_prestamo,
            "prestamo": self.prestamo_actual  # dict con id, saldo e interes
        })
        self.close()
