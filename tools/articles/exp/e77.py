import hashlib, hmac, os, struct, time, json

# ---- 纯 Python SHA-256, 允许从任意中间状态继续(攻击者用它) ----
K = [0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]
IV = [0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]
rotr = lambda x, n: ((x >> n) | (x << (32 - n))) & 0xffffffff
def compress(h, block):
    w = list(struct.unpack('>16I', block))
    for i in range(16, 64):
        s0 = rotr(w[i-15], 7) ^ rotr(w[i-15], 18) ^ (w[i-15] >> 3); s1 = rotr(w[i-2], 17) ^ rotr(w[i-2], 19) ^ (w[i-2] >> 10)
        w.append((w[i-16] + s0 + w[i-7] + s1) & 0xffffffff)
    a, b, c, d, e, f, g, hh = h
    for i in range(64):
        S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25); ch = (e & f) ^ (~e & g); t1 = (hh + S1 + ch + K[i] + w[i]) & 0xffffffff
        S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22); maj = (a & b) ^ (a & c) ^ (b & c); t2 = (S0 + maj) & 0xffffffff
        hh, g, f, e, d, c, b, a = g, f, e, (d + t1) & 0xffffffff, c, b, a, (t1 + t2) & 0xffffffff
    return [(x + y) & 0xffffffff for x, y in zip(h, [a, b, c, d, e, f, g, hh])]
def pad(total_len): return b'\x80' + b'\x00' * ((55 - total_len) % 64) + struct.pack('>Q', total_len * 8)
def sha256_from(state, data, already):   # already: 已经处理过的字节数(必须是 64 的倍数)
    h = list(state); m = data + pad(already + len(data))
    for i in range(0, len(m), 64): h = compress(h, m[i:i+64])
    return struct.pack('>8I', *h)

print("== 〇、自己写的 SHA-256 先对拍 ==")
ok = all(sha256_from(IV, m, 0) == hashlib.sha256(m).digest() for m in (b'', b'abc', b'a' * 55, b'a' * 56, b'a' * 64, os.urandom(300)))
print("  与 hashlib.sha256 对拍 6 组输入, 全部一致?", ok)

print("\n== 一、有缺陷的签名: tag = sha256(secret + message) ==")
secret = os.urandom(16)
def server_sign(msg): return hashlib.sha256(secret + msg).hexdigest()
def server_verify(msg, tag): return hmac.compare_digest(server_sign(msg), tag)
msg = b"user=ann&role=user"; tag = server_sign(msg)
print("  原始 message:", msg); print("  服务端给的 tag:", tag)
print("  攻击者不知道 secret, 只知道它的长度 =", len(secret), "字节")

print("\n== 二、长度扩展攻击 ==")
suffix = b"&role=admin"
glue = pad(len(secret) + len(msg))
forged_msg = msg + glue + suffix
state = list(struct.unpack('>8I', bytes.fromhex(tag)))
forged_tag = sha256_from(state, suffix, len(secret) + len(msg) + len(glue)).hex()
print("  中间填充 glue (%d 字节):" % len(glue), glue)
print("  伪造的 message:", forged_msg)
print("  伪造的 tag:", forged_tag)
print("  服务端验证伪造消息 →", server_verify(forged_msg, forged_tag), "  (攻击者从没见过 secret)")
print("  服务端自己给伪造消息签的 tag 与伪造的一致?", server_sign(forged_msg) == forged_tag)

print("\n== 三、换成 HMAC, 同样的攻击 ==")
def hm_sign(m): return hmac.new(secret, m, hashlib.sha256).hexdigest()
h_tag = hm_sign(msg)
state2 = list(struct.unpack('>8I', bytes.fromhex(h_tag)))
h_forged = sha256_from(state2, suffix, len(secret) + len(msg) + len(glue)).hex()
print("  HMAC tag:", h_tag)
print("  同样构造的伪造 tag 通过 HMAC 验证?", hmac.compare_digest(hm_sign(forged_msg), h_forged))
print("  HMAC 对伪造消息真实的 tag 前 16 位:", hm_sign(forged_msg)[:16], "vs 伪造的前 16 位:", h_forged[:16])
try: hmac.new(secret, msg)
except TypeError as e: print("  hmac.new 忘记写 digestmod →", type(e).__name__ + ":", e)

print("\n== 四、比较 tag: == 还是 compare_digest ==")
N = 20_000_000
good = os.urandom(N)
bad_first = bytes([good[0] ^ 1]) + good[1:]
bad_last = good[:-1] + bytes([good[-1] ^ 1])
def t(f, a, b, reps=20):
    best = 1e9
    for _ in range(reps):
        s = time.perf_counter(); f(a, b); best = min(best, time.perf_counter() - s)
    return best * 1e6
print(f"  两个 {N//1_000_000} MB 的 bytes, 分别在第 1 字节 / 最后 1 字节不同 (取 20 次最小值):")
for name, f in (("a == b", lambda a, b: a == b), ("hmac.compare_digest", hmac.compare_digest)):
    print(f"    {name:<20} 第1字节不同 {t(f, good, bad_first):10.2f} µs   最后1字节不同 {t(f, good, bad_last):10.2f} µs")
json.dump({'tag': tag, 'glue_len': len(glue), 'forged_tag': forged_tag, 'h_tag': h_tag, 'h_forged': h_forged, 'msg': msg.decode(), 'forged_msg': repr(forged_msg), 'glue': repr(glue)}, open('out/77.json', 'w'))
