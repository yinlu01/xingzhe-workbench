#!/usr/bin/env python3
"""PWA + Push Notification server for 行者工作台."""

import http.server
import socketserver
import os
import sys
import json
import base64
import subprocess
import time
from urllib.parse import urlparse

PORT = 8765
DIR = os.path.dirname(os.path.abspath(__file__))

# ---- WeRead auto sync ----
WEREAD_STALE_SECONDS = 30 * 60  # refresh if older than 30 min
WEREAD_SYNC_TIMEOUT = 40  # seconds
_weread_syncing = False

def maybe_sync_weread():
    """Run weread_sync.py --save if weread_data.json is stale (blocking, max 25s)."""
    global _weread_syncing
    if _weread_syncing:
        return
    path = os.path.join(DIR, 'weread_data.json')
    try:
        stale = time.time() - os.path.getmtime(path) > WEREAD_STALE_SECONDS
    except OSError:
        stale = True
    if not stale:
        return
    _weread_syncing = True
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(DIR, 'weread_sync.py'), '--save'],
            capture_output=True, timeout=WEREAD_SYNC_TIMEOUT)
        if r.returncode == 0:
            print('  [WEREAD] auto-synced (stale > 30min)')
        else:
            print(f'  [WEREAD] sync failed: {r.stderr.decode()[:200]}')
    except Exception as e:
        print(f'  [WEREAD] sync error: {e}')
    finally:
        _weread_syncing = False

# VAPID keys (must match PUSH_PUBLIC_KEY in HTML JS)
VAPID_PRIVATE_KEY = 'vDMuUrgHgZQ2vQTOjs4ZHZWbCgXo0jTFh4kXBLGqYzM'
VAPID_PUBLIC_KEY = 'BEl62i2Y7jFjDgTqBGPmNvE3uPPYm3hR5SQkLGcPTXdRhVgCobGkTyvMLHnxVTGkThTlBxbsVQMdPJTmnEDEoDM'

push_subscriptions = []

MIME = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
}

