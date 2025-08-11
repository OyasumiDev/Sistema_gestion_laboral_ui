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


    # --- NUEVO: info completa de columnas de 'pagos'
    def _pagos_columns_info(self) -> dict:
        """
        Devuelve un dict {col: {data_type, is_nullable, column_default}} para la tabla 'pagos'.
        """
        try:
            rows = self.db.get_data_list(
                """
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME='pagos'
                """,
                (self.db.database,),
                dictionary=True,
            ) or []
            info = {}
            for r in rows:
                info[r["COLUMN_NAME"]] = {
                    "data_type": (r["DATA_TYPE"] or "").lower(),
                    "is_nullable": (r["IS_NULLABLE"] or "").upper() == "YES",
                    "column_default": r["COLUMN_DEFAULT"],
                }
            return info
        except Exception as ex:
            print(f"❌ _pagos_columns_info error: {ex}")
            return {}


    def ensure_id_pago_nomina(self, numero_nomina: int, fecha: str, extra_values: dict | None = None) -> int | None:
        """
        Devuelve un id_pago_nomina válido. Si no existe para ese empleado (y fecha),
        crea un registro mínimo en 'pagos' rellenando TODAS las columnas NOT NULL
        sin default con valores sensatos. Puedes forzar valores con extra_values.
        """
        try:
            from datetime import datetime as _dt
            info = self._pagos_columns_info()
            cols = set(info.keys())
            extra_values = extra_values or {}

            # 1) Reutilizar uno pendiente del día (si existen esas columnas)
            where_parts = ["numero_nomina=%s"] if "numero_nomina" in cols else []
            params = [numero_nomina] if "numero_nomina" in cols else []

            # elegir columna de fecha disponible
            fecha_col = None
            for c in ("fecha_pago", "fecha", "fecha_nomina"):
                if c in cols:
                    fecha_col = c
                    break
            if fecha_col:
                where_parts.append(f"{fecha_col}=%s")
                params.append(fecha)

            if "estado" in cols:
                where_parts.append("estado='pendiente'")

            if where_parts:
                q_sel = f"SELECT id_pago_nomina FROM pagos WHERE {' AND '.join(where_parts)} ORDER BY id_pago_nomina DESC LIMIT 1"
                row = self.db.get_data(q_sel, tuple(params), dictionary=True)
                if row and row.get("id_pago_nomina"):
                    return int(row["id_pago_nomina"])

            # 2) Crear uno nuevo: preparar valores
            insert_vals: dict = {}

            # siempre que exista:
            if "numero_nomina" in cols:
                insert_vals["numero_nomina"] = numero_nomina

            if fecha_col:
                insert_vals[fecha_col] = fecha

            if "estado" in cols:
                insert_vals["estado"] = "pendiente"

            if "observaciones" in cols:
                insert_vals["observaciones"] = "Creado automáticamente para registrar pago de préstamo"

            # mes / año si existen:
            try:
                d = _dt.strptime(fecha, "%Y-%m-%d")
                if "mes" in cols and "mes" not in insert_vals:
                    insert_vals["mes"] = d.month
                if {"anio", "año", "year"} & cols:
                    if "anio" in cols and "anio" not in insert_vals:
                        insert_vals["anio"] = d.year
                    if "año" in cols and "año" not in insert_vals:
                        insert_vals["año"] = d.year
                    if "year" in cols and "year" not in insert_vals:
                        insert_vals["year"] = d.year
            except Exception:
                pass

            # Rellenar TODAS las NOT NULL sin default que falten
            for col, meta in info.items():
                if col in ("id_pago_nomina",):  # PK autoincrement
                    continue
                if col in insert_vals:
                    continue
                if col in extra_values:
                    insert_vals[col] = extra_values[col]
                    continue

                is_nullable = meta["is_nullable"]
                has_default = meta["column_default"] is not None
                if is_nullable or has_default:
                    continue  # no necesitamos setearlo

                dt = meta["data_type"]

                # Heurísticas por nombre
                if col == "estado":
                    insert_vals[col] = "pendiente"
                elif "obs" in col or "nota" in col:
                    insert_vals[col] = ""
                elif col in {"mes", "month"}:
                    try:
                        insert_vals[col] = d.month
                    except Exception:
                        insert_vals[col] = 0
                elif col in {"anio", "año", "year"}:
                    try:
                        insert_vals[col] = d.year
                    except Exception:
                        insert_vals[col] = 0
                # Fechas
                elif dt in {"date"}:
                    insert_vals[col] = fecha
                elif dt in {"datetime", "timestamp"}:
                    insert_vals[col] = f"{fecha} 00:00:00"
                # Numéricos → 0 (incluye DECIMAL, INT, BIGINT, DOUBLE, FLOAT)
                elif dt in {"decimal", "int", "bigint", "double", "float", "tinyint", "smallint", "mediumint"}:
                    insert_vals[col] = 0
                # Default texto vacío para VARCHAR/CHAR
                elif dt in {"varchar", "char", "text", "mediumtext", "longtext"}:
                    insert_vals[col] = ""
                else:
                    # fallback general
                    insert_vals[col] = 0

            # Mezclar overrides del caller
            for k, v in extra_values.items():
                insert_vals[k] = v

            # Armar INSERT
            if not insert_vals:
                # como mínimo necesitamos algo; si no hay columnas coincidentes, abortar
                print("⚠️ ensure_id_pago_nomina: no hay columnas compatibles para insertar.")
                return None

            cols_sql = ", ".join(insert_vals.keys())
            ph = ", ".join(["%s"] * len(insert_vals))
            q_ins = f"INSERT INTO pagos ({cols_sql}) VALUES ({ph})"
            self.db.run_query(q_ins, tuple(insert_vals.values()))

            # ID recién creado
            last = self.db.get_data("SELECT LAST_INSERT_ID() AS id", dictionary=True)
            if last and last.get("id"):
                return int(last["id"])

            # Fallback si la conexión no comparte sesión
            where_back = []
            params_back = []
            if "numero_nomina" in cols:
                where_back.append("numero_nomina=%s")
                params_back.append(numero_nomina)
            q_last = "SELECT id_pago_nomina FROM pagos"
            if where_back:
                q_last += " WHERE " + " AND ".join(where_back)
            q_last += " ORDER BY id_pago_nomina DESC LIMIT 1"
            row2 = self.db.get_data(q_last, tuple(params_back), dictionary=True)
            return int(row2["id_pago_nomina"]) if row2 and row2.get("id_pago_nomina") else None

        except Exception as ex:
            print(f"❌ ensure_id_pago_nomina error: {ex}")
            return None
