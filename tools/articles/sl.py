"""Scrapy 实验辅助:所有请求只发给本机自己起的测试服务器(pl.Srv,127.0.0.1,端口 9960+),不访问任何真实网站。
实验脚本用 stmp_venv/bin/python 运行(Scrapy 2.19 / Twisted 26.4 装在这个临时虚拟环境里)。
- sdir(name):清空并返回 stmp/<name>/;write(d, fname, code):写文件(自动 dedent)
- scrapy(d, *args):在目录 d 里跑 `python -m scrapy ...`,返回 (退出码, 合并后的输出(已 tidy), 耗时秒)
- runspider(d, code, settings={}, args=()):把 code 写成 spider.py 再 `scrapy runspider`;默认关掉 telnet 和 remote control(2.19 新增的 HTTP 控制端口)、日志格式去掉时间戳
- stats(out):把 'Dumping Scrapy stats' 之后的字典解析出来;ev(d):读 spider 里用 EV 前缀写的 events.jsonl
- 每个实验开头 tee('sN');临时文件用完 purge_s()(只删 stmp/)"""
import os, sys, subprocess, shutil, pathlib, textwrap, json, re, ast, datetime, time
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from pl import *   # Srv / RawSrv / tee / free_port / median / pr / ms / gz / make_cert ...
SD = HERE / 'stmp'; SD.mkdir(exist_ok=True)
SPY = str(HERE / 'stmp_venv' / 'bin' / 'python')
LOGFMT = '[%(name)s] %(levelname)s: %(message)s'

# 写在 spider 文件开头的小工具:EV(**kw) 往 events.jsonl 追加一行(带相对时间),用来记录引擎内部发生的事
PRE = '''
import time, json, os
_T0 = time.perf_counter()
def EV(**kw):
    kw['t'] = round((time.perf_counter() - _T0) * 1000, 1)
    with open('events.jsonl', 'a') as f: f.write(json.dumps(kw, ensure_ascii=False) + '\\n')
'''


def stidy(t):
    t = re.sub(r'\x1b\[[0-9;]*m', '', t)
    t = t.replace(str(HERE / 'stmp_venv' / 'lib'), '<venv>').replace(str(SD), '<stmp>').replace(str(HERE), '<实验目录>')
    t = re.sub(r'<venv>/python3\.\d+/site-packages', '<site-packages>', t)
    t = re.sub(r'0x[0-9a-f]{6,}', '0x…', t)
    t = re.sub(r'/private/tmp/claude-501/[^\s"\':]*?/scratchpad', '<scratch>', t)
    return '\n'.join(l.rstrip() for l in t.rstrip().split('\n')).strip('\n')


def sdir(name):
    d = SD / name
    shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True); return d


def write(d, fname, code):
    p = pathlib.Path(d) / fname; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(code).lstrip('\n')); return p


def scrapy(d, *args, timeout=120, env=None, inp=None):
    e = dict(os.environ)
    for k, v in (env or {}).items():
        if v is None: e.pop(k, None)   # env 里值为 None 表示从环境里删掉这个变量
        else: e[k] = v
    e['PYTHONDONTWRITEBYTECODE'] = '1'; e['PYTHONUNBUFFERED'] = '1'; e.pop('PYTHONPATH', None)
    t0 = time.perf_counter()
    try:
        r = subprocess.run([SPY, '-m', 'scrapy', *map(str, args)], cwd=d, capture_output=True, text=True, timeout=timeout, env=e, input=inp)
        rc, out = r.returncode, (r.stdout + ('\n' if r.stdout and r.stderr else '') + r.stderr)
    except subprocess.TimeoutExpired as x:
        rc, out = -9, ((x.stdout or b'').decode() if isinstance(x.stdout, bytes) else (x.stdout or '')) + ((x.stderr or b'').decode() if isinstance(x.stderr, bytes) else (x.stderr or '')) + '\n[超时被杀]'
    return rc, stidy(out), time.perf_counter() - t0


