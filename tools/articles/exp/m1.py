import sys, os, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
import bson, re as _re
tee('m1'); reset()
TAGS = {1: 'double', 2: 'string', 3: 'document', 4: 'array', 5: 'binary', 7: 'ObjectId', 8: 'bool', 9: 'datetime', 10: 'null', 11: 'regex', 16: 'int32', 17: 'timestamp', 18: 'int64', 19: 'decimal128'}
def parse(b, off=0):
    """纯 Python 的 BSON 解析:返回 [(key, 类型号, 值的字节长度, 值)],并检查结尾的 0。"""
    n = struct.unpack_from('<i', b, off)[0]; end = off + n; pos = off + 4; res = []
    while b[pos] != 0:
        t = b[pos]; pos += 1; k_end = b.index(0, pos); k = b[pos:k_end].decode(); pos = k_end + 1; st = pos
        if t == 1: v = struct.unpack_from('<d', b, pos)[0]; pos += 8
        elif t == 2: ln = struct.unpack_from('<i', b, pos)[0]; v = b[pos + 4:pos + 4 + ln - 1].decode(); assert b[pos + 4 + ln - 1] == 0; pos += 4 + ln
        elif t in (3, 4): ln = struct.unpack_from('<i', b, pos)[0]; v = parse(b, pos); pos += ln
        elif t == 5: ln = struct.unpack_from('<i', b, pos)[0]; v = (b[pos + 4], b[pos + 5:pos + 5 + ln]); pos += 5 + ln
        elif t == 7: v = b[pos:pos + 12].hex(); pos += 12
        elif t == 8: v = bool(b[pos]); pos += 1
        elif t == 9: v = struct.unpack_from('<q', b, pos)[0]; pos += 8
        elif t == 10: v = None
        elif t == 11: e1 = b.index(0, pos); e2 = b.index(0, e1 + 1); v = (b[pos:e1].decode(), b[e1 + 1:e2].decode()); pos = e2 + 1
        elif t == 16: v = struct.unpack_from('<i', b, pos)[0]; pos += 4
        elif t == 17: v = struct.unpack_from('<II', b, pos); pos += 8
        elif t == 18: v = struct.unpack_from('<q', b, pos)[0]; pos += 8
        elif t == 19: v = b[pos:pos + 16].hex(); pos += 16
        else: raise ValueError(f'未处理的类型 {t}')
        res.append((k, t, pos - st, v))
    assert pos == end - 1 and b[pos] == 0, (pos, end)
    return res

print('== 一:最小的文档 {"a": 1} 编码成 12 字节:总长度(4)+ 类型(1)+ 键名 + 0(2)+ 值(4)+ 结尾 0(1)')
b = bson.encode({'a': 1}); hexdump(b, 32)
n_ = struct.unpack('<i', b[:4])[0]
print(f'  前 4 字节是小端的总长度 = {n_}(= len(bytes) = {len(b)})')
print(f'  第 5 字节 0x{b[4]:02x} = 类型 {b[4]}({TAGS[b[4]]});键名 {b[5:6]!r} 后跟一个 0 字节;值 {b[7:11].hex()} 是小端 int32 = {struct.unpack("<i", b[7:11])[0]};最后一个字节 0x{b[-1]:02x} 结束文档')
e = bson.encode({}); print(f'  空文档 {{}} 编码: {e.hex()}({len(e)} 字节 = 4 字节长度 + 1 字节结尾)')
print('  纯 Python 解析:', parse(b))
print('== 二:每种类型的类型字节和值占的字节数(文档 {"x": 值} 编码后逐个解析)')
import datetime as dt, uuid
vals = [('int32', 1), ('int64', Int64(1)), ('double', 1.5), ('string "abc"', 'abc'), ('bool', True), ('null', None), ('ObjectId', ObjectId('65a000000000000000000001')),
        ('datetime', dt.datetime(2026, 1, 1)), ('Decimal128', Decimal128('1.5')), ('Timestamp', Timestamp(1, 2)), ('binary 4 字节', b'abcd'), ('regex /a/i', bson.regex.Regex('a', 'i')), ('空数组', []), ('数组 [1,2]', [1, 2]), ('空子文档', {}), ('子文档 {"y":1}', {'y': 1})]
