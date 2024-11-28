from robyn import Robyn
from robyn_admin.core.admin import AdminSite
from models import Users, Shop, register_tortoise

app = Robyn(__file__)

# 先配置数据库
register_tortoise(
    app,
    db_url="sqlite://db.sqlite3",
    modules={"models": ["models"]},  # AdminSite会自动添加robyn_admin.models
    generate_schemas=True
)

# 创建admin站点 - 复用已有配置
admin_site = AdminSite(
    app,
    db_url="sqlite://admin.db",
    modules={"models": ["robyn_admin.models"]},
    generate_schemas=True
)

# 注册模型
admin_site.register_model(Users)
admin_site.register_model(Shop)

if __name__ == "__main__":
    app.start(host="127.0.0.1", port=8100)