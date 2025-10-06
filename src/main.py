import flet as ft

from app.views.window_main_view import window_main
from app.core.app_state import AppState

# Modelos (solo import, la creación va en bootstrap siguiendo el orden correcto)
from app.models.employes_model import EmployesModel
from app.models.user_model import UserModel
from app.models.assistance_model import AssistanceModel
from app.models.payment_model import PaymentModel
from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.detalles_pagos_prestamo_model import DetallesPagosPrestamoModel
from app.models.discount_model import DiscountModel
from app.models.performance_model import PerformanceModel
from app.models.weekly_report_model import WeeklyReportModel


def _safe_create(label: str, fn):
    print(f"🔄 Creando {label}...")
    try:
        obj = fn()
        print(f"✔️ {label.capitalize()} ya existe." if getattr(obj, "_exists_table", True) else f"✔️ {label.capitalize()} ok.")
        return obj
    except Exception as ex:
        print(f"❌ Error verificando/creando {label}: {ex}")
        raise


def bootstrap_db():
    # 1) Base
    _safe_create("tabla empleados", EmployesModel)
    _safe_create("tabla usuarios_app", UserModel)

    # 2) Pagos (depende de empleados)
    pagos = _safe_create("tabla pagos", PaymentModel)

    # 3) Asistencias (depende de empleados, y requiere pagos para integridad)
    asistencia = _safe_create("tabla asistencias", AssistanceModel)

    # 4) Préstamos (depende de empleados)
    _safe_create("tabla prestamos", LoanModel)

    # 5) Pagos de préstamo (depende de prestamos y pagos)
    _safe_create("tabla pagos_prestamo", LoanPaymentModel)

    # 6) Staging de pagos de préstamo (si aplica)
    _safe_create("tabla detalles_pagos_prestamo", DetallesPagosPrestamoModel)

    # 7) Descuentos (depende de pagos y empleados)
    _safe_create("tabla descuentos", DiscountModel)

    # 8) Otros módulos
    _safe_create("tabla desempeño", PerformanceModel)
    _safe_create("tabla reportes_semanales", WeeklyReportModel)

    # 9) Stored Procedure
    try:
        print("⚙️  Verificando Stored Procedure 'horas_trabajadas_para_pagos'...")
        pagos.crear_sp_horas_trabajadas_para_pagos()
    except Exception as ex:
        print(f"❌ Error creando SP 'horas_trabajadas_para_pagos': {ex}")



def iniciar_aplicacion():
    # Inicializa BD en orden correcto
    bootstrap_db()

    # Lanza Flet
    print("🚀 Lanzando aplicación...")
    ft.app(target=window_main, assets_dir="assets")


if __name__ == "__main__":
    try:
        iniciar_aplicacion()
    except Exception as e:
        print(f"❌ Error al iniciar la aplicación: {e}")
