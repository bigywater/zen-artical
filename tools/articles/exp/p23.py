import sys, os, io, hashlib, zlib, re, concurrent.futures as cf; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import lxml.html, lxml.etree as etree
tee('p23')
ROW = '<tr class="r"><td><a href="/item/%d">商品 %d</a></td><td class="p">¥%d.00</td><td><span>库存 %d</span></td></tr>\n'
HTML = ('<html><head><title>列表</title></head><body><table>' + ''.join(ROW % (i, i, i % 97, i % 13) for i in range(8000)) + '</table></body></html>').encode()
XML = ('<root>' + ''.join('<item id="%d"><name>商品 %d</name><price>%d.00</price></item>' % (i, i, i % 97) for i in range(9000)) + '</root>').encode()
d = pdir('p23'); (d / 'page.html').write_bytes(HTML); (d / 'data.xml').write_bytes(XML)
BIG = os.urandom(8 << 20)
TREES = [lxml.html.fromstring(HTML) for _ in range(16)]
TEXT = HTML.decode()

W = {
 'lxml.html.fromstring(bytes)': lambda i: lxml.html.fromstring(HTML),
 'etree.HTML(bytes)(C 层 HTML 解析器)': lambda i: etree.HTML(HTML),
 'lxml.html.parse(文件路径)': lambda i: lxml.html.parse(str(d / 'page.html')),
 'lxml.html.parse(BytesIO)': lambda i: lxml.html.parse(io.BytesIO(HTML)),
 'etree.fromstring(XML bytes)': lambda i: etree.fromstring(XML),
 'etree.parse(XML 文件路径)': lambda i: etree.parse(str(d / 'data.xml')),
 'xpath(已解析的树,每线程用自己的树)': lambda i: TREES[i % 16].xpath('//a/@href'),
 'cssselect 风格:iter + 逐元素读 text': lambda i: [e.text for e in TREES[i % 16].iter('a')],
 'etree.tostring(序列化)': lambda i: etree.tostring(TREES[i % 16]),
 '对照:hashlib.sha256(8 MiB)': lambda i: hashlib.sha256(BIG).digest(),
 '对照:zlib.compress(8 MiB)': lambda i: zlib.compress(BIG, 1),
 '对照:re.findall(Python 正则,文本)': lambda i: re.findall(r'href="(/item/\d+)"', TEXT),
 '对照:纯 Python 循环': lambda i: sum(j * j for j in range(400000)),
}

def run(fn, tasks, threads):
    ts = []
    for _ in range(3):
        t0 = time.perf_counter()
        if threads == 1:
            for i in range(tasks): fn(i)
        else:
            with cf.ThreadPoolExecutor(threads) as ex: list(ex.map(fn, range(tasks)))
        ts.append(ms(t0))
    return median(ts)

GROUPS = [
 ('一:先用对照组校准:已知释放 GIL 的 C 扩展(sha256、zlib)与已知持有 GIL 的 Python 代码(纯循环、正则),同样 16 个任务用 1、2、4、8 个线程跑,加速比 = 1 线程总耗时 / N 线程总耗时(本机 %d 个核心)' % os.cpu_count(),
  ['对照:hashlib.sha256(8 MiB)', '对照:zlib.compress(8 MiB)', '对照:纯 Python 循环', '对照:re.findall(Python 正则,文本)']),
 ('二:lxml 的 HTML 解析(不同入口、不同输入方式)', ['lxml.html.fromstring(bytes)', 'etree.HTML(bytes)(C 层 HTML 解析器)', 'lxml.html.parse(文件路径)', 'lxml.html.parse(BytesIO)']),
 ('三:lxml 的 XML 解析', ['etree.fromstring(XML bytes)', 'etree.parse(XML 文件路径)']),
 ('四:解析之后的操作:xpath、遍历取值、序列化(每个任务用自己已解析好的树)', ['xpath(已解析的树,每线程用自己的树)', 'cssselect 风格:iter + 逐元素读 text', 'etree.tostring(序列化)']),
]
for title, names in GROUPS:
    print('== ' + title)
    print(f'  {"任务":<36}{"单次":>8}{"1线程":>9}{"2线程":>8}{"4线程":>8}{"8线程":>8}')
    for name in names:
        fn = W[name]; fn(0)
        one = median([(lambda t0: (fn(0), ms(t0))[1])(time.perf_counter()) for _ in range(5)])
        base = run(fn, 16, 1)
        sp = [base / run(fn, 16, n) for n in (2, 4, 8)]
        print(f'  {name:<36}{one:>6.1f} ms{base:>6.0f} ms{sp[0]:>7.2f}x{sp[1]:>7.2f}x{sp[2]:>7.2f}x')
purge()
