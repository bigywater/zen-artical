import sys, os, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l58')
import ll as _ll
def run(d, cmd, t='now', **k): return _ll.run(d, cmd, t, **k)
def ci(d, msg, files=None, t='now', **k): return _ll.ci(d, msg, files, t, **k)
SAN = lambda t: re.sub(r'\b[0-9a-f]{40}\b', '<sha>', t)
src = lab('l58src'); ci(src, 'S1', {'a': '1\n'}, t=0); ci(src, 'S2', {'a': '2\n'}, t=1)
small = LT / 'l58small.git'; shutil.rmtree(small, ignore_errors=True); run(src, f'git clone -q --bare . {small}')   # 没有 5000 个 tag 的小仓库,让第一节的跟踪短一点
R = LT / 'l58remote.git'; shutil.rmtree(R, ignore_errors=True); run(src, f'git clone -q --bare . {R}')
run(src, 'git update-ref --stdin', stdin=''.join(f'create refs/tags/t{i:05d} HEAD\n' for i in range(5000)))
run(src, f'git push -q {R} --tags')
def tr(d, cmd):
    rc, o = run(d, f'GIT_TRACE_PACKET=1 {cmd} 2>&1 >/dev/null | grep "packet:"')
    return [re.sub(r'\s+', ' ', SAN(re.sub(r'^\S+ pkt-line\.c:\d+\s+', '', l))) for l in o.split('\n') if l]
print('== 一:本机 git 默认就是协议 v2:没有设置 protocol.version,clone 的跟踪里第一行就是 version 2')
sh_ = lambda *a, **k: sh(*a, **k)
sh(LT, 'git config --get protocol.version || echo "protocol.version 未设置(2.26 起默认 v2)"')
shutil.rmtree(LT / 'l58c', ignore_errors=True)
L = tr(LT, f'git clone file://{small} l58c')
for l in L[:38]: print('  ' + l[:150])
print(f'  (共 {len(L)} 行 packet 跟踪)')
print('== 二:v2 把“列出 ref”和“取对象”拆成两条命令:ls-refs(可以带 ref-prefix 过滤)和 fetch')
shutil.rmtree(LT / 'l58c2', ignore_errors=True); run(LT, f'git clone -q {R} l58c2'); c2 = LT / 'l58c2'
ci(src, 'S3 新提交', {'a': '3\n'}, t=5); run(src, f'git push -q {R} main')
L = tr(c2, 'git fetch origin main')
for l in L:
    if re.search(r'(command=|ref-prefix|ls-refs|fetch>|fetch< (shallow|acknowledgments|ready|packfile|ACK|NAK)|0001|0000)', l) and 'refs/tags/t0' not in l: print('  ' + l[:130])
print('== 三:有 5000 个 tag 的远程,fetch 一个分支:v0 先收到全部 5000+ 个 ref,v2 只收到被请求前缀的 ref')
for ver in (0, 2):
    c3 = LT / f'l58v{ver}'; shutil.rmtree(c3, ignore_errors=True); run(LT, f'git -c protocol.version={ver} clone -q --no-tags {R} l58v{ver}')
    ci(src, f'S{ver + 4}', {'a': str(ver + 4) + '\n'}, t=6 + ver); run(src, f'git push -q {R} main')
    L = tr(c3, f'git -c protocol.version={ver} fetch --no-tags origin main')
    recv = [l for l in L if l.startswith('packet: fetch<')]; sent = [l for l in L if l.startswith('packet: upload-pack>')]
    print(f'  v{ver}:服务端发出(upload-pack>){len(sent)} 行,其中 ref 行 {sum(1 for l in sent if "refs/" in l)} 行;客户端收到(fetch<){len(recv)} 行')
print('== 四:什么也没变的 fetch')
for ver in (0, 2):
    c3 = LT / f'l58v{ver}'; run(c3, f'git -c protocol.version={ver} fetch -q --no-tags origin main'); L = tr(c3, f'git -c protocol.version={ver} fetch --no-tags origin main')
    print(f'  v{ver}:跟踪 {len(L)} 行;客户端发出的 want {sum(1 for l in L if re.match(r"packet: fetch> want ", l))} 条;v2 命令:ls-refs {sum(1 for l in L if l.startswith("packet: fetch> command=ls-refs"))} 次、fetch {sum(1 for l in L if l.startswith("packet: fetch> command=fetch"))} 次')
print('== 五:v2 服务端的能力广告(原始 pkt-line):GIT_PROTOCOL=version=2')
raw = subprocess.run([GIT, 'upload-pack', '--advertise-refs', str(R)], capture_output=True, env=lenv(GIT_PROTOCOL='version=2')).stdout
pos = 0
while pos < len(raw):
    ln = int(raw[pos:pos + 4], 16)
    if ln == 0: print('  0000 (flush)'); pos += 4; continue
    if ln == 1: print('  0001 (delim)'); pos += 4; continue
    print('  ' + SAN(raw[pos + 4:pos + ln].decode().rstrip('\n'))); pos += ln
