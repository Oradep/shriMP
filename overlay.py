import customtkinter as ctk
import ctypes
import tkinter as tk

class VignetteOverlay:
    def __init__(self):
        self.window = ctk.CTkToplevel()
        self.window.attributes("-fullscreen", True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.0)
        self.window.wm_attributes("-transparentcolor", "black")
        self.window.configure(fg_color="black")
        self.window.overrideredirect(True)
        
        self.canvas = tk.Canvas(self.window, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.window.withdraw()

        self.target_alpha = 0.5
        self.current_alpha = 0.0
        self.fade_running = False

        self.window.update()
        hwnd = ctypes.windll.user32.GetParent(self.window.winfo_id())
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_LAYERED = 0x00080000
        GWL_EXSTYLE = -20
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED)

    def _hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _rgb_to_hex(self, rgb):
        return '#%02x%02x%02x' % rgb

    def update_settings(self, color_hex, thickness, opacity):
        self.target_alpha = float(opacity)
        self.canvas.delete("all")
        
        w = self.window.winfo_screenwidth()
        h = self.window.winfo_screenheight()
        
        base_rgb = self._hex_to_rgb(color_hex)
        steps = int(thickness)
        
        for i in range(steps):
            ratio = 1.0 - (i / steps)
            r = int(base_rgb[0] * ratio)
            g = int(base_rgb[1] * ratio)
            b = int(base_rgb[2] * ratio)
            current_color = self._rgb_to_hex((r, g, b))
            
            self.canvas.create_rectangle(i, i, w-i, h-i, outline=current_color, width=1)

    def show(self):
        if self.window.state() == "withdrawn":
            self.window.deiconify()
            self.current_alpha = 0.0
            self.fade_running = True
            self._fade_in()

    def _fade_in(self):
        if self.fade_running and self.current_alpha < self.target_alpha:
            self.current_alpha += 0.05
            self.window.attributes("-alpha", self.current_alpha)
            self.window.after(30, self._fade_in)

    def hide(self):
        self.fade_running = False
        self.window.withdraw()
        self.window.attributes("-alpha", 0.0)