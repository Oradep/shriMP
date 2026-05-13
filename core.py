# --- START OF FILE: core.py ---
import cv2
import mediapipe as mp
import numpy as np
import time
import json
import os
import wave
import struct
import math
import ctypes
from ctypes import wintypes
import pygame
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

class PostureCore:
    def __init__(self, db):
        self.db = db
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        # ВАЖНО: model_complexity=0 значительно (в 3-4 раза) снижает нагрузку на процессор
        # без потери качества для базовых точек (плечи, глаза), идеально для слабых ПК.
        self.pose = self.mp_pose.Pose(min_detection_confidence=0.6, min_tracking_confidence=0.6, model_complexity=0)
        
        self.is_running = True
        self.camera_index = 0
        self.cap = None
        self.mode = "monitor" 
        self.calibration_frames = []
        self.calibration_start_time = 0

        # Статусы производительности
        self.active_perf_mode = "Средняя"
        self.is_game_running = False
        self.is_high_load = False

        # Инициализация звука (Pygame)
        pygame.mixer.init()
        self.is_playing_sound = False
        self.current_sound_channel = None

        self.assets_dir = "assets"
        os.makedirs(self.assets_dir, exist_ok=True)

        self.config_file = "settings.json"
        self.settings = self.load_settings()
        
        self.bad_posture_timer = None
        self.is_alerting = False
        self.snooze_until = 0
        self.vignette = None
        
        self.current_frame_rgb = None
        self.current_frame_visualized = None 
        self.status_text = "Ожидание..."


    def load_settings(self):
        default_sens = {"slouch": 0.08, "asymmetry": 0.05, "distance": 0.1}
        default_settings = {
            "first_run": True, 
            "perf_mode": "Минимальная", # Новый параметр (Минимальная / Средняя)
            "profiles": {"Работа за столом": {"baseline": None, "sens": default_sens.copy()}},
            "active_profile": "Работа за столом",
            "tolerance_time": 10.0,
            "notifications": {
                "sound": True, "vignette": True,
                "sound_file": 'shrimp.mp3',
                "sound_fade_ms": 500,
                "sound_volume": 0.3,
                "vig_color": "#ff3333", "vig_opacity": 0.5, "vig_thickness": 50
            }
        }
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "first_run" not in data: data["first_run"] = True
                if "perf_mode" not in data: data["perf_mode"] = "Средняя"
                # Удаляем старый параметр toast, если он есть
                if "notifications" in data and "toast" in data["notifications"]:
                    del data["notifications"]["toast"]
                
                if "sound_fade_ms" not in data["notifications"]: data["notifications"]["sound_fade_ms"] = 500
                if "sound_volume" not in data["notifications"]: data["notifications"]["sound_volume"] = 0.5
                return data
        return default_settings

    def save_settings(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=4)

    def get_real_cameras(self):
        try:
            from pygrabber.dshow_graph import FilterGraph
            devices = FilterGraph().get_input_devices()
            return devices if devices else ["Камера не найдена"]
        except:
            return [f"Камера {i}" for i in range(3)]

    def start_calibration(self):
        self.calibration_frames = []
        self.calibration_start_time = time.time()
        self.mode = "calibrate"

    def extract_metrics(self, landmarks):
        lm = landmarks.landmark
        l_sh = lm[self.mp_pose.PoseLandmark.LEFT_SHOULDER]
        r_sh = lm[self.mp_pose.PoseLandmark.RIGHT_SHOULDER]
        return {
            "slouch": (l_sh.y + r_sh.y) / 2.0,
            "asymmetry": abs(l_sh.y - r_sh.y),
            "distance": abs(l_sh.x - r_sh.x),
            "l_sh": l_sh, "r_sh": r_sh 
        }

    def is_fullscreen_app_running(self):
        """Проверяет, открыто ли сейчас полноэкранное приложение (игра)"""
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd: return False
        
        if hwnd == user32.GetDesktopWindow() or hwnd == user32.GetShellWindow():
            return False

        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top

        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)

        return (width == screen_width and height == screen_height)

    def play_sound(self):
        if self.is_playing_sound: return
        sound_file = os.path.join(self.assets_dir, self.settings["notifications"]["sound_file"])
        fade_ms = int(self.settings["notifications"]["sound_fade_ms"])
        volume = float(self.settings["notifications"]["sound_volume"])
        
        if os.path.exists(sound_file):
            try:
                sound = pygame.mixer.Sound(sound_file)
                sound.set_volume(volume)
                self.current_sound_channel = sound.play(fade_ms=fade_ms, loops=0)
                self.is_playing_sound = True
            except Exception as e:
                print(f"Ошибка воспроизведения звука: {e}")

    def stop_sound(self):
        if self.is_playing_sound and self.current_sound_channel:
            fade_ms = int(self.settings["notifications"]["sound_fade_ms"])
            self.current_sound_channel.fadeout(fade_ms)
            self.is_playing_sound = False

    def trigger_alert(self, v_type, log_to_db=False):
        if log_to_db:
            self.db.log_violation(v_type)
            
        notif = self.settings["notifications"]
            
        if notif["sound"]: 
            self.play_sound()
            
        if notif["vignette"] and self.vignette:
            if not self.is_fullscreen_app_running():
                self.vignette.show()

    def draw_visualizers(self, image, metrics, baseline, sens):
        h, w, _ = image.shape
        overlay = image.copy()
        l_sh = metrics["l_sh"]; r_sh = metrics["r_sh"]
        center_x = int(((l_sh.x + r_sh.x) / 2) * w)
        current_y_avg = int(((l_sh.y + r_sh.y) / 2) * h)

        base_y = int(baseline["slouch"] * h)
        limit_y = int((baseline["slouch"] + sens["slouch"]) * h)
        cv2.line(overlay, (0, base_y), (w, base_y), (0, 255, 0), 2)
        cv2.line(overlay, (0, limit_y), (w, limit_y), (255, 0, 0), 2)
        cv2.rectangle(overlay, (0, limit_y), (w, h), (255, 0, 0), -1)

        limit_dist_px = int((baseline["distance"] + sens["distance"]) * w)
        box_left = center_x - (limit_dist_px // 2)
        box_right = center_x + (limit_dist_px // 2)
        cv2.line(overlay, (box_left, 0), (box_left, h), (255, 0, 255), 2) 
        cv2.line(overlay, (box_right, 0), (box_right, h), (255, 0, 255), 2)
        cv2.putText(overlay, "Z-Limit", (box_right + 10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)

        asym_limit_px = int(sens["asymmetry"] * h)
        cv2.line(overlay, (center_x - 100, current_y_avg - asym_limit_px), (center_x + 100, current_y_avg - asym_limit_px), (255, 255, 0), 2)
        cv2.line(overlay, (center_x - 100, current_y_avg + asym_limit_px), (center_x + 100, current_y_avg + asym_limit_px), (255, 255, 0), 2)

        alpha = 0.3
        cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)
        cv2.putText(image, "Slouch limit", (10, limit_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(image, "Asymmetry corridor", (center_x - 90, current_y_avg - asym_limit_px - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        return image

    def set_snooze(self, minutes):
        self.snooze_until = time.time() + (minutes * 60)
        self.stop_sound()
        if self.vignette: self.vignette.hide()

    def wake_up(self):
        self.snooze_until = 0

    def is_snoozing(self):
        return time.time() < self.snooze_until
    

    def cycle_profile(self):
        """Переключает профиль на следующий по списку"""
        profiles = list(self.settings["profiles"].keys())
        if not profiles: return
        
        try:
            current_idx = profiles.index(self.settings["active_profile"])
            next_idx = (current_idx + 1) % len(profiles)
        except ValueError:
            next_idx = 0
            
        self.settings["active_profile"] = profiles[next_idx]
        self.save_settings()



    def run_camera_loop(self):
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_MSMF)
        
        last_process_time = 0
        last_fs_check = 0
        
        # Делаем холостой вызов psutil, так как первый вызов всегда возвращает 0.0
        if HAS_PSUTIL:
            psutil.cpu_percent()
        
        while self.is_running:
            success, image = self.cap.read()
            if not success:
                time.sleep(0.1)
                continue

            image = cv2.flip(image, 1) 
            now = time.time()
            
            # Проверка на полноэкранное приложение и нагрузку (раз в 2 секунды)
            if now - last_fs_check > 2.0:
                self.is_game_running = self.is_fullscreen_app_running()
                
                # ДОБАВЛЕНО: Проверка нагрузки на процессор (>80%)
                if HAS_PSUTIL:
                    cpu_usage = psutil.cpu_percent()
                    self.is_high_load = cpu_usage > 80.0
                else:
                    self.is_high_load = False
                    
                last_fs_check = now

            # Определение активного режима производительности
            user_mode = self.settings.get("perf_mode", "Средняя")
            
            # Если открыта игра ИЛИ система сильно нагружена -> принудительный Минимальный режим
            if self.is_game_running or self.is_high_load:
                self.active_perf_mode = "Минимальная"
            else:
                self.active_perf_mode = user_mode

            # Троттлинг FPS: Средний = ~15 FPS, Минимальный = ~3 FPS
            process_interval = 0.33 if self.active_perf_mode == "Минимальная" else 0.066
            
            # Если время не пришло - пропускаем обработку нейросетью для экономии ресурсов
            if now - last_process_time < process_interval:
                time.sleep(0.01)
                continue
                
            last_process_time = now

            # --- ОСНОВНАЯ ОБРАБОТКА ---
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.pose.process(image_rgb)
            display_img = image_rgb.copy()

            if results.pose_landmarks:
                self.mp_drawing.draw_landmarks(
                    display_img, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS,
                    self.mp_drawing.DrawingSpec(color=(0,255,0), thickness=2, circle_radius=2),
                    self.mp_drawing.DrawingSpec(color=(255,0,0), thickness=2, circle_radius=2)
                )
            
            self.current_frame_rgb = display_img.copy()
            active_prof = self.settings["active_profile"]

            prof_data = self.settings["profiles"].get(active_prof)
            if results.pose_landmarks and prof_data and prof_data.get("baseline"):
                m = self.extract_metrics(results.pose_landmarks)
                vis_img = display_img.copy()
                self.current_frame_visualized = self.draw_visualizers(vis_img, m, prof_data["baseline"], prof_data["sens"])
            else:
                self.current_frame_visualized = display_img.copy()

            if self.mode == "calibrate":
                self.status_text = "Идет калибровка... Сядьте ровно!"
                if results.pose_landmarks: self.calibration_frames.append(self.extract_metrics(results.pose_landmarks))
                if time.time() - self.calibration_start_time > 5.0:
                    if self.calibration_frames:
                        self.settings["profiles"][active_prof]["baseline"] = {
                            "slouch": np.mean([m["slouch"] for m in self.calibration_frames]),
                            "asymmetry": np.mean([m["asymmetry"] for m in self.calibration_frames]),
                            "distance": np.mean([m["distance"] for m in self.calibration_frames])
                        }
                        self.save_settings()
                        self.status_text = f"Эталон '{active_prof}' сохранен!"
                    else: self.status_text = "Ошибка: Человек не найден."
                    self.mode = "monitor"
                continue

            if self.is_snoozing():
                rem_sec = int(self.snooze_until - time.time())
                mins, secs = divmod(rem_sec, 60)
                self.status_text = f"Сон (Осталось {mins:02d}:{secs:02d})"
                continue
            if not prof_data or not prof_data.get("baseline"):
                self.status_text = "Требуется калибровка!"
                continue

            if results.pose_landmarks:
                m = self.extract_metrics(results.pose_landmarks)
                base = prof_data["baseline"]
                sens = prof_data["sens"]
                v_type = None

                if m["slouch"] > base["slouch"] + sens["slouch"]: v_type = "Сутулость"
                elif m["asymmetry"] > base["asymmetry"] + sens["asymmetry"]: v_type = "Перекос плеч"
                elif m["distance"] > base["distance"] + sens["distance"]: v_type = "Близко к экрану"

                if v_type:
                    self.status_text = f"Обнаружено: {v_type}"
                    if self.bad_posture_timer is None: 
                        self.bad_posture_timer = time.time()
                        self.is_alerting = False # Сбрасываем флаг при новом нарушении
                    elif time.time() - self.bad_posture_timer > self.settings["tolerance_time"]:
                        # Передаем True для записи в БД только в первый момент срабатывания
                        self.trigger_alert(v_type, log_to_db=not self.is_alerting)
                        self.is_alerting = True
                else:
                    self.status_text = "Осанка в норме"
                    self.bad_posture_timer = None
                    self.is_alerting = False # Сбрасываем флаг
                    self.stop_sound()
                    if self.vignette: self.vignette.hide()
            else:
                self.status_text = "Нет человека (Sleep Mode)"
                self.bad_posture_timer = None
                self.stop_sound()
                if self.vignette: self.vignette.hide()

        if self.cap: self.cap.release()

    def change_camera(self, index):
        self.camera_index = index
        if self.cap: self.cap.release()
# --- END OF FILE: core.py ---