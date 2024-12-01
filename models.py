# tortoise-orm 配置sqllite数据库，创建一个简单的用户表
from tortoise.models import Model
from tortoise import Tortoise, connections, fields
from tortoise.log import logger

from robyn import Robyn
from typing import Optional, Dict, Iterable, Union
from types import ModuleType, FunctionType
import datetime

## 注册tortoise-orm
def register_tortoise(
    app: Robyn,
    config: Optional[dict] = None,
    config_file: Optional[str] = None,
    db_url: Optional[str] = None,
    modules: Optional[Dict[str, Iterable[Union[str, ModuleType]]]] = None,
    generate_schemas: bool = False,
    startu_up_function: FunctionType = None
):
    async def tortoise_init() -> None:
        await Tortoise.init(config=config, config_file=config_file, db_url=db_url, modules=modules)
        await Tortoise.generate_schemas()
        # 插入测试数据
        await init_test_data()
        logger.info(
            "Tortoise-ORM started, %s, %s", connections._get_storage(), Tortoise.apps
        )

    @app.startup_handler
    async def init_orm():  # pylint: disable=W0612
        if startu_up_function:
            await startu_up_function()
        await tortoise_init()
        if generate_schemas:
            logger.info("Tortoise-ORM generating schema")
            await Tortoise.generate_schemas()
    
    @app.shutdown_handler
    async def shutdown_orm():  # pylint: disable=W0612
        await Tortoise.close_connections()
        logger.info("Tortoise-ORM connections closed")
# 配置数据库


class Users(Model):
    """用户模型"""
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    email = fields.CharField(max_length=100)
    password = fields.CharField(max_length=128)
    phone = fields.CharField(max_length=20, null=True)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"

class ProductCategory(Model):
    """商品分类"""
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50)
    parent = fields.ForeignKeyField('models.ProductCategory', related_name='children', null=True)
    sort_order = fields.IntField(default=0)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "product_categories"

class Products(Model):
    """商品"""
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    category = fields.ForeignKeyField('models.ProductCategory', related_name='products')
    description = fields.TextField()
    price = fields.DecimalField(max_digits=10, decimal_places=2)
    stock = fields.IntField(default=0)
    status = fields.IntField(default=1)  # 1: 上架, 0: 下架
    image = fields.CharField(max_length=255, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "products"

class Orders(Model):
    """订单"""
    id = fields.IntField(pk=True)
    order_no = fields.CharField(max_length=50, unique=True)
    user = fields.ForeignKeyField('models.Users', related_name='orders')
    total_amount = fields.DecimalField(max_digits=10, decimal_places=2)
    status = fields.IntField(default=0)  # 0: 待支付, 1: 已支付, 2: 已发货, 3: 已完成, 4: 已取消
    contact_name = fields.CharField(max_length=50)
    contact_phone = fields.CharField(max_length=20)
    address = fields.CharField(max_length=255)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "orders"

class OrderDetails(Model):
    """订单详情"""
    id = fields.IntField(pk=True)
    order = fields.ForeignKeyField('models.Orders', related_name='details')
    product = fields.ForeignKeyField('models.Products', related_name='order_details')
    quantity = fields.IntField()
    price = fields.DecimalField(max_digits=10, decimal_places=2)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "order_details"

# 添加一些测试数据
async def init_test_data():
    # 创建用户
    user = await Users.create(
        username="test_user",
        email="test@example.com",
        password="password123",
        phone="1234567890"
    )

    # 创建商品分类
    root_category = await ProductCategory.create(
        name="电子产品",
        sort_order=1
    )

    sub_category1 = await ProductCategory.create(
        name="手机",
        parent=root_category,
        sort_order=1
    )

    sub_category2 = await ProductCategory.create(
        name="电脑",
        parent=root_category,
        sort_order=2
    )

    # 创建商品
    product1 = await Products.create(
        name="iPhone 13",
        category=sub_category1,
        description="苹果最新手机",
        price=6999.00,
        stock=100,
        status=1,
        image="/static/uploads/products/iphone13.jpg"
    )

    product2 = await Products.create(
        name="MacBook Pro",
        category=sub_category2,
        description="苹果专业笔记本",
        price=12999.00,
        stock=50,
        status=1,
        image="/static/uploads/products/macbook.jpg"
    )

    # 创建订单
    order = await Orders.create(
        order_no=f"ORD{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
        user=user,
        total_amount=19998.00,
        status=1,
        contact_name="张三",
        contact_phone="13800138000",
        address="北京市朝阳区xxx街道"
    )

    # 创建订单详情
    await OrderDetails.create(
        order=order,
        product=product1,
        quantity=1,
        price=6999.00
    )

    await OrderDetails.create(
        order=order,
        product=product2,
        quantity=1,
        price=12999.00
    )
