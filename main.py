import pathlib
import os

from models import register_tortoise, init_test_data

from robyn import Robyn, Request, Response
from robyn.templating import JinjaTemplate

app = Robyn(__file__)

# 本地创建一个data.db数据库
register_tortoise(
    app, db_url="sqlite://data.db", modules={"models": ["models"]}, generate_schemas=True,
)

# 启动事件
async def startup_handler():
    await init_test_data()
    print("Starting up")

app.startup_handler(startup_handler)

# 消息中间件

@app.before_request("/")
async def hello_before_request(request: Request):
    request.headers["before"] = "sync_before_request"
    return request

@app.after_request("/")
def hello_after_request(response: Response):
    response.headers.set("after", "sync_after_request")
    return response
@app.get("/")
async def h(request):
    return "Hello, world"


# 全局依赖注入
GLOBAL_DEPENDENCY = "GLOBAL DEPENDENCY"
app.inject_global(GLOBAL_DEPENDENCY=GLOBAL_DEPENDENCY)

@app.get("/sync/global_di")
async def sync_global_di(request, global_dependencies):
    return global_dependencies["GLOBAL_DEPENDENCY"]

# 路由级别依赖注入
ROUTER_DEPENDENCY = "ROUTER DEPENDENCY"
app.inject(ROUTER_DEPENDENCY=ROUTER_DEPENDENCY)
@app.get("/sync/global_di")
async def sync_global_di(r, router_dependencies): # r is the request object
    return router_dependencies["ROUTER_DEPENDENCY"]


# jinja2渲染设置
current_file_path = pathlib.Path(__file__).parent.resolve()
jinja_template = JinjaTemplate(os.path.join(current_file_path, "templates"))

@app.get("/frontend")
async def get_frontend(request):
    context = {"framework": "Robyn", "templating_engine": "Jinja2"}
    return jinja_template.render_template("index.html", **context)

if __name__ == "__main__":
    app.start(host="127.0.0.1", port=3010)
