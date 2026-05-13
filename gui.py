import customtkinter as ctk
from PIL import Image
import os
import shutil
from tkinter import filedialog, messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from overlay import VignetteOverlay
import numpy as np
import time

class ShrimpGUI(ctk.CTk):
    def __init__(self, core, db):
        super().__init__()
        self.core = core
        self.db = db
        
        self.title("shriMP - Умная Осанка")
        self.geometry("1000x750")
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        try:
            self.iconbitmap(os.path.join("icons", "icon.ico"))
        except Exception:
            pass

        self.core.vignette = VignetteOverlay()
        self.apply_vignette_settings()

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.tab_main = self.tabview.add("Главная")
        self.tab_prof = self.tabview.add("Профиль")
        self.tab_notif = self.tabview.add("Уведомления")
        self.tab_stat = self.tabview.add("Статистика")

        self.setup_main_tab()
        self.setup_profile_tab()
        self.setup_notif_tab()
        self.setup_stats_tab()
        
        self.update_ui_loop()
        self.update_video_loop()

        if self.core.settings.get("first_run", True):
            self.after(500, self.show_onboarding)
        else:
            self.withdraw()

    def show_onboarding(self):
        self.core.settings["first_run"] = False
        self.core.save_settings()

        guide = ctk.CTkToplevel(self)
        guide.title("Добро пожаловать в shriMP!")
        
        try:
            guide.iconbitmap(os.path.join("icons", "icon.ico"))
        except Exception:
            pass
            
        guide.attributes("-topmost", True)
        guide.grab_set()

        main_frame = ctk.CTkFrame(guide, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main_frame, text="Добро пожаловать в shriMP! 🦐", font=("Arial", 22, "bold")).pack(pady=(0, 15))
        
        info_text = (
            "Ваш личный фоновый помощник для поддержания идеальной осанки.\n\n"
            "📷 1. Камера\n"
            "Убедитесь, что выбрана правильная веб-камера на главном экране. Мы заботимся о приватности: "
            "видео не записывается и никуда не отправляется, анализируются только координаты точек тела локально.\n\n"
            "📏 2. Калибровка (Создание эталона)\n"
            "Сядьте максимально ровно и комфортно. Нажмите кнопку «Калибровка» и зафиксируйте позу на 5 секунд. "
            "Программа запомнит это положение как идеальное для текущего профиля.\n\n"
            "🗂 3. Профили\n"
            "Создавайте разные профили для разных задач. Каждый профиль имеет свою отдельную калибровку и чувствительность!\n\n"
            "🔔 4. Уведомления и задержка\n"
            "Обязательно настройте «Таймер задержки». Тревога сработает, только если вы сидите криво дольше указанного времени.\n\n"
            "⌨️ 5. Горячие клавиши (работают в фоне):\n"
            " • Ctrl + Alt + C — Быстрая перекалибровка активного профиля.\n"
            " • Ctrl + Alt + S — Режим «Сон» на 30 минут."
        )

        lbl_info = ctk.CTkLabel(main_frame, text=info_text, font=("Arial", 14), justify="left", wraplength=550)
        lbl_info.pack(fill="x", padx=10)

        def close_guide():
            guide.grab_release()
            guide.destroy()

        btn = ctk.CTkButton(main_frame, text="Понятно, начать использование", font=("Arial", 16, "bold"), height=40, command=close_guide)
        btn.pack(pady=(20, 0))

        guide.update_idletasks()
        
        width = guide.winfo_reqwidth() + 20
        height = guide.winfo_reqheight() + 20
        
        screen_width = guide.winfo_screenwidth()
        screen_height = guide.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        
        guide.geometry(f"{width}x{height}+{x}+{y}")

    def create_card(self, parent, title):
        frame = ctk.CTkFrame(parent, corner_radius=10)
        frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(frame, text=title, font=("Arial", 14, "bold")).pack(pady=(10, 5), padx=10, anchor="w")
        return frame

    def create_slider_with_val(self, parent, text, from_, to_, default_val, command, is_int=False):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(frame, text=text).pack(side="left")
        lbl_val = ctk.CTkLabel(frame, text=str(int(default_val) if is_int else round(default_val, 2)), width=40, font=("Arial", 12, "bold"))
        lbl_val.pack(side="right")
        
        def on_change(val):
            display_val = int(val) if is_int else round(val, 2)
            lbl_val.configure(text=str(display_val))
            command(display_val)
            
        sl = ctk.CTkSlider(frame, from_=from_, to=to_, command=on_change)
        sl.set(default_val)
        sl.pack(side="right", fill="x", expand=True, padx=10)
        return sl, lbl_val

    def setup_main_tab(self):
        self.tab_main.grid_columnconfigure(0, weight=2)
        self.tab_main.grid_columnconfigure(1, weight=1)

        video_frame = ctk.CTkFrame(self.tab_main, corner_radius=10)
        video_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.lbl_video_main = ctk.CTkLabel(video_frame, text="Загрузка камеры...")
        self.lbl_video_main.pack(expand=True, fill="both", padx=5, pady=5)

        ctrl_frame = ctk.CTkFrame(self.tab_main, corner_radius=10, fg_color="transparent")
        ctrl_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        card_cam = self.create_card(ctrl_frame, "Камера")
        cams = self.core.get_real_cameras()
        self.cam_var = ctk.StringVar(value=cams[0])
        ctk.CTkOptionMenu(card_cam, variable=self.cam_var, values=cams, command=self.on_cam_change).pack(pady=(0,10), padx=10, fill="x")

        card_prof = self.create_card(ctrl_frame, "Активный профиль [Ctrl+Alt+P]")
        self.main_prof_var = ctk.StringVar(value=self.core.settings["active_profile"])
        self.main_prof_menu = ctk.CTkOptionMenu(card_prof, variable=self.main_prof_var, values=list(self.core.settings["profiles"].keys()), command=self.on_prof_change)
        self.main_prof_menu.pack(pady=(0,10), padx=10, fill="x")

        self.card_snooze = self.create_card(ctrl_frame, "Режим сна")
        self.snooze_times = {"15 мин": 15, "30 мин": 30, "1 час": 60, "2 часа": 120, "4 часа": 240}
        self.snooze_var = ctk.StringVar(value="15 мин")
        self.snooze_menu = ctk.CTkOptionMenu(self.card_snooze, variable=self.snooze_var, values=list(self.snooze_times.keys()))
        self.snooze_menu.pack(pady=(0,5), padx=10, fill="x")
        self.btn_snooze = ctk.CTkButton(self.card_snooze, text="Уснуть [Ctrl+Alt+S]", fg_color="#6c757d", hover_color="#5a6268", command=self.toggle_snooze)
        self.btn_snooze.pack(pady=(0,10), padx=10, fill="x")

        self.card_perf = self.create_card(ctrl_frame, "Нагрузка на систему")
        self.perf_var = ctk.StringVar(value=self.core.settings.get("perf_mode", "Минимальная"))
        self.perf_menu = ctk.CTkOptionMenu(self.card_perf, variable=self.perf_var, values=["Минимальная", "Средняя"], command=self.on_perf_change)
        self.perf_menu.pack(pady=(0,5), padx=10, fill="x")
        
        self.lbl_perf_status = ctk.CTkLabel(self.card_perf, text="", font=("Arial", 11), text_color="gray")
        self.lbl_perf_status.pack(pady=(0,5))

        btn_calib = ctk.CTkButton(ctrl_frame, text="КАЛИБРОВКА (5 сек)", fg_color="#28a745", hover_color="#218838", height=50, font=("Arial", 14, "bold"), command=self.core.start_calibration)
        btn_calib.pack(pady=(20, 0), fill="x", padx=10)
        
        ctk.CTkLabel(ctrl_frame, text="* Эталон сохранится в текущий профиль", font=("Arial", 11, "italic"), text_color="gray").pack(pady=(2, 10))

        self.lbl_status = ctk.CTkLabel(ctrl_frame, text="Статус: Запуск", font=("Arial", 16, "bold"))
        self.lbl_status.pack(pady=10)

    def toggle_snooze(self):
        if self.core.is_snoozing(): self.core.wake_up()
        else: self.core.set_snooze(self.snooze_times[self.snooze_var.get()])

    def setup_profile_tab(self):
        self.tab_prof.grid_columnconfigure(0, weight=1)
        self.tab_prof.grid_columnconfigure(1, weight=1)

        set_frame = ctk.CTkFrame(self.tab_prof, fg_color="transparent")
        set_frame.grid(row=0, column=0, sticky="nsew", padx=5)

        card_add = self.create_card(set_frame, "Создать новый профиль")
        self.entry_new_prof = ctk.CTkEntry(card_add, placeholder_text="Например: Чтение книги...")
        self.entry_new_prof.pack(side="left", fill="x", expand=True, padx=(10,5), pady=(0,10))
        ctk.CTkButton(card_add, text="Добавить", width=100, command=self.add_profile).pack(side="right", padx=(5,10), pady=(0,10))

        card_edit = self.create_card(set_frame, "Настройка допусков")
        
        self.lbl_current_prof_edit = ctk.CTkLabel(
            card_edit, 
            text=f"Активный профиль: {self.core.settings['active_profile']}", 
            font=("Arial", 14, "bold"), 
            text_color="#17a2b8"
        )
        self.lbl_current_prof_edit.pack(pady=(0, 10), padx=10, anchor="w")

        self.sl_slouch, self.lbl_slouch = self.create_slider_with_val(card_edit, "Сутулость (Y-ось):", 0.02, 0.2, 0.08, self.save_profile_settings)
        self.sl_asym, self.lbl_asym = self.create_slider_with_val(card_edit, "Перекос (Асимметрия):", 0.01, 0.15, 0.05, self.save_profile_settings)
        self.sl_dist, self.lbl_dist = self.create_slider_with_val(card_edit, "Приближение (Z-ось):", 0.05, 0.3, 0.1, self.save_profile_settings)
        
        self.btn_delete_prof = ctk.CTkButton(
            card_edit, 
            text="Удалить этот профиль", 
            fg_color="#dc3545", 
            hover_color="#c82333", 
            command=self.delete_profile
        )
        self.btn_delete_prof.pack(pady=(15, 5))

        self.load_profile_settings()

        vis_frame = ctk.CTkFrame(self.tab_prof, corner_radius=10)
        vis_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=10)
        ctk.CTkLabel(vis_frame, text="Визуализация для активного профиля", font=("Arial", 12, "bold")).pack(pady=5)
        self.lbl_video_prof = ctk.CTkLabel(vis_frame, text="Загрузка...")
        self.lbl_video_prof.pack(expand=True, fill="both", padx=5, pady=5)

    def setup_notif_tab(self):
        notif = self.core.settings["notifications"]

        card_time = self.create_card(self.tab_notif, "Таймер задержки (сек)")
        time_frame = ctk.CTkFrame(card_time, fg_color="transparent")
        time_frame.pack(fill="x", padx=10, pady=5)
        self.sl_time = ctk.CTkSlider(time_frame, from_=1, to=60, command=self.on_time_slider)
        self.sl_time.set(self.core.settings["tolerance_time"])
        self.sl_time.pack(side="left", fill="x", expand=True, padx=(0,10))
        self.entry_time = ctk.CTkEntry(time_frame, width=50)
        self.entry_time.insert(0, str(int(self.core.settings["tolerance_time"])))
        self.entry_time.pack(side="right")
        self.entry_time.bind("<Return>", self.on_time_entry)
        self.entry_time.bind("<FocusOut>", self.on_time_entry)

        card_sound = self.create_card(self.tab_notif, "Звуковые уведомления")
        self.chk_sound = ctk.CTkSwitch(card_sound, text="Включить звук", command=self.save_global_settings)
        if notif["sound"]: self.chk_sound.select()
        self.chk_sound.pack(anchor="w", padx=10, pady=5)

        sound_ctrl = ctk.CTkFrame(card_sound, fg_color="transparent")
        sound_ctrl.pack(fill="x", padx=10, pady=5)
        self.sound_var = ctk.StringVar(value=notif["sound_file"])
        self.sound_menu = ctk.CTkOptionMenu(sound_ctrl, variable=self.sound_var, values=self.get_sound_list(), command=self.on_sound_select)
        self.sound_menu.pack(side="left", fill="x", expand=True, padx=(0,5))
        ctk.CTkButton(sound_ctrl, text="Удалить", width=60, fg_color="#dc3545", hover_color="#c82333", command=self.delete_sound).pack(side="left", padx=5)
        ctk.CTkButton(sound_ctrl, text="Добавить свой (.wav, .mp3, .ogg)", width=150, command=self.upload_sound).pack(side="right") 

        self.sl_volume, _ = self.create_slider_with_val(card_sound, "Громкость звука:", 0.0, 1.0, notif.get("sound_volume", 0.5), self.save_global_settings)
        self.sl_fade, _ = self.create_slider_with_val(card_sound, "Плавность звука (Fade ms):", 0, 2000, notif["sound_fade_ms"], self.save_global_settings, is_int=True)

        frame_rep = ctk.CTkFrame(card_sound, fg_color="transparent")
        frame_rep.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(frame_rep, text="Повтор звука:").pack(side="left")
        self.lbl_rep_val = ctk.CTkLabel(frame_rep, text="", width=100, font=("Arial", 12, "bold"))
        self.lbl_rep_val.pack(side="right")

        def on_rep_change(val):
            v = int(val)
            if v == -1: txt = "Непрерывно"
            elif v == 0: txt = "Один раз"
            else: txt = f"Каждые {v} сек"
            self.lbl_rep_val.configure(text=txt)
            self.core.settings["notifications"]["sound_repeat_sec"] = v
            self.core.save_settings()

        self.sl_rep = ctk.CTkSlider(frame_rep, from_=-1, to=60, number_of_steps=61, command=on_rep_change)
        curr_rep = notif.get("sound_repeat_sec", 0)
        self.sl_rep.set(curr_rep)
        on_rep_change(curr_rep)
        self.sl_rep.pack(side="right", fill="x", expand=True, padx=10)

        self.btn_play_sound = ctk.CTkButton(card_sound, text="▶ Прослушать звук", command=self.preview_sound)
        self.btn_play_sound.pack(pady=(10, 15))

        card_vig = self.create_card(self.tab_notif, "Визуальные уведомления (Виньетка)")
        self.chk_vignette = ctk.CTkSwitch(card_vig, text="Включить красную рамку (отключается в играх автоматически)", command=self.save_global_settings)
        if notif["vignette"]: self.chk_vignette.select()
        self.chk_vignette.pack(anchor="w", padx=10, pady=5)

        colors = {"Красный": "#ff3333", "Оранжевый": "#ffaa00", "Синий": "#3366ff", "Фиолетовый": "#9933ff"}
        self.vig_color_var = ctk.StringVar(value=list(colors.keys())[list(colors.values()).index(notif["vig_color"])])
        color_frame = ctk.CTkFrame(card_vig, fg_color="transparent")
        color_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(color_frame, text="Цвет рамки:").pack(side="left")
        ctk.CTkOptionMenu(color_frame, variable=self.vig_color_var, values=list(colors.keys()), command=lambda c: self.save_vignette_settings(colors[c])).pack(side="right")

        self.sl_vig_opac, _ = self.create_slider_with_val(card_vig, "Яркость (непрозрачность):", 0.1, 1.0, notif["vig_opacity"], self.save_vignette_settings)
        self.sl_vig_thick, _ = self.create_slider_with_val(card_vig, "Толщина градиента:", 10, 150, notif["vig_thickness"], self.save_vignette_settings, is_int=True)

        self.btn_preview_vig = ctk.CTkButton(card_vig, text="👁 Показать виньетку (5 сек)", command=self.preview_vignette)
        self.btn_preview_vig.pack(pady=(10, 15))

    def preview_sound(self):
        if self.core.is_playing_sound:
            self.core.is_preview_sound = False 
            self.core.stop_sound()
        else:
            self.save_global_settings() 
            self.core.is_preview_sound = True 
            self.core.play_sound(force=True)

    def preview_vignette(self):
        self.core.is_preview_vignette = True 
        self.apply_vignette_settings()
        self.core.vignette.show()
        
        if hasattr(self, '_vig_timer') and self._vig_timer:
            self.after_cancel(self._vig_timer)
            
        def stop_vig_preview():
            self.core.is_preview_vignette = False 
            self.core.vignette.hide()
            
        self._vig_timer = self.after(5000, stop_vig_preview)

    def setup_stats_tab(self):
        ctrl_frame = ctk.CTkFrame(self.tab_stat, fg_color="transparent")
        ctrl_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(ctrl_frame, text="Выберите дату:").pack(side="left", padx=10)
        
        self.dates_list = self.db.get_available_dates()
        self.date_var = ctk.StringVar(value=self.dates_list[0] if self.dates_list else "Нет данных")
        
        self.date_menu = ctk.CTkOptionMenu(ctrl_frame, variable=self.date_var, values=self.dates_list, command=self.draw_charts)
        self.date_menu.pack(side="left", padx=10)
        
        self.btn_refresh = ctk.CTkButton(ctrl_frame, text="Обновить", command=lambda: self.draw_charts(self.date_var.get()))
        self.btn_refresh.pack(side="left", padx=10)

        self.canvas_frame = ctk.CTkFrame(self.tab_stat)
        self.canvas_frame.pack(fill="both", expand=True)
        
        self.draw_charts(self.date_var.get())

    def draw_charts(self, selected_date=None):
        if not selected_date: selected_date = self.date_var.get()
        if selected_date == "Нет данных": return

        new_dates = self.db.get_available_dates()
        if new_dates != self.dates_list:
            self.dates_list = new_dates
            self.date_menu.configure(values=self.dates_list)

        for widget in self.canvas_frame.winfo_children(): widget.destroy()
        
        stats_pie = self.db.get_stats_by_date(selected_date)
        stats_bar = self.db.get_hourly_stats(selected_date)

        if not stats_pie:
            ctk.CTkLabel(self.canvas_frame, text=f"{selected_date}: Нарушений нет! Score: 100%", font=("Arial", 18, "bold"), text_color="green").pack(expand=True)
            return

        total_violations = sum(stats_pie.values())
        score = max(0, 100 - (total_violations * 2)) 
        
        lbl_score = ctk.CTkLabel(self.canvas_frame, text=f"Индекс осанки за {selected_date}: {score}% (Нарушений: {total_violations})", font=("Arial", 20, "bold"))
        lbl_score.pack(pady=10)
        lbl_score.configure(text_color="#ff3333" if score < 50 else "#ffaa00" if score < 80 else "#28a745")

        fig = Figure(figsize=(9, 4.5), dpi=100)
        fig.patch.set_facecolor('#2b2b2b') 
        
        violation_types = list(stats_pie.keys())
        palette = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99']
        type_colors = {v_type: palette[i % len(palette)] for i, v_type in enumerate(violation_types)}

        ax1 = fig.add_subplot(121)
        ax1.set_title("Типы нарушений", color='white')
        ax1.pie(list(stats_pie.values()), labels=violation_types, autopct='%1.1f%%', startangle=90, 
                colors=[type_colors[t] for t in violation_types], textprops={'color':"w"})
        
        ax2 = fig.add_subplot(122)
        ax2.set_title("Нарушения по часам", color='white')
        
        hours = [f"{i:02d}" for i in range(24)]
        bottoms = np.zeros(24) 
        
        for v_type in violation_types:
            counts = [stats_bar[h].get(v_type, 0) for h in hours]
            ax2.bar(hours, counts, bottom=bottoms, color=type_colors[v_type], label=v_type)
            bottoms += np.array(counts)
        
        ax2.set_xticks(hours[::2]) 
        ax2.tick_params(axis='x', colors='white')
        ax2.tick_params(axis='y', colors='white')
        
        for spine in ax2.spines.values():
            spine.set_edgecolor('#555555')
        ax2.set_facecolor('#2b2b2b')

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def on_perf_change(self, choice):
        self.core.settings["perf_mode"] = choice
        self.core.save_settings()

    def on_time_slider(self, val):
        self.entry_time.delete(0, 'end')
        self.entry_time.insert(0, str(int(val)))
        self.core.settings["tolerance_time"] = float(val)
        self.core.save_settings()

    def on_time_entry(self, event=None):
        try:
            val = float(self.entry_time.get())
            if val < 1: val = 1.0
            self.core.settings["tolerance_time"] = val
            self.core.save_settings()
            if val <= 60: self.sl_time.set(val)
        except ValueError:
            self.entry_time.delete(0, 'end')
            self.entry_time.insert(0, str(int(self.core.settings["tolerance_time"])))

    def get_sound_list(self):
        valid_ext = ('.wav', '.mp3', '.ogg')
        files = [f for f in os.listdir(self.core.assets_dir) if f.lower().endswith(valid_ext)]
        return files if files else self.core.default_sounds

    def upload_sound(self):
        filepath = filedialog.askopenfilename(
            title="Выберите аудио файл", 
            filetypes=[("Audio Files", "*.wav *.mp3 *.ogg")]
        )
        if filepath:
            filename = os.path.basename(filepath)
            dest = os.path.join(self.core.assets_dir, filename)
            shutil.copy(filepath, dest)
            self.sound_menu.configure(values=self.get_sound_list())
            self.sound_var.set(filename)
            self.on_sound_select(filename)

    def delete_sound(self):
        selected = self.sound_var.get()
        if selected in self.core.default_sounds:
            messagebox.showwarning("Ошибка", "Нельзя удалить стандартный звук!")
            return
        path = os.path.join(self.core.assets_dir, selected)
        if os.path.exists(path):
            os.remove(path)
            new_list = self.get_sound_list()
            self.sound_menu.configure(values=new_list)
            self.sound_var.set(new_list[0])
            self.on_sound_select(new_list[0])

    def on_sound_select(self, choice):
        self.core.settings["notifications"]["sound_file"] = choice
        self.core.save_settings()

    def save_vignette_settings(self, color_hex=None):
        notif = self.core.settings["notifications"]
        if color_hex and isinstance(color_hex, str): notif["vig_color"] = color_hex
        notif["vig_opacity"] = self.sl_vig_opac.get()
        notif["vig_thickness"] = int(self.sl_vig_thick.get())
        self.core.save_settings()
        self.apply_vignette_settings()

    def apply_vignette_settings(self):
        n = self.core.settings["notifications"]
        self.core.vignette.update_settings(n["vig_color"], n["vig_thickness"], n["vig_opacity"])

    def on_cam_change(self, choice):
        idx = self.core.get_real_cameras().index(choice)
        self.core.change_camera(idx)

    def on_prof_change(self, choice):
        self.core.settings["active_profile"] = choice
        self.core.save_settings()
        self.load_profile_settings() 

    def add_profile(self):
        new_name = self.entry_new_prof.get().strip()
        if new_name and new_name not in self.core.settings["profiles"]:
            self.core.settings["profiles"][new_name] = {"baseline": None, "sens": {"slouch": 0.08, "asymmetry": 0.05, "distance": 0.1}}
            self.core.settings["active_profile"] = new_name
            self.core.save_settings()
            
            vals = list(self.core.settings["profiles"].keys())
            self.main_prof_menu.configure(values=vals)
            self.main_prof_var.set(new_name)
            
            self.load_profile_settings()
            self.entry_new_prof.delete(0, 'end')

    def delete_profile(self):
        current_prof = self.core.settings["active_profile"]
        
        if len(self.core.settings["profiles"]) <= 1:
            messagebox.showwarning("Ошибка", "Нельзя удалить единственный профиль! Создайте новый, чтобы удалить этот.")
            return
            
        confirm = messagebox.askyesno(
            "Удаление профиля", 
            f"Вы уверены, что хотите удалить профиль '{current_prof}'?\n\nЭталонная поза и настройки чувствительности будут потеряны безвозвратно."
        )
        
        if confirm:
            del self.core.settings["profiles"][current_prof]
            
            new_prof = list(self.core.settings["profiles"].keys())[0]
            self.core.settings["active_profile"] = new_prof
            self.core.save_settings()
            
            vals = list(self.core.settings["profiles"].keys())
            self.main_prof_menu.configure(values=vals)
            self.main_prof_var.set(new_prof)
            
            self.load_profile_settings()

    def load_profile_settings(self):
        prof_name = self.core.settings["active_profile"]
        
        if hasattr(self, 'lbl_current_prof_edit'):
            self.lbl_current_prof_edit.configure(text=f"Активный профиль: {prof_name}")

        sens = self.core.settings["profiles"][prof_name]["sens"]
        self.sl_slouch.set(sens["slouch"])
        self.lbl_slouch.configure(text=str(round(sens["slouch"], 2)))
        self.sl_asym.set(sens["asymmetry"])
        self.lbl_asym.configure(text=str(round(sens["asymmetry"], 2)))
        self.sl_dist.set(sens["distance"])
        self.lbl_dist.configure(text=str(round(sens["distance"], 2)))

    def save_profile_settings(self, _=None):
        prof_name = self.core.settings["active_profile"]
        self.core.settings["profiles"][prof_name]["sens"] = {
            "slouch": self.sl_slouch.get(),
            "asymmetry": self.sl_asym.get(),
            "distance": self.sl_dist.get()
        }
        self.core.save_settings()

    def save_global_settings(self, _=None):
        self.core.settings["notifications"]["sound"] = self.chk_sound.get() == 1
        self.core.settings["notifications"]["vignette"] = self.chk_vignette.get() == 1
        self.core.settings["notifications"]["sound_fade_ms"] = int(self.sl_fade.get())
        self.core.settings["notifications"]["sound_volume"] = self.sl_volume.get()
        self.core.save_settings()

    def update_video_loop(self):
        current_tab = self.tabview.get()
        
        if current_tab == "Главная" and self.core.current_frame_rgb is not None:
            img = Image.fromarray(self.core.current_frame_rgb)
            ctk_img = ctk.CTkImage(light_image=img, size=(500, 380))
            self.lbl_video_main.configure(image=ctk_img, text="")
            
        elif current_tab == "Профиль" and self.core.current_frame_visualized is not None:
            img = Image.fromarray(self.core.current_frame_visualized)
            ctk_img = ctk.CTkImage(light_image=img, size=(450, 340))
            self.lbl_video_prof.configure(image=ctk_img, text="")
            
        self.after(30, self.update_video_loop)

    def update_ui_loop(self):
        if self.core.is_playing_sound and self.core.current_sound_channel:
            if not self.core.current_sound_channel.get_busy():
                self.core.is_playing_sound = False
                self.core.is_preview_sound = False

        if hasattr(self, 'btn_play_sound'):
            if self.core.is_playing_sound:
                self.btn_play_sound.configure(text="⏹ Остановить звук", fg_color="#dc3545", hover_color="#c82333")
            else:
                default_fg = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
                default_hover = ctk.ThemeManager.theme["CTkButton"]["hover_color"]
                self.btn_play_sound.configure(text="▶ Прослушать звук", fg_color=default_fg, hover_color=default_hover)

        current_core_prof = self.core.settings["active_profile"]
        if self.main_prof_var.get() != current_core_prof:
            self.main_prof_var.set(current_core_prof)
            self.load_profile_settings()

        current_perf = self.core.settings.get("perf_mode", "Средняя")
        if getattr(self, "perf_var", None) and self.perf_var.get() != current_perf:
            self.perf_var.set(current_perf)

        if self.core.is_snoozing():
            rem_sec = int(self.core.snooze_until - time.time())
            mins, secs = divmod(rem_sec, 60)
            self.btn_snooze.configure(text=f"ПРОБУДИТЬ ({mins:02d}:{secs:02d})", fg_color="#17a2b8", hover_color="#138496")
            self.snooze_menu.pack_forget()
        else:
            self.btn_snooze.configure(text="Уснуть [Ctrl+Alt+S]", fg_color="#6c757d", hover_color="#5a6268")
            self.snooze_menu.pack(pady=(0,5), padx=10, fill="x", before=self.btn_snooze)

        if self.core.is_game_running:
            self.lbl_perf_status.configure(text="Текущий режим: Минимальный (Открыта игра)", text_color="#ffaa00")
        elif getattr(self.core, 'is_high_load', False):
            self.lbl_perf_status.configure(text="Текущий режим: Минимальный (Высокая нагрузка ЦП)", text_color="#ffaa00")
        elif not getattr(self.core, 'HAS_PSUTIL', True) and hasattr(self, 'lbl_perf_status'):
            self.lbl_perf_status.configure(text=f"Текущий режим: {self.core.active_perf_mode} (Установите psutil)", text_color="gray")
        else:
            self.lbl_perf_status.configure(text=f"Текущий режим: {self.core.active_perf_mode}", text_color="gray")

        self.lbl_status.configure(text=f"Статус: {self.core.status_text}")
        if "Нарушено" in self.core.status_text or "Обнаружено" in self.core.status_text:
            self.lbl_status.configure(text_color="#ff3333")
        elif "Калибровка" in self.core.status_text:
            self.lbl_status.configure(text_color="#ffaa00")
        else:
            self.lbl_status.configure(text_color="#28a745")
            
        self.after(500, self.update_ui_loop)

    def hide_to_tray(self):
        self.withdraw()