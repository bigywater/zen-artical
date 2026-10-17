def work(n=3_000_000):
    s = 0
    for i in range(n): s += i * i
    return s
def noop(): return 1
def echo(x): return x
class Bar: pass
