from typing import Type, Optional, List, Dict, Union, Callable, Any
from tortoise.models import Model
from tortoise import fields
from robyn import Robyn, Request, Response
from robyn.templating import JinjaTemplate
from pathlib import Path
import os
import json
from datetime import datetime
from types import ModuleType
from urllib.parse import parse_qs
from enum import Enum
import traceback

from ..models import AdminUser
from .fields import TableMapping, FormMapping, FilterMapping, FieldType

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

class ModelAdminOptions:
    """模型管理选项类"""
    def __init__(self):
        self.table_mappings = {}
        self.form_mappings = {}
        self.filter_mappings = {}

    def set_table_mapping(self, field_name: str, mapping: 'TableMapping'):
        """设置表映射"""
        self.table_mappings[field_name] = mapping

    def set_form_mapping(self, field_name: str, mapping: 'FormMapping'):
        """设置表单映射"""
        self.form_mappings[field_name] = mapping

    def set_filter_mapping(self, field_name: str, mapping: 'FilterMapping'):
        """设置过滤映射"""
        self.filter_mappings[field_name] = mapping

class ModelAdmin:
    """模型管理类的基类"""
    list_display: List[str] = []  # 列表页显示的字段
    list_display_links: List[str] = []  # 可点击进入编辑页的字段
    list_filter: List[str] = []  # 过滤字段
    search_fields: List[str] = []  # 搜索字段
    ordering: List[str] = []  # 排序字段，使用-表示降序，如['-id', 'name']
    readonly_fields: List[str] = []  # 只读字段
    exclude: List[str] = []  # 排除的字段
    per_page: int = 10  # 每页显示数量
    list_editable: List[str] = []  # 列表页可编辑字段
    field_labels: Dict[str, str] = {}  # 字段别名，如{'name': '名称'}
    field_types: Dict[str, DisplayType] = {}  # 字段显示类型
    date_format: str = "%Y-%m-%d"  # 日期格式
    datetime_format: str = "%Y-%m-%d %H:%M:%S"  # 日期时间格式
    status_choices: Dict[str, Dict[Any, str]] = {}  # 状态选项
    image_width: int = 50  # 图片显示宽度
    image_height: int = 50  # 图片显示高度
    custom_display: Dict[str, Callable] = {}  # 自定义显示函数
    
    def __init__(self, model: Type[Model]):
        self.model = model
        self.options = ModelAdminOptions()
        self._setup_mappings()
        
    def _setup_mappings(self):
        """设置字段映射"""
        # 处理状态字段
        for field_name, field_type in self.field_types.items():
            if field_type == DisplayType.STATUS and field_name in self.status_choices:
                self.options.set_table_mapping(
                    field_name,
                    TableMapping(
                        field_type=FieldType.STATUS,
                        choices=self.status_choices[field_name]
                    )
                )
        
    async def get_queryset(self, search_term: str = None, filters: Dict = None):
        """获取查询集"""
        queryset = self.model.all()
        
        # 应用搜索
        if search_term and self.search_fields:
            from tortoise.expressions import Q
            search_conditions = Q()
            for field in self.search_fields:
                search_conditions |= Q(**{f"{field}__icontains": search_term})
            queryset = queryset.filter(search_conditions)
            
        # 应用过滤
        if filters and self.list_filter:
            filter_conditions = {}
            for field in self.list_filter:
                if field in filters and filters[field]:
                    filter_conditions[field] = filters[field]
            if filter_conditions:
                queryset = queryset.filter(**filter_conditions)
                
        # 应用排序
        if self.ordering:
            order_fields = []
            for field in self.ordering:
                if field.startswith('-'):
                    order_fields.append(field)
                else:
                    order_fields.append(field)
            queryset = queryset.order_by(*order_fields)
            
        return queryset
        
    def get_field_label(self, field_name: str) -> str:
        """获取字体显示显示名称"""
        # 优先使用field_labels中的别名
        if field_name in self.field_labels:
            return self.field_labels[field_name]
        
        # 其次尝试获取模型字段的description
        field = self.model._meta.fields_map.get(field_name)
        if field and hasattr(field, 'description'):
            return field.description
            
        # 最后返回字段名本身
        return field_name.replace('_', ' ').title()
        
    def get_list_display_links(self) -> List[str]:
        """获取可点击的字段列表"""
        if self.list_display_links:
            return self.list_display_links
        # 如果未设置，默认第一个字段可点击
        if self.list_display:
            return [self.list_display[0]]
        return ['id']
        
    def is_field_editable(self, field_name: str) -> bool:
        """判断字段是否可在列表页编辑"""
        return (
            field_name in self.list_editable 
            and field_name not in self.readonly_fields
            and field_name not in self.get_list_display_links()
        )

    def get_filter_choices(self, field_name: str) -> List[tuple]:
        """获取过滤字段的选项"""
        if field_name not in self.list_filter:
            return []
        
        field = self.model._meta.fields_map.get(field_name)
        if not field:
            return []
        
        # 处理布尔字段
        if isinstance(field, fields.BooleanField):
            return [('True', '是'), ('False', '否')]
        
        # 如果字段有status_choices定义，使用它
        if field_name in self.status_choices:
            # 确保返回字符串类型的值作为选项值
            return [(str(k), v) for k, v in self.status_choices[field_name].items()]
        
        # 如果是外键字段，返回空列表（后续可以异步获取选项）
        if field_name.endswith('_id') and isinstance(field, fields.IntField):
            return []
        
        return []
        
    async def get_object(self, pk):
        """获取单个对象"""
        return await self.model.get(id=pk)
        
    def get_form_fields(self) -> List[str]:
        """获取表单字段"""
        fields = []
        # 获取模型的所有字段
        for field_name, field in self.model._meta.fields_map.items():
            # 排除主键和被排除的字段
            if field.pk or field_name in self.exclude:
                continue
            fields.append(field_name)
        return fields

    def get_list_fields(self) -> List[str]:
        """获取列表显示字段"""
        if self.list_display:
            return self.list_display
        # 如果没有指定显示字段，返回所有字段名
        return [field_name for field_name in self.model._meta.fields_map.keys()]

    def get_display_value(self, obj: Model, field_name: str) -> str:
        """获取字段的显示值"""
        raw_value = getattr(obj, field_name)
        if raw_value is None:
            return ''
        
        # 首先检查是否有表格映射
        if field_name in self.options.table_mappings:
            mapping = self.options.table_mappings[field_name]
            return mapping.format_value(raw_value)
        
        # 获取字段类型
        field = self.model._meta.fields_map.get(field_name)
        
        # 先检查是否是状态字段
        if field_name in self.field_types and self.field_types[field_name] == DisplayType.STATUS:
            status_map = self.status_choices.get(field_name, {})
            # 确保使用正确的类型进行查找
            if isinstance(raw_value, bool):
                return status_map.get(raw_value, str(raw_value))
            elif isinstance(raw_value, int):
                return status_map.get(raw_value, str(raw_value))
            elif isinstance(raw_value, str) and raw_value.isdigit():
                return status_map.get(int(raw_value), str(raw_value))
            return status_map.get(raw_value, str(raw_value))
        
        # 自动检测日期时间字段
        if isinstance(field, fields.DatetimeField):
            if isinstance(raw_value, datetime):
                # 如果字段显示类型已设置，使用设置的格式
                if field_name in self.field_types:
                    if self.field_types[field_name] == DisplayType.DATE:
                        return raw_value.strftime(self.date_format)
                    elif self.field_types[field_name] == DisplayType.DATETIME:
                        return raw_value.strftime(self.datetime_format)
                # 默认使用datetime格式
                return raw_value.strftime(self.datetime_format)
            return str(raw_value)
            
        # 获取字段显示类型
        display_type = self.field_types.get(field_name, DisplayType.TEXT)
        
        # 根据显示类型处理值
        if display_type == DisplayType.DATE:
            if isinstance(raw_value, datetime):
                return raw_value.strftime(self.date_format)
            return raw_value
            
        elif display_type == DisplayType.DATETIME:
            if isinstance(raw_value, datetime):
                return raw_value.strftime(self.datetime_format)
            return raw_value
            
        elif display_type == DisplayType.IMAGE:
            # 处理不同类型的图片值
            if raw_value.startswith('data:image'):  # base64
                return f'<img src="{raw_value}" width="{self.image_width}" height="{self.image_height}">'
            elif raw_value.startswith(('http://', 'https://')):  # URL
                return f'<img src="{raw_value}" width="{self.image_width}" height="{self.image_height}">'
            else:  # 本地路径
                return f'<img src="/static/{raw_value}" width="{self.image_width}" height="{self.image_height}">'
                
        elif display_type == DisplayType.BOOLEAN:
            return '是' if raw_value else '否'
            
        elif display_type == DisplayType.LINK:
            # 假设raw_value是URL，可以根据需要自定义链接文本
            return f'<a href="{raw_value}" target="_blank">查看</a>'
            
        elif display_type == DisplayType.HTML:
            # 直接返回HTML内容
            return str(raw_value)
            
        elif display_type == DisplayType.CUSTOM:
            # 使用自定义显示函数
            if field_name in self.custom_display:
                return self.custom_display[field_name](obj)
            
        # 默认返回字符串值
        return str(raw_value)

    def serialize_object(self, obj, for_display=True):
        """
        将模型对象序列化为字典
        
        :param obj: 模型对象
        :param for_display: 是否用于显示（True用于表格显示，False用于表单数据）
        """
        fields = self.get_list_fields()
        if for_display:
            # 用于表格显示的序列化
            return {
                field_name: self.get_display_value(obj, field_name)
                for field_name in fields
            }
        else:
            # 用于表单数据的序列化（使用原始值）
            result = {}
            for field_name in fields:
                value = getattr(obj, field_name)
                # 处理不同类型的值
                if isinstance(value, bool):
                    result[field_name] = 1 if value else 0
                elif isinstance(value, datetime):
                    result[field_name] = value.strftime(self.datetime_format)
                else:
                    result[field_name] = str(value)
            return result

