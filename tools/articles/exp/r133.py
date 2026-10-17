import sys, time, os, json, re, glob, subprocess, shutil, hashlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rl
from rl import *
tee('r133'); R = {}
def has(path, needle):
    d = open(path, 'rb').read() if not isinstance(path, bytes) else path
    return needle.encode() in d
def sh_(cmd, **kw): return subprocess.run(cmd, capture_output=True, text=True, timeout=120, **kw)
n = Node(9210, name='s133', conf={'appendonly': 'yes', 'appendfsync': 'always', 'aclfile': str(RDATA / 's133' / 'users.acl')}); (n.dir / 'users.acl').write_text(''); n.start(); a = n.c()
SECRET = 'token=abc123-SECRET'
long_val = 'CARDNUM-MARKER;' * 400
a.do('SET', 'session:1001', SECRET); a.do('SET', 'user:1', long_val); a.do('SET', 'app:cfg', 'short'); a.pipeline([['SET', f'bulk:{i}', 'v' * 40 + str(i)] for i in range(3000)])
a.do('EVAL', "redis.call('SET', KEYS[1], 'from-script') -- SCRIPT_BODY_MARKER_XYZ", 1, 'script:key')
a.do('ACL', 'SETUSER', 'svc', 'on', '>hunter2-pass', '~app:*', '+get'); a.do('ACL', 'SAVE')
a.do('SAVE'); a.do('BGREWRITEAOF'); time.sleep(1.5)
rdb = n.dir / 'dump.rdb'; aofs = sorted(glob.glob(str(n.dir / 'appendonlydir' / '*')))
print('== 一:RDB 和 AOF 里的内容是不是明文(用 Python 直接在文件字节里查找,相当于 strings | grep)')
rows = [('短字符串 value  "token=abc123-SECRET"', SECRET), ('key 名 "session:1001"', 'session:1001'), ('长且重复的 value 里的标记 "CARDNUM-MARKER"', 'CARDNUM-MARKER'), ('ACL 用户密码明文 "hunter2-pass"', 'hunter2-pass'), ('该密码的 sha256 哈希', hashlib.sha256(b'hunter2-pass').hexdigest()), ('Lua 脚本正文里的注释 "SCRIPT_BODY_MARKER_XYZ"', 'SCRIPT_BODY_MARKER_XYZ'), ('脚本产生的 value "from-script"', 'from-script')]
aofall = b''.join(open(f, 'rb').read() for f in aofs)
print(f'  {"在文件里找":<48}{"dump.rdb":>10}{"AOF 全部":>10}')
R['scan'] = {}
for label, needle in rows:
    r1 = needle.encode() in open(rdb, 'rb').read(); r2 = needle.encode() in aofall
    R['scan'][label] = [r1, r2]; print(f'  {label:<48}{"找到" if r1 else "没有":>10}{"找到" if r2 else "没有":>10}')
sz_yes = rdb.stat().st_size
a.do('CONFIG', 'SET', 'rdbcompression', 'no'); a.do('SAVE'); sz_no = rdb.stat().st_size; r3 = b'CARDNUM-MARKER' in open(rdb, 'rb').read()
print(f'  user:1 的 value 是 "CARDNUM-MARKER;" 重复 400 次(共 {len(long_val)} 字节)。dump.rdb 大小:rdbcompression yes {sz_yes} 字节,no {sz_no} 字节;关掉压缩后标记 {"找到" if r3 else "没有"}')
R['compress'] = dict(yes=sz_yes, no=sz_no, marker_in_yes=R['scan']['长且重复的 value 里的标记 "CARDNUM-MARKER"'][0], value_len=len(long_val))
print('  也就是说:压缩让文件变小,但压缩流里第一份原文仍是明文,压缩不是保护。')
a.do('CONFIG', 'SET', 'rdbcompression', 'yes'); a.do('SAVE')
cr_ = sh_(['redis-check-rdb', str(rdb)]); print('  redis-check-rdb 校验原文件:returncode', cr_.returncode, '|', [l.strip() for l in cr_.stdout.splitlines() if 'OK' in l or 'rror' in l][:2]); R['check_ok'] = [cr_.returncode, [l.strip() for l in cr_.stdout.splitlines() if 'OK' in l or 'rror' in l][:2]]
print()
print('== 二:谁能从网络上把整份数据拉走?redis-cli --rdb(走复制协议)')
a.do('ACL', 'SETUSER', 'app', 'on', '>ap', '~app:*', '-@all', '+get', '+set')
a.do('ACL', 'SETUSER', 'repl', 'on', '>rp', '~app:*', '-@all', '+psync', '+sync', '+replconf', '+ping')
R['rdbpull'] = {}
for user, pw in (('app', 'ap'), ('repl', 'rp')):
    out = RDATA / f's133_{user}.rdb'
    if out.exists(): out.unlink()
    r = sh_(['redis-cli', '-p', '9210', '--user', user, '--pass', pw, '--no-auth-warning', '--rdb', str(out)])
    msg = (r.stdout + r.stderr).strip().replace('\n', ' / ')[:170]
    got = out.exists() and out.stat().st_size > 0
    has_secret = got and SECRET.encode() in out.read_bytes()
    print(f'  用户 {user}(ACL: {"~app:* +get +set" if user == "app" else "~app:* -@all +psync +sync +replconf +ping"})→ 输出:{msg}')
    print(f'    拿到 RDB 文件:{got};文件里含 app:* 以外的 key/value(session:1001 的 token):{has_secret}')
    R['rdbpull'][user] = dict(msg=msg, got=got, leaked=has_secret)
