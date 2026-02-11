from __future__ import annotations

from typing import Dict, Any, Optional
from decimal import Decimal, InvalidOperation

from app.core.interfaces.database_mysql import DatabaseMysql


class DescuentoDetallesModel:
    """
    Borrador temporal de descuentos por pago (NO escribe en la tabla final 'descuentos').

    Tabla real: descuento_detalles
      - id_pago_nomina UNIQUE
      - aplicado_imss / monto_imss
      - aplicado_transporte / monto_transporte
      - aplicado_extra / descripcion_extra / monto_extra

    Reglas robustas:
    - Un registro por id_pago_nomina (UNIQUE), con UPSERT.
    - Si aplicado_* es False => su monto se fuerza a NULL (evita residuos).
    - Sanitiza montos (>=0, finitos) y descripción limpia.
    - Bloquea aplicar a confirmados si el pago ya está pagado.
    """

    TABLE = "descuento_detalles"
    COL_ID = "id_detalle_descuento"
    COL_ID_PAGO = "id_pago_nomina"

    COL_APLICADO_IMSS = "aplicado_imss"
    COL_MONTO_IMSS = "monto_imss"

    COL_APLICADO_TRANSPORTE = "aplicado_transporte"
    COL_MONTO_TRANSPORTE = "monto_transporte"

    COL_APLICADO_EXTRA = "aplicado_extra"
    COL_DESCRIPCION_EXTRA = "descripcion_extra"
    COL_MONTO_EXTRA = "monto_extra"

    # límites razonables para evitar capturas absurdas
    _MAX_MONTO = Decimal("9999999.99")
    _MIN_MONTO = Decimal("0.00")

    def __init__(self):
        self.db = DatabaseMysql()
        # No forzamos CREATE TABLE aquí (ya existe en tu DB),
        # pero lo dejamos opcional por si se usa en ambientes nuevos.
        self._create_table_if_missing()

    # -------------------------------------------------------------
    def _create_table_if_missing(self) -> None:
        """
        Crea la tabla SOLO si no existe.
        Alineada con tu SHOW CREATE TABLE actual.
        """
        sql = f"""
        CREATE TABLE IF NOT EXISTS `{self.TABLE}` (
          `{self.COL_ID}` int NOT NULL AUTO_INCREMENT,
          `{self.COL_ID_PAGO}` int NOT NULL,
          `{self.COL_APLICADO_IMSS}` tinyint(1) NOT NULL DEFAULT '0',
          `{self.COL_MONTO_IMSS}` decimal(10,2) DEFAULT NULL,
          `{self.COL_APLICADO_TRANSPORTE}` tinyint(1) NOT NULL DEFAULT '0',
          `{self.COL_MONTO_TRANSPORTE}` decimal(10,2) DEFAULT NULL,
          `{self.COL_APLICADO_EXTRA}` tinyint(1) NOT NULL DEFAULT '0',
          `{self.COL_DESCRIPCION_EXTRA}` varchar(255) DEFAULT NULL,
          `{self.COL_MONTO_EXTRA}` decimal(10,2) DEFAULT NULL,
          `fecha_creacion` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
          `fecha_modificacion` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (`{self.COL_ID}`),
          UNIQUE KEY `{self.COL_ID_PAGO}` (`{self.COL_ID_PAGO}`),
          CONSTRAINT `fk_desc_det_pagos` FOREIGN KEY (`{self.COL_ID_PAGO}`)
            REFERENCES `pagos` (`id_pago_nomina`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """
        try:
            self.db.run_query(sql)
        except Exception:
            # si no puede crear por permisos o ya existe con otro collation, no rompemos la app
            pass

    # -------------------------------------------------------------
    def upsert_detalles(self, id_pago_nomina: int, detalles: Dict[str, Any]) -> Dict[str, Any]:
        """
        Guarda el borrador NORMALIZANDO:
        - aplicado=False => monto=NULL y desc_extra=NULL
        - aplicado=True => monto Decimal(0.01) (si vacío/invalid => 0.00)
        """
        try:
            id_pago_nomina = int(id_pago_nomina)
            if id_pago_nomina <= 0:
                return {"status": "error", "message": "id_pago_nomina inválido."}

            norm = self._normalizar_detalles(detalles or {})

            q = f"""
            INSERT INTO {self.TABLE} (
                {self.COL_ID_PAGO},
                {self.COL_APLICADO_IMSS}, {self.COL_MONTO_IMSS},
                {self.COL_APLICADO_TRANSPORTE}, {self.COL_MONTO_TRANSPORTE},
                {self.COL_APLICADO_EXTRA}, {self.COL_DESCRIPCION_EXTRA}, {self.COL_MONTO_EXTRA}
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                {self.COL_APLICADO_IMSS}=VALUES({self.COL_APLICADO_IMSS}),
                {self.COL_MONTO_IMSS}=VALUES({self.COL_MONTO_IMSS}),
                {self.COL_APLICADO_TRANSPORTE}=VALUES({self.COL_APLICADO_TRANSPORTE}),
                {self.COL_MONTO_TRANSPORTE}=VALUES({self.COL_MONTO_TRANSPORTE}),
                {self.COL_APLICADO_EXTRA}=VALUES({self.COL_APLICADO_EXTRA}),
                {self.COL_DESCRIPCION_EXTRA}=VALUES({self.COL_DESCRIPCION_EXTRA}),
                {self.COL_MONTO_EXTRA}=VALUES({self.COL_MONTO_EXTRA})
            """

            vals = (
                id_pago_nomina,
                1 if norm[self.COL_APLICADO_IMSS] else 0,
                self._to_db_decimal(norm[self.COL_MONTO_IMSS]),
                1 if norm[self.COL_APLICADO_TRANSPORTE] else 0,
                self._to_db_decimal(norm[self.COL_MONTO_TRANSPORTE]),
                1 if norm[self.COL_APLICADO_EXTRA] else 0,
                norm[self.COL_DESCRIPCION_EXTRA],
                self._to_db_decimal(norm[self.COL_MONTO_EXTRA]),
            )

            self.db.run_query(q, vals)

            # Sincroniza el total del borrador en pagos.monto_descuento
            # para que otros recálculos que lean desde pagos usen el valor vigente.
            total_desc = self._total_descuento_desde_norm(norm)
            sync = self._sync_monto_descuento_pago(
                id_pago_nomina=id_pago_nomina,
                total_descuento=total_desc,
            )
            if (sync or {}).get("status") != "success":
                return {
                    "status": "error",
                    "message": (sync or {}).get("message", "No se pudo sincronizar monto_descuento en pagos."),
                    "detalles_normalizados": norm,
                }

            return {
                "status": "success",
                "detalles_normalizados": norm,
                "sync_pago": sync,
            }

        except Exception as ex:
            return {"status": "error", "message": f"Error al guardar borrador: {ex}"}

    # -------------------------------------------------------------
    def obtener_por_id_pago(self, id_pago_nomina: int) -> Optional[Dict[str, Any]]:
        """
        Devuelve el borrador guardado como dict.
        Si no existe, devuelve None.
        """
        try:
            id_pago_nomina = int(id_pago_nomina)
            if id_pago_nomina <= 0:
                return None
            q = f"SELECT * FROM {self.TABLE} WHERE {self.COL_ID_PAGO}=%s LIMIT 1"
            return self.db.get_data(q, (id_pago_nomina,), dictionary=True)
        except Exception:
            return None

    # -------------------------------------------------------------
    def eliminar_por_id_pago(self, id_pago_nomina: int) -> Dict[str, Any]:
        try:
            id_pago_nomina = int(id_pago_nomina)
            if id_pago_nomina <= 0:
                return {"status": "error", "message": "id_pago_nomina inválido."}
            q = f"DELETE FROM {self.TABLE} WHERE {self.COL_ID_PAGO}=%s"
            self.db.run_query(q, (id_pago_nomina,))
            return {"status": "success"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al borrar borrador: {ex}"}

    # -------------------------------------------------------------
    def aplicar_a_descuentos_y_limpiar(self, id_pago_nomina: int, discount_model) -> Dict[str, Any]:
        """
        Aplica el borrador a 'descuentos' (confirmados) usando DiscountModel y luego limpia el borrador.

        Reglas:
        - Si el pago ya está pagado => NO aplica.
        - Si no hay borrador => no hace nada.
        - Si borrador no tiene nada aplicado => no sobreescribe.
        """
        try:
            id_pago_nomina = int(id_pago_nomina)
            if id_pago_nomina <= 0:
                return {"status": "error", "message": "id_pago_nomina inválido."}

            if self.pago_esta_pagado(id_pago_nomina):
                return {"status": "error", "message": "El pago ya está pagado; no se pueden aplicar descuentos."}

            det = self.obtener_por_id_pago(id_pago_nomina)
            if not det:
                return {"status": "info", "message": "No se aplicó borrador (no existe registro temporal)."}

            numero_nomina = self._get_numero_nomina_de_pago(id_pago_nomina)
            if not numero_nomina:
                return {"status": "error", "message": "No se pudo resolver número de nómina para este pago."}

            norm = self._normalizar_detalles(det)

            if not self._hay_algo_aplicado(norm):
                return {
                    "status": "info",
                    "message": "Borrador existe pero no contiene descuentos aplicados; no se sobreescribió nada.",
                    "detalles_normalizados": norm,
                }

            # delega a tu DiscountModel (tú ya lo tienes)
            res = discount_model.guardar_descuentos_confirmados(
                id_pago=id_pago_nomina,
                numero_nomina=numero_nomina,
                aplicar_imss=bool(norm[self.COL_APLICADO_IMSS]),
                monto_imss=float(norm[self.COL_MONTO_IMSS] or Decimal("0.00")),
                aplicar_transporte=bool(norm[self.COL_APLICADO_TRANSPORTE]),
                monto_transporte=float(norm[self.COL_MONTO_TRANSPORTE] or Decimal("0.00")),
                aplicar_extra=bool(norm[self.COL_APLICADO_EXTRA]),
                monto_extra=float(norm[self.COL_MONTO_EXTRA] or Decimal("0.00")),
                descripcion_extra=(norm[self.COL_DESCRIPCION_EXTRA] or "").strip(),
            )
            if (res or {}).get("status") != "success":
                return res

            self.eliminar_por_id_pago(id_pago_nomina)
            return {
                "status": "success",
                "message": "Descuentos aplicados y borrador eliminado.",
                "detalles_normalizados": norm,
            }
        except Exception as ex:
            return {"status": "error", "message": f"Error al aplicar borrador: {ex}"}

    # -------------------------------------------------------------
    def _get_numero_nomina_de_pago(self, id_pago_nomina: int) -> Optional[int]:
        try:
            q = "SELECT numero_nomina FROM pagos WHERE id_pago_nomina=%s"
            r = self.db.get_data(q, (int(id_pago_nomina),), dictionary=True)
            return int(r["numero_nomina"]) if r and r.get("numero_nomina") is not None else None
        except Exception:
            return None

    def pago_esta_pagado(self, id_pago_nomina: int) -> bool:
        try:
            q = "SELECT estado FROM pagos WHERE id_pago_nomina=%s"
            r = self.db.get_data(q, (int(id_pago_nomina),), dictionary=True)
            return str((r or {}).get("estado") or "").strip().lower() == "pagado"
        except Exception:
            return False

    # =========================
    # Normalización / validación
    # =========================
    def _normalizar_detalles(self, detalles: Dict[str, Any]) -> Dict[str, Any]:
        """
        Devuelve un dict coherente:
        - aplicado_* siempre bool
        - montos siempre Decimal(0.01) o None
        - si aplicado=False => monto=None y descripcion=None (extra)
        """
        aplicar_imss = bool(detalles.get(self.COL_APLICADO_IMSS, False))
        aplicar_transporte = bool(detalles.get(self.COL_APLICADO_TRANSPORTE, False))
        aplicar_extra = bool(detalles.get(self.COL_APLICADO_EXTRA, False))

        monto_imss = self._money_or_none(detalles.get(self.COL_MONTO_IMSS)) if aplicar_imss else None
        monto_transporte = self._money_or_none(detalles.get(self.COL_MONTO_TRANSPORTE)) if aplicar_transporte else None
        monto_extra = self._money_or_none(detalles.get(self.COL_MONTO_EXTRA)) if aplicar_extra else None

        desc_extra = (detalles.get(self.COL_DESCRIPCION_EXTRA) or "").strip() if aplicar_extra else ""
        if not desc_extra:
            desc_extra = None

        return {
            self.COL_APLICADO_IMSS: aplicar_imss,
            self.COL_MONTO_IMSS: monto_imss,
            self.COL_APLICADO_TRANSPORTE: aplicar_transporte,
            self.COL_MONTO_TRANSPORTE: monto_transporte,
            self.COL_APLICADO_EXTRA: aplicar_extra,
            self.COL_DESCRIPCION_EXTRA: desc_extra,
            self.COL_MONTO_EXTRA: monto_extra,
        }

    def _hay_algo_aplicado(self, norm: Dict[str, Any]) -> bool:
        mi = norm.get(self.COL_MONTO_IMSS) or Decimal("0.00")
        mt = norm.get(self.COL_MONTO_TRANSPORTE) or Decimal("0.00")
        me = norm.get(self.COL_MONTO_EXTRA) or Decimal("0.00")
        de = (norm.get(self.COL_DESCRIPCION_EXTRA) or "").strip()

        if norm.get(self.COL_APLICADO_IMSS) and mi > 0:
            return True
        if norm.get(self.COL_APLICADO_TRANSPORTE) and mt > 0:
            return True
        if norm.get(self.COL_APLICADO_EXTRA) and (me > 0 or bool(de)):
            return True
        return False

    def _total_descuento_desde_norm(self, norm: Dict[str, Any]) -> Decimal:
        mi = norm.get(self.COL_MONTO_IMSS) if norm.get(self.COL_APLICADO_IMSS) else Decimal("0.00")
        mt = norm.get(self.COL_MONTO_TRANSPORTE) if norm.get(self.COL_APLICADO_TRANSPORTE) else Decimal("0.00")
        me = norm.get(self.COL_MONTO_EXTRA) if norm.get(self.COL_APLICADO_EXTRA) else Decimal("0.00")
        return (mi or Decimal("0.00")) + (mt or Decimal("0.00")) + (me or Decimal("0.00"))

    def _sync_monto_descuento_pago(self, *, id_pago_nomina: int, total_descuento: Decimal) -> Dict[str, Any]:
        """
        Escribe el total del borrador en pagos.monto_descuento y recalcula
        monto_total + pago_efectivo + saldo para mantener consistencia completa
        tras editar descuentos en pendientes.
        """
        try:
            id_pago_nomina = int(id_pago_nomina)
            total_desc = float(total_descuento or 0)

            row_cur = self.db.get_data(
                """
                SELECT monto_base, monto_prestamo, pago_deposito
                FROM pagos
                WHERE id_pago_nomina=%s
                """,
                (id_pago_nomina,),
                dictionary=True,
            ) or {}
            if not row_cur:
                return {"status": "error", "message": f"No existe pago #{id_pago_nomina} para sincronizar."}

            monto_base = float(row_cur.get("monto_base") or 0.0)
            monto_prestamo = float(row_cur.get("monto_prestamo") or 0.0)
            deposito = float(row_cur.get("pago_deposito") or 0.0)

            monto_total = round(max(0.0, monto_base - total_desc - monto_prestamo), 2)
            calc = self._calcular_efectivo_y_saldo(monto_total=monto_total, deposito=deposito)
            efectivo = float(calc.get("pago_efectivo", 0.0))
            saldo = float(calc.get("saldo", 0.0))

            q = """
                UPDATE pagos
                SET monto_descuento = %s,
                    monto_total = %s,
                    pago_efectivo = %s,
                    saldo = %s
                WHERE id_pago_nomina = %s
            """
            self.db.run_query(
                q,
                (
                    self._to_db_decimal(Decimal(str(total_desc))),
                    f"{monto_total:.2f}",
                    f"{efectivo:.2f}",
                    f"{saldo:.2f}",
                    id_pago_nomina,
                ),
            )

            row = self.db.get_data(
                "SELECT monto_descuento, monto_total, pago_efectivo, saldo FROM pagos WHERE id_pago_nomina=%s",
                (id_pago_nomina,),
                dictionary=True,
            ) or {}
            return {
                "status": "success",
                "id_pago_nomina": id_pago_nomina,
                "monto_descuento": row.get("monto_descuento"),
                "monto_total": row.get("monto_total"),
                "pago_efectivo": row.get("pago_efectivo"),
                "saldo": row.get("saldo"),
            }
        except Exception as ex:
            return {"status": "error", "message": f"Fallo al sincronizar pago #{id_pago_nomina}: {ex}"}

    @staticmethod
    def _calcular_efectivo_y_saldo(*, monto_total: float, deposito: float) -> Dict[str, float]:
        """
        Regla billetes de $50 (igual a la vista):
        - resto = monto_total - deposito
        - resto <= 0: efectivo=0, saldo=resto
        - resto > 0:
          residuo = resto % 50
          residuo >= 25 -> efectivo sube al siguiente 50, saldo negativo
          residuo < 25  -> saldo positivo por ajustar
        """
        try:
            mt_c = int(round(float(monto_total or 0.0) * 100))
            dp_c = int(round(float(deposito or 0.0) * 100))
            resto_c = mt_c - dp_c

            if resto_c <= 0:
                return {"pago_efectivo": 0.0, "saldo": round(resto_c / 100.0, 2)}

            cincuenta_c = 5000
            veinticinco_c = 2500
            residuo_c = resto_c % cincuenta_c
            efectivo_c = resto_c - residuo_c

            if residuo_c >= veinticinco_c:
                efectivo_c += cincuenta_c
                saldo_c = -(cincuenta_c - residuo_c)
            else:
                saldo_c = residuo_c

            if efectivo_c < 0:
                efectivo_c = 0

            return {
                "pago_efectivo": round(efectivo_c / 100.0, 2),
                "saldo": round(saldo_c / 100.0, 2),
            }
        except Exception:
            return {"pago_efectivo": 0.0, "saldo": 0.0}

    def _money_or_none(self, v) -> Optional[Decimal]:
        """
        Parsea montos con reglas seguras:
        - vacío/None/invalid => Decimal('0.00') si está aplicado
        - negativos => 0.00
        - > MAX => MAX
        - cuantiza a 2 decimales
        """
        d = self._to_decimal(v)
        if d is None:
            return Decimal("0.00")

        if d.is_nan() or d.is_infinite():
            return Decimal("0.00")

        if d < self._MIN_MONTO:
            d = self._MIN_MONTO
        if d > self._MAX_MONTO:
            d = self._MAX_MONTO

        return d.quantize(Decimal("0.01"))

    @staticmethod
    def _to_decimal(v) -> Optional[Decimal]:
        try:
            if v is None:
                return None
            s = str(v).strip()
            if not s:
                return None
            s = s.replace("$", "").replace(",", "")
            return Decimal(s)
        except (InvalidOperation, ValueError, TypeError):
            return None

    @staticmethod
    def _to_db_decimal(d: Optional[Decimal]) -> Optional[str]:
        """
        Convierte Decimal a string para DB o None.
        (Evita sorpresas con drivers.)
        """
        if d is None:
            return None
        try:
            return f"{Decimal(d):.2f}"
        except Exception:
            return None
