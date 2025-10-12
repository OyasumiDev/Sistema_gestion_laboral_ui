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

        # 1) Crear/verificar 'pagos' primero (FKs dependerán de esto)
        self._exists_table = self.check_table()

        # 2) Asegurar tabla de grupos manuales (vacíos) por FECHA
        self._ensure_grupos_table()

        # 3) Ahora sí: modelos que pueden referenciar 'pagos'
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
        - fecha_pago = HOY (día de generación).
        - Deduplica por (numero_nomina, fecha_inicio, fecha_fin).
        - Inserta pendientes con deposito=0, efectivo=0 y saldo = monto_total.
        - Al actualizar existentes, NO pisa deposito/efectivo; deja que update_pago recalcule saldo.
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
                                f"DELETE FROM detalles_pagos_prestamo WHERE id_pago_nomina IN ({', '.join(['%s']*len(dup_ids))})",
                                tuple(dup_ids),
                            )
                            self.db.run_query(
                                f"DELETE FROM {self.E.TABLE.value} WHERE {self.E.ID_PAGO_NOMINA.value} IN ({', '.join(['%s']*len(dup_ids))})",
                                tuple(dup_ids),
                            )
                            eliminados += len(dup_ids)

                        # UPDATE PENDIENTE con nuevos totales — NO pisar depósito/efectivo
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
                            # 👇 No mandamos SALDO/DEPÓSITO/EFECTIVO para preservar abonos y que update_pago recalcule SALDO.
                        })
                        actualizados += 1

                    else:
                        # INSERT nuevo PENDIENTE: deposito=0, efectivo=0, saldo = monto_total
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
        - fecha_pago = HOY
        - Si existe pendiente del mismo rango: actualiza totales SIN pisar depósito/efectivo (update_pago recalcula SALDO).
        - Si no existe: crea con deposito=0, efectivo=0, saldo = monto_total.
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
                    self.E.ESTADO.value: "pendiente",
                    # 👇 No mandamos SALDO/DEPÓSITO/EFECTIVO → se preservan y se recalcula SALDO.
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


    def get_grupos_pagos(self) -> List[Dict[str, Any]]:
        """
        Lista de grupos 'pagado' por FECHA para header:
        - Fuente 'manual': tabla grupos_pagos (grupos VACÍOS creados por el usuario).
        - Fuente 'auto'  : fechas con pagos 'pagado' ya confirmados.
        Nota: 'grupo_pago' aquí es una etiqueta visual; para los manuales se muestra 'FECHA:YYYY-MM-DD'.
        """
        try:
            q = f"""
            SELECT
                DATE_FORMAT(g.fecha, 'FECHA:%Y-%m-%d') AS grupo_pago,
                NULL AS fecha_inicio,
                NULL AS fecha_fin,
                g.estado_grupo AS estado_grupo,
                0 AS total_pagos,
                0 AS pagados,
                0 AS suma_montos,
                'manual' AS fuente,
                g.fecha AS fecha_orden
            FROM grupos_pagos g
            WHERE g.categoria='pagado'

            UNION ALL

            SELECT
                DATE_FORMAT(p.{self.E.FECHA_PAGO.value}, 'FECHA:%Y-%m-%d') AS grupo_pago,
                NULL AS fecha_inicio,
                NULL AS fecha_fin,
                'cerrado' AS estado_grupo,
                COUNT(*) AS total_pagos,
                COUNT(*) AS pagados,
                IFNULL(SUM(p.{self.E.MONTO_TOTAL.value}), 0) AS suma_montos,
                'auto' AS fuente,
                p.{self.E.FECHA_PAGO.value} AS fecha_orden
            FROM {self.E.TABLE.value} p
            WHERE p.{self.E.ESTADO.value}='pagado' AND p.{self.E.FECHA_PAGO.value} IS NOT NULL
            GROUP BY p.{self.E.FECHA_PAGO.value}

            ORDER BY fecha_orden DESC;
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


    def cerrar_grupo(self, fecha_o_token: str) -> Dict[str, Any]:
        """
        Cierra el grupo manual por FECHA (no toca pagos).
        Acepta 'FECHA:YYYY-MM-DD' o 'YYYY-MM-DD'.
        """
        try:
            fecha = str(fecha_o_token).replace("FECHA:", "")
            datetime.strptime(fecha, "%Y-%m-%d")  # valida
            q = "UPDATE grupos_pagos SET estado_grupo='cerrado' WHERE fecha=%s AND categoria='pagado'"
            self.db.run_query(q, (fecha,))
            return {"status": "success"}
        except Exception as ex:
            return {"status": "error", "message": str(ex)}

    def reabrir_grupo(self, fecha_o_token: str) -> Dict[str, Any]:
        """
        Reabre el grupo manual por FECHA (no toca pagos).
        Acepta 'FECHA:YYYY-MM-DD' o 'YYYY-MM-DD'.
        """
        try:
            fecha = str(fecha_o_token).replace("FECHA:", "")
            datetime.strptime(fecha, "%Y-%m-%d")  # valida
            q = "UPDATE grupos_pagos SET estado_grupo='abierto' WHERE fecha=%s AND categoria='pagado'"
            self.db.run_query(q, (fecha,))
            return {"status": "success"}
        except Exception as ex:
            return {"status": "error", "message": str(ex)}


    # ---------------------------------------------------------------------
    # Edición / Confirmación / Eliminación
    # ---------------------------------------------------------------------


    def update_pago(self, id_pago: int, cambios: Dict[str, Any]) -> bool:
        """
        Actualiza campos permitidos.
        NUEVO: si sólo llega depósito (o sólo efectivo), NO forzar complemento.
        Se conserva el otro valor y se recalcula SALDO = total - (dep + efec).
        Si la suma se pasa del total, se acota el no enviado.
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

        def _f(x):
            try: return float(x)
            except Exception: return 0.0

        # Si se manda estado 'pendiente' + monto_base, forzamos total=base
        estado_nuevo = str(cambios.get(self.E.ESTADO.value, "")).lower()
        if estado_nuevo == "pendiente" and self.E.MONTO_BASE.value in cambios:
            cambios[self.E.MONTO_TOTAL.value] = _f(cambios[self.E.MONTO_BASE.value])

        # Total contra el que se cuadrará
        total = _f(
            cambios.get(self.E.MONTO_TOTAL.value,
            cambios.get(self.E.MONTO_BASE.value,
            cur.get(self.E.MONTO_TOTAL.value, cur.get(self.E.MONTO_BASE.value, 0))))
        )

        dep_cur  = _f(cur.get(self.E.PAGO_DEPOSITO.value))
        efec_cur = _f(cur.get(self.E.PAGO_EFECTIVO.value))

        dep_in  = self.E.PAGO_DEPOSITO.value in cambios
        efec_in = self.E.PAGO_EFECTIVO.value in cambios

        dep_new  = _f(cambios.get(self.E.PAGO_DEPOSITO.value, dep_cur))
        efec_new = _f(cambios.get(self.E.PAGO_EFECTIVO.value, efec_cur))

        # Acotar individuales
        dep_new  = max(0.0, min(dep_new, total))
        efec_new = max(0.0, min(efec_new, total))

        if dep_in and not efec_in:
            # NO forzar complemento; conservar efectivo actual
            efec_new = efec_cur
            # Si la suma excede el total, acotar el NO enviado (efectivo)
            if dep_new + efec_new > total:
                efec_new = max(0.0, round(total - dep_new, 2))
                cambios[self.E.PAGO_EFECTIVO.value] = efec_new

        elif efec_in and not dep_in:
            # Conservar depósito actual; si se pasa, acotar depósito
            dep_new = dep_cur
            if dep_new + efec_new > total:
                dep_new = max(0.0, round(total - efec_new, 2))
                cambios[self.E.PAGO_DEPOSITO.value] = dep_new

        else:
            # Si llegan ambos y la suma excede, acotar efectivo
            if dep_new + efec_new > total:
                efec_new = max(0.0, round(total - dep_new, 2))
                cambios[self.E.PAGO_EFECTIVO.value] = efec_new

        saldo_new = max(0.0, round(total - dep_new - efec_new, 2))
        cambios[self.E.SALDO.value] = saldo_new

        # Escribir explícitamente los valores finales si fueron enviados o ajustados
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
            self.db.run_query(q, tuple(vals))
            return True
        except Exception as ex:
            print(f"❌ Error en update_pago: {ex}")
            return False


    def confirmar_pago(self, id_pago: int, fecha_real_pago: Optional[str] = None) -> Dict[str, Any]:
        """
        Confirma el pago fijando fecha_pago y totales sin 'barrer' el saldo.
        - Respeta el depósito/efectivo existentes del pendiente.
        - update_pago recalcula saldo = total - (depósito + efectivo).
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

            # 3) recomputar totales (descuentos + préstamos)
            try:
                total_desc = float(self.discount_model.get_total_descuentos_por_pago(id_pago) or 0.0)
            except Exception:
                total_desc = 0.0

            total_prest = self._get_prestamos_totales_para_pago(
                id_pago=id_pago, numero_nomina=numero_nomina, fecha_fin=fecha_guardada
            )
            monto_base = float(p.get(self.E.MONTO_BASE.value) or 0)
            nuevo_total = max(0.0, round(monto_base - total_desc - total_prest, 2))

            # ⚠️ Clave: NO mandar 'pago_efectivo' aquí.
            # Deja depósito/efectivo como están; update_pago recalcula 'saldo'.
            cambios = {
                self.E.FECHA_PAGO.value: fecha_real,
                self.E.MONTO_TOTAL.value: nuevo_total,
                self.D.MONTO_DESCUENTO.value: total_desc,
                self.P.PRESTAMO_MONTO.value: total_prest,
                self.E.ESTADO.value: "pagado",
            }
            ok = self.update_pago(id_pago, cambios)
            if not ok:
                return {"status": "error", "message": "No se pudo confirmar el pago en DB."}

            return {"status": "success", "message": "Pago confirmado correctamente (saldo respetado)."}

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


    # --- reimplementa eliminar_pago con chequeo de existencia de tablas ---
    def eliminar_pago(self, id_pago: int, force: bool = False) -> dict:
        """
        Elimina un pago. Si el pago está 'pagado' requiere force=True.
        Limpia dependencias reales del esquema:
        - detalles_pagos_prestamo (borrador)
        - pagos_prestamo (confirmados)  [solo si existe]
        - descuentos (finales)          [solo si existe]
        - borrador de descuentos via modelo (si existe)
        Todo es 'safe': no se intenta borrar en tablas inexistentes.
        """
        try:
            r = self.get_by_id(id_pago)
            if r.get("status") != "success":
                return {"status": "error", "message": "Pago no encontrado."}
            row = r["data"]
            estado = str(row.get(self.E.ESTADO.value) or "").lower()
            if estado == "pagado" and not force:
                return {"status": "error", "message": "Pago confirmado: usa force=True para eliminarlo."}

            # columnas/tabla principales
            pagos_tab = self.E.TABLE.value                      # p.ej. 'pagos'
            id_col    = self.E.ID_PAGO_NOMINA.value             # 'id_pago_nomina'

            # 1) limpiar dependencias que SÍ existen en tu esquema
            # borradores de préstamo
            self._safe_delete_by_pago("detalles_pagos_prestamo", id_col, id_pago)
            # pagos de préstamo confirmados (si existe en tu DB)
            self._safe_delete_by_pago("pagos_prestamo", id_col, id_pago)
            # descuentos finales (si existe en tu DB)
            self._safe_delete_by_pago("descuentos", id_col, id_pago)

            # borrador de descuentos via modelo (si lo tienes)
            try:
                if self.detalles_desc_model:
                    self.detalles_desc_model.eliminar_por_id_pago(id_pago)
            except Exception:
                pass

            # 2) borra el registro principal
            self.db.run_query(f"DELETE FROM {pagos_tab} WHERE {id_col}=%s", (id_pago,))

            return {"status": "success", "message": f"Pago #{id_pago} eliminado correctamente."}
        except Exception as ex:
            return {"status": "error", "message": f"No se pudo eliminar el pago: {ex}"}


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
        Crea un grupo 'pagado' VACÍO (manual) para la FECHA indicada.
        - No mueve ni confirma pagos.
        - Si ya hay pagos 'pagado' con esa fecha, se rechaza porque el grupo 'real' ya existe.
        """
        try:
            # validar formato
            try:
                datetime.strptime(fecha, "%Y-%m-%d")
            except Exception:
                return {"status": "error", "message": "Formato de fecha inválido (usa YYYY-MM-DD)."}

            # si ya hay confirmados con esa fecha -> grupo 'real' existente
            q_chk = f"""
                SELECT COUNT(*) AS c
                FROM {self.E.TABLE.value}
                WHERE {self.E.ESTADO.value}='pagado' AND {self.E.FECHA_PAGO.value}=%s
            """
            r = self.db.get_data(q_chk, (fecha,), dictionary=True) or {}
            if int(r.get("c", 0)) > 0:
                return {"status": "error", "message": f"Ya existen pagos 'pagado' con fecha {fecha}."}

            # insertar grupo manual vacío (ignore para idempotencia)
            q_ins = """
                INSERT IGNORE INTO grupos_pagos (fecha, categoria, estado_grupo)
                VALUES (%s, 'pagado', 'abierto')
            """
            self.db.run_query(q_ins, (fecha,))
            return {"status": "success", "message": f"Grupo 'pagado' vacío creado para {fecha}."}
        except Exception as ex:
            return {"status": "error", "message": f"No fue posible crear el grupo: {ex}"}


    def eliminar_grupo_por_fecha(self, fecha: str) -> dict:
        """
        Elimina el grupo 'pagado' VACÍO (manual) de la FECHA dada.
        - No mueve ni toca pagos.
        - Si hay pagos 'pagado' con esa fecha, se rechaza (grupo ya 'real').
        """
        try:
            try:
                datetime.strptime(fecha, "%Y-%m-%d")
            except Exception:
                return {"status": "error", "message": "Formato de fecha inválido (usa YYYY-MM-DD)."}

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


    def _ensure_grupos_table(self):
        """
        Crea la tabla auxiliar para registrar grupos 'pagado' VACÍOS por FECHA.
        Estos grupos aparecen en la UI aunque no tengan pagos todavía.
        """
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

    # --- helpers internos seguros ---
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
        """Borra filas en `table` por `id_col=id_pago` SOLO si la tabla existe."""
        if not self._table_exists(table):
            return
        try:
            self.db.run_query(f"DELETE FROM {table} WHERE {id_col}=%s", (id_pago,))
        except Exception:
            # Silencioso para no ensuciar logs si hay FKs/otros detalles
            pass

    # ---------------------------------------------------------------------
    # Alias retrocompatible
    # ---------------------------------------------------------------------
    def get_all(self) -> Dict[str, Any]:
        """
        Alias retrocompatible de get_all_pagos().
        Permite que módulos antiguos que llamen payment_model.get_all()
        sigan funcionando sin romper la compatibilidad.
        """
        return self.get_all_pagos()
