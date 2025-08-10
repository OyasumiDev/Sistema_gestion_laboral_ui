from datetime import datetime
from app.core.interfaces.database_mysql import DatabaseMysql
from app.core.enums.e_prestamos_model import E_PRESTAMOS
from app.core.enums.e_pagos_prestamos import E_PAGOS_PRESTAMO


class LoanModel:
    """
    Modelo de préstamos: múltiples préstamos por empleado.
    """

    def __init__(self):
        self.db = DatabaseMysql()
        self.E = E_PRESTAMOS
        self._exists_table = self.check_table()

    # ---------------------------------------------------------------------
    # Infra / Esquema
    # ---------------------------------------------------------------------
    def check_table(self) -> bool:
        """Verifica si la tabla de préstamos existe y la crea si no."""
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(query, (self.db.database, self.E.TABLE_PRESTAMOS.value), dictionary=True)
            count = result.get("c", 0)

            if count == 0:
                print(f"⚠️ La tabla {self.E.TABLE_PRESTAMOS.value} no existe. Creando...")

                create_query = f"""
                CREATE TABLE {self.E.TABLE_PRESTAMOS.value} (
                    {self.E.PRESTAMO_ID.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {self.E.PRESTAMO_NUMERO_NOMINA.value} SMALLINT UNSIGNED NOT NULL,
                    {self.E.PRESTAMO_NOMBRE_EMPLEADO.value} VARCHAR(100),
                    {self.E.PRESTAMO_GRUPO_EMPLEADO.value} VARCHAR(150),
                    {self.E.PRESTAMO_MONTO.value} DECIMAL(10,2) NOT NULL,
                    {self.E.PRESTAMO_SALDO.value} DECIMAL(10,2) NOT NULL,
                    {self.E.PRESTAMO_ESTADO.value} ENUM('pagando','terminado') NOT NULL,
                    {self.E.PRESTAMO_FECHA_SOLICITUD.value} DATE NOT NULL,
                    {self.E.PRESTAMO_FECHA_CIERRE.value} DATE,
                    {self.E.PRESTAMO_FECHA_CREACION.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    {self.E.PRESTAMO_FECHA_MODIFICACION.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY ({self.E.PRESTAMO_NUMERO_NOMINA.value}) REFERENCES empleados({self.E.PRESTAMO_NUMERO_NOMINA.value}) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {self.E.TABLE_PRESTAMOS.value} creada correctamente.")
            else:
                print(f"✔️ La tabla {self.E.TABLE_PRESTAMOS.value} ya existe.")
            return True
        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {self.E.TABLE_PRESTAMOS.value}: {ex}")
            return False

    # ---------------------------------------------------------------------
    # Inserción (compat con el contenedor)
    # ---------------------------------------------------------------------
    def insert(self, datos: dict) -> dict:
        """
        Inserta un préstamo a partir de un dict.
        Espera, al menos: numero_nomina (int), monto (float), fecha_solicitud (YYYY-MM-DD).
        Opcional: saldo (float). El estado por defecto es 'pagando'.
        """
        try:
            numero_nomina = int(datos["numero_nomina"])
            monto = float(datos["monto"])
            saldo = float(datos.get("saldo", monto))
            fecha = datos.get("fecha_solicitud") or datetime.today().strftime("%Y-%m-%d")
        except Exception as ex:
            return {"status": "error", "message": f"Datos inválidos para insertar préstamo: {ex}"}

        # delegamos en el método nativo
        return self.add(
            numero_nomina=numero_nomina,
            monto_prestamo=monto,
            saldo_prestamo=saldo,
            estado="pagando",
            fecha_solicitud=fecha,
        )

    # Alias por si en algún lado llaman distinto
    def insert_prestamo(self, datos: dict) -> dict:
        return self.insert(datos)

    # ---------------------------------------------------------------------
    # Inserción "nativa" existente
    # ---------------------------------------------------------------------
    def add(self, numero_nomina, monto_prestamo, saldo_prestamo=None, estado="pagando", fecha_solicitud=None):
        """
        Inserta un préstamo construyendo nombre_empleado y grupo a partir de empleados.
        """
        try:
            # 1) Nombre / grupo
            empleado_query = "SELECT nombre_completo FROM empleados WHERE numero_nomina = %s"
            empleado_result = self.db.get_data(empleado_query, (numero_nomina,), dictionary=True)
            if not empleado_result or not empleado_result.get("nombre_completo"):
                return {"status": "error", "message": "Empleado no encontrado para el número de nómina proporcionado"}

            nombre_empleado = empleado_result["nombre_completo"]
            grupo = f"{numero_nomina} - {nombre_empleado}"

            # 2) Siguiente id (seguimos tu estilo actual)
            query_id = f"SELECT MAX({self.E.PRESTAMO_ID.value}) AS max_id FROM {self.E.TABLE_PRESTAMOS.value}"
            result = self.db.get_data(query_id, dictionary=True)
            next_id = (result.get("max_id") or 0) + 1

            # 3) Valores
            saldo = saldo_prestamo if saldo_prestamo is not None else float(monto_prestamo)
            fecha = fecha_solicitud or datetime.today().strftime("%Y-%m-%d")

            # 4) Insert
            query = f"""
                INSERT INTO {self.E.TABLE_PRESTAMOS.value} (
                    {self.E.PRESTAMO_ID.value},
                    {self.E.PRESTAMO_NUMERO_NOMINA.value},
                    {self.E.PRESTAMO_NOMBRE_EMPLEADO.value},
                    {self.E.PRESTAMO_GRUPO_EMPLEADO.value},
                    {self.E.PRESTAMO_MONTO.value},
                    {self.E.PRESTAMO_SALDO.value},
                    {self.E.PRESTAMO_ESTADO.value},
                    {self.E.PRESTAMO_FECHA_SOLICITUD.value}
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(
                query,
                (
                    next_id,
                    numero_nomina,
                    nombre_empleado,
                    grupo,
                    float(monto_prestamo),
                    float(saldo),
                    estado,
                    fecha,
                ),
            )
            return {"status": "success", "message": "Préstamo registrado correctamente", "id": next_id}
        except Exception as ex:
            return {"status": "error", "message": f"Error al registrar el préstamo: {ex}"}

    # ---------------------------------------------------------------------
    # Lecturas
    # ---------------------------------------------------------------------
    def get_all(self):
        try:
            query = f"SELECT * FROM {self.E.TABLE_PRESTAMOS.value}"
            result = self.db.get_data_list(query, dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener préstamos: {ex}"}

    def get_by_id(self, id_prestamo: int):
        try:
            query = f"""
                SELECT * FROM {self.E.TABLE_PRESTAMOS.value}
                WHERE {self.E.PRESTAMO_ID.value} = %s
            """
            result = self.db.get_data(query, (id_prestamo,), dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener el préstamo: {ex}"}

    def get_by_empleado(self, numero_nomina: int):
        try:
            query = f"""
                SELECT * FROM {self.E.TABLE_PRESTAMOS.value}
                WHERE {self.E.PRESTAMO_NUMERO_NOMINA.value} = %s
            """
            result = self.db.get_data_list(query, (numero_nomina,), dictionary=True)
            return {"status": "success", "data": result}
        except Exception as ex:
            return {"status": "error", "message": f"Error al obtener préstamos del empleado: {ex}"}

    def get_prestamo_activo_por_empleado(self, numero_nomina: int):
        try:
            query = f"""
                SELECT *
                FROM {self.E.TABLE_PRESTAMOS.value}
                WHERE {self.E.PRESTAMO_NUMERO_NOMINA.value} = %s
                AND {self.E.PRESTAMO_ESTADO.value} = 'pagando'
                LIMIT 1
            """
            result = self.db.get_data(query, (numero_nomina,), dictionary=True)
            return result if result else None
        except Exception as ex:
            print(f"❌ Error al verificar préstamo activo: {ex}")
            return None

    def get_agrupado_por_empleado(self):
        try:
            query = f"""
                SELECT p.*, e.nombre_completo AS nombre_empleado
                FROM {self.E.TABLE_PRESTAMOS.value} p
                JOIN empleados e ON p.{self.E.PRESTAMO_NUMERO_NOMINA.value} = e.numero_nomina
                ORDER BY p.{self.E.PRESTAMO_NUMERO_NOMINA.value}, p.{self.E.PRESTAMO_FECHA_SOLICITUD.value}
            """
            prestamos = self.db.get_data_list(query, dictionary=True)
            agrupado = {}
            for p in prestamos:
                num = p["numero_nomina"]
                if num not in agrupado:
                    agrupado[num] = {
                        "numero_nomina": num,
                        "nombre_empleado": p["nombre_empleado"],
                        "prestamos_abiertos": 0,
                        "prestamos": [],
                    }
                if p["estado"] == "pagando":
                    agrupado[num]["prestamos_abiertos"] += 1
                agrupado[num]["prestamos"].append(p)

            resultado = sorted(
                agrupado.values(),
                key=lambda x: (-x["prestamos_abiertos"], x["nombre_empleado"]),
            )
            return {"status": "success", "data": resultado}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_prestamos_por_empleado(self, numero_nomina: int) -> list:
        p = self.E
        query = f"""
            SELECT {p.PRESTAMO_ID.value}, {p.PRESTAMO_SALDO.value}, {p.PRESTAMO_ESTADO.value}
            FROM {p.TABLE_PRESTAMOS.value}
            WHERE {p.PRESTAMO_NUMERO_NOMINA.value} = %s
            ORDER BY {p.PRESTAMO_FECHA_SOLICITUD.value} DESC
        """
        return self.db.get_data_list(query, (numero_nomina,), dictionary=True)

    def get_total_prestamos_por_empleado(self, numero_nomina: int, fecha_pago: str) -> float:
        try:
            pp = E_PAGOS_PRESTAMO
            p = self.E  # E_PRESTAMOS
            query = f"""
                SELECT COALESCE(SUM(pp.{pp.PAGO_MONTO_PAGADO.value}), 0) AS total
                FROM {pp.TABLE_PAGOS_PRESTAMOS.value} pp
                JOIN {p.TABLE_PRESTAMOS.value} p ON pp.{pp.ID_PRESTAMO.value} = p.{p.PRESTAMO_ID.value}
                WHERE p.{p.PRESTAMO_ESTADO.value} = 'pagando'
                AND p.{p.PRESTAMO_NUMERO_NOMINA.value} = %s
                AND pp.{pp.PAGO_FECHA_PAGO.value} = %s
            """
            result = self.db.get_data(query, (numero_nomina, fecha_pago), dictionary=True)
            return float(result.get("total", 0.0)) if result else 0.0
        except Exception as ex:
            print(f"❌ Error al obtener préstamos por empleado: {ex}")
            return 0.0


    def get_next_id_prestamo(self):
        try:
            query = """
                SELECT AUTO_INCREMENT
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """
            result = self.db.get_data(query, (self.db.database, self.E.TABLE_PRESTAMOS.value), dictionary=True)
            return result.get("AUTO_INCREMENT", None)
        except Exception as ex:
            print(f"❌ Error al obtener el siguiente ID de préstamo: {ex}")
            return None

    # ---------------------------------------------------------------------
    # Actualización / Borrado
    # ---------------------------------------------------------------------
    def update_by_id_prestamo(self, id_prestamo: int, campos: dict):
        """
        NOTA: aquí `campos` debe usar llaves del Enum E_PRESTAMOS (no strings),
        p.ej.: { E_PRESTAMOS.PRESTAMO_ESTADO: 'terminado' }
        """
        try:
            if not campos:
                return {"status": "error", "message": "No se proporcionaron campos para actualizar"}

            # Autocerrar con fecha si cambia a 'terminado'
            if self.E.PRESTAMO_ESTADO in campos and campos[self.E.PRESTAMO_ESTADO] == "terminado":
                campos[self.E.PRESTAMO_FECHA_CIERRE] = datetime.today().strftime("%Y-%m-%d")

            campos_sql = ", ".join(f"{k.value} = %s" for k in campos.keys())
            valores = list(campos.values())

            query = f"""
                UPDATE {self.E.TABLE_PRESTAMOS.value}
                SET {campos_sql}
                WHERE {self.E.PRESTAMO_ID.value} = %s
            """
            valores.append(id_prestamo)
            self.db.run_query(query, tuple(valores))

            return {"status": "success", "message": "Préstamo actualizado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al actualizar el préstamo: {ex}"}

    def delete_by_id_prestamo(self, id_prestamo: int):
        try:
            query = f"""
                DELETE FROM {self.E.TABLE_PRESTAMOS.value}
                WHERE {self.E.PRESTAMO_ID.value} = %s
            """
            self.db.run_query(query, (id_prestamo,))
            return {"status": "success", "message": f"Préstamo ID {id_prestamo} eliminado correctamente"}
        except Exception as ex:
            return {"status": "error", "message": f"Error al eliminar el préstamo: {ex}"}
