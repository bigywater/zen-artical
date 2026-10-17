import ast, dis, collections, json, sys, io, contextlib, os, json as J

print("== 一、一行赋值的语法树 ==")
src = "x = a + b * c"
tree = ast.parse(src)
print(ast.dump(tree, indent=2))

print("\n== 二、优先级和括号: 树形状表达一切, 括号本身不在树里 ==")
for s in ("a + b * c", "(a + b) * c", "a + (b * c)"):
    print(f"  {s:<14}", ast.dump(ast.parse(s, mode='eval').body))
print("  'a + b * c' 与 'a + (b * c)' 的树相同?", ast.dump(ast.parse('a + b * c')) == ast.dump(ast.parse('a + (b * c)')))

print("\n== 三、注释和空白不在树里 ==")
a1 = "x   =   1   # 这是注释\n\n\n"; a2 = "x = 1"
print("  带注释和多余空白的源码与干净源码, ast.dump 相同?", ast.dump(ast.parse(a1)) == ast.dump(ast.parse(a2)))
print("  ast.unparse(ast.parse(a1)) =", repr(ast.unparse(ast.parse(a1))), "(注释丢了, 格式统一了)")
print("  ast.unparse(ast.parse('(a + b) * c')) =", repr(ast.unparse(ast.parse('(a + b) * c'))), "(括号是按需重新生成的)")

print("\n== 四、位置信息 ==")
t = ast.parse("total = (price *\n    qty)")
n = t.body[0].value
print(f"  BinOp: lineno={n.lineno} col_offset={n.col_offset} end_lineno={n.end_lineno} end_col_offset={n.end_col_offset}; Assign 的 _fields = {ast.Assign._fields}")

print("\n== 五、真实文件里的节点统计: json/decoder.py ==")
import json.decoder as jd
code = open(jd.__file__).read()
tr = ast.parse(code)
cnt = collections.Counter(type(n).__name__ for n in ast.walk(tr))
print(f"  文件 {len(code.splitlines())} 行, 共 {sum(cnt.values())} 个节点, {len(cnt)} 种类型; 出现最多的 8 种:")
for k, v in cnt.most_common(8): print(f"    {k:<14} {v}")
print("  函数定义:", [n.name for n in ast.walk(tr) if isinstance(n, ast.FunctionDef)][:6])

print("\n== 六、NodeTransformer 改写后再执行 ==")
class Bump(ast.NodeTransformer):
    def visit_Constant(self, node):
        if isinstance(node.value, int) and not isinstance(node.value, bool): return ast.copy_location(ast.Constant(node.value + 1), node)
        return node
t = ast.parse("result = 10 * 2 + 5\nprint('原代码里写的是 10*2+5, 计算结果:', result)")
t2 = ast.fix_missing_locations(Bump().visit(t))
print("  改写后的源码:", repr(ast.unparse(t2)))
exec(compile(t2, "<改写后>", "exec"))
print("  (11 * 3 + 6 = 39)")

print("\n== 七、literal_eval 与 eval ==")
print("  literal_eval(\"{'a': [1, 2, (3, 4)]}\") =", ast.literal_eval("{'a': [1, 2, (3, 4)]}"))
try: ast.literal_eval("__import__('os').getcwd()")
except ValueError as e: print("  literal_eval(\"__import__('os').getcwd()\") → ValueError:", e)
print("  eval(\"__import__('os').getcwd()\") → 直接执行了, 返回", os.path.basename(eval("__import__('os').getcwd()")) and "<当前目录>")

print("\n== 八、编译器在树上做的事: 常量折叠 ==")
def ins(src, mode="exec"):
    return [(i.opname, i.argrepr or (i.arg if i.arg is not None else '')) for i in dis.get_instructions(compile(src, "<s>", mode)) if i.opname not in ("RESUME", "RETURN_VALUE", "NOP", "RETURN_CONST", "STORE_NAME")]
for s_ in ("x = 2 * 3 + 1", "x = a * b + 1"):
    print(f"  {s_:<16} →", ins(s_))
order = ins("a + b * c", "eval")
print("  a + b * c 的字节码执行顺序:", order)
J.dump({'order': order}, open('out/81.json', 'w'), ensure_ascii=False)
