# --- START OF FILE: database.py ---
import sqlite3
import datetime

class Database:
    def __init__(self):
        self.conn = sqlite3.connect("shrimp_stats.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS violations
                              (id INTEGER PRIMARY KEY, date TEXT, type TEXT)''')
        self.conn.commit()

    def log_violation(self, v_type):
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute("INSERT INTO violations (date, type) VALUES (?, ?)", (date, v_type))
        self.conn.commit()

    def get_available_dates(self):
        """Возвращает список уникальных дат, в которые были нарушения"""
        self.cursor.execute("SELECT DISTINCT date(date) FROM violations ORDER BY date DESC")
        dates = [row[0] for row in self.cursor.fetchall()]
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        if today not in dates:
            dates.insert(0, today) # Всегда показываем сегодняшний день
        return dates

    def get_stats_by_date(self, target_date):
        """Статистика нарушений (круговая диаграмма)"""
        self.cursor.execute("SELECT type, COUNT(*) FROM violations WHERE date LIKE ? GROUP BY type", (f"{target_date}%",))
        return dict(self.cursor.fetchall())

    def get_hourly_stats(self, target_date):
        """Статистика нарушений по часам и типам (для stacked bar)"""
        self.cursor.execute("""
            SELECT strftime('%H', date) as hour, type, COUNT(*) 
            FROM violations 
            WHERE date LIKE ? 
            GROUP BY hour, type
        """, (f"{target_date}%",))
        
        # Формируем словарь вида: {'00': {'Сутулость': 2, 'Перекос': 1}, ...}
        stats = {f"{i:02d}": {} for i in range(24)}
        for hour, v_type, count in self.cursor.fetchall():
            stats[hour][v_type] = count
            
        return stats
# --- END OF FILE: database.py ---