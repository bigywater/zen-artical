import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d75'); R = {}
apps = ['django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.admin', 'django.contrib.sessions', 'django.contrib.messages', 'lab']
MW = ['django.contrib.sessions.middleware.SessionMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware']
TPL = "\nTEMPLATES[0]['OPTIONS']['context_processors'] += ['django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']\n"
def err(out):
    L = [l.strip() for l in out.strip().splitlines() if 'Error' in l or 'ValueError' in l]; return (L[-1] if L else out.strip().splitlines()[-1])[:200]
print('== 一:一开始就用自定义 User:表名、get_user_model、外键写法')
d = proj('d75a', files={'lab/models.py': "from django.contrib.auth.models import AbstractUser\nfrom django.db import models\nclass User(AbstractUser):\n    phone = models.CharField(max_length=20, blank=True)\nclass Post(models.Model):\n    from django.conf import settings\n    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)\n"}, apps=apps, with_lab=True, middleware=MW, settings_extra=TPL + "\nAUTH_USER_MODEL = 'lab.User'\n")
rc, out = manage(d, 'makemigrations', 'lab'); print('  makemigrations:', [l.strip() for l in out.strip().splitlines()][:3])
rc, out = manage(d, 'migrate'); print('  migrate rc =', rc, ' 最后一行:', out.strip().splitlines()[-1][:60])
rc, o = pyscript(d, "from django.contrib.auth import get_user_model\nfrom django.db import connection\nU = get_user_model(); print('get_user_model() =', U.__module__ + '.' + U.__name__, ' 表名 =', U._meta.db_table)\nprint('是否还有 auth_user 表:', 'auth_user' in connection.introspection.table_names())\nu = U.objects.create_user('a', password='x', phone='1'); print('自定义字段:', u.phone)")
print('  ' + o.strip().replace('\n', '\n  ')); R['fresh'] = o.strip()
print()
print('== 二:项目已经用默认 User 迁移过、有了数据,之后才把 AUTH_USER_MODEL 换成自定义模型')
d = proj('d75b', files={'lab/models.py': "from django.db import models\n"}, apps=apps, with_lab=True, middleware=MW, settings_extra=TPL)
manage(d, 'makemigrations', 'lab'); rc, out = manage(d, 'migrate'); rc, o = pyscript(d, "from django.contrib.auth.models import User\nUser.objects.create_user('old', password='x'); print('默认 User 里已有用户:', User.objects.count())"); print('  ', o.strip())
(d / 'lab' / 'models.py').write_text("from django.contrib.auth.models import AbstractUser\nfrom django.db import models\nclass User(AbstractUser):\n    phone = models.CharField(max_length=20, blank=True)\n")
(d / 'proj' / 'settings.py').write_text((d / 'proj' / 'settings.py').read_text() + "\nAUTH_USER_MODEL = 'lab.User'\n")
rc, out = manage(d, 'makemigrations', 'lab'); print('  换成 lab.User 之后 makemigrations:', err(out)); R['switch_make'] = err(out)
rc, out = manage(d, 'migrate'); print('  migrate:', err(out)); R['switch_migrate'] = err(out)
rc, o = pyscript(d, "from django.db import connection\nprint('表:', sorted(t for t in connection.introspection.table_names() if 'user' in t))"); print('  ', o.strip()); R['tables'] = o.strip()
print()
print('== 三:如果 AUTH_USER_MODEL 保持默认,但自己另建 Profile 一对一扩展(不需要换 User)')
d = proj('d75c', files={'lab/models.py': "from django.conf import settings\nfrom django.db import models\nclass Profile(models.Model):\n    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)\n    phone = models.CharField(max_length=20, blank=True)\n"}, apps=apps, with_lab=True, middleware=MW, settings_extra=TPL)
rc, out = manage(d, 'makemigrations', 'lab'); rc, out = manage(d, 'migrate'); print('  migrate rc =', rc)
rc, o = pyscript(d, "from django.contrib.auth.models import User\nfrom lab.models import Profile\nu = User.objects.create_user('p', password='x'); Profile.objects.create(user=u, phone='1'); print('u.profile.phone =', u.profile.phone)"); print('  ' + o.strip()); R['profile'] = o.strip()
save('d75', R)
