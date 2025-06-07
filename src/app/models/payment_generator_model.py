from datetime import date
from app.core.interfaces.database_mysql import DatabaseMysql
from app.models.payment_model import PaymentModel
from app.models.employes_model import EmployesModel
from app.models.loan_model import LoanModel
from app.models.loan_payment_model import LoanPaymentModel
from app.models.discount_model import DiscountModel
from app.core.enums.e_payment_model import E_PAYMENT
from app.core.enums.e_prestamos_model import E_PRESTAMOS

class PaymentGeneratorModel:
    def __init__(self):
        self.db = DatabaseMysql()
        self.payment_model = PaymentModel()
        self.employee_model = EmployesModel()
        self.loan_model = LoanModel()
        self.loan_payment_model = LoanPaymentModel()
        self.discount_model = DiscountModel()

    def _get_total_horas_trabajadas(self, numero_nomina, fecha_inicio, fecha_fin):
        query = "CALL horas_trabajadas(%s, %s, %s)"
        result = self.db.get_data(query, (numero_nomina, fecha_inicio, fecha_fin), dictionary=True)
        return result.get("total_horas_trabajadas", "00:00:00")

    def _horas_a_decimal(self, tiempo_str):
        h, m, s = map(int, tiempo_str.split(":"))
        return h + m / 60 + s / 3600

    def generar_pago_individual(self, numero_nomina, fecha_inicio, fecha_fin, descuentos=[], abono=0.0, id_prestamo=None):
        empleado = self.employee_model.get_by_id(numero_nomina)
        if not empleado:
            return {"status": "error", "message": "Empleado no encontrado"}

        resultado = self.payment_model.get_total_horas_trabajadas(fecha_inicio, fecha_fin, numero_nomina)
        if resultado["status"] != "success" or not resultado["data"]:
            return {"status": "error", "message": "El empleado no tiene asistencias registradas en este periodo"}

        tiempo_str = resultado["data"][0]["total_horas_trabajadas"]
        horas_decimal = self._horas_a_decimal(tiempo_str)
        sueldo_hora = float(empleado["sueldo_por_hora"])
        monto_base = round(sueldo_hora * horas_decimal, 2)

        monto_descuentos = sum(float(d.get("monto", 0)) for d in descuentos)

        if id_prestamo:
            prestamo = self.loan_model.get_by_id(id_prestamo)
            if prestamo and prestamo["estado"] == "activo":
                saldo = float(prestamo["saldo_prestamo"])
                if abono > saldo:
                    abono = saldo
                nuevo_saldo = round(saldo - abono, 2)
                self.loan_model.update_by_id_prestamo(id_prestamo, {"saldo_prestamo": nuevo_saldo})
                self.loan_payment_model.add_payment(id_prestamo, abono, abono / saldo * 100, date.today(), date.today())
            else:
                return {"status": "error", "message": "Préstamo inválido o inactivo"}
        else:
            prestamos_activos = self.loan_model.get_active_by_numero_nomina(numero_nomina)
            for p in prestamos_activos:
                self.loan_model.incrementar_dias_retraso(p[E_PRESTAMOS.PRESTAMO_ID.value])

        monto_total = round(monto_base - monto_descuentos - abono, 2)
        if monto_total < 0:
            monto_total = 0.0

        pago_data = {
            E_PAYMENT.NUMERO_NOMINA.value: numero_nomina,
            E_PAYMENT.FECHA_PAGO.value: date.today(),
            E_PAYMENT.MONTO_BASE.value: monto_base,
            E_PAYMENT.MONTO_TOTAL.value: monto_total,
            E_PAYMENT.SALDO.value: 0.0,
            E_PAYMENT.PAGO_DEPOSITO.value: 0.0,
            E_PAYMENT.PAGO_EFECTIVO.value: monto_total
        }
        self.payment_model.add_payment(pago_data)

        return {
            "status": "success",
            "numero_nomina": numero_nomina,
            "monto_base": monto_base,
            "descuentos": monto_descuentos,
            "abono_prestamo": abono,
            "monto_total": monto_total,
            "horas_trabajadas": tiempo_str
        }

    def generar_pagos_masivos(self, fecha_inicio, fecha_fin, descuentos_dict={}, abonos_dict={}):
        empleados = self.employee_model.get_all()
        resultados = []

        for emp in empleados:
            num = emp["numero_nomina"]
            resultado = self.generar_pago_individual(
                numero_nomina=num,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                descuentos=descuentos_dict.get(num, []),
                abono=abonos_dict.get(num, 0.0),
                id_prestamo=self._get_prestamo_activo_id(num)
            )
            resultados.append(resultado)
        return resultados

    def _get_prestamo_activo_id(self, numero_nomina):
        prestamos = self.loan_model.get_active_by_numero_nomina(numero_nomina)
        return prestamos[0][E_PRESTAMOS.PRESTAMO_ID.value] if prestamos else None
