import sys, os, random, hashlib, itertools, collections, math; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p39')
rng = random.Random(39)
VOCAB = [f'w{i}' for i in range(6000)]
WEIGHTS = [1 / (i + 5) for i in range(len(VOCAB))]        # 近似 Zipf 分布
def words(n): return rng.choices(VOCAB, WEIGHTS, k=n)
def jaccard(a, b):
    sa, sb = set(a), set(b); return len(sa & sb) / len(sa | sb)

def simhash(tokens, bits=64):
    v = [0] * bits
    for t, c in collections.Counter(tokens).items():
        h = int.from_bytes(hashlib.blake2b(t.encode(), digest_size=8).digest(), 'little')
        for i in range(bits):
            v[i] += c if (h >> i) & 1 else -c
    return sum(1 << i for i in range(bits) if v[i] > 0)
def ham(a, b): return bin(a ^ b).count('1')
def shingles(ws, n=3): return [' '.join(ws[i:i + n]) for i in range(len(ws) - n + 1)]

BOILER = words(600)            # 同一个站点的模板文字(导航、页脚等),所有页面共用
def mutate(body, rate):
    out = list(body)
    for i in range(len(out)):
        if rng.random() < rate: out[i] = rng.choice(VOCAB)
    return out
NB = 150
bases = [words(400) for _ in range(NB)]
docs = []     # (类别, 组号, 正文词表)
for g, b in enumerate(bases):
    docs.append(('原文', g, b))
    docs.append(('改 1%', g, mutate(b, 0.01))); docs.append(('改 5%', g, mutate(b, 0.05))); docs.append(('改 15%', g, mutate(b, 0.15)))
for u in range(150): docs.append(('无关', 1000 + u, words(400)))
print('== 一:合成语料')
print(f'  {NB} 篇原文(各 400 个词),每篇另有改了 1%、5%、15% 的词的 3 个变体;另有 150 篇互不相关的文章。所有页面共用同一段 600 词的站点模板(导航、页脚)。共 {len(docs)} 篇')

def make_hashes(with_boiler, mode='uni'):
    hs = []
    for cat, g, body in docs:
        toks = (BOILER + body) if with_boiler else body
        hs.append(simhash(shingles(toks) if mode == 'sh' else toks))
    return hs
H_body = make_hashes(False); H_full = make_hashes(True)
labels = [(c, g) for c, g, _ in docs]

def pair_stats(H):
    near, un_same_boiler = collections.defaultdict(list), []
    n = len(H); neg = []
    for i in range(n):
        for j in range(i + 1, n):
            d = ham(H[i], H[j]); ci, gi = labels[i]; cj, gj = labels[j]
            if gi == gj: near[(ci, cj)].append(d)
            else: neg.append(d)
    return near, neg
near_b, neg_b = pair_stats(H_body); near_f, neg_f = pair_stats(H_full)

def summ(xs): xs = sorted(xs); return f'最小 {xs[0]}、中位 {xs[len(xs) // 2]}、最大 {xs[-1]}'
print('== 二:64 位 SimHash(词的一元特征,按词频加权)之间的汉明距离。左:只对正文做;右:把共用的站点模板文字也一起做')
print(f'  {"文章对":<24}{"只对正文":>34}{"含 600 词站点模板":>34}')
for key, name in ((('原文', '改 1%'), '原文 与 改 1%'), (('原文', '改 5%'), '原文 与 改 5%'), (('原文', '改 15%'), '原文 与 改 15%')):
    print(f'  {name:<20}{summ(near_b[key]):>38}{summ(near_f[key]):>38}')
print(f'  {"互不相关的两篇":<20}{summ(neg_b):>38}{summ(neg_f):>38}')
rj = []
for g in range(NB):
    for c in (1, 2, 3): rj.append(jaccard(bases[g], docs[g * 4 + c][2]))
print(f'  (对照:原文与变体的词集合 Jaccard 相似度平均 {sum(rj) / len(rj):.3f};随机两篇的词集合 Jaccard 平均 {sum(jaccard(docs[i][2], docs[i + 4][2]) for i in range(0, 300, 4)) / 75:.3f})')

print('== 三:选一个阈值 k(汉明距离 ≤ k 就判为近似重复),各取什么值时,三种变体被找出来的比例(召回)与把互不相关的文章误判为重复的对数(误报)')
pos_b = [d for (a, b_), v in near_b.items() for d in v if a == '原文']          # 原文与各变体
pos_f = [d for (a, b_), v in near_f.items() for d in v if a == '原文']
print(f'  共 {len(pos_b)} 对"原文-变体"正例,{len(neg_b):,} 对不相关的负例')
print(f'  {"k":>3}{"召回(只对正文)":>16}{"误报对数":>10}{"召回(含模板)":>16}{"误报对数":>10}')
for k in (0, 3, 6, 10, 14, 18, 22, 26):
    print(f'  {k:>3}{sum(d <= k for d in pos_b) / len(pos_b) * 100:>14.1f}%{sum(d <= k for d in neg_b):>10}{sum(d <= k for d in pos_f) / len(pos_f) * 100:>14.1f}%{sum(d <= k for d in neg_f):>10}')
print('== 四:用词的 3 元组(shingle)当特征,而不是单个词:模板文字的影响')
H_sh = make_hashes(False, 'sh'); H_shf = make_hashes(True, 'sh')
for nm, H in (('只对正文(3 元组)', H_sh), ('含模板(3 元组)', H_shf)):
    nr, ng = pair_stats(H)
    print(f'  {nm}:原文与改 5% 的距离 {summ(nr[("原文", "改 5%")])};原文与改 15% 的距离 {summ(nr[("原文", "改 15%")])};不相关的两篇 {summ(ng)}')
print('== 五:速度')
t0 = time.perf_counter(); [simhash(d[2]) for d in docs[:200]]; ts = time.perf_counter() - t0
a = H_body; t0 = time.perf_counter(); c = 0
for i in range(len(a)):
    for j in range(i + 1, len(a)): c += ham(a[i], a[j]) <= 3
tp = time.perf_counter() - t0; npairs = len(a) * (len(a) - 1) // 2
print(f'  计算 400 词文章的 SimHash:{ts / 200 * 1000:.2f} ms/篇(纯 Python);两两比较 {npairs:,} 对汉明距离:{tp:.2f} 秒,约 {npairs / tp / 1e6:.2f} 百万对/秒。两两比较是 O(n²),文章数到百万级就必须用索引(按位段分桶)')
purge()
