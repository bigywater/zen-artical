import sys, os, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests, charset_normalizer, lxml.html
tee('p15')
TXT = '爬虫工程:编码识别示例,中文网页常见的 GBK 与 UTF-8,镕。'
def page(meta='', body_txt=TXT): return f'<html><head>{meta}<title>t</title></head><body><p>{body_txt}</p></body></html>'

routes = {}
def server(h):
    p = h.path.split('?')[0]
    ct, data = routes[p]
    h.reply(200, data, headers={'Content-Type': ct} if ct else {})

def ptxt(r): return re.search(r'<p>(.*?)</p>', r.text, re.S).group(1) if '<p>' in r.text else r.text[:40]
def good(s): return s == TXT
with Srv(server) as sv:
    def run(label, path, ct, data, note=''):
        routes[path] = (ct, data)
        r = requests.get(sv.url(path))
        t = ptxt(r)
        lx = lxml.html.fromstring(r.content).findtext('.//p')
        print(f'  {label}')
        print(f'      Content-Type={ct!r};r.encoding={r.encoding!r};r.apparent_encoding={r.apparent_encoding!r}')
        lx = lx or ''
        print(f'      r.text 的正文:开头 {t[:8]!r} 结尾 {t[-4:]!r} → {"正确" if good(t) else "乱码/不一致"};lxml.html.fromstring(r.content):开头 {lx[:8]!r} 结尾 {lx[-4:]!r} → {"正确" if good(lx) else "乱码/不一致"}')
    print('== 一:Content-Type 里有没有 charset,requests 的 r.encoding 就不同')
    u8 = page().encode('utf-8'); gb = page().replace('镕', '').encode('gbk') if False else None
    run('UTF-8 页面,Content-Type: text/html; charset=utf-8', '/a', 'text/html; charset=utf-8', u8)
    run('UTF-8 页面,Content-Type: text/html(没写 charset)', '/b', 'text/html', u8)
    run('UTF-8 页面,Content-Type: application/octet-stream(不是 text/*,没写 charset)', '/b2', 'application/octet-stream', u8)
    run('UTF-8 页面,有 <meta charset="utf-8">,Content-Type 没写 charset', '/c', 'text/html', page('<meta charset="utf-8">').encode('utf-8'))
    run('GBK 页面,<meta charset="gbk">,Content-Type 没写 charset', '/d', 'text/html', page('<meta charset="gbk">').encode('gbk'))
    run('GBK 页面,Content-Type: text/html; charset=gbk', '/e', 'text/html; charset=gbk', page().encode('gbk'))
    print('== 二:声明和实际不一致时')
    run('响应头说 gbk,页面实际是 UTF-8(<meta charset="utf-8">)', '/f', 'text/html; charset=gbk', page('<meta charset="utf-8">').encode('utf-8'))
    run('响应头说 utf-8,页面实际是 GBK(<meta charset="gbk">)', '/g', 'text/html; charset=utf-8', page('<meta charset="gbk">').encode('gbk'))
    run('响应头没写,<meta charset="gb2312">,页面实际是 GBK 且含 GB2312 里没有的字', '/h', 'text/html', page('<meta charset="gb2312">').encode('gbk'))
    r = requests.get(sv.url('/h'))
    for enc in ('gb2312', 'gbk', 'gb18030'):
        dec = r.content.decode(enc, errors='replace'); body = dec[dec.index('<p>') + 3:dec.index('</p>')]
        print(f'      用 {enc} 解码这段 GBK 字节(errors="replace"):结尾 {body[-4:]!r},是否与原文一致:{body == TXT}')
    print('== 三:修正的几种办法(UTF-8 页面,响应头只写 text/html)')
    r = requests.get(sv.url('/b'))
    print(f'  默认 r.text → {ptxt(r)[:20]!r}')
    r.encoding = r.apparent_encoding; print(f'  r.encoding = r.apparent_encoding({r.apparent_encoding!r}) 之后 → {ptxt(r)[:20]!r}')
    r = requests.get(sv.url('/b')); print(f'  自己对字节解码 r.content.decode("utf-8") → {r.content.decode("utf-8")[r.content.decode("utf-8").index("<p>") + 3:][:20]!r}')
    r = requests.get(sv.url('/b')); doc = lxml.html.fromstring(r.content)
    print(f'  交给 lxml 字节(它自己看 meta;这个页面没有 meta)→ {doc.findtext(".//p")[:20]!r}')
    try: lxml.html.fromstring('<?xml version="1.0" encoding="utf-8"?><html><body><p>x</p></body></html>')
    except Exception as e: print(f'  把 r.text(字符串)交给 lxml,如果文档带 XML 编码声明 → {type(e).__name__}: {str(e)[:60]}')
    print('== 四:UTF-8 BOM')
    routes['/bom'] = ('text/html; charset=utf-8', b'\xef\xbb\xbf' + u8)
    r = requests.get(sv.url('/bom')); print(f'  响应体以 BOM 开头:r.encoding={r.encoding!r},r.text 的前 3 个字符 {r.text[:3]!r}(\\ufeff 是 BOM),r.content.decode("utf-8-sig")[:3]={r.content.decode("utf-8-sig")[:3]!r}')

