import sys, os, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l57')
import ll as _ll
def run(d, cmd, t='now', **k): return _ll.run(d, cmd, t, **k)
def ci(d, msg, files=None, t='now', **k): return _ll.ci(d, msg, files, t, **k)
SAN = lambda t: re.sub(r'\b[0-9a-f]{40}\b', '<sha>', t)
src = lab('l57src'); ci(src, 'S1', {'a': '1\n'}, t=0); ci(src, 'S2', {'a': '2\n'}, t=1); run(src, 'git branch dev')
R = LT / 'l57remote.git'; shutil.rmtree(R, ignore_errors=True); run(src, f'git clone -q --bare . {R}')
def tr(d, cmd, side=None):
    rc, o = run(d, f'GIT_TRACE_PACKET=1 {cmd} 2>&1 >/dev/null | grep "packet:"')
    L = [re.sub(r'^\S+ pkt-line\.c:\d+\s+', '', l) for l in o.split('\n') if l]
    return [re.sub(r'\s+', ' ', SAN(l)) for l in L]
print('== 一:协议 v0 的 git clone:服务端先报出自己有哪些 ref 和能力,客户端说 want,再 done,服务端回 NAK/ACK 然后发 pack')
shutil.rmtree(LT / 'l57c', ignore_errors=True)
L = tr(LT, f'git -c protocol.version=0 clone {"file://" + str(R)} l57c')
for l in L[:40]: print('  ' + l[:150])
print(f'  (共 {len(L)} 行 packet 跟踪)')
print('== 二:pkt-line 的格式:每一行前面是 4 位十六进制的长度(含这 4 个字符本身),0000 是 flush-pkt。直接调用服务端 git upload-pack --advertise-refs 看原始字节')
raw = subprocess.run([GIT, 'upload-pack', '--stateless-rpc', '--advertise-refs', str(R)], capture_output=True, env=lenv(GIT_PROTOCOL='')).stdout
pos = 0; n = 0
while pos < len(raw) and n < 5:
    ln = int(raw[pos:pos + 4], 16)
    if ln == 0: print(f'  偏移 {pos}: 0000 → flush-pkt'); pos += 4
    else:
        payload = raw[pos + 4:pos + ln]; print(f'  偏移 {pos}: 长度 {raw[pos:pos+4].decode()}({ln})→ {SAN(payload.decode(errors="replace")).replace(chr(0), "\\0")[:130]!r}'); pos += ln
    n += 1
refs = 0; q = 0
while q < len(raw):
    ln = int(raw[q:q + 4], 16); q += 4 if ln == 0 else ln; refs += (ln != 0)
print(f'  总共 {refs} 个非空 pkt-line(含 HEAD 一行带 capabilities,其余每个 ref 一行),总字节数 {len(raw)}')
print('== 三:增量 fetch:客户端用 have 告诉服务端“我已经有这些”,服务端只发缺的对象')
shutil.rmtree(LT / 'l57inc', ignore_errors=True); run(LT, f'git clone -q {R} l57inc'); inc = LT / 'l57inc'
ci(src, 'S3 新提交', {'a': '3\n', 'b': 'new\n'}, t=5); run(src, f'git push -q {R} main')
CNT = "git count-objects -v | awk '/^in-pack|^count/{s+=$2} END{print s}'"
before = out1(inc, CNT)
L = tr(inc, 'git -c protocol.version=0 fetch origin')
print('  (只列 want / have / ACK / NAK / done 相关行)')
for l in L:
    if re.search(r'(fetch> (want|have|done)|fetch< (ACK|NAK))', l) or 'fetch> 0000' in l: print('  ' + l[:150])
after = out1(inc, CNT)
print(f'  fetch 之前对象总数 {before},之后 {after}:新增 {int(after) - int(before)} 个对象(1 个 commit、1 个 tree、2 个 blob)')
print('== 四:已经是最新时的 fetch:只有 ref 列表,没有 want')
L = tr(inc, 'git -c protocol.version=0 fetch origin')
print(f'  跟踪共 {len(L)} 行;其中 want 行 {sum(1 for l in L if "want" in l)} 条,have 行 {sum(1 for l in L if "have" in l)} 条,done {sum(1 for l in L if "done" in l)} 条')
for l in L[:6]: print('  ' + l[:130])
