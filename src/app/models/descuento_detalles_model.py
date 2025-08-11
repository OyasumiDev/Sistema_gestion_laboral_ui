# app/models/descuento_detalles_model.py
from typing import Dict, Any, Optional
from app.core.interfaces.database_mysql import DatabaseMysql

# Si tienes el enum, ajústalo a estos nombres:
# - E.TABLE -> "descuento_detalles"
# - E.ID -> "id_detalle_descuento"
# - E.ID_PAGO -> "id_pago_nomina"   <-- ¡clave!
# - E.APLICADO_IMSS -> "aplicado_imss"
# - E.MONTO_IMSS -> "monto_imss"
# - E.APLICADO_TRANSPORTE -> "aplicado_transporte"
# - E.MONTO_TRANSPORTE -> "monto_transporte"
# - E.APLICADO_EXTRA -> "aplicado_extra"
# - E.DESCRIPCION_EXTRA -> "descripcion_extra"
# - E.MONTO_EXTRA -> "monto_extra"

class DescuentoDetallesModel:
    """
    Borrador de descuentos por pago (no escribe en la tabla final 'descuentos').
    - Sin 'comida' (eliminado del flujo).
    - Un registro por id_pago_nomina (UNIQUE), con UPSERT.
    - No aplica defaults de negocio (IMSS=50 vive en el FRONT).
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

    def __init__(self):
        self.db = DatabaseMysql()
        self._create_table()

    def _create_table(self):
        # FK explícita hacia pagos(id_pago_nomina); UNIQUE para tener un borrador por pago.
        sql = f"""
        CREATE TABLE IF NOT EXISTS {self.TABLE} (
            {self.COL_ID} INT AUTO_INCREMENT PRIMARY KEY,
            {self.COL_ID_PAGO} INT NOT NULL UNIQUE,

            {self.COL_APLICADO_IMSS} BOOLEAN NOT NULL DEFAULT FALSE,
            {self.COL_MONTO_IMSS} DECIMAL(10,2) DEFAULT NULL,

            {self.COL_APLICADO_TRANSPORTE} BOOLEAN NOT NULL DEFAULT FALSE,
            {self.COL_MONTO_TRANSPORTE} DECIMAL(10,2) DEFAULT NULL,

            {self.COL_APLICADO_EXTRA} BOOLEAN NOT NULL DEFAULT FALSE,
            {self.COL_DESCRIPCION_EXTRA} VARCHAR(100) DEFAULT NULL,
            {self.COL_MONTO_EXTRA} DECIMAL(10,2) DEFAULT NULL,

            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

            CONSTRAINT fk_desc_det_pagos
                FOREIGN KEY ({self.COL_ID_PAGO}) REFERENCES pagos(id_pago_nomina)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        self.db.run_query(sql)

    # ------------------- CRUD borrador -------------------

    def upsert_detalles(self, id_pago_nomina: int, detalles: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inserta/actualiza borrador con UPSERT.
        Los campos numéricos pueden ser NULL; el front decide defaults visuales.
        """
        try:
            q = f"""
            INSERT INTO {self.TABLE} (
                {self.COL_ID_PAGO},
                {self.COL_APLICADO_IMSS}, {self.COL_MONTO_IMSS},
                {self.COL_APLICADO_TRANSPORTE}, {self.COL_MONTO_TRANSPORTE},
                {self.COL_APLICADO_EXTRA}, {self.COL_DESCRIPCION_EXTRA}, {self.COL_MONTO_EXTRA}
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
                bool(detalles.get(self.COL_APLICADO_IMSS, False)),
                self._to_float_or_none(detalles.get(self.COL_MONTO_IMSS)),
                bool(detalles.get(self.COL_APLICADO_TRANSPORTE, False)),
                self._to_float_or_none(detalles.get(self.COL_MONTO_TRANSPORTE)),
                bool(detalles.get(self.COL_APLICADO_EXTRA, False)),
                (detalles.get(self.COL_DESCRIPCION_EXTRA) or None),
                self._to_float_or_none(detalles.get(self.COL_MONTO_EXTRA)),
            )
            self.db.run_query(q, vals)
            return {"status": "success"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al guardar borrador: {ex}"}

    def obtener_por_id_pago(self, id_pago_nomina: int) -> Dict[str, Any]:
        """
        Devuelve el borrador tal cual está en BD, o {} si no existe.
        Si no hay registro, el FRONT mostrará defaults visuales (p.ej. IMSS=50).
        """
        try:
            q = f"SELECT * FROM {self.TABLE} WHERE {self.COL_ID_PAGO}=%s"
            return self.db.get_data(q, (id_pago_nomina,), dictionary=True) or {}
        except Exception as ex:
            return {}

    def eliminar_por_id_pago(self, id_pago_nomina: int) -> Dict[str, Any]:
        try:
            q = f"DELETE FROM {self.TABLE} WHERE {self.COL_ID_PAGO}=%s"
            self.db.run_query(q, (id_pago_nomina,))
            return {"status": "success"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al borrar borrador: {ex}"}

    # ------------------- Utilidades de flujo -------------------

    def aplicar_a_descuentos_y_limpiar(self, id_pago_nomina: int, discount_model) -> Dict[str, Any]:
        """
        Toma el borrador, lo pasa al DiscountModel como registros FINALES
        y luego elimina el borrador (el modal quedará en modo lectura).
        """
        try:
            det = self.obtener_por_id_pago(id_pago_nomina)
            if not det:
                # Nada que aplicar: simplemente no hay borrador.
                return {"status": "success", "message": "Sin borrador de descuentos para aplicar."}

            numero_nomina = self._get_numero_nomina_de_pago(id_pago_nomina)
            if not numero_nomina:
                return {"status": "error", "message": "No se pudo resolver numero_nomina para este pago."}

            # Mapear borrador -> modelo final
            aplicar_imss = bool(det.get(self.COL_APLICADO_IMSS))
            monto_imss = self._to_float_or_zero(det.get(self.COL_MONTO_IMSS))

            aplicar_transporte = bool(det.get(self.COL_APLICADO_TRANSPORTE))
            monto_transporte = self._to_float_or_zero(det.get(self.COL_MONTO_TRANSPORTE))

            aplicar_extra = bool(det.get(self.COL_APLICADO_EXTRA))
            monto_extra = self._to_float_or_zero(det.get(self.COL_MONTO_EXTRA))
            desc_extra = (det.get(self.COL_DESCRIPCION_EXTRA) or "").strip()

            res = discount_model.guardar_descuentos_confirmados(
                id_pago=id_pago_nomina,
                numero_nomina=numero_nomina,
                aplicar_imss=aplicar_imss,
                monto_imss=monto_imss,
                aplicar_transporte=aplicar_transporte,
                monto_transporte=monto_transporte,
                aplicar_extra=aplicar_extra,
                monto_extra=monto_extra,
                descripcion_extra=desc_extra
            )
            if res.get("status") != "success":
                return res

            # Limpia borrador tras guardar definitivo
            self.eliminar_por_id_pago(id_pago_nomina)
            return {"status": "success", "message": "Descuentos aplicados y borrador eliminado."}
        except Exception as ex:
            return {"status": "error", "message": f"Error al aplicar borrador: {ex}"}

    # Resolver numero_nomina a partir del pago (para no exponer lógica al front)
    def _get_numero_nomina_de_pago(self, id_pago_nomina: int) -> Optional[int]:
        try:
            q = "SELECT numero_nomina FROM pagos WHERE id_pago_nomina=%s"
            r = self.db.get_data(q, (id_pago_nomina,), dictionary=True)
            return int(r["numero_nomina"]) if r and r.get("numero_nomina") is not None else None
        except Exception:
            return None

    @staticmethod
    def _to_float_or_none(v):
        try:
            if v is None or v == "":
                return None
            return float(v)
        except Exception:
            return None

    @staticmethod
    def _to_float_or_zero(v):
        try:
            if v is None or v == "":
                return 0.0
            return float(v)
        except Exception:
            return 0.0
