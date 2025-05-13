import flet as ft
from app.views.window_main_view import window_main
from app.core.app_state import AppState

# Importar todos los modelos
from app.models.employes_model import EmployesModel
from app.models.user_model import UserModel
from app.models.assistance_model import AssistanceModel
from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.discount_model import DiscountModel
from app.models.payment_model import PaymentModel
from app.models.performance_model import PerformanceModel
from app.models.weekly_report_model import WeeklyReportModel


def iniciar_aplicacion():
    """
    Método central que inicializa la base de datos
    creando todas las tablas requeridas desde sus modelos.
    """
    # Tablas base (no dependen de otras)
    EmployesModel()     # empleados
    UserModel()         # usuarios_app

    # Tablas que dependen de empleados
    AssistanceModel()   # asistencias → empleados
    LoanModel()         # prestamos → empleados
    PaymentModel()      # pagos → empleados ✅ debe ir antes de descuentos
    DiscountModel()     # descuentos → empleados, pagos
    LoanPaymentModel()  # pagos_prestamo → prestamos
    PerformanceModel()  # desempeno → empleados
    WeeklyReportModel() # reportes_semanales → empleados

    # Lanza la interfaz principal de la app
    ft.app(target=window_main, assets_dir="assets")



if __name__ == "__main__":
    iniciar_aplicacion()
