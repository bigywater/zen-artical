import sys, os, re, time, subprocess, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c58')
img('alpine:3.20')
purge()
def comp(proj, d, *args, timeout=180):
    r = subprocess.run(['docker', 'compose', '-p', proj, '-f', str(d / 'compose.yaml'), *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, tidy(r.stdout + r.stderr)
def started(name):
    s = out('inspect', '--format', '{{.State.StartedAt}}', name)
    return datetime.datetime.fromisoformat(s[:26] + '+00:00' if s.endswith('Z') else s)
def gap(a, b): return (started(b) - started(a)).total_seconds()
def mk(name, yaml):
    return ctx(name, {'compose.yaml': yaml})
DB = 'sh -c "sleep 3; touch /tmp/ready; echo db ready; sleep 120"'
WEB = 'sh -c "if [ -n \\"$WAITDB\\" ]; then :; fi; echo web started; sleep 120"'
print('== 一:只写 depends_on:启动顺序有,但不等就绪(Docker Compose v5.5.1)')
d = mk('c58a', f'''services:
  db:
    image: alpine:3.20
    labels: {{bwlab: "1"}}
    command: {DB}
  web:
    image: alpine:3.20
    labels: {{bwlab: "1"}}
    depends_on: [db]
    command: sh -c "if [ -f /dev/shm/x ]; then :; fi; echo web started; sleep 120"
''')
t0 = time.time(); rc, o = comp('bwlab-c58a', d, 'up', '-d'); t = time.time() - t0
print(f'  docker compose up -d:退出码 {rc},用时 {t:.1f} 秒;输出中的状态行:' + ' | '.join(l.strip() for l in o.splitlines() if 'Container' in l or 'Started' in l)[:200])
print(f'  db 与 web 的启动时间差(web 晚于 db 多少秒):{gap("bwlab-c58a-db-1", "bwlab-c58a-web-1"):.2f} 秒(db 要 3 秒后才就绪)')
comp('bwlab-c58a', d, 'down', '-v', '-t', '1')
print('== 二:condition: service_healthy,等 db 通过健康检查')
d = mk('c58b', f'''services:
  db:
    image: alpine:3.20
    labels: {{bwlab: "1"}}
    command: {DB}
    healthcheck:
      test: ["CMD", "test", "-f", "/tmp/ready"]
      interval: 1s
      timeout: 1s
      retries: 10
  web:
    image: alpine:3.20
    labels: {{bwlab: "1"}}
    depends_on:
      db:
        condition: service_healthy
    command: sh -c "echo web started; sleep 120"
''')
t0 = time.time(); rc, o = comp('bwlab-c58b', d, 'up', '-d'); t = time.time() - t0
print(f'  docker compose up -d:退出码 {rc},用时 {t:.1f} 秒')
print(f'  db 与 web 的启动时间差:{gap("bwlab-c58b-db-1", "bwlab-c58b-web-1"):.2f} 秒;db 的健康状态:{out("inspect", "--format", "{{.State.Health.Status}}", "bwlab-c58b-db-1")}')
comp('bwlab-c58b', d, 'down', '-v', '-t', '1')
print('== 三:condition: service_completed_successfully,等一次性任务成功退出')
for code in (0, 1):
    d = mk(f'c58c{code}', f'''services:
  job:
    image: alpine:3.20
    labels: {{bwlab: "1"}}
    command: sh -c "sleep 2; echo job done; exit {code}"
  web:
    image: alpine:3.20
    labels: {{bwlab: "1"}}
    depends_on:
      job:
        condition: service_completed_successfully
    command: sh -c "echo web started; sleep 120"
''')
    t0 = time.time(); rc, o = comp(f'bwlab-c58c{code}', d, 'up', '-d'); t = time.time() - t0
    web = out('ps', '-a', '--filter', f'name=bwlab-c58c{code}-web', '--format', '{{.Status}}')
    print(f'  job 退出码 {code}:docker compose up -d 退出码 {rc},用时 {t:.1f} 秒;web 容器:{web or "没有创建"};输出里的错误:{next((l.strip() for l in o.splitlines() if "exit" in l.lower() or "fail" in l.lower() or "error" in l.lower()), "无")[:120]}')
    comp(f'bwlab-c58c{code}', d, 'down', '-v', '-t', '1')
print('== 四:docker compose up 时按依赖顺序创建的顺序(--no-deps 的对比)')
d = mk('c58d', '''services:
  a:
    image: alpine:3.20
    labels: {bwlab: "1"}
    command: sleep 120
  b:
    image: alpine:3.20
    labels: {bwlab: "1"}
    depends_on: [a]
    command: sleep 120
  c:
    image: alpine:3.20
    labels: {bwlab: "1"}
    depends_on: [b]
    command: sleep 120
''')
rc, o = comp('bwlab-c58d', d, 'up', '-d', 'c'); print(f'  只指定启动 c:启动了 {sorted(out("ps", "--filter", "name=bwlab-c58d", "--format", "{{.Names}}").split())}')
comp('bwlab-c58d', d, 'down', '-v', '-t', '1')
rc, o = comp('bwlab-c58d', d, 'up', '-d', '--no-deps', 'c'); print(f'  --no-deps 只启动 c:启动了 {sorted(out("ps", "--filter", "name=bwlab-c58d", "--format", "{{.Names}}").split())}')
comp('bwlab-c58d', d, 'down', '-v', '-t', '1')
purge()
