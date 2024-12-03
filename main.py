from robyn import Robyn
from robyn_admin.core.admin import AdminSite, ModelAdmin
from models import register_tortoise, Users
from robyn_admin.models import AdminUser
from robyn_admin.core.fields import (
    DisplayType, TableField, FormField, SearchField, 
)
from robyn_admin.core.filters import SelectFilter, DateRangeFilter, InputFilter
from robyn_admin.core.admin import MenuItem

app = Robyn(__file__)

app.serve_directory(
    route="/static/uploads/products/images",
    directory_path="C:\\Users\\Administrator\\Desktop\\robyn_admin\\static\\uploads\\products\\images",
)

class UsersAdmin(ModelAdmin):
    verbose_name = "用户"
    menu_group = "用户管理"
    menu_icon = "bi bi-person"
    menu_order = 1
    
    # 表格显示配置
    table_fields = [
        TableField(
            name="id", 
            label="ID", 
            display_type=DisplayType.TEXT,
            editable=False,
            hidden=True
        ),
        TableField(
            "username", 
            label="用户名",
            display_type=DisplayType.TEXT, 
            sortable=True,
            formatter=lambda x: str(x)
        ),
        TableField(
            "email", 
            label="邮箱", 
            display_type=DisplayType.TEXT,
            formatter=lambda x: str(x)
        ),
        TableField(
            "is_active", 
            label="状态",
            display_type=DisplayType.STATUS,
            filterable=True,
            formatter=lambda x: {
                True: '正常',
                False: '禁用',
            }.get(x, str(x))
        ),
        TableField(
            "created_at",
            label="创建时间",
            display_type=DisplayType.DATETIME,
            formatter=lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if x else ''
        )
    ]
    
    # 表单字段配置（编辑用）
    form_fields = [
        FormField("username", label="用户名", required=True, readonly=True),
        FormField("email", label="邮箱", field_type=DisplayType.EMAIL),
        FormField("is_active", label="状态", field_type=DisplayType.SELECT, choices={
            '正常': True, 
            '禁用': False
        })
    ]
    
    
    # 添加表单字段配置
    add_form_fields = [
        FormField("username", label="用户名", required=True),
        FormField("email", label="邮箱", field_type=DisplayType.EMAIL, required=True),
        FormField(
            "password", 
            label="密码", 
            field_type=DisplayType.PASSWORD,
            required=True,
            processor=lambda x: AdminUser.hash_password(x)  # 密码处理函数
        ),
        FormField("phone", label="电话", field_type=DisplayType.EMAIL, required=True),
        FormField("is_active", label="状态", field_type=DisplayType.SELECT, choices={"正常": True, "禁用": False}),
        FormField('create_at', label="出生日期", field_type=DisplayType.DATE)
    ]
    
    # 搜索配置
    search_fields = [
        SearchField("username", placeholder="输入用户名搜索", label="用户名"),
    ]

    # 默认排序
    default_ordering = ["-created_at"]
    
    # 开启编辑
    enable_edit = True

    add_form_title = "添加新用户"  # 自定义添加表单标题
    edit_form_title = "修改用户信息"  # 自定义编辑表单标题

    # 添加过滤器配置
    filter_fields = [
        InputFilter(
            name="username",
            label="用户名",
            placeholder="请输入用户名",
            operator='icontains'  # 使用模糊匹配
        ),
        InputFilter(
            name="email",
            label="邮箱",
            placeholder="请输入邮箱",
            operator='icontains'
        ),
        SelectFilter(
            name="is_active",
            label="状态",
            choices={
                True: "正常",
                False: "禁用"
            }
        ),
        DateRangeFilter(
            name="created_at",
            label="创建时间"
        )
    ]

