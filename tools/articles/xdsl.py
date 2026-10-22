"""最小的 xDS 控制平面(ADS,State-of-the-World):只实现 StreamAggregatedResources。资源用 JSON 字典(与 Envoy YAML 同构)经 json_format 转成 protobuf。
用 ttmp_venv 运行(需要 grpcio 和 xds-protos)。"""
import grpc, threading, queue, time, uuid, collections
from concurrent import futures
from google.protobuf import json_format, any_pb2
from envoy.service.discovery.v3 import ads_pb2_grpc, discovery_pb2
from envoy.config.listener.v3 import listener_pb2
from envoy.config.route.v3 import route_pb2
from envoy.config.cluster.v3 import cluster_pb2
from envoy.config.endpoint.v3 import endpoint_pb2
from envoy.extensions.filters.network.http_connection_manager.v3 import http_connection_manager_pb2
from envoy.extensions.filters.http.router.v3 import router_pb2
LDS = 'type.googleapis.com/envoy.config.listener.v3.Listener'; RDS = 'type.googleapis.com/envoy.config.route.v3.RouteConfiguration'
CDS = 'type.googleapis.com/envoy.config.cluster.v3.Cluster'; EDS = 'type.googleapis.com/envoy.config.endpoint.v3.ClusterLoadAssignment'
CLS = {LDS: listener_pb2.Listener, RDS: route_pb2.RouteConfiguration, CDS: cluster_pb2.Cluster, EDS: endpoint_pb2.ClusterLoadAssignment}
SHORT = {LDS: 'LDS', RDS: 'RDS', CDS: 'CDS', EDS: 'EDS'}
class Stream:
    def __init__(self): self.q = queue.Queue(); self.sent_ver = {}; self.sent_names = {}
class Ads(ads_pb2_grpc.AggregatedDiscoveryServiceServicer):
    def __init__(self):
        self.res = {t: {} for t in CLS}; self.ver = {t: 0 for t in CLS}; self.streams = []; self.lk = threading.Lock(); self.log = []; self.t0 = time.time(); self.server = None
    def _log(self, kind, **kw):
        with self.lk: self.log.append(dict(t=round(time.time() - self.t0, 3), kind=kind, **kw))
    def set(self, type_url, mapping):
        """mapping: {name: dict}。整体替换这一类资源,版本号 +1,推送给所有连接"""
        msgs = {n: json_format.ParseDict(d, CLS[type_url]()) for n, d in mapping.items()}
        with self.lk: self.res[type_url] = msgs; self.ver[type_url] += 1; sts = list(self.streams)
        for st in sts: self._respond(st, type_url, None, force=False)
    def _respond(self, st, type_url, names, force):
        with self.lk:
            cur = self.ver[type_url]; res = self.res[type_url]
            use = st.sent_names.get(type_url) if names is None else names
            if not force and st.sent_ver.get(type_url) == cur: return
            sel = [(n, m) for n, m in res.items() if not use or n in use]
            st.sent_ver[type_url] = cur; st.sent_names[type_url] = names if names is not None else st.sent_names.get(type_url)
        any_list = []
        for n, m in sel:
            a = any_pb2.Any(); a.Pack(m); any_list.append(a)
        nonce = uuid.uuid4().hex[:8]; self._log('send', type=SHORT[type_url], version=str(cur), names=[n for n, _ in sel], nonce=nonce)
        st.q.put(discovery_pb2.DiscoveryResponse(version_info=str(cur), resources=any_list, type_url=type_url, nonce=nonce))
    def StreamAggregatedResources(self, request_iterator, context):
        st = Stream()
        with self.lk: self.streams.append(st)
        self._log('stream_open')
        def reader():
            try:
                for r in request_iterator:
                    t = r.type_url; names = list(r.resource_names)
                    if r.error_detail.message: self._log('nack', type=SHORT.get(t, t), version=r.version_info, error=r.error_detail.message[:200])
                    else: self._log('request', type=SHORT.get(t, t), version=r.version_info or '(空)', names=names, nonce=r.response_nonce or '(空)')
                    if t not in CLS: continue
                    if r.error_detail.message: continue
                    if not r.response_nonce: self._respond(st, t, names or None, force=True)          # 第一次请求:给当前全部(或请求的名字)
                    else:
                        prev = st.sent_names.get(t)
                        if (names or None) != prev: self._respond(st, t, names or None, force=True)       # 订阅的名字变了
                        else: self._respond(st, t, None, force=False)                                   # 否则只在版本变了才发
            except Exception: pass
            finally: st.q.put(None)
        threading.Thread(target=reader, daemon=True).start()
        try:
            while context.is_active():
                try: item = st.q.get(timeout=0.2)
                except queue.Empty: continue
                if item is None: break
                yield item
        finally:
            with self.lk:
                if st in self.streams: self.streams.remove(st)
            self._log('stream_close')
    def serve(self, port):
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=16)); ads_pb2_grpc.add_AggregatedDiscoveryServiceServicer_to_server(self, self.server)
        self.server.add_insecure_port(f'127.0.0.1:{port}'); self.server.start(); return self
    def stop(self):
        if self.server: self.server.stop(0)
