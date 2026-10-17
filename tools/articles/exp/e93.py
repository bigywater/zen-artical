import ctypes, ctypes.util, os, sys, subprocess, tempfile, time, json, struct, textwrap

W = tempfile.mkdtemp(); os.chdir(W)
libc = ctypes.CDLL(ctypes.util.find_library('c'))
libm = ctypes.CDLL(ctypes.util.find_library('m'))

print("== 一、直接调用 libc ==")
print("  libc.getpid() =", libc.getpid(), "| os.getpid() =", os.getpid())
print("  libc.abs(-7) =", libc.abs(-7))
print("  libc.strlen(b'hello') =", libc.strlen(b"hello"), "| libc.strlen('你好'.encode()) =", libc.strlen('你好'.encode()), "(UTF-8 字节数)")
try: libc.strlen("hello")
except ctypes.ArgumentError as e: print("  libc.strlen('hello')(传 str) → ArgumentError:", e)

print("\n== 二、不声明类型会怎样 ==")
try: libm.sqrt(2.0)
except ctypes.ArgumentError as e: print("  libm.sqrt(2.0) →", type(e).__name__ + ":", e)
libm.sqrt.argtypes = [ctypes.c_double]
print("  只声明 argtypes、不声明 restype: libm.sqrt(2.0) =", libm.sqrt(2.0), " ← 返回值被当成 int 读, 是一个无意义的数")
libm.sqrt.restype = ctypes.c_double
print("  再声明 restype=c_double: libm.sqrt(2.0) =", libm.sqrt(2.0))
p_wrong = libc.malloc(16); libc.malloc.restype = ctypes.c_void_p; p_right = libc.malloc(16)
print(f"  malloc 不声明 restype 时返回 {p_wrong} (被当成 32 位 int); 声明 c_void_p 时返回 {p_right:#x} (超过 2**32 = {2**32:#x}: {p_right > 2**32})")
libc.free.argtypes = [ctypes.c_void_p]; libc.free(p_right)

print("\n== 三、自己编一个 C 库来调用 ==")
open('demo.c', 'w').write(textwrap.dedent('''
    #include <stdint.h>
    #include <stddef.h>
    #include <stdlib.h>
    typedef struct { char tag; double value; int32_t count; } Rec;
    int64_t sum_array(const int32_t *a, size_t n) { int64_t s = 0; for (size_t i = 0; i < n; i++) s += a[i]; return s; }
    void fill_rec(Rec *r) { r->tag = 'R'; r->value = 2.5; r->count = 7; }
    size_t rec_size(void) { return sizeof(Rec); }
    size_t rec_off_value(void) { return offsetof(Rec, value); }
    size_t rec_off_count(void) { return offsetof(Rec, count); }
    typedef int (*cmp_t)(const void*, const void*);
    void sort_ints(int32_t *a, size_t n, cmp_t f) { qsort(a, n, sizeof(int32_t), f); }
'''))
r = subprocess.run(['cc', '-shared', '-O2', '-fPIC', 'demo.c', '-o', 'libdemo.dylib'], capture_output=True, text=True)
print("  cc -shared -O2 -fPIC demo.c -o libdemo.dylib → 返回码", r.returncode, r.stderr[:100])
lib = ctypes.CDLL('./libdemo.dylib')
lib.sum_array.argtypes = [ctypes.POINTER(ctypes.c_int32), ctypes.c_size_t]; lib.sum_array.restype = ctypes.c_int64
arr = (ctypes.c_int32 * 5)(10, 20, 30, 40, 50)
print("  sum_array((c_int32 * 5)(10..50), 5) =", lib.sum_array(arr, 5))
class Rec(ctypes.Structure): _fields_ = [("tag", ctypes.c_char), ("value", ctypes.c_double), ("count", ctypes.c_int32)]
lib.fill_rec.argtypes = [ctypes.POINTER(Rec)]
rec = Rec(); lib.fill_rec(ctypes.byref(rec))
print("  fill_rec 填写结构体: tag =", rec.tag, "value =", rec.value, "count =", rec.count)
lib.rec_size.restype = ctypes.c_size_t; lib.rec_off_value.restype = ctypes.c_size_t; lib.rec_off_count.restype = ctypes.c_size_t
print(f"  结构体布局 C 与 ctypes 对照: sizeof C={lib.rec_size()} / ctypes={ctypes.sizeof(Rec)}; offset(value) C={lib.rec_off_value()} / ctypes={Rec.value.offset}; offset(count) C={lib.rec_off_count()} / ctypes={Rec.count.offset}  (字段总大小 1+8+4=13, 中间有对齐填充)")

print("\n== 四、C 调用 Python: 回调 ==")
calls = []
CMP = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
def py_cmp(a, b):
    x = ctypes.cast(a, ctypes.POINTER(ctypes.c_int32))[0]; y = ctypes.cast(b, ctypes.POINTER(ctypes.c_int32))[0]
    calls.append((x, y)); return (x > y) - (x < y)
lib.sort_ints.argtypes = [ctypes.POINTER(ctypes.c_int32), ctypes.c_size_t, CMP]
data = (ctypes.c_int32 * 8)(5, 2, 9, 1, 7, 3, 8, 4)
print("  排序前:", list(data))
lib.sort_ints(data, 8, CMP(py_cmp))
print("  排序后:", list(data), "| C 的 qsort 一共回调了 Python 比较函数", len(calls), "次; 前 3 次:", calls[:3])

print("\n== 五、调用开销 ==")
def per_call(f, n=300000):
    t = time.perf_counter()
    for _ in range(n): f()
    return (time.perf_counter() - t) / n * 1e9
libc.abs.argtypes = [ctypes.c_int]; libc.abs.restype = ctypes.c_int
print(f"  Python 内置 abs(-5)      {per_call(lambda: abs(-5)):7.0f} ns / 次 (含 lambda 调用)")
print(f"  ctypes libc.abs(-5)      {per_call(lambda: libc.abs(-5)):7.0f} ns / 次 (含 lambda 调用)")
big = (ctypes.c_int32 * 1_000_000)(*range(1_000_000)); pl = list(range(1_000_000))
t = time.perf_counter(); s1 = lib.sum_array(big, 1_000_000); t1 = (time.perf_counter() - t) * 1000
t = time.perf_counter(); s2 = sum(pl); t2 = (time.perf_counter() - t) * 1000
t = time.perf_counter(); s3 = 0
for v in pl: s3 += v
t3 = (time.perf_counter() - t) * 1000
print(f"  对 100 万个整数求和: C 函数 {t1:.2f} ms | Python sum() {t2:.2f} ms | Python for 循环 {t3:.2f} ms (结果相同: {s1 == s2 == s3})")

print("\n== 六、没有安全网: 读空指针 ==")
r = subprocess.run([sys.executable, '-c', 'import ctypes; print("将要读地址 0"); import sys; sys.stdout.flush(); ctypes.string_at(0)'], capture_output=True, text=True)
print("  子进程 stdout:", r.stdout.strip(), "| 返回码:", r.returncode, "(负数 = 被信号杀死, 11 = SIGSEGV) | stderr 最后一行:", (r.stderr.strip().splitlines() or ['(无)'])[-1][:80])
json.dump({'calls': calls, 't': [t1, t2, t3]}, open(os.path.join(os.environ['HERE'], 'out/93.json'), 'w'))
