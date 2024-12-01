from robyn import Robyn
from robyn_admin.core.admin import AdminSite, ModelAdmin
from models import register_tortoise, OrderDetails, Orders, ProductCategory, Products, Users
from robyn_admin.models import AdminUser
from tortoise.models import Model
from tortoise import fields
from datetime import datetime
import base64
from robyn_admin.core.fields import (
    DisplayType, TableField, FormField, SearchField, 
    FilterField, Action, RowAction
)
import os
from typing import List, Dict, Any
from robyn_admin.core.filters import SelectFilter, DateRangeFilter, InputFilter

app = Robyn(__file__)

app.serve_directory(
    route="/static/uploads/products/images",
    directory_path="C:\\Users\\Administrator\\Desktop\\robyn_admin\\static\\uploads\\products\\images",
)

class UsersAdmin(ModelAdmin):
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
        )
    ]
    
    # 表单字段配置（编辑用）
    form_fields = [
        FormField("username", label="用户名", required=True),
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

# class OrdersAdmin(ModelAdmin):
#     # 表格显示配置
#     table_fields = [
#         TableField("id", label="ID", hidden=True),
#         TableField(
#             name="order_no",
#             label="订单号",
#             sortable=True
#         ),
#         TableField(
#             name="user",  # 外键字段
#             label="用户",
#             display_type=DisplayType.FOREIGN_KEY,
#             formatter=lambda x: x.username if x else ''  # 显示用户名
#         ),
#         TableField(
#             name="total_amount",
#             label="总金额",
#             formatter=lambda x: f"¥{x:.2f}"
#         ),
#         TableField(
#             name="status",
#             label="状态",
#             display_type=DisplayType.STATUS,
#             formatter=lambda x: {
#                 0: '<span class="badge bg-warning">待支付</span>',
#                 1: '<span class="badge bg-info">已支付</span>',
#                 2: '<span class="badge bg-primary">已发货</span>',
#                 3: '<span class="badge bg-success">已完成</span>',
#                 4: '<span class="badge bg-danger">已取消</span>'
#             }.get(x, str(x))
#         ),
#         TableField(
#             name="contact_name",
#             label="联系人"
#         ),
#         TableField(
#             name="contact_phone",
#             label="联系电话"
#         ),
#         TableField(
#             name="created_at",
#             label="创建时间",
#             display_type=DisplayType.DATETIME,
#             sortable=True
#         )
#     ]
    
#     # 表单字段配置
#     form_fields = [
#         FormField(
#             name="user",  # 外键字段
#             label="用户",
#             field_type=DisplayType.FOREIGN_KEY,
#             required=True,
#             choices_loader=lambda: Users.all().values('id', 'username')  # 动态加载用户列表
#         ),
#         FormField("order_no", label="订单号", required=True),
#         FormField("total_amount", label="总金额", required=True),
#         FormField(
#             name="status",
#             label="状态",
#             field_type=DisplayType.SELECT,
#             choices={
#                 0: "待支付",
#                 1: "已支付",
#                 2: "已发货",
#                 3: "已完成",
#                 4: "已取消"
#             }
#         ),
#         FormField("contact_name", label="联系人", required=True),
#         FormField("contact_phone", label="联系电话", required=True),
#         FormField("address", label="收货地址", required=True)
#     ]
    
#     # 内联表单（订单详情）
#     inlines = [
#         {
#             "model": OrderDetails,
#             "fields": [
#                 FormField(
#                     name="product",  # 外键字段
#                     label="商品",
#                     field_type=DisplayType.FOREIGN_KEY,
#                     required=True,
#                     choices_loader=lambda: Products.all().values('id', 'name')
#                 ),
#                 FormField("quantity", label="数量", required=True),
#                 FormField("price", label="单价", required=True)
#             ]
#         }
#     ]
    
#     # 搜索配置
#     search_fields = [
#         SearchField("order_no", placeholder="输入订单号搜索"),
#         SearchField("contact_name", placeholder="输入联系人搜索"),
#         SearchField("contact_phone", placeholder="输入联系电话搜索")
#     ]
    
#     # 过滤器配置
#     filter_fields = [
#         FilterField(
#             name="status",
#             choices={
#                 0: "待支付",
#                 1: "已支付",
#                 2: "已发货",
#                 3: "已完成",
#                 4: "已取消"
#             }
#         ),
#         FilterField(
#             name="user",
#             choices_loader=lambda: Users.all().values('id', 'username')
#         )
#     ]
    
#     # 默认排序
#     default_ordering = ["-created_at"]

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

# # 注册模型
admin_site.register_model(Users, UsersAdmin)
# admin_site.register_model(Orders, OrdersAdmin)


if __name__ == "__main__":
    app.start(host="127.0.0.1", port=8100)