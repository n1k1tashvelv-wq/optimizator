# fix_optimizer.py - временный фикс
import os

# Содержимое исправленного optimizer.py
fixed_code = '''import os
import winreg
import subprocess
import shutil
from datetime import datetime

class StartupOptimizer:
    def __init__(self, db_manager):
        self.db = db_manager
        self.optimization_log = []
    
    def disable_entry(self, entry):
        """Отключение элемента автозагрузки"""
        entry_type = entry.get('type', '')
        entry_id = entry.get('id')
        entry_name = entry.get('name', 'unknown')
        
        try:
            if entry_type == 'registry':
                success = self._disable_registry_entry(entry)
            elif entry_type == 'startup_folder':
                success = self._disable_startup_folder_entry(entry)
            elif entry_type == 'service':
                success = self._disable_service(entry)
            else:
                print(f"Неизвестный тип: {entry_type}")
                success = False
            
            if success:
                self.optimization_log.append({
                    'time': datetime.now(),
                    'entry_id': entry_id,
                    'name': entry_name,
                    'action': 'disabled'
                })
            
            return success
            
        except Exception as error:
            print(f"Ошибка при отключении {entry_name}: {error}")
            return False
    
    def _disable_registry_entry(self, entry):
        try:
            location = entry.get('location', '')
            name = entry.get('name', '')
            entry_id = entry.get('id')
            self.db.create_backup(entry_id, location, name)
            
            if 'HKLM' in location:
                hive = winreg.HKEY_LOCAL_MACHINE
            elif 'HKCU' in location:
                hive = winreg.HKEY_CURRENT_USER
            else:
                return False
            
            path = "SOFTWARE\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Run"
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE)
            
            try:
                value, _ = winreg.QueryValueEx(key, name)
                backup_name = f"_disabled_{name}"
                winreg.SetValueEx(key, backup_name, 0, winreg.REG_SZ, value)
                winreg.DeleteValue(key, name)
                winreg.CloseKey(key)
                self.db.update_entry_state(entry_id, False)
                print(f"  ✅ Отключено: {name}")
                return True
            except WindowsError as error:
                winreg.CloseKey(key)
                print(f"  ⚠️ Ошибка: {error}")
                return False
        except Exception as error:
            print(f"  ❌ Ошибка: {error}")
            return False
    
    def _disable_startup_folder_entry(self, entry):
        try:
            name = entry.get('name', '')
            location = entry.get('location', '')
            entry_id = entry.get('id')
            
            if not location or not os.path.exists(location):
                return False
            
            for file in os.listdir(location):
                if name in file:
                    src = os.path.join(location, file)
                    dst = os.path.join(location, f"_disabled_{file}")
                    self.db.create_backup(entry_id, src, file)
                    shutil.move(src, dst)
                    self.db.update_entry_state(entry_id, False)
                    print(f"  ✅ Отключено: {name}")
                    return True
            return False
        except Exception as error:
            print(f"  ❌ Ошибка: {error}")
            return False
    
    def _disable_service(self, entry):
        try:
            service_name = entry.get('name', '')
            entry_id = entry.get('id')
            self.db.create_backup(entry_id, f'service://{service_name}', 'auto_start')
            
            result = subprocess.run(['sc', 'config', service_name, 'start=', 'disabled'], 
                                   capture_output=True, text=True)
            
            if result.returncode == 0:
                self.db.update_entry_state(entry_id, False)
                print(f"  ✅ Отключено: {service_name}")
                return True
            return False
        except Exception as error:
            print(f"  ❌ Ошибка: {error}")
            return False
    
    def restore_entry(self, backup):
        print("Функция восстановления в разработке")
        return False
    
    def optimize_all(self, entries, selected_actions):
        results = {'kept': 0, 'disabled': 0, 'deleted': 0, 'delayed': 0, 'errors': 0}
        for entry in entries:
            if selected_actions.get(entry.get('id'), 'keep') in ['disable', 'delete']:
                if self.disable_entry(entry):
                    results['disabled'] += 1
                else:
                    results['errors'] += 1
            else:
                results['kept'] += 1
        return results
'''

# Перезаписываем файл
with open('optimizer.py', 'w', encoding='utf-8') as f:
    f.write(fixed_code)

print("✅ optimizer.py исправлен! Теперь можно запускать main.py")