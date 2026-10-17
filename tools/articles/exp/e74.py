import pickle, pickletools, os, io, json, tempfile, sys, copy

d = tempfile.mkdtemp(); os.chdir(d); marker = 'PWNED.txt'

class Evil:
    def __reduce__(self):
        return (os.system, (f"echo pwned > {marker}",))

payload = pickle.dumps(Evil(), protocol=2)
print("payload 长度:", len(payload), "字节;  repr:", payload)
print("\n== 一、pickletools.dis 反汇编 ==")
pickletools.dis(payload)

print("\n== 二、loads 之前/之后 ==")
print("loads 之前, 标记文件存在?", os.path.exists(marker))
obj = pickle.loads(payload)
print("loads 之后, 标记文件存在?", os.path.exists(marker), "| 内容:", open(marker).read().strip())
print("loads 返回的对象:", repr(obj), type(obj).__name__, " ← 不是 Evil 实例, 是 os.system 的返回值")
os.remove(marker)

print("\n== 三、代码在「反序列化」时执行, 不是在「使用」时 ==")
print("payload 字节里含有 'Evil'(类名)?", b'Evil' in payload, "| 含有 'system'(要调用的函数)?", b'system' in payload)

print("\n== 四、allowlist Unpickler ==")
class Safe(pickle.Unpickler):
    ALLOWED = {('builtins', 'list'), ('collections', 'OrderedDict')}
    def find_class(self, module, name):
        if (module, name) in self.ALLOWED: return super().find_class(module, name)
        raise pickle.UnpicklingError(f"禁止加载 {module}.{name}")
try:
    Safe(io.BytesIO(payload)).load()
except pickle.UnpicklingError as e:
    print("Safe.load(payload) → UnpicklingError:", e)
print("标记文件被创建了吗?", os.path.exists(marker))
ok = pickle.dumps([1, 2, {'a': 3}]); print("正常数据 Safe.load →", Safe(io.BytesIO(ok)).load())

print("\n== 五、同一份数据用 json ==")
import json as J
try: J.loads(payload.decode('latin1'))
except Exception as e: print("json.loads(payload) →", type(e).__name__)
print("json.loads('{\"a\": [1, 2]}') →", J.loads('{"a": [1, 2]}'))

# ---- 演示用: 用纯 Python 版 Unpickler 记录每条操作码之后的栈 ----
print("\n== 六、逐条 opcode 记录(pickle._Unpickler)==")
trace = []
class T(pickle._Unpickler):
    def load(self):
        # 复制 load 的主循环, 每步记录
        if not hasattr(self, "_file_read"): raise pickle.UnpicklingError("Unpickler.__init__() was not called")
        self._unframer = pickle._Unframer(self._file_read, self._file_readline)
        self.read = self._unframer.read; self.readinto = self._unframer.readinto; self.readline = self._unframer.readline; self.metastack = []; self.stack = []; self.append = self.stack.append; self.proto = 0
        read = self.read; dispatch = self.dispatch
        try:
            while True:
                key = read(1)
                if not key: raise EOFError
                name = pickle.bytes_types and key
                dispatch[key[0]](self)
                trace.append((key.decode('latin1'), [repr(x) if not callable(x) else f"<callable {getattr(x, '__module__', '?')}.{getattr(x, '__name__', '?')}>" for x in self.stack], repr(list(map(lambda z: type(z).__name__, self.metastack)))))
        except pickle._Stop as stopinst:
            return stopinst.value
os.remove(marker) if os.path.exists(marker) else None
res = T(io.BytesIO(payload)).load()
for k, st, _ in trace: print(f"opcode {k!r:>5}  栈 = {st}")
print("最终返回:", res)
json.dump({'trace': trace, 'payload_len': len(payload)}, open('out/74.json', 'w'), ensure_ascii=False)
