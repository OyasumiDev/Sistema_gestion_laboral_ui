import flet as ft
from app.views.window_main_view import window_main
from app.core.app_state import AppState

# Importar modelos
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

def iniciar_aplicacion():
    """
    Método central que inicializa la base de datos
    creando todas las tablas requeridas desde sus modelos.
    """

    # Tablas base
    print("🔄 Creando tabla empleados...")
    EmployesModel()

    print("🔄 Creando tabla usuarios_app...")
    UserModel()

    # Tablas dependientes de empleados
    print("🔄 Creando tabla asistencias...")
    AssistanceModel()

    print("🔄 Creando tabla pagos...")
    PaymentModel()  # Se necesita antes de descuentos y pagos_prestamo

    print("🔄 Creando tabla prestamos...")
    LoanModel()

    print("🔄 Creando tabla pagos_prestamo...")
    LoanPaymentModel()

    print("🔄 Creando tabla detalles_pagos_prestamo...")
    DetallesPagosPrestamoModel()

    print("🔄 Creando tabla descuentos...")
    DiscountModel()

    print("🔄 Creando tabla desempeño...")
    PerformanceModel()

    print("🔄 Creando tabla reportes_semanales...")
    WeeklyReportModel()

    # Lanzar la app
    print("🚀 Lanzando aplicación...")
    ft.app(target=window_main, assets_dir="assets")


if __name__ == "__main__":
    try:
        iniciar_aplicacion()
    except Exception as e:
        print(f"❌ Error al iniciar la aplicación: {e}")
