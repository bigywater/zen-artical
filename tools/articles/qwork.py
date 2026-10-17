"""RabbitMQ 实验的子进程发布者:python qwork.py PORT QUEUE N NCHAN [SIZE] —— 开 1 条连接、NCHAN 个 channel,轮流发布 N 条(不开 confirm),发完用 queue_declare(passive) 往返一次,打印耗时 ms。"""
import sys, time, pika
port, queue, n, nchan = int(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
size = int(sys.argv[5]) if len(sys.argv) > 5 else 100
c = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', port)); chs = [c.channel() for _ in range(nchan)]
body = b'x' * size
chs[0].queue_declare(queue, durable=True)
t0 = time.perf_counter()
for i in range(n): chs[i % nchan].basic_publish('', queue, body)
chs[0].queue_declare(queue, passive=True)
print(round((time.perf_counter() - t0) * 1000, 1)); c.close()
