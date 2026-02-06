# app/core/enums/e_grupos_fechas_pago_model.py
from enum import Enum


class E_GRUPOS_FECHAS_PAGO(Enum):
    """
    Enum EXCLUSIVO para la tabla `grupos_pagos`.

    Propósito
    ----------
    Esta tabla NO es la misma lógica que `pagos.grupo_pago` (GP-...).
    Aquí hablamos de "grupos por FECHA" usados por la UI para:

    1) Mostrar fechas (grupos) aunque NO existan pagos reales en `pagos`.
       - Ejemplo: crear un grupo 'pagado' vacío para que aparezca en el panel.

    2) Controlar visualmente el estado del grupo por fecha:
       - 'abierto' / 'cerrado' (para UI / navegación / permisos).

    Reglas de uso (anti-confusión)
    ------------------------------
    - Este enum SOLO se usa con la tabla `grupos_pagos`.
    - Sus campos NO deben mezclarse con:
      • E_PAYMENT (tabla `pagos`)
      • E_PAYMENT.GRUPO_PAGO (token GP-INI_AL_FIN)
      • Cualquier "grupo_importacion" de asistencias
    """

    # Tabla
    TABLA_GRUPOS_POR_FECHA = "grupos_pagos"

    # PK
    ID_GRUPO_FECHA = "id_grupo"

    # Campos semánticos del grupo por fecha
    FECHA_GRUPO = "fecha"                 # DATE: la fecha “visible” del grupo
    CATEGORIA_GRUPO = "categoria"         # ENUM('pagado','pendiente')
    ESTADO_GRUPO_FECHA = "estado_grupo"   # ENUM('abierto','cerrado')

    # Auditoría / metadata
    FECHA_CREACION_GRUPO = "created_at"   # TIMESTAMP
