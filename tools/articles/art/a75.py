import json
from lib import *
txt = out('75').splitlines()
J = json.load(open('out/75.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())

calls, hooks, s = J['calls'], J['hooks'], J['s']
FL = lambda cur, done=(): {'nodes': [['Python 对象', ''], ['dumps(default=…)', ''], ['JSON 文本', ''], ['loads(object_hook=…)', ''], ['Python 对象', '']], 'cur': cur, 'done': list(done)}
ex = {
 0: "dumps 开始遍历 {'id':7, 'tags':{'b','a'}, 'owner':User, 'score':9.5}:int、str、float 是内置支持的,不会触发 default。",
 1: "遇到 set:JSON 没有集合类型 → 第一次调用 default,我们把它转成排好序的 list。",
 2: "遇到 User 对象 → default 把它转成一个 dict(带 __user__ 标记),这个 dict 里的 joined 还是 date。",
 3: "dumps 继续遍历这个新 dict,遇到 datetime.date → 再调用一次 default,转成 {'__date__': …}。",
}
steps = []; ev = []
steps.append(step(ex[0], fl=FL([1], [0]), ev={'lines': ['(还没有任何 default 调用)'], 'cur': []}, out={'text': '(输出尚未生成)'}))
for i, c in enumerate(calls):
    ev.append(c)
    steps.append(step(ex[i + 1], fl=FL([1], [0]), ev={'lines': list(ev), 'cur': [len(ev) - 1]}, out={'text': '(输出尚未生成)'}))
steps.append(step("dumps 完成:三个自定义类型各触发了一次 default,共 3 次;文本里全是 JSON 认识的东西。", fl=FL([2], [0, 1]), ev={'lines': list(ev), 'cur': []}, out={'text': s}))
lx = {
 0: "loads 解析时,每个 JSON 对象(dict)解析完立刻交给 object_hook——最内层的 {'__date__':…} 最先被调用,我们把它还原成 date。",
 1: "接着是中间层 {'__user__':…, 'joined': date}:此时里面的 joined 已经是 date 了(由内到外),还原成 User。",
 2: "最后是最外层的整个 dict:owner 已经是 User。注意 tags 仍然是 list,set 没法自动还原。",
}
ev2 = []
for i, h in enumerate(hooks):
    ev2.append(h)
    steps.append(step(lx[i], fl=FL([3], [0, 1, 2]), ev={'lines': list(ev2), 'cur': [len(ev2) - 1]}, out={'text': s}))
steps.append(step("loads 返回:owner 是 User、joined 是 date;但 tags 是 list,不是 set——往返之后类型不一定回得来。", fl=FL([4], [0, 1, 2, 3]), ev={'lines': list(ev2), 'cur': []}, out={'text': "{'id': 7, 'tags': ['a', 'b'], 'owner': User('ann'), 'score': 9.5}"}))

A = dict(
    n=75,
    tags='Python,标准库,序列化,真实验证,动画演示',
    desc='本机真实记录 json 自定义序列化的调用顺序:default 只在遇到不认识的对象时触发(本例 3 次:set、User、date),object_hook 由内到外触发;并实测往返丢类型(tuple→list、int 键→str)、NaN 输出非法 JSON、重复键静默覆盖、default 返回自身抛 Circular reference。',
    lead='<code>json.dumps</code> 遇到自定义对象只会抛 TypeError。要让它工作,得理解两个钩子——<code>default</code> 和 <code>object_hook</code>——到底在什么时候、按什么顺序被调用。这篇把每一次调用都记了下来。',
    facts=[('3 次', '一份数据里 set、User、date 各触发一次 default'), ('由内到外', 'object_hook 的调用顺序:最内层的 dict 最先'), ('tuple → list', '往返后类型对不上,== 也是 False')],
    body=[
        sec('做的事', '一个含 set、自定义类、date 的字典,先 dumps 再 loads',
            src('实验脚本(节选)', '''data = {"id": 7, "tags": {"b", "a"},
        "owner": User("ann", datetime.date(2026, 1, 2)), "score": 9.5}

def default(o):
    calls.append(repr(o))                  # 记录每次调用
    if isinstance(o, User): return {"__user__": True, "name": o.name, "joined": o.joined}
    if isinstance(o, datetime.date): return {"__date__": o.isoformat()}
    if isinstance(o, (set, frozenset)): return sorted(o)
    raise TypeError(...)                   # 别的类型继续报错

s = json.dumps(data, default=default)'''),
            term('', block('== 一', '== 二'))),
        sec('验证一:default 只在「不认识」时才被调用', '', term('', block('== 二', '== 三')),
            '<p>int、str、float 从头到尾没有触发 <code>default</code>;整个字典里只有三个对象触发了它,顺序是字典的遍历顺序(tags → owner → owner 里的 joined)。有一点容易忽略:<code>default</code> 返回的东西会被<b>继续遍历</b>——User 被转成 dict 后,dict 里的 <code>joined</code> 又触发了一次 default(date)。所以 default 不用递归处理,只需要处理「一层」。</p>'),
        sec('验证二:object_hook 由内到外', '', term('', block('== 三', '== 四')),
            '<p>解析时每个 JSON 对象一旦解析完就调用一次 <code>object_hook</code>,所以最内层的日期 dict 最先被调用,等到调用 User 那一层时,<code>joined</code> 已经是 <code>datetime.date</code> 了。这是好事:你不需要自己递归。但也意味着 <code>object_hook</code> 每个 dict 都会碰到——包括最普通的、跟你的类型无关的 dict——所以必须先认出自己的标记(<code>__user__</code>),不认识就原样返回。另外注意 tags 变成了 list:JSON 里没有 set,标记都没留,还原不回去。</p>'),
        sec('验证三:往返之后,类型不一定回得来', '', term('', block('== 四', '== 五')),
            '<ul><li>tuple 序列化成数组,读回来是 list,和原值 <code>==</code> 是 False。</li><li>字典的 int 键在 JSON 里必须是字符串,读回来键变成了 <code>\'1\'</code>。</li><li><code>bytes</code>、<code>Decimal</code> 默认直接 TypeError,需要自己在 <code>default</code> 里选表示方式。</li><li><code>float(\'nan\')</code> 输出的是 <code>NaN</code>——<b>这不是合法 JSON</b>(标准 JSON 没有 NaN),想拦住得用 <code>allow_nan=False</code>,它会抛 ValueError。</li><li>2**70 这样的大整数没有精度损失,这是 Python 侧的结果。</li><li><code>1e400</code> 会被读成 <code>inf</code>,重复键<b>静默</b>覆盖(后者赢),想看到全部重复键要用 <code>object_pairs_hook</code>。</li></ul>'),
        sec('验证四:default 返回不认识的东西,会被拦下', '', term('', block('== 五', 'zzzz')),
            '<p>Python 用一个「正在序列化的对象」集合检测循环。<code>default</code> 返回自己,或返回一个里面还包着自己的 list,都会得到 <code>Circular reference detected</code>。3.14 里异常还带了 <code>__notes__</code>,标出是在序列化哪一层(<code>list item 0</code> → <code>Node object</code>)时出的错,排查时很有用。</p>'),
        sec('分步演示:一次 dumps、一次 loads 里所有钩子的调用', '每一次调用都是上面实验里真实记录到的',
            demo('default 与 object_hook 的调用顺序',
                 [('fl', 'flow', '现在处在哪个阶段'), ('ev', 'term', '钩子调用记录'), ('out', 'text', 'JSON 文本 / 结果')],
                 steps, '当前这一次钩子调用')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>json</code>、<code>datetime</code>、<code>decimal</code>',
          '没有验证:C 加速的编码器与纯 Python 编码器在 default 调用次数上是否完全一致、<code>JSONEncoder</code> 子类写法与 <code>default</code> 参数的差异、超大数据下的性能'],
)
