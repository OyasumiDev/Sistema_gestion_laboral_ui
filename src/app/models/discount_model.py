from datetime import date
from typing import Dict, Any, List, Optional

from app.core.enums.e_discount_model import E_DISCOUNT
from app.core.interfaces.database_mysql import DatabaseMysql


class DiscountModel:
    """
    Lógica de DESCUENTOS (persistidos). NO maneja 'comida'.
    - IMSS ahora tiene default interno = 50.
    - Transporte ahora tiene default interno = 100.
    - Este modelo guarda descuentos ya confirmados para un pago de nómina (id_pago_nomina).
    - El 'borrador' del modal se maneja en DescuentoDetallesModel.
    """

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
                print(f"✔️ La tabla {self.E.TABLE.value} ya existe.")
                return True

            print(f"⚠️ La tabla {self.E.TABLE.value} no existe. Creando...")
            self._create_table()
            print(f"✅ Tabla {self.E.TABLE.value} creada correctamente.")
            return True
        except Exception as e:
            print(f"❌ Error verificando/creando la tabla {self.E.TABLE.value}: {e}")
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

    # ---------------------------------------------------------------------
    # Inserción / upserts
    # ---------------------------------------------------------------------
    def agregar_descuento(
        self,
        numero_nomina: int,
        tipo: str,
        descripcion: Optional[str],
        monto: float,
        id_pago: Optional[int] = None
    ) -> Dict[str, Any]:
        try:
            if float(monto) < 0:
                return {"status": "error", "message": "El monto no puede ser negativo"}

            q = f"""
            INSERT INTO {self.E.TABLE.value} (
                {self.E.PRESTAMO_NUMERO_NOMINA.value}, {self.E.ID_PAGO.value}, {self.E.TIPO.value},
                {self.E.DESCRIPCION.value}, {self.E.MONTO_DESCUENTO.value}, {self.E.FECHA_APLICACION.value}
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(
                q,
                (numero_nomina, id_pago, tipo, (descripcion or None), float(monto), date.today())
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
        **kwargs
    ) -> Dict[str, Any]:
        """
        Inserta descuentos opcionales con defaults internos:
        - IMSS → 50 si no se especifica o es <=0.
        - Transporte → 100 si no se especifica o es <=0.
        """
        try:
            if aplicar_imss:
                monto_final = float(monto_imss) if float(monto_imss) > 0 else 50.0
                self.agregar_descuento(numero_nomina, "retenciones_imss", "Cuota IMSS", monto_final, id_pago)

            if aplicar_transporte:
                monto_final = float(monto_transporte) if float(monto_transporte) > 0 else 100.0
                self.agregar_descuento(numero_nomina, "transporte", "Pasaje diario", monto_final, id_pago)

            if aplicar_extra and (float(monto_extra) > 0) and descripcion_extra:
                self.agregar_descuento(numero_nomina, "descuento_extra", descripcion_extra.strip(), float(monto_extra), id_pago)

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
        descripcion_extra: str
    ) -> Dict[str, Any]:
        """
        Guarda definitivamente los descuentos de un pago:
        - IMSS → 50 si no se especifica o es <=0.
        - Transporte → 100 si no se especifica o es <=0.
        - Extra → solo si tiene monto >0 y descripción.
        """
        try:
            self.eliminar_por_id_pago(id_pago)

            if aplicar_imss:
                monto_final = float(monto_imss) if float(monto_imss) > 0 else 50.0
                self.agregar_descuento(numero_nomina, "retenciones_imss", "Cuota IMSS", monto_final, id_pago)

            if aplicar_transporte:
                monto_final = float(monto_transporte) if float(monto_transporte) > 0 else 100.0
                self.agregar_descuento(numero_nomina, "transporte", "Pasaje diario", monto_final, id_pago)

            if aplicar_extra and (float(monto_extra) > 0) and descripcion_extra:
                self.agregar_descuento(numero_nomina, "descuento_extra", descripcion_extra.strip(), float(monto_extra), id_pago)

            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ---------------------------------------------------------------------
    # Eliminación / Consulta / Resumen (igual que antes)
    # ---------------------------------------------------------------------
    def eliminar_por_id_pago(self, id_pago: int) -> Dict[str, Any]:
        try:
            q = f"DELETE FROM {self.E.TABLE.value} WHERE {self.E.ID_PAGO.value}=%s"
            self.db.run_query(q, (id_pago,))
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_descuentos_por_pago(self, id_pago: int) -> List[Dict[str, Any]]:
        try:
            q = f"""
            SELECT {self.E.TIPO.value}, {self.E.DESCRIPCION.value}, {self.E.MONTO_DESCUENTO.value}
            FROM {self.E.TABLE.value}
            WHERE {self.E.ID_PAGO.value}=%s
            """
            return self.db.get_data_list(q, (id_pago,), dictionary=True) or []
        except Exception as e:
            print(f"❌ Error al obtener descuentos del pago {id_pago}: {e}")
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
        except Exception as e:
            print(f"❌ Error al obtener total de descuentos del pago {id_pago}: {e}")
            return 0.0

    def resumen_por_pago(self, id_pago: int) -> Dict[str, Any]:
        try:
            ds = self.get_descuentos_por_pago(id_pago)
            total = sum(float(d[self.E.MONTO_DESCUENTO.value] or 0) for d in ds)
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
