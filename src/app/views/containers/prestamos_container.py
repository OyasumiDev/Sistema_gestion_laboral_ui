# app/views/containers/prestamos_container.py
import flet as ft
from datetime import date
from typing import List

from app.core.app_state import AppState
from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.views.containers.modal_alert import ModalAlert
from app.core.enums.e_prestamos_model import E_PRESTAMOS
from app.core.enums.e_pagos_prestamos import E_PAGOS_PRESTAMO as EP

from app.helpers.prestamos_helper.prestamos_row_helper import PrestamosRowHelper
from app.helpers.prestamos_helper.pagos_prestamos_row_helper import PagosPrestamosRowHelper
from app.helpers.prestamos_helper.prestamos_validation_helper import PrestamosValidationHelper
from app.helpers.prestamos_helper.prestamos_scroll_helper import PrestamosScrollHelper

# BotonFactory (uniformidad con Empleados)
from app.helpers.boton_factory import (
    crear_boton_importar,
    crear_boton_exportar,
)

# Modal de pagos de préstamos (solo pagos reales)
from app.views.containers.modal_pagos_prestamos import ModalPrestamos


class PrestamosContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20)

        # Estado / modelos
        self.page = AppState().page
        self.loan_model = LoanModel()
        self.loan_payment_model = LoanPaymentModel()
        self.E = E_PRESTAMOS

        # Helpers
        self.validador = PrestamosValidationHelper()
        self.row_helper = PrestamosRowHelper(actualizar_callback=self._actualizar_vista)
        self.pago_helper = PagosPrestamosRowHelper()

        # Estado UI
        self.datos_tabla: dict[str, List[ft.Control]] = {}   # filas temporales (ej. "prestamos_global")
        self._pending_scroll_key: str | None = None

        # === NUEVO: filtros y orden ===
        self.filters = {"id_empleado": "", "id_prestamo": ""}  # prefijos; priorizan sin excluir
        self.sort_key = "numero"   # numero | nombre | fecha | saldo | monto
        self.sort_asc = True
        self._tf_empleado: ft.TextField | None = None
        self._tf_prestamo: ft.TextField | None = None
        self._dd_sort: ft.Dropdown | None = None
        self._btn_dir: ft.IconButton | None = None

        # Layout raíz
        self.layout = ft.Column(expand=True)
        self._build()
        self._actualizar_vista()

    # ---------------------------------------------------------------------
    # UI base
    # ---------------------------------------------------------------------
    def _build(self):
        # Columna scrollable donde se insertan los tiles
        self.tiles_column = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

        # Barra superior (uniforme con Empleados)
        top_bar = ft.Row(
            spacing=10,
            alignment=ft.MainAxisAlignment.START,
            controls=[
                crear_boton_importar(self._importar),
                crear_boton_exportar(self._exportar),
                self._build_add_global_button(),
                ft.Container(width=12),
                # === NUEVO: filtros/orden ===
                self._build_filters_toolbar(),
            ],
        )

        self.layout.controls = [
            ft.Text("ÁREA DE PRÉSTAMOS", style=ft.TextThemeStyle.TITLE_MEDIUM),
            top_bar,
            ft.Divider(height=1),
            self.tiles_column,
        ]
        self.content = self.layout

    def _build_add_global_button(self) -> ft.GestureDetector:
        return ft.GestureDetector(
            on_tap=lambda _: self._agregar_prestamo_global(),
            content=ft.Container(
                padding=8,
                border_radius=12,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=ft.Row(
                    [
                        ft.Icon(ft.icons.ADD_CIRCLE_OUTLINED, size=20),
                        ft.Text("Agregar préstamo global", size=11, weight="bold"),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=5,
                ),
            ),
        )

    # === NUEVO: toolbar de filtros/orden ===
    def _build_filters_toolbar(self) -> ft.Row:
        self._tf_empleado = ft.TextField(
            label="Filtrar No. nómina (prefijo)", width=190, dense=True,
            on_change=lambda e: self._on_change_filters(id_empleado=e.control.value)
        )
        self._tf_prestamo = ft.TextField(
            label="Filtrar ID préstamo (prefijo)", width=200, dense=True,
            on_change=lambda e: self._on_change_filters(id_prestamo=e.control.value)
        )
        self._dd_sort = ft.Dropdown(
            label="Ordenar por", width=180, dense=True,
            value=self.sort_key,
            options=[
                ft.dropdown.Option(text="No. nómina", key="numero"),
                ft.dropdown.Option(text="Nombre", key="nombre"),
                ft.dropdown.Option(text="Fecha reciente", key="fecha"),
                ft.dropdown.Option(text="Saldo total", key="saldo"),
                ft.dropdown.Option(text="Monto total", key="monto"),
            ],
            on_change=lambda e: self._on_change_sort(key=e.control.value)
        )
        self._btn_dir = ft.IconButton(
            icon=ft.icons.ARROW_UPWARD if self.sort_asc else ft.icons.ARROW_DOWNWARD,
            tooltip="Alternar asc/desc",
            on_click=lambda e: self._on_change_sort(dir_toggle=True)
        )
        return ft.Row(spacing=10, controls=[self._tf_empleado, self._tf_prestamo, self._dd_sort, self._btn_dir])

    def _on_change_filters(self, *, id_empleado: str | None = None, id_prestamo: str | None = None):
        if id_empleado is not None:
            self.filters["id_empleado"] = (id_empleado or "").strip()
        if id_prestamo is not None:
            self.filters["id_prestamo"] = (id_prestamo or "").strip()
        self._actualizar_vista()

    def _on_change_sort(self, *, key: str | None = None, dir_toggle: bool = False):
        if key:
            self.sort_key = key
        if dir_toggle:
            self.sort_asc = not self.sort_asc
            if isinstance(self._btn_dir, ft.IconButton):
                self._btn_dir.icon = ft.icons.ARROW_UPWARD if self.sort_asc else ft.icons.ARROW_DOWNWARD
        self._safe_refresh()
        self._actualizar_vista()

    def _safe_refresh(self):
        try:
            if getattr(self.layout, "page", None) is not None:
                self.layout.update()
        except Exception:
            pass
        try:
            if self.page is not None:
                self.page.update()
        except Exception:
            pass

    # ---------------------------------------------------------------------
    # Render jerárquico
    # ---------------------------------------------------------------------
    def _actualizar_vista(self):
        tiles: List[ft.Control] = []

        resultado = self.loan_model.get_agrupado_por_empleado()
        if resultado.get("status") != "success":
            ModalAlert.mostrar_info("Error", resultado.get("message", "No se pudieron cargar los préstamos"))
            self._safe_refresh()
            return

        grupos = resultado.get("data", []) or []
        grupos = self._apply_filters_y_sort_grupos(grupos)  # <--- NUEVO

        if not grupos:
            tiles.append(
                ft.Container(
                    content=ft.Text(
                        "No hay préstamos registrados. Usa 'Agregar préstamo global' o agrega desde el empleado.",
                        size=12,
                        color=ft.colors.GREY_700,
                    ),
                    padding=10,
                )
            )

        # Aliases del enum
        P = self.E
        K_ID = P.PRESTAMO_ID.value
        K_NUM = P.PRESTAMO_NUMERO_NOMINA.value
        K_NOM = P.PRESTAMO_NOMBRE_EMPLEADO.value
        K_MONTO = P.PRESTAMO_MONTO.value
        K_SALDO = P.PRESTAMO_SALDO.value
        K_ESTADO = P.PRESTAMO_ESTADO.value
        K_FECHA = P.PRESTAMO_FECHA_SOLICITUD.value

        for grupo in grupos:
            numero = grupo.get("numero_nomina")
            nombre = grupo.get("nombre_empleado", "") or ""
            prestamos = self._sort_prestamos_en_grupo(grupo.get("prestamos", []) or [])  # <--- NUEVO

            prestamos_tiles: List[ft.Control] = []
            for p in prestamos:
                id_prestamo = p.get(K_ID)

                # Historial de pagos del préstamo
                pagos_res = self.loan_payment_model.get_by_prestamo(id_prestamo)
                pagos = pagos_res.get("data", []) if (isinstance(pagos_res, dict) and pagos_res.get("status") == "success") else []

                # Total pagado robusto (acepta float/str con coma/punto)
                total_pagado = 0.0
                for row in pagos:
                    raw = row.get(EP.PAGO_MONTO_PAGADO.value, row.get("monto_pagado", 0))
                    try:
                        if isinstance(raw, str):
                            raw = raw.strip().replace(",", ".")
                        total_pagado += float(raw or 0)
                    except Exception:
                        pass

                editable_pagos = (str(p.get(K_ESTADO, "")).lower() != "terminado")

                # Lista estable (sin DataTable)
                lista_pagos = self.pago_helper.build_list(
                    pagos=pagos,
                    editable=editable_pagos,
                    on_edit=None,  # no se edita historial por ahora
                    on_delete=lambda pago, pid=id_prestamo, num=numero: self._confirmar_eliminar_pago(pago, pid, num),
                    max_height=260,
                )

                # Registro para la fila resumen del préstamo
                registro_ui = {
                    "id_prestamo": id_prestamo,
                    "numero_nomina": p.get(K_NUM),
                    "nombre_empleado": p.get(K_NOM, nombre) or nombre,
                    "monto": f"{self._to_float(p.get(K_MONTO, 0)):,.2f}",
                    "saldo": f"{self._to_float(p.get(K_SALDO, 0)):,.2f}",
                    "pagado": f"{total_pagado:.2f}",
                    "estado": p.get(K_ESTADO, ""),
                    "fecha_solicitud": p.get(K_FECHA, ""),
                }

                fila_prestamo = self.row_helper.build_fila_lectura(
                    registro=registro_ui,
                    on_edit=(lambda pr=p: self._editar_prestamo(pr)),
                    on_delete=(lambda pr=p: self._eliminar_prestamo(pr[K_ID])),
                    # Abrimos el modal desde “Ver pagos”
                    on_pagos=(lambda pr=p, num=numero: self._ver_pagos_de_prestamo(pr, num)),
                )

                prestamos_tiles.append(
                    ft.ExpansionTile(
                        title=ft.Text(f"Préstamo ID {id_prestamo}"),
                        maintain_state=True,
                        controls=[fila_prestamo, lista_pagos],
                    )
                )

            # Acción “Agregar préstamo” para el empleado
            btn_agregar_prestamo = ft.GestureDetector(
                on_tap=lambda _, num=numero: self._agregar_prestamo_a_empleado(num),
                content=ft.Container(
                    padding=6,
                    border_radius=10,
                    bgcolor=ft.colors.SURFACE_VARIANT,
                    content=ft.Row(
                        [ft.Icon(ft.icons.ADD, size=18), ft.Text("Agregar préstamo", size=11, weight="bold")],
                        spacing=6,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ),
            )

            tiles.append(
                ft.ExpansionTile(
                    title=ft.Text(f"{nombre} - No. {numero}"),
                    maintain_state=True,
                    controls=[btn_agregar_prestamo] + prestamos_tiles,
                )
            )

        # Tile temporal de “préstamo global”
        if self.datos_tabla.get("prestamos_global"):
            tiles.append(
                ft.ExpansionTile(
                    title=ft.Text("Nuevo préstamo global"),
                    maintain_state=True,
                    initially_expanded=True,
                    controls=self.datos_tabla["prestamos_global"],
                )
            )

        self.tiles_column.controls = tiles
        self._safe_refresh()

        # Scroll post-refresh
        scroll_key = self._pending_scroll_key
        if not scroll_key and self.datos_tabla.get("prestamos_global"):
            scroll_key = "grupo_prestamos_global"
        if scroll_key:
            PrestamosScrollHelper.scroll_to_group_after_build(self.page, scroll_key, delay=0.1, retries=30)
            self._pending_scroll_key = None

    # ---------------------------------------------------------------------
    # Crear / Guardar préstamo
    # ---------------------------------------------------------------------
    def _agregar_prestamo_global(self, _=None):
        grupo = "prestamos_global"
        scroll_key = f"grupo_{grupo}"
        page = self.page

        self.datos_tabla.setdefault(grupo, [])

        registro = {
            "numero_nomina": "",
            "nombre_empleado": "",
            "monto": "",
            "saldo": "0.00",
            "pagado": "0.00",
            "estado": "pendiente",
            "fecha_solicitud": "",
        }

        campos_ref = {}

        def on_save():
            self._guardar_fila_desde_campos(grupo, fila_nueva, campos_ref)

        def on_cancel():
            try:
                self.datos_tabla[grupo].remove(fila_nueva)
            except ValueError:
                pass
            self._actualizar_vista()

        fila_nueva = self.row_helper.build_fila_nueva(
            registro=registro,
            on_save=on_save,
            on_cancel=on_cancel,
            page=page,
            scroll_key=scroll_key,
            campos_ref=campos_ref,
            grupo_empleado=None,
        )

        self.datos_tabla[grupo].append(fila_nueva)
        self._pending_scroll_key = scroll_key
        self._actualizar_vista()

    def _agregar_prestamo_a_empleado(self, numero_nomina: int):
        scroll_key = f"prestamos_{numero_nomina}"
        page = self.page
        campos_ref = {}

        registro = {
            "numero_nomina": str(numero_nomina),
            "nombre_empleado": "",
            "monto": "",
            "saldo": "0.00",
            "pagado": "0.00",
            "estado": "pendiente",
            "fecha_solicitud": "",
        }

        def on_save():
            self._guardar_fila_desde_campos(f"nuevo_{numero_nomina}", fila_nueva, campos_ref)

        def on_cancel():
            self._actualizar_vista()

        fila_nueva = self.row_helper.build_fila_nueva(
            registro=registro,
            on_save=on_save,
            on_cancel=on_cancel,
            page=page,
            scroll_key=scroll_key,
            campos_ref=campos_ref,
            grupo_empleado=None,
        )

        # Insertamos arriba para que sea visible inmediato
        self.tiles_column.controls.insert(
            0,
            ft.ExpansionTile(
                title=ft.Text(f"Nuevo préstamo para empleado {numero_nomina}"),
                maintain_state=True,
                initially_expanded=True,
                controls=[fila_nueva],
            ),
        )
        self._pending_scroll_key = scroll_key
        self._safe_refresh()

    def _guardar_fila_desde_campos(self, grupo_key: str, fila_widget: ft.Control, campos_ref: dict):
        numero = (campos_ref.get("numero_nomina").value or "").strip()
        monto_txt = (campos_ref.get("monto").value or "").strip().replace(",", ".")
        fecha_txt = (campos_ref.get("fecha").value or "").strip()

        ok_numero = self.validador.validar_numero_nomina(campos_ref["numero_nomina"])
        ok_monto = self.validador.validar_monto(campos_ref["monto"], limite=10000.0)
        ok_fecha = self.validador.validar_fecha(campos_ref["fecha"])

        if not (ok_numero and ok_monto and ok_fecha):
            ModalAlert.mostrar_info("Error", "Corrige los campos marcados en rojo.")
            return

        try:
            monto = float(monto_txt)
        except Exception:
            ModalAlert.mostrar_info("Error", "Monto inválido.")
            return

        fecha_sql = self.validador.convertir_fecha_mysql(fecha_txt)

        # grupo_empleado automático
        if grupo_key == "prestamos_global":
            grupo_empleado = "GLOBAL"
        elif grupo_key.startswith("nuevo_"):
            grupo_empleado = numero
        else:
            grupo_empleado = numero or "GLOBAL"

        datos = {
            "numero_nomina": int(numero),
            "monto": monto,
            "fecha_solicitud": fecha_sql,
            "grupo_empleado": grupo_empleado,
        }

        res = self._insertar_prestamo(datos)

        if res.get("status") == "success":
            ModalAlert.mostrar_info("Éxito", "Préstamo guardado correctamente.")
            try:
                if grupo_key in self.datos_tabla:
                    self.datos_tabla[grupo_key].remove(fila_widget)
            except ValueError:
                pass
            self._actualizar_vista()
        else:
            ModalAlert.mostrar_info("Error", res.get("message", "No se pudo guardar."))

    def _insertar_prestamo(self, datos: dict) -> dict:
        try:
            numero = int(datos["numero_nomina"])
            monto = float(datos["monto"])
            fecha = datos.get("fecha_solicitud")

            res = self.loan_model.add(
                numero_nomina=numero,
                monto_prestamo=monto,
                saldo_prestamo=None,
                estado="pagando",
                fecha_solicitud=fecha,
            )
            return res if isinstance(res, dict) else {"status": "success", "data": res}
        except Exception as ex:
            return {"status": "error", "message": f"Error al insertar préstamo: {ex}"}

    # ---------------------------------------------------------------------
    # Otras acciones
    # ---------------------------------------------------------------------
    def _editar_prestamo(self, prestamo: dict):
        ModalAlert.mostrar_info("Editar", "Edición no implementada aún en esta vista.")

    def _ver_pagos_de_prestamo(self, prestamo: dict, numero_nomina: int):
        pid = prestamo.get("id_prestamo") or prestamo.get(self.E.PRESTAMO_ID.value)
        if not pid:
            ModalAlert.mostrar_info("Error", "Préstamo inválido.")
            return

        hoy = date.today().strftime("%Y-%m-%d")

        # Modal de pagos REALES (sin lógica de nómina)
        pago_data = {
            "numero_nomina": int(numero_nomina),
            "id_prestamo": int(pid),
            "fecha_generacion": hoy,
            "fecha_pago": hoy,
        }

        def on_confirmar(_):
            self._actualizar_vista()

        modal = ModalPrestamos(pago_data=pago_data, on_confirmar=on_confirmar)
        modal.mostrar()

    def _confirmar_eliminar_pago(self, pago: dict, id_prestamo: int, numero_nomina: int):
        pid = pago.get(EP.ID_PAGO_PRESTAMO.value) or pago.get("id_pago_prestamo")
        if not pid:
            ModalAlert.mostrar_info("Error", "No se pudo determinar el ID del pago.")
            return

        def on_confirm():
            res = self.loan_payment_model.delete_by_id_pago(int(pid))
            if res.get("status") == "success":
                ModalAlert.mostrar_info("Eliminado", f"Pago ID {pid} eliminado correctamente.")
                self._actualizar_vista()
            else:
                ModalAlert.mostrar_info("Error", res.get("message", "No se pudo eliminar el pago."))

        ModalAlert(
            title_text="¿Eliminar pago?",
            message=f"Esta acción no se puede deshacer.\nPago ID: {pid}",
            on_confirm=on_confirm,
        ).mostrar()

    def _importar(self, _):
        ModalAlert.mostrar_info("Importar", "Importación no implementada.")

    def _exportar(self, _):
        ModalAlert.mostrar_info("Exportación", "Exportación no implementada.")

    def _eliminar_prestamo(self, id_prestamo: int):
        res = self.loan_model.delete_by_id_prestamo(id_prestamo)
        if res.get("status") == "success":
            ModalAlert.mostrar_info("Eliminado", "Préstamo eliminado correctamente.")
        else:
            ModalAlert.mostrar_info("Error", res.get("message", "No se pudo eliminar."))
        self._actualizar_vista()

    # ---------------------------------------------------------------------
    # === NUEVO: utilidades para ordenar/priorizar ===
    # ---------------------------------------------------------------------
    @staticmethod
    def _to_float(x) -> float:
        try:
            if isinstance(x, str):
                return float(x.strip().replace(",", "."))
            return float(x or 0)
        except Exception:
            return 0.0

    @staticmethod
    def _to_int(x) -> int:
        try:
            return int(float(str(x).strip()))
        except Exception:
            return 0

    @staticmethod
    def _to_date_ymd(x) -> date:
        try:
            s = (x or "")[:10]
            y, m, d = s.split("-")
            return date(int(y), int(m), int(d))
        except Exception:
            return date.min

    def _grupo_sort_key(self, grupo: dict) -> tuple:
        numero = self._to_int(grupo.get("numero_nomina"))
        nombre = (grupo.get("nombre_empleado") or "").lower()
        prestamos = (grupo.get("prestamos") or [])[:]

        if self.sort_key == "nombre":
            return (nombre, numero)

        if self.sort_key == "fecha":
            fechas = [self._to_date_ymd(p.get(self.E.PRESTAMO_FECHA_SOLICITUD.value) or p.get("fecha_solicitud"))
                      for p in prestamos]
            mx = max(fechas) if fechas else date.min
            return (mx, numero)

        if self.sort_key == "saldo":
            total_saldo = sum(self._to_float(p.get(self.E.PRESTAMO_SALDO.value) or p.get("saldo", 0)) for p in prestamos)
            return (total_saldo, numero)

        if self.sort_key == "monto":
            total_monto = sum(self._to_float(p.get(self.E.PRESTAMO_MONTO.value) or p.get("monto", 0)) for p in prestamos)
            return (total_monto, numero)

        # default: numero
        return (numero, nombre)

    def _prestamo_sort_key(self, p: dict) -> tuple:
        pid = self._to_int(p.get(self.E.PRESTAMO_ID.value) or p.get("id_prestamo"))
        monto = self._to_float(p.get(self.E.PRESTAMO_MONTO.value) or p.get("monto", 0))
        saldo = self._to_float(p.get(self.E.PRESTAMO_SALDO.value) or p.get("saldo", 0))
        fecha = self._to_date_ymd(p.get(self.E.PRESTAMO_FECHA_SOLICITUD.value) or p.get("fecha_solicitud"))

        if self.sort_key == "fecha":
            return (fecha, pid)
        if self.sort_key == "saldo":
            return (saldo, pid)
        if self.sort_key == "monto":
            return (monto, pid)
        if self.sort_key == "nombre":
            # no aplica en préstamo; cae a id
            return (pid, fecha)
        # default numero -> id_prestamo
        return (pid, fecha)

    def _matches_filtros(self, grupo: dict) -> bool:
        ide = (self.filters.get("id_empleado") or "").strip()
        idp = (self.filters.get("id_prestamo") or "").strip()
        if not (ide or idp):
            return False

        ok = False
        if ide:
            ok |= str(grupo.get("numero_nomina") or "").startswith(ide)
        if idp:
            for p in (grupo.get("prestamos") or []):
                pid = str(p.get(self.E.PRESTAMO_ID.value) or p.get("id_prestamo") or "")
                if pid.startswith(idp):
                    ok = True
                    break
        return ok

    def _apply_filters_y_sort_grupos(self, grupos: list[dict]) -> list[dict]:
        # 1) ordenar grupos por clave elegida
        ordered = sorted(grupos, key=self._grupo_sort_key, reverse=not self.sort_asc)
        # 2) priorizar (no excluir) por filtros activos
        matching = [g for g in ordered if self._matches_filtros(g)]
        non_matching = [g for g in ordered if not self._matches_filtros(g)]
        return matching + non_matching

    def _sort_prestamos_en_grupo(self, prestamos: list[dict]) -> list[dict]:
        ordered = sorted(prestamos, key=self._prestamo_sort_key, reverse=not self.sort_asc)
        idp = (self.filters.get("id_prestamo") or "").strip()
        if not idp:
            return ordered
        m = [p for p in ordered if str(p.get(self.E.PRESTAMO_ID.value) or p.get("id_prestamo") or "").startswith(idp)]
        n = [p for p in ordered if p not in m]
        return m + n
