# app/models/fechas_modal_model.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.interfaces.database_mysql import DatabaseMysql
from app.core.enums.e_assistance_model import E_ASSISTANCE
from app.core.enums.e_payment_model import E_PAYMENT
from app.core.enums.e_fechas_modal_model import E_FECHAS_MODAL_FECHA_GRUPOS_PAGADOS as E_FMFGP


@dataclass(frozen=True)
class CalendarState:
    """
    Estado calculado para el DateModalSelector (por mes).

    - fechas_disponibles:
        Fechas con al menos una asistencia (independientemente del estado).
        El selector puede pintar y permitir click según reglas.

    - fechas_bloqueadas:
        Fechas no seleccionables por reglas fuertes:
        • Fechas cubiertas por un rango pagado (pagos.estado='pagado')
        • Fechas marcadas administrativamente en fecha_grupos_pagados con categoria='pagado' (opcional)

    - asistencias_estado:
        Mapa date -> "completo" | "incompleto"
        Regla: si existe al menos una asistencia NO completa en el día => "incompleto"
               si todas completas => "completo"
    """
    fechas_disponibles: Set[date]
    fechas_bloqueadas: Set[date]
    asistencias_estado: Dict[date, str]
    debug: Dict[str, Any]


class FechasModalModel:
    """
    Controlador de lógica de calendario para el modal de selección de fechas.

    PRINCIPIOS (tal cual tu requisito actual):
    - NO se bloquean fechas “porque ya se usaron”.
    - Se bloquean fechas por 2 motivos reales:
        1) No hay asistencias utilizables (el selector las vuelve no clicables porque ni aparecen como disponibles)
        2) Están dentro de rangos ya PAGADOS (eso sí es inmutable)
    - Si borras pagos pendientes, esas fechas vuelven a estar disponibles automáticamente.
    - Si aparecen nuevas asistencias en fechas ya usadas, deben poder seleccionarse también.
      (porque la disponibilidad depende de asistencias existentes, no del historial de “ya generadas”).

    La tabla auxiliar `fecha_grupos_pagados` sirve como control administrativo opcional,
    para reforzar bloqueos visuales/categorización (si lo decides activar).
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self.A = E_ASSISTANCE
        self.P = E_PAYMENT
        self.F = E_FMFGP

        self._payment_model = None
        self._exists_table = self.check_table()

    # ---------------------------------------------------------------------
    # Infra: tabla auxiliar del modal (fecha_grupos_pagados)
    # ---------------------------------------------------------------------
    def check_table(self) -> bool:
        """
        Crea tabla `fecha_grupos_pagados` si no existe.
        """
        try:
            q = f"""
            CREATE TABLE IF NOT EXISTS {self.F.TABLE.value} (
                {self.F.COL_ID_GRUPO.value} INT AUTO_INCREMENT PRIMARY KEY,
                {self.F.COL_FECHA.value} DATE NOT NULL,
                {self.F.COL_CATEGORIA.value} ENUM('{self.F.CATEGORIA_PAGADO.value}','{self.F.CATEGORIA_PENDIENTE.value}')
                    NOT NULL DEFAULT '{self.F.CATEGORIA_PAGADO.value}',
                {self.F.COL_ESTADO_GRUPO.value} ENUM('{self.F.ESTADO_GRUPO_ABIERTO.value}','{self.F.ESTADO_GRUPO_CERRADO.value}')
                    NOT NULL DEFAULT '{self.F.ESTADO_GRUPO_ABIERTO.value}',
                {self.F.COL_CREATED_AT.value} TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_fecha_categoria ({self.F.COL_FECHA.value}, {self.F.COL_CATEGORIA.value})
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            self.db.run_query(q)
            return True
        except Exception as ex:
            print(f"❌ FechasModalModel.check_table error: {ex}")
            return False

    # ---------------------------------------------------------------------
    # PaymentModel lazy (evita ciclos)
    # ---------------------------------------------------------------------
    def _get_payment_model(self):
        if self._payment_model is None:
            from app.models.payment_model import PaymentModel
            self._payment_model = PaymentModel()
        return self._payment_model

    # ---------------------------------------------------------------------
    # Helpers fechas
    # ---------------------------------------------------------------------
    @staticmethod
    def _normalize_date(x: Any) -> Optional[date]:
        if isinstance(x, date) and not isinstance(x, datetime):
            return x
        if isinstance(x, datetime):
            return x.date()
        if not x:
            return None
        s = str(x).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                continue
        return None

    @staticmethod
    def _daterange(d1: date, d2: date) -> List[date]:
        if d2 < d1:
            d1, d2 = d2, d1
        out: List[date] = []
        cur = d1
        while cur <= d2:
            out.append(cur)
            cur = cur + timedelta(days=1)
        return out

    @staticmethod
    def _month_window(year: int, month: int) -> Tuple[date, date]:
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        return start, end

    # ---------------------------------------------------------------------
    # Estado de calendario
    # ---------------------------------------------------------------------
    def build_calendar_state(
        self,
        year: int,
        month: int,
        *,
        numero_nomina: Optional[int] = None,
        bloquear_pagados: bool = True,
        incluir_bloqueo_admin_pagado: bool = True,
    ) -> CalendarState:
        """
        Construye el estado del calendario para DateModalSelector (mes).

        - fechas_disponibles:
            Días que tienen asistencias (si no hay asistencias, no hay selección).

        - asistencias_estado:
            completo / incompleto por día (para pintar y bloquear incompletas en UI).

        - fechas_bloqueadas:
            si bloquear_pagados=True:
                bloquea días dentro de rangos ya pagados (pagos.estado='pagado').
            si incluir_bloqueo_admin_pagado=True:
                bloquea días marcados en fecha_grupos_pagados con categoria='pagado'
                (control administrativo opcional, por si lo usas).
        """
        fi, ff = self._month_window(int(year), int(month))

        asistencias_estado, fechas_con_asistencia = self._fetch_asistencias_estado(fi, ff, numero_nomina)
        fechas_bloqueadas: Set[date] = set()

        if bloquear_pagados:
            fechas_bloqueadas |= self._fetch_fechas_bloqueadas_por_pagados(fi, ff, numero_nomina)

        if incluir_bloqueo_admin_pagado:
            fechas_bloqueadas |= self._fetch_bloqueo_admin_pagado(fi, ff)

        debug = {
            "fi": fi.isoformat(),
            "ff": ff.isoformat(),
            "numero_nomina": numero_nomina,
            "bloquear_pagados": bloquear_pagados,
            "incluir_bloqueo_admin_pagado": incluir_bloqueo_admin_pagado,
            "count_disponibles": len(fechas_con_asistencia),
            "count_bloqueadas": len(fechas_bloqueadas),
        }

        return CalendarState(
            fechas_disponibles=fechas_con_asistencia,
            fechas_bloqueadas=fechas_bloqueadas,
            asistencias_estado=asistencias_estado,
            debug=debug,
        )

    def _fetch_asistencias_estado(
        self, fi: date, ff: date, numero_nomina: Optional[int]
    ) -> Tuple[Dict[date, str], Set[date]]:
        """
        Retorna:
        - asistencias_estado: date -> "completo"/"incompleto"
        - fechas_con_asistencia: set(date)

        Regla por día:
        - si existe al menos 1 asistencia con estado != 'completo' => "incompleto"
        - si todas completas => "completo"
        """
        where = [f"a.{self.A.FECHA.value} BETWEEN %s AND %s"]
        params: List[Any] = [fi, ff]

        if numero_nomina is not None:
            where.append(f"a.{self.A.NUMERO_NOMINA.value}=%s")
            params.append(int(numero_nomina))

        q = f"""
            SELECT
                a.{self.A.FECHA.value} AS fecha,
                SUM(CASE WHEN LOWER(IFNULL(a.{self.A.ESTADO.value},''))='completo' THEN 0 ELSE 1 END) AS incompletas,
                COUNT(*) AS total
            FROM {self.A.TABLE.value} a
            WHERE {" AND ".join(where)}
            GROUP BY a.{self.A.FECHA.value}
        """
        rows = self.db.get_data_list(q, tuple(params), dictionary=True) or []

        estado: Dict[date, str] = {}
        fechas: Set[date] = set()

        for r in rows:
            d = self._normalize_date(r.get("fecha"))
            if not d:
                continue
            fechas.add(d)
            inc = int(r.get("incompletas") or 0)
            estado[d] = "incompleto" if inc > 0 else "completo"

        return estado, fechas

    def _fetch_fechas_bloqueadas_por_pagados(
        self, fi: date, ff: date, numero_nomina: Optional[int]
    ) -> Set[date]:
        """
        Bloqueo por pagos ya PAGADOS.
        Bloquea por rango (fecha_inicio/fecha_fin) cuando existen ambos.
        Si algún pago pagado no trae rango, cae al fallback fecha_pago (si cae dentro del mes).
        """
        where = [
            f"p.{self.P.ESTADO.value}='pagado'",
            f"( (p.{self.P.FECHA_INICIO.value} IS NOT NULL AND p.{self.P.FECHA_FIN.value} IS NOT NULL "
            f"      AND p.{self.P.FECHA_INICIO.value}<=%s AND p.{self.P.FECHA_FIN.value}>=%s)"
            f"  OR (p.{self.P.FECHA_INICIO.value} IS NULL OR p.{self.P.FECHA_FIN.value} IS NULL)"
            f")"
        ]
        params: List[Any] = [ff, fi]

        if numero_nomina is not None:
            where.append(f"p.{self.P.NUMERO_NOMINA.value}=%s")
            params.append(int(numero_nomina))

        q = f"""
            SELECT
                p.{self.P.FECHA_INICIO.value} AS fecha_inicio,
                p.{self.P.FECHA_FIN.value}    AS fecha_fin,
                p.{self.P.FECHA_PAGO.value}   AS fecha_pago
            FROM {self.P.TABLE.value} p
            WHERE {" AND ".join(where)}
        """
        rows = self.db.get_data_list(q, tuple(params), dictionary=True) or []

        out: Set[date] = set()
        for r in rows:
            di = self._normalize_date(r.get("fecha_inicio"))
            df = self._normalize_date(r.get("fecha_fin"))
            if di and df:
                for d in self._daterange(max(di, fi), min(df, ff)):
                    out.add(d)
            else:
                dp = self._normalize_date(r.get("fecha_pago"))
                if dp and (fi <= dp <= ff):
                    out.add(dp)
        return out

    def _fetch_bloqueo_admin_pagado(self, fi: date, ff: date) -> Set[date]:
        """
        Bloqueo administrativo opcional:
        - si existe una fila en fecha_grupos_pagados con categoria='pagado',
          ese día se bloquea en calendario.
        """
        try:
            q = f"""
                SELECT g.{self.F.COL_FECHA.value} AS fecha
                FROM {self.F.TABLE.value} g
                WHERE g.{self.F.COL_FECHA.value} BETWEEN %s AND %s
                  AND g.{self.F.COL_CATEGORIA.value}=%s
            """
            rows = self.db.get_data_list(q, (fi, ff, self.F.CATEGORIA_PAGADO.value), dictionary=True) or []
            out: Set[date] = set()
            for r in rows:
                d = self._normalize_date(r.get("fecha"))
                if d:
                    out.add(d)
            return out
        except Exception:
            return set()

    # ---------------------------------------------------------------------
    # Acciones del modal: generar / eliminar por fechas seleccionadas
    # ---------------------------------------------------------------------
    def fechas_a_rangos(self, fechas: List[date]) -> List[Tuple[date, date]]:
        """
        Convierte fechas sueltas a rangos contiguos.
        [1,2,3, 8,9] -> [(1,3), (8,9)]
        """
        norm = sorted({d for d in fechas if isinstance(d, date)})
        if not norm:
            return []
        rangos: List[Tuple[date, date]] = []
        start = prev = norm[0]
        for d in norm[1:]:
            if d == prev + timedelta(days=1):
                prev = d
                continue
            rangos.append((start, prev))
            start = prev = d
        rangos.append((start, prev))
        return rangos

    def generar_pagos_por_fechas(self, fechas: List[date]) -> Dict[str, Any]:
        """
        Genera/actualiza pagos PENDIENTES por rangos contiguos seleccionados.
        Delegado a PaymentModel.generar_pagos_por_rango(...).

        Diseño:
        - Idempotente para pendientes.
        - Si un rango contiene pagados, PaymentModel debe omitirlos por inmutabilidad.
        """
        if not fechas:
            return {"status": "noop", "message": "Sin fechas seleccionadas."}

        pm = self._get_payment_model()
        rangos = self.fechas_a_rangos(fechas)

        out = {"status": "success", "rangos": [], "detalle": []}
        for fi, ff in rangos:
            res = pm.generar_pagos_por_rango(fi.isoformat(), ff.isoformat())
            out["rangos"].append([fi.isoformat(), ff.isoformat()])
            out["detalle"].append({"rango": [fi.isoformat(), ff.isoformat()], "resultado": res})
        return out

    def eliminar_pagos_por_fechas(
        self,
        fechas: List[date],
        *,
        force: bool = False,
        incluir_pagados: bool = False,
    ) -> Dict[str, Any]:
        """
        Elimina pagos por rangos contiguos seleccionados.

        Seguridad:
        - Por default elimina solo pendientes.
        - Para eliminar pagados: incluir_pagados=True requiere force=True.

        Matching:
        - Elimina por EXACT MATCH de rango: fecha_inicio=fi AND fecha_fin=ff.
          (Esto te mantiene consistente con cómo generas rangos en la nómina.)
        """
        if not fechas:
            return {"status": "noop", "message": "Sin fechas seleccionadas."}

        if incluir_pagados and not force:
            return {"status": "error", "message": "Para eliminar PAGADOS debes usar force=True."}

        pm = self._get_payment_model()
        rangos = self.fechas_a_rangos(fechas)

        estados = ["pendiente"]
        if incluir_pagados:
            estados.append("pagado")

        eliminados = 0
        detalle: List[Dict[str, Any]] = []

        for fi, ff in rangos:
            q = f"""
                SELECT p.{self.P.ID_PAGO_NOMINA.value} AS id_pago,
                       p.{self.P.ESTADO.value} AS estado
                FROM {self.P.TABLE.value} p
                WHERE p.{self.P.FECHA_INICIO.value}=%s
                  AND p.{self.P.FECHA_FIN.value}=%s
                  AND p.{self.P.ESTADO.value} IN ({", ".join(["%s"] * len(estados))})
                ORDER BY p.{self.P.ID_PAGO_NOMINA.value} ASC
            """
            rows = self.db.get_data_list(q, (fi, ff, *estados), dictionary=True) or []

            borrados = 0
            for r in rows:
                pid = int(r.get("id_pago") or 0)
                if pid <= 0:
                    continue
                res = pm.eliminar_pago(pid, force=force)
                if isinstance(res, dict) and res.get("status") == "success":
                    eliminados += 1
                    borrados += 1

            detalle.append({
                "rango": [fi.isoformat(), ff.isoformat()],
                "count_ids": len(rows),
                "borrados": borrados,
            })

        return {
            "status": "success",
            "message": f"Eliminados {eliminados} pagos (por rangos seleccionados).",
            "detalle": detalle,
        }
