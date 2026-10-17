import hashlib, os, time, hmac, json, itertools, resource

print("== 一、直接 sha256(password) ==")
pw = "482915"
stored = hashlib.sha256(pw.encode()).hexdigest()
print("  库里存的:", stored)
t = time.perf_counter(); tries = 0; found = None
for i in range(1_000_000):
    g = f"{i:06d}"; tries += 1
    if hashlib.sha256(g.encode()).hexdigest() == stored: found = g; break
el = time.perf_counter() - t
print(f"  纯 Python 循环暴力枚举 6 位数字: 试了 {tries} 次, 找到 {found!r}, 用时 {el*1000:.0f} ms, 速度 {tries/el:,.0f} 次/秒 (单核, 没有任何优化)")
words = ["password", "123456", "qwerty", "letmein", "iloveyou", "admin", "welcome", "monkey", "dragon", "sunshine"]
t2 = hashlib.sha256(b"letmein").hexdigest()
t = time.perf_counter(); hit = next(w for w in words if hashlib.sha256(w.encode()).hexdigest() == t2); print(f"  字典 (10 个常见口令) 命中 {hit!r}, 用时 {(time.perf_counter()-t)*1e6:.0f} µs")

print("\n== 二、不加盐: 相同口令 = 相同哈希 ==")
for u, p in (("ann", "hunter2"), ("bob", "hunter2"), ("cat", "other")):
    print(f"  {u}: sha256 = {hashlib.sha256(p.encode()).hexdigest()[:24]}…")
print("  加盐 (每人一个随机 16 字节):")
for u, p in (("ann", "hunter2"), ("bob", "hunter2")):
    s = os.urandom(16); print(f"  {u}: salt={s.hex()[:8]}… sha256(salt+pw) = {hashlib.sha256(s + p.encode()).hexdigest()[:24]}…")

print("\n== 三、故意做得慢: pbkdf2_hmac 与 scrypt ==")
salt = os.urandom(16); rates = {}
def measure(name, f, reps):
    t = time.perf_counter()
    for _ in range(reps): f()
    per = (time.perf_counter() - t) / reps
    rates[name] = per; return per
per = measure("sha256", lambda: hashlib.sha256(b"hunter2").digest(), 100000)
print(f"  {'sha256(一次)':<28} {per*1e6:12.2f} µs / 次   → {1/per:>12,.0f} 次/秒")
for it in (1000, 100_000, 600_000):
    per = measure(f"pbkdf2 {it}", lambda: hashlib.pbkdf2_hmac('sha256', b"hunter2", salt, it), 3 if it > 1000 else 20)
    print(f"  {f'pbkdf2_hmac 迭代 {it}':<28} {per*1e3:12.2f} ms / 次   → {1/per:>12,.1f} 次/秒")
for n in (2**14, 2**15):
    per = measure(f"scrypt {n}", lambda: hashlib.scrypt(b"hunter2", salt=salt, n=n, r=8, p=1, maxmem=128*1024*1024), 3)
    print(f"  {f'scrypt n=2^{n.bit_length()-1}, r=8, p=1':<28} {per*1e3:12.2f} ms / 次   → {1/per:>12,.1f} 次/秒   (需要内存 ≈ 128*n*r = {128*n*8/1024/1024:.0f} MiB)")
print(f"  按 6 位数字空间 (100 万种) 算, 枚举全部要:")
for k in ("sha256", "pbkdf2 1000", "pbkdf2 100000", "pbkdf2 600000", "scrypt 16384"):
    print(f"    {k:<16} {1e6*rates[k]:12,.1f} 秒")

print("\n== 四、存储格式与验证 ==")
def hash_pw(pw, it=600_000):
    salt = os.urandom(16); h = hashlib.pbkdf2_hmac('sha256', pw.encode(), salt, it)
    return f"pbkdf2_sha256${it}${salt.hex()}${h.hex()}"
def verify(pw, rec):
    algo, it, salt, h = rec.split('$'); h2 = hashlib.pbkdf2_hmac('sha256', pw.encode(), bytes.fromhex(salt), int(it))
    return hmac.compare_digest(h2, bytes.fromhex(h))
rec = hash_pw("hunter2"); print("  存进库的字符串:", rec[:60] + "…", "长度", len(rec))
print("  verify('hunter2') =", verify("hunter2", rec), "| verify('hunter3') =", verify("hunter3", rec))
print("  同一口令两次 hash_pw 得到相同记录?", hash_pw("hunter2") == hash_pw("hunter2"))
json.dump({'rates': rates, 'found': found, 'tries': tries, 'el': el}, open('out/78.json', 'w'))
