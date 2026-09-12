import os
import mimetypes

def handler(environ, start_response):
    path = environ.get('PATH_INFO', '/').lstrip('/')
    if not path:
        path = 'index.html'
    
    # Prevent directory traversal
    safe_path = os.path.normpath(path)
    if safe_path.startswith('..') or os.path.isabs(safe_path):
        start_response('403 Forbidden', [('Content-Type', 'text/plain')])
        return [b'Forbidden']
    
    if os.path.exists(safe_path) and os.path.isfile(safe_path):
        mime_type, _ = mimetypes.guess_type(safe_path)
        content_type = mime_type or 'application/octet-stream'
        if safe_path.endswith('.html'):
            content_type = 'text/html; charset=utf-8'
        elif safe_path.endswith('.json'):
            content_type = 'application/json; charset=utf-8'
            
        with open(safe_path, 'rb') as f:
            body = f.read()
        start_response('200 OK', [
            ('Content-Type', content_type),
            ('Content-Length', str(len(body)))
        ])
        return [body]
    
    # Fallback to index.html for single-page routing
    if os.path.exists('index.html'):
        with open('index.html', 'rb') as f:
            body = f.read()
        start_response('200 OK', [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Content-Length', str(len(body)))
        ])
        return [body]

    start_response('404 Not Found', [('Content-Type', 'text/plain')])
    return [b'File Not Found']

# Top-level exports for Vercel / WSGI / ASGI serverless runners
app = handler
application = handler
