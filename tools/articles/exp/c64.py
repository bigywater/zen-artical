import sys, os, re, time, subprocess, json, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c64')
img('alpine:3.20')
purge()
P = 'bwlab-c64'
Y = '''services:
  web:
    build: .
    labels: {bwlab: "1"}
    develop:
      watch:
        - action: sync
          path: ./app
          target: /app
        - action: sync+restart
          path: ./conf.txt
          target: /conf.txt
        - action: rebuild
          path: ./deps.txt
'''
DF = '''FROM alpine:3.20
COPY app /app
COPY conf.txt /conf.txt
COPY deps.txt /deps.txt
CMD ["sh", "-c", "echo started-at-$(date +%s); sleep 600"]
'''
d = ctx('c64', {'compose.yaml': Y, 'Dockerfile': DF, 'app/message.txt': 'v1\n', 'conf.txt': 'c1\n', 'deps.txt': 'd1\n'})
def comp(*args, timeout=300):
    r = subprocess.run(['docker', 'compose', '-p', P, *args], capture_output=True, text=True, timeout=timeout, cwd=str(d))
    return r.returncode, tidy(r.stdout + r.stderr)
def cid(): return out('ps', '-q', '--filter', f'name={P}-web')[:12]
def cat(path): return dk('exec', f'{P}-web-1', 'cat', path)[1].strip()
def started(): return out('inspect', '--format', '{{.State.StartedAt}}', f'{P}-web-1')
print('== 一:启动并开始监视(Docker Compose v5.5.1)')
t0 = time.time(); rc, o = comp('up', '-d', '--build'); print(f'  docker compose up -d --build:退出码 {rc},用时 {time.time() - t0:.1f} 秒;容器 {cid()}')
c0 = cid(); s0 = started()
w = subprocess.Popen(['docker', 'compose', '-p', P, 'watch', '--no-up'], cwd=str(d), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(4)
print(f'  docker compose watch --no-up 在后台运行(进程是否还在:{w.poll() is None})')
print('== 二:sync:改 ./app/message.txt')
lat = []
for i in range(3):
    t0 = time.time()
    (d / 'app' / 'message.txt').write_text(f'v{i + 2}\n')
    while time.time() - t0 < 15 and cat('/app/message.txt') != f'v{i + 2}': time.sleep(0.05)
    lat.append((time.time() - t0) * 1000)
print(f'  写入后到容器里读到新内容的时间:{[round(x) for x in lat]} ms(含每次 docker exec 轮询的开销);容器还是原来的吗?{cid() == c0};StartedAt 变了吗?{started() != s0}')
(d / 'app' / 'new.txt').write_text('new file\n'); time.sleep(2)
print(f'  新增 app/new.txt:容器里 {cat("/app/new.txt") or "没有"}')
(d / 'app' / 'new.txt').unlink(); time.sleep(2)
print(f'  删除 app/new.txt 后容器里:{dk("exec", f"{P}-web-1", "ls", "/app")[1].strip().replace(chr(10), " ")}')
print('== 三:sync+restart:改 ./conf.txt')
ev0 = int(time.time()) - 1
t0 = time.time(); (d / 'conf.txt').write_text('c2\n')
while time.time() - t0 < 20 and cat('/conf.txt') != 'c2': time.sleep(0.1)
t_sync = time.time() - t0
for _ in range(100):
    if started() != s0: break
    time.sleep(0.2)
t_rs = time.time() - t0
print(f'  容器里 /conf.txt = {cat("/conf.txt")}(约 {t_sync * 1000:.0f} ms 后读到);容器还是原来的?{cid() == c0};StartedAt 变了吗?{started() != s0}' + (f'(约 {t_rs:.1f} 秒后看到重启)' if started() != s0 else ''))
rc, o = dk('events', '--since', str(ev0), '--until', str(int(time.time()) + 1), '--filter', f'container={P}-web-1', '--format', '{{.Action}}', timeout=30)
print('  这段时间容器的事件(去掉 exec_*):' + ' → '.join(l.strip() for l in o.splitlines() if l.strip() and not l.startswith('exec_')))
s1 = started()
print('== 四:rebuild:改 ./deps.txt')
t0 = time.time(); (d / 'deps.txt').write_text('d2\n')
for _ in range(300):
    if cid() and cid() != c0: break
    time.sleep(0.2)
time.sleep(1)
print(f'  容器被重新创建了吗?{cid() != c0};耗时约 {time.time() - t0:.1f} 秒;新容器里 /deps.txt = {cat("/deps.txt")};/app/message.txt = {cat("/app/message.txt")}')
w.send_signal(signal.SIGINT)
try: wo = w.communicate(timeout=15)[0]
except Exception: w.kill(); wo = ''
print('  watch 进程输出里的不同行:' + ' | '.join(dict.fromkeys(l.strip() for l in tidy(wo).splitlines() if l.strip()))[:420])
comp('down', '-v', '-t', '1')
purge()
