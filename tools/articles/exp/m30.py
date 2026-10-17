import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m30'); reset()
n = Node('m30'); n.start(); c = n.client(); db = c.test
N = 300000; r = random.Random(30)
L = 'abcdefghijklmnopqrstuvwxyz'
def nm(i):
    s = ''.join(r.choice(L) for _ in range(r.randrange(6, 12)))
    return s.capitalize() if i % 4 == 0 else s
docs = [{'_id': i, 'name': nm(i)} for i in range(N)]
for i in range(0, N, 30000): db.t.insert_many(docs[i:i + 30000], ordered=False)
db.t.create_index('name')
db.t.insert_many([{'_id': N + i, 'name': w} for i, w in enumerate(['abcdef', 'abcxyz', 'Abcdef', 'xabcx', 'abd', 'abc'])])
cnt = db.t.count_documents
print(f'== 一:数据:{N:,} 个随机小写字母单词(每 4 个有一个首字母大写),name 上有普通索引;再放 6 个固定的词。几个正则的命中数')
for pat in ['^abc', '^abc$', 'abc', '^abc.*', '^(abc|abd)']:
    print(f'  /{pat}/: {cnt({"name": {"$regex": pat}}):>6,} 个')
print(f'  /^abc/i: {cnt({"name": {"$regex": "^abc", "$options": "i"}}):>6,} 个')
print('== 二:前缀锚定的正则可以走索引范围:/^abc/ 的索引范围是 ["abc", "abd"),只检查命中的键;不锚定的正则要扫整个索引')
def ex_(pat, opts=''):
    q = json.dumps({'name': {'$regex': pat, **({'$options': opts} if opts else {})}})
    return f'ex(db.t.find({q}).explain("executionStats"))'
for pat, opts, lab_, nt in [('^abc', '', '/^abc/', '锚定前缀'), ('abc', '', '/abc/', '不锚定'), ('^abc', 'i', '/^abc/i', '不区分大小写'), ('^.*abc', '', '/^.*abc/', '^ 后面是 .*,等于不锚定'), ('^abc.*', '', '/^abc.*/', '前缀后面跟 .*')]:
    msh(n, EXJS + ex_(pat, opts), label='db.t.find({name: ' + lab_ + '})', note=nt, n=12)
print('== 三:索引范围长什么样:看 explain 的 indexBounds')
def bounds(pat, opts=''):
    q = json.dumps({'name': {'$regex': pat, **({'$options': opts} if opts else {})}})
    return f'var e = db.t.find({q}).explain("queryPlanner"); var s = e.queryPlanner.winningPlan; while (s.inputStage) s = s.inputStage; JSON.stringify(s.indexBounds)'
for pat, opts in [('^abc', ''), ('^abc$', ''), ('^(abc|abd)', ''), ('abc', ''), ('^abc', 'i')]:
    msh(n, bounds(pat, opts), label=f'/{pat}/{opts} 的 indexBounds')
print('== 四:大小写不敏感的前缀:/^abc/i 扫整个索引。办法一:另存一个小写字段并建索引;办法二:collation 索引(但 $regex 不使用 collation)')
db.t.update_many({}, [{'$set': {'name_lc': {'$toLower': '$name'}}}]); db.t.create_index('name_lc')
msh(n, EXJS + 'ex(db.t.find({name_lc: {$regex: "^abc"}}).explain("executionStats"))', label='db.t.find({name_lc: /^abc/})', note='name_lc 是 name 的小写副本', n=12)
print(f'  命中 {cnt({"name_lc": {"$regex": "^abc"}})} 个(= /^abc/i 的 {cnt({"name": {"$regex": "^abc", "$options": "i"}})} 个)')
db.ci.create_index('name', name='name_ci', collation={'locale': 'en', 'strength': 2}); db.ci.insert_many([{'_id': d['_id'], 'name': d['name']} for d in docs[:100000]])
msh(n, EXJS + 'ex(db.ci.find({name: /^abc/i}).collation({locale: "en", strength: 2}).explain("executionStats"))', label='db.ci.find({name: /^abc/i}).collation({locale: "en", strength: 2})', note='ci 集合的索引带 collation', n=12)
print('== 五:耗时(9 次中位数):各种写法')
def t(q): return bench(lambda: list(db.t.find(q, {'_id': 1})), 9)
rows = [('/^abc/', {'name': {'$regex': '^abc'}}), ('/^abc$/(等值)', {'name': {'$regex': '^abc$'}}), ('/abc/(不锚定)', {'name': {'$regex': 'abc'}}), ('/^abc/i', {'name': {'$regex': '^abc', '$options': 'i'}}), ('name_lc /^abc/', {'name_lc': {'$regex': '^abc'}}), ('{name: "abc"} 等值', {'name': 'abc'})]
for nm_, q in rows: print(f'  {nm_:<20}{fm(t(q)):>10}')
print('== 六:$in 里放正则,以及两个前缀并列')
msh(n, EXJS + 'ex(db.t.find({name: {$in: [/^abcd/, /^abce/]}}).explain("executionStats"))', label='db.t.find({name: {$in: [/^abcd/, /^abce/]}})', n=12)
msh(n, bounds('^(abcd|abce)'), label='/^(abcd|abce)/ 的 indexBounds')
n.stop()
