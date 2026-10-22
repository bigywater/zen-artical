"""Outbox / 双写实验的公共部分:MySQL 里的 orders + outbox 表、Kafka 生产者与“读到底”的消费者、轮询式 relay。"""
import time, json, threading
from confluent_kafka import Producer, Consumer, KafkaException


def mk_producer(port, **kw):
    cfg = {'bootstrap.servers': f'127.0.0.1:{port}', 'linger.ms': 0, 'enable.idempotence': True, 'log_level': 3}; cfg.update(kw); return Producer(cfg)


def read_all(port, topic, idle=1.5, group=None):
    """从头读到底(连续 idle 秒没有新消息就停),返回 [(key, value, 时间戳毫秒)]。"""
    c = Consumer({'bootstrap.servers': f'127.0.0.1:{port}', 'group.id': group or f'g-{time.time_ns()}', 'auto.offset.reset': 'earliest', 'enable.auto.commit': False, 'log_level': 3})
    c.subscribe([topic]); out = []; last = time.time(); t0 = time.time()
    while True:
        m = c.poll(0.3)
        if m is None or m.error():
            if time.time() - last > idle and time.time() - t0 > 2: break
            continue
        out.append((m.key().decode() if m.key() else None, m.value().decode(), m.timestamp()[1])); last = time.time()
    c.close(); return out


def create_schema(m):
    m.q('create database if not exists shop')
    m.q('create table if not exists orders(id varchar(40) primary key, amount int)', db='shop')
    m.q('create table if not exists outbox(id bigint auto_increment primary key, aggregate_id varchar(40), type varchar(30), payload json, created timestamp(3) default current_timestamp(3), sent tinyint default 0, key idx_sent (sent, id))', db='shop')


def relay_once(m, producer, topic, batch=100, crash_after_publish=None):
    """一轮轮询:取没发出的行 → 发到 Kafka(flush)→ 标记 sent。返回发了几条。crash_after_publish(row) 返回 True 时,在“已发出、未标记”处直接退出(模拟 relay 崩溃)。"""
    c = m.conn('shop'); cur = c.cursor(); cur.execute('select id, aggregate_id, payload from outbox where sent = 0 order by id limit %s', (batch,)); rows = cur.fetchall(); n = 0
    for id_, agg, payload in rows:
        producer.produce(topic, key=agg, value=payload if isinstance(payload, str) else json.dumps(payload)); producer.flush(10)
        if crash_after_publish and crash_after_publish(id_): c.close(); return n, True
        cur.execute('update outbox set sent = 1 where id = %s', (id_,)); n += 1
    c.close(); return n, False
