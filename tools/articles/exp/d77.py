import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d77'); R = {}
models = "from django.db import models\nclass Article(models.Model):\n    title = models.CharField(max_length=20)\n    class Meta:\n        permissions = [('publish_article', 'Can publish article')]\n"
apps = ['django.contrib.contenttypes', 'django.contrib.auth', 'lab']
d = proj('d77', files={'lab/models.py': models}, apps=apps); manage(d, 'makemigrations', 'lab'); manage(d, 'migrate')
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.contrib.auth.models import User, Group, Permission\nfrom django.db import connection\nfrom django.test.utils import CaptureQueriesContext\nfor n in ('u', 'staff', 'root'): User.objects.filter(username=n).delete()\nu = User.objects.create_user('u', password='x'); root = User.objects.create_superuser('root', password='x')\ndef sql(c): return [' '.join(q['sql'].split())[:100] for q in c.captured_queries]\n" + code); return out.rstrip()
print('== 一:每个模型自动有 add / change / delete / view 四个权限,Meta.permissions 里加的也会创建')
o = run("""
print(sorted(Permission.objects.filter(content_type__app_label='lab').values_list('codename', flat=True)))
""")
print(o); R['perms'] = o
print()
print('== 二:has_perm 的结果:普通用户、被授予权限、通过组、超级用户、不活跃用户')
o = run("""
def fresh(name): return User.objects.get(username=name)
print('没有任何权限:', u.has_perm('lab.add_article'))
u.user_permissions.add(Permission.objects.get(codename='add_article')); print('直接授予 add_article 之后(还是同一个 user 对象):', u.has_perm('lab.add_article'), ' ← 权限缓存!')
print('重新从数据库取用户:', fresh('u').has_perm('lab.add_article'))
g = Group.objects.create(name='editors'); g.permissions.add(Permission.objects.get(codename='publish_article')); u2 = fresh('u'); u2.groups.add(g)
print('加入组后(新取的用户,还没有查过权限):', fresh('u').has_perm('lab.publish_article'))
print('超级用户 has_perm(任意字符串):', root.has_perm('anything.at_all'))
User.objects.filter(username='root').update(is_active=False); print('超级用户但 is_active=False:', fresh('root').has_perm('lab.add_article'))
print('has_perm 需要 "app_label.codename" 格式,只写 codename:', fresh('u').has_perm('add_article'))
""")
print(o); R['has_perm'] = o
print()
print('== 三:权限缓存:第一次 has_perm 查库,同一个 user 对象上之后不再查询')
o = run("""
uu = User.objects.get(username='u')
with CaptureQueriesContext(connection) as c: uu.has_perm('lab.add_article')
print('第一次 has_perm:查询', len(c)); [print('   ', s) for s in sql(c)]
with CaptureQueriesContext(connection) as c: uu.has_perm('lab.change_article'); uu.has_perm('lab.delete_article')
print('之后再查其它权限:查询', len(c), ' (_perm_cache / _user_perm_cache / _group_perm_cache 在对象上)')
print('缓存属性:', sorted(a for a in vars(uu) if 'perm_cache' in a))
""")
print(o); R['cache'] = o
print()
print('== 四:对象级权限:默认后端对 obj 参数一律返回 False(需要第三方或自定义后端)')
o = run("""
from lab.models import Article
a = Article.objects.create(title='t'); uu = User.objects.get(username='u'); uu.user_permissions.add(Permission.objects.get(codename='change_article')); uu = User.objects.get(username='u')
print('has_perm("lab.change_article") =', uu.has_perm('lab.change_article'), ' has_perm("lab.change_article", obj) =', uu.has_perm('lab.change_article', a))
print('超级用户带 obj:', User.objects.get(username='root').is_superuser)
""")
print(o); R['obj'] = o
save('d77', R)
