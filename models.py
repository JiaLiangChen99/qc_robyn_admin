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
    """用户表"""
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, description="用户名")
    password = fields.CharField(max_length=128, description="密码")
    email = fields.CharField(max_length=50, description="邮箱")
    phone = fields.CharField(max_length=20, description="手机号")
    is_active = fields.BooleanField(default=True, description="是否激活")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    
    class Meta:
        table = "users"
        table_description = "用户信息表"

class ProductCategory(Model):
    """商品分类表"""
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, description="分类名称")
    parent_id = fields.IntField(null=True, description="父分类ID")
    sort_order = fields.IntField(default=0, description="排序")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")

    class Meta:
        table = "product_category"
        table_description = "商品分类表"

class Products(Model):
    """商品表"""
    id = fields.IntField(pk=True)
    category_id = fields.IntField(description="分类ID")  # 不设置外键约束
    name = fields.CharField(max_length=100, description="商品名称")
    price = fields.DecimalField(max_digits=10, decimal_places=2, description="价格")
    stock = fields.IntField(default=0, description="库存")
    description = fields.TextField(null=True, description="商品描述")
    status = fields.IntField(default=1, description="状态：1-上架，0-下架")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")
    image = fields.CharField(max_length=255, null=True, description="商品图片")
    class Meta:
        table = "products"
        table_description = "商品信息表"

class Orders(Model):
    """订单表"""
    id = fields.IntField(pk=True)
    order_no = fields.CharField(max_length=50, unique=True, description="订单编号")
    user_id = fields.IntField(description="用户ID")  # 不设置外键约束
    total_amount = fields.DecimalField(max_digits=10, decimal_places=2, description="订单总金额")
    status = fields.IntField(default=0, description="订单状态：0-待支付，1-已支付，2-已发货，3-已完成，4-已取消")
    address = fields.CharField(max_length=255, description="收货地址")
    contact_name = fields.CharField(max_length=50, description="联系人")
    contact_phone = fields.CharField(max_length=20, description="联系电话")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        table = "orders"
        table_description = "订单信息表"

class OrderDetails(Model):
    """订单详情表"""
    id = fields.IntField(pk=True)
    order_no = fields.CharField(max_length=50, description="订单编号")  # 不设置外键约束
    product_id = fields.IntField(description="商品ID")  # 不设置外键约束
    quantity = fields.IntField(description="购买数量")
    price = fields.DecimalField(max_digits=10, decimal_places=2, description="购买时单价")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")

    class Meta:
        table = "order_details"
        table_description = "订单详情表"

# 插入测试数据的函数
async def init_test_data():
    # 创建用户
    await Users.create(
        username="test_user",
        password="password123",
        email="test@example.com",
        phone="13800138000"
    )
    
    # 创建商品分类
    category1 = await ProductCategory.create(name="电子产品", parent_id=None)
    category2 = await ProductCategory.create(name="服装", parent_id=None)
    await ProductCategory.create(name="手机", parent_id=category1.id)
    await ProductCategory.create(name="T恤", parent_id=category2.id)
    
    # 创建商品
    await Products.create(
        category_id=1,
        name="iPhone 13",
        price=6999.00,
        stock=100,
        description="苹果最新手机",
        image="https://example.com/images/iphone13.jpg"
    )
    await Products.create(
        category_id=2,
        name="夏季短袖T恤",
        price=99.00,
        stock=200,
        description="纯棉舒适",
        image="https://example.com/images/tshirt.jpg"
    )
    
    # 创建订单
    order = await Orders.create(
        order_no="ORD" + datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
        user_id=1,
        total_amount=7098.00,
        status=1,
        address="北京市朝阳区xxx街道",
        contact_name="张三",
        contact_phone="13900139000"
    )
    
    # 创建订单详情
    await OrderDetails.create(
        order_no=order.order_no,
        product_id=1,
        quantity=1,
        price=6999.00
    )
    await OrderDetails.create(
        order_no=order.order_no,
        product_id=2,
        quantity=1,
        price=99.00
    )
