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
from dataclasses import dataclass
import asyncio

from ..models import AdminUser
from .fields import (
    DisplayType, TableField, FormField, SearchField, 
    FilterField, Action, RowAction
)
from .filters import (
    FilterField, SelectFilter, DateRangeFilter, 
    NumberRangeFilter, BooleanFilter, FilterType
)
from ..i18n.translations import get_text

@dataclass
class MenuItem:
    """菜单项配置"""
    name: str                    # 菜单名称
    icon: str = ""              # 图标类名 (Bootstrap Icons)
    parent: Optional[str] = None # 父菜单名称
    order: int = 0              # 排序值
    


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
    
    # 模型显示名称
    verbose_name: str = ""
    
    # 菜单配置
    menu_group: str = ""     # 所属菜单组
    menu_icon: str = ""      # 菜单图标
    menu_order: int = 0      # 菜单排序
    
    
    def __init__(self, model: Type[Model]):
        self.model = model
        # 如果没有设置 verbose_name，使用模型名称
        if not self.verbose_name:
            self.verbose_name = model.__name__
        self._process_fields()
        
        # 如果没有设置菜单组使用默认分组
        if not self.menu_group:
            self.menu_group = "系管理"
        
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
                
            # 果是时间字段
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
        
        # 处理搜索
        search = params.get('search', '')
        if search and self.search_fields:
            from tortoise.expressions import Q
            import operator
            from functools import reduce
            
            search_conditions = []
            for field in self.search_fields:
                try:
                    query_dict = await field.build_search_query(search)
                    if query_dict:
                        if len(query_dict) == 1 and "id" in query_dict and query_dict["id"] is None:
                            continue  # 跳过没有匹配结果的关联搜索
                        search_conditions.append(Q(**query_dict))
                except Exception as e:
                    print(f"Error building search query for {field.name}: {str(e)}")
                    continue
                    
            if search_conditions:
                queryset = queryset.filter(reduce(operator.or_, search_conditions))
        
        # 处理过滤器
        for filter_field in self.filter_fields:
            filter_value = params.get(filter_field.name)
            if filter_value:
                try:
                    query_dict = await filter_field.build_filter_query(filter_value)
                    if query_dict:
                        if len(query_dict) == 1 and "id" in query_dict and query_dict["id"] is None:
                            continue  # 跳过没有匹配结果的关联过滤
                        queryset = queryset.filter(**query_dict)
                except Exception as e:
                    print(f"Error building filter query for {filter_field.name}: {str(e)}")
                    continue
        
        # 处理排序
        sort = params.get('sort', '')
        order = params.get('order', 'asc')
        if sort:
            # 处理关联字段的排序
            for field in self.table_fields:
                if field.name == sort and field.related_model and field.related_key:
                    # 获取真实的排序字段
                    field_parts = field.name.split('_')
                    if len(field_parts) > 1:
                        related_field = field_parts[-1]
                        # 使用关联查询进行排序
                        queryset = queryset.annotate(
                            sort_field=getattr(field.related_model, related_field)
                        ).order_by(f"{'-' if order == 'desc' else ''}sort_field")
                        break
            else:
                # 普通字段排序
                order_by = f"{'-' if order == 'desc' else ''}{sort}"
                queryset = queryset.order_by(order_by)
        elif self.default_ordering:
            queryset = queryset.order_by(*self.default_ordering)
        
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
        """判断字段是否可在列页编辑"""
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

    async def serialize_object(self, obj: Model, for_display: bool = True) -> dict:
        """序列化对象"""
        result = {}
        result['id'] = str(getattr(obj, 'id', ''))
        
        for field in self.table_fields:
            try:
                if field.related_model and field.related_key:
                    # 获取外键值
                    fk_value = getattr(obj, field.related_key)
                    if fk_value:
                        try:
                            # 查询关联对象
                            related_obj = await field.related_model.get(id=fk_value)
                            if related_obj:
                                # 使用关联模型名称来分割字段名
                                model_name = field.related_model.__name__
                                if field.name.startswith(model_name + '_'):
                                    # 移除模型名称前缀，获取实际字段名
                                    related_field = field.name[len(model_name + '_'):]
                                else:
                                    # 如果字段名不符合预期格式，使用默认字段
                                    related_field = 'id'
                                print(f"Getting related field: {related_field} from {model_name}")
                                # 获取关联字段的值
                                related_value = getattr(related_obj, related_field)
                                result[field.name] = str(related_value) if related_value is not None else ''
                                continue
                        except Exception as e:
                            print(f"Error getting related object: {str(e)}")
                            print(f"Field name: {field.name}, Related model: {field.related_model.__name__}, Related key: {field.related_key}")
                
                    # 如果获取关联对象失败或没有外键值，设置为空字符串
                    result[field.name] = ''
                else:
                    # 处理普通字段
                    value = getattr(obj, field.name, None)
                    if for_display:
                        if field.formatter and value is not None:
                            try:
                                if asyncio.iscoroutinefunction(field.formatter):
                                    result[field.name] = await field.formatter(value)
                                else:
                                    result[field.name] = field.formatter(value)
                            except Exception as e:
                                print(f"Error formatting field {field.name}: {str(e)}")
                                result[field.name] = str(value) if value is not None else ''
                        else:
                            result[field.name] = str(value) if value is not None else ''
                    else:
                        result[field.name] = str(value) if value is not None else ''
                        
            except Exception as e:
                print(f"Error processing field {field.name}: {str(e)}")
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

    def get_frontend_config(self) -> dict:
        """获取前端配置"""
        return {
            "tableFields": [field.to_dict() for field in self.table_fields],
            "modelName": self.model.__name__,
            "pageSize": self.per_page,
            "formFields": [field.to_dict() for field in self.form_fields],
            "addFormFields": [field.to_dict() for field in self.add_form_fields],
            "addFormTitle": self.add_form_title or f"添加{self.verbose_name}",
            "editFormTitle": self.edit_form_title or f"编辑{self.verbose_name}",
            "searchFields": [field.to_dict() for field in self.search_fields],
            "filterFields": [field.to_dict() for field in self.filter_fields],
            "enableEdit": self.enable_edit,
            "verbose_name": self.verbose_name
        }

