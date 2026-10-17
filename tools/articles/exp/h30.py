import sys, os, subprocess, json, time, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
from pcdp import Chrome
tee('h30')
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
gdir = os.path.join(here, 'grpcgo')
d = pdir('h30')
exe = str(d / 'h30srv')
r = subprocess.run(['go', 'build', '-o', exe, './cmd/h30'], cwd=gdir, capture_output=True, text=True)
if r.returncode: print('BUILD ERROR', r.stderr[-1500:]); sys.exit(1)
sv = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
ports = {}
for _ in range(3):
    k, v = sv.stdout.readline().split(); ports[k] = int(v)
NATIVE, WEB, PAGE = f'https://localhost:{ports["NATIVE"]}', f'https://localhost:{ports["WEB"]}', f'http://127.0.0.1:{ports["PAGE"]}'

JS_HELPERS = """
window.frame = (bytes, flag=0) => { const b = new Uint8Array(5 + bytes.length); b[0] = flag; new DataView(b.buffer).setUint32(1, bytes.length); b.set(bytes, 5); return b; };
window.hex = u8 => Array.from(u8).map(x => x.toString(16).padStart(2, '0')).join('');
window.reqMsg = s => { const t = new TextEncoder().encode(s); return new Uint8Array([0x0a, t.length, ...t]); };
window.parseFrames = u8 => { const out = []; let i = 0; while (i + 5 <= u8.length) { const flag = u8[i]; const len = new DataView(u8.buffer, u8.byteOffset + i + 1, 4).getUint32(0); out.push({flag, len, body: u8.slice(i + 5, i + 5 + len)}); i += 5 + len; } return out; };
"""

def ev(pg, expr):
    return pg.eval(expr, await_promise=True)

