import sys, os, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l13')
d = lab('l13')
rnd = random.Random(13)
lines = [f'第 {i:03d} 行:' + ''.join(rnd.choice('abcdefghij') for _ in range(40)) for i in range(150)]
W(d, {'doc.txt': '\n'.join(lines) + '\n'}); ci(d, 'v0', t=0)
for v in range(1, 5):
    lines[v * 20] = f'已修改 {v}:' + lines[v * 20]
    W(d, {'doc.txt': '\n'.join(lines) + '\n'}); ci(d, f'v{v}', t=v)
print('== 一:pack 文件开头 12 字节:"PACK"、版本号 2、对象个数')
sh(d, 'git gc -q; ls .git/objects/pack; git count-objects -v | grep -E "^(count|in-pack)"')
pk = next((d / '.git' / 'objects' / 'pack').glob('*.pack')); data = pk.read_bytes()
hexdump(data, 32)
ver, n, ents = parse_pack(data)
print(f'  版本 {ver},对象数 {n},文件 {len(data):,} 字节')
print('== 二:逐个解析条目头(类型 3 位 + 大小变长整数),与 git verify-pack -v 对照')
vp = {}
for l in out1(d, f'git verify-pack -v {pk}').split('\n'):
    p = l.split()
    if len(p) >= 5 and len(p[0]) == 40: vp[int(p[4])] = p
print('  偏移   类型        解压后大小  包内大小  头部字节  verify-pack 里的同一行')
for e in ents:
    v = vp[e['off']]; ok = (PTYPES[e['type']].replace('ofs-delta', v[1]) == v[1] or v[1] in ('blob', 'tree', 'commit')) and int(v[3]) == e['hdr'] + e['clen'] + (0 if e['type'] != 6 else 0)
    print(f"  {e['off']:>5}  {PTYPES[e['type']]:<10}  {e['size']:>10}  {e['hdr'] + e['clen']:>8}  {e['hdr']:>8}   verify-pack: {v[1]} {v[2]} {v[3]}" + (f" depth={v[5]}" if len(v) > 5 else ''))
print('== 三:OFS_DELTA:头部后面是“到基础对象的向后偏移量”,基础可以是 blob 或别的 delta')
for e in ents:
    if e['type'] == 6:
        print(f"  偏移 {e['off']} 的 ofs-delta → 基础对象在偏移 {e['base']}(向后 {e['off'] - e['base']} 字节)")
head_sha = out1(d, 'git rev-parse HEAD:doc.txt')
base_sha = next(vp[e['off']][0] for e in ents if e['type'] == 3)
print(f'  完整存放的那个 blob 是不是最新版本(HEAD:doc.txt): {base_sha == head_sha}')
print('== 四:解开一个 delta:源长度、目标长度,然后是 copy / insert 指令,应用后 sha 与 verify-pack 一致')
byoff = {e['off']: e for e in ents}
def resolve(e):
    if e['type'] < 5: return PTYPES[e['type']], e['raw']
    bt, bd = resolve(byoff[e['base']]); return bt, apply_delta(bd, e['raw'])[0]
shown = 0
for e in ents:
    if e['type'] == 6 and shown < 1:
        bt, bd = resolve(byoff[e['base']]); tr = []
        res, s, t = apply_delta(bd, e['raw'], tr); shown += 1
        print(f"  偏移 {e['off']}:delta 本体 {len(e['raw'])} 字节,源 {s} 字节 → 目标 {t} 字节,共 {len(tr)} 条指令")
        for k in tr[:6]:
            print('    ', f'copy 源[{k[1]}:{k[1] + k[2]}] ({k[2]} 字节)' if k[0] == 'copy' else f'insert {k[1]} 字节 {k[2][:24]!r}')
        print(f"    重建出的 {bt} 的 sha = {obj_sha(bt, res)};verify-pack 列出的 = {vp[e['off']][0]}")
ok = all(obj_sha(*resolve(e)) == vp[e['off']][0] for e in ents)
print(f'  全部 {n} 个对象(含 delta)还原后 sha 与 verify-pack 一致: {ok}')
print('== 五:末尾 20 字节是整个 pack 内容的 SHA-1;文件名里的 hash 也是它')
body, trailer = data[:-20], data[-20:]
print('  尾部   :', trailer.hex()); print('  重新算 :', hashlib.sha1(body).hexdigest()); print('  文件名 :', pk.name)
sh(d, f'git verify-pack {pk} && echo verify-pack 通过')
