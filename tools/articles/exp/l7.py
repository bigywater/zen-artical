import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l7')
s1 = lab('l7sha1'); s2 = lab('l7sha256', '--object-format=sha256')
FILES = {f'f{i:02d}.txt': f'内容 {i}\n' for i in range(10)}
c1 = ci(s1, '提交', FILES, t=0); c2 = ci(s2, '提交', FILES, t=0)
print('== 一:object-format 写进仓库配置;repositoryformatversion 变成 1')
for nm, d in [('sha1', s1), ('sha256', s2)]:
    print(f'  [{nm}]'); sh(d, 'git rev-parse --show-object-format; git config --local --list | grep -E "repositoryformatversion|objectformat" || true', ind='    ')
print('== 二:同样的内容,hash 的长度:40 位对 64 位十六进制')
for nm, d, c in [('sha1', s1, c1), ('sha256', s2, c2)]:
    print(f'  [{nm}] HEAD = {c}  ({len(c)} 位十六进制)')
sh(s2, 'find .git/objects -type f | head -3')
sh(s2, "git log --oneline -1; git log --abbrev=10 --oneline -1")
print('== 三:手算 sha256 仓库里的 blob hash:公式相同,只是换成 SHA-256')
body = b'\xe5\x86\x85\xe5\xae\xb9 3\n'
blob = out1(s2, 'git rev-parse HEAD:f03.txt'); data = (s2 / 'f03.txt').read_bytes()
mine = hashlib.sha256(b'blob %d\0' % len(data) + data).hexdigest()
print(f'  git:  {blob}\n  手算: {mine}\n  一致: {blob == mine}')
print('== 四:tree 条目里的 hash 从 20 字节变成 32 字节')
def entries(d):
    t = out1(d, 'git rev-parse HEAD^{tree}'); raw = loose(d, t); hdr, b = raw.split(b'\0', 1); return len(raw), hdr.decode(), b
for nm, d, hl in [('sha1', s1, 20), ('sha256', s2, 32)]:
    n, h, b = entries(d)
    i = 0; cnt = 0
    while i < len(b):
        j = b.index(b'\0', i); i = j + 1 + hl; cnt += 1
    print(f'  [{nm}] tree 解压后 {n} 字节,头部 "{h}",{cnt} 个条目,每个条目的 hash 占 {hl} 字节')
print('== 五:代价:同样 10 个文件,两种格式的 .git/index 与 tree 对象大小')
for nm, d in [('sha1', s1), ('sha256', s2)]:
    print(f'  [{nm}] .git/index = {(d / ".git" / "index").stat().st_size} 字节,tree 对象解压后 {entries(d)[0]} 字节')
print('== 六:两种格式不能互相 fetch')
sh(s2, f'git fetch {s1} main 2>&1 | head -5')
sh(s1, f'git fetch {s2} main 2>&1 | head -5')
sh(LT, f'git clone -q {s2} l7clone 2>&1 && git -C l7clone rev-parse --show-object-format')
