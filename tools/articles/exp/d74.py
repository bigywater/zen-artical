import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d74'); R = {}
apps = ['django.contrib.contenttypes', 'django.contrib.auth']
hashers = ['django.contrib.auth.hashers.PBKDF2PasswordHasher', 'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher', 'django.contrib.auth.hashers.Argon2PasswordHasher', 'django.contrib.auth.hashers.BCryptSHA256PasswordHasher', 'django.contrib.auth.hashers.ScryptPasswordHasher', 'django.contrib.auth.hashers.MD5PasswordHasher']
d = proj('d74', apps=apps, with_lab=False, settings_extra=f"\nPASSWORD_HASHERS = {hashers!r}\n"); manage(d, 'migrate')
def run(code): rc, out = pyscript(d, "import logging, time; logging.disable(logging.CRITICAL)\nfrom django.contrib.auth.hashers import make_password, check_password, get_hasher, identify_hasher\n" + code); return out.rstrip()
print('== 一:默认哈希器与编码后的密码长什么样')
o = run("""
h = make_password('correct horse'); print(h)
parts = h.split('$'); print('算法 =', parts[0], ' 迭代次数 =', parts[1], ' 盐长度 =', len(parts[2]), ' 哈希长度 =', len(parts[3]))
print('同一个密码两次 make_password 结果相同吗:', make_password('correct horse') == h, '(盐每次随机)')
print('未设置的密码 make_password(None) =', make_password(None)[:12] + '…', '(以 ! 开头 = 不可用密码,任何输入都校验失败)')
""")
print(o); R['default'] = o
print()
print('== 二:各哈希器单次 make_password / check_password 的耗时(本机,每种 5 次取中位)')
o = run("""
import statistics
for name in ('pbkdf2_sha256', 'pbkdf2_sha1', 'argon2', 'bcrypt_sha256', 'scrypt', 'md5'):
    h = get_hasher(name); ts = []; ck = []
    for _ in range(5):
        t0 = time.perf_counter(); e = make_password('correct horse', hasher=name); ts.append((time.perf_counter() - t0) * 1000)
        t0 = time.perf_counter(); check_password('correct horse', e); ck.append((time.perf_counter() - t0) * 1000)
    print(f'{name:<14} make {statistics.median(ts):8.1f} ms  check {statistics.median(ck):8.1f} ms   编码前缀:{e[:40]}')
""")
print(o); R['cost'] = o
print()
print('== 三:登录时自动升级旧密码哈希:用旧算法存的密码,校验成功后重新用当前默认算法保存')
o = run("""
from django.contrib.auth.models import User
User.objects.filter(username='u').delete(); u = User(username='u'); u.password = make_password('pw', hasher='md5'); u.save()
print('存的是:', User.objects.get(username='u').password[:20])
from django.contrib.auth import authenticate
r = authenticate(username='u', password='pw'); print('authenticate 成功:', bool(r)); print('之后库里是:', User.objects.get(username='u').password[:28] + '…', ' ← 已升级为默认的 pbkdf2_sha256')
""")
print(o); R['upgrade'] = o
print()
print('== 四:用户名不存在时的耗时:Django 也会跑一次哈希,让「用户不存在」与「密码错」耗时接近(抗计时探测)')
o = run("""
import statistics
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
User.objects.filter(username='u2').delete(); User.objects.create_user('u2', password='pw')
def t(u, p, n=8):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); authenticate(username=u, password=p); ts.append((time.perf_counter() - t0) * 1000)
    return statistics.median(ts)
print('存在的用户 + 错误密码: %.1f ms' % t('u2', 'wrong')); print('不存在的用户:            %.1f ms' % t('nobody', 'wrong')); print('存在的用户 + 正确密码:   %.1f ms' % t('u2', 'pw'))
""")
print(o); R['timing'] = o
print()
print('== 五:密码校验的迭代次数:PBKDF2 迭代次数越高越慢(本机一次 check)')
o = run("""
from django.contrib.auth.hashers import PBKDF2PasswordHasher
import statistics
class H(PBKDF2PasswordHasher):
    iterations = 1
for it in (1, 10000, 100000, 1000000):
    class HH(PBKDF2PasswordHasher): pass
    HH.iterations = it; e = HH().encode('pw', 'salt'); ts = []
    for _ in range(3):
        t0 = time.perf_counter(); HH().verify('pw', e); ts.append((time.perf_counter() - t0) * 1000)
    print(f'iterations={it:>8}  verify 中位 {statistics.median(ts):8.1f} ms')
print('当前默认迭代次数:', get_hasher('pbkdf2_sha256').iterations)
""")
print(o); R['iters'] = o
save('d74', R)
