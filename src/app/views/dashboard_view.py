import flet as ft

class DashboardView(ft.View):

    def __init__(self):
        '''
        Vista de login
        '''
        self.controls_dashboard = []
        
        super().__init__(
            route = '/dashboard',
            controls = self.controls_dashboard
        )


        self.controls_dashboard.append(
            ft.Text(value = 'dashboard')
        )