def runspider(d, code, settings=None, args=(), fname='spider.py', pre=True, **kw):
    st = {'LOG_FORMAT': LOGFMT, 'TELNETCONSOLE_ENABLED': '0', 'REMOTE_CONTROL_ENABLED': '0'}; st.update(settings or {})
    body = textwrap.dedent(code).lstrip('\n')
    write(d, fname, (PRE if pre else '') + body)
    a = ['runspider', fname]
    for k, v in st.items(): a += ['-s', f'{k}={v}']
    return scrapy(d, *a, *args, **kw)


def py(d, code, fname='run.py', timeout=120, env=None):
    """在虚拟环境里直接跑一段 Python(不是 scrapy 命令),返回 (退出码, 输出, 耗时)。"""
    write(d, fname, PRE + textwrap.dedent(code).lstrip('\n') if False else code)
    e = dict(os.environ); e.update(env or {}); e['PYTHONDONTWRITEBYTECODE'] = '1'; e['PYTHONUNBUFFERED'] = '1'; e.pop('PYTHONPATH', None)
    t0 = time.perf_counter()
    try:
        r = subprocess.run([SPY, fname], cwd=d, capture_output=True, text=True, timeout=timeout, env=e)
        return r.returncode, stidy(r.stdout + ('\n' if r.stdout and r.stderr else '') + r.stderr), time.perf_counter() - t0
    except subprocess.TimeoutExpired as x:
        dec = lambda v: v.decode() if isinstance(v, bytes) else (v or '')
        return -9, stidy((dec(x.stdout) + '\n' + dec(x.stderr)).strip() + '\n[超时被杀]'), time.perf_counter() - t0


def stats(out):
    """解析日志里 'Dumping Scrapy stats:' 后面的字典(值里可能有 datetime)。"""
    i = out.find('Dumping Scrapy stats:')
    if i < 0: return {}
    j = out.find('{', i); depth = 0
    for k in range(j, len(out)):
        if out[k] == '{': depth += 1
        elif out[k] == '}':
            depth -= 1
            if depth == 0: break
    return eval(out[j:k + 1], {'datetime': datetime, 'tzinfo': None, 'UTC': datetime.timezone.utc, 'timezone': datetime.timezone})


def ev(d):
    p = pathlib.Path(d) / 'events.jsonl'
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def keep(out, *pats, n=None):
    """只留包含任一子串的行。"""
    L = [l for l in out.split('\n') if any(p in l for p in pats)]
    return '\n'.join(L[:n] if n else L)


import threading, collections
class Track:
    """服务器端处理函数:记录每个 Host(主机名,不含端口)同时在处理的请求数峰值、总峰值、每个请求到达的时间(self.t)。/seed 不延迟。"""
    def __init__(self, delay=0.3, seed='/seed'):
        self.lock = threading.Lock(); self.cur = collections.Counter(); self.peak = collections.Counter(); self.tot = 0; self.totpeak = 0; self.delay = delay; self.t = []; self.seed = seed; self.paths = []
    def __call__(self, h):
        host = dict(h.hdrs)['Host'].split(':')[0]
        with self.lock:
            self.cur[host] += 1; self.tot += 1; self.t.append(time.perf_counter()); self.paths.append((host, h.path))
            self.peak[host] = max(self.peak[host], self.cur[host]); self.totpeak = max(self.totpeak, self.tot)
        if h.path != self.seed: time.sleep(self.delay)
        h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
        with self.lock: self.cur[host] -= 1; self.tot -= 1


def purge_s():
    shutil.rmtree(SD, ignore_errors=True); SD.mkdir(exist_ok=True)


def reset_s():
    """杀掉遗留的 scrapy 子进程(只杀本目录的 stmp_venv)。"""
    subprocess.run(['pkill', '-9', '-f', str(HERE / 'stmp_venv')], capture_output=True)


if __name__ == '__main__':
    purge_s(); print('清理完成')
