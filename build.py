import PyInstaller.__main__
import mediapipe
import customtkinter
import os
import shutil

# 1. Очищаем старые сборки
for folder in ['build', 'dist']:
    if os.path.exists(folder):
        shutil.rmtree(folder)

# Автоматически находим пути к сложным библиотекам
mp_path = os.path.dirname(mediapipe.__file__)
ctk_path = os.path.dirname(customtkinter.__file__)

print("Начинаю сборку shriMP...")

# 2. Запускаем PyInstaller (без упаковки assets и icons, мы сделаем это надежнее)
PyInstaller.__main__.run([
    'main.py',
    '--noconsole',                  
    '--name=shriMP',                
    '--icon=icons/icon.ico',        
    f'--add-data={mp_path};mediapipe',          
    f'--add-data={ctk_path};customtkinter',     
    '--hidden-import=pygrabber',    
    '--noconfirm'                   
])

# 3. ЖЕЛЕЗОБЕТОННОЕ КОПИРОВАНИЕ РЕСУРСОВ
print("\nКопирую папки с картинками и звуками...")
dist_app_dir = os.path.join('dist', 'shriMP')

# Копируем всю папку icons со ВСЕМИ файлами внутри
if os.path.exists('icons'):
    shutil.copytree('icons', os.path.join(dist_app_dir, 'icons'), dirs_exist_ok=True)
    print(" -> Папка 'icons' успешно скопирована.")

# Копируем всю папку assets
if os.path.exists('assets'):
    shutil.copytree('assets', os.path.join(dist_app_dir, 'assets'), dirs_exist_ok=True)
    print(" -> Папка 'assets' успешно скопирована.")

print("\nУРА! Сборка завершена. Ищите shriMP.exe в папке dist/shriMP")