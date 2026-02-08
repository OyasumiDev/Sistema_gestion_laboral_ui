# app/core/enums/e_fechas_modal_model.py
"""
Enums EXCLUSIVOS del subsistema "Fechas Modal" (DateModalSelector + FechasModalModel).

Meta:
- Que sea imposible confundirlo con enums de pagos/asistencias/descuentos.
- Reutilizable sin choques de nombres.

Tabla auxiliar:
- fecha_grupos_pagados
    id_grupo      (PK)
    fecha         (DATE)
    categoria     ENUM('pagado','pendiente')
    estado_grupo  ENUM('abierto','cerrado')
    created_at    TIMESTAMP

Uso:
- FechasModalModel usa esta tabla para reforzar el control del calendario del modal
  (principalmente para bloqueo/estado administrativo de fechas por categoría).
"""

from enum import Enum


class E_FECHAS_MODAL_FECHA_GRUPOS_PAGADOS(Enum):
    # ---------------- Tabla ----------------
    TABLE = "fecha_grupos_pagados"

    # ---------------- Columnas DB ----------------
    COL_ID_GRUPO = "id_grupo"
    COL_FECHA = "fecha"
    COL_CATEGORIA = "categoria"
    COL_ESTADO_GRUPO = "estado_grupo"
    COL_CREATED_AT = "created_at"

    # ---------------- Valores permitidos (DB enums) ----------------
    # categoria
    CATEGORIA_PAGADO = "pagado"
    CATEGORIA_PENDIENTE = "pendiente"

    # estado_grupo
    ESTADO_GRUPO_ABIERTO = "abierto"
    ESTADO_GRUPO_CERRADO = "cerrado"
