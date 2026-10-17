import gc, sys, weakref, json, tracemalloc

class N:
    def __init__(self, name): self.name = name; self.refs = []
    def __repr__(self): return self.name

print("== 一、引用计数回收不了环 ==")
gc.collect(); gc.disable()
a, b = N("a"), N("b"); a.refs.append(b); b.refs.append(a)
wa = weakref.ref(a)
print("  a、b 互相引用。del a, b 之前 sys.getrefcount(a) =", sys.getrefcount(a), "(a 变量 + b.refs 里的一个 + getrefcount 的实参)")
del a, b
print("  del a, b 之后, 弱引用还活着吗?", wa() is not None, "→ 引用计数没有归零,对象泄漏在堆里")
print("  gc.collect() 返回(回收的对象数):", gc.collect(), "| 之后弱引用还活着吗?", wa() is not None)

print("\n== 二、gc 看到的世界 ==")
print("  gc.get_threshold() =", gc.get_threshold(), "| 分代数:", len(gc.get_stats()), "| gc.isenabled() =", gc.isenabled())
gc.enable()
for label, o in (("整数 1", 1), ("字符串 'x'", 'x'), ("空列表 []", []), ("空字典 {}", {}), ("{'a': 1}", {'a': 1}), ("{'a': []}", {'a': []}), ("元组 (1, 2)", (1, 2)), ("元组 (1, [])", (1, [])), ("自定义对象 N()", N('t')), ("N 的类", N)):
    print(f"  gc.is_tracked({label:<14}) = {gc.is_tracked(o)}")

print("\n== 三、自己实现「试探性删除」, 对照真实的 gc.collect() ==")
class Node:
    def __init__(self, name): self.name = name; self.nxt = None
    def __repr__(self): return self.name
dead = []
class Watched(Node):
    def __del__(self): dead.append(self.name)
gc.disable()
A, B, C, D, E = (Watched(n) for n in "ABCDE")
P = Watched("P")               # 校准对象: 只被全局名字 P 引用
A.nxt = B; B.nxt = A          # A<->B: 环, 之后没有任何外部引用
C.nxt = D; D.nxt = C          # C<->D: 环, 但全局名字 C 还指着 C
E.nxt = E                     # E: 自环, 之后没有外部引用
del A, B, D, E                # 只留全局名字 C

def analyze(names):
    """gc 的「试探性删除」: gc_refs = 引用计数 - 来自集合内部的引用; 剩下 >0 的是外部可达的根"""
    S = [o for o in gc.get_objects() if isinstance(o, Watched) and o.name in names]
    S.sort(key=lambda o: o.name)
    # 每个对象此刻的引用计数, 减掉这里几处「观察带来的引用」(S 列表 1 个 + 循环变量 1 个 + getrefcount 实参 1 个)
    raw = {o.name: sys.getrefcount(o) for o in S}
    base = raw["P"] - 1                      # 校准: P 只有全局名字一个外部引用, 其余都是「观察带来的引用」
    gc_refs = {n: v - base for n, v in raw.items() if n != "P"}
    S = [o for o in S if o.name != "P"]
    rc0 = dict(gc_refs)
    for o in S:
        for r in gc.get_referents(o):
            if isinstance(r, Watched): gc_refs[r.name] -= 1
    roots = [n for n, v in gc_refs.items() if v > 0]
    alive = set(roots); todo = list(roots)
    by_name = {o.name: o for o in S}
    while todo:
        for r in gc.get_referents(by_name[todo.pop()]):
            if isinstance(r, Watched) and r.name not in alive: alive.add(r.name); todo.append(r.name)
    return rc0, gc_refs, roots, sorted(set(gc_refs) - alive)
rc0, gc_refs, roots, garbage = analyze("ABCDEP")
print(f"  (校准: 只被一个全局名字引用的对象 P, getrefcount 原始值 = {sys.getrefcount(P)}, 所以观察本身带来 {sys.getrefcount(P)-1-0} 个额外引用。下表都已减掉)")
print("  节点  引用计数  减去「图内部的引用」之后(gc_refs)")
for nm in "ABCDE": print(f"   {nm}       {rc0[nm]}          {gc_refs[nm]}")
print("  gc_refs > 0 的是外部可达的根:", roots, "→ 从根出发能到达:", sorted(set(rc0) - set(garbage)))
print("  我的算法判定的垃圾:", garbage)
print("  gc.collect() 之前 __del__ 已调用的:", dead)
n = gc.collect()
print("  gc.collect() 回收对象数:", n, "| __del__ 通知到的:", sorted(dead), "| 一致?", sorted(dead) == garbage, "| 全局 C 还活着:", C.name, C.nxt.name)
rows = [(nm, rc0[nm], rc0[nm] - gc_refs[nm], gc_refs[nm]) for nm in "ABCDE"]

print("\n== 四、自动触发: gc.callbacks 记录每一次回收 ==")
gc.enable(); ev = []
def cb(phase, info):
    if phase == "stop": ev.append((info["generation"], info["collected"]))
gc.callbacks.append(cb)
for _ in range(20000):
    x = N("x"); y = N("y"); x.refs.append(y); y.refs.append(x)
gc.callbacks.remove(cb)
import collections
gens = collections.Counter(g for g, _ in ev)
print("  创建 20000 对环形垃圾, gc 自动触发了", len(ev), "次回收, 各代次数:", dict(sorted(gens.items())), "| 共回收对象数:", sum(c for _, c in ev))
print("  最后 3 次回收:", ev[-3:])
print("  gc.get_stats():", [{k: v for k, v in s.items()} for s in gc.get_stats()])

print("\n== 五、gc.disable() 时内存会怎样 ==")
def churn(n):
    for _ in range(n):
        x = N("x"); y = N("y"); x.refs.append(y); y.refs.append(x)
for mode in ("enabled", "disabled"):
    gc.collect()
    (gc.enable if mode == "enabled" else gc.disable)()
    tracemalloc.start(); churn(200000); cur, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    print(f"  gc {mode:<9}: 创建 20 万对环形垃圾后, 仍占用 {cur/1e6:8.2f} MB (峰值 {peak/1e6:8.2f} MB)")
gc.enable(); print("  之后 gc.collect() 回收:", gc.collect(), "个对象")
json.dump({'rows': rows}, open('out/84.json', 'w'))
