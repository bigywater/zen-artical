import sys, threading, time, json, os
def work():
    s = 0
    for i in range(3_000_000): s += i * i
def timeit(n, threaded, reps=3):
    best = 1e9
    for _ in range(reps):
        t = time.perf_counter()
        if threaded:
            ths = [threading.Thread(target=work) for _ in range(n)]
            for x in ths: x.start()
            for x in ths: x.join()
        else:
            for _ in range(n): work()
        best = min(best, time.perf_counter() - t)
    return best
res = {'gil': sys._is_gil_enabled(), 'rows': []}
for n in (1, 2, 4, 8):
    s, t = timeit(n, False), timeit(n, True)
    res['rows'].append((n, s, t))
box = [0]
def inc():
    for _ in range(500_000): box[0] += 1
runs = []
for _ in range(5):
    box[0] = 0; ths = [threading.Thread(target=inc) for _ in range(4)]
    for x in ths: x.start()
    for x in ths: x.join()
    runs.append(box[0])
res['race'] = runs
print(json.dumps(res))