class AdminSite:
    """Admin站点主类"""
    def __init__(
        self, 
        app: Robyn, 
        name: str = 'admin',
        db_url: Optional[str] = None,
        modules: Optional[Dict[str, List[Union[str, ModuleType]]]] = None,
        generate_schemas: bool = True
    ):
        """
        初始化Admin站点
        
        :param app: Robyn应用实例
        :param name: Admin路由前缀
        :param db_url: 数据库连接URL,如果为None则尝试复用已有配置
        :param modules: 模型模块配置,如果为None则尝试复用已有配置
        :param generate_schemas: 是否自动生成数据库表结构
        """
        self.app = app
        self.name = name
        self.models: Dict[str, ModelAdmin] = {}
        self._setup_templates()
        
        # 初始化数据库
        self.db_url = db_url
        self.modules = modules
        self.generate_schemas = generate_schemas
        self._init_admin_db()
        
        # 设置路由要在数据库初始化之后
        self._setup_routes()
        self.jinja_template = JinjaTemplate(self.template_dir)

    def _init_admin_db(self):
        """初始化admin数据库"""
        from tortoise import Tortoise
        
        @self.app.startup_handler
        async def init_admin():
            # 如果没有提供配置,尝试获取已有配置
            if not self.db_url:
                if not Tortoise._inited:
                    raise Exception("数据库未初始化,请先配置数据库或提供db_url参数")
                # 复用现有配置
                current_config = Tortoise.get_connection("default").config
                self.db_url = current_config.get("credentials", {}).get("dsn")
                
            if not self.modules:
                if not Tortoise._inited:
                    raise Exception("数据库未初始化,请先配置数据库或提供modules参数")
                # 复用现有modules配置
                self.modules = dict(Tortoise.apps)
                
            # 确保admin模型和用户模型都被加载
            if "models" in self.modules:
                if isinstance(self.modules["models"], list):
                    if "robyn_admin.models" not in self.modules["models"]:
                        self.modules["models"].append("robyn_admin.models")
                    if "models" not in self.modules["models"]:
                        self.modules["models"].append("models")
                else:
                    self.modules["models"] = ["robyn_admin.models", "models", self.modules["models"]]
            else:
                self.modules["models"] = ["robyn_admin.models", "models"]
            
            # 初始化数据库连接
            if not Tortoise._inited:
                await Tortoise.init(
                    db_url=self.db_url,
                    modules=self.modules
                )
                
            if self.generate_schemas:
                await Tortoise.generate_schemas()
                
            # 创建默认超级用户
            try:
                user_exists = await AdminUser.filter(username="admin").exists()
                if not user_exists:
                    await AdminUser.create(
                        username="admin",
                        password=AdminUser.hash_password("admin"),
                        email="admin@example.com",
                        is_superuser=True
                    )
            except Exception as e:
                print(f"创建管理员账号失败: {str(e)}")

    def _setup_templates(self):
        """设置模板目录"""
        current_dir = Path(__file__).parent.parent
        template_dir = os.path.join(current_dir, 'templates')
        self.template_dir = template_dir
        

    def _setup_routes(self):
        """设置路由"""
        # 处理根路径和带斜杠的路径
        @self.app.get(f"/{self.name}")
        async def admin_index(request: Request):
            print("尝试访问admin首页")
            user = await self._get_current_user(request)
            if not user:
                print("用户未登录，重定向到登录页")
                return Response(
                    status_code=307,
                    description="",
                    headers={"Location": f"/{self.name}/login"},
                )
                
            print(f"用户已登录: {user.username}")
            # 打印检查 self.models 的内容
            print("注册的模型:", self.models)
            
            context = {
                "site_title": "Robyn Admin",
                "models": self.models,  # 确保这里传递了 models
                "user": user
            }
            return self.jinja_template.render_template("admin/index.html", **context)
            
        @self.app.get(f"/{self.name}/login")
        async def admin_login(request: Request):
            # 如果用户已登录，直接重定向到首页
            user = await self._get_current_user(request)
            if user:
                return Response(
                    status_code=307,
                    description="",
                    headers={"Location": f"/{self.name}"},
                )
            return self.jinja_template.render_template("admin/login.html", user=None)
            
        @self.app.post(f"/{self.name}/login")
        async def admin_login_post(request: Request):
            data = request.body
            params = parse_qs(data)
            params_dict = {key: value[0] for key, value in params.items()}
            username = params_dict.get("username")
            password = params_dict.get("password")
            user = await AdminUser.authenticate(username, password)
            if user:
                session = {"user_id": user.id}
                
                # 构建安全的 cookie 字符串
                cookie_value = json.dumps(session)
                cookie_attrs = [
                    f"session={cookie_value}",
                    "HttpOnly",          # 防止JavaScript访问
                    "SameSite=Lax",     # 防止CSRF攻
                    # "Secure"          # 仅在生产环境启用HTTPS时取消注释
                    "Path=/",           # cookie的作用路
                ]
                
                response = Response(
                    status_code=303, 
                    description="", 
                    headers={
                        "Location": f"/{self.name}",
                        "Set-Cookie": "; ".join(cookie_attrs)
                    }
                )
                user.last_login = datetime.now()
                await user.save()
                return response
            else:
                print("登录失败")
                return self.jinja_template.render_template(
                    "admin/login.html",
                    error="用户名或密码错误",
                    user=None
                )
                
        @self.app.get(f"/{self.name}/logout")
        async def admin_logout(request: Request):
            # 清除cookie时也需要设置相同的属性
            cookie_attrs = [
                "session=",  # 空值
                "HttpOnly",
                "SameSite=Lax",
                # "Secure"
                "Path=/",
                "Max-Age=0"  # 立即过期
            ]
            
            return Response(
                status_code=303, 
                description="", 
                headers={
                    "Location": f"/{self.name}/login",
                    "Set-Cookie": "; ".join(cookie_attrs)
                }
            )

        @self.app.get(f"/{self.name}/:model_name")
        async def model_list(request: Request):
            """模型列表页"""
            model_name: str = request.path_params.get("model_name")
            user = await self._get_current_user(request)
            if not user:
                return Response(status_code=303, headers={"Location": f"/{self.name}/login"})
            
            model_admin = self.models.get(model_name)
            if not model_admin:
                return Response(status_code=404, description="模型不存在")
            
            # 获取搜索和过滤参数
            search_term = request.query_params.get("search")
            filters = {
                field: request.query_params.get(field)
                for field in model_admin.list_filter
                if request.query_params.get(field)
            }
            
            # 获取数据列表
            queryset = await model_admin.get_queryset(search_term, filters)
            objects = await queryset.limit(model_admin.per_page)
            
            # 获取过滤选项
            filter_choices = {
                field: model_admin.get_filter_choices(field)
                for field in model_admin.list_filter
            }
            
            context = {
                "model_name": model_name,
                "models": self.models,
                "objects": [
                    {
                        'display': model_admin.serialize_object(obj, for_display=True),
                        'data': model_admin.serialize_object(obj, for_display=False)
                    }
                    for obj in objects
                ],
                "fields": model_admin.get_list_fields(),
                "form_fields": model_admin.get_form_fields(),
                "field_labels": model_admin.field_labels,
                "list_display_links": model_admin.get_list_display_links(),
                "list_editable": model_admin.list_editable,
                "list_filter": model_admin.list_filter,
                "filter_choices": filter_choices,
                "filters": filters,
                "search_fields": model_admin.search_fields,
                "search_term": search_term,
                "readonly_fields": model_admin.readonly_fields,
                "user": user,
                "table_mappings": model_admin.options.table_mappings,
                "form_mappings": model_admin.options.form_mappings,
                "filter_mappings": model_admin.options.filter_mappings
            }
            
            return self.jinja_template.render_template("admin/model_list.html", **context)


        @self.app.post(f"/{self.name}/:model_name/add")
        async def model_add_post(request: Request):
            """处理添加记录"""
            model_name: str = request.path_params.get("model_name")
            print(model_name)
            user = await self._get_current_user(request)
            if not user:
                return Response(status_code=303, headers={"Location": f"/{self.name}/login"})
            
            model_admin = self.models.get(model_name)
            if not model_admin:
                return Response(status_code=404, description="模型不存在")
            
            # 解析表单数据
            data = request.body
            params = parse_qs(data)
            form_data = {key: value[0] for key, value in params.items()}
            print('form_data', form_data)   
            try:
                # 创建记录
                await model_admin.model.create(**form_data)
                return Response(
                    status_code=303,
                    headers={"Location": f"/{self.name}/{model_name.lower()}"}
                )
            except Exception as e:
                context = {
                    "models": self.models,
                    "model_name": model_name,
                    "fields": model_admin.get_form_fields(),
                    "user": user,
                    "action": "add",
                    "error": str(e),
                    "form_data": form_data
                }
                return self.jinja_template.render_template("admin/model_form.html", **context)

        @self.app.post(f"/{self.name}/:model_name/:id/edit")
        async def model_edit_post(request: Request):
            """处理编辑记录"""
            model_name: str = request.path_params.get("model_name")
            object_id: str = request.path_params.get("id")
            
            user = await self._get_current_user(request)
            if not user:
                return Response(
                    status_code=303, 
                    headers={"Location": f"/{self.name}/login"}
                )
            
            model_admin = self.models.get(model_name)
            if not model_admin:
                return Response(
                    status_code=404, 
                    description="模型不存在",
                    headers={"Location": f"/{self.name}/{model_name}"},
                )
            
            try:
                # 获取要编辑的对象
                obj = await model_admin.get_object(object_id)
                if not obj:
                    return Response(status_code=404, description="记录不存在", headers={"Location": f"/{self.name}/{model_name}"},)
                
                # 解析表单数据
                data = request.body
                params = parse_qs(data)
                form_data = {key: value[0] for key, value in params.items()}
                
                # 验证字段
                valid_fields = model_admin.get_form_fields()
                filtered_data = {
                    k: v for k, v in form_data.items() 
                    if k in valid_fields and k not in model_admin.readonly_fields
                }
                
                # 处理字段类型
                for field_name, value in filtered_data.items():
                    field = obj._meta.fields_map.get(field_name)
                    if isinstance(field, fields.BooleanField):
                        # 处理布尔值
                        filtered_data[field_name] = bool(int(value))
                    elif isinstance(field, fields.IntField):
                        # 处理整数
                        filtered_data[field_name] = int(value)
                    elif isinstance(field, fields.FloatField):
                        # 处理浮点数
                        filtered_data[field_name] = float(value)
                    elif isinstance(field, fields.DecimalField):
                        # 处理decimal
                        from decimal import Decimal
                        filtered_data[field_name] = Decimal(value)
                
                # 更新对象
                for field, value in filtered_data.items():
                    setattr(obj, field, value)
                await obj.save()
                
                return Response(
                    headers={"Location": f"/{self.name}/{model_name}"},
                    status_code=200,
                    description="更新成功"
                )
            except Exception as e:
                import traceback
                traceback.print_exc()
                return Response(
                    status_code=400,
                    description=f"更新失败: {str(e)}",
                    headers={"Location": f"/{self.name}/{model_name}"},
                )

        @self.app.post(f"/{self.name}/:model_name/:id/delete")
        async def model_delete(request: Request):
            """处理删除记录"""
            model_name: str = request.path_params.get("model_name")
            object_id: str = request.path_params.get("id")
            
            user = await self._get_current_user(request)
            if not user:
                return Response(status_code=303, headers={"Location": f"/{self.name}/login"})
            
            model_admin = self.models.get(model_name)
            if not model_admin:
                return Response(status_code=404, description="模型不存在", headers={"Location": f"/{self.name}/{model_name}"})
            
            try:
                # 获取要删除的对象
                obj = await model_admin.get_object(object_id)
                if not obj:
                    return Response(status_code=404, description="记录不存在",headers={"Location": f"/{self.name}/{model_name}"})
                
                # 删除对
                await obj.delete()
                
                return Response(
                    status_code=200,
                    description="除成功",
                    headers={"Location": f"/{self.name}/{model_name}"}
                )
            except Exception as e:
                print(f"删除失败: {str(e)}")
                return Response(
                    status_code=400,
                    description=f"删除失败: {str(e)}",
                    headers={"Location": f"/{self.name}/{model_name}"}
                )

    async def _get_current_user(self, request: Request) -> Optional[AdminUser]:
        """获取当前登录用户"""
        try:
            # 从cookie中获取session
            session_data = request.headers.get('Cookie')
            print("获取到的session", session_data)
            # session={"user_id": 1};xxxx={"xx":"xx"}
            if not session_data:
                return None
            session_dict = {}
            for item in session_data.split(";"):
                key, value = item.split("=")
                session_dict[key.strip()] = value.strip()
            session = session_dict.get("session")
            user_id = json.loads(session).get("user_id")
            print("获取到的user_id", user_id)
            if not user_id:
                return None
            # 通过user_id获取用户
            user = await AdminUser.get(id=user_id)
            print("获取到的user", user)
            return user
        except Exception as e:
            print(f"获取用户失败: {str(e)}")
            return None

    def register_model(self, model: Type[Model], admin_class: Optional[Type[ModelAdmin]] = None):
        """注册模型到admin站点"""
        if admin_class is None:
            admin_class = ModelAdmin
        self.models[model.__name__] = admin_class(model)
        print(f"已注册模型 {model.__name__}")  # 添加调试信息