print(f'  {"类型":<16}{"类型字节":>8}  {"值字节":>6}   {"整个文档":>8}')
for nm, v in vals:
    b = bson.encode({'x': v}); k, t, ln, val = parse(b)[0]
    print(f'  {nm:<16}{"0x%02x" % t:>8}  {ln:>6}   {len(b):>8}')
print('== 三:字符串带长度前缀和结尾 0;中文是 UTF-8 多字节,长度算字节数;键名是 C 字符串,不能含 0 字节')
for s in ['abc', '', '中文', '😀']:
    b = bson.encode({'s': s}); k, t, ln, v = parse(b)[0]
    print(f'  "{s}" → 字符数 {len(s)},UTF-8 字节数 {len(s.encode())},编码里的长度前缀 {struct.unpack("<i", b[7:11])[0]}(= 字节数 + 1),整个文档 {len(b)} 字节')
try: bson.encode({'a\x00b': 1})
except Exception as ex: print(f'  键名含 NUL: {type(ex).__name__}: {ex}')
try: bson.encode({'s': 'a\x00b'}); print(f'  字符串值里含 NUL 是允许的: {bson.encode({"s": "a" + chr(0) + "b"}).hex()}')
except Exception as ex: print(f'  字符串值含 NUL: {ex}')
print('== 四:数组就是键为 "0"、"1"、"2"… 的子文档,类型字节是 4 而不是 3')
b = bson.encode({'arr': ['x', 'y']}); hexdump(b, 48)
k, t, ln, sub = parse(b)[0]
print(f'  外层: 键 {k},类型 {t}({TAGS[t]}),子文档长度 {ln};子文档里的键: {[x[0] for x in sub]}')
b2 = bson.encode({'arr': {'0': 'x', '1': 'y'}}); print(f'  对照 {{"0":"x","1":"y"}} 这个普通子文档,只有类型字节不同: {b.hex()} vs {b2.hex()};差异位置 {[i for i in range(len(b)) if b[i] != b2[i]]}')
print('== 五:键名每个文档都存一遍:同样的数据,键名从 1 个字符变成 30 个字符')
for nm, doc in [('键名 1 字符', {'a': 1, 'b': 2, 'c': 3}), ('键名 30 字符', {'a' * 30: 1, 'b' * 30: 2, 'c' * 30: 3})]:
    print(f'  {nm}: 单个文档 {len(bson.encode(doc))} 字节')
n1 = Node('m1'); n1.start(); c = n1.client(); db = c.test
for nm, mk in [('short', lambda i: {'a': i, 'b': i, 'c': i}), ('long', lambda i: {'a' * 30: i, 'b' * 30: i, 'c' * 30: i})]:
    db[nm].insert_many([mk(i) for i in range(20000)])
    c.admin.command('fsync'); time.sleep(1); c.admin.command('fsync'); st = db.command('collStats', nm)
    print(f'  集合 {nm}: 20000 个文档,avgObjSize {st["avgObjSize"]} 字节,size {st["size"]:,},storageSize {st["storageSize"]:,}')
print('== 六:服务端怎么看:bsonsize() 与 $bsonSize 和 Python 编码出的字节数一致;mongosh 里取回的值和解析结果一致')
doc = {'_id': 1, 'name': '中文', 'tags': ['a', 'b'], 'n': Int64(7), 'sub': {'ok': True}}
db.t.drop(); db.t.insert_one(doc)
print(f'  Python 编码长度 {len(bson.encode(doc))} 字节;字段 {[(k, TAGS[t], ln) for k, t, ln, v in parse(bson.encode(doc))]}')
msh(n1, 'bsonsize(db.t.findOne())')
msh(n1, 'db.t.aggregate([{$project: {_id: 0, size: {$bsonSize: "$$ROOT"}, types: {$map: {input: {$objectToArray: "$$ROOT"}, in: {k: "$$this.k", t: {$type: "$$this.v"}}}}}}])')
n1.stop()