class AdminSite:
    """Admin站点主类"""
    def __init__(
        self, 
        app: Robyn, 
        name: str = 'admin',
        db_url: Optional[str] = None,
        modules: Optional[Dict[str, List[Union[str, ModuleType]]]] = None,
        generate_schemas: bool = True,
        default_language: str = 'en_US'
    ):
        """
        初始化Admin站点
        
        :param app: Robyn应用实例
        :param name: Admin路由前缀
        :param db_url: 数据库连接URL,果None则尝试复用已有配置
        :param modules: 模型模块配置,如果为None则尝试复用已有配置
        :param generate_schemas: 是否自动生成数据库表构
        """
        self.app = app
        self.name = name
        self.models: Dict[str, ModelAdmin] = {}
        self.default_language = default_language
        self.menus: Dict[str, MenuItem] = {}  # 添加菜单配置字典
        
        # 设置模板
        self._setup_templates()
        
        # 初始化数据库
        self.db_url = db_url
        self.modules = modules
        self.generate_schemas = generate_schemas
        self._init_admin_db()
        
        # 设置路由
        self._setup_routes()

    def _setup_templates(self):
        """设置模板目录"""
        current_dir = Path(__file__).parent.parent
        template_dir = os.path.join(current_dir, 'templates')
        self.template_dir = template_dir
        
        # 创建 Jinja2 环境并添加全局函数
        self.jinja_template = JinjaTemplate(template_dir)
        self.jinja_template.env.globals.update({
            'get_text': get_text
        })

    def _init_admin_db(self):
        """初始化admin数据库"""
        from tortoise import Tortoise
        
        @self.app.startup_handler
        async def init_admin():
            # 如果没有提供配置,试获取已有配置
            if not self.db_url:
                if not Tortoise._inited:
                    raise Exception("数据库未始化,请配置数据库或提供db_url参数")
                # 复用现有配置
                current_config = Tortoise.get_connection("default").config
                self.db_url = current_config.get("credentials", {}).get("dsn")
                
            if not self.modules:
                if not Tortoise._inited:
                    raise Exception("数据库未初始化,请先配置数据库或提供modules参数")
                # 用现有modules配
                self.modules = dict(Tortoise.apps)
            print("第一次", self.modules)
            # 确保admin模型和用户模型都被加载
            if "models" in self.modules:
                if isinstance(self.modules["models"], list):
                    if "robyn_admin.models" not in self.modules["models"]:
                        self.modules["models"].append("robyn_admin.models")
                else:
                    self.modules["models"] = ["robyn_admin.models", self.modules["models"]]
            else:
                self.modules["models"] = ["robyn_admin.models"]
            print("第二次", self.modules)
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

    def _setup_routes(self):
        """设置路由"""
        # 处理路径和带斜杠的路径
        @self.app.get(f"/{self.name}")
        async def admin_index(request: Request):
            user = await self._get_current_user(request)
            if not user:
                return Response(status_code=307, headers={"Location": f"/{self.name}/login"})
            
            language = await self._get_language(request)  # 获取语言设置
            context = {
                "site_title": get_text("admin_title", language),
                "models": self.models,
                "menus": self.menus,  # 添加menus到上下文
                "user": user,
                "language": language  # 传递语言参数
            }
            return self.jinja_template.render_template("admin/index.html", **context)
            
        @self.app.get(f"/{self.name}/login")
        async def admin_login(request: Request):
            user = await self._get_current_user(request)
            if user:
                return Response(status_code=307, headers={"Location": f"/{self.name}"})
            
            language = await self._get_language(request)  # 获取语言设置
            context = {
                "user": None,
                "language": language
            }
            return self.jinja_template.render_template("admin/login.html", **context)
            
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
                    "SameSite=Lax",     # 防止CSRF
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
                context = {
                    "error": "用户或密码错误",
                    "user": None
                }
                return self.jinja_template.render_template("admin/login.html", **context)

                
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
            """模型页面中，搜索功能相关接口，进行匹配查询结果"""
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
            try:
                model_name: str = request.path_params.get("model_name")
                user = await self._get_current_user(request)
                if not user:
                    return Response(status_code=303, description="", headers={"Location": f"/{self.name}/login"})
                
                model_admin = self.models.get(model_name)
                if not model_admin:
                    return Response(status_code=404, description="模型不存在", headers={"Location": f"/{self.name}/login"})
                
                language = await self._get_language(request)
                
                # 获取前端配置
                frontend_config = model_admin.get_frontend_config()
                # 添加语言配置
                frontend_config["language"] = language
                
                # 添加过滤器配置到上下文
                filters = [field.to_dict() for field in model_admin.filter_fields]
                
                # 添加翻译文本
                translations = {
                    "add": get_text("add", language),
                    "batch_delete": get_text("batch_delete", language),
                    "confirm_batch_delete": get_text("confirm_batch_delete", language),
                    "deleting": get_text("deleting", language),
                    "delete_success": get_text("delete_success", language),
                    "delete_failed": get_text("delete_failed", language),
                    "selected_items": get_text("selected_items", language),
                    "clear_selection": get_text("clear_selection", language),
                    "please_select_items": get_text("please_select_items", language),
                    "export": get_text("export", language),
                    "export_selected": get_text("export_selected", language),
                    "export_current": get_text("export_current", language),
                    "load_failed": get_text("load_failed", language),
                    # 添加过滤器相关的翻译
                    "search": get_text("search", language),
                    "reset": get_text("reset", language),
                    "filter": get_text("filter", language),
                    "all": get_text("all", language),  # 添加"全部"选项的翻译
                }
                
                context = {
                    "site_title": get_text("admin_title", language),
                    "models": self.models,
                    "menus": self.menus,
                    "user": user,
                    "language": language,
                    "current_model": model_name,
                    "verbose_name": model_admin.verbose_name,
                    "frontend_config": frontend_config,
                    "filters": filters,  # 添加过滤器配置到上下文
                    "translations": translations  # 添加翻译文本到上下文
                }
                
                return self.jinja_template.render_template("admin/model_list.html", **context)
                
            except Exception as e:
                print(f"Error in model_list: {str(e)}")
                traceback.print_exc()
                return Response(
                    status_code=500,
                    description=f"获取列表页失败: {str(e)}"
                )


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
            
            # 处理表数
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
                model_name = request.path_params.get("model_name")
                model_admin = self.models.get(model_name)
                if not model_admin:
                    return Response(status_code=404, description="模型不存在")

                # 查询参数获取分页和搜索参数
                query_params = request.query_params
                limit = int(query_params.get('limit', str(model_admin.per_page)))
                offset = int(query_params.get('offset', '0'))
                
                # 构建查询参数字典
                params = {
                    'search': query_params.get('search', ''),
                    'sort': query_params.get('sort', ''),
                    'order': query_params.get('order', 'asc')
                }
                
                # 处理过滤器参数
                for filter_field in model_admin.filter_fields:
                    field_value = query_params.get(filter_field.name)
                    if field_value:
                        params[filter_field.name] = field_value
                
                # 构建基础查询
                base_queryset = await model_admin.get_queryset(request, params)
                
                # 获取总记录数
                total = await base_queryset.count()
                
                # 获取分页数据
                objects = await base_queryset.offset(offset).limit(limit)
                
                # 序列化数据
                data = []
                for obj in objects:
                    try:
                        display_data = await model_admin.serialize_object(obj, for_display=True)
                        raw_data = await model_admin.serialize_object(obj, for_display=False)
                        data.append({
                            'display': display_data,
                            'data': raw_data
                        })
                    except Exception as e:
                        print(f"Error serializing object {obj.id}: {str(e)}")
                        continue
                
                return jsonify({
                    "total": total,
                    "data": data
                })
                
            except Exception as e:
                print(f"Error in model_data: {str(e)}")
                traceback.print_exc()
                return jsonify({
                    "success": False,
                    "message": f"获取数据失败: {str(e)}",
                    "total": 0,
                    "data": []
                })
        
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
                    return Response(status_code=404, description="型不存在", headers={"Location": f"/{self.name}/login"})
                
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
                
                # 批量除
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
            """处理文件传"""
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
                            "message": "不支持文件类型，仅支持jpg、jpeg、png、gif格式",
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
        
        @self.app.post(f"/{self.name}/set_language")
        async def set_language(request: Request):
            """设置语言"""
            try:
                data = request.body
                params = parse_qs(data)
                language = params.get('language', [self.default_language])[0]
                
                # 获取当前session
                session_data = request.headers.get('Cookie')
                session_dict = {}
                if session_data:
                    for item in session_data.split(";"):
                        if "=" in item:
                            key, value = item.split("=")
                            session_dict[key.strip()] = value.strip()
                        
                # 更新session中的语言设置
                session = session_dict.get("session", "{}")
                data = json.loads(session)
                data["language"] = language
                
                # 构建cookie
                cookie_value = json.dumps(data)
                cookie_attrs = [
                    f"session={cookie_value}",
                    "HttpOnly",
                    "SameSite=Lax",
                    "Path=/",
                ]
                
                return Response(
                    status_code=200,
                    description="Language set successfully",
                    headers={"Set-Cookie": "; ".join(cookie_attrs)}
                )
            except Exception as e:
                print(f"Set language failed: {str(e)}")
                return Response(status_code=500, description="Set language failed")
        
    def register_model(self, model: Type[Model], admin_class: Optional[Type[ModelAdmin]] = None):
        """注册模型到admin点"""
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
        
    async def _get_language(self, request: Request) -> str:
        """获取当前语言"""
        try:
            session_data = request.headers.get('Cookie')
            if not session_data:
                return self.default_language
                
            session_dict = {}
            for item in session_data.split(";"):
                if "=" in item:  # 确保有等号
                    key, value = item.split("=", 1)  # 只分割第一个等号
                    session_dict[key.strip()] = value.strip()
                
            session = session_dict.get("session")
            if not session:
                return self.default_language
                
            try:
                data = json.loads(session)
                return data.get("language", self.default_language)
            except json.JSONDecodeError:
                return self.default_language
                
        except Exception as e:
            print(f"Error getting language: {str(e)}")
            return self.default_language
        
    def register_menu(self, menu_item: MenuItem):
        """注菜单项"""
