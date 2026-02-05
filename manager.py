#!/usr/bin/env python3
"""
Менеджер для запуска code3.py в фоновом режиме
"""

import os
import sys
import time
import json
import signal
import subprocess
import threading
from pathlib import Path
from datetime import datetime

class BotManager:
    def __init__(self):
        # Указываем ТОЧНОЕ имя вашего файла
        self.bot_script = "code3.py"  # ⬅️ ВАЖНО: ваше имя файла
        self.bot_dir = Path.cwd()  # Текущая директория
        self.data_dir = self.bot_dir / ".bot_data"
        self.data_dir.mkdir(exist_ok=True)
        
        # Файлы для управления
        self.pid_file = self.data_dir / "code3.pid"
        self.log_file = self.data_dir / "code3.log"
        self.status_file = self.data_dir / "code3.status"
        
        print(f"📁 Рабочая директория: {self.bot_dir}")
        print(f"🤖 Целевой скрипт: {self.bot_script}")
        
    def check_script_exists(self):
        """Проверяем, существует ли code3.py"""
        script_path = self.bot_dir / self.bot_script
        if not script_path.exists():
            print(f"❌ Ошибка: файл {self.bot_script} не найден!")
            print(f"   Ищем в: {script_path}")
            print(f"   Текущие файлы в директории:")
            for f in self.bot_dir.iterdir():
                print(f"    - {f.name}")
            return False
        return True
    
    def start(self):
        """Запуск code3.py в фоновом режиме"""
        if not self.check_script_exists():
            return False
            
        if self.is_running():
            pid = self.get_pid()
            print(f"⚠️ code3.py уже запущен! PID: {pid}")
            print(f"   Для остановки: python3 manager.py stop")
            return False
        
        # Полный путь к скрипту
        script_path = self.bot_dir / self.bot_script
        
        # Открываем лог-файл
        log_fd = open(self.log_file, 'a')
        log_fd.write(f"\n{'='*60}\n")
        log_fd.write(f"Запуск code3.py: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_fd.write(f"Директория: {self.bot_dir}\n")
        log_fd.flush()
        
        try:
            # Запускаем процесс
            print(f"🚀 Запускаем {self.bot_script}...")
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                cwd=self.bot_dir  # Важно: запускаем из правильной директории
            )
            
            # Сохраняем PID
            with open(self.pid_file, 'w') as f:
                f.write(str(process.pid))
            
            # Сохраняем статус
            self.save_status({
                'pid': process.pid,
                'start_time': datetime.now().isoformat(),
                'script': str(self.bot_script),
                'status': 'running',
                'directory': str(self.bot_dir)
            })
            
            # Мониторинг в отдельном потоке
            monitor_thread = threading.Thread(
                target=self.monitor_process,
                args=(process.pid,),
                daemon=True
            )
            monitor_thread.start()
            
            print(f"✅ {self.bot_script} запущен!")
            print(f"   PID: {process.pid}")
            print(f"   Логи: tail -f {self.log_file}")
            print(f"   Для остановки: python3 manager.py stop")
            print(f"   Для проверки: python3 manager.py status")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка запуска {self.bot_script}:")
            print(f"   {e}")
            return False
    
    def stop(self):
        """Остановка code3.py"""
        pid = self.get_pid()
        if not pid:
            print("⚠️ code3.py не запущен")
            return False
        
        try:
            print(f"🛑 Останавливаем code3.py (PID: {pid})...")
            
            # Сначала мягко
            os.kill(pid, signal.SIGTERM)
            time.sleep(2)
            
            # Если жив, убиваем
            if self.is_pid_running(pid):
                print(f"   Процесс не отвечает, принудительная остановка...")
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
            
            # Очищаем
            if self.pid_file.exists():
                self.pid_file.unlink()
            
            self.save_status({
                'status': 'stopped', 
                'stop_time': datetime.now().isoformat(),
                'last_pid': pid
            })
            
            print(f"✅ code3.py остановлен")
            return True
            
        except ProcessLookupError:
            print(f"⚠️ Процесс {pid} не найден (возможно уже завершился)")
            self.pid_file.unlink(missing_ok=True)
            return True
        except Exception as e:
            print(f"❌ Ошибка остановки: {e}")
            return False
    
    def monitor_process(self, pid):
        """Мониторинг процесса"""
        while True:
            time.sleep(15)  # Проверяем каждые 15 секунд
            if not self.is_pid_running(pid):
                with open(self.log_file, 'a') as f:
                    f.write(f"\n[Менеджер] Процесс {pid} завершился: {datetime.now()}\n")
                
                if self.pid_file.exists():
                    self.pid_file.unlink()
                
                self.save_status({
                    'status': 'crashed',
                    'last_seen': datetime.now().isoformat(),
                    'last_pid': pid
                })
                break
    
    def is_pid_running(self, pid):
        """Проверка, работает ли процесс"""
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False
    
    def is_running(self):
        """Проверка, запущен ли code3.py"""
        pid = self.get_pid()
        return pid and self.is_pid_running(pid)
    
    def get_pid(self):
        """Получение PID"""
        try:
            with open(self.pid_file, 'r') as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return None
    
    def save_status(self, status_data):
        """Сохранение статуса"""
        try:
            with open(self.status_file, 'w') as f:
                json.dump(status_data, f, indent=2, default=str)
        except Exception as e:
            print(f"Ошибка сохранения статуса: {e}")
    
    def get_status(self):
        """Получение статуса"""
        try:
            with open(self.status_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {'status': 'unknown'}
    
    def show_logs(self, lines=20):
        """Показать логи"""
        try:
            with open(self.log_file, 'r') as f:
                all_lines = f.readlines()
                if lines > 0:
                    print(''.join(all_lines[-lines:]))
                else:
                    print(''.join(all_lines))
                    
                # Показать размер файла
                print(f"\n📊 Всего строк: {len(all_lines)}")
                print(f"📁 Размер файла: {os.path.getsize(self.log_file)} байт")
                
        except FileNotFoundError:
            print("Лог-файл не найден. Бот еще не запускался?")
    
    def clear_logs(self):
        """Очистить логи"""
        try:
            with open(self.log_file, 'w') as f:
                f.write(f"Логи очищены: {datetime.now()}\n")
            print("✅ Логи очищены")
        except Exception as e:
            print(f"❌ Ошибка очистки логов: {e}")
    
    def status(self):
        """Показать статус"""
        pid = self.get_pid()
        
        print(f"\n📊 СТАТУС code3.py")
        print(f"{'='*40}")
        
        # Проверяем существование скрипта
        script_path = self.bot_dir / self.bot_script
        if script_path.exists():
            size = os.path.getsize(script_path)
            print(f"📁 Скрипт: {self.bot_script} ({size} байт)")
        else:
            print(f"❌ Скрипт: {self.bot_script} - НЕ НАЙДЕН!")
            return
        
        if self.is_running():
            status_info = self.get_status()
            start_time = status_info.get('start_time', 'неизвестно')
            
            # Пытаемся вычислить время работы
            try:
                if start_time != 'неизвестно':
                    start_dt = datetime.fromisoformat(start_time)
                    uptime = datetime.now() - start_dt
                    days = uptime.days
                    hours = uptime.seconds // 3600
                    minutes = (uptime.seconds % 3600) // 60
                    uptime_str = f"{days}д {hours}ч {minutes}м"
                else:
                    uptime_str = "неизвестно"
            except:
                uptime_str = "неизвестно"
            
            print(f"✅ Статус: ЗАПУЩЕН")
            print(f"   PID: {pid}")
            print(f"   Время запуска: {start_time}")
            print(f"   Время работы: {uptime_str}")
            print(f"   Логи: {self.log_file}")
            
            # Размер логов
            if self.log_file.exists():
                log_size = os.path.getsize(self.log_file)
                print(f"   Размер логов: {log_size} байт")
            
        else:
            last_status = self.get_status()
            if last_status.get('status') == 'crashed':
                crash_time = last_status.get('last_seen', 'неизвестно')
                print(f"💥 Статус: УПАЛ ({crash_time})")
                print(f"   Последний PID: {last_status.get('last_pid', 'неизвестно')}")
            else:
                print(f"❌ Статус: НЕ ЗАПУЩЕН")
            
            # Показываем последний PID если был
            if pid:
                print(f"   Последний PID: {pid} (процесс не найден)")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description=f'Менеджер для запуска code3.py в фоновом режиме',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f'''
Примеры использования:
  python3 manager.py start     - Запустить code3.py
  python3 manager.py stop      - Остановить code3.py
  python3 manager.py restart   - Перезапустить
  python3 manager.py status    - Показать статус
  python3 manager.py logs      - Показать логи (20 строк)
  python3 manager.py logs -50  - Показать 50 строк логов
  python3 manager.py logs 0    - Показать все логи
  python3 manager.py clear     - Очистить логи
        '''
    )
    
    parser.add_argument('action', 
                       choices=['start', 'stop', 'restart', 'status', 'logs', 'clear'],
                       help='Действие')
    parser.add_argument('lines', type=int, nargs='?', default=20,
                       help='Количество строк логов (только для action=logs)')
    
    args = parser.parse_args()
    manager = BotManager()
    
    print(f"\n🎮 Менеджер для code3.py")
    print(f"{'='*30}")
    
    if args.action == 'start':
        manager.start()
    elif args.action == 'stop':
        manager.stop()
    elif args.action == 'restart':
        print("🔄 Перезапуск code3.py...")
        manager.stop()
        time.sleep(2)
        manager.start()
    elif args.action == 'status':
        manager.status()
    elif args.action == 'logs':
        manager.show_logs(args.lines)
    elif args.action == 'clear':
        confirm = input("❓ Очистить все логи? (y/N): ")
        if confirm.lower() == 'y':
            manager.clear_logs()
        else:
            print("Отменено")

if __name__ == '__main__':
    main()
