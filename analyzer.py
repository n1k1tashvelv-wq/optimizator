import os
import re

class StartupAnalyzer:
    # Системные критичные процессы (НЕЛЬЗЯ ОТКЛЮЧАТЬ)
    CRITICAL_PROCESSES = [
        'winlogon.exe', 'lsass.exe', 'services.exe', 'svchost.exe',
        'explorer.exe', 'wininit.exe', 'csrss.exe', 'smss.exe',
        'dwm.exe', 'taskhost.exe', 'taskhostw.exe', 'rundll32.exe',
        'userinit.exe', 'logonui.exe', 'ctfmon.exe'
    ]
    
    # Драйверы и системные утилиты
    SYSTEM_DRIVERS = [
        'nviddmkm.sys', 'igdkmd64.sys', 'rtkvhd64.sys', 'tcpip.sys',
        'ntoskrnl.exe', 'hal.dll', 'clipsp.sys'
    ]
    
    # Антивирусные процессы
    ANTIVIRUS_PROCESSES = [
        'msmpeng.exe', 'msseces.exe', 'kav', 'avp', 'avast', 'avg',
        'norton', 'mcafee', 'defender', 'antivirus', 'security',
        'kaspersky', 'bitdefender', 'eset'
    ]
    
    # Вредоносные индикаторы
    MALWARE_INDICATORS = [
        'temp', 'tmp', 'download', 'crypt', 'miner', 'trojan',
        'worm', 'ransom', 'spy', 'adware', 'malware'
    ]
    
    # Потенциально нежелательные программы
    PUA_INDICATORS = [
        'optimizer', 'cleaner', 'driver booster', 'pc speed',
        'registry cleaner', 'toolbar', 'browser helper'
    ]
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def analyze_all(self):
        """Анализ всех элементов из БД"""
        entries = self.db.get_all_entries()
        results = []
        
        print("\n" + "=" * 50)
        print("Анализ элементов автозагрузки")
        print("=" * 50)
        
        for entry in entries:
            weight, recommendation = self.analyze_entry(
                entry['entry_name'], 
                entry['target_path'], 
                entry['entry_type']
            )
            
            # Обновляем в БД
            self.db.update_entry_recommendation(entry['id'], weight, recommendation)
            
            results.append({
                'id': entry['id'],
                'name': entry['entry_name'],
                'target_path': entry['target_path'],
                'type': entry['entry_type'],
                'is_enabled': entry['is_enabled'],
                'weight': weight,
                'recommendation': recommendation,
                'category': entry['category'] or 'unknown'
            })
        
        print(f"\n✅ Анализ завершен. Обработано {len(results)} элементов")
        return results
    
    def analyze_entry(self, name, target_path, entry_type):
        """Анализ одного элемента и возврат веса + рекомендации"""
        target_lower = target_path.lower()
        name_lower = name.lower()
        
        # 1. Проверка критических системных процессов
        for critical in self.CRITICAL_PROCESSES:
            if critical.lower() in target_lower or critical.lower() in name_lower:
                return (95, 'keep')
        
        # 2. Проверка драйверов
        for driver in self.SYSTEM_DRIVERS:
            if driver.lower() in target_lower:
                return (85, 'keep')
        
        # 3. Проверка антивирусов
        for av in self.ANTIVIRUS_PROCESSES:
            if av.lower() in target_lower or av.lower() in name_lower:
                return (80, 'keep')
        
        # 4. Проверка на вредоносное ПО
        malware_score = 0
        for indicator in self.MALWARE_INDICATORS:
            if indicator in target_lower:
                malware_score += 20
        if malware_score >= 30:
            return (max(0, 50 - malware_score), 'delete')
        
        # 5. Проверка на PUA
        pua_score = 0
        for indicator in self.PUA_INDICATORS:
            if indicator in target_lower:
                pua_score += 15
        if pua_score >= 20:
            return (max(0, 40 - pua_score), 'disable')
        
        # 6. Анализ по пути расположения
        if target_lower.startswith('c:\\program files\\'):
            if 'update' in target_lower or 'updater' in target_lower:
                return (35, 'disable')
            if 'helper' in target_lower or 'assistant' in target_lower:
                return (30, 'disable')
            # Проверка на известные полезные программы
            useful_apps = ['spotify', 'discord', 'telegram', 'whatsapp', 'slack']
            for app in useful_apps:
                if app in target_lower:
                    return (45, 'delay')
            return (40, 'disable')
        
        elif target_lower.startswith('c:\\windows\\'):
            if 'system32' in target_lower:
                # Системные, но не критические
                return (65, 'keep')
            return (55, 'keep')
        
        elif '\\temp\\' in target_lower or '\\tmp\\' in target_lower:
            return (15, 'delete')
        
        elif 'microsoft' in target_lower or 'windows' in target_lower:
            return (70, 'keep')
        
        # 7. Анализ служб
        if entry_type == 'service':
            if 'update' in name_lower:
                return (35, 'disable')
            if 'printer' in name_lower or 'print' in name_lower:
                return (40, 'disable')
            return (55, 'keep')
        
        # 8. Анализ по расширению
        if target_lower.endswith('.vbs') or target_lower.endswith('.js'):
            return (20, 'disable')
        
        # 9. По умолчанию
        return (35, 'disable')
    
    def get_recommendation_text(self, recommendation, weight):
        """Получение текстового описания рекомендации"""
        texts = {
            'keep': '✅ Оставить — критический компонент',
            'delay': '⏰ Отложить — можно запустить позже',
            'disable': '🔘 Отключить — не влияет на работу',
            'delete': '❌ Удалить — потенциально опасный'
        }
        
        base_text = texts.get(recommendation, '❓ Неизвестно')
        
        if recommendation == 'disable' and weight < 30:
            return f"{base_text} (рекомендуется)"
        elif recommendation == 'delete':
            return base_text
        
        return base_text
    
    def get_statistics_from_db(self):
        """Получение статистики из SQLite"""
        stats = self.db.get_statistics()
        
        print("\n" + "=" * 50)
        print("Статистика из базы данных SQLite")
        print("=" * 50)
        print(f"Всего элементов в БД: {stats['total_entries']}")
        print(f"Средний вес: {stats['avg_weight']:.1f}")
        print("\nПо типам:")
        for entry_type, count in stats['by_type'].items():
            print(f"  {entry_type}: {count}")
        print("\nПо рекомендациям:")
        for rec, count in stats['by_recommendation'].items():
            print(f"  {rec}: {count}")
        
        return stats