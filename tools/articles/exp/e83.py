import tokenize, io, token, keyword, json, collections

print("== 一、一行代码被切成哪些 token ==")
src = "total = price * 3  # 加税\n"
toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
for t in toks:
    print(f"  {token.tok_name[t.type]:<8} {t.string!r:<10} 起 {t.start} 止 {t.end}")
row1 = [(token.tok_name[t.type], t.string) for t in toks]

print("\n== 二、缩进是 token(INDENT / DEDENT) ==")
src2 = "if x:\n    y = 1\n    if z:\n        w = 2\nv = 3\n"
tk2 = list(tokenize.generate_tokens(io.StringIO(src2).readline))
print("  " + " ".join(f"{token.tok_name[t.type]}" + (f"({t.string.strip()!r})" if t.type in (token.NAME, token.NUMBER, token.OP) else "") for t in tk2))
row2 = [(token.tok_name[t.type], t.string) for t in tk2]

print("\n== 三、tokenize 保留注释,ast 不保留 ==")
print("  COMMENT token:", [t.string for t in toks if t.type == tokenize.COMMENT])
import ast
print("  ast.dump 里能找到注释吗?", "加税" in ast.dump(ast.parse(src)))

print("\n== 四、关键字与名字:tokenize 不区分, 都是 NAME ==")
kw = [(t.string, keyword.iskeyword(t.string)) for t in tokenize.generate_tokens(io.StringIO("def f(x): return None if x else True\n").readline) if t.type == token.NAME]
print("  ", kw)
print("  软关键字(match/case/_/type)也是 NAME:", keyword.softkwlist)

print("\n== 五、f-string 在 3.12+ 会被拆成多个 token ==")
tk5 = list(tokenize.generate_tokens(io.StringIO('f"a{x + 1}b"\n').readline))
print("  ", [(token.tok_name[t.type], t.string) for t in tk5])

print("\n== 六、括号内换行不产生 NEWLINE ==")
tk6 = list(tokenize.generate_tokens(io.StringIO("x = (1 +\n     2)\ny = 3\n").readline))
print("  ", [token.tok_name[t.type] for t in tk6])
print("  NL(非逻辑换行)与 NEWLINE(逻辑行结束)出现次数:", collections.Counter(token.tok_name[t.type] for t in tk6 if t.type in (token.NL, token.NEWLINE)))

print("\n== 七、错误也在这里出现 ==")
for bad in ("x = 'abc\n", "x = (1 + 2\n", "if x:\n  a = 1\n    b = 2\n"):
    try: list(tokenize.generate_tokens(io.StringIO(bad).readline)); print(f"  {bad!r}: tokenize 没报错")
    except (tokenize.TokenError, IndentationError, SyntaxError) as e: print(f"  {bad!r}: {type(e).__name__}: {e}")
    try: compile(bad, "<s>", "exec"); print("     compile: 通过")
    except SyntaxError as e: print(f"     compile: {type(e).__name__}: {e.msg}")

print("\n== 八、用 tokenize 统计真实文件 ==")
import json.decoder as jd
src8 = open(jd.__file__).read()
cnt = collections.Counter(token.tok_name[t.type] for t in tokenize.generate_tokens(io.StringIO(src8).readline))
print(f"  json/decoder.py {len(src8.splitlines())} 行:", dict(cnt.most_common(9)))
json.dump({'row1': row1, 'row2': row2, 'toks': [(token.tok_name[t.type], t.string, t.start[1], t.end[1]) for t in toks]}, open('out/83.json', 'w'), ensure_ascii=False)
