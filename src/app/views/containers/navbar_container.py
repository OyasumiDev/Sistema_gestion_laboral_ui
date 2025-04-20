import flet as ft
from app.core.app_state import AppState


class DashboardNavBar(ft.Container):
    def __init__(self, is_root: bool = False):
        super().__init__(
            width=80,
            bgcolor=ft.colors.BLACK,
            padding=10,
            alignment=ft.alignment.top_left
        )

        self.page = AppState().page
        self.is_root = is_root
        self.expandido = False

        # Recupera el tema guardado en client_storage (por defecto oscuro)
        self.tema_oscuro = self.page.client_storage.get("tema_oscuro")
        if self.tema_oscuro is None:
            self.tema_oscuro = True

        self.dashboard_view = None
        self.dialogo_salir = None

        avatar_img = ft.Image(
            src="logos/root.png" if is_root else "logos/user.png",
            width=40,
            height=40,
            border_radius=20,
            fit=ft.ImageFit.COVER,
            tooltip="Usuario"
        )

        avatar_container = ft.Container(
            bgcolor=ft.colors.GREY_800,
            padding=8,
            border_radius=10,
            alignment=ft.alignment.center,
            content=avatar_img
        )

        self.avatar = avatar_container

        self.layout_label = ft.Text("", visible=False, size=12, color=ft.colors.WHITE)
        self.boton_layout = ft.GestureDetector(
            content=ft.Container(
                bgcolor=ft.colors.GREY_800,
                padding=10,
                border_radius=8,
                content=ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            bgcolor=ft.colors.WHITE,
                            border_radius=6,
                            padding=6,
                            content=ft.Image(
                                src="button's/layout_open-button.png",
                                width=20,
                                height=20
                            )
                        ),
                        self.layout_label
                    ]
                )
            ),
            on_tap=self.toggle_nav
        )

        self.menu_items = [
            ("Área de Asistencia", "button's/attendance-area-button.png", "usuario"),
            ("Nómina", "button's/nomina-area-button.png", "nomina"),
            ("Reportes", "button's/reports-area-button.png", "reportes")
        ]

        if is_root:
            self.menu_items.append(("Gestión de Usuarios", "button's/user-manager-area-button.png", "usuarios"))

        self.column = ft.Column(spacing=10, controls=[self.avatar, self.boton_layout])
        self.icon_containers = []

        for texto, icono, ruta in self.menu_items:
            contenedor_icono = ft.Container(
                bgcolor=ft.colors.WHITE,
                border_radius=6,
                padding=6,
                content=ft.Image(src=icono, width=20, height=20)
            )

            fila = ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    contenedor_icono,
                    ft.Text(texto, visible=self.expandido, size=12, color=ft.colors.WHITE)
                ]
            )

            item = ft.Container(
                bgcolor=ft.colors.GREY_800,
                border_radius=8,
                padding=10,
                content=fila,
                on_click=lambda e, destino=ruta: self.navegar(destino)
            )

            self.icon_containers.append((item, fila.controls[1], contenedor_icono))
            self.column.controls.append(item)

        self.tema_label = ft.Text("", visible=False, size=12, color=ft.colors.WHITE)
        self.boton_tema = ft.GestureDetector(
            content=ft.Container(
                bgcolor=ft.colors.GREY_800,
                padding=10,
                border_radius=8,
                content=ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            bgcolor=ft.colors.WHITE,
                            border_radius=6,
                            padding=6,
                            content=ft.Image(
                                src="button's/dark-color-button.png",
                                width=20,
                                height=20
                            )
                        ),
                        self.tema_label
                    ]
                )
            ),
            on_tap=self.toggle_tema
        )

        self.salir_label = ft.Text("Salir", visible=False, size=12, color=ft.colors.WHITE)
        self.boton_salir = ft.GestureDetector(
            content=ft.Container(
                bgcolor=ft.colors.GREY_800,
                padding=10,
                border_radius=8,
                content=ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            bgcolor=ft.colors.WHITE,
                            border_radius=6,
                            padding=6,
                            content=ft.Image(
                                src="button's/exit-button.png",
                                width=20,
                                height=20
                            )
                        ),
                        self.salir_label
                    ]
                )
            ),
            on_tap=self.confirmar_salida
        )

        self.column.controls.append(ft.Container(expand=True))
        self.column.controls.append(self.boton_tema)
        self.column.controls.append(self.boton_salir)
        self.content = self.column

    def toggle_nav(self, e):
        self.expandido = not self.expandido
        self.width = 250 if self.expandido else 80

        img_src = "layout_close-button.png" if self.expandido else "layout_open-button.png"
        self.boton_layout.content.content.controls[0].content.src = f"button's/{img_src}"
        self.layout_label.value = "Comprimir layout" if self.expandido else ""
        self.layout_label.visible = self.expandido
        self.tema_label.visible = self.expandido
        self.tema_label.value = "Cambiar tema"
        self.salir_label.visible = self.expandido

        for item, texto_control, _ in self.icon_containers:
            texto_control.visible = self.expandido

        self.page.update()

    def toggle_tema(self, e):
        self.tema_oscuro = not self.tema_oscuro

        icon_src = "light-color-button.png" if self.tema_oscuro else "dark-color-button.png"
        self.boton_tema.content.content.controls[0].content.src = f"button's/{icon_src}"
        self.bgcolor = ft.colors.BLACK if self.tema_oscuro else ft.colors.WHITE

        for item, texto_control, icono_container in self.icon_containers:
            item.bgcolor = ft.colors.GREY_800 if self.tema_oscuro else ft.colors.GREY_300
            texto_control.color = ft.colors.WHITE if self.tema_oscuro else ft.colors.BLACK
            icono_container.bgcolor = ft.colors.WHITE if self.tema_oscuro else ft.colors.BLACK

        self.tema_label.color = ft.colors.WHITE if self.tema_oscuro else ft.colors.BLACK
        self.layout_label.color = ft.colors.WHITE if self.tema_oscuro else ft.colors.BLACK
        self.salir_label.color = ft.colors.WHITE if self.tema_oscuro else ft.colors.BLACK

        if self.dashboard_view:
            self.dashboard_view.content_area.bgcolor = ft.colors.BLACK if self.tema_oscuro else ft.colors.WHITE
            self.dashboard_view.bgcolor = ft.colors.BLACK if self.tema_oscuro else ft.colors.WHITE

        # Guardar tema en client_storage
        self.page.client_storage.set("tema_oscuro", self.tema_oscuro)

        self.page.update()

    def confirmar_salida(self, e):
        def cerrar_app(ev):
            # Guardar el estado del tema antes de cerrar
            self.page.client_storage.set("tema_oscuro", self.tema_oscuro)
            # Cerrar la aplicación
            self.page.window.destroy()

        def cancelar(ev):
            # Cerrar el diálogo sin realizar ninguna acción adicional
            self.page.dialog.open = False
            self.page.update()

        # Crear el diálogo de confirmación
        self.dialogo_salir = ft.AlertDialog(
            modal=True,
            title=ft.Text("¿Deseas salir de la aplicación?"),
            actions=[
                ft.TextButton("Sí", on_click=cerrar_app),
                ft.TextButton("No", on_click=cancelar)
            ],
            actions_alignment=ft.MainAxisAlignment.CENTER
        )

        # Asignar el diálogo a la página y mostrarlo
        self.page.dialog = self.dialogo_salir
        self.page.dialog.open = True
        self.page.update()





    def navegar(self, destino: str):
        from app.views.dashboard_view import DashboardView
        vista_actual = next((v for v in self.page.views if isinstance(v, DashboardView)), None)
        if vista_actual:
            self.dashboard_view = vista_actual
            vista_actual.update_content(destino)