print('== 五:猜编码有多准:charset_normalizer(requests 用的 apparent_encoding)对不同语言、不同长度的文本')
print(f'  requests 当前用的检测库:{requests.compat.chardet.__name__} {getattr(requests.compat.chardet, "__version__", "")}')
SS = ['今天天气很好,我们一起去公园散步。', '数据库的索引可以加速查询,但会增加写入成本。', '网络爬虫需要遵守网站的访问规则。', '这个函数返回一个包含所有链接的列表。', '服务器返回了错误的状态码,需要重试。', '请在晚上十点之前提交你的作业。', '我们的团队正在开发一个新的搜索引擎。', '浏览器会根据响应头决定如何解码页面。', '咖啡店的老板每天早上六点开门营业。', '学习编程最重要的是多写代码多思考。']
TS = ['今天天氣很好,我們一起去公園散步。', '資料庫的索引可以加速查詢,但會增加寫入成本。', '網路爬蟲需要遵守網站的存取規則。', '這個函式回傳一個包含所有連結的清單。', '伺服器回傳了錯誤的狀態碼,需要重試。', '請在晚上十點之前提交你的作業。', '我們的團隊正在開發一個新的搜尋引擎。', '瀏覽器會根據回應標頭決定如何解碼頁面。', '咖啡店的老闆每天早上六點開門營業。', '學習程式設計最重要的是多寫程式多思考。']
JS = ['今日は天気がいいので、公園へ散歩に行きます。', 'データベースのインデックスは検索を速くします。', 'ウェブクローラーはサイトのルールを守る必要があります。', 'この関数はすべてのリンクのリストを返します。', 'サーバーがエラーを返したので、再試行します。', '今夜十時までに宿題を提出してください。', '私たちのチームは新しい検索エンジンを開発しています。', 'ブラウザは応答ヘッダーに従ってページをデコードします。', '喫茶店の店主は毎朝六時に店を開けます。', 'プログラミングを学ぶには、たくさん書いて考えることが大切です。']
KS = ['오늘은 날씨가 좋아서 공원으로 산책하러 갑니다.', '데이터베이스 인덱스는 검색 속도를 높여 줍니다.', '웹 크롤러는 사이트의 규칙을 지켜야 합니다.', '이 함수는 모든 링크의 목록을 반환합니다.', '서버가 오류를 반환해서 다시 시도합니다.', '오늘 밤 열 시까지 숙제를 제출해 주세요.', '우리 팀은 새로운 검색 엔진을 개발하고 있습니다.', '브라우저는 응답 헤더에 따라 페이지를 디코딩합니다.', '카페 주인은 매일 아침 여섯 시에 문을 엽니다.', '프로그래밍을 배우려면 많이 쓰고 많이 생각해야 합니다.']
FS = ['Aujourd\'hui, il fait très beau et nous allons nous promener au parc.', 'L\'index d\'une base de données accélère les requêtes mais ralentit les écritures.', 'Un robot d\'indexation doit respecter les règles du site.', 'Cette fonction renvoie la liste de tous les liens trouvés.', 'Le serveur a renvoyé une erreur, il faut réessayer plus tard.', 'Veuillez rendre votre devoir avant dix heures ce soir.', 'Notre équipe développe un nouveau moteur de recherche.', 'Le navigateur décode la page selon les en-têtes de la réponse.', 'Le patron du café ouvre la boutique à six heures chaque matin.', 'Apprendre à programmer, c\'est écrire beaucoup et réfléchir beaucoup.']
CASES = [('简体中文', SS, ['utf-8', 'gbk', 'gb18030']), ('繁体中文', TS, ['utf-8', 'big5']), ('日文', JS, ['utf-8', 'shift_jis', 'euc_jp']), ('韩文', KS, ['utf-8', 'euc_kr']), ('法文(带重音)', FS, ['utf-8', 'latin-1'])]
print(f'  {"语言":<12}{"真实编码":<10}' + ''.join(f'{n:>2} 句    ' for n in (1, 3, 10)))
wrong = 0; total = 0
for lang, sents, encs in CASES:
    for enc in encs:
        row = []
        for n in (1, 3, 10):
            raw = ''.join(sents[:n]).encode(enc)
            g = charset_normalizer.from_bytes(raw).best(); guess = g.encoding if g else None
            norm = lambda x: x.replace('_', '-').lower() if x else x
            okk = (guess is not None) and (norm(guess) == norm(enc) or (enc == 'latin-1' and norm(guess) in ('cp1252', 'iso8859-1', 'latin-1', 'cp1250', 'iso8859-15')))
            total += 1; wrong += (not okk)
            row.append(f'{guess}' + ('' if okk else ' ✗'))
        print(f'  {lang:<10}{enc:<12}' + ''.join(f'{r:<10}' for r in row))
print(f'  共 {total} 个组合,猜得和真实编码不同的有 {wrong} 个(✗ 标出;GBK 文本被猜成 gb18030 之类的父集不一定造成乱码,下面再检查解出来的文字是否一致)')
bad = 0; badlist = []
for lang, sents, encs in CASES:
    for enc in encs:
        for n in (1, 3, 10):
            raw = ''.join(sents[:n]).encode(enc); g = charset_normalizer.from_bytes(raw).best()
            if (str(g) if g else None) != ''.join(sents[:n]): bad += 1; badlist.append(f'{lang}/{enc}/{n} 句 被猜成 {g.encoding if g else None}')
print(f'  检测出编码后用它解码,得到的文字与原文不一致的有 {bad} 个(共 {total} 个):' + '; '.join(badlist))
purge()
