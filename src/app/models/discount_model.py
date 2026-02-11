# app/models/discount_model.py
from __future__ import annotations

from datetime import date
from typing import Dict, Any, List, Optional

from app.core.enums.e_discount_model import E_DISCOUNT
from app.core.interfaces.database_mysql import DatabaseMysql


class DiscountModel:
    """
    Lógica de DESCUENTOS (persistidos). NO maneja 'comida'.

    IMPORTANTE (cambio solicitado):
    - Los defaults (50/100) NO deben aplicarse automáticamente al confirmar desde el modal.
    - Los valores por default los manejará el contenedor (UI), no este modelo al confirmar.
    - Para usos “rápidos” (agregar_descuentos_opcionales) se mantiene el comportamiento legacy con defaults.
    """

    DEFAULT_IMSS = 50.0
    DEFAULT_TRANSPORTE = 100.0

    def __init__(self):
        self.db = DatabaseMysql()
        self.E = E_DISCOUNT
        self._exists_table = self._check_table()

    # ---------------------------------------------------------------------
    # Infraestructura / Esquema
    # ---------------------------------------------------------------------
    def _check_table(self) -> bool:
        try:
            q_tbl = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            r_tbl = self.db.get_data(q_tbl, (self.db.database, self.E.TABLE.value), dictionary=True)
            if (r_tbl or {}).get("c", 0) > 0:
                self._migrate_schema()
                return True
            self._create_table()
            return True
        except Exception:
            return False

    def _create_table(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self.E.TABLE.value} (
            {self.E.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
            {self.E.PRESTAMO_NUMERO_NOMINA.value} SMALLINT UNSIGNED NOT NULL,
            {self.E.ID_PAGO.value} INT DEFAULT NULL,
            {self.E.TIPO.value} VARCHAR(50) NOT NULL,
            {self.E.DESCRIPCION.value} VARCHAR(100) DEFAULT NULL,
            {self.E.MONTO_DESCUENTO.value} DECIMAL(10,2) NOT NULL,
            {self.E.FECHA_APLICACION.value} DATE NOT NULL,
            {self.E.FECHA_CREACION.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY ({self.E.PRESTAMO_NUMERO_NOMINA.value})
                REFERENCES empleados({self.E.PRESTAMO_NUMERO_NOMINA.value})
                ON DELETE CASCADE,
            FOREIGN KEY ({self.E.ID_PAGO.value})
                REFERENCES pagos(id_pago_nomina)
                ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        self.db.run_query(query)

    def _migrate_schema(self) -> None:
        """
        Migra columnas/llaves antiguas (id_pago -> id_pago_nomina).
        """
        try:
            columns = self._get_columns_meta()
            target = self.E.ID_PAGO.value.lower()
            if target not in columns and "id_pago" in columns:
                self._rename_legacy_column()
                columns = self._get_columns_meta()
            self._ensure_fk_to_pagos()
        except Exception as ex:
            print(f"⚠️ No se pudo actualizar la tabla {self.E.TABLE.value}: {ex}")

    def _get_columns_meta(self) -> Dict[str, Dict[str, Any]]:
        q = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
        """
        rows = self.db.get_data_list(q, (self.db.database, self.E.TABLE.value), dictionary=True) or []
        cols: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            name = row.get("COLUMN_NAME") or row.get("column_name")
            if not name:
                continue
            cols[str(name).lower()] = row
        return cols

    def _rename_legacy_column(self) -> None:
        self._drop_fk_to_pagos()
        sql = f"""
            ALTER TABLE {self.E.TABLE.value}
            CHANGE COLUMN id_pago {self.E.ID_PAGO.value} INT DEFAULT NULL
        """
        self.db.run_query(sql)
        print("✅ Columna 'id_pago' renombrada a 'id_pago_nomina' en descuentos.")

    def _drop_fk_to_pagos(self) -> None:
        q = """
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = %s
              AND REFERENCED_TABLE_NAME = 'pagos'
        """
        rows = self.db.get_data_list(q, (self.db.database, self.E.TABLE.value), dictionary=True) or []
        for row in rows:
            constraint = row.get("CONSTRAINT_NAME")
            if not constraint:
                continue
            try:
                self.db.run_query(f"ALTER TABLE {self.E.TABLE.value} DROP FOREIGN KEY {constraint}")
                print(f"⚠️ FK '{constraint}' eliminada en {self.E.TABLE.value}.")
            except Exception as ex:
                print(f"⚠️ No se pudo eliminar FK {constraint}: {ex}")

    def _ensure_fk_to_pagos(self) -> None:
        q = """
            SELECT CONSTRAINT_NAME, REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = %s
              AND REFERENCED_TABLE_NAME = 'pagos'
        """
        rows = self.db.get_data_list(q, (self.db.database, self.E.TABLE.value), dictionary=True) or []
        for row in rows:
            if row.get("REFERENCED_COLUMN_NAME") == self.E.ID_PAGO.value:
                return  # FK ya actualizada
        sql = f"""
            ALTER TABLE {self.E.TABLE.value}
            ADD CONSTRAINT fk_descuentos_pago_nomina
                FOREIGN KEY ({self.E.ID_PAGO.value})
                REFERENCES pagos({self.E.ID_PAGO.value})
                ON DELETE SET NULL
        """
        self.db.run_query(sql)
        print("✅ FK de descuentos -> pagos actualizada.")

    # ---------------------------------------------------------------------
    # Inserción / upserts
    # ---------------------------------------------------------------------
    def agregar_descuento(
        self,
        numero_nomina: int,
        tipo: str,
        descripcion: Optional[str],
        monto: float,
        id_pago: Optional[int] = None,
        fecha_aplicacion: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Inserta un descuento (uso interno; limpiar por id_pago antes si deseas upsert)."""
        try:
            monto = float(monto or 0.0)
            if monto < 0:
                return {"status": "error", "message": "El monto no puede ser negativo"}

            q = f"""
            INSERT INTO {self.E.TABLE.value} (
                {self.E.PRESTAMO_NUMERO_NOMINA.value}, {self.E.ID_PAGO.value}, {self.E.TIPO.value},
                {self.E.DESCRIPCION.value}, {self.E.MONTO_DESCUENTO.value}, {self.E.FECHA_APLICACION.value}
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(
                q,
                (
                    int(numero_nomina),
                    id_pago,
                    str(tipo),
                    (descripcion or None),
                    monto,
                    (fecha_aplicacion or date.today()),
                ),
            )
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def agregar_descuentos_opcionales(
        self,
        *,
        id_pago: int,
        numero_nomina: int,
        aplicar_imss: bool = False,
        monto_imss: float = 0.0,
        aplicar_transporte: bool = False,
        monto_transporte: float = 0.0,
        aplicar_extra: bool = False,
        monto_extra: float = 0.0,
        descripcion_extra: str = "",
        fecha_aplicacion: Optional[date] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Inserta descuentos con defaults internos SOLO si los montos recibidos no son válidos (>0).
        Pensado para usos “rápidos”; para confirmación real, usa guardar_descuentos_confirmados(...)
        o copiar_desde_borrador(...).
        """
        try:
            if aplicar_imss:
                monto_final = float(monto_imss or 0.0)
                if monto_final <= 0:
                    monto_final = self.DEFAULT_IMSS
                self.agregar_descuento(
                    numero_nomina, "retenciones_imss", "Cuota IMSS", monto_final, id_pago, fecha_aplicacion
                )

            if aplicar_transporte:
                monto_final = float(monto_transporte or 0.0)
                if monto_final <= 0:
                    monto_final = self.DEFAULT_TRANSPORTE
                self.agregar_descuento(
                    numero_nomina, "transporte", "Pasaje diario", monto_final, id_pago, fecha_aplicacion
                )

            if aplicar_extra and (float(monto_extra or 0.0) > 0) and descripcion_extra:
                self.agregar_descuento(
                    numero_nomina,
                    "descuento_extra",
                    descripcion_extra.strip(),
                    float(monto_extra),
                    id_pago,
                    fecha_aplicacion,
                )

            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def guardar_descuentos_confirmados(
        self,
        *,
        id_pago: int,
        numero_nomina: int,
        aplicar_imss: bool,
        monto_imss: float,
        aplicar_transporte: bool,
        monto_transporte: float,
        aplicar_extra: bool,
        monto_extra: float,
        descripcion_extra: str,
        fecha_aplicacion: Optional[date] = None,
        # 🔒 Nuevos flags seguros (no rompen llamadas existentes)
        aplicar_defaults_si_monto_invalido: bool = False,
        no_borrar_si_no_hay_aplicables: bool = True,
    ) -> Dict[str, Any]:
        """
        Guarda definitivamente los descuentos de un pago (limpia y vuelve a insertar).

        🔒 Cambio solicitado (por defecto):
        - NO aplica defaults si el monto recibido es <= 0.
        - Si no hay nada aplicable, NO borra descuentos existentes (evita “confirmar vacío”).
        """
        try:
            id_pago = int(id_pago)
            numero_nomina = int(numero_nomina)

            def _f(v) -> float:
                try:
                    return float(v or 0.0)
                except Exception:
                    return 0.0

            mi = _f(monto_imss)
            mt = _f(monto_transporte)
            me = _f(monto_extra)
            desc = (descripcion_extra or "").strip()

            # No permitir negativos
            if mi < 0:
                mi = 0.0
            if mt < 0:
                mt = 0.0
            if me < 0:
                me = 0.0

            # Determina si hay algo realmente aplicable
            # IMSS/Transporte: aplicable si monto>0 o si explícitamente quieres defaults
            hay_imss = bool(aplicar_imss) and (mi > 0 or aplicar_defaults_si_monto_invalido)
            hay_trans = bool(aplicar_transporte) and (mt > 0 or aplicar_defaults_si_monto_invalido)
            # Extra: requiere monto>0 y descripción
            hay_extra = bool(aplicar_extra) and (me > 0 and bool(desc))

            if no_borrar_si_no_hay_aplicables and not (hay_imss or hay_trans or hay_extra):
                return {
                    "status": "info",
                    "message": "No se guardó nada porque no hay descuentos aplicables (evité borrar descuentos existentes).",
                    "aplicables": {"imss": hay_imss, "transporte": hay_trans, "extra": hay_extra},
                }

            # Limpia y vuelve a insertar (idempotente)
            self.eliminar_por_id_pago(id_pago)

            warnings: List[str] = []

            # IMSS
            if bool(aplicar_imss):
                monto_final = mi
                if monto_final <= 0 and aplicar_defaults_si_monto_invalido:
                    monto_final = float(self.DEFAULT_IMSS)
                if monto_final > 0:
                    self.agregar_descuento(
                        numero_nomina, "retenciones_imss", "Cuota IMSS", monto_final, id_pago, fecha_aplicacion
                    )
                else:
                    warnings.append("IMSS marcado pero monto inválido/0: no se insertó (sin defaults).")

            # Transporte
            if bool(aplicar_transporte):
                monto_final = mt
                if monto_final <= 0 and aplicar_defaults_si_monto_invalido:
                    monto_final = float(self.DEFAULT_TRANSPORTE)
                if monto_final > 0:
                    self.agregar_descuento(
                        numero_nomina, "transporte", "Pasaje diario", monto_final, id_pago, fecha_aplicacion
                    )
                else:
                    warnings.append("Transporte marcado pero monto inválido/0: no se insertó (sin defaults).")

            # Extra
            if bool(aplicar_extra):
                if me > 0:
                    if not desc:
                        desc = "Descuento extra"
                    self.agregar_descuento(
                        numero_nomina, "descuento_extra", desc, me, id_pago, fecha_aplicacion
                    )
                else:
                    warnings.append("Extra marcado pero falta monto>0: no se insertó.")

            return {"status": "success", "warnings": warnings}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ---------------------------------------------------------------------
    # 🔧 Helper clave: copiar desde el BORRADOR del modal (DescuentoDetallesModel)
    # ---------------------------------------------------------------------
    def copiar_desde_borrador(
        self,
        *,
        id_pago: int,
        numero_nomina: int,
        detalles_model,  # instancia de DescuentoDetallesModel
        fecha_aplicacion: Optional[date] = None,
        preferir_default_si_monto_no_valido: bool = True,
    ) -> Dict[str, Any]:
        """
        Copia los descuentos desde el borrador al registro definitivo.

        Cambio solicitado:
        - Evitar defaults automáticos en confirmación si no quieres (puedes pasar preferir_default...=False).
        - Evitar borrar confirmados si el borrador no trae nada aplicable (protección).
        """
        try:
            id_pago = int(id_pago)
            numero_nomina = int(numero_nomina)

            # 1️⃣ Leer borrador actual (detalles temporales)
            det = detalles_model.obtener_por_id_pago(id_pago) or {}

            apl_imss = bool(det.get(detalles_model.COL_APLICADO_IMSS, False))
            mon_imss = float(det.get(detalles_model.COL_MONTO_IMSS, 0) or 0)

            apl_trans = bool(det.get(detalles_model.COL_APLICADO_TRANSPORTE, False))
            mon_trans = float(det.get(detalles_model.COL_MONTO_TRANSPORTE, 0) or 0)

            apl_extra = bool(det.get(detalles_model.COL_APLICADO_EXTRA, False))
            mon_extra = float(det.get(detalles_model.COL_MONTO_EXTRA, 0) or 0)
            desc_extra = (
                det.get(getattr(detalles_model, "COL_DESC_EXTRA", "descripcion_extra"), "") or ""
            ).strip()

            # Normaliza negativos
            if mon_imss < 0:
                mon_imss = 0.0
            if mon_trans < 0:
                mon_trans = 0.0
            if mon_extra < 0:
                mon_extra = 0.0

            # 2️⃣ Si el borrador no trae nada aplicable, NO borrar confirmados existentes
            hay_imss = apl_imss and (mon_imss > 0 or preferir_default_si_monto_no_valido)
            hay_trans = apl_trans and (mon_trans > 0 or preferir_default_si_monto_no_valido)
            hay_extra = apl_extra and (mon_extra > 0 and bool(desc_extra))

            if not (hay_imss or hay_trans or hay_extra):
                return {
                    "status": "info",
                    "message": "Borrador no contiene descuentos aplicables; no se sobreescribió nada.",
                }

            # 3️⃣ Leer descuentos actuales en DB antes de limpiar (por si necesitas reusar)
            descuentos_previos = self.get_descuentos_por_pago(id_pago)
            prev_map = {d["tipo"]: float(d["monto"]) for d in descuentos_previos if d.get("tipo")}

            # 4️⃣ Limpiar y reinsertar
            self.eliminar_por_id_pago(id_pago)

            # ---------- IMSS ----------
            if apl_imss:
                monto_final = mon_imss
                if monto_final <= 0:
                    # usar monto previo o default (controlado por flag)
                    if "retenciones_imss" in prev_map:
                        monto_final = prev_map["retenciones_imss"]
                    elif preferir_default_si_monto_no_valido:
                        monto_final = self.DEFAULT_IMSS
                if monto_final > 0:
                    self.agregar_descuento(
                        numero_nomina, "retenciones_imss", "Cuota IMSS", monto_final, id_pago, fecha_aplicacion
                    )

            # ---------- Transporte ----------
            if apl_trans:
                monto_final = mon_trans
                if monto_final <= 0:
                    if "transporte" in prev_map:
                        monto_final = prev_map["transporte"]
                    elif preferir_default_si_monto_no_valido:
                        monto_final = self.DEFAULT_TRANSPORTE
                if monto_final > 0:
                    self.agregar_descuento(
                        numero_nomina, "transporte", "Pasaje diario", monto_final, id_pago, fecha_aplicacion
                    )

            # ---------- Extra ----------
            if apl_extra:
                if mon_extra > 0:
                    if not desc_extra:
                        desc_extra = "Descuento extra"
                    self.agregar_descuento(
                        numero_nomina, "descuento_extra", desc_extra, mon_extra, id_pago, fecha_aplicacion
                    )
                elif "descuento_extra" in prev_map:
                    if not desc_extra:
                        desc_extra = "Descuento extra"
                    # reusar monto previo si no hubo cambio
                    self.agregar_descuento(
                        numero_nomina,
                        "descuento_extra",
                        desc_extra,
                        prev_map["descuento_extra"],
                        id_pago,
                        fecha_aplicacion,
                    )

            return {"status": "success"}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ---------------------------------------------------------------------
    # Eliminación / Consulta / Resumen
    # ---------------------------------------------------------------------
    def eliminar_por_id_pago(self, id_pago: int) -> Dict[str, Any]:
        try:
            q = f"DELETE FROM {self.E.TABLE.value} WHERE {self.E.ID_PAGO.value}=%s"
            self.db.run_query(q, (id_pago,))
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # Alias por compatibilidad con patches/ejemplos
    delete_by_pago = eliminar_por_id_pago

    def get_descuentos_por_pago(self, id_pago: int) -> List[Dict[str, Any]]:
        try:
            q = f"""
            SELECT {self.E.TIPO.value} AS tipo, {self.E.DESCRIPCION.value} AS descripcion,
                {self.E.MONTO_DESCUENTO.value} AS monto
            FROM {self.E.TABLE.value}
            WHERE {self.E.ID_PAGO.value}=%s
            """
            return self.db.get_data_list(q, (id_pago,), dictionary=True) or []
        except Exception:
            return []

    def get_total_descuentos_por_pago(self, id_pago: int) -> float:
        try:
            q = f"""
            SELECT IFNULL(SUM({self.E.MONTO_DESCUENTO.value}), 0) AS total
            FROM {self.E.TABLE.value}
            WHERE {self.E.ID_PAGO.value}=%s
            """
            r = self.db.get_data(q, (id_pago,), dictionary=True)
            return float((r or {}).get("total", 0) or 0)
        except Exception:
            return 0.0

    def resumen_por_pago(self, id_pago: int) -> Dict[str, Any]:
        try:
            ds = self.get_descuentos_por_pago(id_pago)
            total = sum(float(d.get("monto", 0) or 0) for d in ds)
            return {"status": "success", "descuentos": ds, "total": round(total, 2)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def tiene_descuentos_guardados(self, id_pago: int) -> bool:
        try:
            q = f"SELECT COUNT(*) AS c FROM {self.E.TABLE.value} WHERE {self.E.ID_PAGO.value}=%s"
            r = self.db.get_data(q, (id_pago,), dictionary=True)
            return (r or {}).get("c", 0) > 0
        except Exception:
            return False
