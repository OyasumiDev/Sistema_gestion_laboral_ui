"""
AssistanceModel (refactor) — “a prueba de balas” (autosave + edición robustos)

✅ Cambios clave para que NO se “rompan” tiempos/estado en DB:

1) TRIGGER BEFORE UPDATE: ya NO pisa tiempos a '00:00:00' cuando el update NO trae horas válidas.
   - Si las horas NO cambiaron (ej. autosave de descanso), conserva OLD.tiempo_trabajo / OLD.tiempo_trabajo_con_descanso.
   - Si las horas SÍ cambiaron pero quedaron inválidas, entonces sí resetea tiempos a '00:00:00'.

2) update_asistencia() ahora NO borra horas por accidente:
   - Si llega "" (string vacío) desde UI, por defecto NO actualiza esa hora (la ignora).
   - Si quieres borrar horas intencionalmente, manda: registro["clear_horas"] = True
     (o "clear_hora_entrada"/"clear_hora_salida" = True).

3) add() y updates usan parseo “nullable”:
   - Si hora no es válida o es 00:00 => se guarda NULL (no '00:00:00') para evitar falsos “completos”.
   - Para asistencias, medianoche como hora real normalmente no aplica (si la ocupas, avísame y lo ajustamos).

4) update_descanso() opcionalmente retorna la fila ya recalculada leyendo DB (para refresco inmediato de UI).

Nota: Con triggers, la DB es la fuente de verdad. Lo ideal: tras cualquier update, re-leer del SELECT.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, time
from typing import Any, Dict, List, Optional, Tuple, Union

from app.core.app_state import AppState
from app.core.enums.e_assistance_model import E_ASSISTANCE
from app.core.interfaces.database_mysql import DatabaseMysql
from app.models.payment_model import PaymentModel

DateLike = Union[str, date, datetime]
TimeLike = Union[str, time, timedelta, None]


class AssistanceModel:
    def __init__(self) -> None:
        self.db = DatabaseMysql()
        self.payment_model = PaymentModel()

        self._exists_table = self.check_table()
        self.verificar_o_crear_triggers()

    # ---------------------------------------------------------------------
    # PubSub (UI)
    # ---------------------------------------------------------------------
    def _publish_pagamentos_delta(self, numero_nomina: int, periodo_ini: str, periodo_fin: str) -> None:
        """Publica un evento para que Pagos refresque incrementalmente."""
        try:
            page = AppState().page
            if not page:
                return
            pubsub = getattr(page, "pubsub", None)
            if not pubsub:
                return

            payload = {
                "id_empleado": int(numero_nomina),
                "periodo_ini": str(periodo_ini),
                "periodo_fin": str(periodo_fin),
            }

            if hasattr(pubsub, "publish"):
                pubsub.publish("asistencias:changed", payload)
            elif hasattr(pubsub, "send_all"):
                pubsub.send_all("asistencias:changed", payload)
        except Exception:
            return

    def _publish_pagos_delta(self, numero_nomina: int, periodo_ini: str, periodo_fin: str) -> None:
        self._publish_pagamentos_delta(numero_nomina, periodo_ini, periodo_fin)

    # ---------------------------------------------------------------------
    # Helpers: fecha / hora / descanso
    # ---------------------------------------------------------------------
    def _convertir_fecha_a_mysql(self, fecha: DateLike) -> str:
        """Acepta 'DD/MM/YYYY', 'YYYY-MM-DD', datetime/date. Retorna 'YYYY-MM-DD'."""
        try:
            if isinstance(fecha, datetime):
                return fecha.strftime("%Y-%m-%d")
            if isinstance(fecha, date):
                return fecha.strftime("%Y-%m-%d")

            s = str(fecha).strip()
            if not s:
                return s

            if "/" in s:
                return datetime.strptime(s, "%d/%m/%Y").strftime("%Y-%m-%d")
            return s
        except Exception as e:
            print(f"❌ Error formateando fecha para MySQL '{fecha}': {e}")
            return str(fecha)

    def _formatear_fecha(self, fecha_sql: str) -> str:
        """Convierte 'YYYY-MM-DD' a 'DD/MM/YYYY' si es posible."""
        try:
            return datetime.strptime(str(fecha_sql), "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return str(fecha_sql)

    def _mapear_descanso_str_a_int(self, descanso_str: str) -> int:
        """
        SN=0, MD=1, CMP=2.
        ✅ Si viene vacío/NULL => MD (1).
        """
        s = str(descanso_str).strip().upper()
        if s in ("", "NONE", "NULL"):
            return 1  # default MD
        if s in ("0", "SN", "SIN"):
            return 0
        if s in ("1", "MD", "MEDIO"):
            return 1
        if s in ("2", "CMP", "COMIDA", "COMPLETO"):
            return 2
        return 1

    def _mapear_descanso_a_int(self, descanso: Any) -> int:
        """Acepta int(0/1/2) o string. ✅ default MD."""
        try:
            if descanso is None:
                return 1
            if isinstance(descanso, int):
                return descanso if descanso in (0, 1, 2) else 1
            return self._mapear_descanso_str_a_int(descanso)
        except Exception:
            return 1

    def _parse_hora_nullable(self, hora: TimeLike) -> Optional[str]:
        """
        Normaliza hora a 'HH:MM:SS' o None.
        ✅ None si viene vacío / inválido / 00:00(:00).
        """
        if hora is None:
            return None

        try:
            if isinstance(hora, time):
                s = hora.strftime("%H:%M:%S")
                return None if s in ("00:00:00", "0:00:00") else s

            if isinstance(hora, timedelta):
                s = (datetime.min + hora).time().strftime("%H:%M:%S")
                return None if s in ("00:00:00", "0:00:00") else s

            if isinstance(hora, str):
                s = hora.strip()
                if not s:
                    return None
                for fmt in ("%H:%M:%S", "%H:%M"):
                    try:
                        out = datetime.strptime(s, fmt).strftime("%H:%M:%S")
                        return None if out in ("00:00:00", "0:00:00") else out
                    except Exception:
                        continue
                return None

            return None
        except Exception:
            return None

    def _parse_tiempo_manual(self, v: Any) -> Optional[str]:
        """
        Acepta HH:MM[:SS] o decimal de horas y lo normaliza a HH:MM:SS.
        """
        if v is None:
            return None
        try:
            if isinstance(v, (int, float)):
                total_min = int(round(float(v) * 60))
                hh = total_min // 60
                mm = total_min % 60
                return f"{hh:02}:{mm:02}:00"
            s = str(v).strip()
            if not s:
                return None
            if ":" in s:
                return self._parse_hora_nullable(s)
            try:
                f = float(s)
                total_min = int(round(f * 60))
                hh = total_min // 60
                mm = total_min % 60
                return f"{hh:02}:{mm:02}:00"
            except Exception:
                return None
        except Exception:
            return None

    @staticmethod
    def _truthy(v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        s = str(v).strip().lower()
        return s in ("1", "true", "t", "yes", "y", "si", "sí", "on")

    def _mapear_fila_asistencia(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza para UI:
        - fecha => DD/MM/YYYY
        - descanso => SN/MD/CMP (✅ default MD)
        - NO inventa tiempos: renderiza lo que venga de DB (triggers = verdad)
        """
        try:
            descanso_map = {0: "SN", 1: "MD", 2: "CMP"}

            if "fecha" in row and row["fecha"] is not None:
                row["fecha"] = self._formatear_fecha(str(row["fecha"]))

            raw_desc = row.get(E_ASSISTANCE.DESCANSO.value, None)
            if raw_desc is None or str(raw_desc).strip() == "":
                raw_desc = 1
            try:
                raw_desc_int = int(raw_desc)
            except Exception:
                raw_desc_int = 1
            row["descanso"] = descanso_map.get(raw_desc_int, "MD")

            # DB es la verdad: si viene null/vacío, mostramos 00:00:00 por UI
            for k in (E_ASSISTANCE.TIEMPO_TRABAJO.value, E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value):
                val = row.get(k, None)
                if val is None or str(val).strip() == "":
                    row[k] = "00:00:00"

            return row
        except Exception as e:
            print(f"❌ Error al mapear fila asistencia: {e}")
            return row

    # ---------------------------------------------------------------------
    # Tabla / migración ligera de columnas
    # ---------------------------------------------------------------------
    def check_table(self) -> bool:
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """
            result = self.db.get_data(
                query,
                (self.db.database, E_ASSISTANCE.TABLE.value),
                dictionary=True
            ) or {}
            existe = (result.get("c") or 0) > 0

            if not existe:
                print(f"⚠️ La tabla {E_ASSISTANCE.TABLE.value} no existe. Creando...")

                create_query = f"""
                CREATE TABLE IF NOT EXISTS {E_ASSISTANCE.TABLE.value} (
                    {E_ASSISTANCE.ID_ASISTENCIA.value} INT AUTO_INCREMENT PRIMARY KEY,
                    {E_ASSISTANCE.NUMERO_NOMINA.value} SMALLINT UNSIGNED NOT NULL,
                    {E_ASSISTANCE.FECHA.value} DATE NOT NULL,
                    {E_ASSISTANCE.HORA_ENTRADA.value} TIME NULL,
                    {E_ASSISTANCE.HORA_SALIDA.value} TIME NULL,

                    {E_ASSISTANCE.DESCANSO.value} TINYINT NOT NULL DEFAULT 1,

                    {E_ASSISTANCE.ESTADO.value} VARCHAR(20),

                    {E_ASSISTANCE.TIEMPO_TRABAJO.value} TIME DEFAULT '00:00:00',
                    {E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value} TIME DEFAULT '00:00:00',

                    {E_ASSISTANCE.FECHA_GENERADA.value} DATE DEFAULT NULL,
                    {E_ASSISTANCE.GRUPO_IMPORTACION.value} VARCHAR(150) DEFAULT NULL,

                    FOREIGN KEY ({E_ASSISTANCE.NUMERO_NOMINA.value})
                        REFERENCES empleados(numero_nomina)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                self.db.run_query(create_query)
                print(f"✅ Tabla {E_ASSISTANCE.TABLE.value} creada correctamente.")

            else:
                columnas_requeridas = {
                    E_ASSISTANCE.DESCANSO.value: "TINYINT NOT NULL DEFAULT 1",
                    E_ASSISTANCE.GRUPO_IMPORTACION.value: "VARCHAR(150) DEFAULT NULL",
                    E_ASSISTANCE.TIEMPO_TRABAJO.value: "TIME DEFAULT '00:00:00'",
                    E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value: "TIME DEFAULT '00:00:00'",
                    E_ASSISTANCE.FECHA_GENERADA.value: "DATE DEFAULT NULL",
                }

                for columna, tipo in columnas_requeridas.items():
                    check_col_query = """
                        SELECT COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s AND column_name = %s
                    """
                    col_result = self.db.get_data(
                        check_col_query,
                        (self.db.database, E_ASSISTANCE.TABLE.value, columna),
                        dictionary=True,
                    )

                    if not col_result:
                        alter_query = f"ALTER TABLE {E_ASSISTANCE.TABLE.value} ADD COLUMN {columna} {tipo}"
                        self.db.run_query(alter_query)
                        print(f"🛠️ Columna '{columna}' agregada como {tipo}.")
                        continue

                    current_type = str(col_result.get("COLUMN_TYPE", "")).upper()
                    current_nullable = str(col_result.get("IS_NULLABLE", "")).upper()
                    current_default = col_result.get("COLUMN_DEFAULT", None)

                    expected_type = str(tipo).upper()
                    base_expected = expected_type.split()[0]

                    if base_expected not in current_type:
                        alter_query = f"ALTER TABLE {E_ASSISTANCE.TABLE.value} MODIFY COLUMN {columna} {tipo}"
                        self.db.run_query(alter_query)
                        print(f"🔄 Columna '{columna}' actualizada a {tipo}.")
                        continue

                    if columna == E_ASSISTANCE.DESCANSO.value:
                        needs_fix = False
                        if "NOT NULL" in expected_type and current_nullable == "YES":
                            needs_fix = True
                        if current_default is None or str(current_default) != "1":
                            needs_fix = True
                        if needs_fix:
                            alter_query = f"ALTER TABLE {E_ASSISTANCE.TABLE.value} MODIFY COLUMN {columna} {tipo}"
                            self.db.run_query(alter_query)
                            print(f"🔄 Columna '{columna}' forzada a {tipo}.")

            return True

        except Exception as ex:
            print(f"❌ Error al verificar/crear la tabla {E_ASSISTANCE.TABLE.value}: {ex}")
            return False

    # ---------------------------------------------------------------------
    # Triggers
    # ---------------------------------------------------------------------
    def verificar_o_crear_triggers(self) -> None:
        """Idempotente: DROP IF EXISTS + CREATE."""
        try:
            self._crear_trigger_calculo_horas()
            self._crear_trigger_actualizar_horas()
            self._crear_triggers_estado()
        except Exception as ex:
            print(f"❌ Error al verificar/crear triggers: {ex}")

    def _get_connection(self):
        conn = getattr(self.db, "connection", None)
        if conn is not None:
            return conn

        try:
            if hasattr(self.db, "connect"):
                self.db.connect()
            elif hasattr(self.db, "_connect"):
                self.db._connect()
            elif hasattr(self.db, "get_connection"):
                conn = self.db.get_connection()
                try:
                    setattr(self.db, "connection", conn)
                except Exception:
                    pass
                return conn
        except Exception:
            pass

        conn = getattr(self.db, "connection", None)
        if conn is None:
            raise RuntimeError(
                "DatabaseMysql no expone 'connection' y no se pudo auto-conectar. "
                "Solución: asegúrate de que DatabaseMysql cree self.connection o provea connect()/get_connection()."
            )
        return conn

    def _get_cursor(self):
        return self._get_connection().cursor()

    def _crear_trigger_calculo_horas(self) -> None:
        trigger_name = "trg_calcular_horas_trabajadas"
        try:
            cursor = self._get_cursor()
            cursor.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")

            table = E_ASSISTANCE.TABLE.value

            trigger_sql = f"""
            CREATE TRIGGER {trigger_name}
            BEFORE INSERT ON {table}
            FOR EACH ROW
            BEGIN
                DECLARE minutos_descanso INT DEFAULT 30;
                DECLARE minutos_trabajo INT DEFAULT 0;

                IF NEW.{E_ASSISTANCE.DESCANSO.value} IS NULL THEN
                    SET NEW.{E_ASSISTANCE.DESCANSO.value} = 1;
                END IF;

                IF NEW.{E_ASSISTANCE.HORA_ENTRADA.value} IS NOT NULL
                AND NEW.{E_ASSISTANCE.HORA_SALIDA.value} IS NOT NULL
                AND NEW.{E_ASSISTANCE.HORA_ENTRADA.value} NOT IN ('00:00:00','0:00:00')
                AND NEW.{E_ASSISTANCE.HORA_SALIDA.value}  NOT IN ('00:00:00','0:00:00')
                AND TIMEDIFF(NEW.{E_ASSISTANCE.HORA_SALIDA.value}, NEW.{E_ASSISTANCE.HORA_ENTRADA.value}) > '00:00:00'
                THEN
                    SET minutos_trabajo = TIME_TO_SEC(TIMEDIFF(
                        NEW.{E_ASSISTANCE.HORA_SALIDA.value},
                        NEW.{E_ASSISTANCE.HORA_ENTRADA.value}
                    )) / 60;

                    IF NEW.{E_ASSISTANCE.DESCANSO.value} = 2 THEN
                        SET minutos_descanso = 60;
                    ELSEIF NEW.{E_ASSISTANCE.DESCANSO.value} = 1 THEN
                        SET minutos_descanso = 30;
                    ELSE
                        SET minutos_descanso = 0;
                    END IF;

                    SET NEW.{E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value} =
                        SEC_TO_TIME(minutos_trabajo * 60);

                    SET minutos_trabajo = GREATEST(0, minutos_trabajo - minutos_descanso);
                    SET NEW.{E_ASSISTANCE.TIEMPO_TRABAJO.value} =
                        SEC_TO_TIME(minutos_trabajo * 60);
                ELSE
                    SET NEW.{E_ASSISTANCE.TIEMPO_TRABAJO.value} = '00:00:00';
                    SET NEW.{E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value} = '00:00:00';
                END IF;
            END;
            """
            cursor.execute(trigger_sql)
            self._get_connection().commit()
            cursor.close()
            print(f"✅ Trigger '{trigger_name}' creado/recreado correctamente.")
        except Exception as ex:
            print(f"❌ Error al crear trigger '{trigger_name}': {ex}")

    def _crear_trigger_actualizar_horas(self) -> None:
        trigger_name = "trg_actualizar_horas_trabajadas"
        try:
            cursor = self._get_cursor()
            cursor.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")

            table = E_ASSISTANCE.TABLE.value

            # ✅ CAMBIO CRÍTICO: si NO hay horas válidas:
            # - si horas NO cambiaron => preservar tiempos OLD (autosave descanso)
            # - si horas SÍ cambiaron => reset a 00:00:00
            trigger_sql = f"""
            CREATE TRIGGER {trigger_name}
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            BEGIN
                DECLARE minutos_descanso INT DEFAULT 30;
                DECLARE minutos_trabajo INT DEFAULT 0;
                DECLARE horas_iguales BOOL DEFAULT FALSE;
                DECLARE manual_override BOOL DEFAULT FALSE;

                IF NEW.{E_ASSISTANCE.DESCANSO.value} IS NULL THEN
                    SET NEW.{E_ASSISTANCE.DESCANSO.value} = 1;
                END IF;

                SET horas_iguales =
                    (NEW.{E_ASSISTANCE.HORA_ENTRADA.value} <=> OLD.{E_ASSISTANCE.HORA_ENTRADA.value})
                    AND
                    (NEW.{E_ASSISTANCE.HORA_SALIDA.value} <=> OLD.{E_ASSISTANCE.HORA_SALIDA.value});

                SET manual_override =
                    (NEW.{E_ASSISTANCE.TIEMPO_TRABAJO.value} IS NOT NULL)
                    AND (NEW.{E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value} IS NOT NULL)
                    AND (
                        NEW.{E_ASSISTANCE.TIEMPO_TRABAJO.value} <> OLD.{E_ASSISTANCE.TIEMPO_TRABAJO.value}
                        OR NEW.{E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value} <> OLD.{E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value}
                    );

                IF manual_override THEN
                    -- Respeta tiempos manuales
                    SET NEW.{E_ASSISTANCE.TIEMPO_TRABAJO.value} = NEW.{E_ASSISTANCE.TIEMPO_TRABAJO.value};
                    SET NEW.{E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value} = NEW.{E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value};
                ELSEIF NEW.{E_ASSISTANCE.HORA_ENTRADA.value} IS NOT NULL
                AND NEW.{E_ASSISTANCE.HORA_SALIDA.value} IS NOT NULL
                AND NEW.{E_ASSISTANCE.HORA_ENTRADA.value} NOT IN ('00:00:00','0:00:00')
                AND NEW.{E_ASSISTANCE.HORA_SALIDA.value}  NOT IN ('00:00:00','0:00:00')
                AND TIMEDIFF(NEW.{E_ASSISTANCE.HORA_SALIDA.value}, NEW.{E_ASSISTANCE.HORA_ENTRADA.value}) > '00:00:00'
                THEN
                    SET minutos_trabajo = TIME_TO_SEC(TIMEDIFF(
                        NEW.{E_ASSISTANCE.HORA_SALIDA.value},
                        NEW.{E_ASSISTANCE.HORA_ENTRADA.value}
                    )) / 60;

                    IF NEW.{E_ASSISTANCE.DESCANSO.value} = 2 THEN
                        SET minutos_descanso = 60;
                    ELSEIF NEW.{E_ASSISTANCE.DESCANSO.value} = 1 THEN
                        SET minutos_descanso = 30;
                    ELSE
                        SET minutos_descanso = 0;
                    END IF;

                    SET NEW.{E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value} =
                        SEC_TO_TIME(minutos_trabajo * 60);

                    SET minutos_trabajo = GREATEST(0, minutos_trabajo - minutos_descanso);
                    SET NEW.{E_ASSISTANCE.TIEMPO_TRABAJO.value} =
                        SEC_TO_TIME(minutos_trabajo * 60);
                ELSE
                    IF horas_iguales THEN
                        -- ✅ autosave descanso (o update parcial sin horas): preservar lo ya calculado
                        SET NEW.{E_ASSISTANCE.TIEMPO_TRABAJO.value} = OLD.{E_ASSISTANCE.TIEMPO_TRABAJO.value};
                        SET NEW.{E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value} = OLD.{E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value};
                    ELSE
                        -- ✅ horas cambiaron y quedaron inválidas: resetea
                        SET NEW.{E_ASSISTANCE.TIEMPO_TRABAJO.value} = '00:00:00';
                        SET NEW.{E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value} = '00:00:00';
                    END IF;
                END IF;
            END;
            """
            cursor.execute(trigger_sql)
            self._get_connection().commit()
            cursor.close()
            print(f"✅ Trigger '{trigger_name}' creado/recreado correctamente.")
        except Exception as ex:
            print(f"❌ Error al crear trigger '{trigger_name}': {ex}")

    def _crear_triggers_estado(self) -> None:
        table = E_ASSISTANCE.TABLE.value
        try:
            cursor = self._get_cursor()

            trigger_bi = "trg_verificar_estado_asistencia_bi"
            cursor.execute(f"DROP TRIGGER IF EXISTS {trigger_bi}")
            trigger_sql_bi = f"""
            CREATE TRIGGER {trigger_bi}
            BEFORE INSERT ON {table}
            FOR EACH ROW
            BEGIN
                IF NEW.{E_ASSISTANCE.HORA_ENTRADA.value} IS NULL OR NEW.{E_ASSISTANCE.HORA_SALIDA.value} IS NULL
                OR NEW.{E_ASSISTANCE.HORA_ENTRADA.value} IN ('00:00:00','0:00:00')
                OR NEW.{E_ASSISTANCE.HORA_SALIDA.value}  IN ('00:00:00','0:00:00')
                OR TIMEDIFF(NEW.{E_ASSISTANCE.HORA_SALIDA.value}, NEW.{E_ASSISTANCE.HORA_ENTRADA.value}) <= '00:00:00' THEN
                    SET NEW.{E_ASSISTANCE.ESTADO.value} = 'incompleto';
                ELSE
                    SET NEW.{E_ASSISTANCE.ESTADO.value} = 'completo';
                END IF;
            END;
            """
            cursor.execute(trigger_sql_bi)

            trigger_bu = "trg_verificar_estado_asistencia_bu"
            cursor.execute(f"DROP TRIGGER IF EXISTS {trigger_bu}")
            trigger_sql_bu = f"""
            CREATE TRIGGER {trigger_bu}
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            BEGIN
                DECLARE manual_override BOOL DEFAULT FALSE;

                SET manual_override =
                    (NEW.{E_ASSISTANCE.TIEMPO_TRABAJO.value} IS NOT NULL)
                    AND (NEW.{E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value} IS NOT NULL)
                    AND (
                        NEW.{E_ASSISTANCE.TIEMPO_TRABAJO.value} <> OLD.{E_ASSISTANCE.TIEMPO_TRABAJO.value}
                        OR NEW.{E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value} <> OLD.{E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value}
                    );

                IF manual_override THEN
                    IF NEW.{E_ASSISTANCE.ESTADO.value} IS NULL THEN
                        SET NEW.{E_ASSISTANCE.ESTADO.value} = 'completo';
                    END IF;
                ELSEIF NEW.{E_ASSISTANCE.HORA_ENTRADA.value} IS NULL OR NEW.{E_ASSISTANCE.HORA_SALIDA.value} IS NULL
                OR NEW.{E_ASSISTANCE.HORA_ENTRADA.value} IN ('00:00:00','0:00:00')
                OR NEW.{E_ASSISTANCE.HORA_SALIDA.value}  IN ('00:00:00','0:00:00')
                OR TIMEDIFF(NEW.{E_ASSISTANCE.HORA_SALIDA.value}, NEW.{E_ASSISTANCE.HORA_ENTRADA.value}) <= '00:00:00' THEN
                    SET NEW.{E_ASSISTANCE.ESTADO.value} = 'incompleto';
                ELSE
                    SET NEW.{E_ASSISTANCE.ESTADO.value} = 'completo';
                END IF;
            END;
            """
            cursor.execute(trigger_sql_bu)

            self._get_connection().commit()
            cursor.close()
            print("✅ Triggers de estado creados/recreados correctamente.")
        except Exception as ex:
            print(f"❌ Error al crear triggers de estado: {ex}")

    # ---------------------------------------------------------------------
    # Queries / operaciones
    # ---------------------------------------------------------------------
    def collect_ranges_for_period(
        self,
        periodo_ini: str,
        periodo_fin: str,
        id_empleado: Optional[int] = None,
    ) -> List[Tuple[int, str, str]]:
        condiciones: List[str] = []
        params: List[Any] = []

        if periodo_ini and periodo_fin:
            condiciones.append(f"{E_ASSISTANCE.FECHA.value} BETWEEN %s AND %s")
            params.extend([periodo_ini, periodo_fin])
        elif periodo_ini:
            condiciones.append(f"{E_ASSISTANCE.FECHA.value} >= %s")
            params.append(periodo_ini)
        elif periodo_fin:
            condiciones.append(f"{E_ASSISTANCE.FECHA.value} <= %s")
            params.append(periodo_fin)

        if id_empleado:
            condiciones.append(f"{E_ASSISTANCE.NUMERO_NOMINA.value} = %s")
            params.append(int(id_empleado))

        where_clause = " AND ".join(condiciones) if condiciones else "1=1"
        q = f"""
            SELECT
                {E_ASSISTANCE.NUMERO_NOMINA.value} AS numero_nomina,
                MIN({E_ASSISTANCE.FECHA.value}) AS fecha_inicio,
                MAX({E_ASSISTANCE.FECHA.value}) AS fecha_fin
            FROM {E_ASSISTANCE.TABLE.value}
            WHERE {where_clause}
            GROUP BY {E_ASSISTANCE.NUMERO_NOMINA.value}
        """
        rows = self.db.get_data_list(q, tuple(params), dictionary=True) or []
        rangos: List[Tuple[int, str, str]] = []

        for row in rows:
            numero = int(row.get("numero_nomina") or 0)
            if numero <= 0:
                continue

            fi = row.get("fecha_inicio")
            ff = row.get("fecha_fin")
            fi_str = fi.strftime("%Y-%m-%d") if hasattr(fi, "strftime") else str(fi)
            ff_str = ff.strftime("%Y-%m-%d") if hasattr(ff, "strftime") else str(ff)
            rangos.append((numero, fi_str, ff_str))
        return rangos

    def add(
        self,
        numero_nomina: int,
        fecha: DateLike,
        hora_entrada: TimeLike = None,
        hora_salida: TimeLike = None,
        descanso: int = 1,
        grupo_importacion: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert (triggers calculan)."""
        try:
            fecha_mysql = self._convertir_fecha_a_mysql(fecha)

            # ✅ guardar NULL si no hay hora válida
            hora_entrada_norm = self._parse_hora_nullable(hora_entrada)
            hora_salida_norm = self._parse_hora_nullable(hora_salida)

            descanso_int = self._mapear_descanso_a_int(descanso)
            if descanso_int not in (0, 1, 2):
                descanso_int = 1

            q = f"""
                INSERT INTO {E_ASSISTANCE.TABLE.value} (
                    {E_ASSISTANCE.NUMERO_NOMINA.value},
                    {E_ASSISTANCE.FECHA.value},
                    {E_ASSISTANCE.HORA_ENTRADA.value},
                    {E_ASSISTANCE.HORA_SALIDA.value},
                    {E_ASSISTANCE.DESCANSO.value},
                    {E_ASSISTANCE.ESTADO.value},
                    {E_ASSISTANCE.TIEMPO_TRABAJO.value},
                    {E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value},
                    {E_ASSISTANCE.FECHA_GENERADA.value},
                    {E_ASSISTANCE.GRUPO_IMPORTACION.value}
                ) VALUES (%s, %s, %s, %s, %s, NULL, NULL, NULL, NULL, %s)
            """
            params = (
                int(numero_nomina),
                fecha_mysql,
                hora_entrada_norm,
                hora_salida_norm,
                descanso_int,
                grupo_importacion,
            )

            self.db.run_query(q, params)

            sync = self.payment_model.sincronizar_desde_asistencia(int(numero_nomina), fecha_mysql)
            self._publish_pagamentos_delta(int(numero_nomina), fecha_mysql, fecha_mysql)
            return {"status": "success", "sync": sync}
        except Exception as ex:
            print(f"[ERROR] Error al agregar asistencia: {ex}")
            return {"status": "error", "message": str(ex)}

    def add_manual_assistance(
        self,
        numero_nomina: int,
        fecha: DateLike,
        hora_entrada: str,
        hora_salida: str,
        descanso: int = 1,
        grupo_importacion: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Inserción manual estricta."""
        try:
            if not all(isinstance(h, str) for h in [hora_entrada, hora_salida]):
                raise ValueError("Las horas deben ser cadenas en formato HH:MM o HH:MM:SS")

            entrada_norm = self._parse_hora_nullable(hora_entrada)
            salida_norm = self._parse_hora_nullable(hora_salida)

            if not entrada_norm or not salida_norm:
                raise ValueError("Horas inválidas (vacías o 00:00).")

            h_entrada = datetime.strptime(entrada_norm, "%H:%M:%S")
            h_salida = datetime.strptime(salida_norm, "%H:%M:%S")
            if h_salida <= h_entrada:
                raise ValueError("La hora de salida debe ser mayor que la de entrada")

            descanso_int = self._mapear_descanso_a_int(descanso)
            fecha_mysql = self._convertir_fecha_a_mysql(fecha)

            q_check = f"""
                SELECT COUNT(*) AS existe
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.NUMERO_NOMINA.value} = %s AND {E_ASSISTANCE.FECHA.value} = %s
            """
            r = self.db.get_data(q_check, (int(numero_nomina), fecha_mysql), dictionary=True) or {}
            if (r.get("existe") or 0) > 0:
                return {"status": "error", "message": "Ya existe una asistencia registrada para ese empleado en esa fecha"}

            q_insert = f"""
                INSERT INTO {E_ASSISTANCE.TABLE.value} (
                    {E_ASSISTANCE.NUMERO_NOMINA.value},
                    {E_ASSISTANCE.FECHA.value},
                    {E_ASSISTANCE.HORA_ENTRADA.value},
                    {E_ASSISTANCE.HORA_SALIDA.value},
                    {E_ASSISTANCE.DESCANSO.value},
                    {E_ASSISTANCE.GRUPO_IMPORTACION.value}
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """
            self.db.run_query(
                q_insert,
                (int(numero_nomina), fecha_mysql, entrada_norm, salida_norm, descanso_int, grupo_importacion),
            )

            sync = self.payment_model.sincronizar_desde_asistencia(int(numero_nomina), fecha_mysql)
            self._publish_pagamentos_delta(int(numero_nomina), fecha_mysql, fecha_mysql)
            return {"status": "success", "message": "Asistencia agregada correctamente", "sync": sync}
        except Exception as e:
            print(f"[ERROR] Error en add_manual_assistance: {e}")
            return {"status": "error", "message": str(e)}

    # ✅ autosave seguro (solo descanso)
    def update_descanso(
        self,
        numero_nomina: int,
        fecha: DateLike,
        descanso: Any,
        *,
        return_row: bool = True,
    ) -> Dict[str, Any]:
        """
        ✅ Update seguro para autosave del dropdown (solo descanso).
        NO toca horas; trigger recalcula si hay horas válidas.
        Con el trigger “a prueba de balas”, si no hay horas válidas NO pisa tiempos.
        """
        try:
            numero_nomina = int(numero_nomina)
            fecha_mysql = self._convertir_fecha_a_mysql(fecha)
            descanso_int = self._mapear_descanso_a_int(descanso)

            q = f"""
                UPDATE {E_ASSISTANCE.TABLE.value}
                SET {E_ASSISTANCE.DESCANSO.value} = %s
                WHERE {E_ASSISTANCE.NUMERO_NOMINA.value} = %s
                  AND {E_ASSISTANCE.FECHA.value} = %s
            """
            self.db.run_query(q, (descanso_int, numero_nomina, fecha_mysql))

            sync = self.payment_model.sincronizar_desde_asistencia(numero_nomina, fecha_mysql)
            self._publish_pagamentos_delta(numero_nomina, fecha_mysql, fecha_mysql)

            out: Dict[str, Any] = {"status": "success", "sync": sync}
            if return_row:
                row = self.get_by_empleado_fecha(numero_nomina, fecha_mysql)
                out["data"] = row
            return out
        except Exception as e:
            print(f"[ERROR] Error en update_descanso: {e}")
            return {"status": "error", "message": str(e)}

    # ✅ update parcial realmente seguro
    def update_asistencia(self, registro: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update por (numero_nomina, fecha).

        ✅ Soporta updates parciales SIN “borrado accidental”:
        - Si el UI manda "" en hora_entrada / hora_salida => por defecto se IGNORA (no se actualiza).
        - Para borrar horas intencionalmente:
            registro["clear_horas"] = True
          o registro["clear_hora_entrada"]=True / ["clear_hora_salida"]=True

        Campos aceptados:
          - 'hora_entrada', 'hora_salida', 'descanso'
        """
        try:
            numero_nomina = int(registro.get("numero_nomina") or 0)
            fecha_mysql = self._convertir_fecha_a_mysql(registro.get("fecha"))

            if numero_nomina <= 0 or not str(fecha_mysql).strip():
                return {"status": "error", "message": "numero_nomina y fecha son requeridos"}

            clear_all = self._truthy(registro.get("clear_horas"))
            clear_ent = clear_all or self._truthy(registro.get("clear_hora_entrada"))
            clear_sal = clear_all or self._truthy(registro.get("clear_hora_salida"))

            sets: List[str] = []
            params: List[Any] = []

            if "hora_entrada" in registro:
                raw = registro.get("hora_entrada")
                if raw is None:
                    if clear_ent:
                        sets.append(f"{E_ASSISTANCE.HORA_ENTRADA.value} = %s")
                        params.append(None)
                else:
                    s = str(raw).strip()
                    if s == "":
                        if clear_ent:
                            sets.append(f"{E_ASSISTANCE.HORA_ENTRADA.value} = %s")
                            params.append(None)
                        # si NO clear => ignorar
                    else:
                        parsed = self._parse_hora_nullable(s)
                        # si parsed None => si quieres “forzar invalidar”, usa clear_hora_entrada=True
                        if parsed is not None:
                            sets.append(f"{E_ASSISTANCE.HORA_ENTRADA.value} = %s")
                            params.append(parsed)

            if "hora_salida" in registro:
                raw = registro.get("hora_salida")
                if raw is None:
                    if clear_sal:
                        sets.append(f"{E_ASSISTANCE.HORA_SALIDA.value} = %s")
                        params.append(None)
                else:
                    s = str(raw).strip()
                    if s == "":
                        if clear_sal:
                            sets.append(f"{E_ASSISTANCE.HORA_SALIDA.value} = %s")
                            params.append(None)
                    else:
                        parsed = self._parse_hora_nullable(s)
                        if parsed is not None:
                            sets.append(f"{E_ASSISTANCE.HORA_SALIDA.value} = %s")
                            params.append(parsed)

            if "descanso" in registro:
                descanso_int = self._mapear_descanso_a_int(registro.get("descanso"))
                sets.append(f"{E_ASSISTANCE.DESCANSO.value} = %s")
                params.append(descanso_int)

            if not sets:
                return {"status": "success", "message": "Sin cambios para aplicar"}

            q = f"""
                UPDATE {E_ASSISTANCE.TABLE.value}
                SET {", ".join(sets)}
                WHERE {E_ASSISTANCE.NUMERO_NOMINA.value} = %s AND {E_ASSISTANCE.FECHA.value} = %s
            """
            params.extend([numero_nomina, fecha_mysql])
            self.db.run_query(q, tuple(params))

            sync = self.payment_model.sincronizar_desde_asistencia(numero_nomina, fecha_mysql)
            self._publish_pagamentos_delta(numero_nomina, fecha_mysql, fecha_mysql)

            # ✅ devuelve fila ya recalculada para que UI pinte lo real
            row = self.get_by_empleado_fecha(numero_nomina, fecha_mysql)
            return {"status": "success", "sync": sync, "data": row}
        except Exception as e:
            print(f"[ERROR] Error al actualizar asistencia: {e}")
            return {"status": "error", "message": str(e)}

    def actualizar_asistencia_completa(
        self,
        numero_nomina: int,
        fecha: DateLike,
        hora_entrada: TimeLike,
        hora_salida: TimeLike,
        estado: str,
        descanso: int = 1,
        tiempo_trabajo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        ✅ Versión segura con columnas TIME + triggers.
        - Actualiza horas/descanso/estado (aunque triggers pueden sobreescribir estado/tiempos).
        - Horas se guardan NULL si están vacías/00:00.
        """
        try:
            fecha_sql = self._convertir_fecha_a_mysql(fecha)
            hora_entrada_norm = self._parse_hora_nullable(hora_entrada)
            hora_salida_norm = self._parse_hora_nullable(hora_salida)

            descanso_int = self._mapear_descanso_a_int(descanso)
            estado_norm = (estado or "").lower().strip() or None

            sets: List[str] = [
                f"{E_ASSISTANCE.HORA_ENTRADA.value} = %s",
                f"{E_ASSISTANCE.HORA_SALIDA.value} = %s",
                f"{E_ASSISTANCE.DESCANSO.value} = %s",
                f"{E_ASSISTANCE.ESTADO.value} = %s",
            ]
            params: List[Any] = [hora_entrada_norm, hora_salida_norm, descanso_int, estado_norm]

            tiempo_manual_norm = None
            if tiempo_trabajo is not None and str(tiempo_trabajo).strip() != "":
                tiempo_manual_norm = self._parse_tiempo_manual(tiempo_trabajo)
            if tiempo_manual_norm is not None:
                # manual override: guarda neto y bruto con el mismo valor
                sets.append(f"{E_ASSISTANCE.TIEMPO_TRABAJO.value} = %s")
                params.append(tiempo_manual_norm)
                sets.append(f"{E_ASSISTANCE.TIEMPO_TRABAJO_CON_DESCANSO.value} = %s")
                params.append(tiempo_manual_norm)

            q = f"""
                UPDATE {E_ASSISTANCE.TABLE.value}
                SET {", ".join(sets)}
                WHERE {E_ASSISTANCE.NUMERO_NOMINA.value} = %s AND {E_ASSISTANCE.FECHA.value} = %s
            """
            params.extend([int(numero_nomina), fecha_sql])
            self.db.run_query(q, params)

            sync = self.payment_model.sincronizar_desde_asistencia(int(numero_nomina), fecha_sql)
            self._publish_pagamentos_delta(int(numero_nomina), fecha_sql, fecha_sql)

            row = self.get_by_empleado_fecha(int(numero_nomina), fecha_sql)
            return {"status": "success", "sync": sync, "data": row}
        except Exception as e:
            print(f"❌ Error al actualizar asistencia completa: {e}")
            return {"status": "error", "message": str(e)}

    def get_all(self) -> Dict[str, Any]:
        try:
            q = f"""
                SELECT a.*, e.nombre_completo
                FROM {E_ASSISTANCE.TABLE.value} a
                JOIN empleados e ON a.{E_ASSISTANCE.NUMERO_NOMINA.value} = e.numero_nomina
                ORDER BY a.{E_ASSISTANCE.FECHA.value} ASC
            """
            result = self.db.get_data_list(q, dictionary=True) or []
            for row in result:
                self._mapear_fila_asistencia(row)
            return {"status": "success", "data": result}
        except Exception as ex:
            print(f"❌ Error al obtener asistencias: {ex}")
            return {"status": "error", "message": f"Error al obtener asistencias: {ex}"}

    def get_by_id(self, id_asistencia: int) -> Dict[str, Any]:
        try:
            q = f"""
                SELECT *
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.ID_ASISTENCIA.value} = %s
            """
            result = self.db.get_data(q, (int(id_asistencia),), dictionary=True)
            if result:
                self._mapear_fila_asistencia(result)
                return {"status": "success", "data": result}
            return {"status": "error", "message": "Asistencia no encontrada"}
        except Exception as ex:
            print(f"❌ Error al obtener asistencia por ID: {ex}")
            return {"status": "error", "message": str(ex)}

    def get_by_empleado_fecha(self, numero_nomina: int, fecha: DateLike) -> Optional[Dict[str, Any]]:
        try:
            fecha_mysql = self._convertir_fecha_a_mysql(fecha)
            q = f"""
                SELECT *
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.NUMERO_NOMINA.value} = %s AND {E_ASSISTANCE.FECHA.value} = %s
            """
            result = self.db.get_data(q, (int(numero_nomina), fecha_mysql), dictionary=True)
            if result:
                self._mapear_fila_asistencia(result)
                return result
            return None
        except Exception as ex:
            print(f"❌ Error al obtener asistencia por empleado y fecha: {ex}")
            return None

    def delete_by_numero_nomina_and_fecha(self, numero_nomina: int, fecha: DateLike) -> Dict[str, Any]:
        try:
            fecha_sql = self._convertir_fecha_a_mysql(fecha)
            q = f"""
                DELETE FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.NUMERO_NOMINA.value} = %s AND {E_ASSISTANCE.FECHA.value} = %s
            """
            self.db.run_query(q, (int(numero_nomina), fecha_sql))
            self._publish_pagamentos_delta(int(numero_nomina), fecha_sql, fecha_sql)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_ultimo_id(self) -> int:
        try:
            q = f"SELECT MAX({E_ASSISTANCE.ID_ASISTENCIA.value}) AS ultimo FROM {E_ASSISTANCE.TABLE.value}"
            r = self.db.get_data(q, dictionary=True) or {}
            return int(r.get("ultimo") or 0)
        except Exception as e:
            print(f"❌ Error al obtener último ID: {e}")
            return 0

    def get_ultimo_numero_nomina(self) -> int:
        try:
            q = f"SELECT MAX({E_ASSISTANCE.NUMERO_NOMINA.value}) AS ultimo FROM {E_ASSISTANCE.TABLE.value}"
            r = self.db.get_data(q, dictionary=True) or {}
            return int(r.get("ultimo") or 0)
        except Exception as e:
            print(f"❌ Error al obtener último numero_nomina: {e}")
            return 0

    def actualizar_horas_manualmente(
        self,
        numero_nomina: int,
        fecha: DateLike,
        hora_entrada: str,
        hora_salida: str
    ) -> Dict[str, Any]:
        try:
            fecha_sql = self._convertir_fecha_a_mysql(fecha)
            entrada_norm = self._parse_hora_nullable(hora_entrada)
            salida_norm = self._parse_hora_nullable(hora_salida)

            if not entrada_norm or not salida_norm:
                raise ValueError("Horas inválidas (vacías o 00:00).")

            h_ent = datetime.strptime(entrada_norm, "%H:%M:%S")
            h_sal = datetime.strptime(salida_norm, "%H:%M:%S")
            if h_sal <= h_ent:
                raise ValueError("La hora de salida debe ser mayor que la de entrada")

            q = f"""
                UPDATE {E_ASSISTANCE.TABLE.value}
                SET {E_ASSISTANCE.HORA_ENTRADA.value} = %s,
                    {E_ASSISTANCE.HORA_SALIDA.value}  = %s
                WHERE {E_ASSISTANCE.NUMERO_NOMINA.value} = %s AND {E_ASSISTANCE.FECHA.value} = %s
            """
            self.db.run_query(q, (entrada_norm, salida_norm, int(numero_nomina), fecha_sql))
            self._publish_pagamentos_delta(int(numero_nomina), fecha_sql, fecha_sql)

            row = self.get_by_empleado_fecha(int(numero_nomina), fecha_sql)
            return {"status": "success", "data": row}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def actualizar_estado_asistencia(self, numero_nomina: int, fecha: DateLike) -> Dict[str, Any]:
        """Recalcula estado a partir de horas (sin depender de triggers)."""
        try:
            fecha_sql = self._convertir_fecha_a_mysql(fecha)
            q = f"""
                UPDATE {E_ASSISTANCE.TABLE.value}
                SET {E_ASSISTANCE.ESTADO.value} = CASE
                    WHEN {E_ASSISTANCE.HORA_ENTRADA.value} IS NOT NULL AND {E_ASSISTANCE.HORA_ENTRADA.value} != '00:00:00'
                    AND {E_ASSISTANCE.HORA_SALIDA.value} IS NOT NULL AND {E_ASSISTANCE.HORA_SALIDA.value} != '00:00:00'
                    AND TIMEDIFF({E_ASSISTANCE.HORA_SALIDA.value}, {E_ASSISTANCE.HORA_ENTRADA.value}) > '00:00:00'
                    THEN 'completo'
                    ELSE 'incompleto'
                END
                WHERE {E_ASSISTANCE.NUMERO_NOMINA.value} = %s AND {E_ASSISTANCE.FECHA.value} = %s
            """
            self.db.run_query(q, (int(numero_nomina), fecha_sql))
            self._publish_pagamentos_delta(int(numero_nomina), fecha_sql, fecha_sql)

            row = self.get_by_empleado_fecha(int(numero_nomina), fecha_sql)
            return {"status": "success", "data": row}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ---------------------------------------------------------------------
    # Fechas mín / máx
    # ---------------------------------------------------------------------
    def get_fecha_minima_asistencia(self) -> Optional[date]:
        try:
            q = f"SELECT MIN({E_ASSISTANCE.FECHA.value}) AS fi FROM {E_ASSISTANCE.TABLE.value}"
            r = self.db.get_data(q, dictionary=True) or {}
            fi = r.get("fi")
            if isinstance(fi, date):
                return fi
            if isinstance(fi, str) and fi:
                return datetime.strptime(fi, "%Y-%m-%d").date()
            return None
        except Exception as e:
            print(f"❌ Error al obtener fecha mínima de asistencia: {e}")
            return None

    def get_fecha_maxima_asistencia(self) -> Optional[date]:
        try:
            q = f"SELECT MAX({E_ASSISTANCE.FECHA.value}) AS ff FROM {E_ASSISTANCE.TABLE.value}"
            r = self.db.get_data(q, dictionary=True) or {}
            ff = r.get("ff")
            if isinstance(ff, date):
                return ff
            if isinstance(ff, str) and ff:
                return datetime.strptime(ff, "%Y-%m-%d").date()
            return None
        except Exception as e:
            print(f"❌ Error al obtener fecha máxima de asistencia: {e}")
            return None

    # ---------------------------------------------------------------------
    # Fechas para nómina / generadas
    # ---------------------------------------------------------------------
    def marcar_asistencias_como_generadas(
        self,
        fecha_inicio: DateLike,
        fecha_fin: DateLike,
        fecha_generacion: Optional[DateLike] = None
    ) -> Dict[str, Any]:
        try:
            fi = self._convertir_fecha_a_mysql(fecha_inicio)
            ff = self._convertir_fecha_a_mysql(fecha_fin)
            fg = self._convertir_fecha_a_mysql(fecha_generacion) if fecha_generacion else datetime.today().strftime("%Y-%m-%d")

            q = f"""
                UPDATE {E_ASSISTANCE.TABLE.value}
                SET {E_ASSISTANCE.FECHA_GENERADA.value} = %s
                WHERE {E_ASSISTANCE.FECHA.value} BETWEEN %s AND %s
                AND {E_ASSISTANCE.ESTADO.value} = 'completo'
            """
            self.db.run_query(q, (fg, fi, ff))
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def marcar_asistencias_como_no_generadas(self, fecha_inicio: DateLike, fecha_fin: DateLike) -> None:
        fi = self._convertir_fecha_a_mysql(fecha_inicio)
        ff = self._convertir_fecha_a_mysql(fecha_fin)
        q = f"""
            UPDATE {E_ASSISTANCE.TABLE.value}
            SET {E_ASSISTANCE.FECHA_GENERADA.value} = NULL
            WHERE {E_ASSISTANCE.FECHA.value} BETWEEN %s AND %s
        """
        self.db.run_query(q, (fi, ff))

    def get_fechas_generadas(self) -> List[date]:
        try:
            q = f"""
                SELECT DISTINCT {E_ASSISTANCE.FECHA.value} AS fecha
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.FECHA_GENERADA.value} IS NOT NULL
                ORDER BY {E_ASSISTANCE.FECHA.value} ASC
            """
            rows = self.db.get_data_list(q, dictionary=True) or []
            out: List[date] = []
            for r in rows:
                f = r.get("fecha")
                if isinstance(f, date):
                    out.append(f)
                elif isinstance(f, str) and f:
                    out.append(datetime.strptime(f, "%Y-%m-%d").date())
            return out
        except Exception as e:
            print(f"❌ Error al obtener fechas generadas: {e}")
            return []

    def get_fechas_disponibles_para_pago(self) -> List[date]:
        try:
            q = f"""
                SELECT DISTINCT {E_ASSISTANCE.FECHA.value} AS fecha
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.ESTADO.value} = 'completo'
                  AND {E_ASSISTANCE.FECHA_GENERADA.value} IS NULL
                ORDER BY fecha ASC
            """
            rows = self.db.get_data_list(q, dictionary=True) or []
            out: List[date] = []
            for r in rows:
                f = r.get("fecha")
                if isinstance(f, date):
                    out.append(f)
                elif isinstance(f, str) and f:
                    out.append(datetime.strptime(f, "%Y-%m-%d").date())
            return out
        except Exception as ex:
            print(f"❌ Error al obtener fechas disponibles para pago: {ex}")
            return []

    def get_fechas_disponibles_para_pago_por_empleado(self, numero_nomina: int) -> List[date]:
        try:
            q = f"""
                SELECT DISTINCT {E_ASSISTANCE.FECHA.value} AS fecha
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.NUMERO_NOMINA.value} = %s
                  AND {E_ASSISTANCE.ESTADO.value} = 'completo'
                  AND {E_ASSISTANCE.FECHA_GENERADA.value} IS NULL
                ORDER BY fecha ASC
            """
            rows = self.db.get_data_list(q, (int(numero_nomina),), dictionary=True) or []
            out: List[date] = []
            for r in rows:
                f = r.get("fecha")
                if isinstance(f, date):
                    out.append(f)
                elif isinstance(f, str) and f:
                    out.append(datetime.strptime(f, "%Y-%m-%d").date())
            return out
        except Exception as ex:
            print(f"❌ Error al obtener fechas disponibles por empleado: {ex}")
            return []

    # ---------------------------------------------------------------------
    # Fechas vacías / incompletas / estado recalculado
    # ---------------------------------------------------------------------
    def get_fechas_vacias(self, fi: date, ff: date) -> List[date]:
        try:
            if not fi or not ff:
                return []

            q = f"""
                SELECT DISTINCT {E_ASSISTANCE.FECHA.value} AS fecha
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {E_ASSISTANCE.FECHA.value} BETWEEN %s AND %s
            """
            rows = self.db.get_data_list(q, (fi, ff), dictionary=True) or []
            ocupadas: set[date] = set()

            for r in rows:
                f = r.get("fecha")
                if isinstance(f, date):
                    ocupadas.add(f)
                elif isinstance(f, str) and f:
                    ocupadas.add(datetime.strptime(f, "%Y-%m-%d").date())

            vacias: List[date] = []
            cur = fi
            while cur <= ff:
                if cur not in ocupadas:
                    vacias.append(cur)
                cur += timedelta(days=1)
            return vacias
        except Exception as ex:
            print(f"❌ Error al obtener fechas vacías: {ex}")
            return []

    def get_fechas_incompletas(
        self,
        fi: Optional[date] = None,
        ff: Optional[date] = None,
        numero_nomina: Optional[int] = None,
    ) -> Dict[date, str]:
        try:
            params: List[Any] = []
            condiciones: List[str] = ["1=1"]

            if fi and ff:
                condiciones.append(f"{E_ASSISTANCE.FECHA.value} BETWEEN %s AND %s")
                params.extend([fi, ff])

            if numero_nomina:
                condiciones.append(f"{E_ASSISTANCE.NUMERO_NOMINA.value} = %s")
                params.append(int(numero_nomina))

            condiciones_incompletas = f"""
            (
                {E_ASSISTANCE.ESTADO.value} = 'incompleto'
                OR {E_ASSISTANCE.ESTADO.value} IS NULL
                OR {E_ASSISTANCE.ESTADO.value} = ''
                OR {E_ASSISTANCE.HORA_ENTRADA.value} IS NULL
                OR {E_ASSISTANCE.HORA_SALIDA.value} IS NULL
                OR {E_ASSISTANCE.HORA_ENTRADA.value} IN ('00:00:00','0:00:00')
                OR {E_ASSISTANCE.HORA_SALIDA.value}  IN ('00:00:00','0:00:00')
                OR TIMEDIFF({E_ASSISTANCE.HORA_SALIDA.value}, {E_ASSISTANCE.HORA_ENTRADA.value}) <= '00:00:00'
            )
            """

            q = f"""
                SELECT DISTINCT {E_ASSISTANCE.FECHA.value} AS fecha
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {" AND ".join(condiciones)}
                  AND {condiciones_incompletas}
                ORDER BY {E_ASSISTANCE.FECHA.value} ASC
            """
            rows = self.db.get_data_list(q, tuple(params), dictionary=True) or []
            out: Dict[date, str] = {}

            for r in rows:
                f = r.get("fecha")
                if isinstance(f, date):
                    out[f] = "incompleto"
                elif isinstance(f, str) and f:
                    out[datetime.strptime(f, "%Y-%m-%d").date()] = "incompleto"

            return out
        except Exception as ex:
            print(f"❌ Error al obtener fechas incompletas: {ex}")
            return {}

    def get_fechas_estado_completo_y_incompleto(
        self,
        fi: Optional[date] = None,
        ff: Optional[date] = None,
        numero_nomina: Optional[int] = None,
    ) -> Dict[date, str]:
        try:
            params: List[Any] = []
            condiciones: List[str] = ["1=1"]

            if fi and ff:
                condiciones.append(f"{E_ASSISTANCE.FECHA.value} BETWEEN %s AND %s")
                params.extend([fi, ff])

            if numero_nomina:
                condiciones.append(f"{E_ASSISTANCE.NUMERO_NOMINA.value} = %s")
                params.append(int(numero_nomina))

            q = f"""
                SELECT DISTINCT {E_ASSISTANCE.FECHA.value} AS fecha,
                    CASE
                        WHEN {E_ASSISTANCE.HORA_ENTRADA.value} IS NOT NULL
                            AND {E_ASSISTANCE.HORA_SALIDA.value} IS NOT NULL
                            AND {E_ASSISTANCE.HORA_ENTRADA.value} NOT IN ('00:00:00','0:00:00')
                            AND {E_ASSISTANCE.HORA_SALIDA.value}  NOT IN ('00:00:00','0:00:00')
                            AND TIMEDIFF({E_ASSISTANCE.HORA_SALIDA.value}, {E_ASSISTANCE.HORA_ENTRADA.value}) > '00:00:00'
                        THEN 'completo'
                        ELSE 'incompleto'
                    END AS estado
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE {" AND ".join(condiciones)}
                ORDER BY {E_ASSISTANCE.FECHA.value} ASC
            """
            rows = self.db.get_data_list(q, tuple(params), dictionary=True) or []
            out: Dict[date, str] = {}

            for r in rows:
                f = r.get("fecha")
                estado = str(r.get("estado", "incompleto")).lower().strip()
                if isinstance(f, date):
                    out[f] = estado
                elif isinstance(f, str) and f:
                    out[datetime.strptime(f, "%Y-%m-%d").date()] = estado
            return out
        except Exception as ex:
            print(f"❌ Error al obtener fechas por estado: {ex}")
            return {}

    def get_fechas_estado(self, fi: Optional[date] = None, ff: Optional[date] = None) -> Dict[date, str]:
        try:
            params: List[Any] = []
            filtro = ""
            if fi and ff:
                filtro = f"AND {E_ASSISTANCE.FECHA.value} BETWEEN %s AND %s"
                params = [fi, ff]

            q = f"""
                SELECT {E_ASSISTANCE.FECHA.value} AS fecha, {E_ASSISTANCE.ESTADO.value} AS estado
                FROM {E_ASSISTANCE.TABLE.value}
                WHERE 1=1 {filtro}
            """
            rows = self.db.get_data_list(q, tuple(params), dictionary=True) or []
            out: Dict[date, str] = {}
            for r in rows:
                f = r.get("fecha")
                estado = str(r.get("estado") or "").lower().strip()
                if isinstance(f, date):
                    out[f] = estado
                elif isinstance(f, str) and f:
                    out[datetime.strptime(f, "%Y-%m-%d").date()] = estado
            return out
        except Exception as ex:
            print(f"❌ Error al obtener fechas con estado: {ex}")
            return {}
