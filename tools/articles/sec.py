"""安全批次的实验辅助:设置通过环境变量 EXTRA_SETTINGS(JSON)覆盖,同一个项目可以反复用不同设置跑。"""
import json
from dj import *
ES = """
import json as _j, os as _o
_x = _j.loads(_o.environ.get('EXTRA_SETTINGS', '{}'))
if isinstance(_x.get('SECURE_PROXY_SSL_HEADER'), list): _x['SECURE_PROXY_SSL_HEADER'] = tuple(_x['SECURE_PROXY_SSL_HEADER'])
globals().update(_x)
"""
PRE = "import logging; logging.disable(logging.CRITICAL)\nfrom django.test import Client\nfrom django.conf import settings\n"
def srun(d, code, timeout=120, **st):
    rc, out = pyscript(d, PRE + code, timeout, EXTRA_SETTINGS=json.dumps(st)); return out.rstrip()
def smanage(d, *args, **st):
    return manage(d, *args, EXTRA_SETTINGS=json.dumps(st))
