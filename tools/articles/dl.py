"""Docker 实验辅助:真实的 docker CLI(Docker Desktop,Engine 29.8.2,linux/arm64)。
- 所有容器/网络/卷/镜像都带标签 bwlab=1 或名字以 bwlab 开头,purge() 一键清理(只清理自己的,不碰别的)
- 构建上下文放在 dtmp/<name>/,用完 shutil.rmtree
- 守护进程拉不到 Docker Hub:镜像用 img() 经 dpull.py 从宿主机下载再 docker load(不改 Docker Desktop 设置)
- 端口:自己起的服务用 9700+;绝不碰 5432/3306/6379/8181/9101/9333"""
import os, sys, subprocess, shutil, pathlib, textwrap, time, json, re, socket, statistics
HERE = pathlib.Path(__file__).parent
DT = HERE / 'dtmp'; DT.mkdir(exist_ok=True)
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
    os.environ.pop(k, None)
sys.path.insert(0, str(HERE))
import rl
from rl import tee, save
LAB = ['--label', 'bwlab=1']


def tidy(t):
    t = re.sub(r'\x1b\[[0-9;]*m', '', t).replace(str(DT), '<dtmp>').replace(str(HERE), '<实验目录>')
    return '\n'.join(l.rstrip() for l in t.rstrip().split('\n')).strip('\n')


def dk(*args, timeout=120, input=None, env=None, raw=False):
    """运行 docker CLI,返回 (退出码, 合并后的输出)。"""
    e = dict(os.environ); e.update(env or {})
    try:
        r = subprocess.run(['docker', *map(str, args)], capture_output=True, text=True, timeout=timeout, input=input, env=e)
        o = r.stdout + r.stderr
        return r.returncode, (o if raw else tidy(o))
    except subprocess.TimeoutExpired as ex:
        o = (ex.stdout.decode() if isinstance(ex.stdout, bytes) else (ex.stdout or '')) + '\n(超时)'
        return -9, tidy(o)


def out(*args, **kw):
    """只要 stdout(去掉末尾换行)。"""
    r = subprocess.run(['docker', *map(str, args)], capture_output=True, text=True, timeout=kw.get('timeout', 120), input=kw.get('input'))
    return r.stdout.strip()


def have(ref):
    return subprocess.run(['docker', 'image', 'inspect', ref], capture_output=True).returncode == 0


def img(*refs):
    """确保镜像在本地:不在就用 dpull.py 经宿主机代理下载并 load。"""
    for ref in refs:
        if not have(ref):
            r = subprocess.run([sys.executable, str(HERE / 'dpull.py'), ref], capture_output=True, text=True, timeout=900)
            assert have(ref), (ref, r.stdout[-300:], r.stderr[-300:])


def run(image, *cmd, opts=(), timeout=120, name=None):
    """docker run --rm,带实验标签。返回 (退出码, 输出)。"""
    a = ['run', '--rm', *LAB]
    if name: a += ['--name', name]
    return dk(*a, *opts, image, *cmd, timeout=timeout)


def ctx(name, files, clean=True):
    """在 dtmp/<name>/ 写一组文件(字典:相对路径 -> 内容 或 bytes),返回目录。"""
    d = DT / name
    if clean: shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    for p, c in files.items():
        f = d / p; f.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(c, bytes): f.write_bytes(c)
        else: f.write_text(textwrap.dedent(c).lstrip('\n') if '\n' in c else c)
    return d


def build(d, tag, *extra, timeout=300, progress='plain', env=None):
    return dk('build', '--progress', progress, '-t', tag, '--label', 'bwlab=1', *extra, str(d), timeout=timeout, env=env)


def ms(t0):
    return (time.time() - t0) * 1000


def med(xs):
    xs = sorted(xs); return xs[len(xs) // 2]


def free_port(start=9700):
    for p in range(start, start + 200):
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1', p)) != 0: return p
    raise RuntimeError('no free port')


def purge(images=True):
    """清理带 bwlab 标签/前缀的容器、网络、卷、镜像,并删掉 dtmp 目录。"""
    ids = out('ps', '-aq', '--filter', 'label=bwlab=1').split()
    if ids: subprocess.run(['docker', 'rm', '-f', *ids], capture_output=True)
    names = [n for n in out('ps', '-a', '--format', '{{.Names}}').split() if n.startswith('bwlab')]
    if names: subprocess.run(['docker', 'rm', '-f', *names], capture_output=True)
    nets = [n for n in out('network', 'ls', '--format', '{{.Name}}').split() if n.startswith('bwlab')]
    for n in nets: subprocess.run(['docker', 'network', 'rm', n], capture_output=True)
    vols = [v for v in out('volume', 'ls', '-q').split() if v.startswith('bwlab')]
    for v in vols: subprocess.run(['docker', 'volume', 'rm', '-f', v], capture_output=True)
    if images:
        imgs = sorted(set(out('images', '-a', '--filter', 'label=bwlab=1', '-q').split()))
        if imgs: subprocess.run(['docker', 'rmi', '-f', *imgs], capture_output=True)
        tags = [t for t in out('images', '--format', '{{.Repository}}:{{.Tag}}').split() if t.startswith('bwlab')]
        if tags: subprocess.run(['docker', 'rmi', '-f', *tags], capture_output=True)
    shutil.rmtree(DT, ignore_errors=True); DT.mkdir(exist_ok=True)


if __name__ == '__main__':
    purge()
    print('清理完成')
