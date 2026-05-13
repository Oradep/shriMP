[Setup]
; Базовые настройки
AppName=shriMP
AppVersion=1.0
AppPublisher=Oradep
AppPublisherURL=https://github.com/Oradep/shriMP

; Установка для конкретного пользователя (без прав администратора)
; Это ВАЖНО, чтобы программа могла сохранять settings.json и базу данных
PrivilegesRequired=lowest
DefaultDirName={autopf}\shriMP
DefaultGroupName=shriMP

; Настройка иконки самого установщика
SetupIconFile=dist\shriMP\icons\icon.ico
UninstallDisplayIcon={app}\shriMP.exe

; Куда сохранить готовый Setup.exe и как его назвать
OutputDir=Output
OutputBaseFilename=shriMP_Setup_v1.0

; Сжатие
Compression=lzma2/ultra
SolidCompression=yes

[Tasks]
; Чекбокс "Создать ярлык на рабочем столе"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Копируем главный файл
Source: "dist\shriMP\shriMP.exe"; DestDir: "{app}"; Flags: ignoreversion

; Копируем все папки (включая _internal, assets, icons)
Source: "dist\shriMP\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\shriMP\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\shriMP\icons\*"; DestDir: "{app}\icons"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Ярлыки в меню Пуск и на рабочем столе
Name: "{group}\shriMP"; Filename: "{app}\shriMP.exe"
Name: "{autodesktop}\shriMP"; Filename: "{app}\shriMP.exe"; Tasks: desktopicon

[Run]
; Предложение запустить после установки
Filename: "{app}\shriMP.exe"; Description: "{cm:LaunchProgram,shriMP}"; Flags: nowait postinstall skipifsilent