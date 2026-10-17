import sys, os, re, time, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c1')
img('alpine:3.20')
purge()
big = os.urandom(50 * 1024 * 1024)
base = {'big.bin': big, 'app.txt': 'hello\n', 'sub/x.txt': 'x\n'}
def ctx_lines(o):
    return [l.strip() for l in o.split('\n') if 'load build context' in l or 'transferring context' in l or 'transferring dockerfile' in l]
def try_build(name, dockerfile, files=None, extra=(), tag=None):
    d = ctx(name, {**(files or base), 'Dockerfile': dockerfile})
    t0 = time.time()
    rc, o = build(d, tag or f'bwlab-{name}', *extra)
    return rc, o, ms(t0), d
print('== 一:上下文里有一个 50 MiB 的无关文件,Dockerfile 只 COPY 一个小文件 vs COPY 整个目录(BuildKit,Docker Engine 29.8.2)')
rc, o, t, d = try_build('c1a', 'FROM alpine:3.20\nCOPY app.txt /app.txt\n')
print('  [只 COPY app.txt] 退出码', rc, f'用时 {t:.0f} ms')
for l in ctx_lines(o): print('    ' + l)
rc, o, t, d = try_build('c1b', 'FROM alpine:3.20\nCOPY . /ctx/\n')
print('  [COPY . /ctx/] 退出码', rc, f'用时 {t:.0f} ms')
for l in ctx_lines(o): print('    ' + l)
print('== 二:同一个上下文再构建一次(没有任何文件改动)')
d = DT / 'c1b'
t0 = time.time(); rc, o = build(d, 'bwlab-c1b'); t = ms(t0)
print(f'  [COPY . /ctx/ 第 2 次] 退出码 {rc},用时 {t:.0f} ms')
for l in ctx_lines(o): print('    ' + l)
print('  ' + ' | '.join(l.strip() for l in o.split('\n') if 'CACHED' in l)[:200])
print('== 三:改动一个小文件后再构建(app.txt 改了内容)')
(d / 'app.txt').write_text('changed\n')
t0 = time.time(); rc, o = build(d, 'bwlab-c1b'); t = ms(t0)
print(f'  [COPY . /ctx/ 改了 app.txt] 退出码 {rc},用时 {t:.0f} ms')
for l in ctx_lines(o): print('    ' + l)
print('== 四:不给上下文(Dockerfile 从标准输入读),Dockerfile 里 COPY 文件')
dd = ctx('c1d', {'Dockerfile': 'FROM alpine:3.20\nCOPY app.txt /app.txt\n'})
rc, o = dk('build', '--progress', 'plain', '-t', 'bwlab-c1d', '-', input=(dd / 'Dockerfile').read_text())
msgs = [l.strip() for l in o.split('\n') if 'ERROR' in l or 'not found' in l or 'failed' in l]
print(f'  退出码 {rc};' + re.sub(r'ref \w+::\w+', 'ref <id>', ' | '.join(msgs))[:260])
print('== 五:Dockerfile 想 COPY 上下文目录之外的文件(../secret.txt)')
(DT / 'c1e_parent').mkdir(exist_ok=True); (DT / 'c1e_parent' / 'secret.txt').write_text('s\n')
ctxdir = ctx('c1e_parent/proj', {'Dockerfile': 'FROM alpine:3.20\nCOPY ../secret.txt /secret.txt\n'}, clean=False)
rc, o = build(ctxdir, 'bwlab-c1e')
msgs = [l.strip() for l in o.split('\n') if 'ERROR' in l or 'forbidden' in l or 'outside' in l]
print(f'  退出码 {rc};' + re.sub(r'ref \w+::\w+', 'ref <id>', ' | '.join(msgs))[:260])
print('== 六:通过 -f 指定上下文之外的 Dockerfile(上下文仍然是最后那个目录参数)')
alt = DT / 'c1e_parent' / 'Dockerfile.alt'
alt.write_text('FROM alpine:3.20\nCOPY app.txt /app.txt\nRUN cat /app.txt\n')
ctx2 = ctx('c1f', {'app.txt': 'from ctx2\n'})
t0 = time.time(); rc, o = dk('build', '--progress', 'plain', '-t', 'bwlab-c1f', '-f', str(alt), str(ctx2)); t = ms(t0)
print(f'  退出码 {rc},用时 {t:.0f} ms;' + ' | '.join(l.strip() for l in o.split('\n') if 'from ctx2' in l or 'transferring dockerfile' in l)[:200])
purge()
