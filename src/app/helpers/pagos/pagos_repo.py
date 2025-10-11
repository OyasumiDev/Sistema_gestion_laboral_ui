# app/helpers/pagos/pagos_repo.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Callable, Iterable
from datetime import datetime
import inspect

from app.models.payment_model import PaymentModel


class PagosRepo:
    """
    Capa de servicios para Pagos.
    - Lecturas planas para DataTable.
    - Confirmación / eliminación / totales.
    - Utilidades de grupos por FECHA (crear/eliminar) con fallbacks robustos.
    - Retry suave en fallos de conexión (re-crea PaymentModel y reintenta 1 vez).
    - Normalización de claves (deposito/pago_deposito, efectivo/pago_efectivo).
    - API tolerante a kwargs ('force', etc.) que solo pasa los aceptados por backend.
    """

    # -------------------- Init --------------------
    def __init__(self, payment_model: Optional[PaymentModel] = None):
        self.payment_model = payment_model or PaymentModel()

    # -------------------- Infra: retry suave --------------------
    def _try(self, fn: Callable, *args, **kwargs):
        """
        Ejecuta fn con un reintento si hay excepción (re-crea model/conn).
        Devuelve siempre un dict con status o el resultado original de fn.
        """
        try:
            return fn(*args, **kwargs)
        except Exception:
            try:
                self.payment_model = PaymentModel()
                return fn(*args, **kwargs)
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
                # Fallback: fecha_pago, numero_nomina (SIN paréntesis extra)
                return (str(r.get("fecha_pago") or ""), int(r.get("numero_nomina") or 0))

            rows.sort(key=key_fn, reverse=not asc)
        else:
            rows.sort(
                key=lambda x: (str(x.get("fecha_pago") or ""), int(x.get("numero_nomina") or 0)),
                reverse=bool(order_desc),
            )

        return rows


    def obtener_pago(self, id_pago: int) -> Optional[Dict[str, Any]]:
        rs = self._try(self.payment_model.get_by_id, id_pago)
        if isinstance(rs, dict) and rs.get("status") == "success":
            return self._normalize_row_keys(rs["data"])
        return None

    # -------------------- Acciones ------------------------------
    def confirmar_pago(self, id_pago: int) -> Dict[str, Any]:
        return self._try(self.payment_model.confirmar_pago, id_pago)

    def eliminar_pago(self, id_pago: int, **kwargs) -> Dict[str, Any]:
        """
        Elimina un pago. Acepta kwargs opcionales (p.ej. force=True) y
        los pasa solo si el backend los soporta.
        """
        fn = getattr(self.payment_model, "eliminar_pago", None)
        return self._try(self._call_maybe_kwargs, fn, id_pago, **kwargs)

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

    # -------------------- Fechas auxiliares ---------------------
    def get_fechas_pagadas(self) -> List[str]:
        """Fechas (YYYY-MM-DD) con pagos confirmados."""
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

    # -------------------- Grupos por FECHA ----------------------
    def crear_grupo_pagado(self, fecha: str, **kwargs) -> Dict[str, Any]:
        """
        Define/crea un grupo 'pagado' para la fecha.
        Intenta usar el backend; hace fallback seguro si no existe.
        """
        if hasattr(self.payment_model, "crear_grupo_pagado"):
            return self._try(self._call_maybe_kwargs, self.payment_model.crear_grupo_pagado, fecha, **kwargs)

        # fallback robusto
        try:
            try:
                _ = datetime.strptime(fecha, "%Y-%m-%d")
            except Exception:
                return {"status": "error", "message": "Formato de fecha inválido (usa YYYY-MM-DD)."}

            pm = self.payment_model
            q1 = f"""
                SELECT COUNT(*) AS c
                FROM {pm.E.TABLE.value}
                WHERE {pm.E.ESTADO.value}='pagado' AND {pm.E.FECHA_PAGO.value}=%s
            """
            r1 = pm.db.get_data(q1, (fecha,), dictionary=True) or {}
            if int(r1.get("c", 0)) > 0:
                return {"status": "error", "message": f"Ya existen 'pagados' con fecha {fecha}."}

            q2 = f"""
                SELECT COUNT(*) AS c
                FROM {pm.E.TABLE.value}
                WHERE {pm.E.ESTADO.value}='pendiente' AND {pm.E.FECHA_PAGO.value}=%s
            """
            r2 = pm.db.get_data(q2, (fecha,), dictionary=True) or {}
            if int(r2.get("c", 0)) > 0:
                return {"status": "success", "message": "Grupo creado (existían pendientes en esa fecha)."}

            q3 = f"""
                UPDATE {pm.E.TABLE.value}
                SET {pm.E.FECHA_PAGO.value}=%s
                WHERE {pm.E.ESTADO.value}='pendiente' AND {pm.E.ESTADO_GRUPO.value}='abierto'
            """
            pm.db.run_query(q3, (fecha,))
            return {"status": "success", "message": f"Grupo creado. Pendientes re-fechados a {fecha}."}
        except Exception as ex:
            return {"status": "error", "message": f"No se pudo crear el grupo: {ex}"}

    def eliminar_grupo_por_fecha(self, fecha: str, **kwargs) -> Dict[str, Any]:
        """
        Elimina un grupo por FECHA para PENDIENTES (no toca 'pagados' ya confirmados).
        Intenta usar backend; hace fallback seguro si no existe.
        """
        if hasattr(self.payment_model, "eliminar_grupo_por_fecha"):
            return self._try(self._call_maybe_kwargs, self.payment_model.eliminar_grupo_por_fecha, fecha, **kwargs)
        if hasattr(self.payment_model, "eliminar_pagos_por_fecha"):
            return self._try(self._call_maybe_kwargs, self.payment_model.eliminar_pagos_por_fecha, fecha, **kwargs)

        # fallback robusto
        try:
            try:
                _ = datetime.strptime(fecha, "%Y-%m-%d")
            except Exception:
                return {"status": "error", "message": "Formato de fecha inválido (usa YYYY-MM-DD)."}

            pm = self.payment_model
            q1 = f"""
                SELECT COUNT(*) AS c
                FROM {pm.E.TABLE.value}
                WHERE {pm.E.ESTADO.value}='pagado' AND {pm.E.FECHA_PAGO.value}=%s
            """
            r1 = pm.db.get_data(q1, (fecha,), dictionary=True) or {}
            if int(r1.get("c", 0)) > 0:
                return {"status": "error", "message": "No se puede eliminar: ya hay pagos 'pagados' en esa fecha."}

            q2 = f"""
                SELECT COUNT(*) AS c
                FROM {pm.E.TABLE.value}
                WHERE {pm.E.ESTADO.value}='pendiente' AND {pm.E.FECHA_PAGO.value}=%s
            """
            r2 = pm.db.get_data(q2, (fecha,), dictionary=True) or {}
            cnt_pend = int(r2.get("c", 0))

            if cnt_pend == 0:
                return {"status": "success", "message": f"No había pendientes con fecha {fecha}."}

            hoy = datetime.now().strftime("%Y-%m-%d")
            q3 = f"""
                UPDATE {pm.E.TABLE.value}
                SET {pm.E.FECHA_PAGO.value}=%s
                WHERE {pm.E.ESTADO.value}='pendiente' AND {pm.E.FECHA_PAGO.value}=%s
            """
            pm.db.run_query(q3, (hoy, fecha))
            return {"status": "success", "message": f"Grupo eliminado. {cnt_pend} pendientes re-fechados a {hoy}."}
        except Exception as ex:
            return {"status": "error", "message": f"No se pudo eliminar el grupo: {ex}"}

    # -------------------- Grupos (por token existente) ----------
    def listar_grupos(self) -> List[Dict[str, Any]]:
        try:
            return self.payment_model.get_grupos_pagos()
        except Exception:
            return []

    def listar_pagos_por_grupo(self, grupo_pago: str, *, order: str = "fecha_desc") -> List[Dict[str, Any]]:
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

    def cerrar_grupo(self, grupo_pago: str) -> Dict[str, Any]:
        return self._try(self.payment_model.cerrar_grupo, grupo_pago)

    def reabrir_grupo(self, grupo_pago: str) -> Dict[str, Any]:
        return self._try(self.payment_model.reabrir_grupo, grupo_pago)

    # -------------------- Cachés (para que el Container pueda llamar) ----
    def invalidate_cache(self):
        """Compat: algunos contenedores llaman a este nombre."""
        self._clear_like()

    def clear_cache(self):
        self._clear_like()

    def refresh_cache(self):
        self._clear_like()

    def reset_cache(self):
        self._clear_like()

    def _clear_like(self):
        for nm in ("invalidate_cache", "clear_cache", "reset_cache", "refresh_cache"):
            fn = getattr(self.payment_model, nm, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
