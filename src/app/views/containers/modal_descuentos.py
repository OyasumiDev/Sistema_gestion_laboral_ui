import flet as ft
from app.core.app_state import AppState
from app.views.containers.modal_alert import ModalAlert


class ModalDescuentos:
    def __init__(self, pago: dict, on_confirmar):
        self.page = AppState().page
        self.pago = pago
        self.on_confirmar = on_confirmar

        # Controles
        self.chk_imss = ft.Checkbox(label="Aplicar IMSS", value=True)

        self.chk_transporte = ft.Checkbox(label="Aplicar Transporte", value=False, on_change=self._toggle_transporte)
        self.input_transporte = ft.TextField(label="Monto Transporte", value="0.0", visible=False, width=200)

        self.chk_comida = ft.Checkbox(label="Aplicar Comida", value=False, on_change=self._toggle_comida)
        self.dropdown_comida = ft.Dropdown(
            label="Tipo de Comida",
            width=200,
            visible=False,
            options=[
                ft.dropdown.Option("diario"),
                ft.dropdown.Option("quincenal"),
                ft.dropdown.Option("mensual")
            ]
        )

        self.txt_desc_extra = ft.TextField(label="Descuento Extra", value="0.0", width=200)
        self.txt_desc_motivo = ft.TextField(label="Motivo del Extra", value="", width=400)

        # Dialog
        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Descuentos para {self.pago['numero_nomina']}", size=20, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    self.chk_imss,
                    ft.Row([self.chk_transporte, self.input_transporte], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([self.chk_comida, self.dropdown_comida], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self.txt_desc_extra,
                    self.txt_desc_motivo
                ], tight=True, spacing=15),
                width=500,
                padding=25
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=self._cerrar),
                ft.ElevatedButton("Aplicar", on_click=self._confirmar)
            ],
            on_dismiss=self._cerrar
        )

    def _toggle_transporte(self, e):
        self.input_transporte.visible = self.chk_transporte.value
        self.page.update()

    def _toggle_comida(self, e):
        self.dropdown_comida.visible = self.chk_comida.value
        self.page.update()

    def mostrar(self):
        if self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    def _cerrar(self, e=None):
        self.dialog.open = False
        self.page.update()

    def _confirmar(self, e):
        try:
            extra = float(self.txt_desc_extra.value.strip())
            transporte = float(self.input_transporte.value.strip()) if self.chk_transporte.value else 0.0
        except ValueError:
            ModalAlert.mostrar_info("Valor inválido", "El descuento extra y transporte deben ser numéricos.")
            return

        self._cerrar()
        self.on_confirmar({
            "aplicar_imss": self.chk_imss.value,
            "aplicar_transporte": self.chk_transporte.value,
            "monto_transporte": transporte,
            "aplicar_comida": self.chk_comida.value,
            "estado_comida": self.dropdown_comida.value if self.chk_comida.value else "",
            "descuento_extra": extra,
            "descripcion_extra": self.txt_desc_motivo.value.strip()
        })

        
        
        
