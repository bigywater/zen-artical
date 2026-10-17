import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f130'); R = {}
import hashlib, timeit, statistics
from werkzeug.security import generate_password_hash, check_password_hash
from argon2 import PasswordHasher
print('== 一:Werkzeug 生成的哈希长什么样:方法、参数、盐、摘要;同一个密码两次结果不同')
h1 = generate_password_hash('correct horse'); h2 = generate_password_hash('correct horse'); print('  默认哈希:', h1[:60] + '…', f'(长度 {len(h1)})'); print('  同一个密码再来一次:', h2[:60] + '…', '| 两次相同吗:', h1 == h2); R['default'] = [h1.split('$')[0], len(h1), h1 == h2]
print('  结构:方法$盐$摘要 →', h1.split('$')[0], '|', f'盐 {len(h1.split("$")[1])} 个字符', '|', f'摘要 {len(h1.split("$")[2])} 个十六进制字符')
print('  check_password_hash 正确/错误:', check_password_hash(h1, 'correct horse'), check_password_hash(h1, 'wrong')); R['check'] = [check_password_hash(h1, 'correct horse'), check_password_hash(h1, 'wrong')]
print()
print('== 二:各种方法与参数的单次耗时(各 5 次中位数):这个耗时就是攻击者每猜一次要付的代价')
rows = {}
def t(fn, n=5): L = []; [fn() for _ in range(1)]; [L.append(timeit.timeit(fn, number=1) * 1000) for _ in range(n)]; return statistics.median(L)
for label, fn in (('pbkdf2:sha256:1000(旧的、太弱)', lambda: generate_password_hash('x', method='pbkdf2:sha256:1000')), ('pbkdf2:sha256:600000', lambda: generate_password_hash('x', method='pbkdf2:sha256:600000')), ('scrypt(Werkzeug 默认 32768:8:1)', lambda: generate_password_hash('x', method='scrypt')), ('scrypt:131072:8:1', lambda: generate_password_hash('x', method='scrypt:131072:8:1')), ('argon2id(argon2-cffi 默认)', lambda: PasswordHasher().hash('x')), ('sha256 一次(错误示范,不要用)', lambda: hashlib.sha256(b'x').hexdigest())):
    rows[label] = t(fn); print(f'  {label:<36} {rows[label]:>10.3f} ms')
R['cost'] = rows
print(f'  差距:scrypt 默认比单次 sha256 慢 {rows["scrypt(Werkzeug 默认 32768:8:1)"] / rows["sha256 一次(错误示范,不要用)"]:.0f} 倍'); 
print()
print('== 三:密码升级:库里还有旧的弱哈希,用户登录成功时重新哈希并写回')
DB = {'ann': generate_password_hash('pw-ann', method='pbkdf2:sha256:1000'), 'bob': generate_password_hash('pw-bob')}
TARGET = 'scrypt'
def needs_upgrade(h): return not h.startswith(TARGET + ':')
def login(user, pw):
    h = DB[user]
    if not check_password_hash(h, pw): return 'fail'
    if needs_upgrade(h): DB[user] = generate_password_hash(pw); return 'ok(并已升级哈希)'
    return 'ok'
print('  升级前:', {u: h.split('$')[0] for u, h in DB.items()}); R['before'] = {u: h.split('$')[0] for u, h in DB.items()}
print('  ann 用错误的密码登录:', login('ann', 'nope'), '| 哈希仍是', DB['ann'].split('$')[0]); print('  ann 正确登录:', login('ann', 'pw-ann')); print('  ann 再登录一次:', login('ann', 'pw-ann'), '| bob 登录:', login('bob', 'pw-bob'))
print('  升级后:', {u: h.split('$')[0] for u, h in DB.items()}); R['after'] = {u: h.split('$')[0] for u, h in DB.items()}
print('  (没有登录过的用户仍是旧哈希——升级只发生在用户登录、明文密码在手的时候)')
print()
print('== 四:算法参数写在哈希字符串里:提高参数后,旧哈希仍然能验证')
old = generate_password_hash('pw', method='scrypt:16384:8:1'); new = generate_password_hash('pw', method='scrypt:131072:8:1'); print('  旧参数哈希头:', old.split('$')[0], '| 新参数哈希头:', new.split('$')[0]); print('  两者都能用同一个 check_password_hash 验证:', check_password_hash(old, 'pw'), check_password_hash(new, 'pw')); R['params'] = [old.split('$')[0], new.split('$')[0], check_password_hash(old, 'pw'), check_password_hash(new, 'pw')]
print()
print('== 五:比较与长度:超长密码与空密码')
long_pw = 'a' * 100000; t0 = time.perf_counter(); h = generate_password_hash(long_pw); tl_ = ms(t0); print(f'  10 万个字符的密码哈希耗时 {tl_:.1f} ms,哈希长度 {len(h)}'); R['long'] = [tl_, len(h)]
print('  空字符串密码也能哈希并验证:', check_password_hash(generate_password_hash(''), '')); print('  (这次测量里耗时没有随密码长度明显增加,和默认的 65 ms 差不多;是否仍要在应用层限制密码长度,这里没有验证)')
print()
print('== 六:argon2 的哈希形式与验证')
ph = PasswordHasher(); ah = ph.hash('pw'); print('  ', ah[:60] + '…'); print('  验证:', ph.verify(ah, 'pw'), '| check_needs_rehash(默认参数):', ph.check_needs_rehash(ah)); R['argon2'] = [ah.split('$')[1], ph.check_needs_rehash(ah)]
weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash('pw'); print('  用更弱参数生成的哈希,按默认参数 check_needs_rehash →', ph.check_needs_rehash(weak), '(argon2-cffi 自带「是否需要升级」的判断)'); R['argon2_weak'] = ph.check_needs_rehash(weak)
save('f130', R)
