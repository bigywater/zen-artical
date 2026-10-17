import sys, os, random, heapq, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p28')
# 生成一个合成的"网站":有层级的链接图,每页有一个"价值"(比如商品页=1,列表页/导航页=0)
# 结构:首页 → 10 个分类页 → 每个分类页有 30 个列表页(分页链) → 每个列表页链接 20 个商品页;另有 8% 的页面是"低价值页"(关于我们、登录、标签云)互相链接成团
def build(seed=7):
    rng = random.Random(seed); links = {}; value = {}; depth = {}
    links['/'] = [f'/cat/{c}' for c in range(10)] + ['/about', '/login', '/tags']
    value['/'] = 0
    for p in ('/about', '/login', '/tags'): value[p] = 0
    links['/about'] = ['/', '/login', '/tags']; links['/login'] = ['/', '/about']; links['/tags'] = [f'/tag/{i}' for i in range(60)]
    for i in range(60):
        links[f'/tag/{i}'] = [f'/tag/{(i + k) % 60}' for k in (1, 7, 13)] + ['/tags']; value[f'/tag/{i}'] = 0
    for c in range(10):
        cat = f'/cat/{c}'; value[cat] = 0
        links[cat] = [f'/cat/{c}/page/1', '/'] 
        for pg in range(1, 31):
            lp = f'/cat/{c}/page/{pg}'; value[lp] = 0
            nxt = [f'/cat/{c}/page/{pg + 1}'] if pg < 30 else []
            items = [f'/item/{c}-{pg}-{k}' for k in range(20)]
            links[lp] = nxt + items + [cat]
            for it in items:
                value[it] = 1; links[it] = [lp, f'/cat/{(c + 1) % 10}'] + ([f'/item/{c}-{pg}-{(int(it.split("-")[-1]) + 1) % 20}'] if True else [])
    return links, value
LINKS, VALUE = build()
TOTAL_ITEMS = sum(VALUE.values()); NPAGES = len(LINKS)
print(f'(合成站点:{NPAGES} 个页面,其中有价值的商品页 {TOTAL_ITEMS} 个;首页链接到 10 个分类,每个分类 30 个分页列表页,每个分页 20 个商品页;另有一团 60 页的"标签云"和 3 个导航页)')

def crawl(order, budget, prio=None):
    """order: 'bfs' | 'dfs' | 'prio'。每抓一个页面计一次预算;返回按预算累计的 (抓到的商品页数) 曲线。"""
    seen = {'/'}; items = 0; curve = []; fetched = 0; depth = {'/': 0}
    if order == 'bfs': fr = collections.deque(['/'])
    elif order == 'dfs': fr = ['/']
    else: fr = [(prio('/', 0), 0, '/')]; cnt = 1
    maxfr = 1
    while (fr if order != 'prio' else fr) and fetched < budget:
        if order == 'bfs': u = fr.popleft()
        elif order == 'dfs': u = fr.pop()
        else: _, _, u = heapq.heappop(fr)
        fetched += 1; items += VALUE[u]; curve.append(items)
        for v in LINKS.get(u, []):
            if v in seen: continue
            seen.add(v); depth[v] = depth[u] + 1
            if order == 'bfs': fr.append(v)
            elif order == 'dfs': fr.append(v)
            else: heapq.heappush(fr, (prio(v, depth[v]), cnt, v)); cnt += 1
        maxfr = max(maxfr, len(fr))
    return curve, maxfr

def at(curve, n): return curve[min(n, len(curve)) - 1]
def prio_item(u, d):   # 优先抓"像商品页"的 URL,其次是分页列表,最后是其它;同类里先发现的先抓
    return 0 if u.startswith('/item/') else (1 if '/page/' in u else (2 if u.startswith('/cat/') else 3))
def prio_depth(u, d): return d

print('== 一:同样的抓取预算(只能抓这么多个页面),BFS、DFS、优先级队列各抓到多少个商品页')
BUDS = (100, 300, 1000, 3000, 6000)
print(f'  {"策略":<30}' + ''.join(f'预算{b:>5}' + ' ' * 3 for b in BUDS))
rows = {}
for name, order, pr in (('BFS(先进先出,按层)', 'bfs', None), ('DFS(后进先出)', 'dfs', None), ('优先级:先商品页再列表', 'prio', prio_item), ('优先级:深度小的先(≈BFS)', 'prio', prio_depth)):
    c, mf = crawl(order, 7000, pr); rows[name] = (c, mf)
    print(f'  {name:<26}' + ''.join(f'{at(c, b):>8}/{TOTAL_ITEMS}' for b in BUDS))
print(f'  (商品页共 {TOTAL_ITEMS} 个,全站 {NPAGES} 个页面;预算 {NPAGES} 时三种策略最终都会抓完)')

print('== 二:为了抓满全站,待抓队列(frontier)里最多同时存了多少个 URL')
for name, (c, mf) in rows.items(): print(f'  {name}:待抓队列峰值 {mf}')

print('== 三:爬虫陷阱:低价值的"标签云"互相链接成团,DFS 一头扎进去会怎样(预算 300)')
for name in ('BFS(先进先出,按层)', 'DFS(后进先出)', '优先级:先商品页再列表'):
    c, _ = rows[name]; print(f'  {name}:预算 300 时抓到商品页 {at(c, 300)}')
def tag_pages(order, pr=None, budget=300):
    seen = {'/'}; fr = collections.deque(['/']) if order == 'bfs' else (['/'] if order == 'dfs' else [(pr('/', 0), 0, '/')]); tags = 0; cnt = 1; fetched = 0; depth = {'/': 0}
    while fr and fetched < budget:
        u = fr.popleft() if order == 'bfs' else (fr.pop() if order == 'dfs' else heapq.heappop(fr)[2])
        fetched += 1; tags += u.startswith('/tag')
        for v in LINKS.get(u, []):
            if v in seen: continue
            seen.add(v); depth[v] = depth[u] + 1
            fr.append(v) if order != 'prio' else heapq.heappush(fr, (pr(v, depth[v]), cnt, v)); cnt += 1
    return tags
print(f'  预算 300 里花在标签云上的页数:BFS {tag_pages("bfs")},DFS {tag_pages("dfs")},优先级 {tag_pages("prio", prio_item)}')

print('== 四:DFS 在这个站点上的路径:最先抓到的 15 个 URL')
fr = ['/']; seen = {'/'}; first = []
while fr and len(first) < 15:
    u = fr.pop(); first.append(u)
    for v in LINKS.get(u, []):
        if v not in seen: seen.add(v); fr.append(v)
print('  ' + ' → '.join(first))
purge()
