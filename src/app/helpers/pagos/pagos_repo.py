# app/helpers/pagos/pagos_repo.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Callable
import time

from app.models.payment_model import PaymentModel


class PagosRepo:
    """
    Capa de servicios para Pagos.
    - Provee lecturas planas (para tu DataTable actual).
    - Expone confirmación / eliminación / totales.
    - Tiene utilidades para grupos y sort (para futuras tablas por grupo).
    - Implementa un pequeño retry suave de conexión (re-crea PaymentModel si falla).
    """

    def __init__(self, payment_model: Optional[PaymentModel] = None):
        self.payment_model = payment_model or PaymentModel()

    # -------------------- Infra: retry suave --------------------
    def _try(self, fn: Callable, *args, **kwargs):
        """
        Ejecuta fn con un reintento si hay excepción (re-crea model/conn).
        """
        try:
            return fn(*args, **kwargs)
        except Exception:
            # recrea modelo/conexión y reintenta 1 vez
            try:
                self.payment_model = PaymentModel()
                return fn(*args, **kwargs)
            except Exception as ex2:
                return {"status": "error", "message": f"Falla de conexión/operación: {ex2}"}

    # -------------------- Lecturas básicas ----------------------
    def listar_pagos(self, order_desc: bool = True) -> List[Dict[str, Any]]:
        """
        Lista plana para tu tabla actual (una sola DataTable).
        Normaliza claves para que existan tanto 'deposito' como 'pago_deposito'.
        """
        rs = self._try(self.payment_model.get_all_pagos)
        if not isinstance(rs, dict) or rs.get("status") != "success":
            return []
        rows = rs.get("data", []) or []
        out: List[Dict[str, Any]] = []
        for r in rows:
            # Normaliza llaves (compatibilidad con PagosContainer existente)
            if "deposito" in r and "pago_deposito" not in r:
                r["pago_deposito"] = r["deposito"]
            if "pago_deposito" in r and "deposito" not in r:
                r["deposito"] = r["pago_deposito"]
            out.append(r)
        # Ordenamiento (por si necesitas invertir aquí)
        if order_desc:
            out.sort(key=lambda x: (str(x.get("fecha_pago") or ""), int(x.get("numero_nomina") or 0)), reverse=True)
        else:
            out.sort(key=lambda x: (str(x.get("fecha_pago") or ""), int(x.get("numero_nomina") or 0)))
        return out

    def obtener_pago(self, id_pago: int) -> Optional[Dict[str, Any]]:
        rs = self._try(self.payment_model.get_by_id, id_pago)
        if isinstance(rs, dict) and rs.get("status") == "success":
            d = rs["data"]
            if "deposito" not in d and "pago_deposito" in d:
                d["deposito"] = d["pago_deposito"]
            if "pago_deposito" not in d and "deposito" in d:
                d["pago_deposito"] = d["deposito"]
            return d
        return None

    # -------------------- Acciones ------------------------------
    def confirmar_pago(self, id_pago: int) -> Dict[str, Any]:
        """
        Pasa por PaymentModel.confirmar_pago (que ya se encarga de:
        - aplicar borrador -> descuentos
        - aplicar detalles préstamos -> pagos_prestamo
        - recalcular totales y marcar 'pagado'
        """
        return self._try(self.payment_model.confirmar_pago, id_pago)

    def eliminar_pago(self, id_pago: int) -> Dict[str, Any]:
        return self._try(self.payment_model.eliminar_pago, id_pago)

    def total_pagado_confirmado(self) -> float:
        """
        Suma el total de pagos ya confirmados (MONTOS TOTALES).
        """
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

    # -------------------- Grupos (para futuras tablas) ----------
    def listar_grupos(self) -> List[Dict[str, Any]]:
        try:
            return self.payment_model.get_grupos_pagos()
        except Exception:
            return []

    def listar_pagos_por_grupo(self, grupo_pago: str, *, order: str = "fecha_desc") -> List[Dict[str, Any]]:
        rows = self.payment_model.get_pagos_por_grupo(grupo_pago) or []
        if order == "fecha_desc":
            rows.sort(key=lambda x: (str(x.get("fecha_pago") or ""), int(x.get("numero_nomina") or 0)), reverse=True)
        elif order == "fecha_asc":
            rows.sort(key=lambda x: (str(x.get("fecha_pago") or ""), int(x.get("numero_nomina") or 0)))
        elif order == "empleado_asc":
            rows.sort(key=lambda x: (str(x.get("nombre_completo") or ""), str(x.get("fecha_pago") or "")))
        elif order == "empleado_desc":
            rows.sort(key=lambda x: (str(x.get("nombre_completo") or ""), str(x.get("fecha_pago") or "")), reverse=True)
        # Normaliza llaves de depósito como arriba
        for r in rows:
            if "deposito" in r and "pago_deposito" not in r:
                r["pago_deposito"] = r["deposito"]
            if "pago_deposito" in r and "deposito" not in r:
                r["deposito"] = r["pago_deposito"]
        return rows

    def cerrar_grupo(self, grupo_pago: str) -> Dict[str, Any]:
        return self._try(self.payment_model.cerrar_grupo, grupo_pago)

    def reabrir_grupo(self, grupo_pago: str) -> Dict[str, Any]:
        return self._try(self.payment_model.reabrir_grupo, grupo_pago)
