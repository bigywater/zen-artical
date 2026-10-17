import sys, os, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
import hmac, hashlib, base64
tee('m77'); reset()
nd = Node('m77', args=['--auth']).start()
anon = nd.client()
def err(f):
    try: return f()
    except Exception as ex: return ex
def fmt(ex):
    return f'code {ex.code} {ex.details.get("codeName")}: {str(ex)[:150]}' if hasattr(ex, 'code') and ex.code is not None else repr(ex)[:150]
print('== 一:--auth 启动后,没有认证的连接:读写被拒;localhost 例外——还没有任何用户时,本机连接可以创建第一个用户')
print('  find 被拒: ' + fmt(err(lambda: list(anon.test.t.find()))))
print('  listCollections 被拒: ' + fmt(err(lambda: anon.test.list_collection_names())))
print('  不需要认证的命令:ping → ' + str(anon.admin.command('ping')) + ';hello 里 saslSupportedMechs 需要先给 user 参数 → ' + str(anon.admin.command('hello', saslSupportedMechs='admin.root')['saslSupportedMechs']))
print('  localhost 例外:第一个用户可以不认证就创建: ' + str(anon.admin.command('createUser', 'root', pwd='rootpw', roles=['root'])))
print('  创建第一个用户之后,再创建第二个用户(没认证): ' + fmt(err(lambda: anon.admin.command('createUser', 'u2', pwd='x', roles=['read']))))
root = MongoClient(nd.uri, directConnection=True, username='root', password='rootpw', authSource='admin')
print('== 二:admin.system.users 里存的是什么:没有明文密码,每种机制各存 iterationCount、salt、storedKey、serverKey')
root.admin.command('createUser', 'alice', pwd='alicepw', roles=[{'role': 'read', 'db': 'test'}])
d = root.admin.system.users.find_one({'user': 'alice'})
print('  顶层字段: ' + str(sorted(d.keys())) + ',_id = ' + d['_id'] + ',mechanisms = ' + str(d['credentials'].keys() and list(d['credentials'].keys())))
for m, cr in d['credentials'].items():
    print(f'  {m}: iterationCount = {cr["iterationCount"]},salt 长度 = {len(base64.b64decode(cr["salt"]))} 字节,storedKey 长度 = {len(base64.b64decode(cr["storedKey"]))} 字节,serverKey 长度 = {len(base64.b64decode(cr["serverKey"]))} 字节')
print('  roles = ' + str(d['roles']))
print('  明文 "alicepw" 在文档里出现吗? ' + str('alicepw' in json.dumps(d, default=str)))
print('== 三:手写 SCRAM-SHA-256:自己用 saslStart / saslContinue 走一遍握手,看每一步的内容,并自己验证 storedKey 和服务器签名')
cr = d['credentials']['SCRAM-SHA-256']
def scram(user, pw, skip=True, verbose=True):
    cx = nd.client()
    nonce = base64.b64encode(os.urandom(18)).decode(); bare = f'n={user},r={nonce}'
    r1 = cx.admin.command('saslStart', mechanism='SCRAM-SHA-256', payload=Binary(('n,,' + bare).encode()), options={'skipEmptyExchange': skip}, autoAuthorize=1)
    sf = bytes(r1['payload']).decode(); kv = dict(x.split('=', 1) for x in sf.split(','))
    if verbose: print(f'  1. 客户端 → 服务器 saslStart:payload = "n,,{bare}"(mechanism = SCRAM-SHA-256)')
    if verbose: print(f'     服务器 → 客户端:conversationId = {r1["conversationId"]},done = {r1["done"]},payload = "r=<客户端nonce+服务端nonce, {len(kv["r"])} 字符>,s={kv["s"][:8]}…,i={kv["i"]}"')
    salted = hashlib.pbkdf2_hmac('sha256', pw.encode(), base64.b64decode(kv['s']), int(kv['i']))
    ck = hmac.new(salted, b'Client Key', 'sha256').digest(); stored = hashlib.sha256(ck).digest(); sk = hmac.new(salted, b'Server Key', 'sha256').digest()
    final_wo = f'c=biws,r={kv["r"]}'; am = f'{bare},{sf},{final_wo}'
    sig = hmac.new(stored, am.encode(), 'sha256').digest(); proof = bytes(a ^ b for a, b in zip(ck, sig))
    r2 = cx.admin.command('saslContinue', conversationId=r1['conversationId'], payload=Binary(f'{final_wo},p={base64.b64encode(proof).decode()}'.encode()))
    sf2 = bytes(r2['payload']).decode(); v = sf2.split('=', 1)[1]
    if verbose: print(f'  2. 客户端 → 服务器 saslContinue:payload = "c=biws,r=…,p=<ClientProof {len(proof)} 字节的 base64>"')
    if verbose: print(f'     服务器 → 客户端:done = {r2["done"]},payload = "v=<ServerSignature>"')
    ok = v == base64.b64encode(hmac.new(sk, am.encode(), 'sha256').digest()).decode()
    n = 2
    if not r2['done']:
        r3 = cx.admin.command('saslContinue', conversationId=r1['conversationId'], payload=Binary(b'')); n = 3
        if verbose: print(f'  3. 客户端 → 服务器 saslContinue(空 payload):done = {r3["done"]}')
    return cx, base64.b64encode(stored).decode(), base64.b64encode(sk).decode(), ok, n
