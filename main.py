import threading
import time
import keyboard
import pystray
import os
from PIL import Image, ImageDraw
import customtkinter as ctk

from database import Database
from core import PostureCore
from gui import ShrimpGUI

def setup_tray(gui, core):
    def show_window(icon, item): gui.after(0, gui.deiconify)
    def quit_app(icon, item):
        core.is_running = False
        icon.stop()
        gui.quit()
        
    def set_snooze(mins):
        return lambda icon, item: core.set_snooze(mins)

    def set_profile(p_name):
        return lambda icon, item: core.settings.update({"active_profile": p_name}) or core.save_settings()
    
    def is_profile_active(p_name):
        return lambda item: core.settings["active_profile"] == p_name

    def get_profile_items():
        return [pystray.MenuItem(p, set_profile(p), checked=is_profile_active(p), radio=True) 
                for p in core.settings["profiles"].keys()]

    def set_perf(mode):
        return lambda icon, item: core.settings.update({"perf_mode": mode}) or core.save_settings()

    def is_perf_active(mode):
        return lambda item: core.settings.get("perf_mode", "Средняя") == mode

    def load_icon(state):
        try:
            if state == "green":
                return Image.open(os.path.join("icons", "icon_green.ico"))
            elif state == "red":
                return Image.open(os.path.join("icons", "icon_red.ico"))
            else: 
                return Image.open(os.path.join("icons", "icon_gray.ico"))
        except Exception:
            img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
            color_map = {"green": "green", "red": "red", "gray": "gray"}
            ImageDraw.Draw(img).ellipse((8, 8, 56, 56), fill=color_map.get(state, "gray"))
            return img

    snooze_menu = pystray.Menu(
        pystray.MenuItem('15 минут', set_snooze(15)),
        pystray.MenuItem('30 минут', set_snooze(30)),
        pystray.MenuItem('1 час', set_snooze(60)),
        pystray.MenuItem('2 часа', set_snooze(120)),
        pystray.MenuItem('4 часа', set_snooze(240))
    )

    perf_menu = pystray.Menu(
        pystray.MenuItem('Минимальная', set_perf('Минимальная'), checked=is_perf_active('Минимальная'), radio=True),
        pystray.MenuItem('Средняя', set_perf('Средняя'), checked=is_perf_active('Средняя'), radio=True)
    )

    menu = pystray.Menu(
        pystray.MenuItem('Развернуть', show_window),
        pystray.MenuItem('Профиль', pystray.Menu(get_profile_items)),
        pystray.MenuItem('Нагрузка', perf_menu),
        pystray.MenuItem('Сон', snooze_menu, visible=lambda item: not core.is_snoozing()),
        pystray.MenuItem('Пробудить', lambda icon, item: core.wake_up(), visible=lambda item: core.is_snoozing()),
        pystray.MenuItem('Выход', quit_app)
    )
    
    icon = pystray.Icon("shriMP", load_icon("green"), "shriMP", menu)
    
    def update_icon():
        while core.is_running:
            if core.is_snoozing() or "Нет человека" in core.status_text: 
                icon.icon = load_icon("gray")
            elif "Обнаружено" in core.status_text: 
                icon.icon = load_icon("red")
            else: 
                icon.icon = load_icon("green")
            icon.update_menu()
            time.sleep(1)
            
    threading.Thread(target=update_icon, daemon=True).start()
    return icon

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    db = Database()
    core = PostureCore(db)
    
    threading.Thread(target=core.run_camera_loop, daemon=True).start()

    keyboard.add_hotkey('ctrl+alt+p', core.cycle_profile) 
    keyboard.add_hotkey('ctrl+alt+s', lambda: core.set_snooze(15))

    app = ShrimpGUI(core, db)
    tray = setup_tray(app, core)
    threading.Thread(target=tray.run, daemon=True).start()

    app.mainloop()