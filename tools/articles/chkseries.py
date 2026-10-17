"""核对本地库与主题文件:每个系列的文章 = 主题文件里的文章 ∪ legacy_articles.json(主题文件出现之前写的老文章)。
用法(在 zen 根目录):python3 manage.py shell -c "exec(open('tools/articles/chkseries.py').read())"
加 REGEN=1 环境变量会用库里的实际情况重写 legacy_articles.json。"""
import json, os
from tech.models import Series, Article
TP = 'tools/articles/'
PREFIX = {'go': 'go-', 'docker': 'docker-', 'k8s': 'k8s-', 'git': 'git-', 'gin': 'gin-', 'crawler': 'crawler-', 'codec': 'codec-', 'mongo': 'mongo-',
          'scrapy': 'scrapy-', 'grpc': 'grpc-', 'redis': 'redis-', 'zookeeper': 'zookeeper-', 'django': 'django-', 'flask': 'flask-', 'java': 'java-', 'rust': 'rust-', 'rabbitmq': 'rabbitmq-', 'network': 'network-', 'transaction': 'transaction-'}
def urls_of(k):
    d = json.load(open(TP + k + '_topics.json'))
    return {PREFIX[k] + v['slug'] + '.html' for v in d.values()}, len(d)
legacy_file = TP + 'legacy_articles.json'
if os.environ.get('REGEN'):
    out = {}
    for k in PREFIX:
        want, _ = urls_of(k)
        ex = [a for a in Article.objects.filter(series__key=k).order_by('id') if a.url not in want]
        if ex: out[k] = [{'id': a.id, 'url': a.url, 'title': a.title} for a in ex]
    json.dump(out, open(legacy_file, 'w'), ensure_ascii=False, indent=1)
legacy = json.load(open(legacy_file))
bad = 0
for k in PREFIX:
    want, n = urls_of(k)
    have = {a.url for a in Article.objects.filter(series__key=k)}
    old = {x['url'] for x in legacy.get(k, [])}
    miss, unk = want - have, have - want - old
    flag = 'OK ' if not miss and not unk else 'BAD'
    bad += flag == 'BAD'
    print(f'{flag} {k:10} 库 {len(have):3} = 主题 {n:3} + 老文章 {len(old):3}   缺 {len(miss)}  未登记 {len(unk)}')
print('全部一致' if not bad else f'{bad} 个系列不一致')
