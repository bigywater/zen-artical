from lib import *
S = SS('g101')
steps = [
    step("同一个值放在不同的上下文里,html/template 的转义结果不同(对比:text/template 对 HTML 文本原样输出 <p><script>alert(1)</script></p>)。HTML 文本:<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>;带引号的属性值:\" 变成 &#34;,onmouseover 留在了引号里;不带引号的属性值:空格变成 &#32;,= 变成 &#61;;href 里的危险协议 javascript:alert(1):整个值被替换成 #ZgotmplZ;href 里的正常 URL:空格变成 %20,& 变成 &amp;;URL 查询参数:& 变成 %26,< 变成 %3c;JavaScript 字符串:值里的 </ 段中的 < 变成 \\u003c,不会提前结束 script 块;数字:var n =  42 ;;对象:被编码成 JSON {\"a\":1,\"b\":\"\\u003cx\\u003e\"};CSS 属性值里的危险内容:ZgotmplZ;HTML 注释里的值:整个注释被删除,只剩 x。", t=tl(S(1)), done=lidx(S(1), 'HTML 文本]', '带引号的属性值]', '不带引号的属性值]', 'JavaScript 里的字符串]', 'JavaScript 里的对象]'), mark=lidx(S(1), '危险协议', 'CSS 属性值]', 'HTML 注释里]', '对比:text/template'), kv=KV([['HTML 文本', '< > & 转成实体'], ['URL', '危险协议被替换成 #ZgotmplZ,正常 URL 做百分号编码'], ['JavaScript', '按 JS 值编码成字符串 / JSON,< > 转成 \\u003c'], ['CSS', '不安全的值被替换成 ZgotmplZ']], ['URL'])),
    step("声明“这段已经安全”的类型会绕过转义。传 string:<p>&lt;b&gt;粗体&lt;/b&gt;</p>;传 template.HTML:<p><b>粗体</b></p>(原样输出);传 template.HTML 但里面有脚本:<p><script>alert(1)</script></p>——调用方负责保证它安全;传 template.URL(\"javascript:alert(1)\") 到 href:不再被替换成 #ZgotmplZ,输出 javascript:alert%281%29(括号被百分号编码,浏览器是否仍会执行它我没有测)。", t=tl(S(2)), mark=lidx(S(2), '传 template.HTML', 'template.URL'), done=lidx(S(2), '传 string'), kv=KV([['string', '被转义'], ['template.HTML', '原样输出,调用方负责'], ['template.URL', '绕过协议检查,仍做编码']], ['template.HTML'])),
    step("模板写法有歧义时,Execute 会报错:{{if}} 的两个分支让上下文不一致(一个在 href 里结束,另一个在 title 里结束):html/template:t:1:5: {{if}} branches end in different contexts: {stateURL …}, {stateAttr …},输出为空;在 script 块里把 {{.}} 当 JS 标识符用:输出 var \"x\" = 1;(值被当成字符串,不是标识符);JS 反引号模板字符串里的 {{.}}(值是 a`b):输出 `a\\u0060b`,反引号被转义。", t=tl(S(3)), mark=lidx(S(3), '分支让上下文不一致'), done=lidx(S(3), '在 <script> 里拼', 'JS 反引号'), kv=KV([['上下文不一致', 'Execute 报错,不输出'], ['JS 标识符', '不能由数据决定,值会变成字符串'], ['JS 模板字符串', '反引号被转义成 \\u0060']], ['上下文不一致'])),
    step("Execute 之后不能再 Parse:已经 Execute 过的 html/template 再调用 Parse,返回 html/template: cannot Parse after Execute。", t=tl(S(4)), mark=lidx(S(4), 'cannot Parse after Execute'), kv=KV([['原因', 'Execute 时才完成上下文转义的分析'], ['做法', '先 Parse 完所有模板,再 Execute']], ['做法'])),
    step("文档(go doc html/template):这个包包装 text/template,所以可以共用模板 API 来解析和执行 HTML 模板且是安全的;文档的示例是 tmpl, err := template.New(\"name\").Parse(...),err = tmpl.Execute(out, data);如果成功,tmpl 现在就是防注入的。", t=tl(S(5)), done=lidx(S(5), 'wraps text/template', 'injection-safe'), kv=KV([['关系', '包装 text/template'], ['保证', 'Parse 与 Execute 都成功后是防注入的']], ['保证'])),
]
A = mkartg('g101', 101, 'Go,html/template,转义,XSS,上下文感知,真实验证,动画演示',
    '在 Go 1.27.1 里实测 html/template 的上下文感知转义:同一个值放在 HTML 文本、属性、URL、JavaScript、CSS、注释里被转义成不同形式(危险协议变成 #ZgotmplZ,JS 值编码成字符串或 JSON,< 变成 \\u003c);template.HTML / template.URL 会绕过转义;{{if}} 分支上下文不一致时 Execute 直接报错;Execute 之后不能再 Parse。',
    'text/template 对 HTML 一无所知,把用户输入原样塞进页面就是 XSS。html/template 按 {{.}} 所在的位置(HTML 文本、属性、URL、JS、CSS)选择转义方式。这篇把同一个恶意输入放进不同位置,逐个看它被改成了什么,以及哪些写法会让保护失效。',
    [('#ZgotmplZ', 'href 里 javascript: 协议的值被替换成的占位符'), ('\\u003c', '放进 script 块的字符串里,< 被编码成这个,避免提前结束 script 块'), ('template.HTML', '传这个类型等于告诉模板“这段已经安全”,会原样输出')],
    [('位置决定转义方式', '<p>同一个 <code>{{.}}</code>,在 HTML 文本里是 <code>&amp;lt;</code> 实体,在属性值里是 <code>&amp;#34;</code>,在 URL 里是百分号编码,在 JS 里是字符串字面量或 JSON,在 CSS 里不安全的值直接变成 <code>ZgotmplZ</code>。<code>text/template</code> 则全部原样输出。</p>'),
     ('绕过', '<p>传 <code>template.HTML</code> 就会原样输出——哪怕里面是 <code>&lt;script&gt;</code>;传 <code>template.URL</code> 会跳过协议检查。这些类型是让你放入已经由你自己净化过的内容,不是让你把用户输入强转成它。</p>'),
     ('歧义时拒绝', '<p>{{if}} 的两个分支把模板带到不同的上下文,<code>Execute</code> 不会猜,而是报错并且不输出任何内容。把 <code>{{.}}</code> 当 JS 标识符用也不行,值只会变成字符串。</p>'),
     ('时机', '<p>转义分析是在第一次 <code>Execute</code> 时完成的,之后再 <code>Parse</code> 会返回 <code>cannot Parse after Execute</code>。</p>'),
     ('文档', '<p>文档的承诺是:<code>Parse</code> 和 <code>Execute</code> 都成功后,模板就是防注入的——但这个承诺不包括上面的绕过类型。</p>')],
    steps,
    [ENV_G + '。每个例子是一个很小的模板加一个恶意输入;输出直接来自 html/template 的 Execute;错误信息超过 120 字符的部分被截断;读过的文档:go doc html/template 开头的一段',
     '没有验证:浏览器是否真的会执行 javascript:alert%281%29、内容安全策略(CSP)与模板转义的配合、模板里用 {{template}} 嵌套时的上下文传播、自定义函数返回值的转义、<style> 块与事件处理属性(onclick 等)里的转义'],
    'html/template')
