"""RabbitMQ 实验的子进程消费者:python qcons.py PORT QUEUE PREFETCH ACK_FIRST —— 消费 QUEUE,确认前 ACK_FIRST 条,其余不确认;收满 PREFETCH 条后打印 READY 并一直挂着(等被 kill)。"""
import sys, time, pika
port, queue, prefetch, ack_first = int(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
c = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1', port, heartbeat=int(sys.argv[5]) if len(sys.argv) > 5 else 60)); ch = c.channel(); ch.basic_qos(prefetch_count=prefetch)
cnt = [0]
def cb(chn, m, p, b):
    cnt[0] += 1
    if cnt[0] <= ack_first: chn.basic_ack(m.delivery_tag)
    if cnt[0] >= prefetch + ack_first: print('READY', flush=True)
ch.basic_consume(queue, cb)
while True: c.process_data_events(0.1)
