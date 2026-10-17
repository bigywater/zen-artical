import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m7'); reset()
n = Node('m7'); n.start(); c = n.client(); db = c.test
def ls(sub='', pat=None):
    out = []
    root = n.db / sub if sub else n.db
    for p in sorted(root.iterdir(), key=lambda p: p.name):
        st = p.stat()
        if pat and not re.search(pat, p.name): continue
        out.append((p.name + ('/' if p.is_dir() else ''), st.st_size))
    return out
def show(items, w=44):
    for nm, sz in items: print(f'  {nm:<{w}}{sz:>14,}')
print('== 一:一个全新的 mongod(还没有建任何用户集合)的 dbpath 里有什么')
show(ls())
msh(n, 'db.getSiblingDB("admin").aggregate([{$listCatalog: {}}, {$project: {_id: 0, ns: 1, ident: 1}}, {$sort: {ns: 1}}])')
print('== 二:建一个集合和两个二级索引之后,多出来的文件:每个集合、每个索引各占一个 .wt 文件')
before = {nm for nm, _ in ls()}
db.users.insert_many([{'_id': i, 'name': f'user{i}', 'age': i % 80, 'city': f'c{i % 50}'} for i in range(20000)])
db.users.create_index('age'); db.users.create_index([('city', 1), ('name', 1)])
c.admin.command('fsync')
show([(nm, sz) for nm, sz in ls() if nm not in before])
st = db.command('collStats', 'users')
print(f'  collStats 里的 wiredTiger.uri = {st["wiredTiger"]["uri"]}')
for nm, d in st['indexDetails'].items(): print(f'  索引 {nm:<12} → {d["uri"]}')
print('== 三:文件名里的数字不是顺序,是 WiredTiger 内部的 ident;用 $listCatalog 把集合/索引和 ident 对上')
msh(n, 'db.getSiblingDB("admin").aggregate([{$listCatalog: {}}, {$match: {db: "test", name: "users"}}, {$project: {_id: 0, ns: 1, ident: 1, idxIdent: 1}}])')
print('== 四:几个文本/小文件:WiredTiger(版本)、mongod.lock(进程号)、WiredTiger.turtle(元数据引导)、storage.bson(存储引擎选项)')
print('  WiredTiger  的内容:'); [print('    ' + l) for l in (n.db / 'WiredTiger').read_text().splitlines()]
print(f'  mongod.lock 的内容: {(n.db / "mongod.lock").read_text().strip()!r}(mongod 进程号 {n.p.pid})')
turtle = (n.db / 'WiredTiger.turtle').read_text().splitlines()
print(f'  WiredTiger.turtle 共 {len(turtle)} 行,前面的几行:')
for l in turtle[:6]: print('    ' + l[:110])
print('  storage.bson 解码:', bson.decode((n.db / 'storage.bson').read_bytes()))
print('== 五:journal 目录与 diagnostic.data 目录')
show(ls('journal'), 30)
jf = [p for p in (n.db / 'journal').iterdir() if p.name.startswith('WiredTigerLog')]
for p in jf: print(f'  {p.name}: 文件大小 {p.stat().st_size:,},实际占用磁盘 {p.stat().st_blocks * 512:,}(du 看到的)')
show(ls('diagnostic.data'), 30)
print('== 六:删除集合之后,对应的 .wt 文件消失;_mdb_catalog.wt、sizeStorer.wt 等全局文件一直在')
files_before = {nm for nm, _ in ls()}
db.users.drop(); time.sleep(2); c.admin.command('fsync'); time.sleep(1)
files_after = {nm for nm, _ in ls()}
print(f'  drop 之前 {len(files_before)} 个条目,之后 {len(files_after)} 个;消失的: {sorted(files_before - files_after)}')
print(f'  新增的: {sorted(files_after - files_before)}')
n.stop()
