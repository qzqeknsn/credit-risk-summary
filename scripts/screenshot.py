import os
import subprocess
import time
import socket
import json
from playwright.sync_api import sync_playwright

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def main():
    port = find_free_port()
    # Start http.server in background
    server_proc = subprocess.Popen(
        ["python3", "-m", "http.server", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    
    time.sleep(2) # Wait for server to start
    
    url = f"http://localhost:{port}/dashboard/index.html"
    output_path = "docs/dashboard.png"
    os.makedirs("docs", exist_ok=True)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            
            # Capture console errors
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            
            print(f"Taking screenshot of {url}...")
            page.goto(url, wait_until="networkidle")
            page.screenshot(path=output_path, full_page=True)
            
            if console_errors:
                print("Console Errors found:")
                for err in console_errors:
                    print(f"- {err}")
            else:
                print("No console errors found.")
            
            browser.close()
    finally:
        server_proc.terminate()

if __name__ == "__main__":
    main()
