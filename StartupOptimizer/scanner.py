import os
import winreg
import subprocess
from pathlib import Path

class StartupScanner:
    def __init__(self):
        self.results = []
    
    def scan_all(self):
        """Запуск всех сканеров"""
        print("=" * 50)
        print("Начало сканирования автозагрузки")
        print("=" * 50)
        
        self.scan_registry()
        self.scan_startup_folders()
        self.scan_services()
        
        print(f"\n✅ Сканирование завершено. Найдено: {len(self.results)} элементов")
        return self.results
    
    def scan_registry(self):
        """Сканирование ключей реестра"""
        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "HKLM\\SOFTWARE\\...\\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce", "HKLM\\...\\RunOnce"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "HKCU\\SOFTWARE\\...\\Run"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU\\...\\RunOnce"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "HKLM\\WOW6432Node\\Run"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run", "HKCU\\StartupApproved\\Run"),
        ]
        
        registry_count = 0
        for hive, path, display_path in registry_paths:
            try:
                key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
                i = 0
                while True:
                    try:
                        name, value, value_type = winreg.EnumValue(key, i)
                        
                        # Определяем, является ли элемент системным
                        is_ms = False
                        if 'microsoft' in value.lower() or 'windows' in value.lower():
                            is_ms = True
                        
                        # Проверяем, существует ли файл
                        is_critical = False
                        if name.lower() in ['securityhealth', 'windowsdefender']:
                            is_critical = True
                        
                        self.results.append({
                            'name': name,
                            'target_path': value,
                            'location': display_path,
                            'type': 'registry',
                            'enabled': True,
                            'is_ms_entry': is_ms,
                            'is_critical': is_critical,
                            'arguments': '',
                            'description': f'Запись в реестре: {display_path}'
                        })
                        registry_count += 1
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except WindowsError:
                pass
        
        print(f"  📁 Реестр: {registry_count} элементов")
    
    def scan_startup_folders(self):
        """Сканирование папок автозагрузки"""
        folders = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"),
            os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs\StartUp"),
        ]
        
        folder_count = 0
        for folder in folders:
            if os.path.exists(folder):
                for file in os.listdir(folder):
                    full_path = os.path.join(folder, file)
                    
                    # Обрабатываем .lnk файлы
                    if file.endswith('.lnk'):
                        target = self._resolve_lnk(full_path)
                        if target:
                            self.results.append({
                                'name': file.replace('.lnk', ''),
                                'target_path': target,
                                'location': folder,
                                'type': 'startup_folder',
                                'enabled': True,
                                'is_ms_entry': False,
                                'is_critical': False,
                                'arguments': '',
                                'description': f'Ярлык в папке автозагрузки'
                            })
                            folder_count += 1
                    elif file.endswith('.exe') or file.endswith('.bat') or file.endswith('.cmd'):
                        self.results.append({
                            'name': file,
                            'target_path': full_path,
                            'location': folder,
                            'type': 'startup_folder',
                            'enabled': True,
                            'is_ms_entry': False,
                            'is_critical': False,
                            'arguments': '',
                            'description': f'Программа в папке автозагрузки'
                        })
                        folder_count += 1
        
        print(f"  📁 Папки автозагрузки: {folder_count} элементов")
    
    def _resolve_lnk(self, lnk_path):
        """Разрешение .lnk файла до целевого пути"""
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortcut(lnk_path)
            return shortcut.TargetPath
        except ImportError:
            # Если win32com не установлен, возвращаем путь к lnk
            return lnk_path
        except:
            return lnk_path
    
    def scan_services(self):
        """Сканирование служб Windows с автозапуском"""
        services_count = 0
        try:
            # Используем sc query для получения списка служб
            result = subprocess.run(
                ['sc', 'query', 'type=', 'service', 'state=', 'all'],
                capture_output=True,
                text=True
            )
            
            lines = result.stdout.split('\n')
            current_service = None
            
            for line in lines:
                if 'SERVICE_NAME:' in line:
                    if current_service and current_service.get('start_type') == 'AUTO_START':
                        self.results.append({
                            'name': current_service['name'],
                            'target_path': f'service://{current_service["name"]}',
                            'location': 'Services',
                            'type': 'service',
                            'enabled': current_service.get('state') == 'RUNNING',
                            'is_ms_entry': 'microsoft' in current_service['name'].lower() or 'windows' in current_service['name'].lower(),
                            'is_critical': current_service['name'].lower() in ['wscsvc', 'wuauserv', 'defender'],
                            'arguments': '',
                            'description': f'Служба Windows: {current_service["name"]}'
                        })
                        services_count += 1
                    
                    current_service = {'name': line.split(':')[1].strip()}
                
                elif 'STATE' in line and ':' in line and current_service:
                    state_part = line.split(':')[1].strip()
                    if 'RUNNING' in state_part:
                        current_service['state'] = 'RUNNING'
                    else:
                        current_service['state'] = 'STOPPED'
                
                elif 'START_TYPE' in line and ':' in line and current_service:
                    start_part = line.split(':')[1].strip()
                    if 'AUTO_START' in start_part or 'AUTO' in start_part:
                        current_service['start_type'] = 'AUTO_START'
            
            # Последняя служба
            if current_service and current_service.get('start_type') == 'AUTO_START':
                self.results.append({
                    'name': current_service['name'],
                    'target_path': f'service://{current_service["name"]}',
                    'location': 'Services',
                    'type': 'service',
                    'enabled': current_service.get('state') == 'RUNNING',
                    'is_ms_entry': 'microsoft' in current_service['name'].lower(),
                    'is_critical': False,
                    'arguments': '',
                    'description': f'Служба Windows: {current_service["name"]}'
                })
                services_count += 1
                
        except Exception as e:
            print(f"  ⚠️ Ошибка при сканировании служб: {e}")
        
        print(f"  ⚙️ Службы: {services_count} элементов")