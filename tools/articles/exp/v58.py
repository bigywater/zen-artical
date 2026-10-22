import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [p for p in sys.path if os.path.basename(p) != 'exp']
from msl import *
import shutil, subprocess as sp, urllib.parse
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
tee('v58'); reset()
print('敏感配置:加密存储与密钥轮换。(一)Nacos 3.2.4(单机,Java 17)默认怎么存密码,改密码、删配置之后旧密码还留在哪里;(二)信封加密(我用 Python cryptography 的 AES-256-GCM 写的几十行,不是任何 KMS 或 Vault)里轮换主密钥和轮换数据密钥各要处理多少数据;(三)双密钥轮换的顺序做错会怎样;(四)进程怎么拿到密钥会不会被 ps 看到(macOS)')
shutil.rmtree(TT / 'nacos_v58', ignore_errors=True)
N = Nacos('v58', 8856, 8857).start(); time.sleep(4)
def pub(did, content):
    s, d = N.http('POST', '/nacos/v3/admin/cs/config', body={'dataId': did, 'groupName': 'DEFAULT_GROUP', 'content': content, 'type': 'text'}, timeout=10.0); assert s == 200, (s, d)
def cur(did):
    s, d = N.http('GET', '/nacos/v3/admin/cs/config', {'dataId': did, 'groupName': 'DEFAULT_GROUP'}, timeout=10.0); j = json.loads(d); return (j['data'] or {}).get('content') if s == 200 and j.get('code') == 0 else f'(HTTP {s})'
def grep(marker, root):
    hits = []; b = marker.encode()
    for p in pathlib.Path(root).rglob('*'):
        if p.is_file():
            try:
                data = p.read_bytes()
                n = data.count(b)
                if n: hits.append((str(p.relative_to(root)), n))
            except Exception: pass
    return hits
def hist_contents(did):
    s, d = N.http('GET', '/nacos/v3/admin/cs/history/list', {'dataId': did, 'groupName': 'DEFAULT_GROUP', 'pageNo': 1, 'pageSize': 50}, timeout=10.0)
    out = []
    for it in json.loads(d)['data']['pageItems']:
        s2, d2 = N.http('GET', '/nacos/v3/admin/cs/history', {'dataId': did, 'groupName': 'DEFAULT_GROUP', 'nid': it['id']}, timeout=10.0); out.append((it['opType'].strip(), json.loads(d2)['data'].get('content')))
    return out

# ============ 一 ============
print('== 一:Nacos 默认怎么存。发布两个配置:plain-db(普通 dataId)和 cipher-aes-db(dataId 带 cipher-aes- 前缀,我印象里 Nacos 用这个前缀去触发加密插件,没有验证);内容里带可以搜索的标记(MARKA 和 MARKB)。取回配置内容,在 Nacos 的数据目录和日志目录里搜这两个标记;然后改成新的值(NEWA / NEWB),再搜旧标记,查历史;最后删除配置,再搜')
A0, B0, A1, B1 = 'MARKA_7f3a91', 'MARKB_9c1d44', 'NEWA_55e2c8', 'NEWB_0b7a3f'
pub('plain-db', f'password={A0}'); pub('cipher-aes-db', f'password={B0}'); time.sleep(1.0)
print(f'  取回:plain-db → {cur("plain-db")!r};cipher-aes-db → {cur("cipher-aes-db")!r}')
plugins = sorted(p.name for p in (N.DIST / 'plugins').glob('*') if 'encrypt' in p.name.lower() or 'cipher' in p.name.lower() or 'kms' in p.name.lower())
print(f'  发行版 plugins 目录里名字带 encrypt / cipher / kms 的文件:{plugins or "没有"}')
def scan(label, markers):
    rows = []
    for m in markers:
        d = grep(m, N.home / 'data'); l = grep(m, N.home / 'logs'); rows.append((label, m, f'{len(d)} 个文件 / {sum(n for _, n in d)} 次' + (f'(如 {d[0][0]})' if d else ''), f'{len(l)} 个文件 / {sum(n for _, n in l)} 次'))
    return rows
