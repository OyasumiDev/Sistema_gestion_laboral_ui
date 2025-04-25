from app.helpers.class_singleton import class_singleton

@class_singleton
class LayoutController:
    def __init__(self):
        self.expandido = False

    def toggle(self):
        self.expandido = not self.expandido
