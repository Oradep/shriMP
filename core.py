import cv2
import mediapipe as mp
import numpy as np
import time
import json
import os
import math
import ctypes
from ctypes import wintypes
import pygame
import subprocess
import sys

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
        self.pose = self.mp_pose.Pose(min_detection_confidence=0.6, min_tracking_confidence=0.6, model_complexity=0)
        
        self.is_running = True
        self.camera_index = 0
        self.cap = None
        self.mode = "monitor" 
        self.calibration_frames = []
        self.calibration_start_time = 0

        self.active_perf_mode = "Средняя"
        self.is_game_running = False
        self.is_high_load = False


        self.default_sounds = ['shrimp.mp3', "ALARM.wav"]


        pygame.mixer.init()
        self.is_playing_sound = False
        self.current_sound_channel = None

        self.assets_dir = "assets"
        os.makedirs(self.assets_dir, exist_ok=True)

        self.config_file = "settings.json"
        self.settings = self.load_settings()
        
        self.bad_posture_timer = None
        self.last_sound_time = 0
        self.is_alerting = False
        self.snooze_until = 0
        self.vignette = None
        
        self.is_preview_sound = False
        self.is_preview_vignette = False
        
        self.current_frame_rgb = None
        self.current_frame_visualized = None 
        self.status_text = "Ожидание..."

    def load_settings(self):
        default_sens = {"slouch": 0.08, "asymmetry": 0.5, "distance": 0.1}
        default_settings = {
            "first_run": True, 
            "autostart": False,
            "perf_mode": "Средняя",
            "profiles": {"Работа за столом": {"baseline": None, "sens": default_sens.copy()}},
            "active_profile": "Работа за столом",
            "tolerance_time": 10.0,
            "notifications": {
                "sound": True, 
                "vignette": True,
                "sound_file": 'shrimp.mp3',
                "sound_fade_ms": 500,
                "sound_volume": 0.06,
                "vig_color": "#ff3333", 
                "vig_opacity": 0.5, 
                "vig_thickness": 50,
                "sound_repeat_sec": 0
            }
        }

        def merge_defaults(loaded_data, defaults):
            for key, value in defaults.items():
                if key not in loaded_data:
                    loaded_data[key] = value
                elif isinstance(value, dict) and isinstance(loaded_data[key], dict):
                    if key == "profiles" and loaded_data[key]:
                        continue
                    merge_defaults(loaded_data[key], value)
            return loaded_data

        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return merge_defaults(data, default_settings)
            except json.JSONDecodeError:
                pass 
                
        return default_settings

    def save_settings(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=4)



    def toggle_autostart(self, enable):
        #путь к папке shell:startup
        startup_folder = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
        shortcut_path = os.path.join(startup_folder, "shriMP.lnk")

        if enable:
            #скрипт или .exe
            target = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
            working_dir = os.path.dirname(target)
            

            ps_script = (
                f'$s=(New-Object -COM WScript.Shell).CreateShortcut("{shortcut_path}");'
                f'$s.TargetPath="{target}";'
                f'$s.WorkingDirectory="{working_dir}";'
                f'$s.Save()'
            )
            try:
                subprocess.run(["powershell", "-Command", ps_script], creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception as e:
                print(f"Ошибка создания ярлыка автозапуска: {e}")
        else:
            if os.path.exists(shortcut_path):
                try:
                    os.remove(shortcut_path)
                except Exception as e:
                    print(f"Ошибка удаления ярлыка автозапуска: {e}")

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

    def extract_metrics(self, landmarks, w, h):
        lm = landmarks.landmark
        l_sh = lm[self.mp_pose.PoseLandmark.LEFT_SHOULDER]
        r_sh = lm[self.mp_pose.PoseLandmark.RIGHT_SHOULDER]
        
        dx = (r_sh.x - l_sh.x) * w
        dy = (r_sh.y - l_sh.y) * h
        
        if dx < 0:
            dx = -dx
            dy = -dy

            
        angle = math.degrees(math.atan2(dy, dx))
        
        return {
            "slouch": (l_sh.y + r_sh.y) / 2.0,
            "asymmetry": abs(l_sh.y - r_sh.y), 
            "distance": abs(l_sh.x - r_sh.x),
            "angle": angle,
            "l_sh": l_sh, "r_sh": r_sh 
        }

    def is_fullscreen_app_running(self):
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

    def play_sound(self, force=False):
        if self.is_playing_sound and not force: return
        
        sound_file = os.path.join(self.assets_dir, self.settings["notifications"]["sound_file"])
        fade_ms = int(self.settings["notifications"]["sound_fade_ms"])
        volume = float(self.settings["notifications"]["sound_volume"])
        
        rep_sec = self.settings["notifications"].get("sound_repeat_sec", 0)
        loops_val = -1 if rep_sec == -1 else 0
        
        if os.path.exists(sound_file):
            try:
                if self.current_sound_channel and force:
                    self.current_sound_channel.stop()
                    
                sound = pygame.mixer.Sound(sound_file)
                sound.set_volume(volume)
                self.current_sound_channel = sound.play(fade_ms=fade_ms, loops=loops_val)
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
            self.play_sound(force=True)
            
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
        
        #тригонометря
        angle_deg = baseline.get("angle", 0.0)
        rad = math.radians(angle_deg)
        tan_a = math.tan(rad)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        def get_line_pts(y_center):
            y_left = int(tan_a * (0 - center_x) + y_center)
            y_right = int(tan_a * (w - center_x) + y_center)
            return (0, y_left), (w, y_right)

        green_pt1, green_pt2 = get_line_pts(base_y)
        red_pt1, red_pt2 = get_line_pts(limit_y)


        cv2.line(overlay, green_pt1, green_pt2, (0, 255, 0), 2)
        cv2.line(overlay, red_pt1, red_pt2, (255, 0, 0), 2)
        

        pts = np.array([red_pt1, red_pt2, (w, h), (0, h)], np.int32)
        cv2.fillPoly(overlay, [pts], (255, 0, 0))


        def get_short_line_pts(y_center, dx=100):
            y1 = int(tan_a * (-dx) + y_center)
            y2 = int(tan_a * (dx) + y_center)
            return (center_x - dx, y1), (center_x + dx, y2)

        asym_limit_px = int(sens["asymmetry"] * h)
        asym_top_1, asym_top_2 = get_short_line_pts(current_y_avg - asym_limit_px, 100)
        asym_bot_1, asym_bot_2 = get_short_line_pts(current_y_avg + asym_limit_px, 100)
        
        cv2.line(overlay, asym_top_1, asym_top_2, (255, 255, 0), 2)
        cv2.line(overlay, asym_bot_1, asym_bot_2, (255, 255, 0), 2)


        limit_dist_px = int((baseline["distance"] + sens["distance"]) * w)
        dx_box = limit_dist_px // 2

        def get_perp_line_pts(offset_x):
            cx_line = center_x + offset_x * cos_a
            cy_line = current_y_avg + offset_x * sin_a

            x1 = int(cx_line - 1000 * (-sin_a))
            y1 = int(cy_line - 1000 * (cos_a))
            x2 = int(cx_line + 1000 * (-sin_a))
            y2 = int(cy_line + 1000 * (cos_a))
            return (x1, y1), (x2, y2)

        z_left_1, z_left_2 = get_perp_line_pts(-dx_box)
        z_right_1, z_right_2 = get_perp_line_pts(dx_box)

        cv2.line(overlay, z_left_1, z_left_2, (255, 0, 255), 2)
        cv2.line(overlay, z_right_1, z_right_2, (255, 0, 255), 2)
        cv2.putText(overlay, "Z-Limit", (z_right_1[0] + 10, max(30, z_right_1[1])), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)

        alpha = 0.3
        cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)
        cv2.putText(image, "Slouch limit", (10, red_pt1[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(image, "Asymmetry corridor", (center_x - 90, asym_top_1[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

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
        
        if HAS_PSUTIL:
            psutil.cpu_percent()
        
        while self.is_running:
            success, image = self.cap.read()
            if not success:
                time.sleep(0.1)
                continue

            image = cv2.flip(image, 1) 
            now = time.time()
            
            if now - last_fs_check > 2.0:
                self.is_game_running = self.is_fullscreen_app_running()
                
                if HAS_PSUTIL:
                    self.is_high_load = psutil.cpu_percent() > 80.0
                else:
                    self.is_high_load = False
                    
                last_fs_check = now

            user_mode = self.settings.get("perf_mode", "Средняя")
            
            if self.is_game_running or self.is_high_load:
                self.active_perf_mode = "Минимальная"
            else:
                self.active_perf_mode = user_mode

            process_interval = 0.33 if self.active_perf_mode == "Минимальная" else 0.066
            
            if now - last_process_time < process_interval:
                time.sleep(0.01)
                continue
                
            last_process_time = now

            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            h, w, _ = image_rgb.shape 
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
                m = self.extract_metrics(results.pose_landmarks, w, h) 
                vis_img = display_img.copy()
                self.current_frame_visualized = self.draw_visualizers(vis_img, m, prof_data["baseline"], prof_data["sens"])
            else:
                self.current_frame_visualized = display_img.copy()

            if self.mode == "calibrate":
                self.status_text = "Идет калибровка... Сядьте ровно!"
                if results.pose_landmarks: 
                    self.calibration_frames.append(self.extract_metrics(results.pose_landmarks, w, h))
                if time.time() - self.calibration_start_time > 5.0:
                    if self.calibration_frames:
                        self.settings["profiles"][active_prof]["baseline"] = {
                            "slouch": np.mean([m["slouch"] for m in self.calibration_frames]),
                            "asymmetry": 0.0, 
                            "distance": np.mean([m["distance"] for m in self.calibration_frames]),
                            "angle": np.mean([m["angle"] for m in self.calibration_frames])
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
                m = self.extract_metrics(results.pose_landmarks, w, h)
                base = prof_data["baseline"]
                sens = prof_data["sens"]
                v_type = None

            
                base_angle_rad = math.radians(base.get("angle", 0.0))
                lx_px = m["l_sh"].x * w
                ly_px = m["l_sh"].y * h
                rx_px = m["r_sh"].x * w
                ry_px = m["r_sh"].y * h
                cx_px = (lx_px + rx_px) / 2
                cy_px = (ly_px + ry_px) / 2
                
                rot_y_l = (lx_px - cx_px) * math.sin(-base_angle_rad) + (ly_px - cy_px) * math.cos(-base_angle_rad)
                rot_y_r = (rx_px - cx_px) * math.sin(-base_angle_rad) + (ry_px - cy_px) * math.cos(-base_angle_rad)
                true_asymmetry = abs(rot_y_l - rot_y_r) / h

                if m["slouch"] > base["slouch"] + sens["slouch"]: v_type = "Сутулость"
                elif true_asymmetry > sens["asymmetry"]: v_type = "Перекос плеч"
                elif m["distance"] > base["distance"] + sens["distance"]: v_type = "Близко к экрану"

                if v_type:
                    self.status_text = f"Обнаружено: {v_type}"
                    if self.bad_posture_timer is None: 
                        self.bad_posture_timer = time.time()
                        self.is_alerting = False
                    elif time.time() - self.bad_posture_timer > self.settings["tolerance_time"]:
                        if not self.is_alerting:
                            self.trigger_alert(v_type, log_to_db=True)
                            self.is_alerting = True
                            self.last_sound_time = time.time()
                        else:
                            rep_sec = self.settings["notifications"].get("sound_repeat_sec", 0)
                            if rep_sec > 0 and (time.time() - self.last_sound_time) >= rep_sec:
                                if self.settings["notifications"]["sound"]:
                                    self.play_sound(force=True)
                                self.last_sound_time = time.time()
                else:
                    self.status_text = "Осанка в норме"
                    self.bad_posture_timer = None
                    self.is_alerting = False
                    
                    if not self.is_preview_sound:
                        self.stop_sound()
                    if self.vignette and not self.is_preview_vignette: 
                        self.vignette.hide()
            else:
                self.status_text = "Нет человека (Sleep Mode)"
                self.bad_posture_timer = None
                
                if not self.is_preview_sound:
                    self.stop_sound()
                if self.vignette and not self.is_preview_vignette: 
                    self.vignette.hide()

        if self.cap: self.cap.release()

    def change_camera(self, index):
        self.camera_index = index
        if self.cap: self.cap.release()