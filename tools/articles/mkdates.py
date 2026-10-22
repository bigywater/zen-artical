"""生成 dates.json:文章 url -> 写作日期。日期取该文章 art/<token>.py 的创建时间(本地时区);一次性冻结到 dates.json,之后 lib.render 和 publish.py 都读它,不再用写死的 DATE。
用法: python3 mkdates.py   (只读 art/ 和 counts.json,只写 dates.json;已有的条目会被覆盖)"""
import sys, os, re, json, glob, datetime, pathlib, importlib.util
HERE = pathlib.Path(__file__).parent; os.chdir(HERE); sys.path.insert(0, str(HERE))
import lib
counts = json.load(open('counts.json')); out = {}; bad = []
_src = open('lib.py').read()
SER_BY_LETTER = {'u': 'rust', 'z': 'zookeeper', 'r': 'redis', 'd': 'django', 'j': 'java', 'x': 'spring'}
for fn, ser in re.findall(r"def mkart(\w+)\(.*?series='(\w+)'\)", _src, re.S): SER_BY_LETTER[fn] = ser
TOPICS_BY_SER = {'redis': lib.RTOPICS, 'django': lib.DTOPICS, 'zookeeper': lib.ZTOPICS, 'rust': lib.UTOPICS, 'flask': lib.FTOPICS, 'java': lib.JTOPICS, 'go': lib.GTOPICS, 'docker': lib.CTOPICS, 'k8s': lib.KTOPICS, 'gin': lib.NTOPICS, 'git': lib.ITOPICS, 'mongo': lib.MTOPICS, 'crawler': lib.PTOPICS, 'codec': lib.ETOPICS, 'scrapy': lib.YTOPICS, 'grpc': lib.HTOPICS, 'rabbitmq': lib.QTOPICS, 'network': lib.WTOPICS, 'transaction': lib.TTOPICS, 'microservice': lib.VTOPICS, 'spring': lib.XTOPICS}
for p in sorted(glob.glob('art/*.py')):
    b = os.path.basename(p); m = re.match(r'([a-z])(\d+)\.py$', b)
    if not m: continue
    try:
        spec = importlib.util.spec_from_file_location('a_' + b[:-3], p); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        url, title, page = lib.render(mod.A, counts)
    except BaseException as e:
        if 'out 里有' in repr(e) or isinstance(e, FileNotFoundError):   # 旧文章(Flask、Rust 等):out 的小节数后来变了,art 没法再执行,但 url 只取决于系列和编号
            ser = SER_BY_LETTER.get(m.group(1))
            if ser: out[f'{ser}-{TOPICS_BY_SER[ser][int(m.group(2))]["slug"]}.html'] = datetime.datetime.fromtimestamp(os.stat(p).st_birthtime).date().isoformat(); continue
        bad.append((b, repr(e)[:80])); continue
    out[url] = datetime.datetime.fromtimestamp(os.stat(p).st_birthtime).date().isoformat()
# 没有 art 文件的旧文章(Java 的一部分、Kafka、ClickHouse、Python 的一部分):取库里 created_at 的本地日期,只补库里日期还是旧常量 2026-09-29 的
sys.path.insert(0, '/Users/w/Desktop/zen'); os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zen.settings')
import django; django.setup()
from tech.models import Article
fb = 0
for a in Article.objects.filter(date='2026-09-29'):
    if a.url not in out: out[a.url] = a.created_at.astimezone().date().isoformat(); fb += 1
print('用 created_at 补了', fb, '篇')
json.dump(dict(sorted(out.items())), open('dates.json', 'w'), ensure_ascii=False, indent=0)
print(len(out), 'urls;失败', len(bad), bad[:5])
