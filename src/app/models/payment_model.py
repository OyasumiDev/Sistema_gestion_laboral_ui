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
        Garantiza la tabla `pagos` y agrega columnas nuevas si faltan (migración suave).
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

                    -- Campos de agrupación de pagos
                    {self.E.GRUPO_PAGO.value} VARCHAR(100) DEFAULT NULL,
                    {self.E.FECHA_INICIO.value} DATE DEFAULT NULL,
                    {self.E.FECHA_FIN.value} DATE DEFAULT NULL,
                    {self.E.ESTADO_GRUPO.value} ENUM('abierto','cerrado') DEFAULT 'abierto',

                    -- Campos de cálculo de nómina
                    {self.E.FECHA_PAGO.value} DATE NOT NULL,
                    {self.E.TOTAL_HORAS_TRABAJADAS.value} DECIMAL(5,2) DEFAULT 0,
                    {self.E.MONTO_BASE.value} DECIMAL(10,2) NOT NULL,
                    {self.E.MONTO_TOTAL.value} DECIMAL(10,2) NOT NULL,
                    {self.D.MONTO_DESCUENTO.value} DECIMAL(10,2) DEFAULT 0,
                    {self.P.PRESTAMO_MONTO.value} DECIMAL(10,2) DEFAULT 0,
                    {self.E.SALDO.value} DECIMAL(10,2) DEFAULT 0,
                    {self.E.PAGO_DEPOSITO.value} DECIMAL(10,2) NOT NULL DEFAULT 0,
                    {self.E.PAGO_EFECTIVO.value} DECIMAL(10,2) NOT NULL DEFAULT 0,
                    {self.E.ESTADO.value} VARCHAR(20) DEFAULT 'pendiente',

                    -- Metadatos
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                    -- Claves foráneas
                    FOREIGN KEY ({self.E.NUMERO_NOMINA.value})
                        REFERENCES empleados(numero_nomina)
                        ON DELETE CASCADE,

                    -- Índices
                    INDEX idx_pagos_grupo ({self.E.GRUPO_PAGO.value}),
                    INDEX idx_pagos_fecha ({self.E.FECHA_PAGO.value})
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {self.E.TABLE.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {self.E.TABLE.value} ya existe.")
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {self.E.TABLE.value}: {ex}")
            return False



    # ---------------------------------------------------------------------
    # Stored Procedure de horas (creación si no existe)
    # ---------------------------------------------------------------------
    def crear_sp_horas_trabajadas_para_pagos(self):
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
                    IF p_numero_nomina IS NOT NULL THEN
                        IF EXISTS (SELECT 1 FROM empleados WHERE numero_nomina = p_numero_nomina) THEN
                            SELECT
                                a.numero_nomina,
                                e.nombre_completo,
                                IFNULL(SEC_TO_TIME(SUM(TIME_TO_SEC(a.tiempo_trabajo))), '00:00:00') AS total_horas_trabajadas
                            FROM asistencias a
                            JOIN empleados e ON a.numero_nomina = e.numero_nomina
                            WHERE a.numero_nomina = p_numero_nomina
                            AND a.fecha BETWEEN p_fecha_inicio AND p_fecha_fin
                            AND a.estado = 'completo'
                            GROUP BY a.numero_nomina, e.nombre_completo;
                        ELSE
                            SELECT 'Empleado no encontrado' AS mensaje;
                        END IF;
                    ELSE
                        SELECT
                            a.numero_nomina,
                            e.nombre_completo,
                            IFNULL(SEC_TO_TIME(SUM(TIME_TO_SEC(a.tiempo_trabajo))), '00:00:00') AS total_horas_trabajadas
                        FROM asistencias a
                        JOIN empleados e ON a.numero_nomina = e.numero_nomina
                        WHERE a.fecha BETWEEN p_fecha_inicio AND p_fecha_fin
                        AND a.estado = 'completo'
                        GROUP BY a.numero_nomina, e.nombre_completo;
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
    def get_total_horas_trabajadas(self, fecha_inicio: str, fecha_fin: str, numero_nomina: Optional[int] = None) -> Dict[str, Any]:
        try:
            cursor = self.db.connection.cursor()
            cursor.callproc("horas_trabajadas_para_pagos", (numero_nomina, fecha_inicio, fecha_fin))
            for result in cursor.stored_results():
                rows = result.fetchall()
                cols = [d[0] for d in result.description]
                data = [dict(zip(cols, r)) for r in rows]
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
    def _hhmmss_to_dec(hhmmss: str) -> float:
        try:
            h, m, s = map(int, str(hhmmss or "0:0:0").split(":"))
            return round(h + m / 60.0 + s / 3600.0, 2)
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
    def generar_pagos_por_rango(self, fecha_inicio: str, fecha_fin: str) -> Dict[str, Any]:
        """
        Genera/actualiza pagos PENDIENTES por empleado para el rango [fecha_inicio, fecha_fin].
        - Asigna grupo lógico (grupo_pago, fecha_inicio, fecha_fin, estado_grupo='abierto').
        - Consolida si ya existen pendientes en el rango.
        - NO escribe 'descuentos' finales; inicializa/actualiza BORRADOR con defaults o clon del último 'pagado'.
        - Deja MONTO_TOTAL = MONTO_BASE (la vista calcula total con borrador/loans).
        """
        try:
            horas_rs = self.get_total_horas_trabajadas(fecha_inicio, fecha_fin, None)
            if horas_rs.get("status") != "success":
                return {"status": "error", "message": "No fue posible obtener horas del SP."}
            horas_rows = horas_rs.get("data") or []
            if not horas_rows:
                return {"status": "success", "message": "No hay horas registradas en el rango."}

            grupo_token = self._build_grupo_token(fecha_inicio, fecha_fin)

            generados = actualizados = eliminados = omitidos_pagados = sin_horas_sueldo = 0

            for r in horas_rows:
                try:
                    numero_nomina = int(r.get("numero_nomina", 0) or 0)
                    if numero_nomina <= 0:
                        continue

                    horas_dec = self._hhmmss_to_dec(r.get("total_horas_trabajadas", "00:00:00"))
                    sh = self._sueldo_hora(numero_nomina)
                    if horas_dec <= 0 or sh <= 0:
                        sin_horas_sueldo += 1
                        continue

                    monto_base = round(sh * horas_dec, 2)

                    # pagos existentes del empleado en el rango
                    q_exist = f"""
                        SELECT {self.E.ID_PAGO_NOMINA.value} AS id_pago,
                            {self.E.FECHA_PAGO.value} AS fecha_pago,
                            {self.E.ESTADO.value} AS estado
                        FROM {self.E.TABLE.value}
                        WHERE {self.E.NUMERO_NOMINA.value}=%s
                        AND {self.E.FECHA_PAGO.value} BETWEEN %s AND %s
                        ORDER BY {self.E.FECHA_PAGO.value} ASC, {self.E.ID_PAGO_NOMINA.value} ASC
                    """
                    existentes = self.db.get_data_list(q_exist, (numero_nomina, fecha_inicio, fecha_fin), dictionary=True) or []

                    if any(str(x.get("estado", "")).lower() == "pagado" for x in existentes):
                        # Si ya hay un pagado en el rango, no se reabre
                        omitidos_pagados += 1
                        continue

                    id_pago_target = None
                    to_delete: List[int] = []

                    if existentes:
                        en_fin = [x for x in existentes if str(x.get("fecha_pago")) == str(fecha_fin)]
                        if en_fin:
                            id_pago_target = int(en_fin[-1]["id_pago"])
                            to_delete = [int(x["id_pago"]) for x in existentes if int(x["id_pago"]) != id_pago_target]
                        else:
                            id_pago_target = int(existentes[-1]["id_pago"])
                            to_delete = [int(x["id_pago"]) for x in existentes[:-1]]

                        # borra duplicados pendientes + sus detalles de préstamo
                        if to_delete:
                            ids_tuple = tuple(to_delete)
                            self.db.run_query(
                                f"DELETE FROM detalles_pagos_prestamo WHERE {E_DET.ID_PAGO.value} IN ({', '.join(['%s']*len(ids_tuple))})",
                                ids_tuple,
                            )
                            self.db.run_query(
                                f"DELETE FROM {self.E.TABLE.value} WHERE {self.E.ID_PAGO_NOMINA.value} IN ({', '.join(['%s']*len(ids_tuple))})",
                                ids_tuple,
                            )
                            eliminados += len(to_delete)

                        # update consolidado
                        self.update_pago(id_pago_target, {
                            self.E.GRUPO_PAGO.value: grupo_token,
                            self.E.FECHA_INICIO.value: fecha_inicio,
                            self.E.FECHA_FIN.value: fecha_fin,
                            self.E.ESTADO_GRUPO.value: "abierto",
                            self.E.FECHA_PAGO.value: fecha_fin,
                            self.E.TOTAL_HORAS_TRABAJADAS.value: horas_dec,
                            self.E.MONTO_BASE.value: monto_base,
                            self.E.MONTO_TOTAL.value: monto_base,
                            self.D.MONTO_DESCUENTO.value: 0.0,
                            self.P.PRESTAMO_MONTO.value: 0.0,
                            self.E.SALDO.value: 0.0,
                            self.E.PAGO_DEPOSITO.value: 0.0,
                            self.E.PAGO_EFECTIVO.value: monto_base,
                            self.E.ESTADO.value: "pendiente",
                        })
                        actualizados += 1
                    else:
                        # insert nuevo
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
                            ) VALUES (%s,%s,%s,%s,'abierto',%s,%s,%s,%s,0,0,0,0,%s,'pendiente')
                        """
                        self.db.run_query(
                            ins_q,
                            (numero_nomina, grupo_token, fecha_inicio, fecha_fin, fecha_fin, horas_dec, monto_base, monto_base, monto_base),
                        )
                        id_pago_target = int(self.db.get_last_insert_id())
                        generados += 1

                    # Prellenar/actualizar BORRADOR de descuentos para ese pago
                    self._prefill_borrador_descuentos(id_pago_target, numero_nomina)

                except Exception as _:
                    # no paramos toda la corrida por un empleado
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

    def generar_pago_por_empleado(self, numero_nomina: int, fecha_inicio: str, fecha_fin: str) -> Dict[str, Any]:
        """
        Genera un pago PENDIENTE para el empleado en fecha_fin con grupo del rango.
        """
        try:
            if not numero_nomina or not isinstance(numero_nomina, int):
                return {"status": "error", "message": "Número de nómina inválido."}

            horas_rs = self.get_total_horas_trabajadas(fecha_inicio, fecha_fin, numero_nomina)
            if horas_rs.get("status") != "success" or not horas_rs.get("data"):
                return {"status": "error", "message": f"No hay horas válidas para el empleado {numero_nomina}."}

            horas_dec = self._hhmmss_to_dec(horas_rs["data"][0].get("total_horas_trabajadas", "00:00:00"))
            sh = self._sueldo_hora(numero_nomina)
            if horas_dec <= 0 or sh <= 0:
                return {"status": "error", "message": "Horas o sueldo por hora inválidos."}

            monto_base = round(sh * horas_dec, 2)
            grupo_token = self._build_grupo_token(fecha_inicio, fecha_fin)

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
                ) VALUES (%s,%s,%s,%s,'abierto',%s,%s,%s,%s,0,0,0,0,%s,'pendiente')
            """
            self.db.run_query(
                insert_q,
                (numero_nomina, grupo_token, fecha_inicio, fecha_fin, fecha_fin, horas_dec, monto_base, monto_base, monto_base),
            )
            id_pago = int(self.db.get_last_insert_id())

            # BORRADOR de descuentos (defaults + clon último 'pagado')
            self._prefill_borrador_descuentos(id_pago, numero_nomina)

            return {"status": "success", "message": f"Pago generado por ${monto_base:.2f}", "id_pago": id_pago}
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
                    p.{self.E.NUMERO_NOMINA.value} AS numero_nomina,
                    e.nombre_completo,
                    e.sueldo_por_hora,
                    p.{self.E.GRUPO_PAGO.value} AS grupo_pago,
                    p.{self.E.FECHA_INICIO.value} AS fecha_inicio,
                    p.{self.E.FECHA_FIN.value} AS fecha_fin,
                    p.{self.E.ESTADO_GRUPO.value} AS estado_grupo,
                    p.{self.E.FECHA_PAGO.value} AS fecha_pago,
                    p.{self.E.TOTAL_HORAS_TRABAJADAS.value} AS horas,
                    p.{self.E.MONTO_BASE.value} AS monto_base,
                    p.{self.E.MONTO_TOTAL.value} AS monto_total,
                    p.{self.D.MONTO_DESCUENTO.value} AS descuentos,
                    p.{self.P.PRESTAMO_MONTO.value} AS prestamos,
                    p.{self.E.SALDO.value} AS saldo,
                    p.{self.E.PAGO_DEPOSITO.value} AS deposito,
                    p.{self.E.PAGO_EFECTIVO.value} AS efectivo,
                    p.{self.E.ESTADO.value} AS estado
                FROM {self.E.TABLE.value} p
                JOIN empleados e ON p.{self.E.NUMERO_NOMINA.value} = e.numero_nomina
                ORDER BY p.{self.E.FECHA_PAGO.value} DESC, e.numero_nomina
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
                    p.{self.E.NUMERO_NOMINA.value} AS numero_nomina,
                    e.nombre_completo,
                    e.sueldo_por_hora,
                    p.{self.E.GRUPO_PAGO.value} AS grupo_pago,
                    p.{self.E.FECHA_INICIO.value} AS fecha_inicio,
                    p.{self.E.FECHA_FIN.value} AS fecha_fin,
                    p.{self.E.ESTADO_GRUPO.value} AS estado_grupo,
                    p.{self.E.FECHA_PAGO.value} AS fecha_pago,
                    p.{self.E.TOTAL_HORAS_TRABAJADAS.value} AS horas,
                    p.{self.E.MONTO_BASE.value} AS monto_base,
                    p.{self.E.MONTO_TOTAL.value} AS monto_total,
                    p.{self.D.MONTO_DESCUENTO.value} AS descuentos,
                    p.{self.P.PRESTAMO_MONTO.value} AS prestamos,
                    p.{self.E.SALDO.value} AS saldo,
                    p.{self.E.PAGO_DEPOSITO.value} AS deposito,
                    p.{self.E.PAGO_EFECTIVO.value} AS efectivo,
                    p.{self.E.ESTADO.value} AS estado
                FROM {self.E.TABLE.value} p
                JOIN empleados e ON p.{self.E.NUMERO_NOMINA.value} = e.numero_nomina
                WHERE p.{self.E.NUMERO_NOMINA.value}=%s
                ORDER BY p.{self.E.FECHA_PAGO.value} DESC
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
                    p.{self.E.NUMERO_NOMINA.value} AS numero_nomina,
                    e.nombre_completo,
                    e.sueldo_por_hora,
                    p.{self.E.GRUPO_PAGO.value} AS grupo_pago,
                    p.{self.E.FECHA_PAGO.value} AS fecha_pago,
                    p.{self.E.TOTAL_HORAS_TRABAJADAS.value} AS horas,
                    p.{self.E.MONTO_BASE.value} AS monto_base,
                    p.{self.E.MONTO_TOTAL.value} AS monto_total,
                    p.{self.D.MONTO_DESCUENTO.value} AS descuentos,
                    p.{self.P.PRESTAMO_MONTO.value} AS prestamos,
                    p.{self.E.SALDO.value} AS saldo,
                    p.{self.E.PAGO_DEPOSITO.value} AS deposito,
                    p.{self.E.PAGO_EFECTIVO.value} AS efectivo,
                    p.{self.E.ESTADO.value} AS estado
                FROM {self.E.TABLE.value} p
                JOIN empleados e ON p.{self.E.NUMERO_NOMINA.value} = e.numero_nomina
                ORDER BY e.numero_nomina, p.{self.E.FECHA_PAGO.value} DESC
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
                    p.{self.E.NUMERO_NOMINA.value} AS numero_nomina,
                    e.nombre_completo,
                    e.sueldo_por_hora,
                    p.{self.E.FECHA_PAGO.value} AS fecha_pago,
                    p.{self.E.TOTAL_HORAS_TRABAJADAS.value} AS horas,
                    p.{self.E.MONTO_BASE.value} AS monto_base,
                    p.{self.E.MONTO_TOTAL.value} AS monto_total,
                    p.{self.D.MONTO_DESCUENTO.value} AS descuentos,
                    p.{self.P.PRESTAMO_MONTO.value} AS prestamos,
                    p.{self.E.SALDO.value} AS saldo,
                    p.{self.E.PAGO_DEPOSITO.value} AS deposito,
                    p.{self.E.PAGO_EFECTIVO.value} AS efectivo,
                    p.{self.E.ESTADO.value} AS estado
                FROM {self.E.TABLE.value} p
                JOIN empleados e ON p.{self.E.NUMERO_NOMINA.value} = e.numero_nomina
                WHERE p.{self.E.GRUPO_PAGO.value}=%s
                ORDER BY p.{self.E.FECHA_PAGO.value} DESC, e.numero_nomina
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
        if not cambios:
            return True
        permitidas = {
            self.E.GRUPO_PAGO.value, self.E.FECHA_INICIO.value, self.E.FECHA_FIN.value, self.E.ESTADO_GRUPO.value,
            self.E.FECHA_PAGO.value, self.E.TOTAL_HORAS_TRABAJADAS.value, self.E.MONTO_BASE.value,
            self.E.MONTO_TOTAL.value, self.D.MONTO_DESCUENTO.value, self.P.PRESTAMO_MONTO.value,
            self.E.SALDO.value, self.E.PAGO_DEPOSITO.value, self.E.PAGO_EFECTIVO.value, self.E.ESTADO.value,
        }
        sets, vals = [], []
        for k, v in cambios.items():
            if k in permitidas:
                sets.append(f"{k}=%s"); vals.append(v)
        if not sets:
            return True
        q = f"UPDATE {self.E.TABLE.value} SET {', '.join(sets)} WHERE {self.E.ID_PAGO_NOMINA.value}=%s"
        vals.append(id_pago)
        self.db.run_query(q, tuple(vals))
        return True

    def confirmar_pago(self, id_pago: int, fecha_real_pago: Optional[str] = None) -> Dict[str, Any]:
        """
        Confirmación:
        1) Aplica borrador -> descuentos (finales) y limpia borrador.
        2) Aplica detalles de préstamos -> pagos_prestamo.
        3) Recalcula total (base - desc - préstamos) y marca 'pagado'.
        """
        try:
            pago = self.get_by_id(id_pago)
            if pago.get("status") != "success":
                return pago
            p = pago["data"]
            if str(p.get(self.E.ESTADO.value, "")).lower() == "pagado":
                return {"status": "success", "message": "El pago ya estaba confirmado."}

            numero_nomina = int(p.get(self.E.NUMERO_NOMINA.value))
            fecha_pago = str(p.get(self.E.FECHA_PAGO.value))
            fecha_real = fecha_real_pago or fecha_pago

            # 1) Aplicar y limpiar borrador de descuentos
            self.detalles_desc_model.aplicar_a_descuentos_y_limpiar(id_pago, self.discount_model)

            # 2) Aplicar detalles de préstamos -> pagos_prestamo
            self._aplicar_detalles_prestamo_de_pago(id_pago_nomina=id_pago, fecha_pago=fecha_pago, fecha_real=fecha_real)

            # 3) Recalcular totales reales
            total_desc = float(self.discount_model.get_total_descuentos_por_pago(id_pago) or 0.0)
            total_prest = self._get_prestamos_totales_para_pago(id_pago=id_pago, numero_nomina=numero_nomina, fecha_fin=fecha_pago)
            monto_base = float(p.get(self.E.MONTO_BASE.value) or 0)
            nuevo_total = max(0.0, round(monto_base - total_desc - total_prest, 2))

            self.update_pago(id_pago, {
                self.E.MONTO_TOTAL.value: nuevo_total,
                self.D.MONTO_DESCUENTO.value: total_desc,
                self.P.PRESTAMO_MONTO.value: total_prest,
                self.E.PAGO_EFECTIVO.value: max(0.0, nuevo_total - float(p.get(self.E.PAGO_DEPOSITO.value) or 0)),
                self.E.ESTADO.value: "pagado"
            })
            return {"status": "success", "message": "Pago confirmado correctamente."}
        except Exception as ex:
            return {"status": "error", "message": f"Error al confirmar pago: {ex}"}

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
        - Si llega `descuentos`, refresca la tabla `descuentos` (delete+insert) con totales planos.
        (Para flujos legacy; en el flujo nuevo se usa el borrador y 'confirmar_pago'.)
        - Actualiza `estado` y/o `pago_deposito`.
        """
        def _to_float(v):
            try:
                return float(v or 0)
            except Exception:
                return 0.0

        try:
            # Descuentos (legacy, no recomendado en el nuevo flujo)
            if descuentos is not None:
                total_desc = round(
                    _to_float(descuentos.get("monto_imss", descuentos.get("imss"))) +
                    _to_float(descuentos.get("monto_transporte", descuentos.get("transporte"))) +
                    _to_float(descuentos.get("monto_extra", descuentos.get("extra"))),
                    2
                )
                # Limpia y sube un agregate simple (si tu tabla 'descuentos' es por-línea, omite este bloque)
                # Mantengo el patrón por compatibilidad con tu método previo.
                del_q = "DELETE FROM descuentos WHERE id_pago_nomina=%s"
                self.db.run_query(del_q, (id_pago,))
                ins_q = """
                    INSERT INTO descuentos (id_pago_nomina, tipo, descripcion, monto_descuento, fecha_aplicacion)
                    VALUES (%s,'totales', 'carga_legacy', %s, CURRENT_DATE())
                """
                self.db.run_query(ins_q, (id_pago, total_desc))

            # Estado / depósito
            cambios = {}
            if estado is not None:
                cambios[self.E.ESTADO.value] = estado
            if deposito is not None:
                cambios[self.E.PAGO_DEPOSITO.value] = float(deposito)
            if cambios:
                self.update_pago(id_pago, cambios)

            return {"status": "success", "message": "Pago actualizado correctamente."}
        except Exception as ex:
            return {"status": "error", "message": f"Error al actualizar pago: {ex}"}


