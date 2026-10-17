"""Django 实验辅助:在 djtmp/<name>/ 下生成真实的小项目,用 djlab 虚拟环境的 python 运行。
端口 9300+;绝不碰 6379(用户 redis)、8181/9101(用户 weed)、用户自己的 mysql / postgres。"""
import os, sys, subprocess, shutil, pathlib, textwrap, time, json, re
HERE = pathlib.Path(__file__).parent
PY = str(HERE.parent / 'djlab' / 'bin' / 'python')
DJ = HERE / 'djtmp'
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
    os.environ.pop(k, None)
sys.path.insert(0, str(HERE))
import rl
from rl import tee, save

BASE = '''
import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'lab-secret-key-not-for-production'
DEBUG = True
ALLOWED_HOSTS = ['*']
INSTALLED_APPS = %(apps)s
MIDDLEWARE = %(middleware)s
ROOT_URLCONF = 'proj.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
              'OPTIONS': {'context_processors': ['django.template.context_processors.request']}}]
WSGI_APPLICATION = 'proj.wsgi.application'
DATABASES = %(databases)s
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = 'static/'
'''
WSGI = "import os\nfrom django.core.wsgi import get_wsgi_application\nos.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proj.settings')\napplication = get_wsgi_application()\n"
ASGI = "import os\nfrom django.core.asgi import get_asgi_application\nos.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proj.settings')\napplication = get_asgi_application()\n"
MANAGE = "#!/usr/bin/env python\nimport os, sys\nif __name__ == '__main__':\n    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proj.settings')\n    from django.core.management import execute_from_command_line\n    execute_from_command_line(sys.argv)\n"
DEFAULT_APPS = ['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.sessions', 'django.contrib.messages', 'lab']
DEFAULT_MW = []


def proj(name, files=None, apps=None, middleware=None, databases=None, settings_extra='', urls="from django.urls import path\nurlpatterns = []\n", with_lab=True):
    """新建(覆盖)项目目录并写入文件。files: {相对路径: 内容}。返回目录。"""
    d = DJ / name
    shutil.rmtree(d, ignore_errors=True)
    (d / 'proj').mkdir(parents=True)
    (d / 'proj' / '__init__.py').write_text('')
    apps = DEFAULT_APPS if apps is None else apps
    middleware = DEFAULT_MW if middleware is None else middleware
    databases = databases or "{'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}"
    (d / 'proj' / 'settings.py').write_text(BASE % dict(apps=repr(apps), middleware=repr(middleware), databases=databases) + settings_extra)
    (d / 'proj' / 'urls.py').write_text(urls)
    (d / 'proj' / 'wsgi.py').write_text(WSGI)
    (d / 'proj' / 'asgi.py').write_text(ASGI)
    (d / 'manage.py').write_text(MANAGE)
    if with_lab:
        (d / 'lab').mkdir()
        (d / 'lab' / '__init__.py').write_text('')
        (d / 'lab' / 'models.py').write_text('from django.db import models\n')
    for rel, txt in (files or {}).items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(txt).lstrip('\n'))
    return d


def env(d, **extra):
    e = dict(os.environ); e.pop('DJANGO_SETTINGS_MODULE', None); e['PYTHONPATH'] = str(d); e['PYTHONUNBUFFERED'] = '1'; e['PYTHONDONTWRITEBYTECODE'] = '1'; e.update({k: str(v) for k, v in extra.items()})
    return e


def manage(d, *args, timeout=180, **extra):
    """python manage.py args...;返回 (returncode, stdout+stderr)"""
    r = subprocess.run([PY, 'manage.py', *args], cwd=d, env=env(d, **extra), capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr)


def py(d, code, timeout=180, **extra):
    """在项目环境里运行一段代码(DJANGO_SETTINGS_MODULE=proj.settings)。返回 (rc, out)"""
    e = env(d, **extra); e['DJANGO_SETTINGS_MODULE'] = 'proj.settings'
    r = subprocess.run([PY, '-c', textwrap.dedent(code)], cwd=d, env=e, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr)


def pyscript(d, code, timeout=180, **extra):
    """同 py,但先 django.setup()"""
    return py(d, 'import django; django.setup()\n' + textwrap.dedent(code), timeout, **extra)


def pr(title_out):
    print(title_out.rstrip('\n'))


def ms(t0):
    return (time.perf_counter() - t0) * 1000


# ---------- 自己的临时 PostgreSQL 实例(端口 9400+,数据目录在 pgdata/,绝不碰用户自己的 postgres) ----------
PGBIN = '/opt/homebrew/bin'
class PG:
    def __init__(self, port=9400, name=None, conf=None):
        assert port not in (5432, 6379, 8181, 9101)
        self.port = port; self.name = name or f'pg{port}'; self.dir = HERE / 'pgdata' / self.name; self.sock = f'/tmp/pgs{port}'
        self.conf = conf or {}
    def start(self):
        if self.dir.exists(): subprocess.run([f'{PGBIN}/pg_ctl', '-D', str(self.dir), '-m', 'immediate', 'stop'], capture_output=True)
        shutil.rmtree(self.dir, ignore_errors=True); shutil.rmtree(self.sock, ignore_errors=True); os.makedirs(self.sock); self.dir.parent.mkdir(exist_ok=True)
        r = subprocess.run([f'{PGBIN}/initdb', '-D', str(self.dir), '-U', 'lab', '--auth=trust', '-E', 'UTF8', '--locale=C'], capture_output=True, text=True); assert r.returncode == 0, r.stderr
        opts = f'-p {self.port} -k {self.sock} -c listen_addresses=127.0.0.1 -c fsync=off -c synchronous_commit=off -c max_connections=200' + ''.join(f' -c {k}={v}' for k, v in self.conf.items())
        r = subprocess.run([f'{PGBIN}/pg_ctl', '-D', str(self.dir), '-o', opts, '-l', str(self.dir / 'pg.log'), '-w', 'start'], capture_output=True, text=True); assert r.returncode == 0, r.stderr + (self.dir / 'pg.log').read_text()[-500:]
        r = subprocess.run([f'{PGBIN}/createdb', '-h', '127.0.0.1', '-p', str(self.port), '-U', 'lab', 'lab'], capture_output=True, text=True); assert r.returncode == 0, r.stderr
        return self
    def stop(self):
        subprocess.run([f'{PGBIN}/pg_ctl', '-D', str(self.dir), '-m', 'fast', '-w', 'stop'], capture_output=True, text=True)
        shutil.rmtree(self.sock, ignore_errors=True)
    def databases(self, extra=''):
        return "{'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'lab', 'USER': 'lab', 'HOST': '127.0.0.1', 'PORT': %d%s}}" % (self.port, extra)
    def psql(self, sql):
        r = subprocess.run([f'{PGBIN}/psql', '-h', '127.0.0.1', '-p', str(self.port), '-U', 'lab', '-d', 'lab', '-At', '-c', sql], capture_output=True, text=True); return r.stdout.strip() + r.stderr.strip()
