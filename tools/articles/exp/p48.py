import sys, os, re, unicodedata as ud; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import lxml.html
tee('p48')
print(f'(Python {sys.version.split()[0]},unicodedata 的 Unicode 版本 {ud.unidata_version})')
print('== 一:看起来像"空格"的字符,Python 的 str.strip()、str.split()、正则 \\s 各把谁当空白')
CH = [('普通空格', ' '), ('制表符', '\t'), ('换行', '\n'), ('不间断空格 nbsp', '\xa0'), ('全角空格(表意文字空格)', '　'), ('细空格 U+2009', ' '), ('窄不间断空格 U+202F', ' '),
      ('零宽空格 U+200B', '​'), ('零宽不连字 U+200C', '‌'), ('零宽连字 U+200D', '‍'), ('字节顺序标记/零宽不换行 U+FEFF', '﻿'), ('软连字符 U+00AD', '­'), ('左到右标记 U+200E', '‎'), ('单词连接符 U+2060', '⁠')]
print(f'  {"字符":<30}{"类别":>5}{"isspace":>9}{"strip 去掉":>10}{"split 当分隔":>12}{r"\s 匹配":>8}   显示')
for name, c in CH:
    cat = ud.category(c)
    print(f'  {name:<26}{cat:>5}{str(c.isspace()):>9}{str("a" + c + "b" == ("a" + c + "b").strip() and "否" or "是") if False else str(("x" + c).strip() == "x" and "是" or "否"):>10}{str(len(("a" + c + "b").split()) == 2 and "是" or "否"):>12}{str(bool(re.fullmatch(r"\s", c)) and "是" or "否"):>8}   U+{ord(c):04X}')
s = 'Price:\xa0¥100​ 　 ok﻿'
print(f'  例:{s!r}.strip() = {s.strip()!r};.split() = {s.split()!r}——零宽空格和 BOM 留在了结果里,看不见但存在')
print('== 二:全角/半角与 NFKC 规范化:好处与副作用')
samples = ['１２３ＡＢＣ，．', 'ｱｲｳ（ﾊﾝｶｸ）', '㈱テスト', '①②③', 'x²+y³', 'ﬁle ﬂow', '™ ® ©', '１２，３４５．６７円', '“引号”‘单引号’', '…', '——', '～', '‐ – — −']
for sx in samples:
    n = ud.normalize('NFKC', sx); print(f'  {sx!r:<22}→ NFKC {n!r:<22}{"(有变化)" if n != sx else "(不变)"}')
print('  注意:NFKC 把 "x²+y³" 变成 "x2+y3"(数学含义变了)、把 "①" 变成 "1"、把 "ﬁ" 变成 "fi"、把 "™" 变成 "TM";中文引号、省略号、破折号等有的变有的不变——不要无脑对全文做 NFKC')
print('  中文标点 NFKC 之后:' + ' '.join(f'{c}→{ud.normalize("NFKC", c)}' for c in '，。！？：；（）【】、'))
print('== 三:NFC 与 NFD:看起来相同的字符串,比较时不相等')
a, b = 'café', 'café'
print(f'  {a!r} 与 {b!r}:显示都是 café;==:{a == b};len:{len(a)} 和 {len(b)};NFC 之后相等:{ud.normalize("NFC", a) == ud.normalize("NFC", b)}')
h1, h2 = '한글', ud.normalize('NFD', '한글')
print(f'  韩文 "한글":NFC len={len(h1)},NFD len={len(h2)},==:{h1 == h2},NFC 之后相等:{ud.normalize("NFC", h2) == h1}')
print(f'  去重集合:{{a, b}} 的大小 = {len({a, b})};规范化后 = {len({ud.normalize("NFC", a), ud.normalize("NFC", b)})}')
print('== 四:数字与价格解析的坑')
for t in ('１２３', '１２．５', '١٢٣', '123', '1,234.56', '１，２３４．５６', '1 234,56', '¥100', '￥100', '１００円', '12.5万'):
    try: iv = int(t)
    except Exception as e: iv = f'{type(e).__name__}'
    try: fv = float(t)
    except Exception as e: fv = f'{type(e).__name__}'
    print(f'  {t!r:<14}int() = {str(iv):<12}float() = {str(fv):<12}NFKC 后 {ud.normalize("NFKC", t)!r}')
print('== 五:从 HTML 取文本:text_content()、itertext()、xpath string() 的差别,以及一个清洗函数')
HTML = '<div class="p"> Price:&nbsp;<b>¥１２，３４５</b><br>half​width ｱｲｳ\n   next&#8203;line&emsp;ok <span>a</span><span>b</span></div>'
el = lxml.html.fromstring(HTML)
print(f'  原始 HTML:{HTML!r}')
print(f'  text_content():{el.text_content()!r}')
print(f'  "".join(itertext()):{"".join(el.itertext())!r}')
print(f'  xpath string():{el.xpath("string(.)")!r}')
print(f'  " ".join(itertext()):{" ".join(el.itertext())!r}')
ZW = dict.fromkeys(map(ord, '​‌‍⁠﻿­‎‏'), None)
def clean(t):
    t = ud.normalize('NFKC', t).translate(ZW)         # 全角转半角(只对要做的字段),去零宽/软连字符/方向标记
    return re.sub(r'\s+', ' ', t).strip()               # 把各种空白(含 nbsp、全角空格)折叠成一个普通空格
print(f'  clean(text_content()):{clean(el.text_content())!r}')
print(f'  clean(" ".join(itertext())):{clean(" ".join(el.itertext()))!r}')
price = re.search(r'¥\s*([\d,]+)', clean(el.text_content())); print(f'  从清洗后的文本里取价格:{price.group(1) if price else None} → {int(price.group(1).replace(",", "")) if price else None}')
raw = re.search(r'¥\s*([\d,]+)', el.text_content()); print(f'  不清洗直接用同一个正则:匹配到 {raw.group(1)!r}——Python 的 \\d 匹配全角数字,但全角逗号 "，" 不在 [\\d,] 里,价格被截断;int({raw.group(1)!r}) = {int(raw.group(1))},静默得到了错误的 12 而不是 12345')
purge()
