import sys, os, time, json, re, urllib.request, urllib.parse; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z102'); R = {}
def get(url):
    for i in range(3):
        try: return json.load(urllib.request.urlopen(url, timeout=40))
        except Exception as e: err = e; time.sleep(1)
    raise err
def versions(ga):
    d = get('https://api.deps.dev/v3/systems/maven/packages/' + urllib.parse.quote(ga, safe=''))
    return [(v['versionKey']['version'], v['publishedAt']) for v in d['versions']]
def zkdep(ga, v):
    d = get(f'https://api.deps.dev/v3/systems/maven/packages/{urllib.parse.quote(ga, safe="")}/versions/{v}:dependencies')
    z = [n for n in d['nodes'] if n['versionKey']['name'] == 'org.apache.zookeeper:zookeeper']
    cu = sorted({n['versionKey']['name'].split(':')[1] + ' ' + n['versionKey']['version'] for n in d['nodes'] if n['versionKey']['name'].startswith('org.apache.curator:')})
    return (z[0]['versionKey']['version'], z[0]['relation']) if z else None, cu
def latest(ga):
    vs = [(v, t) for v, t in versions(ga) if re.fullmatch(r'\d+(\.\d+){1,2}', v)]
    vs.sort(key=lambda x: x[1]); return vs[-1]
print('== 一:各项目「最新正式版」在 Maven 依赖图里有没有 ZooKeeper、是哪个版本、是直接依赖还是传递依赖(数据来自 deps.dev 对 Maven Central 依赖图的解析;只说明声明的依赖,不说明运行时是否必须使用)')
projects = ['org.apache.kafka:kafka_2.13', 'org.apache.hbase:hbase-client', 'org.apache.hadoop:hadoop-common', 'org.apache.solr:solr-solrj-zookeeper', 'org.apache.flink:flink-runtime', 'org.apache.storm:storm-client', 'org.apache.pulsar:pulsar-metadata', 'org.apache.bookkeeper:bookkeeper-server', 'org.apache.accumulo:accumulo-core', 'org.apache.curator:curator-framework', 'org.apache.dubbo:dubbo', 'org.apache.druid:druid-processing', 'org.apache.hive:hive-metastore', 'org.springframework.cloud:spring-cloud-zookeeper-core']
rows = []
print(f'  {"项目":<52}{"最新版":<12}{"ZooKeeper 依赖":<24}Curator')
for ga in projects:
    try:
        v, t = latest(ga); z, cu = zkdep(ga, v)
        rows.append(dict(ga=ga, v=v, t=t[:10], zk=z, cu=cu)); print(f'  {ga:<52}{v:<12}{(z[0] + " " + z[1]) if z else "(无)":<24}{", ".join(c.replace("curator-", "") for c in cu) or "-"}')
    except Exception as e: rows.append(dict(ga=ga, err=str(e)[:80])); print(f'  {ga:<52}查询失败 {str(e)[:60]}')
R['rows'] = rows
print()
print('== 二:Kafka 不同版本对 ZooKeeper 的依赖(ZooKeeper 模式 → KRaft 的转变在依赖图上的体现)')
kv = [v for v, t in versions('org.apache.kafka:kafka_2.13') if re.fullmatch(r'(2\.8|3\.0|3\.3|3\.6|3\.7|3\.8|3\.9|4\.0|4\.1)\.\d+', v)]
byminor = {}
for v in kv: byminor.setdefault('.'.join(v.split('.')[:2]), []).append(v)
kr = []
for m, vs in sorted(byminor.items(), key=lambda x: [int(p) for p in x[0].split('.')]):
    v = sorted(vs, key=lambda s: [int(p) for p in s.split('.')])[-1]
    try: z, cu = zkdep('org.apache.kafka:kafka_2.13', v); kr.append(dict(v=v, zk=z)); print(f'  kafka_2.13 {v:<8}→ ZooKeeper {(z[0] + " (" + z[1] + ")") if z else "无"}')
    except Exception as e: print('  ', v, '失败', str(e)[:50])
R['kafka'] = kr
print()
print('== 三:ZooKeeper 自己的发布节奏(Maven Central 上的正式版)')
zv = [(v, t[:10]) for v, t in versions('org.apache.zookeeper:zookeeper') if re.fullmatch(r'3\.(7|8|9)\.\d+', v)]
zv.sort(key=lambda x: x[1]); print('  3.7 / 3.8 / 3.9 系列最近的 8 个版本:', [f'{v} ({t})' for v, t in zv[-8:]]); R['zkvers'] = zv[-8:]
save('z102', R); os._exit(0)
