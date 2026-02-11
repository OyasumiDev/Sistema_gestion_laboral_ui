# app/models/payment_model.py
from __future__ import annotations

from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple

from app.core.enums.e_payment_model import E_PAYMENT
from app.core.enums.e_discount_model import E_DISCOUNT
from app.core.enums.e_prestamos_model import E_PRESTAMOS
from app.core.enums.e_pagos_prestamos import E_PAGOS_PRESTAMO
from app.core.enums.e_detalles_pagos_prestamo_model import E_DETALLES_PAGOS_PRESTAMO as E_DET
from app.core.interfaces.database_mysql import DatabaseMysql

from app.models.employes_model import EmployesModel
from app.models.discount_model import DiscountModel
from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.descuento_detalles_model import DescuentoDetallesModel


class PaymentModel:
    """
    Modelo de Pagos (Nómina) – versión robusta y alineada al flujo actual del sistema.

    Conceptos base
    --------------
    1) Pagos de nómina (tabla `pagos`)
       - Cada pago pertenece a un empleado (numero_nomina).
       - Puede ser "auto" (generado desde asistencias) o "manual" (sin fecha_inicio/fecha_fin).
       - Estados:
         - 'pendiente': editable (depósito/efectivo/montos según reglas).
         - 'pagado': INMUTABLE por defecto (solo lectura). Ajustes excepcionales vía flags/force.
         - 'cancelado': reservado.

    2) Grupos
       - Auto: grupo_pago = GP-YYYY-MM-DD_AL_YYYY-MM-DD, con fecha_inicio/fecha_fin.
       - Manual por FECHA (UI): tabla `grupos_pagos` permite mostrar fechas "vacías" aun sin pagos.

    3) Borradores / confirmación
       - Descuentos: borrador (descuento_detalles) se prellena y luego se aplica a `descuentos`.
       - Préstamos: detalles_pagos_prestamo se aplican a `pagos_prestamo` al confirmar.
       - Confirmar: fija estado='pagado', recalcula totales, respeta depósito/efectivo existentes.

    Reglas críticas
    ---------------
    A) Pagos 'pagado' no deben modificarse por sincronizaciones automáticas.
       - Por defecto: refresh/restore/sync NO tocan pagados.
       - Excepción controlada: allow_paid_updates / overwrite_paid => ajusta SOLO horas y audita.

    B) update_pago:
       - Si solo llega depósito (o solo efectivo), NO fuerza el complemento.
       - Recalcula saldo = total - (dep + efec) y permite saldo negativo (adelanto).
       - Si el pago ya está 'pagado', bloquea cambios salvo force=True.

    Compatibilidad
    --------------
    - get_all() sigue existiendo como alias a get_all_pagos().
    """

    def __init__(self):
        self.db = DatabaseMysql()

        # Enums
        self.E = E_PAYMENT
        self.D = E_DISCOUNT
        self.P = E_PRESTAMOS
        self.LP = E_PAGOS_PRESTAMO

        # Modelos dependientes (perezosos / seguros)
        self.employee_model = None
        self.discount_model = None
        self.loan_model = None
        self.loan_payment_model = None
        self.detalles_desc_model = None
        self._assistance_model = None  # lazy import para evitar ciclos

        # Infra
        self._exists_table = self.check_table()
        self._ensure_grupos_table()
        self._ensure_auditoria_table()

        # Dependencias
        self.employee_model = EmployesModel()
        self.discount_model = DiscountModel()
        self.loan_model = LoanModel()
        self.loan_payment_model = LoanPaymentModel()
        try:
            self.detalles_desc_model = DescuentoDetallesModel()
        except Exception:
            self.detalles_desc_model = None

    # ---------------------------------------------------------------------
    # Infra / Esquema
    # ---------------------------------------------------------------------
    def check_table(self) -> bool:
        """
        Garantiza la tabla `pagos` con columnas/índices necesarios.
        Si existe, ejecuta migraciones tolerantes.
        """
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, self.E.TABLE.value), dictionary=True)

            if (result or {}).get("c", 0) == 0:
                print(f"⚠️ La tabla {self.E.TABLE.value} no existe. Creando...")
                create_query = f"""
                CREATE TABLE IF NOT EXISTS {self.E.TABLE.value} (
                    {self.E.ID_PAGO_NOMINA.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {self.E.NUMERO_NOMINA.value} SMALLINT UNSIGNED NOT NULL,

                    {self.E.GRUPO_PAGO.value} VARCHAR(100) DEFAULT NULL,
                    {self.E.FECHA_INICIO.value} DATE DEFAULT NULL,
                    {self.E.FECHA_FIN.value} DATE DEFAULT NULL,
                    {self.E.ESTADO_GRUPO.value} ENUM('abierto','cerrado') DEFAULT 'abierto',

                    {self.E.FECHA_PAGO.value} DATE NOT NULL,
                    {self.E.TOTAL_HORAS_TRABAJADAS.value} DECIMAL(8,4) DEFAULT 0,
                    {self.E.MONTO_BASE.value} DECIMAL(10,2) NOT NULL DEFAULT 0,
                    {self.E.MONTO_TOTAL.value} DECIMAL(10,2) NOT NULL DEFAULT 0,
                    {self.D.MONTO_DESCUENTO.value} DECIMAL(10,2) DEFAULT 0,
                    {self.P.PRESTAMO_MONTO.value} DECIMAL(10,2) DEFAULT 0,
                    {self.E.SALDO.value} DECIMAL(10,2) DEFAULT 0,

                    {self.E.PAGO_DEPOSITO.value} DECIMAL(10,2) NOT NULL DEFAULT 0,
                    {self.E.PAGO_EFECTIVO.value} DECIMAL(10,2) NOT NULL DEFAULT 0,

                    {self.E.ESTADO.value} ENUM('pendiente','pagado','cancelado') DEFAULT 'pendiente',

                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                    FOREIGN KEY ({self.E.NUMERO_NOMINA.value})
                        REFERENCES empleados(numero_nomina)
                        ON DELETE CASCADE,

                    INDEX idx_pagos_grupo ({self.E.GRUPO_PAGO.value}),
                    INDEX idx_pagos_fecha ({self.E.FECHA_PAGO.value}),
                    INDEX idx_pagos_estado ({self.E.ESTADO.value})
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {self.E.TABLE.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {self.E.TABLE.value} ya existe. Verificación completa.")
                self._ensure_schema_migrations()

            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {self.E.TABLE.value}: {ex}")
            return False

    def _ensure_schema_migrations(self) -> None:
        """Migra esquemas heredados de la tabla `pagos` de forma tolerante."""
        try:
            cols = self._get_columns_meta(self.E.TABLE.value)
            cols = self._maybe_rename_legacy_pk(cols)
            self._ensure_additional_columns(cols)
        except Exception as ex:
            print(f"⚠️ No se pudo actualizar el esquema de '{self.E.TABLE.value}': {ex}")

    def _get_columns_meta(self, table_name: str) -> Dict[str, Dict[str, Any]]:
        q = """
            SELECT column_name, data_type, column_type, is_nullable, column_default, extra
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
        """
        rows = self.db.get_data_list(q, (self.db.database, table_name), dictionary=True) or []
        normalized: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            name = row.get("COLUMN_NAME") or row.get("column_name")
            if not name:
                continue
            norm = {str(k).lower(): v for k, v in row.items()}
            normalized[str(name).lower()] = norm
        return normalized

    def _maybe_rename_legacy_pk(self, columns: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Renombra id_pago -> id_pago_nomina si detecta esquema antiguo."""
        pk = self.E.ID_PAGO_NOMINA.value.lower()
        if pk in columns:
            return columns

        legacy = "id_pago"
        if legacy not in columns:
            return columns

        dropped = self._drop_foreign_keys_referencing(self.E.TABLE.value, legacy)
        alter = f"""
            ALTER TABLE {self.E.TABLE.value}
            CHANGE COLUMN {legacy} {pk} INT NOT NULL AUTO_INCREMENT
        """
        self.db.run_query(alter)
        print("✅ Columna 'id_pago' renombrada a 'id_pago_nomina'.")
        columns = self._get_columns_meta(self.E.TABLE.value)

        if dropped:
            print("ℹ️ Se eliminaron temporalmente llaves foráneas antiguas. "
                  "Los modelos dependientes las recrearán automáticamente si aplica.")
        return columns

    def _drop_foreign_keys_referencing(self, referenced_table: str, referenced_column: str) -> List[Tuple[str, str]]:
        q = """
            SELECT TABLE_NAME, CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE REFERENCED_TABLE_SCHEMA = %s
              AND REFERENCED_TABLE_NAME = %s
              AND REFERENCED_COLUMN_NAME = %s
        """
        rows = self.db.get_data_list(q, (self.db.database, referenced_table, referenced_column), dictionary=True) or []
        dropped = []
        for row in rows:
            table = row.get("TABLE_NAME")
            constraint = row.get("CONSTRAINT_NAME")
            if not table or not constraint:
                continue
            try:
                self.db.run_query(f"ALTER TABLE {table} DROP FOREIGN KEY {constraint}")
                dropped.append((table, constraint))
                print(f"⚠️ FK '{constraint}' eliminada en '{table}' (referencia a {referenced_table}.{referenced_column}).")
            except Exception as ex:
                print(f"⚠️ No se pudo eliminar FK {constraint} en {table}: {ex}")
        return dropped

    def _ensure_additional_columns(self, columns: Dict[str, Dict[str, Any]]) -> None:
        """Asegura columnas nuevas para agrupación por corridas."""
        add_specs = [
            (self.E.GRUPO_PAGO.value, "VARCHAR(100) DEFAULT NULL", self.E.NUMERO_NOMINA.value),
            (self.E.FECHA_INICIO.value, "DATE DEFAULT NULL", self.E.GRUPO_PAGO.value),
            (self.E.FECHA_FIN.value, "DATE DEFAULT NULL", self.E.FECHA_INICIO.value),
            (self.E.ESTADO_GRUPO.value, "ENUM('abierto','cerrado') NOT NULL DEFAULT 'abierto'", self.E.FECHA_FIN.value),
        ]
        for name, definition, after in add_specs:
            key = name.lower()
            if key in columns:
                continue
            sql = f"ALTER TABLE {self.E.TABLE.value} ADD COLUMN {name} {definition}"
            if after:
                sql += f" AFTER {after}"
            self.db.run_query(sql)
            columns[key] = {"column_name": name}
            print(f"✅ Columna '{name}' añadida en {self.E.TABLE.value}.")

        # Ajuste tolerante del tipo de horas
        horas_col = self.E.TOTAL_HORAS_TRABAJADAS.value.lower()
        meta = columns.get(horas_col)
        if meta:
            col_type = str(meta.get("column_type") or meta.get("COLUMN_TYPE") or "").lower()
            if col_type != "decimal(8,4)":
                try:
                    sql = f"""
                        ALTER TABLE {self.E.TABLE.value}
                        MODIFY COLUMN {self.E.TOTAL_HORAS_TRABAJADAS.value} DECIMAL(8,4) NOT NULL DEFAULT 0
                    """
                    self.db.run_query(sql)
                    print(f"✅ Columna '{self.E.TOTAL_HORAS_TRABAJADAS.value}' ajustada a DECIMAL(8,4).")
                except Exception as ex:
                    print(f"⚠️ No se pudo ajustar tipo de '{self.E.TOTAL_HORAS_TRABAJADAS.value}': {ex}")

    # ---------------------------------------------------------------------
    # Stored Procedure horas
    # ---------------------------------------------------------------------
    def crear_sp_horas_trabajadas_para_pagos(self):
        """
        Crea/recrea SP 'horas_trabajadas_para_pagos' para sumar horas desde asistencias
        adaptándose a si asistencias.tiempo_trabajo es TIME o DECIMAL.
        """
        try:
            check_query = """
                SELECT COUNT(*) AS c
                FROM information_schema.routines
                WHERE routine_schema = %s
                AND routine_name = 'horas_trabajadas_para_pagos'
                AND routine_type = 'PROCEDURE'
            """
            result = self.db.get_data(check_query, (self.db.database,), dictionary=True)

            sp_sql = """
            CREATE PROCEDURE horas_trabajadas_para_pagos (
                IN p_numero_nomina INT,
                IN p_fecha_inicio DATE,
                IN p_fecha_fin DATE
            )
            BEGIN
                DECLARE v_dtype VARCHAR(32);

                SELECT DATA_TYPE INTO v_dtype
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                AND table_name = 'asistencias'
                AND column_name = 'tiempo_trabajo'
                LIMIT 1;

                IF p_numero_nomina IS NOT NULL THEN
                    IF EXISTS (SELECT 1 FROM empleados WHERE numero_nomina = p_numero_nomina) THEN
                        IF v_dtype = 'time' THEN
                            SELECT
                                a.numero_nomina,
                                e.nombre_completo,
                                (SUM(TIME_TO_SEC(a.tiempo_trabajo)) / 3600) AS total_horas_trabajadas
                            FROM asistencias a
                            JOIN empleados e ON a.numero_nomina = e.numero_nomina
                            WHERE a.numero_nomina = p_numero_nomina
                            AND a.fecha BETWEEN p_fecha_inicio AND p_fecha_fin
                            AND a.estado = 'completo'
                            GROUP BY a.numero_nomina, e.nombre_completo;
                        ELSE
                            SELECT
                                a.numero_nomina,
                                e.nombre_completo,
                                SUM(a.tiempo_trabajo) AS total_horas_trabajadas
                            FROM asistencias a
                            JOIN empleados e ON a.numero_nomina = e.numero_nomina
                            WHERE a.numero_nomina = p_numero_nomina
                            AND a.fecha BETWEEN p_fecha_inicio AND p_fecha_fin
                            AND a.estado = 'completo'
                            GROUP BY a.numero_nomina, e.nombre_completo;
                        END IF;
                    ELSE
                        SELECT 'Empleado no encontrado' AS mensaje;
                    END IF;
                ELSE
                    IF v_dtype = 'time' THEN
                        SELECT
                            a.numero_nomina,
                            e.nombre_completo,
                            (SUM(TIME_TO_SEC(a.tiempo_trabajo)) / 3600) AS total_horas_trabajadas
                        FROM asistencias a
                        JOIN empleados e ON a.numero_nomina = e.numero_nomina
                        WHERE a.fecha BETWEEN p_fecha_inicio AND p_fecha_fin
                        AND a.estado = 'completo'
                        GROUP BY a.numero_nomina, e.nombre_completo;
                    ELSE
                        SELECT
                            a.numero_nomina,
                            e.nombre_completo,
                            SUM(a.tiempo_trabajo) AS total_horas_trabajadas
                        FROM asistencias a
                        JOIN empleados e ON a.numero_nomina = e.numero_nomina
                        WHERE a.fecha BETWEEN p_fecha_inicio AND p_fecha_fin
                        AND a.estado = 'completo'
                        GROUP BY a.numero_nomina, e.nombre_completo;
                    END IF;
                END IF;
            END
            """

            if (result or {}).get("c", 0) == 0:
                print("⚠️ SP 'horas_trabajadas_para_pagos' no existe. Creando...")
            else:
                print("🔁 SP 'horas_trabajadas_para_pagos' existe. Re-creando para consistencia.")

            cursor = self.db.connection.cursor()
            cursor.execute("DROP PROCEDURE IF EXISTS horas_trabajadas_para_pagos")
            cursor.execute(sp_sql)
            self.db.connection.commit()
            cursor.close()
            print("✅ SP 'horas_trabajadas_para_pagos' creado/recreado correctamente.")
        except Exception as ex:
            print(f"❌ Error al crear SP 'horas_trabajadas_para_pagos': {ex}")

    def get_total_horas_trabajadas(
        self, fecha_inicio: str, fecha_fin: str, numero_nomina: Optional[int] = None
    ) -> Dict[str, Any]:
        """Obtiene horas trabajadas (sin redondeo extra) vía SP."""
        try:
            self.crear_sp_horas_trabajadas_para_pagos()

            cursor = self.db.connection.cursor()
            cursor.callproc("horas_trabajadas_para_pagos", (numero_nomina, fecha_inicio, fecha_fin))

            data = []
            for result in cursor.stored_results():
                rows = result.fetchall()
                cols = [d[0] for d in result.description]
                for r in rows:
                    row = dict(zip(cols, r))
                    if "total_horas_trabajadas" in row:
                        try:
                            row["total_horas_trabajadas"] = float(row["total_horas_trabajadas"] or 0)
                        except Exception:
                            row["total_horas_trabajadas"] = 0.0
                    data.append(row)

            cursor.close()
            return {"status": "success", "data": data}
        except Exception as ex:
            print(f"❌ Error en get_total_horas_trabajadas: {ex}")
            return {"status": "error", "message": "No fue posible obtener horas."}

    # ---------------------------------------------------------------------
    # Utilidades internas (sueldo, fechas, grupos)
    # ---------------------------------------------------------------------
    def _sueldo_hora(self, numero_nomina: int) -> float:
        try:
            e = self.employee_model.get_by_numero_nomina(numero_nomina) or {}
            sh = float(e.get("sueldo_por_hora", 0) or 0)
            if sh <= 0:
                sd = float(e.get("sueldo_diario", 0) or 0)
                if sd > 0:
                    sh = round(sd / 8.0, 2)
            return max(0.0, sh)
        except Exception:
            return 0.0

    @staticmethod
    def _build_grupo_token(fi: str, ff: str) -> str:
        return f"GP-{fi}_AL_{ff}"

    @staticmethod
    def _today_str() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def _normalize_date(value: Any) -> str:
        """Normaliza a YYYY-MM-DD tolerando DD/MM/YYYY."""
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
        return text

    @staticmethod
    def _build_scope(periodo_ini: str, periodo_fin: str, numero_nomina: Optional[int]) -> Dict[str, Any]:
        return {"scope": {"periodo_ini": periodo_ini, "periodo_fin": periodo_fin, "id_empleado": numero_nomina}}

    @staticmethod
    def _is_auto_pago(row: Dict[str, Any]) -> bool:
        return bool(row.get("fecha_inicio") and row.get("fecha_fin"))

    def _get_assistance_model(self):
        """Lazy import para evitar import circular."""
        if self._assistance_model is None:
            from app.models.assistance_model import AssistanceModel
            self._assistance_model = AssistanceModel()
        return self._assistance_model

    # ---------------------------------------------------------------------
    # Borrador descuentos (prefill)
    # ---------------------------------------------------------------------
    def _get_ultimo_pago_confirmado(self, numero_nomina: int) -> Optional[Dict[str, Any]]:
        try:
            q = f"""
                SELECT {self.E.ID_PAGO_NOMINA.value} AS id_pago, {self.E.FECHA_PAGO.value} AS fecha
                FROM {self.E.TABLE.value}
                WHERE {self.E.NUMERO_NOMINA.value}=%s AND {self.E.ESTADO.value}='pagado'
                ORDER BY {self.E.FECHA_PAGO.value} DESC, {self.E.ID_PAGO_NOMINA.value} DESC
                LIMIT 1
            """
            r = self.db.get_data(q, (numero_nomina,), dictionary=True)
            return r or None
        except Exception:
            return None

    def _prefill_borrador_descuentos(self, id_pago: int, numero_nomina: int) -> dict:
        """
        Prellena/actualiza borrador de descuentos para pago pendiente.
        Defaults: IMSS=50, Transporte=100.
        Si hay último pago pagado, clona valores finales.
        """
        if not self.detalles_desc_model:
            return {"status": "warning", "message": "Módulo detalles_desc no disponible, se omitió prellenado."}

        aplicado_imss, monto_imss = True, 50.0
        aplicado_transporte, monto_transporte = True, 100.0
        aplicado_extra, monto_extra, desc_extra = False, 0.0, None

        try:
            ultimo = self._get_ultimo_pago_confirmado(numero_nomina)
            if ultimo:
                ds_prev = self.discount_model.get_descuentos_por_pago(int(ultimo["id_pago"])) or []
                for d in ds_prev:
                    tipo = str(d.get("tipo") or d.get("tipo_descuento") or "").lower()
                    monto = float(d.get("monto_descuento") or d.get("monto") or 0.0)
                    if tipo == "retenciones_imss":
                        aplicado_imss, monto_imss = True, max(0.0, monto)
                    elif tipo == "transporte":
                        aplicado_transporte, monto_transporte = True, max(0.0, monto)
                    elif tipo == "descuento_extra":
                        aplicado_extra, monto_extra = True, max(0.0, monto)
                        desc_extra = (d.get("descripcion") or "").strip() or None

            self.detalles_desc_model.upsert_detalles(id_pago, {
                self.detalles_desc_model.COL_APLICADO_IMSS: aplicado_imss,
                self.detalles_desc_model.COL_MONTO_IMSS: monto_imss,
                self.detalles_desc_model.COL_APLICADO_TRANSPORTE: aplicado_transporte,
                self.detalles_desc_model.COL_MONTO_TRANSPORTE: monto_transporte,
                self.detalles_desc_model.COL_APLICADO_EXTRA: aplicado_extra,
                self.detalles_desc_model.COL_MONTO_EXTRA: monto_extra,
                self.detalles_desc_model.COL_DESCRIPCION_EXTRA: desc_extra
            })
            return {"status": "success", "message": "Borrador de descuentos prellenado correctamente."}
        except Exception as ex:
            return {"status": "error", "message": f"Error al prellenar borrador: {ex}"}

    # ---------------------------------------------------------------------
    # Generación pagos
    # ---------------------------------------------------------------------
    def existe_pago_para_fecha(self, numero_nomina: int, fecha: str, *, incluir_pendientes: bool = False) -> bool:
        try:
            if incluir_pendientes:
                q = f"""
                    SELECT COUNT(*) AS c FROM {self.E.TABLE.value}
                    WHERE {self.E.NUMERO_NOMINA.value}=%s AND {self.E.FECHA_PAGO.value}=%s
                """
                r = self.db.get_data(q, (numero_nomina, fecha), dictionary=True)
            else:
                q = f"""
                    SELECT COUNT(*) AS c FROM {self.E.TABLE.value}
                    WHERE {self.E.NUMERO_NOMINA.value}=%s AND {self.E.FECHA_PAGO.value}=%s
                    AND {self.E.ESTADO.value}='pagado'
                """
                r = self.db.get_data(q, (numero_nomina, fecha), dictionary=True)
            return (r or {}).get("c", 0) > 0
        except Exception:
            return False

    def generar_pagos_por_rango(self, fecha_inicio: str, fecha_fin: str) -> Dict[str, Any]:
        """
        Genera/actualiza pagos PENDIENTES por empleado para el rango [fecha_inicio, fecha_fin].
        - Dedup por (numero_nomina, fecha_inicio, fecha_fin): conserva el último, borra duplicados.
        - Si existe pagado en ese rango => omite (inmutabilidad).
        - Actualiza totales SIN pisar depósito/efectivo (update_pago recalcula saldo).
        """
        try:
            fecha_inicio = self._normalize_date(fecha_inicio)
            fecha_fin = self._normalize_date(fecha_fin)

            horas_rs = self.get_total_horas_trabajadas(fecha_inicio, fecha_fin, None)
            if horas_rs.get("status") != "success":
                return {"status": "error", "message": "No fue posible obtener horas del SP."}

            horas_rows = horas_rs.get("data") or []
            if not horas_rows:
                return {"status": "success", "message": "No hay horas registradas en el rango."}

            grupo_token = self._build_grupo_token(fecha_inicio, fecha_fin)
            hoy = self._today_str()

            generados = actualizados = eliminados = omitidos_pagados = sin_horas_sueldo = 0

            for r in horas_rows:
                try:
                    numero_nomina = int(r.get("numero_nomina", 0) or 0)
                    if numero_nomina <= 0:
                        continue

                    horas_dec = float(r.get("total_horas_trabajadas", 0.0) or 0.0)
                    sh = self._sueldo_hora(numero_nomina)
                    if horas_dec <= 0 or sh <= 0:
                        sin_horas_sueldo += 1
                        continue

                    monto_base = round(sh * horas_dec, 2)

                    q_exist = f"""
                        SELECT {self.E.ID_PAGO_NOMINA.value} AS id_pago,
                               {self.E.ESTADO.value} AS estado
                        FROM {self.E.TABLE.value}
                        WHERE {self.E.NUMERO_NOMINA.value}=%s
                          AND {self.E.FECHA_INICIO.value}=%s
                          AND {self.E.FECHA_FIN.value}=%s
                        ORDER BY {self.E.ID_PAGO_NOMINA.value} ASC
                    """
                    existentes = self.db.get_data_list(
                        q_exist, (numero_nomina, fecha_inicio, fecha_fin), dictionary=True
                    ) or []

                    if any(str(x.get("estado", "")).lower() == "pagado" for x in existentes):
                        omitidos_pagados += 1
                        continue

                    id_pago_target = None
                    if existentes:
                        id_pago_target = int(existentes[-1]["id_pago"])
                        dup_ids = [int(x["id_pago"]) for x in existentes[:-1]]
                        if dup_ids:
                            self.db.run_query(
                                f"DELETE FROM detalles_pagos_prestamo WHERE id_pago_nomina IN ({', '.join(['%s']*len(dup_ids))})",
                                tuple(dup_ids),
                            )
                            self.db.run_query(
                                f"DELETE FROM {self.E.TABLE.value} WHERE {self.E.ID_PAGO_NOMINA.value} IN ({', '.join(['%s']*len(dup_ids))})",
                                tuple(dup_ids),
                            )
                            eliminados += len(dup_ids)

                        self.update_pago(id_pago_target, {
                            self.E.GRUPO_PAGO.value: grupo_token,
                            self.E.FECHA_INICIO.value: fecha_inicio,
                            self.E.FECHA_FIN.value: fecha_fin,
                            self.E.ESTADO_GRUPO.value: "abierto",
                            self.E.FECHA_PAGO.value: hoy,
                            self.E.TOTAL_HORAS_TRABAJADAS.value: horas_dec,
                            self.E.MONTO_BASE.value: monto_base,
                            self.E.MONTO_TOTAL.value: monto_base,
                            self.D.MONTO_DESCUENTO.value: 0.0,
                            self.P.PRESTAMO_MONTO.value: 0.0,
                            self.E.ESTADO.value: "pendiente",
                        })
                        actualizados += 1
                    else:
                        ins_q = f"""
                            INSERT INTO {self.E.TABLE.value} (
                                {self.E.NUMERO_NOMINA.value},
                                {self.E.GRUPO_PAGO.value}, {self.E.FECHA_INICIO.value}, {self.E.FECHA_FIN.value}, {self.E.ESTADO_GRUPO.value},
                                {self.E.FECHA_PAGO.value},
                                {self.E.TOTAL_HORAS_TRABAJADAS.value},
                                {self.E.MONTO_BASE.value},
                                {self.E.MONTO_TOTAL.value},
                                {self.D.MONTO_DESCUENTO.value},
                                {self.P.PRESTAMO_MONTO.value},
                                {self.E.SALDO.value},
                                {self.E.PAGO_DEPOSITO.value},
                                {self.E.PAGO_EFECTIVO.value},
                                {self.E.ESTADO.value}
                            ) VALUES (%s,%s,%s,%s,'abierto',%s,%s,%s,%s,0,0,%s,0,0,'pendiente')
                        """
                        self.db.run_query(
                            ins_q,
                            (numero_nomina, grupo_token, fecha_inicio, fecha_fin, hoy,
                             horas_dec, monto_base, monto_base, monto_base)
                        )
                        id_pago_target = int(self.db.get_last_insert_id())
                        generados += 1

                    self._prefill_borrador_descuentos(id_pago_target, numero_nomina)

                except Exception:
                    continue

            msg = (
                f"{generados} creados, {actualizados} actualizados, {eliminados} duplicados eliminados, "
                f"{omitidos_pagados} omitidos (ya pagados), {sin_horas_sueldo} sin horas/sueldo."
            )
            return {"status": "success", "message": msg}
        except Exception as ex:
            return {"status": "error", "message": f"Error al generar por rango: {ex}"}

    def registrar_pago_manual(self, numero_nomina: int) -> Dict[str, Any]:
        """Crea pago manual unitario (fecha_inicio=fecha_fin=hoy)."""
        try:
            if not isinstance(numero_nomina, int) or numero_nomina <= 0:
                return {"status": "error", "message": "Número de nómina inválido"}
            today = self._today_str()
            if self.existe_pago_para_fecha(numero_nomina, today, incluir_pendientes=True):
                return {"status": "error", "message": "Ya existe un pago registrado para hoy"}
            return self.generar_pago_por_empleado(numero_nomina, today, today)
        except Exception as ex:
            return {"status": "error", "message": f"Error en pago manual: {ex}"}

    def generar_pago_por_empleado(self, numero_nomina: int, fecha_inicio: str, fecha_fin: str) -> Dict[str, Any]:
        """
        Genera pago pendiente del empleado para el rango dado.
        - Si existe el rango pendiente: actualiza totales sin pisar depósito/efectivo.
        - Si existe el rango pagado: error (inmutabilidad).
        """
        try:
            fecha_inicio = self._normalize_date(fecha_inicio)
            fecha_fin = self._normalize_date(fecha_fin)

            if not numero_nomina or not isinstance(numero_nomina, int):
                return {"status": "error", "message": "Número de nómina inválido."}

            horas_rs = self.get_total_horas_trabajadas(fecha_inicio, fecha_fin, numero_nomina)
            if horas_rs.get("status") != "success" or not horas_rs.get("data"):
                return {"status": "error", "message": f"No hay horas válidas para el empleado {numero_nomina}."}

            horas_dec = float(horas_rs["data"][0].get("total_horas_trabajadas", 0.0) or 0.0)
            sh = self._sueldo_hora(numero_nomina)
            if horas_dec <= 0 or sh <= 0:
                return {"status": "error", "message": "Horas o sueldo por hora inválidos."}

            monto_base = round(sh * horas_dec, 2)
            grupo_token = self._build_grupo_token(fecha_inicio, fecha_fin)
            hoy = self._today_str()

            q_exist = f"""
                SELECT {self.E.ID_PAGO_NOMINA.value} AS id_pago, {self.E.ESTADO.value} AS estado
                FROM {self.E.TABLE.value}
                WHERE {self.E.NUMERO_NOMINA.value}=%s
                  AND {self.E.FECHA_INICIO.value}=%s
                  AND {self.E.FECHA_FIN.value}=%s
                ORDER BY {self.E.ID_PAGO_NOMINA.value} ASC
            """
            existentes = self.db.get_data_list(q_exist, (numero_nomina, fecha_inicio, fecha_fin), dictionary=True) or []

            if any(str(x.get("estado", "")).lower() == "pagado" for x in existentes):
                return {"status": "error", "message": "Ese rango ya está pagado para el empleado."}

            if existentes:
                id_pago = int(existentes[-1]["id_pago"])
                self.update_pago(id_pago, {
                    self.E.GRUPO_PAGO.value: grupo_token,
                    self.E.FECHA_INICIO.value: fecha_inicio,
                    self.E.FECHA_FIN.value: fecha_fin,
                    self.E.ESTADO_GRUPO.value: "abierto",
                    self.E.FECHA_PAGO.value: hoy,
                    self.E.TOTAL_HORAS_TRABAJADAS.value: horas_dec,
                    self.E.MONTO_BASE.value: monto_base,
                    self.E.MONTO_TOTAL.value: monto_base,
                    self.D.MONTO_DESCUENTO.value: 0.0,
                    self.P.PRESTAMO_MONTO.value: 0.0,
                    self.E.ESTADO.value: "pendiente",
                })
                id_pago_target = id_pago
            else:
                insert_q = f"""
                    INSERT INTO {self.E.TABLE.value} (
                        {self.E.NUMERO_NOMINA.value},
                        {self.E.GRUPO_PAGO.value}, {self.E.FECHA_INICIO.value}, {self.E.FECHA_FIN.value}, {self.E.ESTADO_GRUPO.value},
                        {self.E.FECHA_PAGO.value},
                        {self.E.TOTAL_HORAS_TRABAJADAS.value},
                        {self.E.MONTO_BASE.value},
                        {self.E.MONTO_TOTAL.value},
                        {self.D.MONTO_DESCUENTO.value},
                        {self.P.PRESTAMO_MONTO.value},
                        {self.E.SALDO.value},
                        {self.E.PAGO_DEPOSITO.value},
                        {self.E.PAGO_EFECTIVO.value},
                        {self.E.ESTADO.value}
                    ) VALUES (%s,%s,%s,%s,'abierto',%s,%s,%s,%s,0,0,%s,0,0,'pendiente')
                """
                self.db.run_query(
                    insert_q,
                    (numero_nomina, grupo_token, fecha_inicio, fecha_fin, hoy,
                     horas_dec, monto_base, monto_base, monto_base)
                )
                id_pago_target = int(self.db.get_last_insert_id())

            self._prefill_borrador_descuentos(id_pago_target, numero_nomina)
            return {"status": "success", "message": f"Pago generado por ${monto_base:.2f}", "id_pago": id_pago_target}

        except Exception as ex:
            return {"status": "error", "message": f"Error en generar_pago_por_empleado: {ex}"}

    # ---------------------------------------------------------------------
    # Lectura (plano, por empleado, agrupado)
    # ---------------------------------------------------------------------
    def get_all_pagos(self) -> Dict[str, Any]:
        try:
            q = f"""
                SELECT 
                    p.{self.E.ID_PAGO_NOMINA.value} AS id_pago_nomina,
                    p.{self.E.ID_PAGO_NOMINA.value} AS id_pago,
                    p.{self.E.NUMERO_NOMINA.value}   AS numero_nomina,
                    p.{self.E.NUMERO_NOMINA.value}   AS id_empleado,
                    e.nombre_completo,
                    e.sueldo_por_hora,
                    p.{self.E.GRUPO_PAGO.value}      AS grupo_pago,
                    p.{self.E.FECHA_INICIO.value}    AS fecha_inicio,
                    p.{self.E.FECHA_FIN.value}       AS fecha_fin,
                    p.{self.E.ESTADO_GRUPO.value}    AS estado_grupo,
                    p.{self.E.FECHA_PAGO.value}      AS fecha_pago,
                    p.{self.E.TOTAL_HORAS_TRABAJADAS.value} AS horas,
                    p.{self.E.MONTO_BASE.value}      AS monto_base,
                    p.{self.E.MONTO_TOTAL.value}     AS monto_total,
                    p.{self.D.MONTO_DESCUENTO.value} AS descuentos,
                    p.{self.P.PRESTAMO_MONTO.value}  AS prestamos,
                    p.{self.E.SALDO.value}           AS saldo,
                    p.{self.E.PAGO_DEPOSITO.value}   AS deposito,
                    p.{self.E.PAGO_EFECTIVO.value}   AS efectivo,
                    p.{self.E.ESTADO.value}          AS estado
                FROM {self.E.TABLE.value} p
                JOIN empleados e ON p.{self.E.NUMERO_NOMINA.value} = e.numero_nomina
                ORDER BY p.{self.E.FECHA_PAGO.value} DESC, p.{self.E.ID_PAGO_NOMINA.value} DESC
            """
            rows = self.db.get_data_list(q, dictionary=True) or []
            return {"status": "success", "data": rows}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener pagos: {ex}"}

    def get_by_id(self, id_pago: int) -> Dict[str, Any]:
        try:
            if not isinstance(id_pago, int) or id_pago <= 0:
                return {"status": "error", "message": "ID de pago inválido"}
            q = f"SELECT * FROM {self.E.TABLE.value} WHERE {self.E.ID_PAGO_NOMINA.value}=%s"
            r = self.db.get_data(q, (id_pago,), dictionary=True)
            if not r:
                return {"status": "error", "message": "No se encontró el pago con ese ID"}
            return {"status": "success", "data": r}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener el pago: {ex}"}

    # ---------------------------------------------------------------------
    # Update (núcleo)
    # ---------------------------------------------------------------------
    def update_pago(self, id_pago: int, cambios: Dict[str, Any], *, force: bool = False) -> bool:
        """
        Actualiza campos permitidos con reglas robustas.

        Protecciones:
        - Si el pago ya está 'pagado', se bloquea cualquier modificación salvo force=True.
        - Si llega solo depósito o solo efectivo, NO fuerza complemento.
        - Recalcula saldo = total - (dep + efec) y permite saldo negativo (adelanto).

        Nota:
        - Si estado_nuevo='pendiente' y llega monto_base => monto_total = monto_base.
        """
        if not isinstance(id_pago, int) or id_pago <= 0:
            return False
        if not cambios:
            return True

        permitidas = {
            self.E.GRUPO_PAGO.value, self.E.FECHA_INICIO.value, self.E.FECHA_FIN.value, self.E.ESTADO_GRUPO.value,
            self.E.FECHA_PAGO.value, self.E.TOTAL_HORAS_TRABAJADAS.value, self.E.MONTO_BASE.value,
            self.E.MONTO_TOTAL.value, self.D.MONTO_DESCUENTO.value, self.P.PRESTAMO_MONTO.value,
            self.E.SALDO.value, self.E.PAGO_DEPOSITO.value, self.E.PAGO_EFECTIVO.value, self.E.ESTADO.value,
        }

        cur_rs = self.get_by_id(id_pago)
        if cur_rs.get("status") != "success":
            return False
        cur = cur_rs["data"]

        estado_actual = str(cur.get(self.E.ESTADO.value, "") or "").lower()
        if estado_actual == "pagado" and not force:
            # Bloquea modificaciones a pagados por defecto
            # (La UI ya lo bloquea, pero aquí queda blindado).
            return False

        def _f(x):
            try:
                return float(x)
            except Exception:
                return 0.0

        # Si se manda estado 'pendiente' + monto_base, forzamos total=base
        estado_nuevo = str(cambios.get(self.E.ESTADO.value, "")).lower()
        if estado_nuevo == "pendiente" and self.E.MONTO_BASE.value in cambios:
            cambios[self.E.MONTO_TOTAL.value] = _f(cambios[self.E.MONTO_BASE.value])

        total = _f(
            cambios.get(
                self.E.MONTO_TOTAL.value,
                cambios.get(self.E.MONTO_BASE.value, cur.get(self.E.MONTO_TOTAL.value, cur.get(self.E.MONTO_BASE.value, 0)))
            )
        )

        dep_cur = _f(cur.get(self.E.PAGO_DEPOSITO.value))
        efec_cur = _f(cur.get(self.E.PAGO_EFECTIVO.value))

        dep_in = self.E.PAGO_DEPOSITO.value in cambios
        efec_in = self.E.PAGO_EFECTIVO.value in cambios

        dep_new = _f(cambios.get(self.E.PAGO_DEPOSITO.value, dep_cur))
        efec_new = _f(cambios.get(self.E.PAGO_EFECTIVO.value, efec_cur))

        dep_new = max(0.0, dep_new)
        efec_new = max(0.0, efec_new)

        if dep_in and not efec_in:
            efec_new = efec_cur

        elif efec_in and not dep_in:
            dep_new = dep_cur
        saldo_new = round(total - dep_new - efec_new, 2)
        cambios[self.E.SALDO.value] = saldo_new

        if dep_in or dep_new != dep_cur:
            cambios[self.E.PAGO_DEPOSITO.value] = dep_new
        if efec_in or efec_new != efec_cur:
            cambios[self.E.PAGO_EFECTIVO.value] = efec_new

        sets, vals = [], []
        for k, v in cambios.items():
            if k in permitidas:
                sets.append(f"{k}=%s")
                vals.append(v)

        if not sets:
            return True

        try:
            q = f"UPDATE {self.E.TABLE.value} SET {', '.join(sets)} WHERE {self.E.ID_PAGO_NOMINA.value}=%s"
            vals.append(id_pago)

            cursor = self.db._cursor()
            cursor.execute(q, tuple(vals))
            rowcount = getattr(cursor, "rowcount", None)
            try:
                while cursor.nextset():
                    pass
            except Exception:
                pass
            cursor.close()
            self.db.connection.commit()

            if rowcount == 0:
                print(f"⚠️ update_pago: 0 filas afectadas (id_pago={id_pago}).")
            return True
        except Exception as ex:
            print(f"❌ Error en update_pago: {ex}")
            return False

    # ---------------------------------------------------------------------
    # Confirmación
    # ---------------------------------------------------------------------
    def confirmar_pago(self, id_pago: int, fecha_real_pago: Optional[str] = None) -> Dict[str, Any]:
        """
        Confirma el pago:
        - Aplica borrador de descuentos -> descuentos y limpia borrador.
        - Aplica detalles préstamo -> pagos_prestamo.
        - Recalcula monto_total = monto_base - descuentos - prestamos.
        - Respeta depósito/efectivo existentes; update_pago recalcula saldo.
        """
        try:
            pago = self.get_by_id(id_pago)
            if pago.get("status") != "success":
                return pago
            p = pago["data"]

            if str(p.get(self.E.ESTADO.value, "")).lower() == "pagado":
                return {"status": "success", "message": "El pago ya estaba confirmado."}

            numero_nomina = int(p.get(self.E.NUMERO_NOMINA.value))
            fecha_guardada = str(p.get(self.E.FECHA_PAGO.value) or "")
            fecha_real = self._normalize_date(fecha_real_pago or (fecha_guardada if fecha_guardada else self._today_str()))

            # 1) aplicar/limpiar borrador descuentos
            if self.detalles_desc_model is not None:
                try:
                    res_desc = self.detalles_desc_model.aplicar_a_descuentos_y_limpiar(
                        id_pago,
                        self.discount_model,
                    ) or {}
                except Exception as _ex:
                    return {"status": "error", "message": f"No se pudo aplicar descuentos del borrador: {_ex}"}

                # No confirmar silenciosamente si falló la aplicación de descuentos.
                if isinstance(res_desc, dict) and str(res_desc.get("status") or "").lower() == "error":
                    return {
                        "status": "error",
                        "message": (res_desc.get("message") or "Error al aplicar descuentos del borrador."),
                    }

            # 2) aplicar detalles préstamo -> pagos_prestamo
            self._aplicar_detalles_prestamo_de_pago(
                id_pago_nomina=id_pago,
                fecha_pago=fecha_guardada,
                fecha_real=fecha_real
            )

            # 3) recomputar totales
            try:
                total_desc = float(self.discount_model.get_total_descuentos_por_pago(id_pago) or 0.0)
            except Exception:
                total_desc = 0.0

            # Respaldo: si no se pudo materializar en tabla descuentos, conserva el monto ya guardado en pagos.
            if total_desc <= 0:
                try:
                    total_desc = float(p.get(self.D.MONTO_DESCUENTO.value) or 0.0)
                except Exception:
                    total_desc = 0.0

            total_prest = self._get_prestamos_totales_para_pago(
                id_pago=id_pago, numero_nomina=numero_nomina, fecha_fin=fecha_guardada
            )
            monto_base = float(p.get(self.E.MONTO_BASE.value) or 0)
            nuevo_total = max(0.0, round(monto_base - total_desc - total_prest, 2))

            cambios = {
                self.E.FECHA_PAGO.value: fecha_real,
                self.E.MONTO_TOTAL.value: nuevo_total,
                self.D.MONTO_DESCUENTO.value: total_desc,
                self.P.PRESTAMO_MONTO.value: total_prest,
                self.E.ESTADO.value: "pagado",
            }

            ok = self.update_pago(id_pago, cambios, force=True)
            if not ok:
                return {"status": "error", "message": "No se pudo confirmar el pago en DB."}

            return {"status": "success", "message": "Pago confirmado correctamente (saldo respetado)."}
        except Exception as ex:
            return {"status": "error", "message": f"Error al confirmar pago: {ex}"}

    def crear_grupo_pagado(self, fecha: str) -> Dict[str, Any]:
        """
        CONFIRMA pagos pendientes del día `fecha` y cierra el grupo en `pagos`.
        (Este es el comportamiento 'seguro' para el botón de confirmar/cerrar fecha).
        """
        try:
            fecha = self._normalize_date(fecha)
            datetime.strptime(fecha, "%Y-%m-%d")

            q_ids = f"""
                SELECT {self.E.ID_PAGO_NOMINA.value} AS id
                FROM {self.E.TABLE.value}
                WHERE {self.E.FECHA_PAGO.value}=%s
                  AND {self.E.ESTADO.value}='pendiente'
                ORDER BY {self.E.NUMERO_NOMINA.value} ASC, {self.E.ID_PAGO_NOMINA.value} ASC
            """
            filas = self.db.get_data_list(q_ids, (fecha,), dictionary=True) or []
            if not filas:
                return {"status": "error", "message": f"No hay pagos PENDIENTES con fecha_pago = {fecha}."}

            confirmados, errores = 0, 0
            fallos: List[Dict[str, Any]] = []
            for r in filas:
                pid = int(r["id"])
                res = self.confirmar_pago(pid, fecha_real_pago=fecha)
                if res.get("status") == "success":
                    confirmados += 1
                else:
                    errores += 1
                    fallos.append({"id_pago": pid, "error": res.get("message", "Error desconocido")})

            q_close = f"""
                UPDATE {self.E.TABLE.value}
                SET {self.E.ESTADO_GRUPO.value}='cerrado'
                WHERE {self.E.FECHA_PAGO.value}=%s
            """
            self.db.run_query(q_close, (fecha,))

            return {
                "status": "success",
                "message": f"Grupo {fecha}: {confirmados} pagos confirmados, {errores} con error.",
                "detalle_errores": fallos
            }
        except Exception as ex:
            return {"status": "error", "message": f"Error al confirmar/cerrar grupo por fecha: {ex}"}

    # ---------------------------------------------------------------------
    # Grupos manuales vacíos (UI)
    # ---------------------------------------------------------------------
    def crear_grupo_pagado_vacio(self, fecha: str) -> dict:
        """
        Crea grupo 'pagado' VACÍO (manual) para que aparezca en UI aunque no tenga pagos.
        NO confirma ni toca pagos.
        """
        try:
            fecha = self._normalize_date(fecha)
            datetime.strptime(fecha, "%Y-%m-%d")

            q_chk = f"""
                SELECT COUNT(*) AS c
                FROM {self.E.TABLE.value}
                WHERE {self.E.ESTADO.value}='pagado' AND {self.E.FECHA_PAGO.value}=%s
            """
            r = self.db.get_data(q_chk, (fecha,), dictionary=True) or {}
            if int(r.get("c", 0)) > 0:
                return {"status": "error", "message": f"Ya existen pagos 'pagado' con fecha {fecha}."}

            q_ins = """
                INSERT IGNORE INTO grupos_pagos (fecha, categoria, estado_grupo)
                VALUES (%s, 'pagado', 'abierto')
            """
            self.db.run_query(q_ins, (fecha,))
            return {"status": "success", "message": f"Grupo 'pagado' vacío creado para {fecha}."}
        except Exception as ex:
            return {"status": "error", "message": f"No fue posible crear el grupo: {ex}"}

    def eliminar_grupo_por_fecha(self, fecha: str) -> dict:
        """Elimina grupo manual vacío (si NO hay pagos pagados en esa fecha)."""
        try:
            fecha = self._normalize_date(fecha)
            datetime.strptime(fecha, "%Y-%m-%d")

            q_chk = f"""
                SELECT COUNT(*) AS c
                FROM {self.E.TABLE.value}
                WHERE {self.E.ESTADO.value}='pagado' AND {self.E.FECHA_PAGO.value}=%s
            """
            r = self.db.get_data(q_chk, (fecha,), dictionary=True) or {}
            if int(r.get("c", 0)) > 0:
                return {"status": "error", "message": "No se puede eliminar: ya hay pagos 'pagado' en esa fecha."}

            q_del = "DELETE FROM grupos_pagos WHERE fecha=%s AND categoria='pagado'"
            self.db.run_query(q_del, (fecha,))
            return {"status": "success", "message": f"Grupo manual eliminado para {fecha}."}
        except Exception as ex:
            return {"status": "error", "message": f"No fue posible eliminar el grupo: {ex}"}

    # ---------------------------------------------------------------------
    # Sync / refresh desde asistencias (blindado para pagados)
    # ---------------------------------------------------------------------
    def _fetch_range_rows(self, numero_nomina: int, periodo_ini: str, periodo_fin: str) -> List[Dict[str, Any]]:
        q = f"""
            SELECT
                {self.E.ID_PAGO_NOMINA.value}   AS id_pago,
                {self.E.FECHA_PAGO.value}       AS fecha_pago,
                {self.E.FECHA_INICIO.value}     AS fecha_inicio,
                {self.E.FECHA_FIN.value}        AS fecha_fin,
                {self.E.GRUPO_PAGO.value}       AS grupo_pago,
                {self.E.ESTADO.value}           AS estado,
                {self.E.TOTAL_HORAS_TRABAJADAS.value} AS horas,
                {self.E.MONTO_BASE.value}       AS monto_base,
                {self.E.MONTO_TOTAL.value}      AS monto_total,
                {self.D.MONTO_DESCUENTO.value}  AS descuentos,
                {self.P.PRESTAMO_MONTO.value}   AS prestamos,
                {self.E.PAGO_DEPOSITO.value}    AS deposito,
                {self.E.PAGO_EFECTIVO.value}    AS efectivo
            FROM {self.E.TABLE.value}
            WHERE {self.E.NUMERO_NOMINA.value}=%s
              AND {self.E.FECHA_PAGO.value} BETWEEN %s AND %s
            ORDER BY {self.E.FECHA_PAGO.value} ASC, {self.E.ID_PAGO_NOMINA.value} ASC
        """
        return self.db.get_data_list(q, (numero_nomina, periodo_ini, periodo_fin), dictionary=True) or []

    def _rebuild_payment_from_range(
        self,
        numero_nomina: int,
        periodo_ini: str,
        periodo_fin: str,
        *,
        overwrite: bool,
        action: str,
        allow_paid_updates: bool,
    ) -> Dict[str, Any]:
        """
        Reconstruye/refresca pagos AUTO en un rango:
        - Si detecta pagos manuales en el rango => conflicto a menos que overwrite=True.
        - Si no existen pagos auto => genera.
        - Si existe pago auto pendiente => actualiza horas/base/total.
        - Si existe pago pagado => por defecto NO toca; si allow_paid_updates=True ajusta SOLO horas y audita.
        """
        detalle = {"id_empleado": numero_nomina, "rango": [periodo_ini, periodo_fin], "accion": "skip", "motivo": ""}
        resultado = {
            "creados": 0,
            "actualizados": 0,
            "omitidos_pagados": [],
            "conflictivos": [],
            "requires_overwrite": False,
            "detalle": detalle,
        }

        try:
            sueldo = self._sueldo_hora(numero_nomina)
            horas_rs = self.get_total_horas_trabajadas(periodo_ini, periodo_fin, numero_nomina)
            horas_rows = horas_rs.get("data") or []
            horas = float(horas_rows[0].get("total_horas_trabajadas", 0.0)) if horas_rows else 0.0

            if horas <= 0 or sueldo <= 0:
                detalle["motivo"] = "sin_horas_o_sueldo"
                return resultado

            rows = self._fetch_range_rows(numero_nomina, periodo_ini, periodo_fin)
            auto_rows = [r for r in rows if self._is_auto_pago(r)]
            manual_rows = [r for r in rows if not self._is_auto_pago(r)]

            if manual_rows:
                if not overwrite:
                    detalle["accion"] = "conflict"
                    detalle["motivo"] = "pagos_manual_en_rango"
                    resultado["conflictivos"].append({
                        "id_empleado": numero_nomina,
                        "pagos": [int(r.get("id_pago") or 0) for r in manual_rows],
                        "motivo": "manual_en_rango",
                    })
                    resultado["requires_overwrite"] = True
                    return resultado
                for manual in manual_rows:
                    self.eliminar_pago(int(manual.get("id_pago") or 0), force=True)

            monto_base = round(sueldo * horas, 2)

            if not auto_rows:
                gen = self.generar_pago_por_empleado(numero_nomina, periodo_ini, periodo_fin)
                if gen.get("status") == "success":
                    detalle["accion"] = "create"
                    detalle["motivo"] = "creado_desde_asistencias"
                    resultado["creados"] = 1
                else:
                    detalle["accion"] = "error"
                    detalle["motivo"] = gen.get("message", "error_generar")
                return resultado

            auto = auto_rows[-1]
            id_pago = int(auto.get("id_pago") or 0)
            estado = str(auto.get("estado") or "").lower()
            horas_actuales = float(auto.get("horas") or 0.0)

            if abs(horas - horas_actuales) < 0.01 and action == "refresh":
                detalle["motivo"] = "sin_cambios"
                return resultado

            if estado == "pendiente":
                descuentos = float(auto.get("descuentos") or 0.0)
                prestamos = float(auto.get("prestamos") or 0.0)
                total = round(max(0.0, monto_base - descuentos - prestamos), 2)
                payload = {
                    self.E.FECHA_INICIO.value: periodo_ini,
                    self.E.FECHA_FIN.value: periodo_fin,
                    self.E.GRUPO_PAGO.value: auto.get("grupo_pago") or self._build_grupo_token(periodo_ini, periodo_fin),
                    self.E.TOTAL_HORAS_TRABAJADAS.value: horas,
                    self.E.MONTO_BASE.value: monto_base,
                    self.E.MONTO_TOTAL.value: total,
                }
                ok = self.update_pago(id_pago, payload)
                if ok:
                    detalle["accion"] = "update"
                    detalle["motivo"] = "pendiente_actualizado"
                    resultado["actualizados"] = 1
                else:
                    detalle["accion"] = "error"
                    detalle["motivo"] = "fallo_update_pendiente"
                return resultado

            if estado == "pagado":
                # ✅ Inmutabilidad por defecto
                if not allow_paid_updates:
                    detalle["accion"] = "skip"
                    detalle["motivo"] = "pagado_inmutable"
                    resultado["omitidos_pagados"].append(id_pago)
                    return resultado

                # Excepción: solo ajustar horas y auditar
                payload = {self.E.TOTAL_HORAS_TRABAJADAS.value: horas}
                ok = self.update_pago(id_pago, payload, force=True)
                if not ok:
                    detalle["accion"] = "error"
                    detalle["motivo"] = "fallo_update_pagado_horas"
                    return resultado

                self._registrar_auditoria_pago(
                    id_pago=id_pago,
                    numero_nomina=numero_nomina,
                    fecha_referencia=periodo_fin,
                    campo=self.E.TOTAL_HORAS_TRABAJADAS.value,
                    valor_anterior=horas_actuales,
                    valor_nuevo=horas,
                    motivo=f"sync_paid_{action}",
                )
                detalle["accion"] = "update"
                detalle["motivo"] = "pagado_horas_ajustadas"
                resultado["actualizados"] = 1
                return resultado

            detalle["motivo"] = f"estado_{estado}"
            return resultado

        except Exception as ex:
            detalle["accion"] = "error"
            detalle["motivo"] = str(ex)
            return resultado

    def refresh_from_assistance(
        self,
        periodo_ini: str,
        periodo_fin: str,
        id_empleado: Optional[int] = None,
        *,
        overwrite: bool = False,
        allow_paid_updates: bool = False,
    ) -> Dict[str, Any]:
        """
        Recalcula pagos AUTO usando asistencias.
        - Por defecto NO toca pagados (allow_paid_updates=False).
        """
        periodo_ini = self._normalize_date(periodo_ini)
        periodo_fin = self._normalize_date(periodo_fin)

        resumen = {
            **self._build_scope(periodo_ini, periodo_fin, id_empleado),
            "creados": 0,
            "actualizados": 0,
            "omitidos_pagados": [],
            "conflictivos": [],
            "requires_overwrite": False,
            "detallado": [],
        }

        try:
            asistencia = self._get_assistance_model()
            rangos = asistencia.collect_ranges_for_period(periodo_ini, periodo_fin, id_empleado)
        except Exception as ex:
            resumen["detallado"].append({
                "accion": "error",
                "motivo": f"collect_ranges: {ex}",
                "rango": [periodo_ini, periodo_fin],
                "id_empleado": id_empleado,
            })
            return resumen

        if not rangos and id_empleado:
            rangos = [(id_empleado, periodo_ini, periodo_fin)]

        for numero_nomina, ini, fin in rangos:
            ini_norm = self._normalize_date(ini)
            fin_norm = self._normalize_date(fin)
            resultado = self._rebuild_payment_from_range(
                numero_nomina,
                ini_norm,
                fin_norm,
                overwrite=overwrite,
                action="refresh",
                allow_paid_updates=allow_paid_updates,
            )
            resumen["creados"] += resultado["creados"]
            resumen["actualizados"] += resultado["actualizados"]
            resumen["omitidos_pagados"].extend(resultado["omitidos_pagados"])
            resumen["conflictivos"].extend(resultado["conflictivos"])
            if resultado["requires_overwrite"]:
                resumen["requires_overwrite"] = True
            resumen["detallado"].append(resultado["detalle"])

        return resumen

    def restore_green_dates(
        self,
        periodo_ini: str,
        periodo_fin: str,
        id_empleado: Optional[int] = None,
        *,
        overwrite: bool = False,
        allow_paid_updates: bool = False,
    ) -> Dict[str, Any]:
        """
        Restaura pagos AUTO faltantes tras eliminaciones (fechas verdes).
        - Por defecto NO toca pagados.
        """
        periodo_ini = self._normalize_date(periodo_ini)
        periodo_fin = self._normalize_date(periodo_fin)

        resumen = {
            **self._build_scope(periodo_ini, periodo_fin, id_empleado),
            "creados": 0,
            "actualizados": 0,
            "omitidos_pagados": [],
            "conflictivos": [],
            "requires_overwrite": False,
            "detallado": [],
        }

        try:
            asistencia = self._get_assistance_model()
            rangos = asistencia.collect_ranges_for_period(periodo_ini, periodo_fin, id_empleado)
        except Exception as ex:
            resumen["detallado"].append({
                "accion": "error",
                "motivo": f"collect_ranges: {ex}",
                "rango": [periodo_ini, periodo_fin],
                "id_empleado": id_empleado,
            })
            return resumen

        if not rangos and id_empleado:
            rangos = [(id_empleado, periodo_ini, periodo_fin)]

        for numero_nomina, ini, fin in rangos:
            ini_norm = self._normalize_date(ini)
            fin_norm = self._normalize_date(fin)
            resultado = self._rebuild_payment_from_range(
                numero_nomina,
                ini_norm,
                fin_norm,
                overwrite=overwrite,
                action="restore",
                allow_paid_updates=allow_paid_updates,
            )
            resumen["creados"] += resultado["creados"]
            resumen["actualizados"] += resultado["actualizados"]
            resumen["omitidos_pagados"].extend(resultado["omitidos_pagados"])
            resumen["conflictivos"].extend(resultado["conflictivos"])
            if resultado["requires_overwrite"]:
                resumen["requires_overwrite"] = True
            resumen["detallado"].append(resultado["detalle"])

        return resumen

    def sincronizar_desde_asistencia(self, numero_nomina: int, fecha: str, *, overwrite_paid: bool = False) -> Dict[str, Any]:
        """
        Recalcula pagos cuyo rango incluye `fecha` tras un cambio en asistencias.

        - Pagos 'pendiente': actualiza horas y montos base/total preservando abonos.
        - Pagos 'pagado'  : por defecto NO se toca (inmutable). Si overwrite_paid=True ajusta SOLO horas y audita.
        """
        resumen = {
            "status": "success",
            "pendientes_actualizados": 0,
            "pagados_ajustados": 0,
            "sin_cambios": 0,
            "errores": [],
        }

        try:
            if not numero_nomina or not isinstance(numero_nomina, int):
                return {"status": "noop", "message": "Número de nómina inválido."}
            if not fecha:
                return {"status": "noop", "message": "Fecha vacia; no se sincroniza."}

            def _parse_fecha(val) -> Optional[date]:
                if isinstance(val, datetime):
                    return val.date()
                if isinstance(val, date):
                    return val
                if not val:
                    return None
                s = str(val).strip()
                for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                    try:
                        return datetime.strptime(s, fmt).date()
                    except ValueError:
                        continue
                return None

            fecha_ref = _parse_fecha(fecha)
            if not fecha_ref:
                return {"status": "noop", "message": f"Fecha {fecha} inválida; usa YYYY-MM-DD."}

            q = f"""
                SELECT
                    {self.E.ID_PAGO_NOMINA.value}     AS id_pago,
                    {self.E.FECHA_INICIO.value}       AS fecha_inicio,
                    {self.E.FECHA_FIN.value}          AS fecha_fin,
                    {self.E.FECHA_PAGO.value}         AS fecha_pago,
                    {self.E.ESTADO.value}             AS estado,
                    {self.E.TOTAL_HORAS_TRABAJADAS.value} AS horas_registradas,
                    {self.E.MONTO_BASE.value}         AS monto_base,
                    {self.D.MONTO_DESCUENTO.value}    AS descuentos_totales,
                    {self.P.PRESTAMO_MONTO.value}     AS prestamos_totales,
                    {self.E.MONTO_TOTAL.value}        AS monto_total_guardado
                FROM {self.E.TABLE.value}
                WHERE {self.E.NUMERO_NOMINA.value}=%s
            """
            pagos = self.db.get_data_list(q, (numero_nomina,), dictionary=True) or []
            if not pagos:
                return {"status": "noop", "message": "Sin pagos relacionados al empleado."}

            fecha_iso = fecha_ref.strftime("%Y-%m-%d")
            sueldo_hora = self._sueldo_hora(numero_nomina)

            for pago in pagos:
                id_pago = int(pago.get("id_pago") or 0)
                if id_pago <= 0:
                    continue

                fi = _parse_fecha(pago.get("fecha_inicio")) or _parse_fecha(pago.get("fecha_pago"))
                ff = _parse_fecha(pago.get("fecha_fin")) or _parse_fecha(pago.get("fecha_pago"))
                if not fi or not ff:
                    continue
                if not (fi <= fecha_ref <= ff):
                    continue

                rs_horas = self.get_total_horas_trabajadas(fi.strftime("%Y-%m-%d"), ff.strftime("%Y-%m-%d"), numero_nomina)
                if rs_horas.get("status") != "success":
                    resumen["errores"].append(f"Pago {id_pago}: no se pudieron obtener horas ({rs_horas.get('message')}).")
                    continue

                data_horas = rs_horas.get("data") or []
                horas_nuevas = float(data_horas[0].get("total_horas_trabajadas", 0.0) or 0.0) if data_horas else 0.0
                horas_actuales = float(pago.get("horas_registradas") or 0.0)

                if abs(horas_nuevas - horas_actuales) < 0.01:
                    resumen["sin_cambios"] += 1
                    continue

                estado = str(pago.get("estado") or "").lower()

                if estado == "pagado" and not overwrite_paid:
                    resumen["sin_cambios"] += 1
                    continue

                cambios = {self.E.TOTAL_HORAS_TRABAJADAS.value: horas_nuevas}

                if estado == "pendiente":
                    monto_base_actual = float(pago.get("monto_base") or 0.0)
                    descuentos_actuales = float(pago.get("descuentos_totales") or 0.0)
                    prestamos_actuales = float(pago.get("prestamos_totales") or 0.0)
                    monto_total_actual = float(pago.get("monto_total_guardado") or 0.0)

                    monto_base_nuevo = round(max(0.0, sueldo_hora * horas_nuevas), 2)
                    monto_total_nuevo = round(max(0.0, monto_base_nuevo - descuentos_actuales - prestamos_actuales), 2)

                    cambios[self.E.MONTO_BASE.value] = monto_base_nuevo
                    cambios[self.E.MONTO_TOTAL.value] = monto_total_nuevo

                    if not self.update_pago(id_pago, cambios):
                        resumen["errores"].append(f"Pago {id_pago}: error al actualizar montos.")
                        continue

                    self._registrar_auditoria_pago(
                        id_pago=id_pago,
                        numero_nomina=numero_nomina,
                        fecha_referencia=fecha_iso,
                        campo=self.E.TOTAL_HORAS_TRABAJADAS.value,
                        valor_anterior=horas_actuales,
                        valor_nuevo=horas_nuevas,
                        motivo="sync_pendiente",
                    )
                    if abs(monto_base_nuevo - monto_base_actual) >= 0.01:
                        self._registrar_auditoria_pago(
                            id_pago=id_pago,
                            numero_nomina=numero_nomina,
                            fecha_referencia=fecha_iso,
                            campo=self.E.MONTO_BASE.value,
                            valor_anterior=monto_base_actual,
                            valor_nuevo=monto_base_nuevo,
                            motivo="sync_pendiente",
                        )
                    if abs(monto_total_nuevo - monto_total_actual) >= 0.01:
                        self._registrar_auditoria_pago(
                            id_pago=id_pago,
                            numero_nomina=numero_nomina,
                            fecha_referencia=fecha_iso,
                            campo=self.E.MONTO_TOTAL.value,
                            valor_anterior=monto_total_actual,
                            valor_nuevo=monto_total_nuevo,
                            motivo="sync_pendiente",
                        )
                    resumen["pendientes_actualizados"] += 1

                else:
                    # pagado con overwrite_paid=True -> ajustar solo horas + auditar
                    if not self.update_pago(id_pago, cambios, force=True):
                        resumen["errores"].append(f"Pago {id_pago}: no se pudieron ajustar las horas.")
                        continue

                    self._registrar_auditoria_pago(
                        id_pago=id_pago,
                        numero_nomina=numero_nomina,
                        fecha_referencia=fecha_iso,
                        campo=self.E.TOTAL_HORAS_TRABAJADAS.value,
                        valor_anterior=horas_actuales,
                        valor_nuevo=horas_nuevas,
                        motivo="sync_pagado_forzado",
                    )
                    resumen["pagados_ajustados"] += 1

            if resumen["pendientes_actualizados"] == 0 and resumen["pagados_ajustados"] == 0 and not resumen["errores"]:
                return {"status": "noop", "message": "No se encontraron pagos pendientes que involucren la fecha indicada."}
            return resumen

        except Exception as ex:
            return {"status": "error", "message": f"Fallo al sincronizar pagos: {ex}"}

    # ---------------------------------------------------------------------
    # Eliminación (safe)
    # ---------------------------------------------------------------------
    def eliminar_pago(self, id_pago: int, force: bool = False) -> dict:
        """
        Elimina un pago. Si está 'pagado' requiere force=True.
        Limpia dependencias si existen:
        - detalles_pagos_prestamo
        - pagos_prestamo
        - descuentos
        - borrador descuento_detalles (si existe)
        """
        try:
            r = self.get_by_id(id_pago)
            if r.get("status") != "success":
                return {"status": "error", "message": "Pago no encontrado."}
            row = r["data"]
            estado = str(row.get(self.E.ESTADO.value) or "").lower()
            if estado == "pagado" and not force:
                return {"status": "error", "message": "Pago confirmado: usa force=True para eliminarlo."}

            pagos_tab = self.E.TABLE.value
            id_col = self.E.ID_PAGO_NOMINA.value
            prestamos_afectados = self._get_prestamos_relacionados_a_pago(id_pago)

            self._safe_delete_by_pago("detalles_pagos_prestamo", id_col, id_pago)
            self._safe_delete_by_pago("pagos_prestamo", id_col, id_pago)
            self._safe_delete_by_pago("descuentos", id_col, id_pago)

            try:
                if self.detalles_desc_model:
                    self.detalles_desc_model.eliminar_por_id_pago(id_pago)
            except Exception:
                pass

            self.db.run_query(f"DELETE FROM {pagos_tab} WHERE {id_col}=%s", (id_pago,))

            # Recalcula saldos/estado de préstamos impactados tras eliminar pagos_prestamo.
            for id_prestamo in prestamos_afectados:
                self._recalcular_saldo_y_estado_prestamo(id_prestamo)

            return {"status": "success", "message": f"Pago #{id_pago} eliminado correctamente."}
        except Exception as ex:
            return {"status": "error", "message": f"No se pudo eliminar el pago: {ex}"}

    def eliminar_pagos_por_fecha(self, fecha: str, *, force: bool = False, estado: Optional[str] = "pagado") -> dict:
        """
        Elimina pagos por fecha_pago.
        - Por defecto elimina solo estado='pagado'.
        - Si force=False y hay pagados, bloquea.
        """
        try:
            fecha = self._normalize_date(fecha)
            datetime.strptime(fecha, "%Y-%m-%d")

            estado = (estado or "").strip().lower()
            if estado in ("*", "all", "any", "todos"):
                estado = ""

            where_estado = ""
            params: List[Any] = [fecha]
            if estado:
                where_estado = f" AND {self.E.ESTADO.value}=%s"
                params.append(estado)

            q_ids = f"""
                SELECT {self.E.ID_PAGO_NOMINA.value} AS id_pago, {self.E.ESTADO.value} AS estado
                FROM {self.E.TABLE.value}
                WHERE {self.E.FECHA_PAGO.value}=%s{where_estado}
            """
            rows = self.db.get_data_list(q_ids, tuple(params), dictionary=True) or []
            if not rows:
                return {"status": "noop", "message": f"No hay pagos para eliminar en {fecha}."}

            if not force and any(str(r.get("estado") or "").lower() == "pagado" for r in rows):
                return {"status": "error", "message": "Hay pagos 'pagado' en esa fecha. Usa force=True para eliminarlos."}

            eliminados = 0
            for r in rows:
                pid = int(r.get("id_pago") or 0)
                if pid <= 0:
                    continue
                res = self.eliminar_pago(pid, force=True)
                if isinstance(res, dict) and res.get("status") == "success":
                    eliminados += 1

            try:
                self.db.run_query("DELETE FROM grupos_pagos WHERE fecha=%s AND categoria='pagado'", (fecha,))
            except Exception:
                pass

            if eliminados == 0:
                return {"status": "error", "message": "No se eliminaron pagos (posible error de IDs)."}
            return {"status": "success", "message": f"Se eliminaron {eliminados} pagos de {fecha}."}
        except Exception as ex:
            return {"status": "error", "message": f"No fue posible eliminar pagos por fecha: {ex}"}

    # ---------------------------------------------------------------------
    # Préstamos (confirmados + pendientes)
    # ---------------------------------------------------------------------
    def _get_prestamos_totales_para_pago(self, id_pago: int, numero_nomina: int, fecha_fin: str) -> float:
        try:
            total_confirmado = float(self.loan_payment_model.get_total_prestamos_por_pago(id_pago) or 0)
        except Exception:
            total_confirmado = 0.0
        try:
            total_pendiente = float(self._get_total_detalles_prestamo_por_pago(id_pago) or 0)
        except Exception:
            total_pendiente = 0.0
        return round(total_confirmado + total_pendiente, 2)

    def _get_total_detalles_prestamo_por_pago(self, id_pago: int) -> float:
        try:
            q = f"""
                SELECT IFNULL(SUM({E_DET.MONTO_GUARDADO.value}), 0) AS total
                FROM detalles_pagos_prestamo
                WHERE {E_DET.ID_PAGO.value}=%s
            """
            r = self.db.get_data(q, (id_pago,), dictionary=True)
            return float((r or {}).get("total", 0) or 0)
        except Exception:
            return 0.0

    def _aplicar_detalles_prestamo_de_pago(self, id_pago_nomina: int, fecha_pago: str, fecha_real: str):
        try:
            q = f"""
                SELECT {E_DET.ID_PRESTAMO.value} AS id_prestamo
                FROM detalles_pagos_prestamo
                WHERE {E_DET.ID_PAGO.value}=%s
            """
            rows = self.db.get_data_list(q, (id_pago_nomina,), dictionary=True) or []
            for r in rows:
                id_prestamo = int(r["id_prestamo"])
                self.loan_payment_model.add_from_detalle(
                    id_pago_nomina=id_pago_nomina,
                    id_prestamo=id_prestamo,
                    fecha_pago=fecha_pago,
                    fecha_generacion=fecha_pago,
                    aplicado=True,
                    fecha_real_pago=fecha_real
                )
        except Exception as ex:
            print(f"❌ Error aplicando detalle de préstamo: {ex}")

    # ---------------------------------------------------------------------
    # Auditoría + grupos auxiliares
    # ---------------------------------------------------------------------
    def _ensure_auditoria_table(self):
        """Crea tabla pagos_auditoria si hace falta."""
        try:
            q = f"""
            CREATE TABLE IF NOT EXISTS pagos_auditoria (
                id_auditoria INT AUTO_INCREMENT PRIMARY KEY,
                id_pago INT NOT NULL,
                numero_nomina SMALLINT UNSIGNED NOT NULL,
                fecha_referencia DATE NOT NULL,
                campo VARCHAR(80) NOT NULL,
                valor_anterior VARCHAR(50) NULL,
                valor_nuevo VARCHAR(50) NULL,
                motivo VARCHAR(40) NOT NULL,
                fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_pago)
                    REFERENCES {self.E.TABLE.value}({self.E.ID_PAGO_NOMINA.value})
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            self.db.run_query(q)
        except Exception as ex:
            print(f"❌ No se pudo asegurar la tabla pagos_auditoria: {ex}")

    def _registrar_auditoria_pago(
        self,
        *,
        id_pago: int,
        numero_nomina: int,
        fecha_referencia: str,
        campo: str,
        valor_anterior,
        valor_nuevo,
        motivo: str,
    ) -> None:
        """Inserta fila de auditoría (silencioso si falla)."""
        try:
            if not self._table_exists("pagos_auditoria"):
                return
            q = """
                INSERT INTO pagos_auditoria
                (id_pago, numero_nomina, fecha_referencia, campo, valor_anterior, valor_nuevo, motivo)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(
                q,
                (
                    id_pago,
                    numero_nomina,
                    fecha_referencia,
                    campo,
                    "" if valor_anterior is None else str(valor_anterior),
                    "" if valor_nuevo is None else str(valor_nuevo),
                    motivo,
                ),
            )
        except Exception as ex:
            print(f"❌ Auditoría no registrada ({campo}): {ex}")

    def _ensure_grupos_table(self):
        """Crea tabla grupos_pagos para mostrar grupos manuales por fecha en UI."""
        q = """
        CREATE TABLE IF NOT EXISTS grupos_pagos (
            id_grupo INT AUTO_INCREMENT PRIMARY KEY,
            fecha DATE NOT NULL,
            categoria ENUM('pagado','pendiente') NOT NULL DEFAULT 'pagado',
            estado_grupo ENUM('abierto','cerrado') NOT NULL DEFAULT 'abierto',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_fecha_categoria (fecha, categoria)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        self.db.run_query(q)

    # ---------------------------------------------------------------------
    # Helpers seguros
    # ---------------------------------------------------------------------
    def _table_exists(self, table_name: str) -> bool:
        try:
            q = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            r = self.db.get_data(q, (self.db.database, table_name), dictionary=True)
            return int((r or {}).get("c", 0)) > 0
        except Exception:
            return False

    def _safe_delete_by_pago(self, table: str, id_col: str, id_pago: int) -> None:
        """Borra filas en `table` por `id_col=id_pago` solo si existe la tabla."""
        if not self._table_exists(table):
            return
        try:
            self.db.run_query(f"DELETE FROM {table} WHERE {id_col}=%s", (id_pago,))
        except Exception:
            pass

    def _get_prestamos_relacionados_a_pago(self, id_pago: int) -> List[int]:
        """
        Obtiene los id_prestamo vinculados a un pago de nómina
        (confirmados y/o detalles pendientes).
        """
        ids: set[int] = set()
        try:
            if self._table_exists("pagos_prestamo"):
                q = f"""
                    SELECT DISTINCT {self.LP.ID_PRESTAMO.value} AS id_prestamo
                    FROM pagos_prestamo
                    WHERE {self.LP.ID_PAGO_NOMINA.value}=%s
                """
                rows = self.db.get_data_list(q, (id_pago,), dictionary=True) or []
                for row in rows:
                    pid = int(row.get("id_prestamo") or 0)
                    if pid > 0:
                        ids.add(pid)
        except Exception:
            pass

        try:
            if self._table_exists("detalles_pagos_prestamo"):
                q = f"""
                    SELECT DISTINCT {E_DET.ID_PRESTAMO.value} AS id_prestamo
                    FROM detalles_pagos_prestamo
                    WHERE {E_DET.ID_PAGO.value}=%s
                """
                rows = self.db.get_data_list(q, (id_pago,), dictionary=True) or []
                for row in rows:
                    pid = int(row.get("id_prestamo") or 0)
                    if pid > 0:
                        ids.add(pid)
        except Exception:
            pass

        return sorted(ids)

    def _recalcular_saldo_y_estado_prestamo(self, id_prestamo: int) -> None:
        """
        Ajusta saldo/estado del préstamo tras eliminar pagos:
        - Si aún hay pagos_prestamo del préstamo, toma el último saldo_restante.
        - Si no hay pagos, restaura saldo al monto original.
        """
        if id_prestamo <= 0:
            return
        if not self._table_exists(self.P.TABLE_PRESTAMOS.value):
            return

        try:
            q_base = f"""
                SELECT {self.P.PRESTAMO_MONTO.value} AS monto_base
                FROM {self.P.TABLE_PRESTAMOS.value}
                WHERE {self.P.PRESTAMO_ID.value}=%s
                LIMIT 1
            """
            base_row = self.db.get_data(q_base, (id_prestamo,), dictionary=True) or {}
            monto_base = float(base_row.get("monto_base") or 0.0)
        except Exception:
            return

        saldo_nuevo = monto_base
        try:
            if self._table_exists("pagos_prestamo"):
                q_last = f"""
                    SELECT {self.LP.PAGO_SALDO_RESTANTE.value} AS saldo_restante
                    FROM pagos_prestamo
                    WHERE {self.LP.ID_PRESTAMO.value}=%s
                    ORDER BY {self.LP.PAGO_FECHA_REAL.value} DESC,
                             {self.LP.PAGO_FECHA_PAGO.value} DESC,
                             {self.LP.ID_PAGO_PRESTAMO.value} DESC
                    LIMIT 1
                """
                last_row = self.db.get_data(q_last, (id_prestamo,), dictionary=True) or {}
                if last_row and last_row.get("saldo_restante") is not None:
                    saldo_nuevo = float(last_row.get("saldo_restante") or 0.0)
        except Exception:
            pass

        saldo_nuevo = round(max(0.0, saldo_nuevo), 2)
        estado_nuevo = "terminado" if saldo_nuevo <= 0 else "pagando"
        fecha_cierre = datetime.today().strftime("%Y-%m-%d") if estado_nuevo == "terminado" else None

        try:
            q_upd = f"""
                UPDATE {self.P.TABLE_PRESTAMOS.value}
                SET {self.P.PRESTAMO_SALDO.value}=%s,
                    {self.P.PRESTAMO_ESTADO.value}=%s,
                    {self.P.PRESTAMO_FECHA_CIERRE.value}=%s
                WHERE {self.P.PRESTAMO_ID.value}=%s
            """
            self.db.run_query(q_upd, (saldo_nuevo, estado_nuevo, fecha_cierre, id_prestamo))
        except Exception:
            pass

    # ---------------------------------------------------------------------
    # Alias retrocompatible
    # ---------------------------------------------------------------------
    def get_all(self) -> Dict[str, Any]:
        """Alias retrocompatible."""
        return self.get_all_pagos()
