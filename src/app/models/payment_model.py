# app/models/payment_model.py
from datetime import datetime, date
from typing import Dict, Any, List, Optional

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


class PaymentModel:
    """
    Modelo de Pagos (Nómina)
    - Genera pagos por empleado o por rango
    - Lee pagos plano y AGRUPADO por empleado (para UI con grupos expansibles)
    - Confirma pagos (aplica detalles de préstamos pendientes)
    - Elimina pagos no confirmados
    - Utilidades: fechas usadas, horas trabajadas (vía SP), existencia de pago por fecha, etc.
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self.employee_model = EmployesModel()
        self.discount_model = DiscountModel()
        self.loan_model = LoanModel()
        self.loan_payment_model = LoanPaymentModel()
        self.E = E_PAYMENT
        self.D = E_DISCOUNT
        self.P = E_PRESTAMOS
        self.LP = E_PAGOS_PRESTAMO
        self._exists_table = self.check_table()

    # ---------------------------------------------------------------------
    # Infra / Esquema
    # ---------------------------------------------------------------------
    def check_table(self) -> bool:
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
                    {self.E.FECHA_PAGO.value} DATE NOT NULL,
                    {self.E.TOTAL_HORAS_TRABAJADAS.value} DECIMAL(5,2) DEFAULT 0,
                    {self.E.MONTO_BASE.value} DECIMAL(10,2) NOT NULL,
                    {self.E.MONTO_TOTAL.value} DECIMAL(10,2) NOT NULL,
                    {self.D.MONTO_DESCUENTO.value} DECIMAL(10,2) DEFAULT 0,
                    {self.P.PRESTAMO_MONTO.value} DECIMAL(10,2) DEFAULT 0,
                    {self.E.SALDO.value} DECIMAL(10,2) DEFAULT 0,
                    {self.E.PAGO_DEPOSITO.value} DECIMAL(10,2) NOT NULL,
                    {self.E.PAGO_EFECTIVO.value} DECIMAL(10,2) NOT NULL,
                    {self.E.ESTADO.value} VARCHAR(20) DEFAULT 'pendiente',
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY ({self.E.NUMERO_NOMINA.value})
                        REFERENCES empleados(numero_nomina)
                        ON DELETE CASCADE
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
                print("⚠️ Stored Procedure 'horas_trabajadas_para_pagos' no existe. Creando...")

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
                print("✅ Stored Procedure 'horas_trabajadas_para_pagos' creado correctamente.")
            else:
                print("✔️ Stored Procedure 'horas_trabajadas_para_pagos' ya existe.")
        except Exception as ex:
            print(f"❌ Error al crear SP 'horas_trabajadas_para_pagos': {ex}")

    # ---------------------------------------------------------------------
    # Utilidades de lectura/cálculo
    # ---------------------------------------------------------------------
    def get_total_horas_trabajadas(self, fecha_inicio: str, fecha_fin: str, numero_nomina: Optional[int] = None) -> Dict[str, Any]:
        """
        Llama al SP para obtener horas trabajadas (HH:MM:SS) por empleado o global.
        Retorna {"status":"success", "data":[{numero_nomina, nombre_completo, total_horas_trabajadas}, ...]}
        """
        try:
            cursor = self.db.connection.cursor()
            cursor.callproc("horas_trabajadas_para_pagos", (numero_nomina, fecha_inicio, fecha_fin))
            # El primer resultset tiene los datos
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
        """
        Devuelve fechas de pago usadas (pendientes o pagadas) para bloquear en el selector.
        """
        try:
            q = f"SELECT DISTINCT {self.E.FECHA_PAGO.value} AS f FROM {self.E.TABLE.value}"
            rows = self.db.get_data_list(q, dictionary=True) or []
            return [str(r["f"]) for r in rows if r and r.get("f")]
        except Exception:
            return []

    def existe_pago_para_fecha(self, numero_nomina: int, fecha: str, incluir_pendientes: bool = False) -> bool:
        """
        Verifica si ya hay un pago para ese empleado en esa fecha.
        - incluir_pendientes=False → solo 'pagado'
        - True → cuenta cualquier estado
        """
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
        Genera/actualiza UN ÚNICO pago PENDIENTE por empleado para el rango [fecha_inicio, fecha_fin].
        - Consolida (update) si ya existen pendientes en el rango y elimina los duplicados.
        - Si hay un 'pagado' en el rango, omite ese empleado (no se reabre).
        - Fecha de pago del registro consolidado: fecha_fin.
        """
        try:
            # 1) Horas agregadas por empleado (SP en modo "todos")
            horas_rs = self.get_total_horas_trabajadas(fecha_inicio, fecha_fin, None)
            if horas_rs.get("status") != "success":
                return {"status": "error", "message": "No fue posible obtener horas del SP."}
            horas_rows = horas_rs.get("data") or []
            if not horas_rows:
                return {"status": "success", "message": "No hay horas registradas en el rango."}

            # Índice de empleados (para sueldo_por_hora / sueldo_diario)
            empleados_idx = {}
            try:
                all_emps = self.employee_model.get_all()
                if all_emps and all_emps.get("status") == "success":
                    for e in all_emps["data"]:
                        num = int(e.get("numero_nomina", 0) or 0)
                        if num > 0:
                            empleados_idx[num] = e
            except Exception:
                pass

            def _get_sueldo_hora(num: int) -> float:
                emp = empleados_idx.get(num)
                if not emp:
                    try:
                        emp = self.employee_model.get_by_numero_nomina(num) or {}
                    except Exception:
                        emp = {}
                sh = float(emp.get("sueldo_por_hora", 0) or 0)
                if sh <= 0:
                    # fallback: sueldo_diario / 8
                    try:
                        sd = float(emp.get("sueldo_diario", 0) or 0)
                        if sd > 0:
                            sh = round(sd / 8.0, 2)
                    except Exception:
                        pass
                return max(0.0, sh)

            def _to_hours_dec(hhmmss: str) -> float:
                try:
                    h, m, s = map(int, str(hhmmss or "0:0:0").split(":"))
                    return round(h + m/60.0 + s/3600.0, 2)
                except Exception:
                    return 0.0

            generados, actualizados, eliminados, omitidos_pagados, sin_horas_sueldo, errores = 0, 0, 0, 0, 0, 0

            for r in horas_rows:
                try:
                    numero_nomina = int(r.get("numero_nomina", 0) or 0)
                    if numero_nomina <= 0:
                        continue

                    horas_dec = _to_hours_dec(r.get("total_horas_trabajadas", "00:00:00"))
                    if horas_dec <= 0:
                        sin_horas_sueldo += 1
                        continue

                    sueldo_hora = _get_sueldo_hora(numero_nomina)
                    if sueldo_hora <= 0:
                        sin_horas_sueldo += 1
                        continue

                    monto_base = round(sueldo_hora * horas_dec, 2)

                    # 2) Buscar pagos existentes del empleado en el RANGO
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

                    # Si hay algún pagado en el rango -> omitir (no tocamos cierres ya confirmados)
                    if any(str(x.get("estado", "")).lower() == "pagado" for x in existentes):
                        omitidos_pagados += 1
                        continue

                    id_pago_target = None

                    if existentes:
                        # Prefiere el que ya esté en fecha_fin; sino el más reciente
                        en_fin = [x for x in existentes if str(x.get("fecha_pago")) == str(fecha_fin)]
                        if en_fin:
                            id_pago_target = int(en_fin[-1]["id_pago"])
                            to_delete = [x for x in existentes if int(x["id_pago"]) != id_pago_target]
                        else:
                            id_pago_target = int(existentes[-1]["id_pago"])
                            to_delete = [x for x in existentes[:-1]]

                        # Eliminar duplicados pendientes del rango (salvo el target)
                        if to_delete:
                            ids = tuple(int(x["id_pago"]) for x in to_delete)
                            # elimina detalles de préstamos pendientes ligados a esos pagos
                            dq = f"DELETE FROM detalles_pagos_prestamo WHERE {E_DET.ID_PAGO.value} IN ({', '.join(['%s']*len(ids))})"
                            self.db.run_query(dq, ids)
                            # elimina pagos
                            del_q = f"DELETE FROM {self.E.TABLE.value} WHERE {self.E.ID_PAGO_NOMINA.value} IN ({', '.join(['%s']*len(ids))})"
                            self.db.run_query(del_q, ids)
                            eliminados += len(ids)

                        # UPDATE del pago target con la base consolidada
                        self.update_pago(id_pago_target, {
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
                        # INSERT único con fecha_fin
                        ins_q = f"""
                            INSERT INTO {self.E.TABLE.value} (
                                {self.E.NUMERO_NOMINA.value},
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
                            ) VALUES (%s, %s, %s, %s, %s, 0, 0, 0, 0, %s, 'pendiente')
                        """
                        self.db.run_query(ins_q, (numero_nomina, fecha_fin, horas_dec, monto_base, monto_base, monto_base))
                        id_pago_target = self.db.get_last_insert_id()
                        generados += 1

                    # 3) Reaplicar descuentos y préstamos al pago target resultante
                    try:
                        self.discount_model.agregar_descuentos_opcionales(
                            numero_nomina=numero_nomina,
                            id_pago=id_pago_target,
                            aplicar_imss=True,
                            aplicar_transporte=True,
                            aplicar_comida=True,
                            estado_comida="media",
                        )
                    except Exception:
                        pass

                    total_desc = float(self.discount_model.get_total_descuentos_por_pago(id_pago_target) or 0.0)
                    total_prest = self._get_prestamos_totales_para_pago(
                        id_pago=id_pago_target, numero_nomina=numero_nomina, fecha_fin=fecha_fin
                    )
                    monto_final = max(0.0, round(monto_base - total_desc - total_prest, 2))

                    self.update_pago(id_pago_target, {
                        self.E.MONTO_TOTAL.value: monto_final,
                        self.D.MONTO_DESCUENTO.value: total_desc,
                        self.P.PRESTAMO_MONTO.value: total_prest,
                        self.E.PAGO_EFECTIVO.value: monto_final,  # depósito=0
                        self.E.SALDO.value: 0.0,
                    })

                except Exception:
                    errores += 1
                    continue

            msg = (
                f"{generados} creados, {actualizados} actualizados, {eliminados} duplicados pendientes eliminados, "
                f"{omitidos_pagados} omitidos (ya pagados), {sin_horas_sueldo} sin horas/sueldo válido."
            )
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
            return self.generar_pago_por_empleado(numero_nomina, today, today)
        except Exception as ex:
            return {"status": "error", "message": f"Error en pago manual: {ex}"}

    def generar_pago_por_empleado(self, numero_nomina: int, fecha_inicio: str, fecha_fin: str) -> Dict[str, Any]:
        """
        Genera un pago PENDIENTE para el empleado en fecha_fin.
        """
        try:
            if not numero_nomina or not isinstance(numero_nomina, int):
                return {"status": "error", "message": "Número de nómina inválido."}

            # Empleado y sueldo
            empleado = self.employee_model.get_by_numero_nomina(numero_nomina)
            if not empleado or not isinstance(empleado, dict):
                return {"status": "error", "message": f"Empleado {numero_nomina} no encontrado."}

            sueldo_hora = float(empleado.get("sueldo_por_hora", 0) or 0)
            if sueldo_hora <= 0:
                return {"status": "error", "message": "Sueldo por hora inválido o no definido."}

            # Horas trabajadas del periodo
            horas_rs = self.get_total_horas_trabajadas(fecha_inicio, fecha_fin, numero_nomina)
            if horas_rs.get("status") != "success" or not horas_rs.get("data"):
                return {"status": "error", "message": f"No hay horas válidas para el empleado {numero_nomina}."}

            total_hhmmss = horas_rs["data"][0].get("total_horas_trabajadas", "00:00:00")
            h, m, s = map(int, total_hhmmss.split(":"))
            horas_dec = round(h + m / 60 + s / 3600, 2)

            monto_base = round(sueldo_hora * horas_dec, 2)

            # Inserta base (pendiente)
            insert_q = f"""
                INSERT INTO {self.E.TABLE.value} (
                    {self.E.NUMERO_NOMINA.value},
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
                ) VALUES (%s, %s, %s, %s, %s, 0, 0, 0, 0, 0, 'pendiente')
            """
            self.db.run_query(insert_q, (numero_nomina, fecha_fin, horas_dec, monto_base, monto_base))
            id_pago = self.db.get_last_insert_id()

            # Aplica descuentos opcionales (usa id real)
            self.discount_model.agregar_descuentos_opcionales(
                numero_nomina=numero_nomina,
                id_pago=id_pago,
                aplicar_imss=True,
                aplicar_transporte=True,
                aplicar_comida=True,
                estado_comida="media",
            )
            total_desc = float(self.discount_model.get_total_descuentos_por_pago(id_pago) or 0)

            # Préstamos: confirmados (por pago) + pendientes (en detalles para ese pago)
            total_prestamos = self._get_prestamos_totales_para_pago(id_pago=id_pago, numero_nomina=numero_nomina, fecha_fin=fecha_fin)

            monto_final = max(0.0, monto_base - total_desc - total_prestamos)

            # Actualiza campos derivados
            self.update_pago(id_pago, {
                self.E.MONTO_TOTAL.value: monto_final,
                self.D.MONTO_DESCUENTO.value: total_desc,
                self.P.PRESTAMO_MONTO.value: total_prestamos,
                self.E.PAGO_EFECTIVO.value: monto_final,     # por defecto todo en efectivo si depósito=0
                self.E.SALDO.value: 0.0
            })

            return {
                "status": "success",
                "message": f"✅ Pago generado por ${monto_final:.2f}",
                "id_pago": id_pago,
                "monto_base": monto_base,
                "total_descuentos": total_desc,
                "total_prestamos": total_prestamos
            }

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
                # si no hay pagos, devolvemos encabezado de empleado igualmente
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
        """
        Estructura lista para UI con grupos expansibles:
        {
          numero_nomina: {
            "numero_nomina": int,
            "nombre_empleado": str,
            "sueldo_por_hora": float,
            "pagos": [ {...}, ... ]
          }, ...
        }
        """
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

    # ---------------------------------------------------------------------
    # Edición / Confirmación / Eliminación
    # ---------------------------------------------------------------------
    def update_pago(self, id_pago: int, cambios: Dict[str, Any]) -> bool:
        """
        Actualiza campos del pago por id. 'cambios' es {columna: valor}
        Solo permite columnas de la tabla pagos.
        """
        if not cambios:
            return True
        permitidas = {
            self.E.FECHA_PAGO.value,
            self.E.TOTAL_HORAS_TRABAJADAS.value,
            self.E.MONTO_BASE.value,
            self.E.MONTO_TOTAL.value,
            self.D.MONTO_DESCUENTO.value,
            self.P.PRESTAMO_MONTO.value,
            self.E.SALDO.value,
            self.E.PAGO_DEPOSITO.value,
            self.E.PAGO_EFECTIVO.value,
            self.E.ESTADO.value,
        }
        sets, vals = [], []
        for k, v in cambios.items():
            if k in permitidas:
                sets.append(f"{k}=%s")
                vals.append(v)
        if not sets:
            return True
        q = f"UPDATE {self.E.TABLE.value} SET {', '.join(sets)} WHERE {self.E.ID_PAGO_NOMINA.value}=%s"
        vals.append(id_pago)
        self.db.run_query(q, tuple(vals))
        return True

    def confirmar_pago(self, id_pago: int, fecha_real_pago: Optional[str] = None) -> Dict[str, Any]:
        """
        Confirma el pago:
        - Aplica detalles de préstamos pendientes para este id_pago (crea pagos reales en pagos_prestamo)
        - Marca el pago como 'pagado'
        """
        try:
            pago = self.get_by_id(id_pago)
            if pago.get("status") != "success":
                return pago
            p = pago["data"]
            if str(p.get(self.E.ESTADO.value, "")).lower() == "pagado":
                return {"status": "success", "message": "El pago ya estaba confirmado."}

            fecha_pago = str(p.get(self.E.FECHA_PAGO.value))
            fecha_real = fecha_real_pago or fecha_pago

            # Aplica todos los detalles pendientes de préstamos de este pago
            self._aplicar_detalles_prestamo_de_pago(id_pago_nomina=id_pago, fecha_pago=fecha_pago, fecha_real=fecha_real)

            # Recalcula total préstamos (por si se añadieron reales) y actualiza monto_total/efectivo si es necesario
            numero_nomina = int(p.get(self.E.NUMERO_NOMINA.value))
            total_desc = float(self.discount_model.get_total_descuentos_por_pago(id_pago) or 0)
            total_prest = self._get_prestamos_totales_para_pago(id_pago=id_pago, numero_nomina=numero_nomina, fecha_fin=fecha_pago)
            monto_base = float(p.get(self.E.MONTO_BASE.value) or 0)
            nuevo_total = max(0.0, monto_base - total_desc - total_prest)

            self.update_pago(id_pago, {
                self.E.MONTO_TOTAL.value: nuevo_total,
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
        También elimina detalles de préstamos PENDIENTES asociados a ese pago.
        """
        try:
            pago = self.get_by_id(id_pago)
            if pago.get("status") != "success":
                return pago
            p = pago["data"]
            if str(p.get(self.E.ESTADO.value, "")).lower() == "pagado":
                return {"status": "error", "message": "No se puede eliminar un pago ya confirmado."}

            # Borra detalles pendientes de préstamo ligados al pago
            dq = f"DELETE FROM detalles_pagos_prestamo WHERE {E_DET.ID_PAGO.value}=%s"
            self.db.run_query(dq, (id_pago,))

            # (Opcional) eliminar descuentos ligados a este pago si los manejas como 'pendientes'
            # self.discount_model.eliminar_por_pago(id_pago)  # si tienes este método

            # Borra el pago
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

            q = f"""
                SELECT * FROM {self.E.TABLE.value}
                WHERE {self.E.ID_PAGO_NOMINA.value}=%s
            """
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
        """
        Suma préstamos confirmados PARA ESTE PAGO (pagos_prestamo) + pendientes en detalles ligados al pago.
        Además, si manejas lógicas por empleado/periodo, aquí podrías sumar otros cargos.
        """
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
        """
        Lee la suma de detalles_pagos_prestamo para un id_pago_nomina.
        """
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
        """
        Convierte TODOS los detalles pendientes (detalles_pagos_prestamo) de este pago en pagos reales (pagos_prestamo),
        usando LoanPaymentModel.add_from_detalle (que limpia el detalle tras crear el pago).
        """
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
            # Log y continuar (no romper confirmación si falla 1 detalle)
            print(f"❌ Error aplicando detalle de préstamo: {ex}")


# Dentro de app/models/payment_model.py  (clase PaymentModel)

    def update_pago_completo(
        self,
        *,
        id_pago: int,
        descuentos: dict | None = None,
        estado: str | None = None,
        deposito: float | None = None,
    ) -> dict:
        """
        Persiste cambios del pago de forma atómica (si hay conexión):
        - Si se provee `descuentos`, confirma los montos en tabla `descuentos`
            para `id_pago_nomina = id_pago` (delete + insert).
        - Actualiza `estado` y, si viene, `pago_deposito` en `pagos_nomina`.
        Retorna: {"status": "success" | "error", "message": str}
        """
        # ---- 0) Helpers internos para portabilidad ----
        def _to_float(v):
            try:
                return float(v or 0)
            except Exception:
                return 0.0

        def _get_conn_and_cursor():
            # soporta self.conn / self.db / self._conn (sqlite3/pyodbc/etc.)
            conn = getattr(self, "conn", None) or getattr(self, "db", None) or getattr(self, "_conn", None)
            cur = None
            if conn is not None:
                try:
                    cur = conn.cursor()
                except Exception:
                    cur = None
            return conn, cur

        def _execute_direct(cur, sql, params=()):
            cur.execute(sql, params)

        # Intento 1: usar SQL directo si hay conexión/cursor
        conn, cur = _get_conn_and_cursor()
        if cur is not None:
            try:
                # BEGIN (algunos drivers requieren manejo manual)
                try:
                    _execute_direct(cur, "BEGIN")
                except Exception:
                    pass  # muchos drivers inician transacción implícitamente

                # ---- 1) Confirmar descuentos si se proveen ----
                if descuentos is not None:
                    # Mapea claves típicas
                    imss = _to_float(
                        descuentos.get("monto_imss",
                        descuentos.get("imss", 0))
                    )
                    transporte = _to_float(
                        descuentos.get("monto_transporte",
                        descuentos.get("transporte", 0))
                    )
                    extra = _to_float(
                        descuentos.get("monto_extra",
                        descuentos.get("extra", 0))
                    )
                    total_desc = round(imss + transporte + extra, 2)

                    # delete + insert para ser agnóstico del motor
                    _execute_direct(cur, "DELETE FROM descuentos WHERE id_pago_nomina = ?", (id_pago,))
                    _execute_direct(
                        cur,
                        """
                        INSERT INTO descuentos
                            (id_pago_nomina, monto_imss, monto_transporte, monto_extra, total_descuentos, updated_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (id_pago, imss, transporte, extra, total_desc),
                    )

                # ---- 2) Actualizar estado / depósito en pagos_nomina ----
                if estado is not None and deposito is not None:
                    _execute_direct(
                        cur,
                        """
                        UPDATE pagos_nomina
                        SET estado = ?,
                            pago_deposito = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id_pago_nomina = ?
                        """,
                        (estado, float(deposito), id_pago),
                    )
                elif estado is not None:
                    _execute_direct(
                        cur,
                        """
                        UPDATE pagos_nomina
                        SET estado = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id_pago_nomina = ?
                        """,
                        (estado, id_pago),
                    )
                elif deposito is not None:
                    _execute_direct(
                        cur,
                        """
                        UPDATE pagos_nomina
                        SET pago_deposito = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id_pago_nomina = ?
                        """,
                        (float(deposito), id_pago),
                    )

                # COMMIT
                try:
                    conn.commit()
                except Exception:
                    pass

                return {"status": "success", "message": "Pago actualizado correctamente."}

            except Exception as ex:
                # ROLLBACK si algo falló
                try:
                    conn.rollback()
                except Exception:
                    pass
                return {"status": "error", "message": f"Error al actualizar pago: {ex}"}

        # Intento 2: si no hay conexión directa pero existe helper `execute`
        if hasattr(self, "execute") and callable(getattr(self, "execute")):
            try:
                # No podemos garantizar transacción aquí; hacemos operaciones básicas.
                if descuentos is not None:
                    imss = _to_float(descuentos.get("monto_imss", descuentos.get("imss", 0)))
                    transporte = _to_float(descuentos.get("monto_transporte", descuentos.get("transporte", 0)))
                    extra = _to_float(descuentos.get("monto_extra", descuentos.get("extra", 0)))
                    total_desc = round(imss + transporte + extra, 2)

                    self.execute("DELETE FROM descuentos WHERE id_pago_nomina = ?", (id_pago,))
                    self.execute(
                        """
                        INSERT INTO descuentos
                            (id_pago_nomina, monto_imss, monto_transporte, monto_extra, total_descuentos, updated_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (id_pago, imss, transporte, extra, total_desc),
                    )

                if estado is not None and deposito is not None:
                    self.execute(
                        "UPDATE pagos_nomina SET estado=?, pago_deposito=?, updated_at=CURRENT_TIMESTAMP WHERE id_pago_nomina=?",
                        (estado, float(deposito), id_pago),
                    )
                elif estado is not None:
                    self.execute(
                        "UPDATE pagos_nomina SET estado=?, updated_at=CURRENT_TIMESTAMP WHERE id_pago_nomina=?",
                        (estado, id_pago),
                    )
                elif deposito is not None:
                    self.execute(
                        "UPDATE pagos_nomina SET pago_deposito=?, updated_at=CURRENT_TIMESTAMP WHERE id_pago_nomina=?",
                        (float(deposito), id_pago),
                    )

                return {"status": "success", "message": "Pago actualizado correctamente."}
            except Exception as ex:
                return {"status": "error", "message": f"Error al actualizar pago: {ex}"}

        # Si no hay forma de escribir, reportamos no-op claro
        return {
            "status": "error",
            "message": "No hay conexión/cursor ni helper 'execute' disponibles en PaymentModel.",
        }
