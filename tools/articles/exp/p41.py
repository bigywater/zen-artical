import sys, os, json, random, threading, urllib.parse as up, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests
tee('p41')
PAGE = 20; N0 = 1000

class Store:
    def __init__(self, seed):
        self.items = list(range(1, N0 + 1)); self.next_id = N0 + 1; self.lock = threading.Lock(); self.rng = random.Random(seed)
        self.snapshots = {}; self.deleted = set(); self.stop = False
    def mutate(self, mode, interval=0.004):
        while not self.stop:
            time.sleep(interval)
            with self.lock:
                if mode in ('insert', 'both'):
                    self.items.append(self.next_id); self.next_id += 1
                if mode in ('delete', 'both') and len(self.items) > 100:
                    victim = self.items[self.rng.randrange(0, len(self.items))]       # 删掉随机一条(不管新旧)
                    self.items.remove(victim); self.deleted.add(victim)

def make_server(st):
    def fn(h):
        u = up.urlsplit(h.path); q = dict(up.parse_qsl(u.query)); p = u.path
        with st.lock:
            items = sorted(st.items)             # 按 id 升序的当前全部数据
            if p == '/offset_new':                # 偏移量分页,最新的在前
                off = int(q['offset']); page = list(reversed(items))[off:off + PAGE]
            elif p == '/offset_old':              # 偏移量分页,最旧的在前
                off = int(q['offset']); page = items[off:off + PAGE]
            elif p == '/cursor':                  # 键集(游标)分页:id 小于 before 的 PAGE 条,最新的在前;不给 before 就从最新的开始
                before = int(q.get('before', st.next_id + 1)); page = [i for i in reversed(items) if i < before][:PAGE]
            elif p == '/snapshot':                # 快照分页:第一次请求时冻结当前数据,游标指向快照里的位置
                tok = q.get('token')
                if tok is None: tok = str(len(st.snapshots)); st.snapshots[tok] = list(reversed(items))
                snap = st.snapshots[tok]; off = int(q.get('offset', 0)); page = snap[off:off + PAGE]
                return h.reply(200, json.dumps(dict(items=page, token=tok)).encode())
            else: return h.reply(404, b'')
        h.reply(200, json.dumps(dict(items=page)).encode())
    return fn

def crawl(sv, kind, delay=0.01):
    s = requests.Session(); got = []; pages = 0
    if kind in ('offset_new', 'offset_old'):
        off = 0
        while True:
            d = s.get(sv.url(f'/{kind}?offset={off}')).json()['items']; pages += 1
            if not d: break
            got += d; off += PAGE; time.sleep(delay)
    elif kind == 'cursor':
        before = None
        while True:
            d = s.get(sv.url('/cursor' + (f'?before={before}' if before else ''))).json()['items']; pages += 1
            if not d: break
            got += d; before = d[-1]; time.sleep(delay)
    else:
        tok = None; off = 0
        while True:
            r = s.get(sv.url('/snapshot' + (f'?token={tok}&offset={off}' if tok is not None else ''))).json(); pages += 1
            if not r['items']: break
            tok = r['token']; got += r['items']; off += PAGE; time.sleep(delay)
    return got, pages

def run(kind, mode, seed=1):
    st = Store(seed)
    with Srv(make_server(st)) as sv:
        th = None
        if mode != 'none': th = threading.Thread(target=st.mutate, args=(mode,), daemon=True); th.start()
        got, pages = crawl(sv, kind)
        st.stop = True
        if th: th.join()
        survivors = set(range(1, N0 + 1)) - st.deleted                # 初始的、整个抓取期间都没被删除的数据
        dup = len(got) - len(set(got)); missed = len(survivors - set(got))
        return dict(total=len(got), dup=dup, missed=missed, pages=pages, added=st.next_id - 1 - N0, deleted=len(st.deleted))

KINDS = [('offset_new', '偏移量分页,最新在前'), ('offset_old', '偏移量分页,最旧在前'), ('cursor', '游标(键集)分页,最新在前'), ('snapshot', '服务器快照分页')]
SECTIONS = (('一:数据没有变化(基准)', 'none'), ('二:抓取期间不断新增数据(每 4 ms 在末尾新增一条,新增的是最新的)', 'insert'), ('三:抓取期间不断随机删除数据(每 4 ms 删一条)', 'delete'), ('四:同时新增和删除', 'both'))
for title, mode in SECTIONS:
    print('== ' + title)
    if mode == 'none': print('  (初始 1000 条数据,每页 20 条,约 50 页;每页之间客户端间隔 10 ms。"漏掉"=初始就有、整个抓取期间都没被删除、却从没返回过的数据条数;"重复"=返回的总条数减去不同的条数)')
    print(f'  {"分页方式":<24}{"请求页数":>8}{"返回条数":>8}{"重复":>6}{"漏掉":>6}   期间新增/删除')
    for kind, lab in KINDS:
        rs = [run(kind, mode, seed) for seed in (1, 2, 3)]
        r = rs[1]
        print(f'  {lab:<20}{r["pages"]:>8}{r["total"]:>8}{r["dup"]:>6}{r["missed"]:>6}   {r["added"]} / {r["deleted"]}' + (f'   (3 次的 重复/漏掉:{[(x["dup"], x["missed"]) for x in rs]})' if mode != 'none' else ''))

print('== 五:确定性的小演示(没有线程):100 条数据 id 1..100,每页 5 条;读完第 2 页之后,数据发生变化,再读第 3 页会得到什么')
def demo(label, change):
    st = Store(1); st.items = list(range(1, 101)); st.next_id = 101
    with Srv(make_server(st)) as sv:
        global PAGE
        old = PAGE; PAGE = 5
        try:
            res = {}
            for kind in ('offset_new', 'offset_old', 'cursor'):
                st.items = list(range(1, 101)); st.next_id = 101
                p2 = requests.get(sv.url(f'/{kind}?offset=5')).json()['items'] if kind != 'cursor' else requests.get(sv.url('/cursor?before=96')).json()['items']
                change(st)
                p3 = requests.get(sv.url(f'/{kind}?offset=10')).json()['items'] if kind != 'cursor' else requests.get(sv.url(f'/cursor?before={p2[-1]}')).json()['items']
                res[kind] = (p2, p3)
        finally: PAGE = old
    print(f'  {label}:')
    for kind, (p2, p3) in res.items(): print(f'      {kind:<11}第 2 页 {p2},变化后的第 3 页 {p3}')
demo('读完第 2 页后,新增 3 条(id 101–103)', lambda st: [st.items.append(st.next_id + i) for i in range(3)])
demo('读完第 2 页后,删除 3 条已读过的条目', lambda st: [st.items.remove(x) for x in (100, 99, 98)])
purge()
