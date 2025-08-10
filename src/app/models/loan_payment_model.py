from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from app.core.interfaces.database_mysql import DatabaseMysql
from app.core.enums.e_pagos_prestamos import E_PAGOS_PRESTAMO as E
from app.core.enums.e_prestamos_model import E_PRESTAMOS as P


class LoanPaymentModel:
    """
    Modelo de pagos de préstamo.
    - add_payment: inserta un pago directo.
    - add_from_detalle: toma un detalle guardado (staging) y crea el pago real.
    - preview_calculo: calcula interés/nuevo saldo sin escribir en BD.
    """

    INTERESES_PERMITIDOS = (5, 10, 15)

    def __init__(self):
        self.db = DatabaseMysql()
        self.E = E
        self.P = P
        self.table = self.E.TABLE_PAGOS_PRESTAMOS.value
        self._exists_table = self.check_table()

    # ------------------------------------------------------------
    # Infra: verificación / creación de tabla
    # ------------------------------------------------------------
    def check_table(self) -> bool:
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(
                query, (self.db.database, self.E.TABLE_PAGOS_PRESTAMOS.value), dictionary=True
            )
            if result.get("c", 0) > 0:
                print(f"✔️ La tabla {self.E.TABLE_PAGOS_PRESTAMOS.value} ya existe.")
                return True

            # Verifica dependencias
            def tabla_existe(nombre_tabla):
                res = self.db.get_data(query, (self.db.database, nombre_tabla), dictionary=True)
                return res.get("c", 0) > 0

            if not tabla_existe(self.P.TABLE_PRESTAMOS.value):
                print(f"❌ Falta la tabla {self.P.TABLE_PRESTAMOS.value}")
                return False
            if not tabla_existe("pagos"):
                print("❌ Falta la tabla 'pagos'")
                return False

            # Crear tabla pagos_prestamo
            print(f"⚠️ La tabla {self.E.TABLE_PAGOS_PRESTAMOS.value} no existe. Creando...")
            create_query = f"""
            CREATE TABLE {self.E.TABLE_PAGOS_PRESTAMOS.value} (
                {self.E.ID_PAGO_PRESTAMO.value} INT AUTO_INCREMENT PRIMARY KEY,
                {self.E.ID_PRESTAMO.value} INT NOT NULL,
                {self.E.ID_PAGO_NOMINA.value} INT NOT NULL,
                {self.E.PAGO_MONTO_PAGADO.value} DECIMAL(10,2) NOT NULL,
                {self.E.PAGO_FECHA_PAGO.value} DATE NOT NULL,
                {self.E.PAGO_FECHA_REAL.value} DATE,
                {self.E.PAGO_APLICADO.value} BOOLEAN NOT NULL DEFAULT 0,
                {self.E.PAGO_INTERES_PORCENTAJE.value} INT NOT NULL,
                {self.E.PAGO_INTERES_APLICADO.value} DECIMAL(10,2) NOT NULL,
                {self.E.PAGO_DIAS_RETRASO.value} INT DEFAULT 0,
                {self.E.PAGO_SALDO_RESTANTE.value} DECIMAL(10,2),
                {self.E.PAGO_OBSERVACIONES.value} TEXT,
                FOREIGN KEY ({self.E.ID_PRESTAMO.value})
                    REFERENCES {self.P.TABLE_PRESTAMOS.value}({self.P.PRESTAMO_ID.value})
                    ON DELETE CASCADE,
                FOREIGN KEY ({self.E.ID_PAGO_NOMINA.value})
                    REFERENCES pagos(id_pago_nomina)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            self.db.run_query(create_query)
            print(f"✅ Tabla {self.E.TABLE_PAGOS_PRESTAMOS.value} creada correctamente.")
            return True

        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla: {ex}")
            return False

    # ------------------------------------------------------------
    # Utilidades de cálculo
    # ------------------------------------------------------------
    def get_saldo_y_monto_prestamo(self, id_prestamo: int) -> Dict[str, Any]:
        try:
            query = f"""
                SELECT 
                    {self.P.PRESTAMO_MONTO.value} AS monto_prestamo,
                    {self.P.PRESTAMO_SALDO.value} AS saldo_prestamo
                FROM {self.P.TABLE_PRESTAMOS.value}
                WHERE {self.P.PRESTAMO_ID.value} = %s
            """
            result = self.db.get_data(query, (id_prestamo,), dictionary=True)
            return result if result else {}
        except Exception as ex:
            print(f"❌ Error al obtener monto y saldo del préstamo: {ex}")
            return {}

    def preview_calculo(
        self,
        id_prestamo: int,
        monto_pagado: float,
        interes_porcentaje: int,
        fecha_pago: str,         # "YYYY-MM-DD"
        fecha_generacion: str,   # "YYYY-MM-DD"
        fecha_real_pago: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calcula interés, saldo con interés, normaliza monto si excede y devuelve el nuevo saldo,
        sin escribir en BD.
        """
        try:
            s = self.get_saldo_y_monto_prestamo(id_prestamo) or {}
            saldo_actual = float(s.get("saldo_prestamo") or 0.0)

            if not (0 <= int(interes_porcentaje) <= 100):
                return {"status": "error", "message": "El interés debe estar entre 0 y 100%."}

            interes_aplicado = round(saldo_actual * (int(interes_porcentaje) / 100.0), 2)
            saldo_con_interes = round(saldo_actual + interes_aplicado, 2)

            if monto_pagado > saldo_con_interes:
                monto_pagado = saldo_con_interes

            nuevo_saldo = round(saldo_con_interes - float(monto_pagado), 2)

            f_gen = datetime.strptime(fecha_generacion, "%Y-%m-%d")
            f_pago = datetime.strptime((fecha_real_pago or fecha_pago), "%Y-%m-%d")
            dias_retraso = max((f_pago - f_gen).days, 0)

            return {
                "status": "success",
                "interes_aplicado": interes_aplicado,
                "saldo_con_interes": saldo_con_interes,
                "monto_pagado_normalizado": float(monto_pagado),
                "nuevo_saldo": nuevo_saldo,
                "dias_retraso": dias_retraso,
            }
        except Exception as ex:
            return {"status": "error", "message": f"Error en preview: {ex}"}

    # ------------------------------------------------------------
    # Inserción de pagos (directo o desde detalle)
    # ------------------------------------------------------------
    def add_payment(
        self,
        id_prestamo: int,
        id_pago_nomina: int,
        monto_pagado: float,
        fecha_pago: str,
        fecha_generacion: str,
        interes_porcentaje: int,
        aplicado: bool = False,
        fecha_real_pago: Optional[str] = None,
        observaciones: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            # Evita duplicado pendiente
            if self.existe_pago_pendiente_para_pago_nomina(id_pago_nomina, id_prestamo):
                return {"status": "error", "message": "Ya existe un pago pendiente para este préstamo en esta nómina."}

            # Saldo actual
            result = self.db.get_data(
                f"""
                SELECT {self.P.PRESTAMO_SALDO.value}
                FROM {self.P.TABLE_PRESTAMOS.value}
                WHERE {self.P.PRESTAMO_ID.value} = %s
                """,
                (id_prestamo,),
                dictionary=True,
            )
            if not result:
                return {"status": "error", "message": "Préstamo no encontrado."}

            saldo_actual = float(result.get(self.P.PRESTAMO_SALDO.value, 0.0))

            if not (0 <= int(interes_porcentaje) <= 100):
                return {"status": "error", "message": "El interés debe ser un porcentaje entre 0 y 100."}

            interes_aplicado = round(saldo_actual * (int(interes_porcentaje) / 100.0), 2)
            saldo_con_interes = round(saldo_actual + interes_aplicado, 2)

            # Normaliza monto si excede
            if float(monto_pagado) > saldo_con_interes:
                monto_pagado = saldo_con_interes

            nuevo_saldo = round(saldo_con_interes - float(monto_pagado), 2)

            f_gen = datetime.strptime(fecha_generacion, "%Y-%m-%d")
            f_pago = datetime.strptime((fecha_real_pago or fecha_pago), "%Y-%m-%d")
            dias_retraso = max((f_pago - f_gen).days, 0)

            # Insert
            insert_query = f"""
                INSERT INTO {self.E.TABLE_PAGOS_PRESTAMOS.value} (
                    {self.E.ID_PRESTAMO.value},
                    {self.E.ID_PAGO_NOMINA.value},
                    {self.E.PAGO_MONTO_PAGADO.value},
                    {self.E.PAGO_FECHA_PAGO.value},
                    {self.E.PAGO_FECHA_REAL.value},
                    {self.E.PAGO_APLICADO.value},
                    {self.E.PAGO_INTERES_PORCENTAJE.value},
                    {self.E.PAGO_INTERES_APLICADO.value},
                    {self.E.PAGO_DIAS_RETRASO.value},
                    {self.E.PAGO_SALDO_RESTANTE.value},
                    {self.E.PAGO_OBSERVACIONES.value}
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(
                insert_query,
                (
                    id_prestamo,
                    id_pago_nomina,
                    float(monto_pagado),
                    fecha_pago,
                    (fecha_real_pago or fecha_pago),
                    bool(aplicado),
                    int(interes_porcentaje),
                    float(interes_aplicado),
                    int(dias_retraso),
                    float(nuevo_saldo),
                    observaciones,
                ),
            )

            # Actualiza saldo préstamo
            self.db.run_query(
                f"""
                UPDATE {self.P.TABLE_PRESTAMOS.value}
                SET {self.P.PRESTAMO_SALDO.value} = %s
                WHERE {self.P.PRESTAMO_ID.value} = %s
                """,
                (float(nuevo_saldo), id_prestamo),
            )

            # Marca como terminado si corresponde
            if nuevo_saldo <= 0:
                self.db.run_query(
                    f"""
                    UPDATE {self.P.TABLE_PRESTAMOS.value}
                    SET {self.P.PRESTAMO_ESTADO.value} = 'terminado'
                    WHERE {self.P.PRESTAMO_ID.value} = %s
                    """,
                    (id_prestamo,),
                )

            return {
                "status": "success",
                "message": f"Pago registrado. Interés: ${interes_aplicado}, nuevo saldo: ${nuevo_saldo}, retraso: {dias_retraso} día(s).",
            }

        except Exception as ex:
            return {"status": "error", "message": f"Error al registrar pago: {ex}"}

    def add_from_detalle(
        self,
        id_pago_nomina: int,
        id_prestamo: int,
        fecha_pago: str,          # "YYYY-MM-DD"
        fecha_generacion: str,    # "YYYY-MM-DD"
        aplicado: bool = False,
        fecha_real_pago: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Crea un pago real leyendo el detalle guardado (staging) en detalles_pagos_prestamo.
        Si se inserta con éxito, borra el detalle.
        """
        try:
            from app.models.detalles_pagos_prestamo_model import DetallesPagosPrestamoModel

            detalles = DetallesPagosPrestamoModel()
            det = detalles.get_detalle(id_pago_nomina, id_prestamo)
            if not det:
                return {"status": "error", "message": "No existe detalle guardado para este pago/préstamo."}

            monto = float(det.get("monto_guardado") or 0.0)
            interes = int(det.get("interes_guardado") or 0)
            observaciones = det.get("observaciones")

            res = self.add_payment(
                id_prestamo=id_prestamo,
                id_pago_nomina=id_pago_nomina,
                monto_pagado=monto,
                fecha_pago=fecha_pago,
                fecha_generacion=fecha_generacion,
                interes_porcentaje=interes,
                aplicado=aplicado,
                fecha_real_pago=fecha_real_pago,
                observaciones=observaciones,
            )
            if res.get("status") == "success":
                try:
                    detalles.delete_detalle(id_pago_nomina, id_prestamo)
                except Exception:
                    pass
            return res
        except Exception as ex:
            return {"status": "error", "message": f"Error al crear pago desde detalle: {ex}"}

    # ------------------------------------------------------------
    # Lectura / consulta
    # ------------------------------------------------------------
    def get_by_prestamo(self, id_prestamo: int) -> Dict[str, Any]:
        try:
            query = f"""
                SELECT *
                FROM {self.E.TABLE_PAGOS_PRESTAMOS.value}
                WHERE {self.E.ID_PRESTAMO.value} = %s
                ORDER BY {self.E.PAGO_FECHA_PAGO.value} ASC
            """
            result = self.db.get_data_list(query, (id_prestamo,), dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener pagos: {ex}"}

    # Alias por compatibilidad
    def get_by_id_prestamo(self, id_prestamo: int) -> Dict[str, Any]:
        return self.get_by_prestamo(id_prestamo)

    def get_next_id(self) -> int:
        try:
            query = f"""
                SELECT MAX({self.E.ID_PAGO_PRESTAMO.value}) AS max_id
                FROM {self.E.TABLE_PAGOS_PRESTAMOS.value}
            """
            result = self.db.get_data(query, dictionary=True)
            max_id = result.get("max_id", 0) if result else 0
            return int(max_id) + 1 if max_id else 1
        except Exception as ex:
            print(f"❌ Error al obtener el siguiente ID: {ex}")
            return 1

    def get_prestamo_activo_por_empleado(self, numero_nomina: int) -> Dict[str, Any]:
        try:
            query = f"""
                SELECT 
                    {self.P.PRESTAMO_ID.value} AS id_prestamo,
                    {self.P.PRESTAMO_SALDO.value} AS saldo,
                    {self.P.PRESTAMO_MONTO.value} AS monto_original,
                    {self.P.PRESTAMO_NUMERO_NOMINA.value} AS numero_nomina
                FROM {self.P.TABLE_PRESTAMOS.value}
                WHERE {self.P.PRESTAMO_NUMERO_NOMINA.value} = %s
                AND {self.P.PRESTAMO_ESTADO.value} = 'pagando'
                ORDER BY {self.P.PRESTAMO_ID.value} ASC
                LIMIT 1
            """
            result = self.db.get_data(query, (numero_nomina,), dictionary=True)
            return result if result else {}
        except Exception as e:
            print(f"❌ Error al buscar préstamo activo: {e}")
            return {}

    def get_total_prestamos_por_pago(self, id_pago_nomina: int) -> float:
        try:
            query = f"""
                SELECT IFNULL(SUM({self.E.PAGO_MONTO_PAGADO.value}), 0) AS total_prestamo
                FROM {self.E.TABLE_PAGOS_PRESTAMOS.value}
                WHERE {self.E.ID_PAGO_NOMINA.value} = %s AND {self.E.PAGO_APLICADO.value} = 1
            """
            result = self.db.get_data(query, (id_pago_nomina,), dictionary=True)
            return float(result.get("total_prestamo", 0.0)) if result else 0.0
        except Exception as ex:
            print(f"❌ Error en get_total_prestamos_por_pago: {ex}")
            return 0.0

    def get_total_pagado_por_pago(self, id_pago_nomina: int) -> float:
        try:
            query = f"""
                SELECT IFNULL(SUM({self.E.PAGO_MONTO_PAGADO.value}), 0) AS total
                FROM {self.E.TABLE_PAGOS_PRESTAMOS.value}
                WHERE {self.E.ID_PAGO_NOMINA.value} = %s AND {self.E.PAGO_APLICADO.value} = 1
            """
            result = self.db.get_data(query, (id_pago_nomina,), dictionary=True)
            return float(result.get("total", 0.0)) if result else 0.0
        except Exception as ex:
            print(f"❌ Error al obtener total pagado por pago: {ex}")
            return 0.0

    def get_total_pagado_por_prestamo(self, id_prestamo: int) -> float:
        try:
            query = f"""
                SELECT IFNULL(SUM({self.E.PAGO_MONTO_PAGADO.value}), 0) AS total
                FROM {self.E.TABLE_PAGOS_PRESTAMOS.value}
                WHERE {self.E.ID_PRESTAMO.value} = %s AND {self.E.PAGO_APLICADO.value} = 1
            """
            result = self.db.get_data(query, (id_prestamo,), dictionary=True)
            return float(result.get("total", 0.0)) if result else 0.0
        except Exception as ex:
            print(f"❌ Error al obtener total pagado por préstamo: {ex}")
            return 0.0

    def existe_pago_pendiente_para_pago_nomina(self, id_pago_nomina: int, id_prestamo: int) -> bool:
        try:
            query = f"""
                SELECT COUNT(*) AS cantidad
                FROM {self.E.TABLE_PAGOS_PRESTAMOS.value}
                WHERE {self.E.ID_PAGO_NOMINA.value} = %s
                AND {self.E.ID_PRESTAMO.value} = %s
                AND {self.E.PAGO_APLICADO.value} = 0
            """
            resultado = self.db.get_data(query, (id_pago_nomina, id_prestamo), dictionary=True)
            return resultado.get("cantidad", 0) > 0
        except Exception as ex:
            print(f"❌ Error al verificar existencia de pago pendiente: {ex}")
            return False

    # ------------------------------------------------------------
    # Update / Delete
    # ------------------------------------------------------------
    def update_by_id_pago(self, id_pago: int, campos: Dict[Any, Any]) -> Dict[str, Any]:
        """
        campos puede venir con claves Enum o strings. Ej:
        { E.PAGO_APLICADO: 1, E.PAGO_FECHA_REAL: '2024-09-01' }
        o
        { 'aplicado': 1, 'fecha_real_pago': '2024-09-01' }
        """
        try:
            if not campos:
                return {"status": "error", "message": "No se proporcionaron campos para actualizar."}

            def _col(k):
                return k.value if hasattr(k, "value") else str(k)

            cols = [_col(k) for k in campos.keys()]
            valores = list(campos.values())

            set_sql = ", ".join(f"{c} = %s" for c in cols)
            query = f"""
                UPDATE {self.E.TABLE_PAGOS_PRESTAMOS.value}
                SET {set_sql}
                WHERE {self.E.ID_PAGO_PRESTAMO.value} = %s
            """
            self.db.run_query(query, tuple(valores + [id_pago]))
            return {"status": "success", "message": "Pago actualizado correctamente."}
        except Exception as ex:
            return {"status": "error", "message": f"Error al actualizar el pago: {ex}"}

    def delete_by_id_pago(self, id_pago: int) -> Dict[str, Any]:
        try:
            query = f"""
                DELETE FROM {self.E.TABLE_PAGOS_PRESTAMOS.value}
                WHERE {self.E.ID_PAGO_PRESTAMO.value} = %s
            """
            self.db.run_query(query, (id_pago,))
            return {"status": "success", "message": f"Pago ID {id_pago} eliminado correctamente."}
        except Exception as ex:
            return {"status": "error", "message": f"Error al eliminar el pago: {ex}"}
