import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f38'); R = {}
import io, uuid, tempfile
from werkzeug.utils import secure_filename
from werkzeug.security import safe_join
from werkzeug.datastructures import FileStorage
print('== 一:secure_filename 对各种输入的结果')
cases = ['report.pdf', 'my report 2024.pdf', '../../etc/passwd', '..\\..\\windows\\system32\\cmd.exe', '/absolute/path/x.txt', '.htaccess', '..hidden', 'a/b/c.txt', '中文报告.docx', 'résumé.pdf', 'file name (1).txt', 'a\x00b.txt', 'a\nb.txt', 'CON', 'con.txt', 'NUL.txt', 'AUX', 'COM1.txt', 'LPT1', '   .txt  ', 'x' * 300 + '.txt', '', '...', '.', 'tar.gz', 'a.tar.gz', '版本.v2.txt', 'emoji😀.png', '$HOME/x', 'name;rm -rf.txt']
R['rows'] = {}
print(f'  {"输入":<36} → 输出')
for s in cases:
    out = secure_filename(s); R['rows'][s if len(s) < 40 else s[:20] + '…(%d 字符)' % len(s)] = out; print(f'  {s!r:<36}'[:40] + f' → {out[:60]!r}' + (f'(长度 {len(out)})' if len(out) > 60 else ''))
print()
print('== 二:中文文件名被整个去掉了——只剩扩展名:要保留原文件名时要自己处理')
for s in ('中文报告.docx', '中文', '你好.txt'): print(f'  secure_filename({s!r}) → {secure_filename(s)!r}')
R['cn'] = {s: secure_filename(s) for s in ('中文报告.docx', '中文', '你好.txt')}
print()
print('== 三:不清洗的危险演示(只在本机临时目录里):用客户端给的 filename 直接拼路径,../ 可以写到上传目录之外')
base = FT / 'f38'; shutil.rmtree(base, ignore_errors=True); up = base / 'uploads'; up.mkdir(parents=True)
for evil in ('../escaped.txt', '../../escaped2.txt'):
    fs = FileStorage(io.BytesIO(b'PWNED'), filename=evil); dest = os.path.join(up, fs.filename); fs.save(dest); print(f'  filename={evil!r} → 实际写入 {tidy(str(os.path.realpath(dest)))}(是否在上传目录里面:{str(os.path.realpath(dest)).startswith(str(os.path.realpath(up)) + os.sep)})'); R.setdefault('evil', {})[evil] = str(os.path.realpath(dest)).startswith(str(os.path.realpath(up)) + os.sep)
print('  上传目录之外多出的文件:', sorted(p.name for p in base.iterdir() if p.is_file()))
R['escaped'] = sorted(p.name for p in base.iterdir() if p.is_file())
print()
print('== 四:用 secure_filename 之后,拼出来的路径是否始终在上传目录内(用上面所有输入、再加一批随机字符串做模糊测试)')
import random, string
random.seed(7); fuzz = [''.join(random.choice(string.printable + '中文é/\\.') for _ in range(random.randint(1, 40))) for _ in range(20000)]
bad = []
for s in cases + fuzz:
    n = secure_filename(s)
    if not n: continue
    p = os.path.realpath(os.path.join(up, n))
    if not p.startswith(str(os.path.realpath(up)) + os.sep): bad.append(s)
print(f'  测试 {len(cases) + len(fuzz)} 个输入(其中 {sum(1 for s in cases + fuzz if not secure_filename(s))} 个清洗后为空串),越出上传目录的有 {len(bad)} 个'); R['fuzz'] = [len(cases) + len(fuzz), sum(1 for s in cases + fuzz if not secure_filename(s)), len(bad)]
print()
print('== 五:清洗后可能为空;可能重名;Windows 保留名:常见的处理——空则用随机名,总是加随机前缀,保留扩展名白名单')
def safe_name(orig, allowed=('png', 'jpg', 'pdf', 'txt')):
    n = secure_filename(orig); ext = n.rsplit('.', 1)[1].lower() if '.' in n else ''
    if ext not in allowed: return None
    return f'{uuid.uuid4().hex[:12]}.{ext}'
for s in ('photo.PNG', 'a.exe', '中文.jpg', 'noext', '../x.pdf', 'archive.tar.gz'): print(f'  safe_name({s!r:<18}) → {safe_name(s)!r}'); R.setdefault('safe_name', {})[s] = None if safe_name(s) is None else 'xxxxxxxxxxxx.' + safe_name(s).split('.')[1]
print()
print('== 六:werkzeug.security.safe_join:把「目录 + 不可信路径」拼起来,逃出目录时返回 None')
for part in ('a.txt', 'sub/a.txt', '../x', '/etc/passwd', 'sub/../../x', 'a/../a.txt', ''): print(f'  safe_join(上传目录, {part!r:<16}) →', repr(safe_join(str(up), part)).replace(str(up), '<uploads>')); R.setdefault('safe_join', {})[part] = (safe_join(str(up), part) or '').replace(str(up), '<uploads>') or None
save('f38', R)
