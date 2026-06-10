from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from time import sleep
from os import getenv
from urllib.request import urlopen
from logging import error as logerror

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is successfully running 24/7!")

    def log_message(self, format, *args):
        return

def run_server():
    port = int(getenv("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), Handler)
    server.serve_forever()

BASE_URL = getenv("BASE_URL", None)
try:
    if len(BASE_URL) == 0:
        raise TypeError
    BASE_URL = BASE_URL.rstrip("/")
except TypeError:
    BASE_URL = None

def ping_url():
    PORT = getenv("PORT", None)
    if PORT is not None and BASE_URL is not None:
        while True:
            try:
                urlopen(BASE_URL).status
                sleep(600)
            except Exception as e:
                logerror(f"cron_boot.py: {e}")
                sleep(2)
                continue

def keep_alive():
    t1 = Thread(target=run_server)
    t1.daemon = True
    t1.start()
    
    t2 = Thread(target=ping_url)
    t2.daemon = True
    t2.start()
