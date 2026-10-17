from lib import *
S = SS('m24')
steps = [
    step("唯一索引 email_1 上:插入没有 email 的文档 {_id: 1} 成功;再插一个没有 email 的 {_id: 2} 报 E11000 ... dup key: { email: null };显式 {_id: 3, email: null} 同样冲突;两个不同的非空 email 都成功。——缺失字段被当成 null。", t=tl(S(1)), mark=lidx(S(1), 'E11000'), done=lidx(S(1), 'ok', '  true'), kv=KV([['缺失字段', '按 null 进唯一索引'], ['第二个缺失 / null', 'E11000 dup key: { email: null }']], ['缺失字段'])),
    step("唯一 + sparse:三个缺失 email 的文档一起插入成功(缺失的不进索引);显式 null 的第一个成功,第二个报 E11000 ... dup key: { email: null }——显式 null 仍是一个值。", t=tl(S(2)), mark=lidx(S(2), 'E11000', '_id: 5'), done=lidx(S(2), 'ok', 'unique: true, sparse: true'), kv=KV([['sparse + unique', '缺失的文档不限数量'], ['显式 null', '只能有一个']], ['显式 null'])),
    step("唯一 + partialFilterExpression {email: {$type: \"string\"}}:缺失 ×2、null ×2 都能插入(不参与唯一性);两个相同的字符串 email \"a@x.com\" 的第二个报 E11000 ... dup key: { email: \"a@x.com\" };集合里最后共 5 个文档(前 4 个 + 第一个 a@x.com)。", t=tl(S(3)), mark=lidx(S(3), 'E11000'), done=lidx(S(3), 'ok', '  5'), kv=KV([['部分唯一索引', '只有字符串 email 参与'], ['缺失 / null', '不限数量']], ['部分唯一索引'])),
    step("复合唯一索引 {a, b}:{a: 1}(b 缺失)成功;{a: 1, b: null} 与之冲突,E11000 dup key: { a: 1, b: null };{a: 1, b: 2} 成功;{}(a、b 都缺失)成功,再来一个 a、b 都缺失的冲突,dup key: { a: null, b: null }。", t=tl(S(4)), mark=lidx(S(4), 'E11000'), done=lidx(S(4), 'ok'), kv=KV([['缺失按 null', '逐个字段'], ['冲突', '整个组合相同']], ['冲突'])),
    step("已有重复数据时建唯一索引失败:集合里 k 有两个 'x'、两个缺失,createIndex 报 code 11000 和 Index build failed ... E11000 duplicate key error;用 $group 加 $match n > 1 找出重复:{_id: null, ids: [3, 4], n: 2} 与 {_id: 'x', ids: [1, 2], n: 2}。", t=tl(S(5)), mark=lidx(S(5), 'code: 11000', 'ids: [ 3, 4 ]', "ids: [ 1, 2 ]"), done=lidx(S(5), 'Index build failed'), kv=KV([['建索引', '有重复就失败'], ['找重复', '$group + $match n > 1'], ['缺失', '也会被分成 null 一组']], ['找重复'])),
    step("E11000 错误里有什么:code 11000,keyPattern { email: 1 },keyValue { email: null },message 带集合名、索引名 email_1、dup key;复合索引的冲突 keyValue 是 { a: 1, b: 2 }。", t=tl(S(6)), mark=lidx(S(6), 'keyValue'), done=lidx(S(6), 'code: 11000', 'keyPattern'), kv=KV([['keyPattern', '哪个索引'], ['keyValue', '冲突的值(缺失显示成 null)'], ['message', '集合名 + 索引名 + dup key']], ['keyValue'])),
]
A = mkartm('m24', 24, 'MongoDB,唯一索引,null,缺失字段,E11000,sparse,真实验证,动画演示',
    '实测唯一索引遇到 null 和缺失字段:缺失按 null 算,第二个缺失或 null 的文档就报 E11000;唯一加 sparse 允许任意多个缺失但显式 null 仍然冲突;唯一加部分索引(字符串 email)缺失和 null 都不限;复合索引逐字段按 null;已有重复数据时建索引失败及找重复的办法。',
    '唯一索引上第二个没有这个字段的文档能不能插入?显式 null 呢?这篇用同一个 email 字段在四种唯一索引设置下逐个试,再看复合索引和已有重复数据的情形。',
    [('E11000', '唯一索引上第二个缺失 email 的文档就报这个错,dup key: { email: null }'), ('3 个缺失 + 1 个 null', '唯一 + sparse 的索引上能同时存在的缺失与显式 null 文档数'), ('5 个', '唯一部分索引(只管字符串 email)的集合最后的文档数,缺失与 null 不限')],
    [('缺失就是 null', '<p>普通唯一索引里,字段缺失与显式 <code>null</code> 都按 <code>null</code> 进索引,所以只能有一个。</p>'),
     ('唯一 + sparse', '<p>缺失字段的文档不进索引,可以有任意多个;显式 <code>null</code> 仍是一个值,只能有一个。</p>'),
     ('唯一 + 部分索引', '<p>用 <code>partialFilterExpression: {email: {$type: "string"}}</code> 让只有字符串参与唯一性,缺失和 null 都不限制。</p>'),
     ('复合索引', '<p>复合唯一索引逐个字段把缺失当 null,整个组合相同才冲突;<code>{a: 1}</code> 与 <code>{a: 1, b: null}</code> 冲突。</p>'),
     ('已有重复数据', '<p>集合里已有重复值时建唯一索引会失败;用 <code>$group</code> 加 <code>$match</code> 找出重复的值和 _id,缺失的文档会被分在 null 一组。</p>'),
     ('错误信息', '<p>E11000 的 <code>keyPattern</code>、<code>keyValue</code> 指出是哪个索引、哪个值冲突;缺失字段的冲突值显示为 <code>null</code>。</p>')],
    steps,
    [ENV_M + '。每个设置都在新建的集合上验证,错误信息来自 mongosh',
     '没有验证:分片集合上的唯一索引限制(后面单独一篇);唯一索引对 upsert 并发的影响(下面几篇);collation 唯一索引;多键唯一索引(同一文档内重复元素不冲突);写关注对唯一性检查的影响'],
    '唯一索引与 null')
