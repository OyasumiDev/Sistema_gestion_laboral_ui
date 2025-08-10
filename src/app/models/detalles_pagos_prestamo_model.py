from typing import Dict, Any, Optional
from app.core.interfaces.database_mysql import DatabaseMysql
from app.core.enums.e_detalles_pagos_prestamo_model import E_DETALLES_PAGOS_PRESTAMO as E


class DetallesPagosPrestamoModel:
    def __init__(self):
        self.db = DatabaseMysql()
        self.E = E
        self._exists_table = self.check_table()

    # ------------------------------------------------------------------
    # Infra
    # ------------------------------------------------------------------
    def check_table(self) -> bool:
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, self.E.TABLE.value), dictionary=True)
            if result.get("c", 0) == 0:
                print(f"⚠️ La tabla {self.E.TABLE.value} no existe. Creando...")
                create_query = f"""
                    CREATE TABLE {self.E.TABLE.value} (
                        {self.E.ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                        {self.E.ID_PAGO.value} INT NOT NULL,
                        {self.E.ID_PRESTAMO.value} INT NOT NULL,
                        {self.E.MONTO_GUARDADO.value} DECIMAL(10,2),
                        {self.E.INTERES_GUARDADO.value} INT,
                        {self.E.OBSERVACIONES.value} TEXT,
                        {self.E.FECHA.value} DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE KEY uk_pago_prestamo ({self.E.ID_PAGO.value}, {self.E.ID_PRESTAMO.value}),
                        FOREIGN KEY ({self.E.ID_PAGO.value}) REFERENCES pagos(id_pago_nomina) ON DELETE CASCADE,
                        FOREIGN KEY ({self.E.ID_PRESTAMO.value}) REFERENCES prestamos(id_prestamo) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {self.E.TABLE.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {self.E.TABLE.value} ya existe.")
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla: {ex}")
            return False

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def upsert_detalle(self, id_pago: int, id_prestamo: int, monto: float, interes: int, observaciones: str):
        try:
            query = f"""
                INSERT INTO {self.E.TABLE.value} (
                    {self.E.ID_PAGO.value},
                    {self.E.ID_PRESTAMO.value},
                    {self.E.MONTO_GUARDADO.value},
                    {self.E.INTERES_GUARDADO.value},
                    {self.E.OBSERVACIONES.value}
                ) VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    {self.E.MONTO_GUARDADO.value} = VALUES({self.E.MONTO_GUARDADO.value}),
                    {self.E.INTERES_GUARDADO.value} = VALUES({self.E.INTERES_GUARDADO.value}),
                    {self.E.OBSERVACIONES.value} = VALUES({self.E.OBSERVACIONES.value}),
                    {self.E.FECHA.value} = CURRENT_TIMESTAMP
            """
            self.db.run_query(query, (id_pago, id_prestamo, monto, interes, observaciones))
            return {"status": "success", "message": "Guardado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al guardar detalles: {ex}"}

    def get_detalle(self, id_pago: int, id_prestamo: int) -> dict:
        try:
            query = f"""
                SELECT * FROM {self.E.TABLE.value}
                WHERE {self.E.ID_PAGO.value} = %s AND {self.E.ID_PRESTAMO.value} = %s
            """
            return self.db.get_data(query, (id_pago, id_prestamo), dictionary=True)
        except Exception as ex:
            print(f"❌ Error al obtener detalle: {ex}")
            return {}

    def get_todos_por_pago(self, id_pago: int) -> list:
        try:
            query = f"""
                SELECT * FROM {self.E.TABLE.value}
                WHERE {self.E.ID_PAGO.value} = %s
            """
            return self.db.get_data_list(query, (id_pago,), dictionary=True)
        except Exception as ex:
            print(f"❌ Error al obtener detalles por pago: {ex}")
            return []

    def delete_detalle(self, id_pago: int, id_prestamo: int):
        try:
            query = f"""
                DELETE FROM {self.E.TABLE.value}
                WHERE {self.E.ID_PAGO.value} = %s AND {self.E.ID_PRESTAMO.value} = %s
            """
            self.db.run_query(query, (id_pago, id_prestamo))
            return {"status": "success", "message": "Detalle eliminado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al eliminar: {ex}"}

    def exists_detalle(self, id_pago: int, id_prestamo: int) -> bool:
        try:
            query = f"""
                SELECT COUNT(*) AS c
                FROM {self.E.TABLE.value}
                WHERE {self.E.ID_PAGO.value} = %s AND {self.E.ID_PRESTAMO.value} = %s
            """
            r = self.db.get_data(query, (id_pago, id_prestamo), dictionary=True)
            return (r.get("c") or 0) > 0
        except Exception as ex:
            print(f"❌ Error en exists_detalle: {ex}")
            return False

    # ------------------------------------------------------------------
    # Agregaciones
    # ------------------------------------------------------------------
    def calcular_total_pendiente_por_pago(self, id_pago: int) -> float:
        """
        Suma SOLO los montos guardados (el interés aquí es porcentaje, no dinero).
        """
        try:
            query = f"""
                SELECT COALESCE(SUM({self.E.MONTO_GUARDADO.value}), 0) AS total
                FROM {self.E.TABLE.value}
                WHERE {self.E.ID_PAGO.value} = %s
            """
            resultado = self.db.get_data(query, (id_pago,), dictionary=True)
            total = resultado.get("total", 0)
            return float(total)
        except Exception as ex:
            print(f"❌ Error al calcular total pendiente: {ex}")
            return 0.0

    # ------------------------------------------------------------------
    # Helpers de recálculo en tiempo real (para el modal)
    # ------------------------------------------------------------------
    def preview_from_inputs(
        self,
        id_prestamo: int,
        monto: float,
        interes: int,
        fecha_pago: str,          # "YYYY-MM-DD"
        fecha_generacion: str,    # "YYYY-MM-DD"
        fecha_real_pago: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Devuelve un preview universal (sin escribir en BD) usando LoanPaymentModel.preview_calculo.
        """
        try:
            # Import local para evitar dependencias circulares al cargar módulos
            from app.models.loan_payment_model import LoanPaymentModel
            lp = LoanPaymentModel()
            return lp.preview_calculo(
                id_prestamo=id_prestamo,
                monto_pagado=float(monto),
                interes_porcentaje=int(interes),
                fecha_pago=fecha_pago,
                fecha_generacion=fecha_generacion,
                fecha_real_pago=fecha_real_pago,
            )
        except Exception as ex:
            return {"status": "error", "message": f"Error en preview_from_inputs: {ex}"}

    def preview_desde_guardado(
        self,
        id_pago: int,
        id_prestamo: int,
        fecha_pago: str,          # "YYYY-MM-DD"
        fecha_generacion: str,    # "YYYY-MM-DD"
        fecha_real_pago: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Toma el detalle guardado (monto, interés) y retorna el preview,
        útil para reabrir el modal y recalcular.
        """
        try:
            det = self.get_detalle(id_pago, id_prestamo)
            if not det:
                return {"status": "error", "message": "No hay detalle guardado para recalcular."}

            monto = float(det.get(self.E.MONTO_GUARDADO.value) or 0.0)
            interes = int(det.get(self.E.INTERES_GUARDADO.value) or 0)

            return self.preview_from_inputs(
                id_prestamo=id_prestamo,
                monto=monto,
                interes=interes,
                fecha_pago=fecha_pago,
                fecha_generacion=fecha_generacion,
                fecha_real_pago=fecha_real_pago,
            )
        except Exception as ex:
            return {"status": "error", "message": f"Error en preview_desde_guardado: {ex}"}
