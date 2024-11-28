# tortoise-orm 配置sqllite数据库，创建一个简单的用户表
from tortoise.models import Model
from tortoise import Tortoise, connections, fields
from tortoise.log import logger

from robyn import Robyn
from typing import Optional, Dict, Iterable, Union
from types import ModuleType, FunctionType

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
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    email = fields.CharField(max_length=255)

class Shop(Model):
    id = fields.IntField(pk=True)
    shop_name = fields.CharField(max_length=255)
    shop_address = fields.CharField(max_length=255)