rows = scan('发布之后', [A0, B0])
pub('plain-db', f'password={A1}'); pub('cipher-aes-db', f'password={B1}'); time.sleep(1.0)
rows += scan('改成新值之后', [A0, A1, B0, B1])
hp = hist_contents('plain-db'); hc = hist_contents('cipher-aes-db')
s, d = N.http('DELETE', '/nacos/v3/admin/cs/config', {'dataId': 'plain-db', 'groupName': 'DEFAULT_GROUP'}); N.http('DELETE', '/nacos/v3/admin/cs/config', {'dataId': 'cipher-aes-db', 'groupName': 'DEFAULT_GROUP'}); time.sleep(1.0)
rows += scan('删除配置之后', [A0, A1, B0, B1])
table(rows, ['时间点', '搜索的标记', '数据目录(data/)', '日志目录(logs/)'])
print(f'  改成新值之后,plain-db 的历史:{hp};cipher-aes-db 的历史:{hc}')
print(f'  删除之后取 plain-db:{cur("plain-db")}')
N.stop()
print('  搜索的是文件里的原始字节,发布之后约 1 s 就搜了,当时标记已经在 derby-data/log/ 下的文件里;发行版里没有加密插件时,cipher- 前缀的 dataId 和普通 dataId 一样是明文存的')

# ============ 二 ============
print('== 二:信封加密里轮换主密钥要处理多少数据。数据:(a)10000 条各 64 字节的小密文;(b)100 条各 1 MiB 的大密文。三种方案:A 单密钥:所有数据直接用一把密钥 AES-256-GCM 加密,轮换 = 全部解密再用新密钥加密;B 每条记录一个数据密钥(DEK),DEK 被主密钥(KEK)加密后存在记录旁边,轮换 KEK = 把每条记录的 DEK 解开再用新 KEK 包起来;C 每 20 条记录共用一个 DEK,轮换 KEK = 只重新包这些共用 DEK。每种测 3 次取中位数')
def mk(n, size):
    return [os.urandom(size) for _ in range(n)]
def timeit(f, k=3):
    ts = []
    for _ in range(k): t = time.perf_counter(); r = f(); ts.append(time.perf_counter() - t)
    return statistics.median(ts), r
