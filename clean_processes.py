import psutil
import os

count = 0
for p in psutil.process_iter(['pid', 'name', 'exe']):
    try:
        exe = p.info.get('exe') or ''
        if 'ms-playwright' in exe.lower():
            p.kill()
            count += 1
            print(f"Killed orphaned playwright process PID {p.info['pid']}")
    except Exception:
        pass

print(f"Total killed: {count}")