def send_push_simple(subscription, title, body, url='/'):
    """Send push notification using raw Web Push protocol."""
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        import struct, http.client
    except ImportError:
        print('  [PUSH] cryptography not installed. Run: pip install cryptography')
        return False

    try:
        endpoint = subscription['endpoint']
        p256dh = base64.urlsafe_b64decode(subscription['keys']['p256dh'] + '==')
        auth = base64.urlsafe_b64decode(subscription['keys']['auth'] + '==')
        
        curve = ec.SECP256R1()
        local_priv = ec.generate_private_key(curve)
        local_pub = local_priv.public_key()
        local_pub_bytes = local_pub.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        
        remote_pub = ec.EllipticCurvePublicKey.from_encoded_point(curve, p256dh)
        shared = local_priv.exchange(ec.ECDH(), remote_pub)
        
        info = b'WebPush: info\x00' + p256dh + local_pub_bytes
        prk = HKDF(algorithm=hashes.SHA256(), length=32, salt=auth, info=info).derive(shared)
        
        payload = json.dumps({
            'title': title, 'body': body, 'url': url,
            'icon': '/icons/icon-192.png', 'badge': '/icons/icon-192.png',
            'tag': 'reading', 'requireInteraction': True,
            'vibrate': [200, 100, 200],
            'actions': [{'action': 'open', 'title': '打开'}, {'action': 'dismiss', 'title': '知道了'}]
        }).encode()
        
        salt = os.urandom(16)
        cek_info = b'Content-Encoding: aes128gcm\x00'
        cek = HKDF(algorithm=hashes.SHA256(), length=16, salt=salt, info=cek_info).derive(prk)
        nonce_info = b'Content-Encoding: nonce\x00'
        nonce = HKDF(algorithm=hashes.SHA256(), length=12, salt=salt, info=nonce_info).derive(prk)
        
        cipher = Cipher(algorithms.AES(cek), modes.GCM(nonce))
        encryptor = cipher.encryptor()
        record = b'\x00\x00' + payload + b'\x02\x00'
        ciphertext = encryptor.update(record) + encryptor.finalize()
        
        salt_b64 = base64.urlsafe_b64encode(salt).decode().rstrip('=')
        dh_b64 = base64.urlsafe_b64encode(local_pub_bytes).decode().rstrip('=')
        
        body_bytes = salt + struct.pack('!I', 4096) + bytes([len(local_pub_bytes)]) + local_pub_bytes + ciphertext
        
        parsed = urlparse(endpoint)
        conn = http.client.HTTPSConnection(parsed.netloc, timeout=10)
        conn.request('POST', parsed.path, body_bytes, {
            'Content-Type': 'application/octet-stream',
            'Content-Encoding': 'aes128gcm',
            'TTL': '60',
            'Crypto-Key': f'dh={dh_b64}',
            'Encryption': f'salt={salt_b64}'
        })
        resp = conn.getresponse()
        resp.read()
        conn.close()
        return resp.status in (200, 201, 202)
    except Exception as e:
        print(f'  [PUSH] Error: {e}')
        return False


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def guess_type(self, path):
        ext = os.path.splitext(path)[1].lower()
        return MIME.get(ext, super().guess_type(path))

    def end_headers(self):
        path = self.path.split('?')[0]
        if '/api/' in self.path:
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        if path == '/sw.js':
            self.send_header('Service-Worker-Allowed', '/')
            self.send_header('Cache-Control', 'no-cache')
        elif path.endswith('.json') or path.endswith('.html') or path.endswith('.svg'):
            # 计划/数据/页面文件一律不缓存，确保 App 壳 WKWebView 每次拿到最新版
            self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        
        if parsed.path == '/api/save-subscription':
            length = int(self.headers.get('Content-Length', 0))
            sub = json.loads(self.rfile.read(length).decode())
            if sub not in push_subscriptions:
                push_subscriptions.append(sub)
                print(f'  [PUSH] Subscription saved ({len(push_subscriptions)} total)')
            self._json_resp({'ok': True})
            return
        
        if parsed.path == '/api/send-notification':
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length).decode())
            title = data.get('title', '行者工作台')
            body = data.get('body', '新提醒')
            url = data.get('url', '/life-dashboard.html')
            
            sent = 0
            for sub in push_subscriptions[:]:
                if send_push_simple(sub, title, body, url):
                    sent += 1
                else:
                    push_subscriptions.remove(sub)
            
            print(f'  [PUSH] Sent {sent} notifications')
            self._json_resp({'ok': True, 'sent': sent})
            return
        
        if parsed.path == '/api/push-key':
            self._json_resp({'publicKey': VAPID_PUBLIC_KEY})
            return
        
        if parsed.path == '/api/review':
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length).decode())
            path = os.path.join(DIR, 'review.json')
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    rv = json.load(f)
            except (OSError, ValueError):
                rv = {'entries': {}, 'weekly': {}, 'insights': []}
            rv.setdefault('entries', {})
            date = data.get('date')
            if not date:
                self._json_resp({'ok': False, 'error': 'missing date'})
                return
            prev = rv['entries'].get(date, {})
            rv['entries'][date] = {
                'text': data.get('text', ''),
                'energy': data.get('energy'),
                'savedAt': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'checkSnapshot': data.get('checkSnapshot', {}),
                'prevSuggestionDone': data.get('prevSuggestionDone'),
                'aiSummary': prev.get('aiSummary'),
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(rv, f, ensure_ascii=False, indent=2)
            print(f'  [REVIEW] saved {date}')
            try:
                subprocess.run([sys.executable, os.path.join(DIR, 'sync_obsidian_review.py'), date],
                               capture_output=True, timeout=10)
            except Exception as e:
                print(f'  [OBS] sync failed: {e}')
            self._json_resp({'ok': True})
            return
        
        self.send_response(405)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == '/api/list-subscriptions':
            self._json_resp({'count': len(push_subscriptions), 'subscriptions': push_subscriptions})
            return
        
        if parsed.path == '/api/push-key':
            self._json_resp({'publicKey': VAPID_PUBLIC_KEY})
            return

        if parsed.path == '/weread_data.json':
            maybe_sync_weread()

        super().do_GET()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _json_resp(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, fmt, *args):
        try:
            msg = fmt % args
            if '/ws/events' in msg or '/favicon' in msg:
                return
            print(f'  {msg}')
        except:
            pass


if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        local_ip = os.popen('ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null || echo "127.0.0.1"').read().strip()
        print(f"\n{'='*55}")
        print(f"  行者 · 生活工作台 PWA 服务器")
        print(f"  本机: http://localhost:{PORT}")
        print(f"  局域网: http://{local_ip}:{PORT}")
        print(f"{'='*55}")
        print(f"  Android: Chrome 打开 → 菜单 → 添加到主屏幕")
        print(f"  Ctrl+C 停止\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  服务器已停止")
            sys.exit(0)
