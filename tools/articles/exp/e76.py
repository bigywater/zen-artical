import random, secrets, hashlib, subprocess, sys, time, json, os

print("== 一、random:同一个种子,同一串数 ==")
for k in range(2):
    random.seed(42); print(f"  第{k+1}次 seed(42):", [random.randint(0, 99) for _ in range(6)])
random.seed(); a = [random.randint(0, 99) for _ in range(6)]; random.seed(); b = [random.randint(0, 99) for _ in range(6)]
print("  不给种子(系统熵), 两次:", a, b, "| 相同?", a == b)

print("\n== 二、secrets:没有种子可言 ==")
print("  secrets.token_hex(8) 三次:", [secrets.token_hex(8) for _ in range(3)])
print("  secrets.SystemRandom().seed(42) 有效吗?", end=" ")
sr = secrets.SystemRandom(); sr.seed(42); x = [sr.randint(0, 99) for _ in range(6)]; sr.seed(42); y = [sr.randint(0, 99) for _ in range(6)]
print(x, y, "→ 相同?", x == y)

print("\n== 三、拿到 624 个输出,就能预测 random 的所有未来输出 ==")
def untemper(y):
    y ^= y >> 18
    y ^= (y << 15) & 0xefc60000
    t = y
    for _ in range(5): t = y ^ ((t << 7) & 0x9d2c5680)
    y = t
    t = y
    for _ in range(3): t = y ^ (t >> 11)
    return t
def attack(victim_gen):
    outs = [victim_gen() for _ in range(624)]
    state = [untemper(o) for o in outs]
    global LAST; LAST = (outs[:4], state[:4], outs[-1])
    clone = random.Random(); clone.setstate((3, tuple(state + [624]), None))
    return clone
victim = random.Random(); victim.seed(int.from_bytes(os.urandom(16), 'big'))   # 受害者种子未知
clone = attack(lambda: victim.getrandbits(32))
pred = [clone.getrandbits(32) for _ in range(5)]; real = [victim.getrandbits(32) for _ in range(5)]
print("  观察了受害者 624 个 32 位输出, 还原内部状态后预测接下来 5 个:")
for p, r in zip(pred, real): print(f"    预测 {p:>10}   真实 {r:>10}   {'一致' if p == r else '不一致'}")
pred_f = [clone.random() for _ in range(3)]; real_f = [victim.random() for _ in range(3)]
print("  同一个克隆预测 random() 的下 3 个浮点数:", pred_f == real_f)
tok_pred = ''.join(clone.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=12)); tok_real = ''.join(victim.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=12))
print(f"  受害者用 random.choices 生成的 12 位「重置令牌」: {tok_real}   攻击者预测: {tok_pred}   一致? {tok_pred == tok_real}")
SAVED = LAST
sv = secrets.SystemRandom()
try:
    clone2 = attack(lambda: sv.getrandbits(32))
    p2 = [clone2.getrandbits(32) for _ in range(5)]; r2 = [sv.getrandbits(32) for _ in range(5)]
    print("  同样对 SystemRandom 做:", "预测", p2, "真实", r2, "→ 命中个数", sum(a == b for a, b in zip(p2, r2)), "/ 5")
except Exception as e: print("  对 SystemRandom 攻击失败:", e)

print("\n== 四、hashlib:不随机,是确定性的指纹 ==")
code = "import hashlib;print(hashlib.sha256(b'hello').hexdigest()[:16], hash('hello'))"
outs = [subprocess.run([sys.executable, '-c', code], capture_output=True, text=True).stdout.strip() for _ in range(3)]
for o in outs: print("  新进程里 sha256('hello')[:16], hash('hello') =", o)
print("  sha256 三个进程一致?", len({o.split()[0] for o in outs}) == 1, "| 内置 hash() 三个进程一致?", len({o.split()[1] for o in outs}) == 1)
print("  sha256(b'hello') 完整:", hashlib.sha256(b'hello').hexdigest())
print("  同一输入改一位 sha256(b'hellp'):", hashlib.sha256(b'hellp').hexdigest())

print("\n== 五、速度 ==")
def bench(f, n=200000):
    t = time.perf_counter()
    for _ in range(n): f()
    return (time.perf_counter() - t) / n * 1e9
r = random.Random(1)
for name, f in (("random.getrandbits(64)", lambda: r.getrandbits(64)), ("secrets.randbits(64)", lambda: secrets.randbits(64)), ("secrets.token_bytes(8)", lambda: secrets.token_bytes(8)), ("hashlib.sha256(b'x').digest()", lambda: hashlib.sha256(b'x').digest())):
    print(f"  {name:<32} {bench(f):8.0f} ns / 次")
json.dump({'pred': pred, 'real': real, 'first_obs': SAVED[0], 'first_state': SAVED[1]}, open('out/76.json', 'w'))
