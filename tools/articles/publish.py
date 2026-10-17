"""用法: python3 publish.py 71 72 ...   构建 html 到 html/ 并(加 --save)写入 zen 库。"""
import sys, os, importlib.util, pathlib, re, json, subprocess
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import lib
os.chdir(HERE)

args = [a for a in sys.argv[1:] if not a.startswith('--')]
save = '--save' in sys.argv
(HERE / 'html').mkdir(exist_ok=True)

if save:
    sys.path.insert(0, '/Users/w/Desktop/zen')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zen.settings')
    import django; django.setup()
    from django.conf import settings
    from django.urls import set_urlconf
    from django.db import transaction
    set_urlconf(settings.SITE_URLCONF_MAP['tech'])
    from tech.models import Article, Series
    counts = {s.key: s.articles.count() for s in Series.objects.all()}
    from tech import static_site as _ss
    if '--lists-only' in sys.argv:  # 只重建首页/分类分页(约 30 秒),不发布文章
        print('lists', _ss.rebuild_lists()); sys.exit(0)
    if '--rebuild' not in sys.argv:  # 默认不在每次保存后重建列表页(很慢),批量发布完后用 --lists-only 补一次
        _ss.schedule_rebuild = lambda: None
else:
    counts = json.load(open(HERE / 'counts.json'))

built = []
for tok in args:
    n = int(tok.lstrip('rdazufjgcknlmpeshqwt'))
    p = HERE / 'art' / (f'{tok[0]}{n}.py' if tok[0] in 'rdzufjgcknlmpeshqwt' else f'a{n}.py')
    spec = importlib.util.spec_from_file_location(f'a{tok}', p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    url, title, page = lib.render(m.A, counts)
    (HERE / 'html' / url).write_text(page)
    # 校验: 内联脚本语法
    scripts = re.findall(r'<script>(.*?)</script>', page, re.S)
    for i, s in enumerate(scripts):
        (HERE / 'chk.js').write_text(s)
        r = subprocess.run(['node', '--check', str(HERE / 'chk.js')], capture_output=True, text=True)
        assert r.returncode == 0, (url, r.stderr)
    built.append((n, url, title, m.A, page))
    print('built', n, url, len(page), 'bytes')

if save:
    with transaction.atomic():
        for n, url, title, A, page in built:
            s = Series.objects.get(key=A.get('series', 'python'))
            tags = A.get('tags', 'Python,标准库,真实验证,动画演示')
            obj, created = Article.objects.update_or_create(url=url, defaults=dict(
                title=title, series=s, tags=tags, date=lib.DATE, description=A['desc'], content_html=page))
            print('saved', url, 'created' if created else 'updated')
