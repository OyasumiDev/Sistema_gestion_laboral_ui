# app/models/fechas_modal_model.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple, Literal

from app.core.interfaces.database_mysql import DatabaseMysql

# Enums (nuevos y específicos)
from app.core.enums.e_fechas_modal_model import E_GRUPOS_FECHAS_PAGO as E_GFP
from app.core.enums.e_payment_model import E_PAYMENT


CategoriaGrupo = Literal["pagado", "pendiente"]
EstadoGrupoFecha = Literal["abierto", "cerrado"]


@dataclass(frozen=True)
class FechaGrupoUI:
    """
    Estructura que representa un "grupo por fecha" para la UI.

    NOTA:
    - Este grupo por fecha NO es lo mismo que `pagos.grupo_pago` (GP-...).
    - Este modelo sirve para controlar/mostrar el modal por fecha (p. ej. en Pagos Pagados/Pendientes).
    """
    fecha: str                      # YYYY-MM-DD
    categoria: CategoriaGrupo       # 'pagado' | 'pendiente'
    estado_grupo: EstadoGrupoFecha  # 'abierto' | 'cerrado'
    id_grupo: Optional[int] = None

    # Datos extra útiles para el modal (opcionales)
    total_pagos: int = 0
    total_monto: float = 0.0


class FechasModalModel:
    """
    Modelo robusto para CONTROLAR correctamente el "modal de fechas" (grupos por fecha).

    Qué resuelve este modelo
    ------------------------
    1) Crea/asegura la tabla `grupos_pagos`.
    2) Permite crear fechas "vacías" para que existan en UI aunque NO existan pagos reales:
       - ejemplo: crear un grupo 'pagado' vacío.
    3) Permite listar grupos y, opcionalmente, enriquecerlos con conteos/total desde `pagos`.
    4) Controla reglas para NO confundir grupos de fecha vs tokens GP-...:
       - Este modelo se limita a `grupos_pagos` y opera por (fecha, categoria).

    Reglas sugeridas para tu UI (modal)
    -----------------------------------
    - Si un grupo es 'pagado':
        - debería existir porque hay pagos pagados en esa fecha
          o porque tú lo creaste manualmente con create_empty_group().
        - Si hay pagos pagados reales, NO permitas eliminar el grupo manual.
    - Si un grupo es 'pendiente':
        - normalmente vendrá de pagos pendientes reales, pero si quieres, puedes también
          generar grupos manuales.

    Dependencias
    ------------
    - DatabaseMysql
    - E_GRUPOS_FECHAS_PAGO (tabla `grupos_pagos`)
    - E_PAYMENT (tabla `pagos`) para enriquecer totales del modal
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self.G = E_GFP
        self.P = E_PAYMENT

        # Asegura tabla
        self._ensure_table()

    # ---------------------------------------------------------------------
    # Normalización / validación
    # ---------------------------------------------------------------------
    @staticmethod
    def normalize_date(value: Any) -> str:
        """
        Normaliza a 'YYYY-MM-DD' tolerando:
        - datetime
        - date
        - 'YYYY-MM-DD'
        - 'DD/MM/YYYY'
        """
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        if not value:
            return ""

        text = str(value).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
            except Exception:
                continue
        # si no parsea, regresa lo que venga (pero luego lo validamos)
        return text

    @staticmethod
    def _validate_iso_date(iso: str) -> None:
        """Lanza ValueError si la fecha no cumple YYYY-MM-DD."""
        if not iso:
            raise ValueError("Fecha vacía.")
        datetime.strptime(iso, "%Y-%m-%d")

    @staticmethod
    def _validate_categoria(cat: str) -> CategoriaGrupo:
        cat = (cat or "").strip().lower()
        if cat not in ("pagado", "pendiente"):
            raise ValueError("Categoría inválida. Usa: 'pagado' | 'pendiente'.")
        return cat  # type: ignore

    @staticmethod
    def _validate_estado(estado: str) -> EstadoGrupoFecha:
        estado = (estado or "").strip().lower()
        if estado not in ("abierto", "cerrado"):
            raise ValueError("Estado inválido. Usa: 'abierto' | 'cerrado'.")
        return estado  # type: ignore

    # ---------------------------------------------------------------------
    # Infra / Tabla
    # ---------------------------------------------------------------------
    def _ensure_table(self) -> None:
        """
        Crea la tabla `grupos_pagos` si no existe.

        Esquema clave:
        - UNIQUE(fecha, categoria) => un grupo por fecha/categoría
        """
        q = f"""
        CREATE TABLE IF NOT EXISTS {self.G.TABLA_GRUPOS_POR_FECHA.value} (
            {self.G.ID_GRUPO_FECHA.value} INT AUTO_INCREMENT PRIMARY KEY,
            {self.G.FECHA_GRUPO.value} DATE NOT NULL,
            {self.G.CATEGORIA_GRUPO.value} ENUM('pagado','pendiente') NOT NULL DEFAULT 'pagado',
            {self.G.ESTADO_GRUPO_FECHA.value} ENUM('abierto','cerrado') NOT NULL DEFAULT 'abierto',
            {self.G.FECHA_CREACION_GRUPO.value} TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_fecha_categoria ({self.G.FECHA_GRUPO.value}, {self.G.CATEGORIA_GRUPO.value})
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        self.db.run_query(q)

    # ---------------------------------------------------------------------
    # CRUD de grupos (por fecha)
    # ---------------------------------------------------------------------
    def get_group(self, fecha: Any, categoria: str = "pagado") -> Optional[Dict[str, Any]]:
        """
        Obtiene un grupo exacto por (fecha, categoria).
        Retorna dict o None.
        """
        iso = self.normalize_date(fecha)
        self._validate_iso_date(iso)
        cat = self._validate_categoria(categoria)

        q = f"""
            SELECT
                {self.G.ID_GRUPO_FECHA.value} AS id_grupo,
                {self.G.FECHA_GRUPO.value} AS fecha,
                {self.G.CATEGORIA_GRUPO.value} AS categoria,
                {self.G.ESTADO_GRUPO_FECHA.value} AS estado_grupo
            FROM {self.G.TABLA_GRUPOS_POR_FECHA.value}
            WHERE {self.G.FECHA_GRUPO.value}=%s AND {self.G.CATEGORIA_GRUPO.value}=%s
            LIMIT 1
        """
        row = self.db.get_data(q, (iso, cat), dictionary=True)
        return row or None

    def upsert_group(
        self,
        fecha: Any,
        categoria: str = "pagado",
        estado_grupo: str = "abierto",
    ) -> Dict[str, Any]:
        """
        Inserta o actualiza un grupo por fecha.

        Uso típico:
        - crear "grupo pagado vacío": upsert_group(fecha, 'pagado', 'abierto')
        - marcar como cerrado: upsert_group(fecha, 'pagado', 'cerrado')

        IMPORTANTE:
        - Este método NO toca la tabla `pagos`.
        - Es para controlar existencia/estado del grupo en UI.
        """
        iso = self.normalize_date(fecha)
        self._validate_iso_date(iso)
        cat = self._validate_categoria(categoria)
        est = self._validate_estado(estado_grupo)

        q = f"""
            INSERT INTO {self.G.TABLA_GRUPOS_POR_FECHA.value}
            ({self.G.FECHA_GRUPO.value}, {self.G.CATEGORIA_GRUPO.value}, {self.G.ESTADO_GRUPO_FECHA.value})
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                {self.G.ESTADO_GRUPO_FECHA.value}=VALUES({self.G.ESTADO_GRUPO_FECHA.value})
        """
        self.db.run_query(q, (iso, cat, est))
        row = self.get_group(iso, cat)
        return {"status": "success", "data": row, "message": "Grupo upsert aplicado."}

    def create_empty_group(self, fecha: Any, categoria: str = "pagado") -> Dict[str, Any]:
        """
        Crea un grupo VACÍO (manual) para UI.

        Regla robusta (para evitar inconsistencias):
        - Si categoria='pagado' y ya hay pagos 'pagado' reales en esa fecha,
          NO es “vacío” (pero igual se puede upsert). Aquí lo tratamos como:
          'ya hay pagos reales, el grupo realmente existe por pagos', retornamos warning.

        Nota:
        - Si deseas permitir siempre, puedes ignorar el warning.
        """
        iso = self.normalize_date(fecha)
        self._validate_iso_date(iso)
        cat = self._validate_categoria(categoria)

        if cat == "pagado" and self._exists_real_pagos_for_date(iso, estado="pagado"):
            # No bloqueamos duro: devolvemos warning (porque igual puede ser útil para estado_grupo)
            self.upsert_group(iso, cat, "abierto")
            return {
                "status": "warning",
                "message": "Ya existen pagos 'pagado' reales en esa fecha; el grupo no es vacío, pero se aseguró en grupos_pagos.",
                "data": self.get_group(iso, cat),
            }

        rs = self.upsert_group(iso, cat, "abierto")
        rs["message"] = f"Grupo vacío creado/asegurado para {iso} ({cat})."
        return rs

    def delete_empty_group(self, fecha: Any, categoria: str = "pagado") -> Dict[str, Any]:
        """
        Elimina un grupo manual.

        Regla robusta:
        - Si hay pagos reales (por ejemplo pagados) en esa fecha/categoría, NO se elimina.

        Esto evita:
        - que la UI “pierda” fechas que sí tienen pagos reales.
        """
        iso = self.normalize_date(fecha)
        self._validate_iso_date(iso)
        cat = self._validate_categoria(categoria)

        # Bloqueo: si existen pagos reales que justifican la fecha en UI, no borrar
        estado_pago = "pagado" if cat == "pagado" else "pendiente"
        if self._exists_real_pagos_for_date(iso, estado=estado_pago):
            return {
                "status": "error",
                "message": f"No se puede eliminar: ya hay pagos reales '{estado_pago}' en {iso}.",
            }

        q = f"""
            DELETE FROM {self.G.TABLA_GRUPOS_POR_FECHA.value}
            WHERE {self.G.FECHA_GRUPO.value}=%s AND {self.G.CATEGORIA_GRUPO.value}=%s
        """
        self.db.run_query(q, (iso, cat))
        return {"status": "success", "message": f"Grupo manual eliminado: {iso} ({cat})."}

    def set_group_state(self, fecha: Any, categoria: str, estado_grupo: str) -> Dict[str, Any]:
        """
        Cambia estado_grupo ('abierto'/'cerrado') para el grupo por fecha.
        Si el grupo no existe, lo crea.
        """
        return self.upsert_group(fecha, categoria, estado_grupo)

    # ---------------------------------------------------------------------
    # Listado para UI (modal)
    # ---------------------------------------------------------------------
    def list_groups(
        self,
        categoria: str = "pagado",
        *,
        include_real_dates: bool = True,
        include_manual_dates: bool = True,
        enrich_with_pagos: bool = True,
        limit: int = 200,
    ) -> Dict[str, Any]:
        """
        Lista grupos para UI, por categoría.

        Parámetros clave:
        - include_real_dates:
            agrega fechas provenientes de `pagos` (p. ej. pagos pagados reales).
        - include_manual_dates:
            agrega fechas provenientes de `grupos_pagos` (manual/vacío).
        - enrich_with_pagos:
            si True, calcula total_pagos y total_monto desde `pagos` por fecha.

        Salida:
        - data: List[FechaGrupoUI] (convertido a dicts)
        """
        cat = self._validate_categoria(categoria)
        limit = max(1, min(int(limit or 200), 2000))

        fechas: Dict[str, FechaGrupoUI] = {}

        # 1) Manuales: tabla grupos_pagos
        if include_manual_dates:
            q_manual = f"""
                SELECT
                    {self.G.ID_GRUPO_FECHA.value} AS id_grupo,
                    {self.G.FECHA_GRUPO.value} AS fecha,
                    {self.G.CATEGORIA_GRUPO.value} AS categoria,
                    {self.G.ESTADO_GRUPO_FECHA.value} AS estado_grupo
                FROM {self.G.TABLA_GRUPOS_POR_FECHA.value}
                WHERE {self.G.CATEGORIA_GRUPO.value}=%s
                ORDER BY {self.G.FECHA_GRUPO.value} DESC
                LIMIT %s
            """
            rows = self.db.get_data_list(q_manual, (cat, limit), dictionary=True) or []
            for r in rows:
                f = self.normalize_date(r.get("fecha"))
                if not f:
                    continue
                fechas[f] = FechaGrupoUI(
                    fecha=f,
                    categoria=cat,  # por query
                    estado_grupo=str(r.get("estado_grupo") or "abierto").lower(),  # type: ignore
                    id_grupo=int(r.get("id_grupo") or 0) or None,
                )

        # 2) Reales: tabla pagos por fecha_pago y estado (pagado/pendiente)
        if include_real_dates:
            estado_pago = "pagado" if cat == "pagado" else "pendiente"
            q_real = f"""
                SELECT DISTINCT {self.P.FECHA_PAGO.value} AS fecha
                FROM {self.P.TABLE.value}
                WHERE {self.P.ESTADO.value}=%s
                ORDER BY {self.P.FECHA_PAGO.value} DESC
                LIMIT %s
            """
            rows = self.db.get_data_list(q_real, (estado_pago, limit), dictionary=True) or []
            for r in rows:
                f = self.normalize_date(r.get("fecha"))
                if not f:
                    continue
                if f not in fechas:
                    # si es real y no existe manual, estado_grupo default 'abierto'
                    fechas[f] = FechaGrupoUI(
                        fecha=f,
                        categoria=cat,
                        estado_grupo="abierto",
                        id_grupo=None,
                    )

        # 3) Enriquecer con totales desde pagos
        if enrich_with_pagos and fechas:
            self._enrich_groups_with_pagos(fechas, categoria=cat)

        # Orden final (desc)
        data_sorted = sorted(fechas.values(), key=lambda x: x.fecha, reverse=True)
        return {
            "status": "success",
            "data": [self._as_dict(x) for x in data_sorted],
            "count": len(data_sorted),
        }

    # ---------------------------------------------------------------------
    # Internals: pagos enrichment / existence checks
    # ---------------------------------------------------------------------
    def _exists_real_pagos_for_date(self, fecha_iso: str, *, estado: str) -> bool:
        """
        Retorna True si hay pagos en `pagos` para esa fecha y estado.
        """
        estado = (estado or "").strip().lower()
        if estado not in ("pagado", "pendiente", "cancelado"):
            # si te equivocas, mejor no “asumir”
            return False

        q = f"""
            SELECT COUNT(*) AS c
            FROM {self.P.TABLE.value}
            WHERE {self.P.FECHA_PAGO.value}=%s AND {self.P.ESTADO.value}=%s
        """
        r = self.db.get_data(q, (fecha_iso, estado), dictionary=True) or {}
        return int(r.get("c", 0) or 0) > 0

    def _enrich_groups_with_pagos(self, groups: Dict[str, FechaGrupoUI], *, categoria: CategoriaGrupo) -> None:
        """
        Enriquecer:
        - total_pagos: conteo de pagos en `pagos` por fecha + estado según categoria
        - total_monto: suma de monto_total en `pagos` por fecha + estado

        Esto permite:
        - que tu modal muestre “cuántos pagos hay en esa fecha”
        - y el total monetario del grupo
        """
        estado_pago = "pagado" if categoria == "pagado" else "pendiente"

        # Para no hacer N queries, resolvemos en batch por rango
        fechas = sorted(groups.keys())
        if not fechas:
            return

        # Hacemos un IN seguro (placeholders) en bloques razonables
        CHUNK = 100
        for i in range(0, len(fechas), CHUNK):
            chunk = fechas[i:i + CHUNK]
            placeholders = ", ".join(["%s"] * len(chunk))

            q = f"""
                SELECT
                    {self.P.FECHA_PAGO.value} AS fecha,
                    COUNT(*) AS total_pagos,
                    IFNULL(SUM({self.P.MONTO_TOTAL.value}), 0) AS total_monto
                FROM {self.P.TABLE.value}
                WHERE {self.P.FECHA_PAGO.value} IN ({placeholders})
                  AND {self.P.ESTADO.value}=%s
                GROUP BY {self.P.FECHA_PAGO.value}
            """
            params: Tuple[Any, ...] = tuple(chunk) + (estado_pago,)
            rows = self.db.get_data_list(q, params, dictionary=True) or []
            for r in rows:
                f = self.normalize_date(r.get("fecha"))
                if not f or f not in groups:
                    continue
                # Como FechaGrupoUI es frozen, reconstruimos
                prev = groups[f]
                groups[f] = FechaGrupoUI(
                    fecha=prev.fecha,
                    categoria=prev.categoria,
                    estado_grupo=prev.estado_grupo,
                    id_grupo=prev.id_grupo,
                    total_pagos=int(r.get("total_pagos") or 0),
                    total_monto=float(r.get("total_monto") or 0.0),
                )

    @staticmethod
    def _as_dict(x: FechaGrupoUI) -> Dict[str, Any]:
        return {
            "id_grupo": x.id_grupo,
            "fecha": x.fecha,
            "categoria": x.categoria,
            "estado_grupo": x.estado_grupo,
            "total_pagos": x.total_pagos,
            "total_monto": x.total_monto,
        }
