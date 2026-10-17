import os, sys, subprocess, tempfile, textwrap, json, time

HERE = os.environ['HERE']; W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W)
PY = HERE + '/venv/bin/python'
E = dict(os.environ); E.pop('HTTP_PROXY', None); E.pop('HTTPS_PROXY', None)
def w(path, body): open(path, 'w').write(textwrap.dedent(body).lstrip())
def run(args, **kw):
    r = subprocess.run([PY, *args], capture_output=True, text=True, env=E, cwd=W, **kw); return (r.stdout + r.stderr).strip().replace(W + '/', '')

w('rle.py', '''
    def rle_encode(s):
        out = []; i = 0
        while i < len(s):
            j = i
            while j < len(s) and s[j] == s[i]: j += 1
            out.append(f"{j - i}{s[i]}"); i = j
        return "".join(out)

    def rle_decode(t):
        out = []; num = ""
        for ch in t:
            if ch.isdigit(): num += ch
            else: out.append(ch * int(num)); num = ""
        return "".join(out)
''')
w('test_examples.py', '''
    from rle import rle_encode, rle_decode
    def test_examples():
        for s in ["aaabcc", "", "abc", "zzzz", "xyzzy", "hello world", "aabbcc"]:
            assert rle_decode(rle_encode(s)) == s
''')
print("pytest", run(['-m', 'pytest', '--version']).splitlines()[0], "| hypothesis", run(['-c', 'import hypothesis; print(hypothesis.__version__)']))
print("\n== 一、手写的 7 个例子: 全部通过 ==")
print(run(['-m', 'pytest', '-p', 'no:cacheprovider', '-q', '--no-header', 'test_examples.py']).splitlines()[-1])

w('prop.py', '''
    import json, sys
    from hypothesis import given, settings, strategies as st, Phase
    from rle import rle_encode, rle_decode

    seen = []          # 每次 property 被调用时的输入
    failing = []       # 其中导致失败的输入

    @settings(database=None, derandomize=True, max_examples=200, deadline=None)
    @given(st.text(max_size=30))
    def prop(s):
        seen.append(s)
        try:
            assert rle_decode(rle_encode(s)) == s
        except AssertionError:
            failing.append(s); raise

    try:
        prop()
        print("没有发现反例")
    except AssertionError as e:
        print("Hypothesis 报告失败。最终(最小)反例 =", repr(failing[-1]))
        notes = getattr(e, "__notes__", [])
        for n in notes: print("  note:", n)
    print(f"property 被调用了 {len(seen)} 次; 其中失败 {len(failing)} 次")
    print("被调用的前 12 个输入:", [s for s in seen[:12]])
    print("首次失败的输入:", repr(failing[0]), "(长度 %d)" % len(failing[0]))
    print("缩小(shrinking)过程中依次出现的失败输入(去重, 按出现顺序):")
    uniq = []
    for f in failing:
        if f not in uniq: uniq.append(f)
    for f in uniq: print("   ", repr(f), "长度", len(f))
    json.dump({"seen": seen[:12], "uniq": uniq, "calls": len(seen), "fails": len(failing)}, open("prop.json", "w"), ensure_ascii=False)
''')
print("\n== 二、property: decode(encode(s)) == s, 输入是任意文本 ==")
print(run(['prop.py']))
d = json.load(open('prop.json')); json.dump(d, open(HERE + '/out/99.json', 'w'), ensure_ascii=False)

print("\n== 三、第一次「修复」: 只排除 Unicode 类别 Nd(十进制数字)的字符 ==")
w('prop2.py', '''
    from hypothesis import given, settings, strategies as st
    from rle import rle_encode, rle_decode
    calls = [0]
    @settings(database=None, derandomize=True, max_examples=200, deadline=None)
    @given(st.text(alphabet=st.characters(exclude_categories=("Nd", "Cs")), max_size=30))
    def prop(s):
        calls[0] += 1
        assert rle_decode(rle_encode(s)) == s
    try: prop(); print("全部通过", calls[0])
    except BaseException as e:
        subs = getattr(e, "exceptions", [e])
        print("Hypothesis 发现", len(subs), "种不同的失败:")
        for x in subs:
            notes = " ".join(getattr(x, "__notes__", [])).replace("\\n", " ")
            print("   ", type(x).__name__ + ":", str(x)[:60], "|", " ".join(notes.split())[:60])
        print("   调用次数", calls[0])
    print("  '²'.isdigit() =", "²".isdigit(), "| unicodedata.category('²') =", __import__("unicodedata").category("²"), "| '²'.isdecimal() =", "²".isdecimal())
''')
print(run(['prop2.py']))
print("\n== 三·补、第二次修复: 用 str.isdigit 本身当过滤条件 ==")
w('prop2b.py', '''
    from hypothesis import given, settings, strategies as st
    from rle import rle_encode, rle_decode
    calls = [0]
    @settings(database=None, derandomize=True, max_examples=300, deadline=None)
    @given(st.text(max_size=30).filter(lambda s: not any(c.isdigit() for c in s)))
    def prop(s):
        calls[0] += 1
        assert rle_decode(rle_encode(s)) == s
    prop(); print("  过滤掉所有 isdigit() 为真的字符后,", calls[0], "个随机输入全部通过")
''')
print(run(['prop2b.py']))

print("\n== 四、失败例子会被记住(.hypothesis/examples 数据库) ==")
w('prop3.py', '''
    import time
    from hypothesis import given, settings, strategies as st
    from rle import rle_encode, rle_decode
    calls = [0]
    @settings(max_examples=200, deadline=None)      # 使用默认数据库(当前目录 .hypothesis)
    @given(st.text(max_size=30))
    def prop(s):
        calls[0] += 1
        assert rle_decode(rle_encode(s)) == s
    try: prop()
    except BaseException as e: print("  失败:", type(e).__name__)
    print("  本次运行 property 被调用", calls[0], "次")
''')
for k in (1, 2):
    print(f"第 {k} 次运行:"); print(run(['prop3.py']))
print("  .hypothesis 目录里:", sorted(os.listdir('.hypothesis')))
print("\n== 五、随机输入的分布: 会主动试边界 ==")
w('prop4.py', '''
    from hypothesis import given, settings, strategies as st
    import collections
    seen = []
    @settings(database=None, derandomize=True, max_examples=100, deadline=None)
    @given(st.integers())
    def p(n): seen.append(n)
    p()
    print("  st.integers() 100 个样本里: 0 出现", seen.count(0), "次; 绝对值 < 10 的占", sum(abs(x) < 10 for x in seen), "个; 超过 2**32 的占", sum(abs(x) > 2**32 for x in seen), "个; 最大 =", max(seen), "最小 =", min(seen))
    seen.clear()
    @settings(database=None, derandomize=True, max_examples=100, deadline=None)
    @given(st.text(max_size=10))
    def q(s): seen.append(s)
    q()
    print("  st.text() 100 个样本里: 空串", seen.count(""), "个; 含非 ASCII 的", sum(any(ord(c) > 127 for c in s) for s in seen), "个; 含数字字符的", sum(any(c.isdigit() for c in s) for s in seen), "个")
''')
print(run(['prop4.py']))
