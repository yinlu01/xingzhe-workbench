#!/usr/bin/env python3
"""Send push notification via the PWA server API."""
import json, sys
from urllib import request

SERVER = 'http://127.0.0.1:8765'

def send_push(title, body, tag='default', url='/life-dashboard.html'):
    """Send push notification to all subscribed devices."""
    data = json.dumps({
        'title': title,
        'body': body,
        'tag': tag,
        'url': url
    }).encode()
    try:
        req = request.Request(f'{SERVER}/api/send-notification', data=data,
            headers={'Content-Type': 'application/json'})
        resp = request.urlopen(req, timeout=5)
        result = json.loads(resp.read())
        return result
    except Exception as e:
        print(f'send_push error: {e}')
        return {'sent': 0, 'error': str(e)}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python notify.py "title" "body" [url]')
        sys.exit(1)
    
    title = sys.argv[1]
    body = sys.argv[2] if len(sys.argv) > 2 else title
    url = sys.argv[3] if len(sys.argv) > 3 else '/life-dashboard.html'
    
    result = send_push(title, body, url=url)
    print(json.dumps(result, ensure_ascii=False))
