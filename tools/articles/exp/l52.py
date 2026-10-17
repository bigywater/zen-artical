import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l52')
P = '''def calculate_total_price(items):
    total = sum(item.price for item in items)
    return total
'''
Q = '''def collect_user_names(users):
    names = [user.name for user in users]
    return sorted(names)
'''
SH = '''def short(a):
    return a
'''
FA = P + '\n' + Q + '\n' + SH
FB = '''def format_report_header(title):
    return "== " + title.upper() + " =="
'''
def authors(d, opt, f):
    o = out1(d, f'git blame {opt} --line-porcelain -- {f}')
    res = []
    for l in o.split('\n'):
        if l.startswith('author '): res.append(l[7:])
    return res
def show(d, opt, f, lines):
    code = out1(d, f'git show HEAD:{f}').split('\n'); a = authors(d, opt, f)
    for i, (c, who) in enumerate(zip(code, a), 1):
        if c.strip() and i in lines: print(f'    {who:<6}| {c}')
print('== 一:历史:Alice 写了 P(calculate_total_price)、Q(collect_user_names)和 short;Bob 先交换 P 与 Q 的位置,再把 short 挪到文件开头;Carol 把 P 搬进 b.py')
d = lab('l52')
ci(d, 'Alice 写了三个函数', {'a.py': FA}, t=0, who='Alice')
ci(d, 'Bob 交换 P 与 Q', {'a.py': Q + '\n' + P + '\n' + SH}, t=1, who='Bob')
ci(d, 'Bob 把 short 挪到开头', {'a.py': SH + '\n' + Q + '\n' + P}, t=2, who='Bob')
d2 = lab('l52b'); [ci(d2, m, f, t=i, who=w) for i, (m, f, w) in enumerate([('Alice 写了三个函数', {'a.py': FA}, 'Alice'), ('Bob 交换 P 与 Q', {'a.py': Q + '\n' + P + '\n' + SH}, 'Bob'), ('Bob 把 short 挪到开头', {'a.py': SH + '\n' + Q + '\n' + P}, 'Bob')])]
ci(d, 'Carol 把 P 搬到 b.py', {'a.py': SH + '\n' + Q, 'b.py': P + '\n' + FB}, t=3, who='Carol')
sh(d, "git log --format='%an: %s' --reverse")
print('  现在 a.py 与 b.py 的内容:'); sh(d, 'cat a.py; echo ------; cat b.py')
print('== 二:默认的 git blame:被挪动的行全算在“挪动者”名下')
print('  b.py(Carol 搬来的函数 P):'); show(d, '', 'b.py', range(1, 4))
print('  a.py(Bob 交换并挪动过的):'); show(d, '', 'a.py', range(1, 9))
print('== 三:-M:同一个文件里移动的行,追到原作者——但每行至少要有 20 个字母数字字符')
print('  [默认] Bob 的两个提交之后的 a.py(P 被 Bob 挪到了最后):'); show(d2, '', 'a.py', range(1, 11))
print('  [-M]:'); show(d2, '-M', 'a.py', range(1, 11))
print('  → 长函数 P、Q 的各行(≥ 20 个字母数字)被追到 Alice;短函数 short 的两行(不到 20 个字母数字)仍算 Bob')
print('  降低阈值:-M5 让短的行也能追上:'); show(d2, '-M5', 'a.py', range(1, 3))
print('== 四:-C:跨文件。Carol 把函数从 a.py 搬到 b.py,默认算 Carol;-C 在“同一个提交修改的其它文件”里找来源')
print('  [默认] b.py:'); show(d, '', 'b.py', range(1, 4))
print('  [-C]  :'); show(d, '-C', 'b.py', range(1, 4))
print('  [-M]  (-M 只在同一文件里找,对跨文件没用):'); show(d, '-M', 'b.py', range(1, 4))
print('  b.py 里 Carol 自己写的 format_report_header 还是 Carol:'); show(d, '-C', 'b.py', range(5, 7))
print('== 五:-C 的三个层级:-C 只在同一提交里被修改的文件中找;-C -C 也找这个提交里新建的文件;-C -C -C 找任何提交里的任何文件')
d3 = lab('l52c'); ci(d3, 'Alice 写了 a.py', {'a.py': FA}, t=0, who='Alice')
ci(d3, 'Carol 新建 b.py(拷贝了 calculate_total_price,a.py 没改)', {'b.py': FA.split('\n\n')[0] + '\n'}, t=1, who='Carol')
for opt in ['', '-C', '-C -C', '-C -C -C']:
    a = authors(d3, opt, 'b.py'); print(f'  git blame {opt:<9} b.py → ' + ', '.join(sorted(set(a))))
print('  (这个提交只新建了 b.py,没有修改 a.py:-C 只在“同一提交里被修改的文件”里找,找不到;-C -C 才会去别的文件里找)')
print('== 六:格式化提交会“偷走”整个文件的 blame:--ignore-rev / .git-blame-ignore-revs')
d4 = lab('l52d'); ci(d4, 'Alice 写代码', {'c.py': 'def f():\n  return 1\n\ndef g():\n  return 2\n'}, t=0, who='Alice')
fm = ci(d4, 'Bob 统一缩进(格式化)', {'c.py': 'def f():\n    return 1\n\ndef g():\n    return 2\n'}, t=1, who='Bob')
print('  默认:', ', '.join(f'{x}' for x in authors(d4, '', 'c.py')))
print('  --ignore-rev:', ', '.join(authors(d4, f'--ignore-rev {fm}', 'c.py')))
(d4 / '.git-blame-ignore-revs').write_text(f'# 统一缩进\n{fm}\n'); run(d4, 'git config blame.ignoreRevsFile .git-blame-ignore-revs')
print('  配置 blame.ignoreRevsFile 之后(不用每次传参数):', ', '.join(authors(d4, '', 'c.py')))