rows = []
for label, n, size in (('(a)10000 条 × 64 B', 10000, 64), ('(b)100 条 × 1 MiB', 100, 1 << 20)):
    data = mk(n, size); k_old, k_new = AESGCM(AESGCM.generate_key(256)), AESGCM(AESGCM.generate_key(256))
    nonce = lambda: os.urandom(12)
    # A
    encA = []
    for p in data: nn = nonce(); encA.append((nn, k_old.encrypt(nn, p, None)))
    def rotA():
        out = []
        for nn, c in encA: pt = k_old.decrypt(nn, c, None); n2 = nonce(); out.append((n2, k_new.encrypt(n2, pt, None)))
        return out
    tA, _ = timeit(rotA)
    # B
    deks = [AESGCM.generate_key(256) for _ in data]; encB = []
    for p, dk in zip(data, deks): nn = nonce(); wn = nonce(); encB.append((wn, k_old.encrypt(wn, dk, None), nn, AESGCM(dk).encrypt(nn, p, None)))
    def rotB():
        out = []
        for wn, wd, nn, c in encB: dk = k_old.decrypt(wn, wd, None); w2 = nonce(); out.append((w2, k_new.encrypt(w2, dk, None), nn, c))
        return out
    tB, _ = timeit(rotB)
    # C
    G = 20; groups = [AESGCM.generate_key(256) for _ in range((n + G - 1) // G)]; wrapC = []
    for dk in groups: wn = nonce(); wrapC.append((wn, k_old.encrypt(wn, dk, None)))
    def rotC():
        out = []
        for wn, wd in wrapC: dk = k_old.decrypt(wn, wd, None); w2 = nonce(); out.append((w2, k_new.encrypt(w2, dk, None)))
        return out
    tC, _ = timeit(rotC)
    rows.append((label, 'A 单密钥(全部重新加密)', n, f'{n * size:,}', f'{tA * 1000:.1f}'))
    rows.append((label, 'B 每条一个 DEK(重新包 DEK)', n, f'{n * 32:,}', f'{tB * 1000:.1f}'))
    rows.append((label, 'C 每 20 条共用一个 DEK', len(groups), f'{len(groups) * 32:,}', f'{tC * 1000:.2f}'))
table(rows, ['数据', '方案', '轮换主密钥要处理的记录数', '要解密再加密的字节数(DEK 按 32 字节算)', '中位用时(ms)'])
print('  单密钥轮换要把所有数据读出来再写回去;信封加密轮换主密钥只处理 DEK,与数据本身多大无关。轮换 DEK 本身(也就是换掉保护数据的那把密钥)仍然要重新加密对应的数据')

# ============ 三 ============
print('== 三:双密钥轮换的顺序。1000 条记录,每条带密钥编号(K1 / K2),读取方有一个“认识哪些密钥”的集合。正确的顺序:(1)读取方先认识 K1 和 K2;(2)写入方改用 K2;(3)后台把 K1 的记录重新加密成 K2;(4)读取方不再认识 K1。出错的两种做法:写入方先改用 K2、读取方还只认识 K1;或者重新加密之前就让读取方忘掉 K1。每个阶段都读全部 1000 条,统计读不出来(解密失败)的记录数')
K = {'K1': AESGCM(AESGCM.generate_key(256)), 'K2': AESGCM(AESGCM.generate_key(256))}
def enc(kid, pt): nn = os.urandom(12); return (kid, nn, K[kid].encrypt(nn, pt, None))
def readable(rec, known):
    kid, nn, c = rec
    if kid not in known: return False
    try: K[kid].decrypt(nn, c, None); return True
    except Exception: return False
def scenario(order):
    recs = [enc('K1', f'secret-{i}'.encode()) for i in range(1000)]; known = {'K1'}; writer = 'K1'; rows = []
    def snap(label): rows.append((label, sum(1 for r in recs if r[0] == 'K1'), sum(1 for r in recs if r[0] == 'K2'), sorted(known), sum(1 for r in recs if not readable(r, known))))
    snap('开始(都是 K1)')
    if order == 'correct':
        known.add('K2'); snap('读取方认识 K1 和 K2'); writer = 'K2'
        for i in range(400): recs.append(enc(writer, f'new-{i}'.encode()))
        snap('写入方改用 K2,又写了 400 条新记录')
        recs = [r if r[0] == 'K2' else enc('K2', f'secret-{j}'.encode()) for j, r in enumerate(recs)]; snap('后台把 K1 记录重新加密成 K2')
        known.discard('K1'); snap('读取方不再认识 K1')
    elif order == 'writer_first':
        writer = 'K2'
        for i in range(400): recs.append(enc(writer, f'new-{i}'.encode()))
        snap('写入方先改用 K2(读取方还只认识 K1),又写了 400 条')
        known.add('K2'); snap('读取方后来也认识了 K2')
    else:
        known.add('K2'); writer = 'K2'
        for i in range(400): recs.append(enc(writer, f'new-{i}'.encode()))
        known.discard('K1'); snap('还没重新加密,读取方就忘掉了 K1')
    return rows
for order, name in (('correct', '正确顺序'), ('writer_first', '出错一:写入方先改用 K2'), ('drop_early', '出错二:重新加密之前忘掉 K1')):
    print(f'  {name}:')
    table(scenario(order), ['阶段', 'K1 记录数', 'K2 记录数', '读取方认识的密钥', '读不出来的记录数'])

# ============ 四 ============
print('== 四:密钥怎么交给进程会不会被 ps 看到(macOS,同一个用户)。起一个子进程,同一份密钥分别通过命令行参数(ARGSECRET)、环境变量(ENVSECRET)和文件(FILESECRET,权限 0600,进程自己读)交给它;用 ps 看这个进程的命令行(ps -o command=)和带环境的输出(ps eww -p PID)里能不能搜到这三个标记')
f = TT / 'v58_secret.txt'; f.write_text('FILESECRET_d41c7e'); os.chmod(f, 0o600)
code = "import sys,time; s=open(sys.argv[2]).read(); time.sleep(20)"
p = sp.Popen([sys.executable, '-c', code, 'ARGSECRET_a93f10', str(f)], env={**os.environ, 'SECRET': 'ENVSECRET_6be2a8'}, stdout=sp.DEVNULL, stderr=sp.DEVNULL); time.sleep(1.0)
o1 = sp.run(['ps', '-o', 'command=', '-p', str(p.pid)], capture_output=True, text=True).stdout
o2 = sp.run(['ps', 'eww', '-p', str(p.pid)], capture_output=True, text=True).stdout
p.kill()
rows = [(m, 'ps -o command=', m in o1) for m in ('ARGSECRET_a93f10', 'ENVSECRET_6be2a8', 'FILESECRET_d41c7e')] + [(m, 'ps eww', m in o2) for m in ('ARGSECRET_a93f10', 'ENVSECRET_6be2a8', 'FILESECRET_d41c7e')]
table([(a, b, '能搜到' if c else '搜不到') for a, b, c in rows], ['标记(交给进程的方式)', 'ps 的输出', '结果'])
print(f'  文件权限:{oct(os.stat(f).st_mode & 0o777)}。命令行参数用普通的 ps 就能看到,环境变量在 ps eww 里能看到(这里都是同一个用户,别的用户能不能看到我没有测);文件里的内容 ps 看不到,由文件权限保护')
print('ERRORS', dict(ERRORS))
