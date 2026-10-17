import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f114'); R = {}
import json
from flask import Flask, jsonify, request
from flask.views import MethodView
from marshmallow import Schema, fields, validate
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec_webframeworks.flask import FlaskPlugin
from openapi_spec_validator import validate as validate_spec
import flask_smorest
from flask_smorest import Api, Blueprint
class UserSchema(Schema):
    id = fields.Int(dump_only=True); name = fields.Str(required=True, validate=validate.Length(min=1, max=20)); age = fields.Int(validate=validate.Range(min=0, max=150))
print('== 一:apispec:从 marshmallow 模型和视图函数的 docstring 生成 OpenAPI 文档')
app = Flask('o1'); app.logger.disabled = True
@app.get('/users/<int:uid>')
def get_user(uid):
    """获取用户
    ---
    get:
      summary: 获取一个用户
      parameters:
        - {name: uid, in: path, required: true, schema: {type: integer}}
      responses:
        200:
          description: 用户
          content:
            application/json:
              schema: UserSchema
        404: {description: 不存在}
    """
    return {}
spec = APISpec(title='Demo API', version='1.0.0', openapi_version='3.0.3', plugins=[FlaskPlugin(), MarshmallowPlugin()])
spec.components.schema('User', schema=UserSchema)
with app.test_request_context(): spec.path(view=get_user)
d = spec.to_dict(); print('  顶层键:', list(d)); print('  paths:', list(d['paths'])); print('  components.schemas:', list(d['components']['schemas']))
print('  User 模型生成的 schema:', json.dumps(d['components']['schemas']['User'], ensure_ascii=False)); R['schema'] = d['components']['schemas']['User']
print('  视图 docstring 里引用 "UserSchema" 被解析成:', d['paths']['/users/{uid}']['get']['responses']['200']['content']['application/json']['schema']); R['ref'] = d['paths']['/users/{uid}']['get']['responses']['200']['content']['application/json']['schema']
print('  Flask 的 <int:uid> 路由被转成 OpenAPI 的路径:', list(d['paths'])[0])
try: validate_spec(d); print('  openapi-spec-validator:文档合法'); R['valid1'] = True
except Exception as e: print('  文档不合法:', str(e)[:100]); R['valid1'] = False
print()
print('== 二:校验规则会进文档:Length(1,20)、Range(0,150)、required、dump_only')
p = d['components']['schemas']['User']['properties']; print('  name:', p['name'], '| age:', p['age'], '| id:', p['id']); print('  required:', d['components']['schemas']['User'].get('required')); R['rules'] = [p['name'], p['age'], p['id'], d['components']['schemas']['User'].get('required')]
print()
print('== 三:flask-smorest:装饰器同时做校验、序列化和生成文档,并自带 /openapi.json 与 Swagger UI')
app2 = Flask('o2'); app2.logger.disabled = True
app2.config.update(API_TITLE='Demo', API_VERSION='v1', OPENAPI_VERSION='3.0.3', OPENAPI_URL_PREFIX='/', OPENAPI_JSON_PATH='openapi.json', OPENAPI_SWAGGER_UI_PATH='/docs', OPENAPI_SWAGGER_UI_URL='https://cdn.jsdelivr.net/npm/swagger-ui-dist/')
api = Api(app2); blp = Blueprint('users', __name__, url_prefix='/users', description='用户')
@blp.route('/')
class Users(MethodView):
    @blp.response(200, UserSchema(many=True))
    def get(self): return [{'id': 1, 'name': 'ann', 'age': 30}]
    @blp.arguments(UserSchema)
    @blp.response(201, UserSchema)
    def post(self, data): return {'id': 2, **data}
api.register_blueprint(blp); c = app2.test_client()
r = c.get('/openapi.json'); sp = r.get_json(); print('  GET /openapi.json →', r.status_code, '| openapi =', sp['openapi'], '| paths =', list(sp['paths'])); R['smorest_paths'] = list(sp['paths'])
print('  /users/ 下的方法:', list(sp['paths']['/users/']), '| POST 的响应码:', list(sp['paths']['/users/']['post']['responses'])); R['smorest_post'] = list(sp['paths']['/users/']['post']['responses'])
try: validate_spec(sp); print('  文档合法'); R['valid2'] = True
except Exception as e: print('  文档不合法:', str(e)[:100]); R['valid2'] = False
r = c.get('/docs'); print('  GET /docs(Swagger UI)→', r.status_code, r.content_type.split(';')[0], '| 页面里引用的脚本源:', 'cdn.jsdelivr.net' in r.get_data(as_text=True)); R['docs'] = [r.status_code, 'cdn.jsdelivr.net' in r.get_data(as_text=True)]
print('  (Swagger UI 的 JS 来自 CDN——离线环境或有内容安全策略的站点要自己托管,本篇没有在浏览器里渲染它)')
print()
print('== 四:smorest 的自动校验:请求体不合法时返回 422,格式固定')
r = c.post('/users/', json={'name': '', 'age': 200}); print('  POST {name:"", age:200} →', r.status_code, json.dumps(r.get_json(), ensure_ascii=False)[:200]); R['422'] = [r.status_code, r.get_json()]
r = c.post('/users/', json={'name': 'bob', 'extra': 1}); print('  多余字段 extra →', r.status_code, r.get_json().get('errors')); R['extra'] = [r.status_code, r.get_json().get('errors')]
r = c.post('/users/', json={'name': 'bob', 'age': 5}); print('  合法 →', r.status_code, r.get_json()); R['ok'] = [r.status_code, r.get_json()]
print('  文档里写了 422 响应吗:', '422' in sp['paths']['/users/']['post']['responses']); R['doc422'] = '422' in sp['paths']['/users/']['post']['responses']
print()
print('== 五:代码改了,文档跟着变(给 age 加 required)')
class UserSchema2(UserSchema): age = fields.Int(required=True)
spec2 = APISpec(title='D', version='1', openapi_version='3.0.3', plugins=[MarshmallowPlugin()]); spec2.components.schema('User', schema=UserSchema2)
print('  required 变成:', spec2.to_dict()['components']['schemas']['User'].get('required'), '(之前是 [\'name\'])'); R['drift'] = spec2.to_dict()['components']['schemas']['User'].get('required')
print('  手写的 YAML docstring 不会自动跟着变——这部分仍要靠人维护')
save('f114', R)
