"""最小的 Chrome DevTools Protocol 客户端(用 websocket-client):启动本机的 Google Chrome(headless,独立的 --user-data-dir,只监听 127.0.0.1),
通过 websocket 控制页面。结束时按唯一的 user-data-dir 精确结束这批进程,不碰用户自己的 Chrome。"""
import os, sys, json, time, subprocess, shutil, urllib.request, threading, queue
import websocket
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'


class Chrome:
    def __init__(self, port, workdir, extra=()):
        self.port = port; self.dir = str(workdir) + f'/chrome_{os.getpid()}_{port}'
        env = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower()}
        self.p = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={port}', '--remote-debugging-address=127.0.0.1', f'--user-data-dir={self.dir}',
                                   '--no-first-run', '--no-default-browser-check', '--disable-gpu', '--no-sandbox', '--no-proxy-server', '--disable-extensions',
                                   '--disable-background-networking', '--disable-component-update', *extra, 'about:blank'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(150):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version', timeout=1).read(); break
            except Exception: time.sleep(0.1)
        else: self.stop(); raise RuntimeError('Chrome 没起来')
        self.version = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version').read())['Browser']

    def new_page(self, url='about:blank'):
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}/json/new?{url}', method='PUT')
        info = json.loads(urllib.request.urlopen(req).read())
        return Page(info['webSocketDebuggerUrl'], info['id'], self)

    def stop(self):
        try:
            if self.p.poll() is None: self.p.terminate()
        except Exception: pass
        for sig in ('-TERM', '-KILL'):
            ids = subprocess.run(['pgrep', '-f', f'user-data-dir={self.dir}'], capture_output=True, text=True).stdout.split()
            for i in ids:
                try: os.kill(int(i), 15 if sig == '-TERM' else 9)
                except Exception: pass
            time.sleep(0.5)
        shutil.rmtree(self.dir, ignore_errors=True)
    def __enter__(self): return self
    def __exit__(self, *a): self.stop()


class Page:
    def __init__(self, ws_url, tid, chrome):
        self.ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True); self.id = 0; self.events = []; self.tid = tid; self.chrome = chrome

    def send(self, method, **params):
        self.id += 1; mid = self.id
        self.ws.send(json.dumps({'id': mid, 'method': method, 'params': params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get('id') == mid:
                if 'error' in m: raise RuntimeError(f'{method}: {m["error"]}')
                return m.get('result', {})
            if 'method' in m: self.events.append(m)

    def wait_event(self, name, timeout=15, clear=False):
        end = time.time() + timeout
        while time.time() < end:
            for i, e in enumerate(self.events):
                if e['method'] == name:
                    return self.events.pop(i) if clear else e
            self.ws.settimeout(max(0.1, end - time.time()))
            try:
                m = json.loads(self.ws.recv())
                if 'method' in m: self.events.append(m)
            except websocket.WebSocketTimeoutException: break
        raise TimeoutError(name)

    def drain(self, sec):
        end = time.time() + sec
        while time.time() < end:
            self.ws.settimeout(max(0.05, end - time.time()))
            try:
                m = json.loads(self.ws.recv())
                if 'method' in m: self.events.append(m)
            except websocket.WebSocketTimeoutException: break

    def goto(self, url, wait='Page.loadEventFired'):
        self.events = [e for e in self.events if e['method'] != wait]
        self.send('Page.enable')
        self.send('Page.navigate', url=url)
        self.wait_event(wait)

    def eval(self, expr, await_promise=False):
        r = self.send('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=await_promise)
        if 'exceptionDetails' in r: raise RuntimeError(str(r['exceptionDetails'].get('exception', r['exceptionDetails']))[:200])
        return r['result'].get('value')

    def close(self):
        """真正关闭这个标签页(/json/close/<id>),再断开 websocket。"""
        try: urllib.request.urlopen(f'http://127.0.0.1:{self.chrome.port}/json/close/{self.tid}', timeout=3).read()
        except Exception: pass
        try: self.ws.close()
        except Exception: pass


class Browser:
    """浏览器级连接(/json/version 里的 webSocketDebuggerUrl):可以创建/销毁独立的 browser context(相当于隐身窗口,Cookie、缓存互相隔离)。"""
    def __init__(self, chrome):
        info = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{chrome.port}/json/version').read())
        self.chrome = chrome; self.ws = websocket.create_connection(info['webSocketDebuggerUrl'], timeout=30, suppress_origin=True); self.id = 0

    def send(self, method, **params):
        self.id += 1; mid = self.id
        self.ws.send(json.dumps({'id': mid, 'method': method, 'params': params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get('id') == mid:
                if 'error' in m: raise RuntimeError(f'{method}: {m["error"]}')
                return m.get('result', {})

    def new_context(self): return self.send('Target.createBrowserContext')['browserContextId']
    def dispose_context(self, ctx): self.send('Target.disposeBrowserContext', browserContextId=ctx)

    def page_in(self, ctx, url='about:blank'):
        tid = self.send('Target.createTarget', url=url, browserContextId=ctx)['targetId']
        return Page(f'ws://127.0.0.1:{self.chrome.port}/devtools/page/{tid}', tid, self.chrome)

    def close_target(self, tid):
        try: self.send('Target.closeTarget', targetId=tid)
        except Exception: pass

    def close(self):
        try: self.ws.close()
        except Exception: pass
