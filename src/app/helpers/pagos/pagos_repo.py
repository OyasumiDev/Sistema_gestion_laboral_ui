# helpers/pagos/pagos_repo.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.models.payment_model import PaymentModel
from app.core.interfaces.database_mysql import DatabaseMysql


class PagosRepo:
    """
    Repositorio de acceso a datos para el área de Pagos.
    - Estandariza NOMBRES de columnas para la UI (id_pago_nomina, etc).
    - Centraliza SELECTs con los JOINs que usa la tabla del contenedor.
    - Expone operaciones típicas (listar, obtener, actualizar campos, confirmar, eliminar).
    - Ofrece utilidades de agrupación por empleado para tu futura vista "expandible".
    """

    def __init__(self, payment_model: Optional[PaymentModel] = None):
        self.pm = payment_model or PaymentModel()
        # acceso directo al adaptador para queries simples (solo lectura)
        self.db: DatabaseMysql = self.pm.db

    # ---------------------------------------------------------------------
    # Lecturas base
    # ---------------------------------------------------------------------
    def listar_pagos(self, *, order_desc: bool = True) -> List[Dict[str, Any]]:
        """
        Lista pagos con datos del empleado listos para pintarse en la tabla.
        Normaliza nombres claves para la UI.
        """
        order = "DESC" if order_desc else "ASC"
        q = f"""
            SELECT
                p.id_pago_nomina,
                p.numero_nomina,
                p.fecha_pago,
                p.total_horas_trabajadas,
                p.monto_base,
                p.monto_total,
                p.saldo,
                p.pago_deposito,
                p.pago_efectivo,
                p.estado,
                e.nombre_completo,
                e.sueldo_por_hora
            FROM pagos p
            JOIN empleados e ON p.numero_nomina = e.numero_nomina
            ORDER BY p.fecha_pago {order}, p.id_pago_nomina {order}
        """
        rows = self.db.get_data_list(q, dictionary=True) or []
        return [self._normalize_row(r) for r in rows]

    def obtener_pago(self, id_pago_nomina: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene un pago por id_pago_nomina.
        """
        q = """
            SELECT
                p.*,
                e.nombre_completo,
                e.sueldo_por_hora
            FROM pagos p
            JOIN empleados e ON p.numero_nomina = e.numero_nomina
            WHERE p.id_pago_nomina = %s
            LIMIT 1
        """
        r = self.db.get_data(q, (id_pago_nomina,), dictionary=True)
        return self._normalize_row(r) if r else None

    def listar_fechas_utilizadas(self) -> List[str]:
        """
        Retorna fechas (YYYY-MM-DD) ya usadas en pagos. Útil para bloquear rangos en el selector.
        """
        try:
            return self.pm.get_fechas_utilizadas()  # delega al modelo si ya lo tienes
        except Exception:
            q = "SELECT DISTINCT fecha_pago FROM pagos"
            rows = self.db.get_data_list(q, dictionary=True) or []
            return [str(r.get("fecha_pago")) for r in rows if r.get("fecha_pago")]

    # ---------------------------------------------------------------------
    # Escrituras / cambios
    # ---------------------------------------------------------------------
    def actualizar_campos_pago(self, id_pago_nomina: int, campos: Dict[str, Any]) -> Dict[str, Any]:
        """
        Actualiza campos en 'pagos' usando el método del modelo (si existe),
        o hace un UPDATE directo.
        """
        # Si el PaymentModel ya expone update_pago(id, dict), úsalo
        if hasattr(self.pm, "update_pago"):
            return self.pm.update_pago(id_pago_nomina, campos)

        # Fallback: UPDATE dinámico
        sets = ", ".join([f"{k}=%s" for k in campos.keys()])
        vals = list(campos.values()) + [id_pago_nomina]
        q = f"UPDATE pagos SET {sets} WHERE id_pago_nomina=%s"
        self.db.run_query(q, tuple(vals))
        return {"status": "success", "message": "Pago actualizado."}

    def confirmar_pago(self, id_pago_nomina: int) -> Dict[str, Any]:
        """
        Confirma un pago. Idealmente delega a PaymentModel.confirmar_pago(),
        que debe encargarse de:
          - aplicar detalles de préstamos pendientes
          - recalcular totales con descuentos confirmados
          - marcar estado='pagado'
        """
        if hasattr(self.pm, "confirmar_pago"):
            return self.pm.confirmar_pago(id_pago_nomina)

        # Si tu modelo aún no tiene confirmar_pago, deja claro el contrato:
        return {
            "status": "error",
            "message": (
                "PaymentModel.confirmar_pago(id_pago_nomina) no está implementado. "
                "Agrega este método en el modelo para confirmar pagos end-to-end."
            ),
        }

    def eliminar_pago(self, id_pago_nomina: int) -> Dict[str, Any]:
        """
        Elimina un pago. Delegado al PaymentModel si existe delete_pago(),
        sino un DELETE simple.
        """
        if hasattr(self.pm, "delete_pago"):
            return self.pm.delete_pago(id_pago_nomina)

        q = "DELETE FROM pagos WHERE id_pago_nomina=%s"
        self.db.run_query(q, (id_pago_nomina,))
        return {"status": "success", "message": f"Pago {id_pago_nomina} eliminado."}

    # ---------------------------------------------------------------------
    # Métricas / agregados
    # ---------------------------------------------------------------------
    def total_pagado_confirmado(self) -> float:
        """
        Suma de monto_total de pagos con estado='pagado'.
        """
        q = "SELECT IFNULL(SUM(monto_total),0) AS total FROM pagos WHERE estado='pagado'"
        r = self.db.get_data(q, dictionary=True) or {}
        try:
            return float(r.get("total") or 0.0)
        except Exception:
            return 0.0

    # ---------------------------------------------------------------------
    # Agrupación por empleado (para tu vista expandible futura)
    # ---------------------------------------------------------------------
    def agrupar_por_empleado(self, pagos: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Devuelve una lista de grupos:
        [
          {
            "numero_nomina": 12,
            "nombre_empleado": "Jane Doe",
            "sueldo_por_hora": 110.0,
            "pagos": [ {pago_row...}, ... ]
          },
          ...
        ]
        """
        if pagos is None:
            pagos = self.listar_pagos(order_desc=True)

        grupos: Dict[int, Dict[str, Any]] = {}
        for p in pagos:
            num = int(p["numero_nomina"])
            g = grupos.get(num)
            if not g:
                grupos[num] = {
                    "numero_nomina": num,
                    "nombre_empleado": p.get("nombre_completo"),
                    "sueldo_por_hora": p.get("sueldo_por_hora"),
                    "pagos": [],
                }
            grupos[num]["pagos"].append(p)

        # Ordena pagos por fecha desc dentro de cada grupo (opcional)
        for g in grupos.values():
            g["pagos"].sort(key=lambda r: (str(r.get("fecha_pago") or ""), int(r.get("id_pago_nomina") or 0)), reverse=True)

        # Convierte a lista ordenada por numero_nomina asc
        return sorted(grupos.values(), key=lambda g: g["numero_nomina"])

    # ---------------------------------------------------------------------
    # Normalización
    # ---------------------------------------------------------------------
    @staticmethod
    def _normalize_row(r: Dict[str, Any]) -> Dict[str, Any]:
        """
        Asegura nombres consistentes para la UI.
        Soporta casos donde el modelo/consulta use 'id_pago' (legacy) y lo mapea a 'id_pago_nomina'.
        """
        if not r:
            return {}

        out = dict(r)
        # normaliza ID
        if "id_pago_nomina" not in out and "id_pago" in out:
            out["id_pago_nomina"] = out.pop("id_pago")

        # normaliza nombres comunes (por si vienen como Decimal/None, etc.)
        # (la UI puede castear a float/str donde lo necesite)
        keep = {
            "id_pago_nomina",
            "numero_nomina",
            "fecha_pago",
            "total_horas_trabajadas",
            "monto_base",
            "monto_total",
            "saldo",
            "pago_deposito",
            "pago_efectivo",
            "estado",
            "nombre_completo",
            "sueldo_por_hora",
        }
        # elimina llaves inesperadas si quieres una salida estricta
        # out = {k: out.get(k) for k in keep if k in out}

        return out
