import sys, os, subprocess, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
tee('e2')
P = products(); T = timeseries()
zs = lambda b, lv=3: len(zstandard.ZstdCompressor(level=lv).compress(b))
print('== 一:一条 products 记录的 JSON 字节是怎么构成的(2 万条,紧凑 JSON Lines,逐个记号统计)')
def tok_stats(o, acc):
    if isinstance(o, dict):
        acc['结构标点'] += 2 + max(0, len(o) - 1) + len(o)           # {} 逗号 冒号
        for k, v in o.items(): acc['键名(含引号)'] += len(json.dumps(k, ensure_ascii=False).encode()); tok_stats(v, acc)
    elif isinstance(o, list):
        acc['结构标点'] += 2 + max(0, len(o) - 1)
        for v in o: tok_stats(v, acc)
    elif isinstance(o, str): acc['字符串值(含引号)'] += len(json.dumps(o, ensure_ascii=False).encode())
    elif isinstance(o, bool) or o is None: acc['其它'] += len(json.dumps(o))
    else: acc['数字文本'] += len(json.dumps(o))
acc = collections.Counter()
for x in P: tok_stats(x, acc)
total = len(jl(P)) - (len(P) - 1); asum = sum(acc.values())
for k, v in acc.most_common(): print(f'  {k:14s} {v:9d} 字节  {v * 100 / asum:5.1f}%')
print(f'  合计 {asum} 字节,实际 JSON 字节(去掉换行){total};{"相等" if asum == total else "不等,差 " + str(asum - total)};键名在一条记录里占 {acc["键名(含引号)"] / len(P):.0f} 字节,共 {len(P[0]) - 1 + len(P[0]["seller"])} 个键')
print('== 二:数字的文本长度 与 二进制长度(紧凑 JSON 里每个数字占几个字节)')
vals = [x['price'] for x in P]; ints = [x['stock'] for x in P]; ids = [x['id'] for x in P]
for lab, v, binlen in (('price(2 位小数的浮点)', vals, 8), ('stock(0–500 的整数)', ints, 2), ('id(7 位整数)', ids, 4)):
    L = [len(json.dumps(x)) for x in v]; print(f'  {lab:22s} 文本长度:平均 {statistics.mean(L):.2f}、最短 {min(L)}、最长 {max(L)} 字节;二进制(定长 {binlen} 字节)')
tv = [x['value'] for x in T]; print(f'  timeseries 的 value(round(…,3))文本平均 {statistics.mean(len(json.dumps(x)) for x in tv):.2f} 字节,二进制 float64 是 8 字节')
print(f'  Python 的浮点重复表示:json.dumps(0.1 + 0.2) = {json.dumps(0.1 + 0.2)}(17 位);json.dumps(0.1) = {json.dumps(0.1)};json.dumps(1/3) = {json.dumps(1/3)};json.dumps(1e22) = {json.dumps(1e22)};json.dumps(1e-7) = {json.dumps(1e-7)}')
print('== 三:非 ASCII 和转义:同一段文字在 JSON 里占多少字节')
zh = '数据编码与压缩的实验' * 100; em = '😀数据' * 100; esc = ('引号"和反斜杠\\\n换行\t制表' * 100); ctl = ''.join(chr(i) for i in range(1, 32)) * 30
for lab, s in (('中文 1000 字', zh), ('含 emoji(😀 + 2 个汉字)×100', em), ('引号/反斜杠/换行/制表 重复 100 次', esc), ('控制字符 1–31 各 30 次', ctl)):
    a = len(json.dumps(s, ensure_ascii=True).encode()); b = len(json.dumps(s, ensure_ascii=False).encode()); u = len(s.encode())
    print(f'  {lab:32s} UTF-8 原文 {u:5d} 字节;JSON ensure_ascii=False {b:5d} ({b / u:.2f}×);ensure_ascii=True {a:5d} ({a / u:.2f}×)')
