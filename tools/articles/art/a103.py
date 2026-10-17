import json
from lib import *
txt = out('103').splitlines(); R = json.load(open('out/103.json')); C = R['counts']; t1, t2, t3 = R['t']
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
lv = [('默认配置', 0), ('--check-untyped-defs', C['--check-untyped-defs']), ('--disallow-untyped-defs', C['--disallow-untyped-defs']), ('--strict', C['--strict'])]
FL = lambda cur, done=(): {'nodes': [['默认配置', '不检查无注解函数'], ['check-untyped-defs', '检查函数体'], ['disallow-untyped-defs', '要求写签名'], ['strict', '全部严格'], ['按模块分档', '旧宽新严']], 'cur': cur, 'done': list(done)}
bars = lambda k, cur: {'items': [[n, max(v, 0.3), f'{v} 个错误'] for n, v in lv[:k]], 'max': 14, 'cur': cur}
steps = [
    step("一个「旧项目」:legacy/ 下的函数都没有类型注解,里面藏着 bug(例如 int + \"1\");newcode/ 是新写的、有类型的代码,会调用 legacy。默认配置的 mypy:0 个错误——因为它默认不检查没有注解的函数体。", fl=FL([0]), b=bars(1, [0]), kv={'items': [['legacy/orders.py:11', 'total + "1"(int + str)'], ['mypy 默认', 'Success: no issues found in 6 source files']], 'hl': ['mypy 默认']}),
    step(f"打开 --check-untyped-defs:开始检查无注解函数的函数体,{C['--check-untyped-defs']} 个错误——旧代码里真实存在的 int + str,以及新代码里 c.hits + \"1\"(此前 c.hits 是 Any,不会报)。", fl=FL([1], [0]), b=bars(2, [1]), kv={'items': [['legacy/orders.py:11', 'Unsupported operand types for + ("int" and "str")'], ['newcode/service.py:13', '同类错误(因为 hits 现在被推断成 int)']], 'hl': ['legacy/orders.py:11']}),
    step(f"再加 --disallow-untyped-defs:每个没有注解的函数都是错误,{C['--disallow-untyped-defs']} 个。这一档不是「发现 bug」,而是「要求补签名」。", fl=FL([2], [0, 1]), b=bars(3, [2]), kv={'items': [['no-untyped-def', '10']], 'hl': ['no-untyped-def']}),
    step(f"--strict:{C['--strict']} 个错误 = 10 个 no-untyped-def + 2 个 operator + 2 个 no-untyped-call(typed 代码调用无类型函数)。对一个旧项目直接开 strict,一次面对全部问题。", fl=FL([3], [0, 1, 2]), b=bars(4, [3]), kv={'items': [['no-untyped-def', '10'], ['operator', '2'], ['no-untyped-call', '2']], 'hl': ['no-untyped-call']}),
    step("Any 会传染:没有注解的函数,参数和返回值都是 Any。reveal_type(safe_int(\"3\")) 是 Any,reveal_type(merge(...)) 也是 Any——调用它的新代码得到的所有结果都被「放过」了。", fl=FL([0]), kv={'items': [['reveal_type(safe_int)', 'def (x: Any, default: Any =) -> Any'], ['reveal_type(safe_int("3"))', 'Any'], ['reveal_type(merge(...))', 'Any']], 'hl': ['reveal_type(safe_int("3"))']}),
    step("渐进式方案:mypy.ini 里全局 check_untyped_defs、legacy.* ignore_errors、newcode.* strict。旧模块的问题被暂时压住,新模块严格——结果 3 个错误,全在新代码里(2 个是新代码调用了无类型的旧函数)。", fl=FL([4], [0, 1, 2, 3]), kv={'items': [['newcode/service.py:5', 'Call to untyped function "order_total" in typed context'], ['newcode/service.py:9', 'Call to untyped function "safe_int" in typed context'], ['newcode/service.py:13', 'int + str']], 'hl': ['newcode/service.py:5']}),
    step("接入的成本:增量缓存。60 个模块冷启动 %.2f s;无改动再跑 %.2f s;改一个文件再跑 %.2f s。" % (t1, t2, t3), fl=FL([4]), b={'items': [['冷启动', t1, f'{t1:.2f} s'], ['再跑(无改动)', t2, f'{t2:.2f} s'], ['改 1 个文件', t3, f'{t3:.2f} s']], 'max': t1, 'cur': [0]}),
]
A = dict(
    n=103,
    tags='Python,类型检查,mypy,工程化,真实验证,动画演示',
    desc=f'本机 mypy 2.3.1 在一个旧项目上真实逐档收紧:默认配置 0 个错误、--check-untyped-defs {C["--check-untyped-defs"]} 个(暴露 int + str 的真实 bug)、--disallow-untyped-defs {C["--disallow-untyped-defs"]} 个、--strict {C["--strict"]} 个;无注解函数返回 Any 让新代码的错误被放过;按模块设置「legacy 忽略、newcode strict」得到 3 个错误;增量缓存下重跑 {t2:.2f} s。',
    lead='给一个没有类型注解的旧项目接上 mypy,直接 <code>--strict</code> 会淹没在几百个错误里,直接默认配置又什么都查不到。这篇造了一个「旧项目 + 新代码」的小环境,把 mypy 的严格程度一档一档拧紧,看每一档到底多出了什么错误,以及一个实用的「旧宽新严」渐进方案。',
    facts=[('0 → 2 → 10 → 14', '默认 / check-untyped-defs / disallow-untyped-defs / strict 下的错误数'), ('Any', '无注解函数的参数和返回值都是 Any,新代码调用它得不到任何检查'), (f'{t1:.2f} → {t2:.2f} s', '60 个模块的 mypy 冷启动与增量重跑')],
    body=[
        sec('做的事:一个旧项目加一点新代码', '', src('legacy/orders.py(节选,没有任何注解)', '''def order_total(order):
    total = 0
    for item in order["items"]:
        total = total + item["price"] * item["qty"]
    return total + "1"                     # 旧代码里的 bug: int + str

class Cache:
    def __init__(self):
        self.data = {}
        self.hits = 0'''),
            src('newcode/service.py(节选,有注解)', '''def discounted(order: dict[str, object], rate: float) -> float:
    base: float = order_total(order)
    return base * rate

def cache_hits(c: Cache) -> int:
    return c.hits + "1"                    # 新代码里自己写错的'''),
            term('', txt[0])),
        sec('验证一:默认配置什么都看不到', '', term('', block('== 一', '== 二')),
            '<p>默认配置下 mypy <b>不检查没有类型注解的函数的函数体</b>(它们被当作「动态代码」)。所以 <code>order_total</code> 里的 <code>int + "1"</code> 完全不报;连新代码里的 <code>c.hits + "1"</code> 也没报——因为 <code>Cache.__init__</code> 没有注解,里面的 <code>self.hits = 0</code> 没有被推断,<code>c.hits</code> 是 <code>Any</code>。</p>'),
        sec('验证二:逐档收紧', '', term('', block('== 二', '== 三')),
            f'<p><b>--check-untyped-defs</b>:开始检查无注解函数的函数体,{C["--check-untyped-defs"]} 个错误立刻出现——旧代码里那个 <code>int + str</code>,以及新代码里的 <code>c.hits + "1"</code>(现在 <code>hits</code> 被推断成 int 了)。这一档最有价值:<b>不需要改任何代码就能发现真正的 bug</b>。<b>--disallow-untyped-defs</b> 变成 {C["--disallow-untyped-defs"]} 个:每个没写签名的函数都算错误,这是「要求补注解」的一档。<b>--strict</b> 是 {C["--strict"]} 个,里面 10 个 <code>no-untyped-def</code>、2 个 <code>operator</code>、2 个 <code>no-untyped-call</code>(有类型的代码调用了无类型的函数)。</p>'),
        sec('验证三:Any 传染', '', term('', block('== 三', '== 四')),
            '<p>没有注解的函数,参数和返回值都是 <code>Any</code>。<code>safe_int("3")</code>、<code>merge(...)</code>、<code>Cache().get("k")</code> 得到的全是 <code>Any</code>。所以新代码把 <code>safe_int</code> 的结果标成 <code>str</code>(其实是 int)——不报错,因为 mypy 没有信息可对比。<b>Any 不是「未知类型」,而是「关闭检查」</b>,每多一个无类型的函数,就多一个检查不到的洞。</p>'),
        sec('验证四:旧宽新严', '按模块设置不同的严格程度', src('mypy.ini', '''[mypy]
check_untyped_defs = true

[mypy-legacy.*]
ignore_errors = true

[mypy-newcode.*]
strict = true'''), term('', block('== 四', '== 五')),
            '<p>整体打开 <code>check_untyped_defs</code>,旧模块 <code>ignore_errors</code>(暂时压住,不必一次修完),新模块 <code>strict</code>。3 个错误全在新代码里:一个是它自己的 <code>int + str</code>,另两个是「在有类型的上下文里调用了无类型的旧函数」——这是渐进式的关键信号:新代码想严格,就会推着你去给它依赖的旧函数补类型。补完一个,就把对应模块从 <code>ignore_errors</code> 名单里拿掉。</p>'),
        sec('验证五:type: ignore 与 warn_unused_ignores', '', term('', block('== 五', '== 六')),
            '<p>三行里有一行的 <code># type: ignore</code> 是多余的(<code>y: int = 1</code> 本来就对)。默认配置下多余的 ignore 不会被发现,还悄悄留着;打开 <code>--warn-unused-ignores</code> 立刻报出来。渐进接入时会大量使用 <code>ignore</code>,这个开关能保证它们不会变成永远不清理的死注释;写 <code>[assignment]</code> 这样带错误码的形式,可以避免误吞别的错误。</p>'),
        sec('验证六:增量缓存', '', term('', block('== 六', 'zzzz')),
            f'<p>60 个小模块:冷启动 {t1:.2f} s,无改动再跑 {t2:.2f} s,只改一个文件再跑 {t3:.2f} s;缓存目录只有 2.6 MB。这个规模太小,不能推到大项目,但说明缓存命中后开销很低,把 mypy 放进 pre-commit 或 CI 不会拖垮反馈速度。</p>'),
        sec('分步演示:把严格程度一档一档拧紧', '每一档的错误数来自上面的真实运行',
            demo('渐进式接入 mypy', [('fl', 'flow', '严格程度'), ('b', 'bars', '各档错误数 / 耗时'), ('kv', 'kv', '具体是什么')], steps, '当前档位')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,mypy 2.3.1(compiled);缓存计时取一次冷启动、一次热重跑、一次改动后重跑',
          '没有验证:真实大型项目上的错误数量级、第三方库缺少类型存根(<code>ignore_missing_imports</code>)、<code>--warn-return-any</code>、mypy daemon(dmypy)、与 pyright 的差异'],
)