cx, st, svk, ok, n = scram('alice', 'alicepw')
print(f'  自己算出的 storedKey == system.users 里的 storedKey: {st == cr["storedKey"]};serverKey 相等: {svk == cr["serverKey"]};客户端校验服务器签名通过: {ok};握手共 {n} 条命令')
print('  认证后 connectionStatus: ' + json.dumps(cx.admin.command('connectionStatus')['authInfo']['authenticatedUsers']))
cx, st, svk, ok, n2 = scram('alice', 'alicepw', skip=False, verbose=False)
print(f'  不带 skipEmptyExchange:握手共 {n2} 条命令(多一次空的 saslContinue)')
print('== 四:失败的认证:密码错、用户不存在、机制不对——错误一样吗?')
def attempt(user, pw, mech=None, src='admin'):
    kw = dict(username=user, password=pw, authSource=src, directConnection=True)
    if mech: kw['authMechanism'] = mech
    return fmt(err(lambda: MongoClient(nd.uri, serverSelectionTimeoutMS=3000, **kw).admin.command('ping')))
print('  密码错的 alice: ' + attempt('alice', 'wrong'))
print('  不存在的用户 nobody: ' + attempt('nobody', 'wrong'))
print('  alice 在错误的 authSource(test): ' + attempt('alice', 'alicepw', src='test'))
print('  正确的 alice: ' + attempt('alice', 'alicepw'))
print('  机制 PLAIN(服务端没开): ' + attempt('alice', 'alicepw', 'PLAIN'))
print('== 五:角色:alice 只有 test 库的 read。写入被拒;grantRolesToUser 之后,同一个已认证连接上不重新登录就能写吗?')
al = MongoClient(nd.uri, directConnection=True, username='alice', password='alicepw', authSource='admin')
print('  alice 读 test.t: ' + str(err(lambda: list(al.test.t.find()))))
print('  alice 写 test.t: ' + fmt(err(lambda: al.test.t.insert_one({'_id': 1}))))
print('  alice 读 test2.t(没有授权的库): ' + fmt(err(lambda: list(al.test2.t.find()))))
print('  connectionStatus 的 authenticatedUserRoles: ' + json.dumps(al.admin.command('connectionStatus')['authInfo']['authenticatedUserRoles']))
root.admin.command('grantRolesToUser', 'alice', roles=[{'role': 'readWrite', 'db': 'test'}])
print('  root 给 alice 加 readWrite@test 后,alice 的同一个连接写 test.t: ' + str(err(lambda: al.test.t.insert_one({'_id': 1}).inserted_id)))
root.admin.command('revokeRolesFromUser', 'alice', roles=[{'role': 'readWrite', 'db': 'test'}])
print('  root 回收 readWrite@test 后,同一连接再写: ' + fmt(err(lambda: al.test.t.insert_one({'_id': 2}))))
print('== 六:认证的代价:新建连接并认证的耗时,SCRAM-SHA-256(iterationCount 15000)与 SCRAM-SHA-1(10000),各 15 次中位数')
def conn_auth(mech): 
    def f(): MongoClient(nd.uri, directConnection=True, username='alice', password='alicepw', authSource='admin', authMechanism=mech).admin.command('ping')
    return f
def conn_noauth(): anon_c = MongoClient(nd.uri, directConnection=True); anon_c.admin.command('ping')
a256 = bench(conn_auth('SCRAM-SHA-256'), n=15); a1 = bench(conn_auth('SCRAM-SHA-1'), n=15); a0 = bench(conn_noauth, n=15)
print(f'  不认证的 ping:{fm(a0)};SCRAM-SHA-1:{fm(a1)};SCRAM-SHA-256:{fm(a256)}')
print('  (每次都是新建 MongoClient 加一次 ping;客户端和服务端在同一台机器上,没有网络延迟)')
nd.stop()
