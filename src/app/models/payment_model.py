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
    Modelo de Pagos (Nómina)

    - Estructura con GRUPOS: cada corrida por rango [fecha_inicio, fecha_fin]
    genera/actualiza pagos con: grupo_pago, fecha_inicio, fecha_fin, estado_grupo.
    - Generación por rango o por empleado (estado 'pendiente').
    - Uso de borrador de descuentos (descuento_detalles): defaults IMSS=50 y Transporte=100,
    y clon automático del último pago CONFIRMADO del empleado.
    - Confirmación aplica: borrador -> descuentos (finales) + detalles de préstamos -> pagos_prestamo.
    - Lecturas: plano, agrupado por empleado, y agrupado por grupo_pago.
    """
    def __init__(self):
        self.db = DatabaseMysql()

        # Enums (solo strings; no crean tablas)
        self.E = E_PAYMENT
        self.D = E_DISCOUNT
        self.P = E_PRESTAMOS
        self.LP = E_PAGOS_PRESTAMO

        # ⚠️ NO instanciar modelos dependientes aún
        self.employee_model = None
        self.discount_model = None
        self.loan_model = None
        self.loan_payment_model = None
        self.detalles_desc_model = None

        # 1) Crear/verificar 'pagos' primero
        self._exists_table = self.check_table()

        # 2) Ahora sí: modelos que pueden referenciar 'pagos'
        #    (ya existe la tabla, así que sus FKs no fallan)
        self.employee_model = EmployesModel()
        self.discount_model = DiscountModel()
        self.loan_model = LoanModel()
        self.loan_payment_model = LoanPaymentModel()
        try:
            self.detalles_desc_model = DescuentoDetallesModel()
        except Exception:
            # si no existe este módulo en tu entorno, no rompas la app
            self.detalles_desc_model = None


    # ---------------------------------------------------------------------
    # Infra / Esquema
    # ---------------------------------------------------------------------
    def check_table(self) -> bool:
        """
        Garantiza la tabla `pagos` con todas las columnas requeridas por el sistema.
        Crea la tabla si no existe. Totalmente compatible con los modelos actuales.
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

                    -- Agrupación y metadatos de lotes de nómina
                    {self.E.GRUPO_PAGO.value} VARCHAR(100) DEFAULT NULL,
                    {self.E.FECHA_INICIO.value} DATE DEFAULT NULL,
                    {self.E.FECHA_FIN.value} DATE DEFAULT NULL,
                    {self.E.ESTADO_GRUPO.value} ENUM('abierto','cerrado') DEFAULT 'abierto',

                    -- Datos de cálculo de nómina
                    {self.E.FECHA_PAGO.value} DATE NOT NULL,
                    {self.E.TOTAL_HORAS_TRABAJADAS.value} DECIMAL(6,2) DEFAULT 0,
                    {self.E.MONTO_BASE.value} DECIMAL(10,2) NOT NULL DEFAULT 0,
                    {self.E.MONTO_TOTAL.value} DECIMAL(10,2) NOT NULL DEFAULT 0,
                    {self.D.MONTO_DESCUENTO.value} DECIMAL(10,2) DEFAULT 0,
                    {self.P.PRESTAMO_MONTO.value} DECIMAL(10,2) DEFAULT 0,
                    {self.E.SALDO.value} DECIMAL(10,2) DEFAULT 0,

                    -- Métodos de pago
                    {self.E.PAGO_DEPOSITO.value} DECIMAL(10,2) NOT NULL DEFAULT 0,
                    {self.E.PAGO_EFECTIVO.value} DECIMAL(10,2) NOT NULL DEFAULT 0,

                    -- Estado general del pago
                    {self.E.ESTADO.value} ENUM('pendiente','pagado','cancelado') DEFAULT 'pendiente',

                    -- Metadatos de auditoría
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                    -- Relación con empleados
                    FOREIGN KEY ({self.E.NUMERO_NOMINA.value})
                        REFERENCES empleados(numero_nomina)
                        ON DELETE CASCADE,

                    -- Índices de búsqueda y agrupación
                    INDEX idx_pagos_grupo ({self.E.GRUPO_PAGO.value}),
                    INDEX idx_pagos_fecha ({self.E.FECHA_PAGO.value}),
                    INDEX idx_pagos_estado ({self.E.ESTADO.value})
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {self.E.TABLE.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {self.E.TABLE.value} ya existe. Verificación completa.")
            return True

        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {self.E.TABLE.value}: {ex}")
            return False



    # ---------------------------------------------------------------------
    # Stored Procedure de horas (creación si no existe)
    # ---------------------------------------------------------------------
    def crear_sp_horas_trabajadas_para_pagos(self):
        """
        Crea (si no existe) el procedimiento almacenado para calcular horas trabajadas.
        Devuelve horas en DECIMAL(5,2). Es robusto: detecta si asistencias.tiempo_trabajo
        es TIME o DECIMAL y aplica la fórmula correcta en cada caso.
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
            if (result or {}).get("c", 0) == 0:
                print("⚠️ SP 'horas_trabajadas_para_pagos' no existe. Creando...")

                cursor = self.db.connection.cursor()
                cursor.execute("DROP PROCEDURE IF EXISTS horas_trabajadas_para_pagos")
                sp_sql = """
                CREATE PROCEDURE horas_trabajadas_para_pagos (
                    IN p_numero_nomina INT,
                    IN p_fecha_inicio DATE,
                    IN p_fecha_fin DATE
                )
                BEGIN
                    DECLARE v_dtype VARCHAR(32);

                    -- Detectar el tipo real de la columna asistencias.tiempo_trabajo
                    SELECT DATA_TYPE INTO v_dtype
                    FROM information_schema.columns
                    WHERE table_schema = DATABASE()
                    AND table_name = 'asistencias'
                    AND column_name = 'tiempo_trabajo'
                    LIMIT 1;

                    IF p_numero_nomina IS NOT NULL THEN
                        IF EXISTS (SELECT 1 FROM empleados WHERE numero_nomina = p_numero_nomina) THEN
                            IF v_dtype = 'time' THEN
                                -- Esquema antiguo: TIME -> convertir a horas
                                SELECT
                                    a.numero_nomina,
                                    e.nombre_completo,
                                    ROUND(SUM(TIME_TO_SEC(a.tiempo_trabajo)) / 3600, 2) AS total_horas_trabajadas
                                FROM asistencias a
                                JOIN empleados e ON a.numero_nomina = e.numero_nomina
                                WHERE a.numero_nomina = p_numero_nomina
                                AND a.fecha BETWEEN p_fecha_inicio AND p_fecha_fin
                                AND a.estado = 'completo'
                                GROUP BY a.numero_nomina, e.nombre_completo;
                            ELSE
                                -- Esquema nuevo: DECIMAL(5,2) en horas
                                SELECT
                                    a.numero_nomina,
                                    e.nombre_completo,
                                    ROUND(SUM(a.tiempo_trabajo), 2) AS total_horas_trabajadas
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
                                ROUND(SUM(TIME_TO_SEC(a.tiempo_trabajo)) / 3600, 2) AS total_horas_trabajadas
                            FROM asistencias a
                            JOIN empleados e ON a.numero_nomina = e.numero_nomina
                            WHERE a.fecha BETWEEN p_fecha_inicio AND p_fecha_fin
                            AND a.estado = 'completo'
                            GROUP BY a.numero_nomina, e.nombre_completo;
                        ELSE
                            SELECT
                                a.numero_nomina,
                                e.nombre_completo,
                                ROUND(SUM(a.tiempo_trabajo), 2) AS total_horas_trabajadas
                            FROM asistencias a
                            JOIN empleados e ON a.numero_nomina = e.numero_nomina
                            WHERE a.fecha BETWEEN p_fecha_inicio AND p_fecha_fin
                            AND a.estado = 'completo'
                            GROUP BY a.numero_nomina, e.nombre_completo;
                        END IF;
                    END IF;
                END
                """
                cursor.execute(sp_sql)
                self.db.connection.commit()
                cursor.close()
                print("✅ SP 'horas_trabajadas_para_pagos' creado correctamente.")
            else:
                print("✔️ SP 'horas_trabajadas_para_pagos' ya existe.")
        except Exception as ex:
            print(f"❌ Error al crear SP 'horas_trabajadas_para_pagos': {ex}")



    # ---------------------------------------------------------------------
    # Utilidades de lectura/cálculo
    # ---------------------------------------------------------------------
    def get_total_horas_trabajadas(
        self, fecha_inicio: str, fecha_fin: str, numero_nomina: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Obtiene las horas trabajadas entre fecha_inicio y fecha_fin,
        siempre en DECIMAL(5,2). Usa el SP que ya se adapta al tipo de columna.
        """
        try:
            # Asegura que el SP exista (por si migraste recientemente)
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
                            horas = float(row["total_horas_trabajadas"] or 0)
                            row["total_horas_trabajadas"] = round(horas, 2)
                        except Exception:
                            row["total_horas_trabajadas"] = 0.0
                    data.append(row)

            cursor.close()
            return {"status": "success", "data": data}
        except Exception as ex:
            print(f"❌ Error en get_total_horas_trabajadas: {ex}")
            return {"status": "error", "message": "No fue posible obtener horas."}


    def get_fechas_utilizadas(self) -> List[str]:
        """Fechas de pago ya usadas (cualquier estado)."""
        try:
            q = f"SELECT DISTINCT {self.E.FECHA_PAGO.value} AS f FROM {self.E.TABLE.value}"
            rows = self.db.get_data_list(q, dictionary=True) or []
            return [str(r["f"]) for r in rows if r and r.get("f")]
        except Exception:
            return []

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

    # ---------------------------------------------------------------------
    # Helpers internos (sueldo, horas, grupo, defaults)
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
        Prellena o actualiza el borrador de descuentos para un pago pendiente.
        - Defaults: IMSS=50, Transporte=100 (ambos aplicados).
        - Clona descuentos del último pago 'pagado' del empleado si existen.
        - Si no existe `detalles_desc_model`, no hace nada.
        Retorna dict con status y mensaje.
        """
        if not self.detalles_desc_model:
            return {"status": "warning", "message": "Módulo detalles_desc no disponible, se omitió prellenado."}

        # Defaults
        aplicado_imss, monto_imss = True, 50.0
        aplicado_transporte, monto_transporte = True, 100.0
        aplicado_extra, monto_extra, desc_extra = False, 0.0, None

        try:
            # Buscar último pago confirmado del empleado
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

            # Guardar en la tabla de borradores
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
    # Generación de pagos
    # ---------------------------------------------------------------------
# --- REEMPLAZO COMPLETO ---
    def generar_pagos_por_rango(self, fecha_inicio: str, fecha_fin: str) -> Dict[str, Any]:
        """
        Genera/actualiza pagos PENDIENTES por empleado para el rango [fecha_inicio, fecha_fin].
        Ahora: fecha_pago = HOY (día de generación), no fecha_fin.
        Deduplica por (numero_nomina, fecha_inicio, fecha_fin).
        """
        try:
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

                    # Buscar existentes por (fecha_inicio, fecha_fin) del empleado
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
                        # Conserva el último y borra duplicados si los hay
                        id_pago_target = int(existentes[-1]["id_pago"])
                        dup_ids = [int(x["id_pago"]) for x in existentes[:-1]]
                        if dup_ids:
                            self.db.run_query(
                                f"DELETE FROM detalles_pagos_prestamo WHERE {E_DET.ID_PAGO.value} IN ({', '.join(['%s']*len(dup_ids))})",
                                tuple(dup_ids),
                            )
                            self.db.run_query(
                                f"DELETE FROM {self.E.TABLE.value} WHERE {self.E.ID_PAGO_NOMINA.value} IN ({', '.join(['%s']*len(dup_ids))})",
                                tuple(dup_ids),
                            )
                            eliminados += len(dup_ids)

                        # Update a PENDIENTE con fecha_pago = hoy
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
                            self.E.SALDO.value: monto_base,
                            self.E.PAGO_DEPOSITO.value: 0.0,
                            self.E.PAGO_EFECTIVO.value: monto_base,
                            self.E.ESTADO.value: "pendiente",
                        })
                        actualizados += 1

                    else:
                        # Insert nuevo PENDIENTE con fecha_pago = hoy
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
                            ) VALUES (%s,%s,%s,%s,'abierto',%s,%s,%s,%s,0,0,%s,0,%s,'pendiente')
                        """
                        self.db.run_query(
                            ins_q,
                            (numero_nomina, grupo_token, fecha_inicio, fecha_fin, hoy,
                            horas_dec, monto_base, monto_base, monto_base, monto_base)
                        )
                        id_pago_target = int(self.db.get_last_insert_id())
                        generados += 1

                    # Prellenar borrador de descuentos
                    self._prefill_borrador_descuentos(id_pago_target, numero_nomina)

                except Exception:
                    continue

            msg = f"{generados} creados, {actualizados} actualizados, {eliminados} duplicados eliminados, {omitidos_pagados} omitidos (ya pagados), {sin_horas_sueldo} sin horas/sueldo."
            return {"status": "success", "message": msg}
        except Exception as ex:
            return {"status": "error", "message": f"Error al generar por rango: {ex}"}



    def registrar_pago_manual(self, numero_nomina: int) -> Dict[str, Any]:
        try:
            if not isinstance(numero_nomina, int) or numero_nomina <= 0:
                return {"status": "error", "message": "Número de nómina inválido"}
            today = datetime.now().strftime("%Y-%m-%d")
            if self.existe_pago_para_fecha(numero_nomina, today, incluir_pendientes=True):
                return {"status": "error", "message": "Ya existe un pago registrado para hoy"}
            # grupo unitario = mismo día
            return self.generar_pago_por_empleado(numero_nomina, today, today)
        except Exception as ex:
            return {"status": "error", "message": f"Error en pago manual: {ex}"}

# --- REEMPLAZO COMPLETO ---
    def generar_pago_por_empleado(self, numero_nomina: int, fecha_inicio: str, fecha_fin: str) -> Dict[str, Any]:
        """
        Genera un pago PENDIENTE para el empleado en el rango dado.
        Ahora: fecha_pago = HOY y se deduplica por (fecha_inicio, fecha_fin).
        """
        try:
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

            # ¿Existe ya ese rango?
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
                    self.E.SALDO.value: monto_base,
                    self.E.PAGO_DEPOSITO.value: 0.0,
                    self.E.PAGO_EFECTIVO.value: monto_base,
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
                    ) VALUES (%s,%s,%s,%s,'abierto',%s,%s,%s,%s,0,0,%s,0,%s,'pendiente')
                """
                self.db.run_query(
                    insert_q,
                    (numero_nomina, grupo_token, fecha_inicio, fecha_fin, hoy,
                    horas_dec, monto_base, monto_base, monto_base, monto_base)
                )
                id_pago_target = int(self.db.get_last_insert_id())

            self._prefill_borrador_descuentos(id_pago_target, numero_nomina)
            return {"status": "success", "message": f"Pago generado por ${monto_base:.2f}", "id_pago": id_pago_target}
        except Exception as ex:
            return {"status": "error", "message": f"Error en generar_pago_por_empleado: {ex}"}



    # ---------------------------------------------------------------------
    # Lectura (plano, por empleado y AGRUPADO)
    # ---------------------------------------------------------------------
    def get_all_pagos(self) -> Dict[str, Any]:
        try:
            q = f"""
                SELECT 
                    p.{self.E.ID_PAGO_NOMINA.value} AS id_pago_nomina,
                    p.{self.E.ID_PAGO_NOMINA.value} AS id_pago,          -- alias para la vista/helper
                    p.{self.E.NUMERO_NOMINA.value}   AS numero_nomina,
                    p.{self.E.NUMERO_NOMINA.value}   AS id_empleado,     -- alias para la vista/helper
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


    def get_pagos_por_empleado(self, numero_nomina: int) -> Dict[str, Any]:
        try:
            q = f"""
                SELECT 
                    p.{self.E.ID_PAGO_NOMINA.value} AS id_pago_nomina,
                    p.{self.E.ID_PAGO_NOMINA.value} AS id_pago,          -- alias
                    p.{self.E.NUMERO_NOMINA.value}   AS numero_nomina,
                    p.{self.E.NUMERO_NOMINA.value}   AS id_empleado,     -- alias
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
                WHERE p.{self.E.NUMERO_NOMINA.value}=%s
                ORDER BY p.{self.E.FECHA_PAGO.value} DESC, p.{self.E.ID_PAGO_NOMINA.value} DESC
            """
            rows = self.db.get_data_list(q, (numero_nomina,), dictionary=True) or []
            if not rows:
                emp = self.employee_model.get_by_numero_nomina(numero_nomina) or {}
                return {"status": "success", "data": {
                    "numero_nomina": numero_nomina,
                    "nombre_empleado": emp.get("nombre_completo", ""),
                    "sueldo_por_hora": float(emp.get("sueldo_por_hora", 0) or 0),
                    "pagos": []
                }}
            header = rows[0]
            return {"status": "success", "data": {
                "numero_nomina": numero_nomina,
                "nombre_empleado": header["nombre_completo"],
                "sueldo_por_hora": float(header.get("sueldo_por_hora", 0) or 0),
                "pagos": rows
            }}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener pagos por empleado: {ex}"}


    def get_agrupado_por_empleado(self) -> Dict[str, Any]:
        try:
            q = f"""
                SELECT 
                    p.{self.E.ID_PAGO_NOMINA.value} AS id_pago_nomina,
                    p.{self.E.ID_PAGO_NOMINA.value} AS id_pago,          -- alias
                    p.{self.E.NUMERO_NOMINA.value}   AS numero_nomina,
                    p.{self.E.NUMERO_NOMINA.value}   AS id_empleado,     -- alias
                    e.nombre_completo,
                    e.sueldo_por_hora,
                    p.{self.E.GRUPO_PAGO.value}      AS grupo_pago,
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
                ORDER BY e.numero_nomina, p.{self.E.FECHA_PAGO.value} DESC, p.{self.E.ID_PAGO_NOMINA.value} DESC
            """
            rows = self.db.get_data_list(q, dictionary=True) or []
            grupos: Dict[int, Dict[str, Any]] = {}
            for r in rows:
                num = r["numero_nomina"]
                if num not in grupos:
                    grupos[num] = {
                        "numero_nomina": num,
                        "nombre_empleado": r["nombre_completo"],
                        "sueldo_por_hora": float(r.get("sueldo_por_hora", 0) or 0),
                        "pagos": []
                    }
                grupos[num]["pagos"].append(r)
            return {"status": "success", "data": grupos}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener pagos agrupados: {ex}"}


    # ---------------------- Agrupación por grupo_pago ---------------------
    def get_grupos_pagos(self) -> List[Dict[str, Any]]:
        """
        Lista de grupos con métricas básicas para el header de cada tabla (sortable independiente).
        """
        try:
            q = f"""
                SELECT {self.E.GRUPO_PAGO.value} AS grupo_pago,
                    {self.E.FECHA_INICIO.value} AS fecha_inicio,
                    {self.E.FECHA_FIN.value} AS fecha_fin,
                    {self.E.ESTADO_GRUPO.value} AS estado_grupo,
                    COUNT(*) AS total_pagos,
                    SUM(CASE WHEN {self.E.ESTADO.value}='pagado' THEN 1 ELSE 0 END) AS pagados,
                    SUM({self.E.MONTO_TOTAL.value}) AS suma_montos
                FROM {self.E.TABLE.value}
                GROUP BY {self.E.GRUPO_PAGO.value}, {self.E.FECHA_INICIO.value}, {self.E.FECHA_FIN.value}, {self.E.ESTADO_GRUPO.value}
                ORDER BY {self.E.FECHA_INICIO.value} DESC, {self.E.FECHA_FIN.value} DESC
            """
            return self.db.get_data_list(q, dictionary=True) or []
        except Exception:
            return []


    def get_pagos_por_grupo(self, grupo_pago: str) -> List[Dict[str, Any]]:
        try:
            q = f"""
                SELECT 
                    p.{self.E.ID_PAGO_NOMINA.value} AS id_pago_nomina,
                    p.{self.E.ID_PAGO_NOMINA.value} AS id_pago,          -- alias
                    p.{self.E.NUMERO_NOMINA.value}   AS numero_nomina,
                    p.{self.E.NUMERO_NOMINA.value}   AS id_empleado,     -- alias
                    e.nombre_completo,
                    e.sueldo_por_hora,
                    p.{self.E.FECHA_PAGO.value}      AS fecha_pago,
                    p.{self.E.TOTAL_HORAS_TRABAJADAS.value} AS horas,
                    p.{self.E.MONTO_BASE.value}      AS monto_base,
                    p.{self.E.MONTO_TOTAL.value}     AS monto_total,
                    p.{self.D.MONTO_DESCUENTO.value} AS descuentos,
                    p.{self.P.PRESTAMO_MONTO.value}  AS prestamos,
                    p.{self.E.SALDO.value}           AS saldo,
                    p.{self.E.PAGO_DEPOSITO.value}   AS deposito,
                    p.{self.E.PAGO_EFECTIVO.value}   AS efectivo,
                    p.{self.E.ESTADO.value}          AS estado,
                    p.{self.E.GRUPO_PAGO.value}      AS grupo_pago
                FROM {self.E.TABLE.value} p
                JOIN empleados e ON p.{self.E.NUMERO_NOMINA.value} = e.numero_nomina
                WHERE p.{self.E.GRUPO_PAGO.value}=%s
                ORDER BY p.{self.E.FECHA_PAGO.value} DESC, p.{self.E.ID_PAGO_NOMINA.value} DESC
            """
            return self.db.get_data_list(q, (grupo_pago,), dictionary=True) or []
        except Exception:
            return []


    def cerrar_grupo(self, grupo_pago: str) -> Dict[str, Any]:
        try:
            q = f"UPDATE {self.E.TABLE.value} SET {self.E.ESTADO_GRUPO.value}='cerrado' WHERE {self.E.GRUPO_PAGO.value}=%s"
            self.db.run_query(q, (grupo_pago,))
            return {"status": "success"}
        except Exception as ex:
            return {"status": "error", "message": str(ex)}

    def reabrir_grupo(self, grupo_pago: str) -> Dict[str, Any]:
        try:
            q = f"UPDATE {self.E.TABLE.value} SET {self.E.ESTADO_GRUPO.value}='abierto' WHERE {self.E.GRUPO_PAGO.value}=%s"
            self.db.run_query(q, (grupo_pago,))
            return {"status": "success"}
        except Exception as ex:
            return {"status": "error", "message": str(ex)}

    # ---------------------------------------------------------------------
    # Edición / Confirmación / Eliminación
    # ---------------------------------------------------------------------


    def update_pago(self, id_pago: int, cambios: Dict[str, Any]) -> bool:
        """
        Actualiza campos permitidos. Si se cambia el depósito o el monto total/base,
        se recalculan automáticamente pago_efectivo y saldo para mantener consistencia.
        """
        if not isinstance(id_pago, int) or id_pago <= 0:
            return False
        if not cambios:
            return True

        # Campos permitidos
        permitidas = {
            self.E.GRUPO_PAGO.value, self.E.FECHA_INICIO.value, self.E.FECHA_FIN.value, self.E.ESTADO_GRUPO.value,
            self.E.FECHA_PAGO.value, self.E.TOTAL_HORAS_TRABAJADAS.value, self.E.MONTO_BASE.value,
            self.E.MONTO_TOTAL.value, self.D.MONTO_DESCUENTO.value, self.P.PRESTAMO_MONTO.value,
            self.E.SALDO.value, self.E.PAGO_DEPOSITO.value, self.E.PAGO_EFECTIVO.value, self.E.ESTADO.value,
        }

        # Traer el registro actual para tener totales vigentes
        cur_rs = self.get_by_id(id_pago)
        if cur_rs.get("status") != "success":
            return False
        cur = cur_rs["data"]

        # Normalizar floats
        def _f(x): 
            try: return float(x)
            except Exception: return 0.0

        # Si se manda estado 'pendiente' + monto_base, forzamos total=base
        estado_nuevo = str(cambios.get(self.E.ESTADO.value, "")).lower()
        if estado_nuevo == "pendiente" and self.E.MONTO_BASE.value in cambios:
            cambios[self.E.MONTO_TOTAL.value] = _f(cambios[self.E.MONTO_BASE.value])

        # Determinar total contra el que vamos a cuadrar depósito/efectivo/saldo
        total = _f(
            cambios.get(self.E.MONTO_TOTAL.value,
            cambios.get(self.E.MONTO_BASE.value,
            cur.get(self.E.MONTO_TOTAL.value, cur.get(self.E.MONTO_BASE.value, 0))))
        )

        # Si llega un depósito pero NO llega efectivo, lo calculamos
        if self.E.PAGO_DEPOSITO.value in cambios and self.E.PAGO_EFECTIVO.value not in cambios:
            dep = max(0.0, _f(cambios[self.E.PAGO_DEPOSITO.value]))
            if dep > total:
                dep = total
                cambios[self.E.PAGO_DEPOSITO.value] = dep
            efec = max(0.0, round(total - dep, 2))
            cambios[self.E.PAGO_EFECTIVO.value] = efec
            # saldo contable = total - (dep + efec)
            cambios[self.E.SALDO.value] = max(0.0, round(total - dep - efec, 2))

        # Si llega efectivo pero NO depósito, también cuadramos
        if self.E.PAGO_EFECTIVO.value in cambios and self.E.PAGO_DEPOSITO.value not in cambios:
            efec = max(0.0, _f(cambios[self.E.PAGO_EFECTIVO.value]))
            if efec > total:
                efec = total
                cambios[self.E.PAGO_EFECTIVO.value] = efec
            dep = max(0.0, round(total - efec, 2))
            cambios[self.E.PAGO_DEPOSITO.value] = dep
            cambios[self.E.SALDO.value] = max(0.0, round(total - dep - efec, 2))

        # Si llega total/base y no llega ni depósito ni efectivo, garantizamos consistencia básica en pendientes
        if (self.E.MONTO_TOTAL.value in cambios or self.E.MONTO_BASE.value in cambios) and \
        self.E.PAGO_DEPOSITO.value not in cambios and self.E.PAGO_EFECTIVO.value not in cambios:
            # Mantener lo que ya tenía el registro, pero acotar a nuevo total
            dep_actual = _f(cur.get(self.E.PAGO_DEPOSITO.value))
            efec_actual = _f(cur.get(self.E.PAGO_EFECTIVO.value))
            if dep_actual + efec_actual > total:
                dep_actual = min(dep_actual, total)
                efec_actual = max(0.0, round(total - dep_actual, 2))
            cambios[self.E.PAGO_DEPOSITO.value] = dep_actual
            cambios[self.E.PAGO_EFECTIVO.value] = efec_actual
            cambios[self.E.SALDO.value] = max(0.0, round(total - dep_actual - efec_actual, 2))

        # Construir UPDATE
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
            self.db.run_query(q, tuple(vals))
            return True
        except Exception as ex:
            print(f"❌ Error en update_pago: {ex}")
            return False


        # --- REEMPLAZO COMPLETO ---
    def confirmar_pago(self, id_pago: int, fecha_real_pago: Optional[str] = None) -> Dict[str, Any]:
        """
        Confirma el pago y fija fecha_pago.
        ⚠️ Si NO se especifica `fecha_real_pago`, se respeta la `fecha_pago` que ya trae el registro,
        en lugar de forzar 'hoy'. Así preservamos el “grupo por fecha” definido antes.
        """
        try:
            pago = self.get_by_id(id_pago)
            if pago.get("status") != "success":
                return pago
            p = pago["data"]
            if str(p.get(self.E.ESTADO.value, "")).lower() == "pagado":
                return {"status": "success", "message": "El pago ya estaba confirmado."}

            numero_nomina = int(p.get(self.E.NUMERO_NOMINA.value))
            fecha_guardada = str(p.get(self.E.FECHA_PAGO.value))  # fecha elegida al crear el grupo
            # 👉 prioridad: parámetro explícito > fecha_guardada > HOY
            fecha_real = fecha_real_pago or (fecha_guardada if fecha_guardada else self._today_str())

            # 1) aplicar/limpiar borrador de descuentos
            try:
                if self.detalles_desc_model is not None:
                    self.detalles_desc_model.aplicar_a_descuentos_y_limpiar(id_pago, self.discount_model)
            except Exception as _ex:
                print(f"⚠️ No se pudo aplicar/limpiar borrador de descuentos: {_ex}")

            # 2) aplicar detalles préstamo -> pagos_prestamo
            self._aplicar_detalles_prestamo_de_pago(
                id_pago_nomina=id_pago,
                fecha_pago=fecha_guardada,
                fecha_real=fecha_real
            )

            # 3) recalcular totales reales (descuentos + préstamos)
            try:
                total_desc = float(self.discount_model.get_total_descuentos_por_pago(id_pago) or 0.0)
            except Exception:
                total_desc = 0.0

            total_prest = self._get_prestamos_totales_para_pago(
                id_pago=id_pago, numero_nomina=numero_nomina, fecha_fin=fecha_guardada
            )
            monto_base = float(p.get(self.E.MONTO_BASE.value) or 0)
            nuevo_total = max(0.0, round(monto_base - total_desc - total_prest, 2))

            self.update_pago(id_pago, {
                self.E.FECHA_PAGO.value: fecha_real,
                self.E.MONTO_TOTAL.value: nuevo_total,
                self.D.MONTO_DESCUENTO.value: total_desc,
                self.P.PRESTAMO_MONTO.value: total_prest,
                self.E.PAGO_EFECTIVO.value: max(0.0, nuevo_total - float(p.get(self.E.PAGO_DEPOSITO.value) or 0)),
                self.E.ESTADO.value: "pagado",
            })
            return {"status": "success", "message": "Pago confirmado correctamente."}
        except Exception as ex:
            return {"status": "error", "message": f"Error al confirmar pago: {ex}"}


    def crear_grupo_pagado(self, fecha: str) -> Dict[str, Any]:
        """
        Reemplazo SEGURO de 'crear_grupo_pagado':
        - NO inserta filas en `pagos`.
        - Busca todos los pagos PENDIENTES con fecha_pago = `fecha`.
        - Confirma cada pago (aplica borrador de descuentos y detalles de préstamo).
        - Cierra el grupo (`estado_grupo='cerrado'`) para esa fecha.
        - Devuelve conteo de confirmados y errores.

        Requisitos de esquema:
        - pagos.estado ENUM('pendiente','pagado','cancelado')
        - pagos.fecha_pago DATE
        """
        try:
            # Validación simple de fecha (YYYY-MM-DD)
            try:
                datetime.strptime(fecha, "%Y-%m-%d")
            except Exception:
                return {"status": "error", "message": "Fecha no válida. Formato esperado YYYY-MM-DD."}

            # 1) Tomar IDs de pagos pendientes del día indicado
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

            # 2) Confirmar cada pago (esto aplica borrador de descuentos y préstamos)
            confirmados, errores = 0, 0
            fallos: list[dict] = []
            for r in filas:
                pid = int(r["id"])
                res = self.confirmar_pago(pid, fecha_real_pago=fecha)
                if res.get("status") == "success":
                    confirmados += 1
                else:
                    errores += 1
                    fallos.append({"id_pago": pid, "error": res.get("message", "Error desconocido")})

            # 3) Cerrar grupo (solo marca 'cerrado' a los que tengan esa fecha)
            q_close = f"""
                UPDATE {self.E.TABLE.value}
                SET {self.E.ESTADO_GRUPO.value}='cerrado'
                WHERE {self.E.FECHA_PAGO.value}=%s
            """
            self.db.run_query(q_close, (fecha,))

            out = {
                "status": "success",
                "message": f"Grupo {fecha}: {confirmados} pagos confirmados, {errores} con error.",
                "detalle_errores": fallos
            }
            return out

        except Exception as ex:
            return {"status": "error", "message": f"Error al confirmar/cerrar grupo por fecha: {ex}"}


    def eliminar_pago(self, id_pago: int) -> Dict[str, Any]:
        """
        Elimina un pago si no está confirmado.
        Limpia detalles de préstamos y borrador de descuentos asociados.
        """
        try:
            pago = self.get_by_id(id_pago)
            if pago.get("status") != "success":
                return pago
            p = pago["data"]
            if str(p.get(self.E.ESTADO.value, "")).lower() == "pagado":
                return {"status": "error", "message": "No se puede eliminar un pago ya confirmado."}

            # borra detalles de préstamo pendientes
            dq = f"DELETE FROM detalles_pagos_prestamo WHERE {E_DET.ID_PAGO.value}=%s"
            self.db.run_query(dq, (id_pago,))

            # borra borrador de descuentos (si existe)
            try:
                self.detalles_desc_model.eliminar_por_id_pago(id_pago)
            except Exception:
                pass

            # borra pago
            q = f"DELETE FROM {self.E.TABLE.value} WHERE {self.E.ID_PAGO_NOMINA.value}=%s"
            self.db.run_query(q, (id_pago,))
            return {"status": "success", "message": "Pago eliminado correctamente."}
        except Exception as ex:
            return {"status": "error", "message": f"Error al eliminar pago: {ex}"}

    # ---------------------------------------------------------------------
    # Lecturas auxiliares / básicos
    # ---------------------------------------------------------------------
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
    # Internos: préstamos confirmados + pendientes
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
    # Persistencia atómica auxiliar (utilizada por UI legacy)
    # ---------------------------------------------------------------------
    def update_pago_completo(
        self,
        *,
        id_pago: int,
        descuentos: dict | None = None,
        estado: str | None = None,
        deposito: float | None = None,
    ) -> dict:
        """
        Persistencia compacta:
        - Si llega `descuentos` (legacy), guarda UNA fila agregada en `descuentos`
        y recalcula MONTO_TOTAL = MONTO_BASE - total_desc - prestamos.
        - Para `deposito`, delega en update_pago (que recalcula efectivo/saldo).
        - Permite actualizar `estado`.
        """
        def _f(v):
            try:
                return float(v or 0)
            except Exception:
                return 0.0

        try:
            # Traer pago para obtener numero_nomina y datos base
            cur_rs = self.get_by_id(id_pago)
            if cur_rs.get("status") != "success":
                return {"status": "error", "message": "Pago no encontrado para cargar descuentos."}
            cur = cur_rs["data"]

            num_nomina = int(cur.get(self.E.NUMERO_NOMINA.value))
            if num_nomina <= 0:
                return {"status": "error", "message": "El pago no tiene numero_nomina válido."}

            cambios = {}

            # 1) Descuentos legacy (opcional) -> UNA fila agregada 'totales'
            if descuentos is not None:
                imss = _f(descuentos.get("monto_imss", descuentos.get("imss")))
                trans = _f(descuentos.get("monto_transporte", descuentos.get("transporte")))
                extra = _f(descuentos.get("monto_extra", descuentos.get("extra")))
                total_desc = round(imss + trans + extra, 2)

                # Limpia descuentos previos asociados a este pago
                del_q = "DELETE FROM descuentos WHERE id_pago_nomina=%s"
                self.db.run_query(del_q, (id_pago,))

                # Inserta fila agregada CUMPLIENDO el esquema real
                ins_q = """
                    INSERT INTO descuentos
                    (numero_nomina, id_pago_nomina, tipo_descuento, descripcion, monto_descuento, fecha_aplicacion)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_DATE())
                """
                self.db.run_query(ins_q, (num_nomina, id_pago, 'totales', 'carga_legacy', total_desc))

                # Recalcular totales del pago
                base = _f(cur.get(self.E.MONTO_BASE.value))
                prest = self._get_prestamos_totales_para_pago(
                    id_pago=id_pago,
                    numero_nomina=num_nomina,
                    fecha_fin=str(cur.get(self.E.FECHA_PAGO.value)),
                )
                nuevo_total = max(0.0, round(base - total_desc - prest, 2))
                cambios[self.E.MONTO_TOTAL.value] = nuevo_total
                cambios[self.D.MONTO_DESCUENTO.value] = total_desc
                cambios[self.P.PRESTAMO_MONTO.value] = prest

            # 2) Estado (opcional)
            if estado is not None:
                cambios[self.E.ESTADO.value] = estado

            # 3) Depósito (opcional) -> que lo cuadre update_pago
            if deposito is not None:
                cambios[self.E.PAGO_DEPOSITO.value] = _f(deposito)

            if not cambios:
                return {"status": "success", "message": "Sin cambios."}

            ok = self.update_pago(id_pago, cambios)
            if not ok:
                return {"status": "error", "message": "No se pudo guardar los montos en DB."}

            return {"status": "success", "message": "Pago actualizado correctamente."}
        except Exception as ex:
            return {"status": "error", "message": f"Error al actualizar pago: {ex}"}


    @staticmethod
    def _today_str() -> str:
        return datetime.now().strftime("%Y-%m-%d")


    # --- NUEVO (opcional pero útil) ---
    def get_fechas_utilizadas_pagadas(self) -> List[str]:
        """Fechas de pago ya usadas SOLO por pagos 'pagado'."""
        try:
            q = f"SELECT DISTINCT {self.E.FECHA_PAGO.value} AS f FROM {self.E.TABLE.value} WHERE {self.E.ESTADO.value}='pagado'"
            rows = self.db.get_data_list(q, dictionary=True) or []
            return [str(r["f"]) for r in rows if r and r.get("f")]
        except Exception:
            return []

    # ---------------------- Grupos por FECHA (confirmados) ----------------------
    def get_fechas_pagadas(self) -> list[str]:
        """Fechas (YYYY-MM-DD) que ya tienen pagos CONFIRMADOS."""
        try:
            q = f"SELECT DISTINCT {self.E.FECHA_PAGO.value} AS f FROM {self.E.TABLE.value} WHERE {self.E.ESTADO.value}='pagado'"
            rows = self.db.get_data_list(q, dictionary=True) or []
            return [str(r["f"]) for r in rows if r and r.get("f")]
        except Exception:
            return []

    def get_fechas_pendientes(self) -> list[str]:
        """Fechas (YYYY-MM-DD) que tienen pagos PENDIENTES."""
        try:
            q = f"SELECT DISTINCT {self.E.FECHA_PAGO.value} AS f FROM {self.E.TABLE.value} WHERE {self.E.ESTADO.value}='pendiente'"
            rows = self.db.get_data_list(q, dictionary=True) or []
            return [str(r["f"]) for r in rows if r and r.get("f")]
        except Exception:
            return []

    def crear_grupo_pagado(self, fecha: str) -> dict:
        """
        Define una FECHA de agrupación para futuros 'pagados'.
        - No requiere que existan pendientes con esa fecha.
        - Re-fecha los pagos PENDIENTES de grupos 'abiertos' para que usen esa fecha.
        - Si ya hay PAGADOS con esa fecha, no permite crear (ya existe el grupo real).
        """
        try:
            # normaliza/valida formato
            try:
                _ = datetime.strptime(fecha, "%Y-%m-%d")
            except Exception:
                return {"status": "error", "message": "Formato de fecha inválido (usa YYYY-MM-DD)."}

            # si ya hay confirmados con esa fecha -> grupo real existente
            if fecha in set(self.get_fechas_pagadas()):
                return {"status": "error", "message": f"Ya existen pagos 'pagados' con fecha_pago = {fecha}."}

            # si ya hay PENDIENTES con esa fecha, listo
            if fecha in set(self.get_fechas_pendientes()):
                return {"status": "success", "message": "Grupo creado (ya había pendientes en esa fecha)."}

            # estrategia: llevar TODOS los pendientes de grupos abiertos a esa fecha
            q = f"""
                UPDATE {self.E.TABLE.value}
                SET {self.E.FECHA_PAGO.value}=%s
                WHERE {self.E.ESTADO.value}='pendiente' AND {self.E.ESTADO_GRUPO.value}='abierto'
            """
            self.db.run_query(q, (fecha,))
            return {"status": "success", "message": f"Grupo creado. Pendientes re-fechados a {fecha}."}
        except Exception as ex:
            return {"status": "error", "message": f"No fue posible crear el grupo: {ex}"}

    def eliminar_grupo_por_fecha(self, fecha: str) -> dict:
        """
        Elimina un 'grupo por fecha' para pagos NO confirmados:
        - Si hay PAGADOS con esa fecha -> se rechaza (seguro).
        - Para PENDIENTES con esa fecha, los re-fecha a HOY.
        """
        try:
            try:
                _ = datetime.strptime(fecha, "%Y-%m-%d")
            except Exception:
                return {"status": "error", "message": "Formato de fecha inválido (usa YYYY-MM-DD)."}

            # si hay confirmados con esa fecha, no se puede “eliminar” el grupo
            q_chk = f"""
                SELECT COUNT(*) AS c
                FROM {self.E.TABLE.value}
                WHERE {self.E.ESTADO.value}='pagado' AND {self.E.FECHA_PAGO.value}=%s
            """
            r = self.db.get_data(q_chk, (fecha,), dictionary=True) or {}
            if int(r.get("c", 0)) > 0:
                return {"status": "error", "message": "No se puede eliminar: ya hay pagos 'pagados' en esa fecha."}

            hoy = self._today_str()
            q_up = f"""
                UPDATE {self.E.TABLE.value}
                SET {self.E.FECHA_PAGO.value}=%s
                WHERE {self.E.ESTADO.value}='pendiente' AND {self.E.FECHA_PAGO.value}=%s
            """
            self.db.run_query(q_up, (hoy, fecha))
            return {"status": "success", "message": "Grupo eliminado para pendientes (re-fechados a hoy)."}
        except Exception as ex:
            return {"status": "error", "message": f"No fue posible eliminar el grupo: {ex}"}
