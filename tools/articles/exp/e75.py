import json, datetime, decimal, math

class User:
    def __init__(self, name, joined): self.name, self.joined = name, joined
    def __repr__(self): return f"User({self.name!r})"

print("== 一、默认不认识自定义类 ==")
try: json.dumps({"u": User("ann", datetime.date(2026, 1, 2))})
except TypeError as e: print("TypeError:", e)

print("\n== 二、default 钩子:只在遇到不认识的对象时被调用 ==")
calls = []
def default(o):
    calls.append(f"default({o!r})")
    if isinstance(o, User): return {"__user__": True, "name": o.name, "joined": o.joined}
    if isinstance(o, datetime.date): return {"__date__": o.isoformat()}
    if isinstance(o, (set, frozenset)): return sorted(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")
data = {"id": 7, "tags": {"b", "a"}, "owner": User("ann", datetime.date(2026, 1, 2)), "score": 9.5}
s = json.dumps(data, default=default)
for c in calls: print("  ", c)
print("dumps →", s)

print("\n== 三、object_hook:每个 JSON 对象(dict)解析完就调用一次, 由内到外 ==")
hooks = []
def hook(d):
    hooks.append(f"object_hook({d!r})")
    if d.get("__date__"): return datetime.date.fromisoformat(d["__date__"])
    if d.get("__user__"): return User(d["name"], d["joined"])
    return d
back = json.loads(s, object_hook=hook)
for h in hooks: print("  ", h)
print("loads →", back, "| owner 类型:", type(back["owner"]).__name__, "| joined 类型:", type(back["owner"].joined).__name__)
print("tags 还原成了:", type(back["tags"]).__name__, back["tags"], "(set 变成了 list)")

print("\n== 四、往返之后类型会变 ==")
samples = [("tuple (1,2)", (1, 2)), ("int 键 {1:'a'}", {1: 'a'}), ("bytes", None), ("Decimal('1.10')", None), ("float('nan')", float('nan')), ("大整数 2**70", 2**70), ("1e400", None)]
def rt(v):
    try: r = json.loads(json.dumps(v)); return r
    except Exception as e: return f"{type(e).__name__}: {e}"
print(f"  tuple (1,2)        → {json.dumps((1,2))} → {rt((1,2))!r}  相等? {rt((1,2)) == (1,2)}")
print(f"  int 键 {{1:'a'}}     → {json.dumps({1:'a'})} → {rt({1:'a'})!r}  相等? {rt({1:'a'}) == {1:'a'}}")
print(f"  bytes b'x'         → {rt(b'x')}")
print(f"  Decimal('1.10')    → {rt(decimal.Decimal('1.10'))}")
print(f"  float('nan')       → {json.dumps(float('nan'))} → {rt(float('nan'))!r}  ← 输出了不是合法 JSON 的 NaN")
try: json.dumps(float('nan'), allow_nan=False)
except ValueError as e: print("  allow_nan=False    →", "ValueError:", e)
print(f"  大整数 2**70       → {json.dumps(2**70)} → {rt(2**70)!r}  相等? {rt(2**70) == 2**70}")
print(f"  loads('1e400')     → {json.loads('1e400')!r}")
print(f"  重复键 loads('{{\"a\":1,\"a\":2}}') → {json.loads('{\"a\":1,\"a\":2}')}   (后者覆盖前者)")
pairs = json.loads('{"a":1,"a":2}', object_pairs_hook=lambda p: p)
print(f"  object_pairs_hook 看到全部: {pairs}")

print("\n== 五、default 返回了另一个不认识的对象会怎样 ==")
class Node:
    pass
n = Node()
try: json.dumps(n, default=lambda o: o)
except ValueError as e: print("default 返回自己 →", type(e).__name__ + ":", e)
n2 = Node()
depth = []
def d2(o): depth.append(type(o).__name__); return [o]
try: json.dumps(n2, default=d2)
except ValueError as e: print("default 返回 [o] (里面还是同一个对象) →", type(e).__name__ + ":", e, "| __notes__ =", getattr(e, '__notes__', None), "| default 被调用", len(depth), "次")

import json as J
json_out = {"calls": calls, "hooks": hooks, "s": s}
J.dump(json_out, open('out/75.json', 'w'), ensure_ascii=False)
