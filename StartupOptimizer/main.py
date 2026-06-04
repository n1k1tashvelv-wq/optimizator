import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading

# Добавляем текущую папку в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import DatabaseManager
from scanner import StartupScanner
from analyzer import StartupAnalyzer
from optimizer import StartupOptimizer

class StartupOptimizerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Startup Optimizer - Оптимизатор автозагрузки")
        self.root.geometry("1000x650")
        self.root.configure(bg='#f0f0f0')
        
        # Инициализация
        self.db = DatabaseManager()
        self.scanner = StartupScanner()
        self.analyzer = StartupAnalyzer(self.db)
        self.optimizer = StartupOptimizer(self.db)
        
        self.entries = []
        self.checkboxes = {}
        
        self.setup_ui()
        
    def setup_ui(self):
        # Заголовок
        title = tk.Label(self.root, text="🚀 Startup Optimizer", font=("Arial", 18, "bold"), 
                         bg='#f0f0f0', fg='#2c3e50')
        title.pack(pady=10)
        
        # Кнопки
        btn_frame = tk.Frame(self.root, bg='#f0f0f0')
        btn_frame.pack(pady=10)
        
        self.scan_btn = tk.Button(btn_frame, text="🔍 Сканировать", command=self.scan_system,
                                  bg='#27ae60', fg='white', font=("Arial", 11), padx=20, pady=5)
        self.scan_btn.pack(side=tk.LEFT, padx=10)
        
        self.optimize_btn = tk.Button(btn_frame, text="⚡ Оптимизировать выбранные", command=self.optimize_selected,
                                      bg='#e67e22', fg='white', font=("Arial", 11), padx=20, pady=5, state='disabled')
        self.optimize_btn.pack(side=tk.LEFT, padx=10)
        
        self.restore_btn = tk.Button(btn_frame, text="🔄 Восстановить", command=self.show_restore_dialog,
                                     bg='#3498db', fg='white', font=("Arial", 11), padx=20, pady=5)
        self.restore_btn.pack(side=tk.LEFT, padx=10)
        
        # Статус
        self.status_label = tk.Label(self.root, text="Готов к работе. Нажмите 'Сканировать'", 
                                     bg='#f0f0f0', fg='#7f8c8d', font=("Arial", 10))
        self.status_label.pack(pady=5)
        
        # Таблица
        frame = tk.Frame(self.root, bg='#f0f0f0')
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Создаем Canvas и Scrollbar для прокрутки
        canvas = tk.Canvas(frame, bg='#f0f0f0')
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas, bg='#f0f0f0')
        
        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.table_frame = self.scrollable_frame
        
        # Прогресс-бар
        self.progress = ttk.Progressbar(self.root, mode='indeterminate')
        self.progress.pack(fill=tk.X, padx=20, pady=10)
        
    def scan_system(self):
        self.scan_btn.config(state='disabled')
        self.status_label.config(text="Сканирование...")
        self.progress.start()
        
        thread = threading.Thread(target=self._do_scan)
        thread.start()
    
    def _do_scan(self):
        try:
            # Очищаем таблицу
            for widget in self.table_frame.winfo_children():
                widget.destroy()
            
            # Сканируем
            results = self.scanner.scan_all()
            
            # Сохраняем в БД
            scan_id = self.db.save_scan_results(results)
            
            # Получаем все записи из БД
            db_entries = self.db.get_all_entries()
            
            # Анализируем
            for entry in db_entries:
                weight, rec = self.analyzer.analyze_entry(
                    entry['entry_name'], entry['target_path'], entry['entry_type']
                )
                self.db.update_entry_recommendation(entry['id'], weight, rec)
            
            # Обновляем список
            self.entries = self.db.get_all_entries()
            
            self.root.after(0, self._update_table)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
        finally:
            self.root.after(0, self._scan_complete)
    
    def _update_table(self):
        # Заголовки
        headers = ["Вкл.", "Имя", "Тип", "Путь (кратко)", "Рекомендация", "Вес"]
        for col, text in enumerate(headers):
            label = tk.Label(self.table_frame, text=text, font=("Arial", 10, "bold"),
                            bg='#34495e', fg='white', padx=10, pady=5)
            label.grid(row=0, column=col, sticky='ew', padx=1)
        
        # Данные
        for row, entry in enumerate(self.entries, start=1):
            # Чекбокс для выбора
            var = tk.BooleanVar()
            # Автоматически выбираем для отключения
            if entry['recommendation'] in ['disable', 'delete']:
                var.set(True)
            
            cb = tk.Checkbutton(self.table_frame, variable=var, bg='#f0f0f0')
            cb.grid(row=row, column=0, padx=5)
            self.checkboxes[entry['id']] = var
            
            # Имя
            name_label = tk.Label(self.table_frame, text=entry['entry_name'][:40], 
                                  bg='#f0f0f0', anchor='w')
            name_label.grid(row=row, column=1, sticky='ew', padx=5)
            
            # Тип
            type_label = tk.Label(self.table_frame, text=entry['entry_type'], 
                                  bg='#f0f0f0')
            type_label.grid(row=row, column=2, padx=5)
            
            # Путь (кратко)
            path_short = entry['target_path'][:50] + '...' if len(entry['target_path']) > 50 else entry['target_path']
            path_label = tk.Label(self.table_frame, text=path_short, 
                                  bg='#f0f0f0', anchor='w', font=("Arial", 8))
            path_label.grid(row=row, column=3, sticky='ew', padx=5)
            
            # Рекомендация
            if entry['recommendation'] == 'keep':
                rec_text = "✅ Оставить"
                rec_color = '#27ae60'
            elif entry['recommendation'] == 'delay':
                rec_text = "⏰ Отложить"
                rec_color = '#f39c12'
            elif entry['recommendation'] == 'disable':
                rec_text = "🔘 Отключить"
                rec_color = '#e67e22'
            else:
                rec_text = "❌ Удалить"
                rec_color = '#e74c3c'
            
            rec_label = tk.Label(self.table_frame, text=rec_text, bg='#f0f0f0', fg=rec_color)
            rec_label.grid(row=row, column=4, padx=5)
            
            # Вес
            weight_val = entry['current_weight'] or 50
            weight_label = tk.Label(self.table_frame, text=str(weight_val), bg='#f0f0f0')
            weight_label.grid(row=row, column=5, padx=5)
        
        # Настройка весов колонок
        self.table_frame.columnconfigure(1, weight=2)
        self.table_frame.columnconfigure(3, weight=3)
    
    def _scan_complete(self):
        self.progress.stop()
        self.scan_btn.config(state='normal')
        self.optimize_btn.config(state='normal')
        count = len(self.entries)
        self.status_label.config(text=f"Сканирование завершено. Найдено {count} элементов в автозагрузке.")
    
    def optimize_selected(self):
        selected = []
        for entry in self.entries:
            if self.checkboxes.get(entry['id'], tk.BooleanVar()).get():
                selected.append({
                    'id': entry['id'],
                    'name': entry['entry_name'],
                    'type': entry['entry_type'],
                    'location': entry['entry_location'],
                    'target_path': entry['target_path'],
                    'recommendation': entry['recommendation']
                })
        
        if not selected:
            messagebox.showinfo("Информация", "Не выбрано ни одного элемента")
            return
        
        result = messagebox.askyesno("Подтверждение", 
                                     f"Вы выбрали {len(selected)} элементов для оптимизации.\n"
                                     "Продолжить? (рекомендуется создать точку восстановления системы)")
        
        if not result:
            return
        
        self.optimize_btn.config(state='disabled')
        self.status_label.config(text="Оптимизация...")
        self.progress.start()
        
        thread = threading.Thread(target=self._do_optimize, args=(selected,))
        thread.start()
    
    def _do_optimize(self, selected):
        success_count = 0
        for entry in selected:
            if self.optimizer.disable_entry(entry):
                success_count += 1
        
        self.root.after(0, lambda: self._optimize_complete(success_count, len(selected)))
    
    def _optimize_complete(self, success, total):
        self.progress.stop()
        self.optimize_btn.config(state='normal')
        self.status_label.config(text=f"Оптимизация завершена. Отключено {success} из {total} элементов.")
        messagebox.showinfo("Результат", f"Успешно отключено: {success}\nОшибок: {total - success}")
        
        # Обновляем список
        self.scan_system()
    
    def show_restore_dialog(self):
        backups = self.db.get_backups()
        
        if not backups:
            messagebox.showinfo("Информация", "Нет резервных копий для восстановления")
            return
        
        # Создаем диалог
        dialog = tk.Toplevel(self.root)
        dialog.title("Восстановление из резервной копии")
        dialog.geometry("600x400")
        
        listbox = tk.Listbox(dialog, width=80, height=15)
        listbox.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        for backup in backups:
            listbox.insert(tk.END, f"[{backup['backup_time']}] {backup['entry_name']} - {backup['original_key_path']}")
        
        def restore_selected():
            selection = listbox.curselection()
            if selection:
                backup = backups[selection[0]]
                if self.optimizer.restore_entry(backup):
                    messagebox.showinfo("Успех", "Элемент восстановлен")
                    dialog.destroy()
                    self.scan_system()
                else:
                    messagebox.showerror("Ошибка", "Не удалось восстановить")
        
        btn_restore = tk.Button(dialog, text="Восстановить выбранный", command=restore_selected,
                                bg='#3498db', fg='white', padx=20, pady=5)
        btn_restore.pack(pady=10)
    
    def run(self):
        self.root.mainloop()
        self.db.close()

if __name__ == "__main__":
    # Проверка прав администратора
    import ctypes
    if not ctypes.windll.shell32.IsUserAnAdmin():
        messagebox.showwarning("Внимание", 
                               "Рекомендуется запустить программу от имени администратора\n"
                               "для доступа ко всем точкам автозагрузки.")
    
    app = StartupOptimizerApp()
    app.run()