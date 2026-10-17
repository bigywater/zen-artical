import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l1')
d = lab('l1')
ci(d, '第一次提交', {'README.md': 'hello world\n', 'src/main.py': 'print("hi")\n'}, t=0)
c2 = ci(d, '改一下 README', {'README.md': 'hello world\nsecond line\n'}, t=5)
print('== 一:一个有两次提交的小仓库,.git/objects 里到底有哪些文件')
sh(d, 'git log --oneline')
sh(d, 'find .git/objects -type f | sort')
sh(d, 'find .git/objects -type f | wc -l')
print('== 二:blob:zlib 解压松散对象,拿到的是 "blob 长度\\0内容"')
sha = out1(d, 'git rev-parse HEAD:src/main.py')
print(f'  src/main.py 的 blob = {sha}')
raw = loose(d, sha)
print(f'  文件 .git/objects/{sha[:2]}/{sha[2:]} 的大小: {(d / ".git" / "objects" / sha[:2] / sha[2:]).stat().st_size} 字节(压缩后);解压后 {len(raw)} 字节:')
hexdump(raw)
print('  repr:', repr(raw))
sh(d, f'git cat-file -t {sha}; git cat-file -s {sha}; git cat-file -p {sha}')
print('== 三:tree:头部之后是一串 "模式 名字\\0 20 字节二进制 hash",没有分隔符')
tsha = out1(d, 'git rev-parse HEAD^{tree}')
raw = loose(d, tsha)
print(f'  根 tree = {tsha},解压后 {len(raw)} 字节:')
hexdump(raw, 128)
hdr, body = raw.split(b'\0', 1)
print('  头部:', hdr.decode())
i = 0; n = 0
while i < len(body):
    j = body.index(b' ', i); mode = body[i:j].decode(); k = body.index(b'\0', j); name = body[j + 1:k].decode(); h = body[k + 1:k + 21].hex(); i = k + 21; n += 1
    print(f'  条目 {n}: 模式={mode:<6} 名字={name:<10} 20 字节={h}')
sh(d, f'git ls-tree {tsha}')
print('== 四:commit:纯文本,几行头加一个空行加提交说明')
raw = loose(d, c2)
print(f'  HEAD = {c2},解压后 {len(raw)} 字节:')
hdr, body = raw.split(b'\0', 1)
print('  头部:', hdr.decode())
for l in body.decode().split('\n'): print('  | ' + l)
sh(d, 'git cat-file -p HEAD')
print('== 五:不用 git,只用 Python 的 zlib 从 HEAD 往下走一遍,和 git ls-tree -r 对比')
def obj(sha):
    r = loose(d, sha); h, b = r.split(b'\0', 1); t, ln = h.split(b' '); assert int(ln) == len(b); return t.decode(), b
def walk(tsha, pre=''):
    t, b = obj(tsha); assert t == 'tree'; i = 0
    while i < len(b):
        j = b.index(b' ', i); mode = b[i:j].decode(); k = b.index(b'\0', j); name = b[j + 1:k].decode(); h = b[k + 1:k + 21].hex(); i = k + 21
        if mode == '40000': yield from walk(h, pre + name + '/')
        else: yield mode.zfill(6), h, pre + name
head = open(d / '.git' / 'HEAD').read().strip(); print('  .git/HEAD:', head)
ref = head.split(' ')[1]; csha = open(d / '.git' / ref).read().strip(); print(f'  {ref}: {csha}')
t, b = obj(csha); root = b.decode().split('\n')[0].split(' ')[1]; print('  commit 的 tree 行:', root)
mine = [f'{m} blob {h}\t{p}' for m, h, p in walk(root)]
git_ = out1(d, 'git ls-tree -r HEAD').split('\n')
print('  Python 走出来的:'); [print('    ' + x) for x in mine]
print('  与 git ls-tree -r HEAD 完全一致:', mine == git_)
