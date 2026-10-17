from lib import *
S = SS('m16')
steps = [
    step("people 集合用 $jsonSchema 校验器(name 字符串且长度 ≥ 2,age 为 int 且 0~150,两者必填):{name: \"Alice\", age: 30} 插入成功;{name: \"B\", age: 200, extra: 1} 报 code 121、Document failed validation,errInfo.details 里列出不满足的规则(operatorName: $jsonSchema,schemaRulesNotSatisfied…);缺 age 的文档 missingProperties 是 ['age'];age 为 30.5 时原因是 type did not match,consideredValue 30.5,consideredType double。", t=tl(S(1)), mark=lidx(S(1), 'code: 121', "[ 'age' ]", 'type did not match'), done=lidx(S(1), 'acknowledged: true', 'createCollection'), kv=KV([['错误码', '121 Document failed validation'], ['errInfo.details', '逐条列出哪条规则没通过'], ['int 与 30.5', 'double 不满足 bsonType: int']], ['errInfo.details'])),
    step("validationAction 改成 warn:插入 {name: \"X\", age: 999}(超出范围)照样成功,集合文档数变成 2;mongod 日志里多了 1 条 \"Document would fail validation\"(级别 W,组件 STORAGE,attr 里有 document、errInfo、namespace)。", t=tl(S(2)), mark=lidx(S(2), 'Document would fail validation'), done=lidx(S(2), 'acknowledged: true', '  2'), kv=KV([['warn', '不拒绝,写日志'], ['日志', '\"Document would fail validation\"'], ['attr', 'document / errInfo / namespace']], ['warn'])),
    step("validationLevel:legacy 集合里先有一个合法文档(_id 1)和一个不合法的老文档(_id 2,age 是字符串),之后才加校验器——加校验器并没有拒绝或改动老文档,但 $nor + $jsonSchema 能把它找出来([ 2 ])。strict 下:改 _id 2(不合法的老文档)加字段 note 失败(Document failed validation),把 _id 1 改成不合法也失败;moderate 下:改 _id 2 成功(返回 1),把合法的 _id 1 改成不合法仍然失败。", t=tl(S(3)), mark=lidx(S(3), 'validationLevel: "moderate"', '  1', 'Document failed validation'), done=lidx(S(3), '[ 2 ]', 'strict'), kv=KV([['strict', '所有更新都校验,不合法的老文档也改不了'], ['moderate', '只校验原本合法的文档'], ['已有文档', '加校验器时不会被检查']], ['moderate'])),
    step("strict 下插入 {_id: 3, age: -5} 报 Document failed validation;带 bypassDocumentValidation: true 的插入成功(true);validationLevel 改成 off 后,插入 age 为 \"?\" 的文档也成功。", t=tl(S(4)), mark=lidx(S(4), 'bypassDocumentValidation', 'off'), done=lidx(S(4), 'Document failed validation'), kv=KV([['bypassDocumentValidation', '单次操作绕过校验'], ['validationLevel: off', '整个集合不校验']], ['bypassDocumentValidation'])),
    step("校验器不限于 $jsonSchema:events 用 {$expr: {$lte: [\"$start\", \"$end\"]}},{start: 1, end: 5} 插入成功,{start: 9, end: 5} 失败,errInfo.details 是 operatorName: $expr、reason: expression did not match、expressionResult: false。", t=tl(S(5)), mark=lidx(S(5), 'expression did not match'), done=lidx(S(5), 'true'), kv=KV([['$expr 校验器', '字段之间的比较'], ['失败原因', 'expressionResult: false']], ['$expr 校验器'])),
    step("校验器存在集合选项里:getCollectionInfos 的 options 有 validator、validationLevel: 'strict'、validationAction: 'warn'(上面改过)。insertMany([合法, 不合法, 合法])(把 action 改回 error 后),默认 ordered:遇到第 2 个就停,只插入 1 个、1 个 writeError、位置 1;ordered: false 则插入 2 个、1 个 writeError。", t=tl(S(6)), mark=lidx(S(6), 'inserted: 1', 'inserted: 2'), done=lidx(S(6), 'validationLevel', 'validationAction'), kv=KV([['options', 'validator / validationLevel / validationAction'], ['ordered', '第一个失败就停'], ['unordered', '其它合法的照样插入']], ['ordered'])),
]
A = mkartm('m16', 16, 'MongoDB,Schema校验,jsonSchema,validationLevel,validationAction,真实验证,动画演示',
    '实测 Schema 校验:121 错误里 errInfo.details 逐条说明哪条规则没通过;validationAction 为 warn 时照样写入并在日志里记警告;validationLevel 的 strict 与 moderate 对不合法的老文档的区别;bypassDocumentValidation 与 off;$expr 校验器;insertMany 在 ordered 与 unordered 下的行为。',
    'validationLevel 和 validationAction 到底差在哪?加了校验器之后已有的不合法文档会怎样?这篇用同一个 $jsonSchema 逐个组合试一遍,再看错误详情、日志和 insertMany 的行为。',
    [('121', '不合法文档的错误码,errInfo.details 带每条规则的原因'), ('moderate', '不合法的老文档仍可更新,合法文档被改成不合法仍被拒'), ('2 / 1', 'unordered 的 insertMany([合法, 不合法, 合法]) 插入 2 个、1 个写入错误')],
    [('校验失败的信息', '<p>违反校验器的写入报 121 <code>Document failed validation</code>,<code>errInfo.details</code> 里按规则列出原因:缺少哪个字段、类型不匹配(30.5 是 double,不满足 int)、数值超出范围。</p>'),
     ('validationAction', '<p><code>warn</code> 下文档照样写入,只在 mongod 日志里记一条 “Document would fail validation”,附带文档与原因。</p>'),
     ('validationLevel', '<p>加校验器不会检查已有文档。<code>strict</code> 下连不合法的老文档也不能更新;<code>moderate</code> 下老的不合法文档可以更新,但原本合法的文档被改成不合法仍会被拒。</p>'),
     ('绕过与关闭', '<p>单次操作可以用 <code>bypassDocumentValidation</code> 绕过;<code>validationLevel: off</code> 则整个集合不再校验。</p>'),
     ('$expr 校验器', '<p>校验器也可以是 <code>$expr</code>,用来校验字段之间的关系,失败详情里是 <code>expressionResult: false</code>。</p>'),
     ('配置位置与批量写入', '<p>校验器保存在集合 options 里。<code>insertMany</code> 默认 ordered,遇到不合法的文档就停止;<code>ordered: false</code> 则继续插入其余合法的。</p>')],
    steps,
    [ENV_M + '。校验器统一用同一个 $jsonSchema;日志里的警告通过解析 mongod 的结构化日志得到',
     '没有验证:$jsonSchema 的全部关键字(pattern、enum、oneOf、additionalProperties 等)的行为;校验器对 upsert 与 findAndModify 的作用;分片集合与副本集上 collMod 修改校验器的传播;校验对写入吞吐的开销;validate 命令对已有不合法文档的报告;校验器里的 $where 或 $text 限制'],
    'Schema 校验')
