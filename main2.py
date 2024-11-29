from robyn import Robyn
from robyn_admin.core.admin import AdminSite, ModelAdmin
from models import register_tortoise, OrderDetails, Orders, ProductCategory, Products, Users
from tortoise.models import Model
from tortoise import fields
from datetime import datetime
import base64
from enum import Enum
from robyn_admin.core.fields import TableMapping, FormMapping, FilterMapping, FieldType

app = Robyn(__file__)

class DisplayType(Enum):
    """显示类型枚举"""
    TEXT = 'text'           # 普通文本
    DATE = 'date'          # 日期
    DATETIME = 'datetime'  # 日期时间
    IMAGE = 'image'        # 图片
    STATUS = 'status'      # 状态
    BOOLEAN = 'boolean'    # 布尔值
    LINK = 'link'          # 链接
    HTML = 'html'          # HTML内容
    CUSTOM = 'custom'      # 自定义渲染

class UsersAdmin(ModelAdmin):
    list_display = ['id', 'username', 'email', 'phone', 'is_active', 'created_at']
    list_display_links = ['username']
    search_fields = ['username', 'email', 'phone']
    list_filter = ['is_active']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    
    # 字段标签
    field_labels = {
        'username': '用户名',
        'email': '邮箱',
        'phone': '手机号',
        'is_active': '状态',
        'created_at': '创建时间'
    }
    
    # 字段显示类型
    field_types = {
        'created_at': DisplayType.DATETIME,
        'is_active': DisplayType.STATUS
    }
    
    # 日期时间格式
    datetime_format = "%Y-%m-%d %H:%M:%S"
    
    # 状态映射
    status_choices = {
        'is_active': {
            '1': '<span class="badge bg-success">上架</span>',
            '0': '<span class="badge bg-danger">下架</span>',
            1: '<span class="badge bg-success">上架</span>',
            0: '<span class="badge bg-danger">下架</span>'
        }
    }
    
    def __init__(self, model):
        super().__init__(model)
        # 可以在这里添加额外的映射配置
        self.options.set_table_mapping(
            'is_active',
            TableMapping(
                field_type=FieldType.STATUS,
                choices={
                    True: '<span class="badge bg-success">上架</span>',
                    False: '<span class="badge bg-danger">下架</span>',
                    1: '<span class="badge bg-success">上架</span>',
                    0: '<span class="badge bg-danger">下架</span>'
                }
            )
        )

class ProductCategoryAdmin(ModelAdmin):
    list_display = ['id', 'name', 'parent_id', 'sort_order', 'created_at']
    list_display_links = ['name']
    search_fields = ['name']
    ordering = ['sort_order', 'id']
    list_editable = ['sort_order']

class ProductsAdmin(ModelAdmin):
    list_display = ['id', 'name', 'category_id', 'price', 'stock', 'status', 'created_at', 'image']
    list_display_links = ['name']
    search_fields = ['name', 'description']
    list_filter = ['status', 'category_id']
    list_editable = ['price', 'stock', 'status']
    ordering = ['-created_at']
    
    # 字段标签
    field_labels = {
        'name': '商品名称',
        'category_id': '分类',
        'price': '价格',
        'stock': '库存',
        'status': '状态',
        'created_at': '创建时间',
        'image': '商品图片'
    }
    
    # 设置字段显示类型
    field_types = {
        'created_at': DisplayType.DATETIME,
        'updated_at': DisplayType.DATETIME,
        'status': DisplayType.STATUS,
        'image': DisplayType.IMAGE  # 设置image字段为图片类型
    }
    
    # 设置状态映射
    status_choices = {
        'status': {
            0: '<span class="badge bg-danger">下架</span>',
            1: '<span class="badge bg-success">上架</span>'
        }
    }
    
    # 图片显示尺寸
    image_width = 80   # 设置图片显示宽度
    image_height = 80  # 设置图片显示高度
    
    def __init__(self, model):
        super().__init__(model)
        # 添加图片字段的表格映射
        self.options.set_table_mapping(
            'image',
            TableMapping(
                field_type=FieldType.IMAGE,
                formatter=lambda url: f'<img src="{url}" width="{self.image_width}" height="{self.image_height}" style="object-fit: cover; border-radius: 4px;" alt="商品图片">' if url else ''
            )
        )
        
        # 添加状态字段的表格映射
        self.options.set_table_mapping(
            'status',
            TableMapping(
                field_type=FieldType.STATUS,
                choices=self.status_choices['status']
            )
        )
    
    # 自定义价格显示格式
    def format_price(self, obj):
        return f'¥{obj.price:.2f}'
        
    custom_display = {
        'price': format_price
    }

class OrdersAdmin(ModelAdmin):
    list_display = ['id', 'order_no', 'user_id', 'total_amount', 'status', 'created_at']
    list_display_links = ['order_no']
    search_fields = ['order_no', 'contact_name', 'contact_phone']
    list_filter = ['status']
    readonly_fields = ['order_no', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    field_types = {
        'created_at': DisplayType.DATETIME,
        'updated_at': DisplayType.DATETIME,
        'status': DisplayType.STATUS,
    }
    
    # 设置状态映射
    status_choices = {
        'status': {
            0: '待支付',
            1: '已支付',
            2: '已发货',
            3: '已完成',
            4: '已取消'
        }
    }

class OrderDetailsAdmin(ModelAdmin):
    list_display = ['id', 'order_no', 'product_id', 'quantity', 'price']
    list_display_links = ['order_no']
    search_fields = ['order_no']
    readonly_fields = ['created_at']

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

# 注册模型
admin_site.register_model(Users, UsersAdmin)
admin_site.register_model(ProductCategory, ProductCategoryAdmin)
admin_site.register_model(Products, ProductsAdmin)
admin_site.register_model(Orders, OrdersAdmin)
admin_site.register_model(OrderDetails, OrderDetailsAdmin)

if __name__ == "__main__":
    app.start(host="127.0.0.1", port=8100)