try:
    with Chrome(free_port(9990), d, extra=['--ignore-certificate-errors']) as ch:
        print('== 一:浏览器直接用 fetch 调原生 gRPC(同源,HTTPS/HTTP2):成功的调用和被拒绝的调用,JS 能看到哪些信息')
        pg = ch.new_page(NATIVE + '/'); pg.send('Page.enable'); pg.drain(0.8)
        pg.eval(JS_HELPERS)
        js = """(async () => {
          const out = {};
          for (const m of ['hi', 'deny']) {
            const r = await fetch('/demo.Demo/Unary', {method: 'POST', headers: {'Content-Type': 'application/grpc', 'TE': 'trailers'}, body: frame(reqMsg(m))});
            const buf = new Uint8Array(await r.arrayBuffer());
            out[m] = {status: r.status, protocol: performance.getEntriesByType('resource').slice(-1)[0].nextHopProtocol, contentType: r.headers.get('content-type'), grpcStatus: r.headers.get('grpc-status'), grpcMessage: r.headers.get('grpc-message'), bodyBytes: buf.length, bodyHex: hex(buf), headerNames: [...r.headers.keys()].sort().join(',')};
          }
          return JSON.stringify(out);
        })()"""
        o = json.loads(ev(pg, js))
        for m, label in (('hi', '成功的调用(msg=hi)'), ('deny', '被服务端拒绝的调用(msg=deny,服务端返回 Unauthenticated)')):
            x = o[m]
            print(f'  {label}:HTTP {x["status"]}、协议 {x["protocol"]};响应头可见:{x["headerNames"]};grpc-status={x["grpcStatus"]}、grpc-message={x["grpcMessage"]};响应体 {x["bodyBytes"]} 字节 {x["bodyHex"]}')

        print('== 二:跨域(页面在 http://127.0.0.1 的另一个端口)用 fetch 调原生 gRPC:预检请求')
        pg2 = ch.new_page(PAGE + '/'); pg2.send('Page.enable'); pg2.send('Network.enable'); pg2.drain(0.6); pg2.eval(JS_HELPERS); pg2.events.clear()
        js = f"""(async () => {{
          try {{ const r = await fetch('{NATIVE}/demo.Demo/Unary', {{method: 'POST', headers: {{'Content-Type': 'application/grpc'}}, body: frame(reqMsg('hi'))}}); return 'HTTP ' + r.status; }}
          catch (e) {{ return e.name + ': ' + e.message; }}
        }})()"""
        res = ev(pg2, js); pg2.drain(0.5)
        opts = [e['params']['request']['method'] for e in pg2.events if e['method'] == 'Network.requestWillBeSent']
        print(f'  fetch 的结果:{res};浏览器实际发出的请求方法:{opts}')

        print('== 三:grpc-web(content-type: application/grpc-web+proto,跨域,经过 improbable-eng/grpc-web 的 Go 包装):响应体里的帧')
        js = f"""(async () => {{
          const out = {{}};
          for (const m of ['hi', 'deny']) {{
            const r = await fetch('{WEB}/demo.Demo/Unary', {{method: 'POST', headers: {{'Content-Type': 'application/grpc-web+proto', 'X-Grpc-Web': '1'}}, body: frame(reqMsg(m))}});
            const buf = new Uint8Array(await r.arrayBuffer());
            const fr = parseFrames(buf).map(f => ({{flag: f.flag, len: f.len, text: f.flag === 128 ? new TextDecoder().decode(f.body) : hex(f.body)}}));
            out[m] = {{status: r.status, contentType: r.headers.get('content-type'), grpcStatusHeader: r.headers.get('grpc-status'), bodyBytes: buf.length, frames: fr}};
          }}
          return JSON.stringify(out);
        }})()"""
        o = json.loads(ev(pg2, js))
        for m, label in (('hi', '成功的调用'), ('deny', '被拒绝的调用')):
            x = o[m]
            print(f'  {label}:HTTP {x["status"]}、content-type={x["contentType"]}、响应头 grpc-status={x["grpcStatusHeader"]};响应体 {x["bodyBytes"]} 字节,共 {len(x["frames"])} 帧')
            for f in x['frames']:
                kind = '数据帧' if f['flag'] == 0 else ('trailers 帧' if f['flag'] == 128 else f'标志位 {f["flag"]}')
                print(f'      {kind}(标志位 {f["flag"]},长度 {f["len"]}):{f["text"]!r}')

        print('== 四:grpc-web 的服务端流:浏览器用 ReadableStream 边收边读,每一帧到达的时刻(服务端每 200 ms 发一条)')
        js = f"""(async () => {{
          const t0 = performance.now();
          const r = await fetch('{WEB}/demo.Demo/ServerStream', {{method: 'POST', headers: {{'Content-Type': 'application/grpc-web+proto', 'X-Grpc-Web': '1'}}, body: frame(reqMsg('go'))}});
          const rd = r.body.getReader(); let acc = new Uint8Array(0); const ev = [];
          while (true) {{
            const {{value, done}} = await rd.read(); if (done) break;
            const n = new Uint8Array(acc.length + value.length); n.set(acc); n.set(value, acc.length); acc = n;
            const fr = parseFrames(acc); while (ev.length < fr.length) {{ const f = fr[ev.length]; ev.push({{t: Math.round(performance.now() - t0), flag: f.flag, text: f.flag === 128 ? new TextDecoder().decode(f.body).trim() : hex(f.body)}}); }}
          }}
          return JSON.stringify(ev);
        }})()"""
        for e in json.loads(ev(pg2, js)):
            print(f'  {e["t"]:4d} ms:标志位 {e["flag"]}  {e["text"]!r}')

        print('== 五:客户端流:把两条消息帧一次性写在同一个请求体里,调用 ClientStream(服务端数收到几条)')
        js = f"""(async () => {{
          const body = new Uint8Array([...frame(reqMsg('a')), ...frame(reqMsg('b'))]);
          const r = await fetch('{WEB}/demo.Demo/ClientStream', {{method: 'POST', headers: {{'Content-Type': 'application/grpc-web+proto', 'X-Grpc-Web': '1'}}, body}});
          const buf = new Uint8Array(await r.arrayBuffer());
          return JSON.stringify({{status: r.status, frames: parseFrames(buf).map(f => ({{flag: f.flag, len: f.len, text: f.flag === 128 ? new TextDecoder().decode(f.body) : hex(f.body)}}))}});
        }})()"""
        x = json.loads(ev(pg2, js))
        print(f'  HTTP {x["status"]};响应帧:{[(f["flag"], f["text"]) for f in x["frames"]]}')
finally:
    try: sv.stdin.close(); sv.wait(timeout=5)
    except Exception: sv.kill()
    shutil.rmtree(d, ignore_errors=True)