print()
print('== 三:备份加密:openssl enc AES-256-CBC + pbkdf2;加密后能不能找到,解密回来是否一致,篡改会怎样')
enc = RDATA / 's133.enc'; dec = RDATA / 's133.dec'; PW = 'backup-pass-123'
t0 = time.perf_counter(); r = sh_(['openssl', 'enc', '-aes-256-cbc', '-pbkdf2', '-salt', '-pass', f'pass:{PW}', '-in', str(rdb), '-out', str(enc)]); te = time.perf_counter() - t0
print(f'  加密 dump.rdb({rdb.stat().st_size} 字节)→ {enc.stat().st_size} 字节,用时 {te*1000:.0f} ms;returncode={r.returncode}')
data = enc.read_bytes(); print('  加密文件里能找到 key 名 / value / 标记吗:', {k: (k.encode() in data) for k in ('session:1001', 'abc123-SECRET')})
R['enc'] = dict(size_in=rdb.stat().st_size, size_out=enc.stat().st_size, ms=te * 1000, found=[(k.encode() in data) for k in ('session:1001', 'abc123-SECRET')])
r = sh_(['openssl', 'enc', '-d', '-aes-256-cbc', '-pbkdf2', '-pass', f'pass:{PW}', '-in', str(enc), '-out', str(dec)])
same = dec.read_bytes() == rdb.read_bytes(); print('  用对的密码解密,与原文件逐字节相同:', same); R['roundtrip'] = same
r = sh_(['openssl', 'enc', '-d', '-aes-256-cbc', '-pbkdf2', '-pass', 'pass:wrong', '-in', str(enc), '-out', str(dec) + '.bad']); print('  用错的密码解密:returncode', r.returncode, (r.stderr.strip()[:80])); R['wrongpw'] = [r.returncode, r.stderr.strip()[:80]]
bad = bytearray(data); mid = len(bad) // 2; bad[mid] ^= 0x01; (RDATA / 's133.tamper').write_bytes(bytes(bad))
r = sh_(['openssl', 'enc', '-d', '-aes-256-cbc', '-pbkdf2', '-pass', f'pass:{PW}', '-in', str(RDATA / 's133.tamper'), '-out', str(dec) + '.tam'])
print('  密文中间翻转 1 个比特后解密:returncode', r.returncode, '(解密本身有没有报错)'); R['tamper_rc'] = r.returncode
c = sh_(['redis-check-rdb', str(dec) + '.tam']); ls_ = [l.strip() for l in (c.stdout + c.stderr).splitlines() if any(k in l for k in ('rror', 'OK', 'CRC', 'checksum', 'Wrong', 'wrong', 'nvalid', 'ERR'))][:4]; print('  对被篡改后解出的文件运行 redis-check-rdb:returncode', c.returncode, '|', ls_); R['tamper_check'] = [c.returncode, ls_]
same2 = (RDATA / 's133.dec.tam').read_bytes() == rdb.read_bytes(); diff = sum(1 for x, y in zip((RDATA / 's133.dec.tam').read_bytes(), rdb.read_bytes()) if x != y); print(f'  被篡改解出的文件与原文件相同:{same2};不同的字节数 {diff}(共 {rdb.stat().st_size} 字节)'); R['tamper_diff'] = diff
save('r133', R); cleanup([n])
