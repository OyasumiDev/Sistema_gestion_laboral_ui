# app/helpers/pagos/pagos_repo.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Callable, Iterable, Tuple
from datetime import datetime
import inspect


from app.models.payment_model import PaymentModel
from app.core.app_state import AppState  # CHANGE: publicar eventos a page.pubsub


class PagosRepo:
    """
    Capa de servicios para Pagos.
    - Lecturas planas para DataTable.
    - Confirmación / eliminación / totales.
    - Utilidades de grupos por FECHA (crear/eliminar) con fallbacks seguros.
    - Retry suave en fallos de conexión (re-crea PaymentModel y reintenta 1 vez).
    - Normalización de claves (deposito/pago_deposito, efectivo/pago_efectivo).
    - API tolerante a kwargs ('force', etc.) que solo pasa los aceptados por backend.
    - ⚡ Auto-refresh: invalida caché y notifica listeners tras cualquier cambio.
    - 🧭 Detección de cambios de ESQUEMA y refresh automático.
    """

    # -------------------- Init --------------------
    def __init__(self, payment_model: Optional[PaymentModel] = None):
        self.payment_model = payment_model or PaymentModel()

        # listeners de cambios (para contenedores/UI)
        self._listeners: List[Callable[[str, Dict[str, Any]], None]] = []
        self._version: int = 0  # puedes leerlo para saber si hubo cambios

        # snapshot del esquema para detectar altas/bajas de tablas
        self._schema_sig: Tuple[str, ...] = self._schema_signature()

    # -------------------- Suscripción cambios --------------------
    def add_change_listener(self, fn: Callable[[str, Dict[str, Any]], None]) -> None:
        """Registra una función que se invoca tras cambios de datos/esquema."""
        if callable(fn) and fn not in self._listeners:
            self._listeners.append(fn)

    def remove_change_listener(self, fn: Callable[[str, Dict[str, Any]], None]) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    def get_version(self) -> int:
        """Número que aumenta cada vez que hay cambios relevantes."""
        return self._version

    def _emit_change(self, kind: str, **payload) -> None:
        """Notifica a listeners y sube versión."""
        self._version += 1
        for fn in list(self._listeners):
            try:
                fn(kind, payload)
            except Exception:
                # nunca romper por un listener
                pass
        self._publish_pubsub(kind, payload)  # CHANGE: propagar evento a pubsub global

    def _publish_pubsub(self, kind: str, payload: Dict[str, Any]) -> None:
        # CHANGE: emite un aviso ligero en page.pubsub para contenedores desacoplados
        page = AppState().page
        if not page:
            return
        pubsub = getattr(page, "pubsub", None)
        if not pubsub:
            return
        message = {"kind": kind, **payload}
        try:
            if hasattr(pubsub, "publish"):
                pubsub.publish("pagos:changed", message)
            elif hasattr(pubsub, "send_all"):
                pubsub.send_all("pagos:changed", message)
        except Exception:
            pass

    # -------------------- Utils --------------------
    @staticmethod
    def _is_success(res: Any) -> bool:
        return isinstance(res, dict) and res.get("status") == "success"

    def _table_exists(self, table: str) -> bool:
        """Consulta rápida en information_schema; tolerante a errores."""
        try:
            q = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema=%s AND table_name=%s
            """
            r = self.payment_model.db.get_data(q, (self.payment_model.db.database, table), dictionary=True)
            return int((r or {}).get("c", 0)) > 0
        except Exception:
            return False

    def _schema_signature(self) -> Tuple[str, ...]:
        """
        Huella ligera del esquema relevante: existencia de tablas clave.
        Útil para detectar si se creó/eliminó algo y refrescar UI/cachés.
        """
        # tablas más usadas por la vista/operaciones
        tables = (
            self.payment_model.E.TABLE.value,  # pagos
            "descuentos",
            "detalles_pagos_prestamo",
            "pagos_prestamo",
            "grupos_pagos",
            "empleados",
        )
        sig: List[str] = []
        for t in tables:
            sig.append(f"{t}:{'1' if self._table_exists(t) else '0'}")
        return tuple(sig)

    def _refresh_if_schema_changed(self) -> None:
        """Si detecta cambios de tablas, limpia cachés y notifica."""
        try:
            new_sig = self._schema_signature()
            if new_sig != self._schema_sig:
                self._schema_sig = new_sig
                # limpiar caches en model si expone helpers
                self._clear_like()
                self._emit_change("schema_changed", signature=new_sig)
        except Exception:
            # no romper las lecturas
            pass

    # -------------------- Infra: retry suave --------------------
    def _try(self, fn: Callable, *args, **kwargs):
        """
        Ejecuta fn con un reintento si hay excepción (re-crea model/conn).
        Devuelve el resultado original de fn o dict de error.
        Además, si el fallo suena a esquema → fuerza verificación/creación mínima.
        """
        try:
            out = fn(*args, **kwargs)
            # tras una llamada, revisar esquema (por si hubo migrations fuera)
            self._refresh_if_schema_changed()
            return out
        except Exception:
            # reintento reconstruyendo modelo/conexión
            try:
                # algunos modelos tienen utilidades de chequeo/creación
                # garantizamos al menos la tabla principal y grupos
                self.payment_model = PaymentModel()
                # si existen estos métodos, ejecútalos (idempotentes)
                try:
                    self.payment_model.check_table()
                except Exception:
                    pass
                try:
                    self.payment_model._ensure_grupos_table()
                except Exception:
                    pass

                out = fn(*args, **kwargs)
                self._refresh_if_schema_changed()
                return out
            except Exception as ex2:
                return {"status": "error", "message": f"Falla de conexión/operación: {ex2}"}

    # Solo pasa kwargs que la firma del destino acepte
    @staticmethod
    def _call_maybe_kwargs(fn: Callable, *args, **kwargs):
        if not callable(fn):
            return {"status": "error", "message": "Operación no disponible"}
        try:
            sig = inspect.signature(fn)
            accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
            return fn(*args, **accepted)
        except Exception as ex:
            return {"status": "error", "message": str(ex)}

    # -------------------- Normalización --------------------
    @staticmethod
    def _normalize_row_keys(row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Asegura que existan ambas claves equivalentes:
        - deposito  <-> pago_deposito
        - efectivo  <-> pago_efectivo
        (sin pisar valores ya presentes)
        """
        if "deposito" in row and "pago_deposito" not in row:
            row["pago_deposito"] = row["deposito"]
        if "pago_deposito" in row and "deposito" not in row:
            row["deposito"] = row["pago_deposito"]

        if "efectivo" in row and "pago_efectivo" not in row:
            row["pago_efectivo"] = row["efectivo"]
        if "pago_efectivo" in row and "efectivo" not in row:
            row["efectivo"] = row["pago_efectivo"]

        return row

    @classmethod
    def _normalize_list(cls, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [cls._normalize_row_keys(dict(r or {})) for r in (rows or [])]

    # -------------------- Filtros/orden opcionales --------------------
    @staticmethod
    def _parse_id_query(text: str) -> List[int]:
        """
        Parsea expresiones tipo '1,3,5-9' -> [1,3,5,6,7,8,9]
        """
        out: List[int] = []
        if not text:
            return out
        for token in (t.strip() for t in text.split(",") if t.strip()):
            if "-" in token:
                a, b = token.split("-", 1)
                try:
                    ia, ib = int(a), int(b)
                    if ia <= ib:
                        out.extend(range(ia, ib + 1))
                except Exception:
                    continue
            else:
                try:
                    out.append(int(token))
                except Exception:
                    continue
        return out

    # -------------------- Lecturas básicas ----------------------
    def listar_pagos(
        self,
        order_desc: bool = True,
        *,
        sort_key: Optional[str] = None,
        sort_asc: bool = True,
        filtros: Optional[Dict[str, str]] = None,
        compute_total: Optional[Callable[[Dict[str, Any]], float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Devuelve lista plana de pagos normalizados.
        - `order_desc`: orden por (fecha_pago, numero_nomina) descendente por defecto.
        - `sort_key`: si se indica ('id_pago', 'id_empleado', 'monto_base', 'total'), se aplica.
        - `sort_asc`: dirección para `sort_key`.
        - `filtros`: dict opcional {'id_empleado': '...', 'id_pago': '...', 'estado': '...'}.
        - `compute_total`: callback opcional para ordenar por 'total' si se solicita.
        """
        # antes de leer, detecta si el esquema cambió (alta/baja de tablas)
        self._refresh_if_schema_changed()

        rs = self._try(self.payment_model.get_all_pagos)
        if not isinstance(rs, dict) or rs.get("status") != "success":
            return []
        rows = self._normalize_list(rs.get("data", []) or [])

        # --- filtros simples (si se piden) ---
        filtros = filtros or {}
        id_emp = (filtros.get("id_empleado") or "").strip()
        id_pago_q = (filtros.get("id_pago") or filtros.get("id_pago_conf") or "").strip()
        estado = (filtros.get("estado") or "").strip().lower()

        if estado:
            rows = [r for r in rows if str(r.get("estado", "")).lower() == estado]

        ids_filtrados = set(self._parse_id_query(id_pago_q)) if id_pago_q else set()
        if ids_filtrados:
            rows = [
                r for r in rows
                if int(r.get("id_pago_nomina") or r.get("id_pago") or 0) in ids_filtrados
            ]
        elif id_emp:
            rows = [r for r in rows if str(r.get("numero_nomina") or "").startswith(id_emp)]

        # --- ordenación ---
        if sort_key:
            asc = bool(sort_asc)

            def key_fn(r: Dict[str, Any]):
                if sort_key == "id_pago":
                    return int(r.get("id_pago_nomina") or r.get("id_pago") or 0)
                if sort_key == "id_empleado":
                    return int(r.get("numero_nomina") or 0)
                if sort_key == "monto_base":
                    return float(r.get("monto_base") or 0.0)
                if sort_key == "total":
                    if compute_total:
                        try:
                            return float(compute_total(r))
                        except Exception:
                            return float(r.get("monto_total") or 0.0)
                    return float(r.get("monto_total") or 0.0)
                # Fallback: fecha_pago, numero_nomina
                return (str(r.get("fecha_pago") or ""), int(r.get("numero_nomina") or 0))

            rows.sort(key=key_fn, reverse=not asc)
        else:
            rows.sort(
                key=lambda x: (str(x.get("fecha_pago") or ""), int(x.get("numero_nomina") or 0)),
                reverse=bool(order_desc),
            )

        return rows

    def refresh_from_assistance(
        self,
        periodo_ini: str,
        periodo_fin: str,
        id_empleado: Optional[int] = None,
        *,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        # CHANGE: delega al PaymentModel y emite eventos de actualización
        resumen = self._try(
            self.payment_model.refresh_from_assistance,
            periodo_ini,
            periodo_fin,
            id_empleado=id_empleado,
            overwrite=overwrite,
        )
        if isinstance(resumen, dict):
            if resumen.get("creados", 0) or resumen.get("actualizados", 0) or resumen.get("requires_overwrite"):
                self._after_change("refresh_from_assistance", resumen=resumen)
        return resumen if isinstance(resumen, dict) else {}

    def restore_green_dates(
        self,
        periodo_ini: str,
        periodo_fin: str,
        id_empleado: Optional[int] = None,
        *,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        # CHANGE: reconstruye pagos auto-generados faltantes tras eliminaciones
        resumen = self._try(
            self.payment_model.restore_green_dates,
            periodo_ini,
            periodo_fin,
            id_empleado=id_empleado,
            overwrite=overwrite,
        )
        if isinstance(resumen, dict):
            if resumen.get("creados", 0) or resumen.get("actualizados", 0) or resumen.get("requires_overwrite"):
                self._after_change("restore_green_dates", resumen=resumen)
        return resumen if isinstance(resumen, dict) else {}

    def obtener_pago(self, id_pago: int) -> Optional[Dict[str, Any]]:
        # si el esquema cambió desde la última vez, refresca caches
        self._refresh_if_schema_changed()
        rs = self._try(self.payment_model.get_by_id, id_pago)
        if isinstance(rs, dict) and rs.get("status") == "success":
            return self._normalize_row_keys(rs["data"])
        return None

    # -------------------- Acciones (mutaciones) ------------------------------
    def _after_change(self, kind: str, **payload) -> None:
        """
        Lógica común post-mutación:
        - Invalida cachés del modelo.
        - Revisa esquema (por si la operación lo creó/eliminó).
        - Emite evento de cambio para que la UI se recargue.
        """
        self._clear_like()
        self._refresh_if_schema_changed()
        self._emit_change(kind, **payload)

    def confirmar_pago(self, id_pago: int) -> Dict[str, Any]:
        res = self._try(self.payment_model.confirmar_pago, id_pago)
        if self._is_success(res):
            self._after_change("confirmar_pago", id_pago=id_pago)
        return res

    def eliminar_pago(self, id_pago: int, **kwargs) -> Dict[str, Any]:
        """
        Elimina un pago. Acepta kwargs opcionales (p.ej. force=True) y
        los pasa solo si el backend los soporta.
        """
        fn = getattr(self.payment_model, "eliminar_pago", None)
        res = self._try(self._call_maybe_kwargs, fn, id_pago, **kwargs)
        if self._is_success(res):
            self._after_change("eliminar_pago", id_pago=id_pago)
        return res

    # ---- Grupos por fecha ----
    def crear_grupo_pagado(self, fecha: str, **kwargs) -> Dict[str, Any]:
        """
        Crea un grupo 'pagado' VACÍO para la fecha.
        - No mueve pendientes.
        - No confirma pagos.
        - Si el backend soporta grupos, delega; si no, hace no-op seguro.
        """
        pm = self.payment_model

        # Backend nativo (si existe): intentamos pasar un indicio de "crear_vacio"
        if hasattr(pm, "crear_grupo_pagado"):
            res = self._try(self._call_maybe_kwargs, pm.crear_grupo_pagado, fecha, crear_vacio=True, **kwargs)
            if self._is_success(res):
                self._after_change("crear_grupo_pagado", fecha=fecha)
            return res

        # Fallback: validar fecha y "simular" creación (no toca pagos)
        try:
            _ = datetime.strptime(fecha, "%Y-%m-%d")
        except Exception:
            return {"status": "error", "message": "Formato de fecha inválido (usa YYYY-MM-DD)."}

        self._after_change("crear_grupo_pagado_fallback", fecha=fecha)
        return {"status": "success", "message": f"Grupo creado (vacío) para {fecha}."}

    def eliminar_grupo_por_fecha(self, fecha: str, **kwargs) -> Dict[str, Any]:
        """
        Elimina un grupo por FECHA (solo el grupo), sin mover ni tocar pagos.
        - Si el grupo está vacío, lo borra.
        - Si hay pagos ya 'pagados' en esa fecha, backend debe bloquear.
        """
        pm = self.payment_model

        # Backend nativo
        if hasattr(pm, "eliminar_grupo_por_fecha"):
            res = self._try(self._call_maybe_kwargs, pm.eliminar_grupo_por_fecha, fecha, **kwargs)
            if self._is_success(res):
                self._after_change("eliminar_grupo", fecha=fecha)
            return res

        # Fallback
        try:
            _ = datetime.strptime(fecha, "%Y-%m-%d")
        except Exception:
            return {"status": "error", "message": "Formato de fecha inválido (usa YYYY-MM-DD)."}

        self._after_change("eliminar_grupo_fallback", fecha=fecha)
        return {"status": "success", "message": f"Grupo eliminado (si existía) para {fecha}."}

    def cerrar_grupo(self, grupo_pago: str) -> Dict[str, Any]:
        res = self._try(self.payment_model.cerrar_grupo, grupo_pago)
        if self._is_success(res):
            self._after_change("cerrar_grupo", grupo_pago=grupo_pago)
        return res

    def reabrir_grupo(self, grupo_pago: str) -> Dict[str, Any]:
        res = self._try(self.payment_model.reabrir_grupo, grupo_pago)
        if self._is_success(res):
            self._after_change("reabrir_grupo", grupo_pago=grupo_pago)
        return res

    # -------------------- Totales / fechas auxiliares ---------------------
    def total_pagado_confirmado(self) -> float:
        try:
            q = f"""
            SELECT IFNULL(SUM({self.payment_model.E.MONTO_TOTAL.value}), 0) AS t
            FROM {self.payment_model.E.TABLE.value}
            WHERE {self.payment_model.E.ESTADO.value}='pagado'
            """
            r = self.payment_model.db.get_data(q, dictionary=True)
            return float((r or {}).get("t", 0) or 0.0)
        except Exception:
            return 0.0

    def get_fechas_pagadas(self) -> List[str]:
        """Fechas (YYYY-MM-DD) con pagos confirmados."""
        self._refresh_if_schema_changed()
        if hasattr(self.payment_model, "get_fechas_pagadas"):
            rs = self._try(self.payment_model.get_fechas_pagadas)
            return list(rs or [])
        try:
            q = f"""
            SELECT DISTINCT {self.payment_model.E.FECHA_PAGO.value} AS f
            FROM {self.payment_model.E.TABLE.value}
            WHERE {self.payment_model.E.ESTADO.value}='pagado'
            """
            rows = self.payment_model.db.get_data_list(q, dictionary=True) or []
            return [str(r["f"]) for r in rows if r and r.get("f")]
        except Exception:
            return []

    def get_fechas_pendientes(self) -> List[str]:
        """Fechas (YYYY-MM-DD) con pagos pendientes."""
        self._refresh_if_schema_changed()
        if hasattr(self.payment_model, "get_fechas_pendientes"):
            rs = self._try(self.payment_model.get_fechas_pendientes)
            return list(rs or [])
        try:
            q = f"""
            SELECT DISTINCT {self.payment_model.E.FECHA_PAGO.value} AS f
            FROM {self.payment_model.E.TABLE.value}
            WHERE {self.payment_model.E.ESTADO.value}='pendiente'
            """
            rows = self.payment_model.db.get_data_list(q, dictionary=True) or []
            return [str(r["f"]) for r in rows if r and r.get("f")]
        except Exception:
            return []

    # -------------------- Grupos (por token existente) ----------
    def listar_grupos(self) -> List[Dict[str, Any]]:
        self._refresh_if_schema_changed()
        try:
            return self.payment_model.get_grupos_pagos()
        except Exception:
            return []

    def listar_pagos_por_grupo(self, grupo_pago: str, *, order: str = "fecha_desc") -> List[Dict[str, Any]]:
        self._refresh_if_schema_changed()
        rows = self._normalize_list(self.payment_model.get_pagos_por_grupo(grupo_pago) or [])
        if order == "fecha_desc":
            rows.sort(key=lambda x: (str(x.get("fecha_pago") or ""), int(x.get("numero_nomina") or 0)), reverse=True)
        elif order == "fecha_asc":
            rows.sort(key=lambda x: (str(x.get("fecha_pago") or ""), int(x.get("numero_nomina") or 0)))
        elif order == "empleado_asc":
            rows.sort(key=lambda x: (str(x.get("nombre_completo") or ""), str(x.get("fecha_pago") or "")))
        elif order == "empleado_desc":
            rows.sort(key=lambda x: (str(x.get("nombre_completo") or ""), str(x.get("fecha_pago") or "")), reverse=True)
        return rows

    # -------------------- Cachés (para que el Container pueda llamar) ----
    def invalidate_cache(self):
        """Compat: algunos contenedores llaman a este nombre."""
        self._clear_like()
        self._refresh_if_schema_changed()
        self._emit_change("invalidate_cache")

    def clear_cache(self):
        self.invalidate_cache()

    def refresh_cache(self):
        self.invalidate_cache()

    def reset_cache(self):
        self.invalidate_cache()

    def _clear_like(self):
        for nm in ("invalidate_cache", "clear_cache", "reset_cache", "refresh_cache"):
            fn = getattr(self.payment_model, nm, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