class AdminUserAdmin(ModelAdmin):
    verbose_name = "管理员"
    menu_group = "系统管理"
    menu_icon = "bi bi-person-gear"
    menu_order = 1
    
    # 表格显示配置
    table_fields = [
        TableField(
            name="id", 
            label="ID", 
            display_type=DisplayType.TEXT,
            editable=False,
            hidden=True
        ),
        TableField(
            "username", 
            label="用户名",
            display_type=DisplayType.TEXT, 
            sortable=True,
            formatter=lambda x: str(x)
        ),
        TableField(
            "email", 
            label="邮箱", 
            display_type=DisplayType.TEXT,
            formatter=lambda x: str(x)
        ),
        TableField(
            "is_superuser", 
            label="管理员",
            display_type=DisplayType.STATUS,
            filterable=True,
            formatter=lambda x: {
                True: '<span class="badge bg-success">是</span>',
                False: '<span class="badge bg-secondary">否</span>'
            }.get(x, str(x))
        ),
        TableField(
            "is_active", 
            label="状态",
            display_type=DisplayType.STATUS,
            filterable=True,
            formatter=lambda x: {
                True: '<span class="badge bg-success">正常</span>',
                False: '<span class="badge bg-danger">禁用</span>'
            }.get(x, str(x))
        ),
        TableField(
            "last_login",
            label="最后登录",
            display_type=DisplayType.DATETIME,
            formatter=lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if x else '-'
        ),
        TableField(
            "created_at",
            label="创建时间",
            display_type=DisplayType.DATETIME,
            formatter=lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if x else ''
        )
    ]
    
    # 表单字段配置（编辑用）
    form_fields = [
        FormField("username", label="用户名", required=True, readonly=True),
        FormField("email", label="邮箱", field_type=DisplayType.EMAIL),
        FormField("is_superuser", label="管理员", field_type=DisplayType.SELECT, choices={
            True: "是", 
            False: "否"
        }),
        FormField("is_active", label="状态", field_type=DisplayType.SELECT, choices={
            True: "正常", 
            False: "禁用"
        })
    ]
    
    # 添加表单字段配置
    add_form_fields = [
        FormField("username", label="用户名", required=True),
        FormField("email", label="邮箱", field_type=DisplayType.EMAIL, required=True),
        FormField(
            "password", 
            label="密码", 
            field_type=DisplayType.PASSWORD,
            required=True,
            processor=lambda x: AdminUser.hash_password(x)  # 密码处理函数
        ),
        FormField("is_superuser", label="管理员", field_type=DisplayType.SELECT, choices={
            True: "是", 
            False: "否"
        }),
        FormField("is_active", label="状态", field_type=DisplayType.SELECT, choices={
            True: "正常", 
            False: "禁用"
        })
    ]
    
    # 搜索配置
    search_fields = [
        SearchField("username", placeholder="输入用户名搜索", label="用户名"),
        SearchField("email", placeholder="输入邮箱搜索", label="邮箱")
    ]

    # 过滤器配置
    filter_fields = [
        InputFilter(
            name="username",
            label="用户名",
            placeholder="请输入用户名"
        ),
        InputFilter(
            name="email",
            label="邮箱",
            placeholder="请输入邮箱"
        ),
        SelectFilter(
            name="is_superuser",
            label="管理员",
            choices={
                True: "是",
                False: "否"
            }
        ),
        SelectFilter(
            name="is_active",
            label="状态",
            choices={
                True: "正常",
                False: "禁用"
            }
        ),
        DateRangeFilter(
            name="last_login",
            label="最后登录时间"
        )
    ]

    # 默认排序
    default_ordering = ["-created_at"]
    
    # 开启编辑
    enable_edit = True

    add_form_title = "添加管理员"
    edit_form_title = "编辑管理员信息"

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

# 创建admin站点
admin_site = AdminSite(
    app,
    db_url="sqlite://app.db",
    modules={
        "models": ["models", "robyn_admin.models"]
    },
    generate_schemas=True
)

# 注册菜单组
admin_site.register_menu(MenuItem(
    name="系统管理",
    icon="bi bi-gear",
    order=1
))

admin_site.register_menu(MenuItem(
    name="用户管理",
    icon="bi bi-people",
    order=2
))

# 注册模型
admin_site.register_model(AdminUser, AdminUserAdmin)
admin_site.register_model(Users, UsersAdmin)


if __name__ == "__main__":
    app.start(host="127.0.0.1", port=8100)