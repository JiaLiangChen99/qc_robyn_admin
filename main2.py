from robyn import Robyn
from robyn_admin.core.admin import AdminSite, ModelAdmin
from models import Users, Shop, register_tortoise

app = Robyn(__file__)

# 配置数据库
DB_CONFIG = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.sqlite",
            "credentials": {"file_path": "app.db"}
        }
    },
    "apps": {
        "models": {
            "models": ["models", "robyn_admin.models"],
            "default_connection": "default",
        }
    },
    "use_tz": False,
    "timezone": "Asia/Shanghai"
}

# 注册数据库
register_tortoise(
    app,
    config=DB_CONFIG,
    generate_schemas=True
)

# 创建 Users 的管理类
class UsersAdmin(ModelAdmin):
    list_display = ['id', 'name', 'email']
    search_fields = ['name', 'email']
    readonly_fields = ['id']
    
# 创建 Shop 的管理类
class ShopAdmin(ModelAdmin):
    list_display = ['id', 'shop_name', 'shop_address']
    search_fields = ['shop_name']
    readonly_fields = ['id']

# 创建admin站点 - 提供完整的配置
admin_site = AdminSite(
    app,
    db_url="sqlite://app.db",
    modules={
        "models": ["models", "robyn_admin.models"]
    },
    generate_schemas=True
)

# 注册模型
admin_site.register_model(Users, UsersAdmin)
admin_site.register_model(Shop, ShopAdmin)

# 添加调试信息
print("已注册的模型:", admin_site.models)

if __name__ == "__main__":
    app.start(host="127.0.0.1", port=8100)