print(f'  压缩之后(zstd-3):中文 ensure_ascii=False {zs(json.dumps(zh, ensure_ascii=False).encode())} 字节,ensure_ascii=True {zs(json.dumps(zh).encode())} 字节')
print('== 四:JSON 的类型限制与大整数(Python json、orjson、node 26)')
big = 2 ** 53 + 1
print(f'  Python:json.loads(json.dumps({big})) == {big}:{json.loads(json.dumps(big)) == big}')
r = subprocess.run(['node', '-e', f'const o = JSON.parse(\'{{"id":{big}}}\'); console.log(o.id, o.id === {big}n ? "same" : "differs", JSON.stringify(o))'], capture_output=True, text=True)
print(f'  node 26:JSON.parse(\'{{"id":{big}}}\') 得到 {r.stdout.strip()}')
for lab, o in (('float("nan")', float('nan')), ('float("inf")', float('inf')), ('bytes', b'abc'), ('set', {1, 2}), ('datetime', __import__('datetime').datetime(2026, 10, 12)), ('dict 的整数键 {1: "a"}', {1: 'a'}), ('tuple', (1, 2))):
    try: s1 = json.dumps(o)
    except Exception as e: s1 = f'抛出 {type(e).__name__}'
    try: s2 = orjson.dumps(o).decode()
    except Exception as e: s2 = f'抛出 {type(e).__name__}'
    rn = subprocess.run(['node', '-e', f'try{{JSON.parse({json.dumps(s1)});console.log("可解析")}}catch(e){{console.log("node 解析失败")}}'], capture_output=True, text=True).stdout.strip() if not s1.startswith('抛出') else '-'
    print(f'  {lab:22s} json.dumps → {s1:18s} orjson.dumps → {s2:30s} node 解析 json 的结果:{rn}')
print('== 五:序列化与解析速度(products 2 万条整体作为一个 JSON 数组,7.2 MB;各取 7 次中位数)')
b = json.dumps(P, separators=(',', ':'), ensure_ascii=False).encode(); sz = len(b) / 1048576
for lab, f in (('json.dumps', lambda: json.dumps(P, separators=(',', ':'), ensure_ascii=False)), ('orjson.dumps', lambda: orjson.dumps(P)), ('json.loads', lambda: json.loads(b)), ('orjson.loads', lambda: orjson.loads(b))):
    m, lo, hi = timeit(f, 7); print(f'  {lab:14s} 中位 {m * 1000:6.1f} ms({lo * 1000:.1f}–{hi * 1000:.1f}),{sz / m:7.0f} MiB/s')
print(f'  orjson 的输出和标准库紧凑输出字节相同:{orjson.dumps(P) == b}')
print('== 六:键名重复的代价——同样的数据换三种写法,压缩前后各多大(products 2 万条)')
keys_ = list(P[0].keys())
def short(o, mp):
    if isinstance(o, dict): return {mp.get(k, k): short(v, mp) for k, v in o.items()}
    return o
mp = {'id': 'i', 'url': 'u', 'title': 't', 'price': 'p', 'currency': 'c', 'stock': 's', 'rating': 'r', 'tags': 'g', 'category': 'k', 'updated_at': 'a', 'seller': 'v', 'name': 'n'}
v1 = jl(P); v2 = jl([short(x, mp) for x in P]); v3 = jl([[x[k] for k in keys_] for x in P]) 
print(f'  {"写法":28s} {"原始字节":>9s} {"zstd-3":>9s} {"gzip-6":>9s}')
for lab, v in (('原键名(object)', v1), ('键名缩成 1 个字母', v2), ('每条记录是数组(表头另存)', v3)):
    print(f'  {lab:28s} {len(v):9d} {zs(v):9d} {len(zlib.compress(v, 6)):9d}')
print(f'  原始字节省下:缩短键名 {100 - len(v2) * 100 / len(v1):.1f}%、改数组 {100 - len(v3) * 100 / len(v1):.1f}%;压缩后省下:缩短键名 {100 - zs(v2) * 100 / zs(v1):.1f}%、改数组 {100 - zs(v3) * 100 / zs(v1):.1f}%(zstd-3)')
purge()
