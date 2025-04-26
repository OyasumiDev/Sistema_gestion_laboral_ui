import flet as ft
from app.core.app_state import AppState

class ScreenScaler:
    """
    Utility for detecting screen dimensions, computing scale factors,
    and adjusting controls (e.g., images) to fit the viewport.
    """
    def __init__(self, page: ft.Page | None = None):
        # Use global AppState if not provided
        self.page = page or AppState().page

    def get_dimensions(self) -> tuple[int, int]:
        """Returns current window width and height (logical pixels)."""
        if not self.page:
            return (1024, 768)
        try:
            return (self.page.window_width, self.page.window_height)
        except AttributeError:
            return (1024, 768)

    def get_device_pixel_ratio(self) -> float:
        """Returns device pixel ratio for scaling high-DPI screens."""
        if not self.page:
            return 1.0
        try:
            return float(self.page.window.device_pixel_ratio)
        except (AttributeError, ValueError):
            return 1.0

    def get_scale_factor(self, design_width: int, design_height: int) -> float:
        """
        Computes a scale factor so that a design of given dimensions
        fits within the current viewport without exceeding 1.0.
        """
        screen_w, screen_h = self.get_dimensions()
        ratio_w = screen_w / design_width if design_width else 1.0
        ratio_h = screen_h / design_height if design_height else 1.0
        # Do not enlarge beyond original size
        return min(ratio_w, ratio_h, 1.0)

    def scale_image(self, image: ft.Image, design_width: int, design_height: int) -> ft.Image:
        """
        Adjusts an ft.Image control's width/height based on design dimensions.
        """
        factor = self.get_scale_factor(design_width, design_height)
        image.width = int(design_width * factor)
        image.height = int(design_height * factor)
        return image

    def wrap_with_scroll(self, control: ft.Control) -> ft.Container:
        """
        Wraps a control in a scrollable container if its height exceeds the viewport.
        """
        return ft.Container(
            content=ft.Scrollable(
                content=control
            ),
            expand=True
        )
