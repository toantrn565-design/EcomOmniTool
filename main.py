import os
import sys
import time
import socket
import asyncio
import threading
import subprocess
import webbrowser



def find_free_port(start_port=8030):
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                port += 1

def open_browser(port):
    time.sleep(2)
    url = f"http://127.0.0.1:{port}"
    print(f"\n[Tool] Đang mở giao diện điều khiển tại địa chỉ: {url}")
    
    chrome_paths = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    chrome_path = None
    for path in chrome_paths:
        if os.path.exists(path):
            chrome_path = path
            break
            
    if chrome_path:
        cmd = f'"{chrome_path}" --app={url} --window-size=1300,850'
        subprocess.Popen(cmd, shell=True)
    else:
        webbrowser.open(url)

if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
        
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)
    sys.path.append(current_dir)
    
    
    
    app_port = find_free_port()
    
    threading.Thread(target=open_browser, args=(app_port,), daemon=True).start()
    
    print(f"\n[Tool] Đang khởi động server trên cổng {app_port}...")
    import uvicorn
    uvicorn.run("backend.app:app", host="127.0.0.1", port=app_port, reload=False)
