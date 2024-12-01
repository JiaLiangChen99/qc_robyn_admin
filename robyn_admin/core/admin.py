from typing import Type, Optional, List, Dict, Union, Callable, Any
from urllib.parse import unquote
from tortoise.models import Model
from tortoise import fields
from robyn import Robyn, Request, Response, jsonify
from robyn.templating import JinjaTemplate
from pathlib import Path
import os
import json
from datetime import datetime
from types import ModuleType
from urllib.parse import parse_qs
import traceback

from ..models import AdminUser
from .fields import (
    DisplayType, TableField, FormField, SearchField, 
    FilterField, Action, RowAction
)
from .filters import (
    FilterField, SelectFilter, DateRangeFilter, 
    NumberRangeFilter, BooleanFilter, FilterType
)

class ModelAdmin:
    """模型管理类
    
    配置模型在后台的展示和行为：
    - table_fields: 表格中要显示的字段
    - form_fields: 表单中可编辑的字段
    - search_fields: 可搜索的字段
    - filter_fields: 可筛选的字段（下拉框）
    - action_buttons: 行操作按钮
    - batch_actions: 批量操作按钮
    - page_actions: 页面操作按钮
    
    Example:
        class UserAdmin(ModelAdmin):
            # 表格显示配置
            table_fields = [
                TableField("id", label="ID"),
                TableField("username", label="用户名", sortable=True),
                TableField("email", label="邮箱"),
                TableField("status", label="状态", type=DisplayType.STATUS)
            ]
            
            # 表单字段配置
            form_fields = [
                FormField("username", label="用户名", required=True),
                FormField("email", label="邮箱", type=DisplayType.EMAIL),
                FormField("password", label="密码", type=DisplayType.PASSWORD)
            ]
            
            # 搜索配置
            search_fields = [
                SearchField("username", placeholder="输入用户名搜索"),
                SearchField("email", placeholder="输入邮箱搜索")
            ]
            
            # 过滤器配置
            filter_fields = [
                FilterField("status", 
                    choices={
                        1: "正常",
                        0: "禁用"
                    }
                ),
                FilterField("role", 
                    choices={
                        "admin": "管理员",
                        "user": "普通用户"
                    }
                )
            ]
            
            # 行操作按钮
            row_actions = [
                Action("edit", "编辑", "warning"),
                Action("delete", "删除", "danger", confirm="确定要删除吗？")
            ]
            
            # 批量操作按钮
            batch_actions = [
                Action("batch_delete", "批量删除", "danger"),
                Action("batch_enable", "批量启用", "success")
            ]
            
            # 页面操作按钮
            page_actions = [
                Action("add", "添加用户", "primary")
            ]
            
            # 分页配置
            per_page = 20
            
            # 默认排序
            default_ordering = ["-created_at"]
    """
    
    # 表格相关配置
    table_fields: List[TableField] = []
    enable_edit: bool = True  # 新增：是否启用编辑功能
    per_page: int = 10
    default_ordering: List[str] = []
    
    # 表单相关配置
    form_fields: List[FormField] = []
    add_form_fields: List[FormField] = []
    add_form_title: Optional[str] = None  # 添加表题
    edit_form_title: Optional[str] = None  # 编辑表单标题
    
    # 搜索和过滤配置
    search_fields: List[SearchField] = []
    filter_fields: List[FilterField] = []
    
    def __init__(self, model: Type[Model]):
        self.model = model
        self._process_fields()
        
    def _process_fields(self):
        """处理字段配置，生成便捷属性"""
        # 如果没有定义table_fields，自动从模型生成
        if not self.table_fields:
            self.table_fields = [
                TableField(name=field_name)
                for field_name in self.model._meta.fields_map.keys()
            ]
            
        # 处理表格字段的显示配置
        for field in self.table_fields:
            model_field = self.model._meta.fields_map.get(field.name)
            
            # 如果是主键字段
            if model_field and model_field.pk:
                field.readonly = True
                field.editable = False
                
            # 如果是时间字段
            elif isinstance(model_field, fields.DatetimeField):
                field.readonly = True
                field.sortable = True
                if not field.display_type:
                    field.display_type = DisplayType.DATETIME
                    
            # 默所字段都不可编辑，除非明确指定
            if not hasattr(field, 'editable') or field.editable is None:
                field.editable = False
        
        # 生成表格字段映射
        self.table_field_map = {field.name: field for field in self.table_fields}
            
        # 如果没有定义form_fields，从table_fields生成
        if not self.form_fields:
            self.form_fields = [
                FormField(
                    name=field.name,
                    label=field.label,
                    field_type=field.display_type,
                    readonly=field.readonly
                )
                for field in self.table_fields
                if not field.readonly
            ]
        
        # 生成便捷属性
        self.list_display = [
            field.name for field in self.table_fields 
            if field.visible
        ]
        
        self.list_display_links = [
            field.name for field in self.table_fields 
            if field.visible and field.is_link
        ]
        
        # 如果没有定义 search_fields，从 table_fields 生成
        if not self.search_fields:
            self.search_fields = [
                SearchField(
                    name=field.name,
                    label=field.label,
                    placeholder=f"输入{field.label}搜索"
                )
                for field in self.table_fields 
                if field.searchable
            ]
        
        self.list_filter = [
            field.name for field in self.table_fields 
            if field.filterable
        ]
        
        self.list_editable = [
            field.name for field in self.table_fields 
            if field.editable and not field.readonly
        ]
        
        self.readonly_fields = [
            field.name for field in self.table_fields 
            if field.readonly
        ]
        
        # 排序字段，带-表示降序
        self.ordering = [
            f"-{field.name}" if not field.sortable else field.name
            for field in self.table_fields 
            if field.sortable
        ]
        
        # 如果没有定义add_form_fields，使用form_fields
        if not self.add_form_fields:
            self.add_form_fields = self.form_fields
        
    def get_field(self, field_name: str) -> Optional[TableField]:
        """获取字段配置"""
        return self.table_field_map.get(field_name)
        
    async def get_queryset(self, request, params: dict):
        """获取查询集"""
        queryset = self.model.all()
        
        # 处理过滤条件
        if params.get('filters'):
            for field, value in params['filters'].items():
                if value:
                    queryset = queryset.filter(**{field: value})
        
        return queryset
        
    def get_field_label(self, field_name: str) -> str:
        """获取字段显示名称"""
        for field in self.table_fields:
            if field.name == field_name and field.label:
                return field.label
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
        for field in self.table_fields:
            if field.name == field_name:
                return field.editable and not field.readonly
        return False

    def get_filter_choices(self, field_name: str) -> List[tuple]:
        """获取过滤字段的选项"""
        # 从 filter_fields 中获取选项
        for field in self.filter_fields:
            if field.name == field_name:
                if field.choices:
                    return [(str(k), v) for k, v in field.choices.items()]
                break
            
        # 处理布尔字段
        model_field = self.model._meta.fields_map.get(field_name)
        if isinstance(model_field, fields.BooleanField):
            return [('True', '是'), ('False', '否')]
            
        # 如果是外键字段，返回空列表（后续可以异步获取选项）
        if field_name.endswith('_id') and isinstance(model_field, fields.IntField):
            return []
            
        return []
        
    async def get_object(self, pk):
        """获取单个对象"""
        return await self.model.get(id=pk)
        
    def get_form_fields(self) -> List[str]:
        """获取表单字段"""
        return [
            field.name for field in self.form_fields
            if not field.readonly and field.name != 'id'
        ]

    def get_list_fields(self) -> List[str]:
        """获取显示字段"""
        return self.list_display or [field.name for field in self.table_fields]

    def format_field_value(self, obj: Model, field_name: str) -> str:
        """格式化字段值"""
        field = self.get_field(field_name)
        if not field:
            return str(getattr(obj, field_name, ''))
        return field.format_value(getattr(obj, field_name, ''))

    def serialize_object(self, obj: Model, for_display: bool = True) -> Dict[str, Any]:
        """将模型对象序列化为字典"""
        result = {}
        
        # 确保包含 id 字段
        result['id'] = str(getattr(obj, 'id', ''))
        
        print(f"Serializing object {obj.id} for {'display' if for_display else 'data'}")
        
        for field in self.table_fields:
            try:
                value = getattr(obj, field.name, None)
                print(f"  Field {field.name}: {value} (type: {type(value)})")
                
                if for_display:
                    # 如果有 formatter，使用 formatter 处理
                    if field.formatter:
                        try:
                            result[field.name] = field.formatter(value) if value is not None else ''
                            print(f"    Formatted value: {result[field.name]}")
                        except Exception as e:
                            print(f"    Error formatting field {field.name}: {str(e)}")
                            result[field.name] = str(value) if value is not None else ''
                    else:
                        # 根据字段类型处理
                        if value is None:
                            result[field.name] = ''
                        elif isinstance(value, datetime):
                            if field.display_type == DisplayType.DATE:
                                result[field.name] = value.strftime("%Y-%m-%d")
                            else:
                                result[field.name] = value.strftime("%Y-%m-%d %H:%M:%S")
                        elif isinstance(value, bool):
                            result[field.name] = "是" if value else "否"
                        else:
                            result[field.name] = str(value)
                else:
                    # 原始数据
                    if value is None:
                        result[field.name] = ''
                    elif isinstance(value, datetime):
                        result[field.name] = value.strftime("%Y-%m-%d %H:%M:%S")
                    elif isinstance(value, bool):
                        result[field.name] = 1 if value else 0
                    else:
                        result[field.name] = str(value)
                    
                print(f"    Final value: {result[field.name]}")
            except Exception as e:
                print(f"  Error processing field {field.name}: {str(e)}")
                result[field.name] = ''
        
        return result

    def serialize_field(self, field: TableField) -> Dict[str, Any]:
        """序列化字段配置信息"""
        return {
            'name': field.name,
            'label': field.label,
            'display_type': field.display_type.value if field.display_type else 'text',
            'sortable': field.sortable,
            'readonly': field.readonly,
            'editable': field.editable,
            'filterable': field.filterable,
            'width': field.width,
            'is_link': field.is_link,
            'hidden': field.hidden,
            'formatter': True if field.formatter else False
        }

    def get_search_fields(self) -> List[str]:
        """获取可搜索字段列表"""
        return [field.name for field in self.search_fields]

    def get_ordering_fields(self) -> List[str]:
        """获取可排序字段列表"""
        return [field.name for field in self.table_fields if field.sortable]

    def get_filter_fields(self) -> List[FilterField]:
        """获取过滤字段配置"""
        return self.filter_fields

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
        :param db_url: 数据库连接URL,果为None则尝试复用已有配置
        :param modules: 模型模块配置,如果为None则尝试复用已有配置
        :param generate_schemas: 是否自动生成数据库表构
        """
        self.app = app
        self.name = name
        self.models: Dict[str, ModelAdmin] = {}
        self._setup_templates()
        
        # 初始化数库
        self.db_url = db_url
        self.modules = modules
        self.generate_schemas = generate_schemas
        self._init_admin_db()
        
        # 设置路由要在数据初始化之后
        self._setup_routes()
        self.jinja_template = JinjaTemplate(self.template_dir)

    def _init_admin_db(self):
        """初始化admin数据库"""
        from tortoise import Tortoise
        
        @self.app.startup_handler
        async def init_admin():
            # 如果没有提供配置,试获取已有配置
            if not self.db_url:
                if not Tortoise._inited:
                    raise Exception("数据库未初始化,请先配置数据库或提供db_url参数")
                # 复用现有配置
                current_config = Tortoise.get_connection("default").config
                self.db_url = current_config.get("credentials", {}).get("dsn")
                
            if not self.modules:
                if not Tortoise._inited:
                    raise Exception("数据库未初始化,请先配置数据库或提供modules参数")
                # 用现有modules配
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
                
            # 创建默认超级用
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
                print(f"创建管理账号失败: {str(e)}")

    def _setup_templates(self):
        """设置模板录"""
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
            # 如果户已登录，直接重定向到首页
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
                    # "Secure"          # 仅在生产环境启用HTTPS时消注释
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
                    error="户或密码错误",
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
        
        @self.app.get(f"/{self.name}/:model_name/search")
        async def model_search(request: Request):
            """模型页面中，搜索功能用相关接口，进行糊匹配查询结果"""
            model_name: str = request.path_params.get("model_name")
            user = await self._get_current_user(request)
            if not user:
                return Response(
                    status_code=401, 
                    description="未登录",
                    headers={"Content-Type": "application/json"}
                )
            
            model_admin = self.models.get(model_name)
            if not model_admin:
                return Response(
                    status_code=404, 
                    description="模型不存在",
                    headers={"Content-Type": "application/json"}
                )
            
            # 获取索参数， 同时还要进行url解码
            search_values = {
                field.name: unquote(request.query_params.get(f"search_{field.name}"))
                for field in model_admin.search_fields
                if request.query_params.get(f"search_{field.name}")
            }
            print("搜索参数", search_values)
            # 执行搜索查询
            queryset = await model_admin.get_queryset(None, search_values)
            objects = await queryset.limit(model_admin.per_page)
            
            # 序列化结果
            result = {
                "data": [
                    {
                        'display': model_admin.serialize_object(obj, for_display=True),
                        'data': model_admin.serialize_object(obj, for_display=False)
                    }
                    for obj in objects
                ]
            }
            print("查询功能结果", result)
            return jsonify(result)


        @self.app.get(f"/{self.name}/:model_name")
        async def model_list(request: Request):
            """模型列表页"""
            model_name: str = request.path_params.get("model_name")
            user = await self._get_current_user(request)
            if not user:
                return Response(status_code=303, description="", headers={"Location": f"/{self.name}/login"})
            
            model_admin = self.models.get(model_name)
            if not model_admin:
                return Response(status_code=404, description="模型不存在", headers={"Location": f"/{self.name}/login"})
            
            # 获取数据列表包括总数）
            base_queryset = await model_admin.get_queryset(None, {})
            total = await base_queryset.count()  # 获取总记录数
            objects = await base_queryset.limit(model_admin.per_page)  # 获取第一页数据
            
            # 准备表格数据
            table_data = []
            for obj in objects:
                try:
                    display_data = model_admin.serialize_object(obj, for_display=True)
                    raw_data = model_admin.serialize_object(obj, for_display=False)
                    table_data.append({
                        'display': display_data,
                        'data': raw_data
                    })
                except Exception as e:
                    print(f"Error serializing object {obj.id}: {str(e)}")
                    continue
            
            # 准备上下文数据
            context = {
                "model_name": model_name,
                "models": self.models,
                "user": user,
                "frontend_config": {
                    "tableData": table_data,
                    "total": total,  # 添加总记录数
                    "tableFields": [model_admin.serialize_field(field) for field in model_admin.table_fields],
                    "modelName": model_name,
                    "pageSize": model_admin.per_page,
                    "formFields": [field.to_dict() for field in model_admin.form_fields],
                    "addFormFields": [field.to_dict() for field in model_admin.add_form_fields],
                    "addFormTitle": model_admin.add_form_title or f"添加{model_name}",
                    "editFormTitle": model_admin.edit_form_title or f"编辑{model_name}",
                    "searchFields": [field.to_dict() for field in model_admin.search_fields],
                    "filterFields": [field.to_dict() for field in model_admin.filter_fields],
                    "enableEdit": model_admin.enable_edit
                }
            }
            
            # 调试日志
            print(f"Model: {model_name}")
            print(f"Total records: {total}")
            print(f"First page records: {len(table_data)}")
            print(f"First row sample: {table_data[0] if table_data else None}")
            
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
            
            # 处理表单数据
            processed_data = {}
            for field in model_admin.add_form_fields:
                if field.name in form_data:
                    processed_data[field.name] = field.process_value(form_data[field.name])
            print("创建的表单数据", processed_data)
            try:
                # 创建记录
                await model_admin.model.create(**processed_data)
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
                return Response(status_code=303, headers={"Location": f"/{self.name}/login"})
            
            model_admin = self.models.get(model_name)
            if not model_admin:
                return Response(status_code=404, description="模型不存在")
            
            if not model_admin.enable_edit:
                return Response(status_code=403, description="该模型不允许编辑")
            
            try:
                # 获取要编辑的对象
                obj = await model_admin.get_object(object_id)
                if not obj:
                    return Response(status_code=404, description="记录不存在")
                
                # 解析表单数据
                data = request.body
                params = parse_qs(data)
                form_data = {key: value[0] for key, value in params.items()}
                
                # 处理表数
                processed_data = {}
                for field in model_admin.form_fields:
                    if field.name in form_data:
                        processed_data[field.name] = field.process_value(form_data[field.name])
                
                # 更新对象
                for field, value in processed_data.items():
                    setattr(obj, field, value)
                await obj.save()
                
                return Response(
                    status_code=200,
                    description="更新成功",
                    headers={"Content-Type": "application/json"}
                )
                
            except Exception as e:
                print(f"编辑失败: {str(e)}")
                return Response(
                    status_code=400,
                    description=f"编辑失败: {str(e)}",
                    headers={"Content-Type": "application/json"}
                )

        @self.app.post(f"/{self.name}/:model_name/:id/delete")
        async def model_delete(request: Request):
            """处理删除记录"""
            model_name: str = request.path_params.get("model_name")
            object_id: str = request.path_params.get("id")
            
            user = await self._get_current_user(request)
            if not user:
                return Response(status_code=401, description="未登录", headers={"Location": f"/{self.name}/login"})
            
            model_admin = self.models.get(model_name)
            if not model_admin:
                return Response(status_code=404, description="模型不存在", headers={"Location": f"/{self.name}/login"})
            
            try:
                # 获取要删除的对象
                obj = await model_admin.get_object(object_id)
                if not obj:
                    return Response(status_code=404, description="记录不存在", headers={"Location": f"/{self.name}/{model_name}"})
                
                # 删除对象
                await obj.delete()
                
                return Response(status_code=200, description="删除成功", headers={"Location": f"/{self.name}/{model_name}"})
            except Exception as e:
                print(f"删除失败: {str(e)}")
                return Response(status_code=500, description=f"删除失败: {str(e)}", headers={"Location": f"/{self.name}/{model_name}"}  )
        
        @self.app.get(f"/{self.name}/:model_name/data")
        async def model_data(request: Request):
            """获取模型数据，支持分页、搜索和排序"""
            try:
                # 从路径参数获取模型名称
                print("body", request.body)
                print("query_params", request.query_params) 
                print("form", request.form_data)
                model_name = request.path_params.get("model_name")
                model_admin = self.models.get(model_name)
                if not model_admin:
                    return Response(status_code=404, description="模型不存在")

                # 从查询参数获取分页和搜索参数
                query_params = request.query_params
                limit = int(query_params.get('limit', str(model_admin.per_page)))
                offset = int(query_params.get('offset', '0'))
                search = query_params.get('search', '')
                sort = query_params.get('sort', '')
                order = query_params.get('order', 'asc')
                
                print(f"Query params: {query_params}")
                
                # 构建基础查询
                base_queryset = await model_admin.get_queryset(None, {})
                
                # 处理过滤条件
                for filter_field in model_admin.filter_fields:
                    filter_value = query_params.get(filter_field.name)
                    if filter_value:
                        if filter_field.filter_type == FilterType.INPUT:
                            # 输入框过滤，使用 icontains
                            base_queryset = base_queryset.filter(
                                **{f"{filter_field.name}__{filter_field.operator}": filter_value}
                            )
                        elif filter_field.filter_type == FilterType.SELECT:
                            # 下拉框过滤，使用精确匹配
                            # 处理布尔值
                            if filter_value.lower() == 'true':
                                filter_value = True
                            elif filter_value.lower() == 'false':
                                filter_value = False
                            base_queryset = base_queryset.filter(**{filter_field.name: filter_value})
                        elif filter_field.filter_type == FilterType.DATE_RANGE:
                            # 日期范围过滤
                            start_date = query_params.get(f"{filter_field.name}_start")
                            end_date = query_params.get(f"{filter_field.name}_end")
                            if start_date:
                                base_queryset = base_queryset.filter(
                                    **{f"{filter_field.name}__gte": start_date}
                                )
                            if end_date:
                                base_queryset = base_queryset.filter(
                                    **{f"{filter_field.name}__lte": end_date}
                                )
                        elif filter_field.filter_type == FilterType.NUMBER_RANGE:
                            # 数字范围过滤
                            min_value = query_params.get(f"{filter_field.name}_min")
                            max_value = query_params.get(f"{filter_field.name}_max")
                            if min_value:
                                base_queryset = base_queryset.filter(
                                    **{f"{filter_field.name}__gte": float(min_value)}
                                )
                            if max_value:
                                base_queryset = base_queryset.filter(
                                    **{f"{filter_field.name}__lte": float(max_value)}
                                )
                
                # 处理搜索
                if search and model_admin.search_fields:
                    from tortoise.expressions import Q
                    import operator
                    from functools import reduce
                    
                    search_conditions = []
                    for field in model_admin.search_fields:
                        search_conditions.append(Q(**{f"{field.name}__icontains": search}))
                    if search_conditions:
                        base_queryset = base_queryset.filter(reduce(operator.or_, search_conditions))
                
                # 处理排序
                if sort:
                    order_by = f"{'-' if order == 'desc' else ''}{sort}"
                    base_queryset = base_queryset.order_by(order_by)
                elif model_admin.default_ordering:
                    base_queryset = base_queryset.order_by(*model_admin.default_ordering)
                
                # 获取总记录数
                total = await base_queryset.count()
                print(f"Total records: {total}")
                
                # 获取分页数据
                objects = await base_queryset.offset(offset).limit(limit)
                print(f"Page records: {len(objects)}")
                
                # 序列化数据
                data = []
                for obj in objects:
                    try:
                        display_data = model_admin.serialize_object(obj, for_display=True)
                        raw_data = model_admin.serialize_object(obj, for_display=False)
                        data.append({
                            'display': display_data,
                            'data': raw_data
                        })
                    except Exception as e:
                        print(f"Error serializing object {obj.id}: {str(e)}")
                        continue
                
                # 返回数据
                response_data = {
                    "total": total,
                    "data": data
                }
                print(f"Response: total={total}, page_size={len(data)}")
                return jsonify(response_data)
                
            except Exception as e:
                print(f"Error in model_data: {str(e)}")
                traceback.print_exc()
                return Response(
                    status_code=500,
                    description=f"获取数据失败: {str(e)}",
                    headers={"Content-Type": "application/json"}
                )
        
        @self.app.post(f"/{self.name}/:model_name/batch_delete")
        async def model_batch_delete(request: Request):
            """批量删除记录"""
            try:
                model_name: str = request.path_params.get("model_name")
                user = await self._get_current_user(request)
                if not user:
                    return Response(status_code=401, description="未登录", headers={"Location": f"/{self.name}/login"})
                
                model_admin = self.models.get(model_name)
                if not model_admin:
                    return Response(status_code=404, description="模型不存在", headers={"Location": f"/{self.name}/login"})
                
                # 解析请求数据
                data = request.body
                params = parse_qs(data)
                ids = params.get('ids[]', [])  # 获取要删除的ID列表
                
                if not ids:
                    return Response(
                        status_code=400,
                        description="未选择要删除的记录",
                        headers={"Content-Type": "application/json"}
                    )
                
                # 批量删除
                deleted_count = 0
                for id in ids:
                    try:
                        obj = await model_admin.get_object(id)
                        if obj:
                            await obj.delete()
                            deleted_count += 1
                    except Exception as e:
                        print(f"删除记录 {id} 失败: {str(e)}")
                
                print(f"除成功 {deleted_count} 条记录")
                # 修改返回格式
                return jsonify({
                    "code": 200,
                    "message": f"成功删除 {deleted_count} 条记录",
                    "success": True
                })
                
            except Exception as e:
                print(f"批量删除失败: {str(e)}")
                # 修改错误返回格式
                return jsonify({
                    "code": 500,
                    "message": f"批量删除失败: {str(e)}",
                    "success": False
                })
        
        @self.app.post(f"/{self.name}/upload")
        async def file_upload(request: Request):
            """处理文件上传"""
            try:
                # 验证用户登录
                user = await self._get_current_user(request)
                if not user:
                    return jsonify({
                        "code": 401,
                        "message": "未登录",
                        "success": False
                    })

                # 获取上传的文件
                files = request.files
                if not files:
                    return jsonify({
                        "code": 400,
                        "message": "没有上传文件",
                        "success": False
                    })
                # 获取上传路径参数
                upload_path = request.form_data.get('upload_path', 'static/uploads')
                # 处理上传的文件
                uploaded_files = []
                for file_name, file_bytes in files.items():
                    # 验证文件类型
                    if not file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        return jsonify({
                            "code": 400,
                            "message": "不支持的文件类型，仅支持jpg、jpeg、png、gif格式",
                            "success": False
                        })

                    # 生成安全的文件名
                    import uuid
                    safe_filename = f"{uuid.uuid4().hex}{os.path.splitext(file_name)[1]}"
                    
                    # 确保上传目录存在
                    os.makedirs(upload_path, exist_ok=True)
                    
                    # 保存文件
                    file_path = os.path.join(upload_path, safe_filename)
                    with open(file_path, 'wb') as f:
                        f.write(file_bytes)
                    
                    # 生成访问URL（使用相对路径）
                    file_url = f"/{file_path.replace(os.sep, '/')}"
                    uploaded_files.append({
                        "original_name": file_name,
                        "saved_name": safe_filename,
                        "url": file_url
                    })
                
                # 返回成功响应
                return jsonify({
                    "code": 200,
                    "message": "上传成功",
                    "success": True,
                    "data": uploaded_files[0] if uploaded_files else None  # 返回第一个文件的信息
                })
                
            except Exception as e:
                print(f"文件上传失败: {str(e)}")
                traceback.print_exc()
                return jsonify({
                    "code": 500,
                    "message": f"文件上传失败: {str(e)}",
                    "success": False
                })
        
    def register_model(self, model: Type[Model], admin_class: Optional[Type[ModelAdmin]] = None):
        """注册模型到admin站点"""
        if admin_class is None:
            admin_class = ModelAdmin
        self.models[model.__name__] = admin_class(model)
        print(f"已注册模型 {model.__name__}")  # 添加调试信息
        
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
        