import sqlite3
import os
import hashlib
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path="startup_optimizer.db"):
        self.db_path = db_path
        self.conn = None
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных SQLite"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
        self.populate_categories()
        print(f"База данных SQLite создана: {self.db_path}")
    
    def create_tables(self):
        """Создание всех таблиц в SQLite"""
        cursor = self.conn.cursor()
        
        # Таблица категорий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                default_action TEXT,
                min_weight INTEGER,
                max_weight INTEGER
            )
        ''')
        
        # Таблица приложений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                publisher TEXT,
                file_path TEXT UNIQUE,
                file_hash TEXT,
                category_id INTEGER,
                base_weight INTEGER DEFAULT 50,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            )
        ''')
        
        # Таблица элементов автозагрузки
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS startup_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER,
                entry_name TEXT NOT NULL,
                entry_type TEXT NOT NULL,
                entry_location TEXT NOT NULL,
                target_path TEXT NOT NULL,
                arguments TEXT,
                description TEXT,
                is_enabled BOOLEAN DEFAULT 1,
                is_ms_entry BOOLEAN DEFAULT 0,
                signature_valid BOOLEAN DEFAULT 0,
                current_weight INTEGER,
                recommendation TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (application_id) REFERENCES applications(id)
            )
        ''')
        
        # Таблица истории сканирований
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_entries INTEGER,
                enabled_count INTEGER,
                disabled_count INTEGER,
                critical_count INTEGER
            )
        ''')
        
        # Таблица резервных копий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                entry_id INTEGER,
                original_key_path TEXT,
                original_value TEXT,
                original_state BOOLEAN,
                FOREIGN KEY (entry_id) REFERENCES startup_entries(id)
            )
        ''')
        
        # Таблица статистики для будущего краудсорсинга
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS app_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER,
                total_scans INTEGER DEFAULT 1,
                times_disabled INTEGER DEFAULT 0,
                times_kept INTEGER DEFAULT 0,
                avg_weight REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (application_id) REFERENCES applications(id)
            )
        ''')
        
        self.conn.commit()
    
    def populate_categories(self):
        """Заполнение таблицы категорий начальными данными"""
        categories = [
            ('system_critical', 'Критически важные системные', 'keep', 90, 100),
            ('driver', 'Драйверы', 'keep', 80, 89),
            ('antivirus', 'Антивирус/Безопасность', 'keep', 75, 79),
            ('system_utility', 'Системные утилиты', 'keep', 60, 74),
            ('user_active', 'Пользовательские (частые)', 'delay', 40, 59),
            ('user_rare', 'Пользовательские (редкие)', 'disable', 20, 39),
            ('pua', 'Потенциально нежелательные', 'delete', 5, 19),
            ('malware', 'Вредоносное ПО', 'delete', 0, 4),
            ('unknown', 'Неизвестные', 'disable', 25, 35),
        ]
        
        cursor = self.conn.cursor()
        for cat in categories:
            cursor.execute('''
                INSERT OR IGNORE INTO categories (name, display_name, default_action, min_weight, max_weight)
                VALUES (?, ?, ?, ?, ?)
            ''', cat)
        self.conn.commit()
    
    def save_scan_results(self, entries):
        """Сохранение результатов сканирования в SQLite"""
        cursor = self.conn.cursor()
        
        # Начинаем новое сканирование
        enabled_count = sum(1 for e in entries if e.get('enabled', True))
        critical_count = sum(1 for e in entries if e.get('is_critical', False))
        
        cursor.execute('''
            INSERT INTO scan_history (scan_time, total_entries, enabled_count, disabled_count, critical_count)
            VALUES (CURRENT_TIMESTAMP, ?, ?, ?, ?)
        ''', (len(entries), enabled_count, len(entries) - enabled_count, critical_count))
        scan_id = cursor.lastrowid
        
        for entry in entries:
            # Ищем или создаем приложение
            app_id = self.get_or_create_application(entry['target_path'])
            
            # Проверяем существование записи
            cursor.execute('''
                SELECT id FROM startup_entries 
                WHERE target_path = ? AND entry_location = ? AND entry_name = ?
            ''', (entry['target_path'], entry.get('location', ''), entry.get('name', '')))
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute('''
                    UPDATE startup_entries 
                    SET last_seen = CURRENT_TIMESTAMP, is_enabled = ?
                    WHERE id = ?
                ''', (entry.get('enabled', True), existing['id']))
                entry_id = existing['id']
            else:
                cursor.execute('''
                    INSERT INTO startup_entries 
                    (application_id, entry_name, entry_type, entry_location, target_path, 
                     arguments, description, is_enabled, is_ms_entry, signature_valid, current_weight)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (app_id, entry.get('name', ''), entry.get('type', ''),
                      entry.get('location', ''), entry['target_path'], 
                      entry.get('arguments', ''), entry.get('description', ''),
                      entry.get('enabled', True), entry.get('is_ms_entry', False),
                      entry.get('signature_valid', False), entry.get('weight', 50)))
                entry_id = cursor.lastrowid
        
        self.conn.commit()
        return scan_id
    
    def get_or_create_application(self, file_path):
        """Получение или создание записи о приложении в SQLite"""
        cursor = self.conn.cursor()
        
        # Проверяем существование
        cursor.execute("SELECT id FROM applications WHERE file_path = ?", (file_path,))
        result = cursor.fetchone()
        if result:
            # Обновляем статистику
            cursor.execute('''
                UPDATE app_statistics 
                SET total_scans = total_scans + 1, last_updated = CURRENT_TIMESTAMP
                WHERE application_id = ?
            ''', (result['id'],))
            self.conn.commit()
            return result['id']
        
        # Извлекаем имя из пути
        name = os.path.basename(file_path)
        
        cursor.execute('''
            INSERT INTO applications (name, file_path, base_weight)
            VALUES (?, ?, 50)
        ''', (name, file_path))
        app_id = cursor.lastrowid
        
        # Создаем запись статистики
        cursor.execute('''
            INSERT INTO app_statistics (application_id, total_scans, avg_weight)
            VALUES (?, 1, 50)
        ''', (app_id,))
        
        self.conn.commit()
        return app_id
    
    def update_entry_recommendation(self, entry_id, weight, recommendation):
        """Обновление рекомендации для элемента"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE startup_entries 
            SET current_weight = ?, recommendation = ?
            WHERE id = ?
        ''', (weight, recommendation, entry_id))
        self.conn.commit()
    
    def get_all_entries(self):
        """Получение всех элементов автозагрузки из SQLite"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT se.id, se.entry_name, se.entry_type, se.entry_location, 
                   se.target_path, se.is_enabled, se.current_weight, se.recommendation,
                   a.name as app_name, c.display_name as category,
                   CASE 
                       WHEN se.recommendation = 'keep' THEN '✅ Оставить'
                       WHEN se.recommendation = 'delay' THEN '⏰ Отложить'
                       WHEN se.recommendation = 'disable' THEN '🔘 Отключить'
                       WHEN se.recommendation = 'delete' THEN '❌ Удалить'
                       ELSE '❓ Неизвестно'
                   END as recommendation_text
            FROM startup_entries se
            LEFT JOIN applications a ON se.application_id = a.id
            LEFT JOIN categories c ON a.category_id = c.id
            ORDER BY se.current_weight DESC, se.id
        ''')
        return cursor.fetchall()
    
    def get_entries_count(self):
        """Получение количества записей в БД"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM startup_entries")
        result = cursor.fetchone()
        return result['count'] if result else 0
    
    def create_backup(self, entry_id, key_path, value):
        """Создание резервной копии в SQLite"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO backups (entry_id, original_key_path, original_value, original_state)
            VALUES (?, ?, ?, ?)
        ''', (entry_id, key_path, value, True))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_backups(self):
        """Получение всех резервных копий из SQLite"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT b.id, b.backup_time, b.original_key_path, b.original_value,
                   se.entry_name, se.target_path, se.id as entry_id
            FROM backups b
            JOIN startup_entries se ON b.entry_id = se.id
            ORDER BY b.backup_time DESC
        ''')
        return cursor.fetchall()
    
    def get_backups_by_entry(self, entry_id):
        """Получение резервных копий для конкретного элемента"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, backup_time, original_key_path, original_value
            FROM backups
            WHERE entry_id = ?
            ORDER BY backup_time DESC
        ''', (entry_id,))
        return cursor.fetchall()
    
    def delete_backup(self, backup_id):
        """Удаление резервной копии из SQLite"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM backups WHERE id = ?", (backup_id,))
        self.conn.commit()
    
    def update_entry_state(self, entry_id, enabled):
        """Обновление состояния элемента в SQLite"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE startup_entries SET is_enabled = ?
            WHERE id = ?
        ''', (enabled, entry_id))
        self.conn.commit()
    
    def get_scan_history(self, limit=10):
        """Получение истории сканирований из SQLite"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM scan_history 
            ORDER BY scan_time DESC 
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()
    
    def execute_query(self, query, params=None):
        """Выполнение произвольного SQL-запроса"""
        cursor = self.conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        self.conn.commit()
        return cursor.fetchall()
    
    def export_to_csv(self, filename="export.csv"):
        """Экспорт данных из SQLite в CSV"""
        import csv
        
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT se.entry_name, se.entry_type, se.target_path, se.recommendation, se.current_weight,
                   a.name as app_name
            FROM startup_entries se
            LEFT JOIN applications a ON se.application_id = a.id
        ''')
        rows = cursor.fetchall()
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Имя', 'Тип', 'Путь', 'Рекомендация', 'Вес', 'Приложение'])
            for row in rows:
                writer.writerow([row['entry_name'], row['entry_type'], 
                               row['target_path'], row['recommendation'],
                               row['current_weight'], row['app_name']])
        
        print(f"Экспортировано в {filename}")
        return filename
    
    def vacuum(self):
        """Оптимизация базы данных SQLite"""
        self.conn.execute("VACUUM")
        print("База данных оптимизирована")
    
    def get_statistics(self):
        """Получение статистики из SQLite"""
        cursor = self.conn.cursor()
        
        stats = {}
        
        # Общее количество элементов
        cursor.execute("SELECT COUNT(*) as total FROM startup_entries")
        stats['total_entries'] = cursor.fetchone()['total']
        
        # По типам
        cursor.execute("SELECT entry_type, COUNT(*) as count FROM startup_entries GROUP BY entry_type")
        stats['by_type'] = {row['entry_type']: row['count'] for row in cursor.fetchall()}
        
        # По рекомендациям
        cursor.execute("SELECT recommendation, COUNT(*) as count FROM startup_entries GROUP BY recommendation")
        stats['by_recommendation'] = {row['recommendation']: row['count'] for row in cursor.fetchall()}
        
        # Средний вес
        cursor.execute("SELECT AVG(current_weight) as avg_weight FROM startup_entries WHERE current_weight IS NOT NULL")
        stats['avg_weight'] = cursor.fetchone()['avg_weight'] or 0
        
        return stats
    
    def close(self):
        """Закрытие соединения с SQLite"""
        if self.conn:
            self.vacuum()  # Оптимизация перед закрытием
            self.conn.close()
            print("Соединение с БД закрыто")