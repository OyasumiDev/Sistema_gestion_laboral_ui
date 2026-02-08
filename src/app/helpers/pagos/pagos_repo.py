# app/helpers/pagos/pagos_repo.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Callable, Iterable, Tuple
from datetime import datetime
import inspect

from app.models.payment_model import PaymentModel
from app.core.app_state import AppState  # publicar eventos a page.pubsub

try:
    from app.models.descuento_detalles_model import DescuentoDetallesModel
    from app.models.discount_model import DiscountModel
except Exception:  # pragma: no cover
    DescuentoDetallesModel = None  # type: ignore
    DiscountModel = None  # type: ignore


class PagosRepo:
    """
    Capa de servicios para Pagos.

    ✅ Incluye:
    - Lecturas planas para DataTable (normaliza ids, deposito/efectivo).
    - Confirmación / eliminación / grupos.
    - Retry suave: si la conexión cae, recrea PaymentModel y reintenta 1 vez.
    - API tolerante a kwargs (solo pasa los aceptados por la firma).
    - Auto-refresh: invalida caché y notifica listeners + page.pubsub.
    - Detección de cambios de ESQUEMA y refresh automático.
    - ensure_borrador_descuentos(): SOLO crea borrador default (no aplica confirmados).
    - actualizar_montos_ui(): guarda depósito/efectivo/saldo de forma estándar.

    ❌ Importante:
    - Este repo NO aplica descuentos a confirmados.
      Eso lo hace ÚNICAMENTE ModalDescuentos (regla del proyecto).
    """

    def __init__(self, payment_model: Optional[PaymentModel] = None):
        self.payment_model = payment_model or PaymentModel()
        self._listeners: List[Callable[[str, Dict[str, Any]], None]] = []
        self._version: int = 0
        self._schema_sig: Tuple[str, ...] = self._schema_signature()

    # -------------------- Suscripción cambios --------------------
    def add_change_listener(self, fn: Callable[[str, Dict[str, Any]], None]) -> None:
        if callable(fn) and fn not in self._listeners:
            self._listeners.append(fn)

    def remove_change_listener(self, fn: Callable[[str, Dict[str, Any]], None]) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    def get_version(self) -> int:
        return self._version

    def _emit_change(self, kind: str, **payload) -> None:
        self._version += 1
        for fn in list(self._listeners):
            try:
                fn(kind, payload)
            except Exception:
                pass
        self._publish_pubsub(kind, payload)

    def _publish_pubsub(self, kind: str, payload: Dict[str, Any]) -> None:
        try:
            page = AppState().page
        except Exception:
            page = None
        if not page:
            return
        pubsub = getattr(page, "pubsub", None)
        if not pubsub:
            return
        message = {"kind": kind, **(payload or {})}
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
        try:
            q = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema=%s AND table_name=%s
            """
            r = self.payment_model.db.get_data(
                q,
                (self.payment_model.db.database, table),
                dictionary=True,
            )
            return int((r or {}).get("c", 0)) > 0
        except Exception:
            return False

    def _schema_signature(self) -> Tuple[str, ...]:
        try:
            pagos_table = self.payment_model.E.TABLE.value
        except Exception:
            pagos_table = "pagos"

        tables = (
            pagos_table,
            "descuentos",
            "descuento_detalles",
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
        try:
            new_sig = self._schema_signature()
            if new_sig != self._schema_sig:
                self._schema_sig = new_sig
                self._clear_like()
                self._emit_change("schema_changed", signature=new_sig)
        except Exception:
            pass

    # -------------------- Infra: retry suave --------------------
    def _try(self, fn: Callable, *args, **kwargs):
        fn_name = getattr(fn, "__name__", None)
        fn_is_bound_to_pm = getattr(fn, "__self__", None) is self.payment_model

        def _call_current():
            if fn_is_bound_to_pm and fn_name and hasattr(self.payment_model, fn_name):
                return getattr(self.payment_model, fn_name)(*args, **kwargs)
            return fn(*args, **kwargs)

        try:
            out = _call_current()
            self._refresh_if_schema_changed()
            return out
        except Exception:
            try:
                self.payment_model = PaymentModel()
                try:
                    self.payment_model.check_table()
                except Exception:
                    pass
                try:
                    ensure = getattr(self.payment_model, "_ensure_grupos_table", None)
                    if callable(ensure):
                        ensure()
                except Exception:
                    pass

                out = _call_current()
                self._refresh_if_schema_changed()
                return out
            except Exception as ex2:
                return {"status": "error", "message": f"Falla de conexión/operación: {ex2}"}

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
        Asegura equivalencias:
        - id_pago_nomina <-> id_pago
        - deposito <-> pago_deposito
        - efectivo <-> pago_efectivo
        """
        row = dict(row or {})

        # ids
        if "id_pago_nomina" in row and "id_pago" not in row:
            row["id_pago"] = row["id_pago_nomina"]
        if "id_pago" in row and "id_pago_nomina" not in row:
            row["id_pago_nomina"] = row["id_pago"]

        # deposito
        if "deposito" in row and "pago_deposito" not in row:
            row["pago_deposito"] = row["deposito"]
        if "pago_deposito" in row and "deposito" not in row:
            row["deposito"] = row["pago_deposito"]

        # efectivo
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
        out: List[int] = []
        if not text:
            return out
        for token in (t.strip() for t in str(text).split(",") if t.strip()):
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
        self._refresh_if_schema_changed()

        rs = self._try(self.payment_model.get_all_pagos)
        if not isinstance(rs, dict) or rs.get("status") != "success":
            return []

        rows = self._normalize_list(rs.get("data", []) or [])

        filtros = filtros or {}
        id_emp = (filtros.get("id_empleado") or "").strip()
        id_pago_q = (filtros.get("id_pago") or filtros.get("id_pago_conf") or "").strip()
        estado = (filtros.get("estado") or "").strip().lower()

        if estado:
            rows = [r for r in rows if str(r.get("estado", "")).strip().lower() == estado]

        ids_filtrados = set(self._parse_id_query(id_pago_q)) if id_pago_q else set()
        if ids_filtrados:
            rows = [r for r in rows if int(r.get("id_pago_nomina") or 0) in ids_filtrados]
        elif id_emp:
            rows = [r for r in rows if str(r.get("numero_nomina") or "").startswith(id_emp)]

        if sort_key:
            asc = bool(sort_asc)

            def key_fn(r: Dict[str, Any]):
                if sort_key == "id_pago":
                    return int(r.get("id_pago_nomina") or 0)
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
                return (str(r.get("fecha_pago") or ""), int(r.get("numero_nomina") or 0))

            rows.sort(key=key_fn, reverse=not asc)
        else:
            rows.sort(
                key=lambda x: (str(x.get("fecha_pago") or ""), int(x.get("numero_nomina") or 0)),
                reverse=bool(order_desc),
            )

        return rows

    def obtener_pago(self, id_pago: int) -> Optional[Dict[str, Any]]:
        self._refresh_if_schema_changed()
        rs = self._try(self.payment_model.get_by_id, id_pago)
        if isinstance(rs, dict) and rs.get("status") == "success":
            return self._normalize_row_keys(rs.get("data") or {})
        return None

    # -------------------- Guardado de montos UI (dep/efectivo/saldo) --------------------
    def actualizar_montos_ui(self, id_pago: int, cambios: Dict[str, Any]) -> Dict[str, Any]:
        try:
            id_pago = int(id_pago)
            if id_pago <= 0:
                return {"status": "error", "message": "id_pago inválido."}
            if not isinstance(cambios, dict) or not cambios:
                return {"status": "error", "message": "Cambios vacíos."}

            # seguridad: NO tocar pagados desde este flujo
            p = self.obtener_pago(id_pago) or {}
            st = str(p.get("estado") or "").strip().lower()
            if st == "pagado":
                return {"status": "error", "message": "El pago ya está pagado; no se permite editar montos."}

            res = self._try(self.payment_model.update_pago, id_pago, cambios)
            if res is True:
                self._after_change("actualizar_montos_ui", id_pago=id_pago, cambios=cambios)
                return {"status": "success", "message": "Montos actualizados."}
            if self._is_success(res):
                self._after_change("actualizar_montos_ui", id_pago=id_pago, cambios=cambios)
                return res
            return res if isinstance(res, dict) else {"status": "error", "message": "Respuesta inválida"}
        except Exception as ex:
            return {"status": "error", "message": str(ex)}

    # -------------------- Descuentos (borrador) --------------------
    def ensure_borrador_descuentos(self, id_pago: int) -> Dict[str, Any]:
        """
        Garantiza que un pago PENDIENTE tenga borrador de descuentos para el modal.

        NOTA: Este método SOLO crea borrador default.
        Aplicar a confirmados y recalcular pago se hace SOLO en ModalDescuentos.
        """
        p = self.obtener_pago(id_pago)
        if not p:
            return {"status": "error", "message": "Pago no encontrado."}

        estado = str(p.get("estado") or "").strip().lower()
        if estado != "pendiente":
            return {"status": "noop", "message": "No aplica: el pago no está pendiente."}

        pm = self.payment_model
        detalles = getattr(pm, "detalles_desc_model", None)
        discount_model = getattr(pm, "discount_model", None)

        if detalles is None and DescuentoDetallesModel:
            try:
                detalles = DescuentoDetallesModel()
            except Exception:
                detalles = None
        if discount_model is None and DiscountModel:
            try:
                discount_model = DiscountModel()
            except Exception:
                discount_model = None

        if not detalles or not discount_model:
            return {"status": "warning", "message": "Modelos de descuentos no disponibles."}

        # Si ya hay descuentos confirmados, no crear defaults
        try:
            fn_has = getattr(discount_model, "tiene_descuentos_guardados", None)
            if callable(fn_has) and bool(fn_has(int(id_pago))):
                return {"status": "noop", "message": "Ya existen descuentos confirmados."}
        except Exception:
            pass

        # Si ya hay borrador, no tocar
        try:
            det = detalles.obtener_por_id_pago(int(id_pago))
            if det:
                return {"status": "noop", "message": "Borrador ya existe."}
        except Exception:
            return {"status": "warning", "message": "No se pudo verificar borrador (lectura falló)."}

        # payload sin meter 0.0 cuando no aplica (coherente con ModalDescuentos)
        try:
            default_imss = float(getattr(detalles, "DEFAULT_IMSS", 50.0))
            default_trans = float(getattr(detalles, "DEFAULT_TRANSPORTE", 100.0))

            payload = {
                getattr(detalles, "COL_APLICADO_IMSS"): True,
                getattr(detalles, "COL_MONTO_IMSS"): default_imss,

                getattr(detalles, "COL_APLICADO_TRANSPORTE"): True,
                getattr(detalles, "COL_MONTO_TRANSPORTE"): default_trans,

                getattr(detalles, "COL_APLICADO_EXTRA"): False,
                getattr(detalles, "COL_MONTO_EXTRA"): None,
                getattr(detalles, "COL_DESCRIPCION_EXTRA"): None,
            }

            res = detalles.upsert_detalles(int(id_pago), payload) or {"status": "error", "message": "upsert sin respuesta"}
            if isinstance(res, dict) and res.get("status") == "success":
                self._after_change("ensure_borrador_descuentos", id_pago=int(id_pago))
            return res if isinstance(res, dict) else {"status": "error", "message": "Respuesta inválida"}
        except Exception as ex:
            return {"status": "error", "message": f"No se pudo crear borrador: {ex}"}

    # -------------------- Acciones (mutaciones) ------------------------------
    def _after_change(self, kind: str, **payload) -> None:
        self._clear_like()
        self._refresh_if_schema_changed()
        self._emit_change(kind, **payload)

    def confirmar_pago(self, id_pago: int) -> Dict[str, Any]:
        res = self._try(self.payment_model.confirmar_pago, id_pago)
        if self._is_success(res):
            self._after_change("confirmar_pago", id_pago=id_pago)
        return res if isinstance(res, dict) else {"status": "error", "message": "Respuesta inválida"}

    def eliminar_pago(self, id_pago: int, **kwargs) -> Dict[str, Any]:
        fn = getattr(self.payment_model, "eliminar_pago", None)
        res = self._try(self._call_maybe_kwargs, fn, id_pago, **kwargs)
        if self._is_success(res):
            self._after_change("eliminar_pago", id_pago=id_pago)
        return res if isinstance(res, dict) else {"status": "error", "message": "Respuesta inválida"}

    # ---- Grupos por fecha ----
    def crear_grupo_pagado(self, fecha: str, **kwargs) -> Dict[str, Any]:
        pm = self.payment_model

        # Flujo UI "Agregar fecha pagada": crear grupo VACIO sin tocar pagos.
        if hasattr(pm, "crear_grupo_pagado_vacio"):
            res = self._try(self._call_maybe_kwargs, pm.crear_grupo_pagado_vacio, fecha, **kwargs)
            if self._is_success(res):
                self._after_change("crear_grupo_pagado", fecha=fecha)
            return res if isinstance(res, dict) else {"status": "error", "message": "Respuesta inválida"}

        if hasattr(pm, "crear_grupo_pagado"):
            res = self._try(self._call_maybe_kwargs, pm.crear_grupo_pagado, fecha, crear_vacio=True, **kwargs)
            if self._is_success(res):
                self._after_change("crear_grupo_pagado", fecha=fecha)
            return res if isinstance(res, dict) else {"status": "error", "message": "Respuesta inválida"}

        try:
            _ = datetime.strptime(str(fecha).strip(), "%Y-%m-%d")
        except Exception:
            return {"status": "error", "message": "Formato de fecha inválido (usa YYYY-MM-DD)."}

        self._after_change("crear_grupo_pagado_fallback", fecha=fecha)
        return {"status": "success", "message": f"Grupo creado (vacío) para {fecha}."}

    def eliminar_grupo_por_fecha(self, fecha: str, **kwargs) -> Dict[str, Any]:
        pm = self.payment_model

        if hasattr(pm, "eliminar_grupo_por_fecha"):
            res = self._try(self._call_maybe_kwargs, pm.eliminar_grupo_por_fecha, fecha, **kwargs)
            if self._is_success(res):
                self._after_change("eliminar_grupo", fecha=fecha)
            return res if isinstance(res, dict) else {"status": "error", "message": "Respuesta inválida"}

        try:
            _ = datetime.strptime(str(fecha).strip(), "%Y-%m-%d")
        except Exception:
            return {"status": "error", "message": "Formato de fecha inválido (usa YYYY-MM-DD)."}

        self._after_change("eliminar_grupo_fallback", fecha=fecha)
        return {"status": "success", "message": f"Grupo eliminado (si existía) para {fecha}."}

    def cerrar_grupo(self, grupo_pago: str) -> Dict[str, Any]:
        res = self._try(self.payment_model.cerrar_grupo, grupo_pago)
        if self._is_success(res):
            self._after_change("cerrar_grupo", grupo_pago=grupo_pago)
        return res if isinstance(res, dict) else {"status": "error", "message": "Respuesta inválida"}

    def reabrir_grupo(self, grupo_pago: str) -> Dict[str, Any]:
        res = self._try(self.payment_model.reabrir_grupo, grupo_pago)
        if self._is_success(res):
            self._after_change("reabrir_grupo", grupo_pago=grupo_pago)
        return res if isinstance(res, dict) else {"status": "error", "message": "Respuesta inválida"}

    # -------------------- Cachés (para que el Container pueda llamar) ----
    def invalidate_cache(self) -> None:
        self._clear_like()
        self._refresh_if_schema_changed()
        self._emit_change("invalidate_cache")

    def clear_cache(self) -> None:
        self.invalidate_cache()

    def refresh_cache(self) -> None:
        self.invalidate_cache()

    def reset_cache(self) -> None:
        self.invalidate_cache()

    def _clear_like(self) -> None:
        for nm in ("invalidate_cache", "clear_cache", "reset_cache", "refresh_cache"):
            fn = getattr(self.payment_model, nm, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
