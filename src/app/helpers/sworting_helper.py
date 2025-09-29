# src/app/helpers/sworting_helper.py
from __future__ import annotations
from datetime import datetime, date
import unicodedata
from typing import Any, Callable, Dict, List, Optional


class Sworting:
    """
    Helper de ordenamiento reutilizable para todos los módulos.
    Soporta:
      - Texto (normalizado sin acentos, case-insensitive)
      - Números (conversión segura)
      - Fechas (YYYY-MM-DD o DD/MM/YYYY)
      - Completo/Incompleto (para asistencias)
      - Atajos listos para Empleados y Asistencias con desempates estables
    """

    # ---------- Normalizadores ----------
    @staticmethod
    def normalize_text(s: Any) -> str:
        s = "" if s is None else str(s)
        nfkd = unicodedata.normalize("NFKD", s)
        return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()

    @staticmethod
    def to_number(x: Any, default: float = 0.0) -> float:
        try:
            return float(str(x).strip()) if str(x).strip() != "" else float(default)
        except Exception:
            return float(default)

    @staticmethod
    def to_date(x: Any, default: date = date.min) -> date:
        if x is None:
            return default
        s = str(x).strip()
        if not s:
            return default
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                pass
        if isinstance(x, datetime):
            return x.date()
        if isinstance(x, date):
            return x
        return default

    # ---------- Núcleo de ordenamiento ----------
    @staticmethod
    def stable_sort(items: List[Dict], keyfunc: Callable[[Dict], Any], asc: bool = True,
                    tie_breakers: Optional[List[Callable[[Dict], Any]]] = None) -> List[Dict]:
        if not items:
            return items
        ordered = list(items)
        if tie_breakers:
            for tb in reversed(tie_breakers):
                ordered.sort(key=tb)
        ordered.sort(key=keyfunc, reverse=not asc)
        return ordered

    @staticmethod
    def sort_by_field(items: List[Dict], field: str, asc: bool = True, mode: str = "auto",
                      tie_breakers: Optional[List[Callable[[Dict], Any]]] = None) -> List[Dict]:
        if mode == "auto":
            if "fecha" in field:
                mode = "date"
            elif any(tok in field for tok in ("sueldo", "monto", "id", "numero", "horas")):
                mode = "number"
            else:
                mode = "text"

        if mode == "text":
            keyfunc = lambda r: Sworting.normalize_text(r.get(field, ""))
        elif mode == "number":
            keyfunc = lambda r: Sworting.to_number(r.get(field, 0))
        elif mode == "date":
            keyfunc = lambda r: Sworting.to_date(r.get(field))
        else:
            keyfunc = lambda r: r.get(field)

        return Sworting.stable_sort(items, keyfunc, asc=asc, tie_breakers=tie_breakers)

    # ---------- Lógica específica: asistencias ----------
    @staticmethod
    def is_asistencia_incomplete(r: Dict) -> bool:
        """
        Incompleto si falta: numero_nomina, fecha, hora_entrada o hora_salida.
        """
        if not str(r.get("numero_nomina", "")).isdigit():
            return True
        if not str(r.get("fecha", "")).strip():
            return True
        if not str(r.get("hora_entrada", "")).strip():
            return True
        if not str(r.get("hora_salida", "")).strip():
            return True
        return False

    @staticmethod
    def sort_asistencias(items: List[Dict], key: str, asc: bool = True,
                         incompletos_first: bool = True) -> List[Dict]:
        """
        key: 'numero_nomina' | 'fecha' | 'completo'
        - Coloca incompletos arriba si incompletos_first=True
        - Desempates: numero_nomina -> fecha
        """
        data = list(items)

        if incompletos_first:
            data.sort(key=lambda r: 0 if Sworting.is_asistencia_incomplete(r) else 1)

        tiebreakers = [
            lambda r: Sworting.to_number(r.get("numero_nomina", 0)),
            lambda r: Sworting.to_date(r.get("fecha")),
        ]

        if key == "numero_nomina":
            return Sworting.sort_by_field(data, "numero_nomina", asc=asc, mode="number", tie_breakers=tiebreakers)
        elif key == "fecha":
            return Sworting.sort_by_field(data, "fecha", asc=asc, mode="date", tie_breakers=tiebreakers)
        elif key == "completo":
            return Sworting.stable_sort(data, keyfunc=lambda r: 0, asc=True, tie_breakers=tiebreakers)
        else:
            return Sworting.sort_by_field(data, "fecha", asc=asc, mode="date", tie_breakers=tiebreakers)

    # ---------- Lógica específica: empleados ----------
    @staticmethod
    def sort_empleados(items: List[Dict], key: str, asc: bool = True) -> List[Dict]:
        """
        key: 'numero_nomina' | 'nombre_completo' | 'sueldo_por_hora'
        """
        data = list(items)
        tiebreakers = [lambda r: Sworting.to_number(r.get("numero_nomina", 0))]

        if key == "numero_nomina":
            return Sworting.sort_by_field(data, "numero_nomina", asc=asc, mode="number", tie_breakers=tiebreakers)
        elif key == "sueldo_por_hora":
            return Sworting.sort_by_field(data, "sueldo_por_hora", asc=asc, mode="number", tie_breakers=tiebreakers)
        elif key == "nombre_completo":
            return Sworting.stable_sort(
                data,
                keyfunc=lambda r: Sworting.normalize_text(r.get("nombre_completo", "")),
                asc=asc,
                tie_breakers=tiebreakers
            )
        else:
            return Sworting.sort_by_field(data, "numero_nomina", asc=asc, mode="number", tie_breakers=tiebreakers)
