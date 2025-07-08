import flet as ft

class TableColumnBuilder:
    def __init__(self, sort_helper=None, on_edit=None, on_delete=None):
        self.sort_helper = sort_helper
        self.on_edit = on_edit
        self.on_delete = on_delete

    def build_columns(self, columnas_definidas):
        columnas = []

        for titulo, clave in columnas_definidas:
            if self.sort_helper:
                icon = self.sort_helper.get_icon(clave)
                col = ft.DataColumn(
                    ft.Row([
                        ft.Text(titulo),
                        ft.Icon(name=icon, size=14)
                    ], spacing=5),
                    on_sort=lambda e, k=clave: self.sort_helper.toggle_sort(k)
                )
            else:
                col = ft.DataColumn(ft.Text(titulo))
            columnas.append(col)

        # Si hay acciones definidas, se agrega columna extra
        if self.on_edit or self.on_delete:
            columnas.append(ft.DataColumn(ft.Text("Acciones")))

        return columnas
