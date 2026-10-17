import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m31'); reset()
n = Node('m31'); n.start(); c = n.client(); db = c.test
DOCS = [
 (1, 'The quick brown fox', 'jumps over the lazy dog near the river'),
 (2, 'Running shoes review', 'I run every morning; these shoes ran well and he runs faster'),
 (3, 'Brown bread recipe', 'Mix flour and water. The dough should rest. Quick and easy.'),
 (4, 'Café guide', 'The best cafe in town, a café with coffee and cake'),
 (5, 'Lazy Sunday', 'Nothing to do but sleep. The lazy cat sleeps all day.'),
 (6, 'Quick fox facts', 'A fox is quick. Foxes are quick animals, quick on their feet.'),
 (7, 'Database indexing', 'Indexes make queries fast. An index on a field speeds up queries.'),
 (8, 'Fast queries', 'How to make a query fast using indexes and explain'),
]
db.docs.insert_many([{'_id': i, 'title': t, 'body': b} for i, t, b in DOCS])
print('== 一:建一个文本索引(title 和 body 两个字段);listIndexes 里的 weights、default_language、textIndexVersion')
msh(n, 'db.docs.createIndex({title: "text", body: "text"}, {name: "ft"})')
msh(n, 'db.docs.getIndexes().filter(i => i.name == "ft")')
print('== 二:分词与词干:搜 running、jumped、foxes 能匹配 run/runs、jumps、fox 吗?英文词干把词形变化归一')
msh(n, 'db.docs.find({$text: {$search: "running"}}, {title: 1}).toArray().map(d => d._id + ":" + d.title)')
msh(n, 'db.docs.find({$text: {$search: "jumped"}}, {title: 1}).toArray().map(d => d._id + ":" + d.title)', label='$search: "jumped"    // 文档 1 里是 jumps')
msh(n, 'db.docs.find({$text: {$search: "foxes"}}, {title: 1}).toArray().map(d => d._id + ":" + d.title).sort()', label='$search: "foxes"    // 文档里有 fox 和 foxes')
msh(n, 'db.docs.find({$text: {$search: "ran"}}, {title: 1}).toArray().map(d => d._id + ":" + d.title)', label='$search: "ran"    // 文档 2 里有字面的 ran')
msh(n, 'db.docs.find({$text: {$search: "index"}}, {title: 1}).toArray().map(d => d._id + ":" + d.title)', label='$search: "index"    // 文档里是 Indexes / index / indexing')
msh(n, 'db.docs.find({$text: {$search: "queries"}}, {title: 1}).toArray().map(d => d._id + ":" + d.title)', label='$search: "queries"    // 文档里有 queries / query')
print('== 三:停用词与大小写:the / and / a 这类词不进索引;大小写默认不敏感,重音默认不敏感')
msh(n, 'db.docs.find({$text: {$search: "the"}}).toArray().length', label='$search: "the"')
msh(n, 'db.docs.find({$text: {$search: "the quick"}}, {title: 1}).toArray().map(d => d._id)', label='$search: "the quick"    // 等价于 quick')
msh(n, 'db.docs.find({$text: {$search: "CAFE"}}, {title: 1}).toArray().map(d => d._id + ":" + d.title)', label='$search: "CAFE"    // 大小写、重音都不敏感')
msh(n, 'db.docs.find({$text: {$search: "CAFE", $caseSensitive: true}}, {title: 1}).toArray().map(d => d._id)', label='{$caseSensitive: true}')
msh(n, 'db.docs.find({$text: {$search: "cafe", $diacriticSensitive: true}}, {title: 1}).toArray().map(d => d._id + ":" + d.title)', label='{$search: "cafe", $diacriticSensitive: true}')
print('== 四:多个词是 OR;引号里是短语;减号排除')
msh(n, 'db.docs.find({$text: {$search: "fox lazy"}}, {title: 1}).toArray().map(d => d._id).sort()', label='$search: "fox lazy"    // 多个词按 OR')
msh(n, 'db.docs.find({$text: {$search: "\\"quick brown\\""}}, {title: 1}).toArray().map(d => d._id + ":" + d.title)', label='$search: "\\"quick brown\\""    // 短语')
msh(n, 'db.docs.find({$text: {$search: "quick -fox"}}, {title: 1}).toArray().map(d => d._id + ":" + d.title)', label='$search: "quick -fox"    // 排除含 fox 的')
print('== 五:打分:{$meta: "textScore"} 排序;默认 title 与 body 权重都是 1;把 title 权重设成 10 后标题命中的文档得分大幅提高')
msh(n, 'db.docs.find({$text: {$search: "quick fox"}}, {title: 1, score: {$meta: "textScore"}}).sort({score: {$meta: "textScore"}}).toArray().map(d => d._id + ":" + d.score.toFixed(2))', label='默认权重(title 1、body 1)')
msh(n, 'db.docs.dropIndex("ft"); db.docs.createIndex({title: "text", body: "text"}, {name: "ft2", weights: {title: 10, body: 1}})')
msh(n, 'db.docs.find({$text: {$search: "quick fox"}}, {score: {$meta: "textScore"}}).sort({score: {$meta: "textScore"}}).toArray().map(d => d._id + ":" + d.score.toFixed(2))', label='title 权重 10')
print('== 六:限制:一个集合只能有一个文本索引;$text 必须有文本索引;聚合里 $match + $text 要放第一个阶段')
msh(n, 'try { db.docs.createIndex({body: "text"}, {name: "ft3"}) } catch (e) { e.message.slice(0, 230) }')
msh(n, 'try { db.nodocs.insertOne({a: "x"}); db.nodocs.find({$text: {$search: "x"}}).toArray() } catch (e) { e.message.slice(0, 120) }', label='没有文本索引的集合 $text')
msh(n, 'try { db.docs.aggregate([{$match: {_id: {$gt: 0}}}, {$match: {$text: {$search: "fox"}}}]).toArray() } catch (e) { e.message.slice(0, 140) }', label='$text 不在 pipeline 第一阶段')
msh(n, 'db.docs.find({$text: {$search: "fox"}}).explain("executionStats").queryPlanner.winningPlan.stage + " / " + (function(){ var s = db.docs.find({$text: {$search: "fox"}}).explain("executionStats").queryPlanner.winningPlan; while (s.inputStage) s = s.inputStage; return s.stage + " " + s.indexName })()', label='explain 的计划')
n.stop()
