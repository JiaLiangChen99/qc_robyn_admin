from typing import Type, Optional, List, Dict, Union
from tortoise.models import Model
from robyn import Robyn, Request, Response
from robyn.templating import JinjaTemplate
from pathlib import Path
import os
import json
from datetime import datetime
from types import ModuleType
from urllib.parse import parse_qs

from ..models import AdminUser

class ModelAdmin:
    """模型管理类的基类"""
    list_display: List[str] = []  # 列表页显示的字段
    search_fields: List[str] = []  # 搜索字段
    readonly_fields: List[str] = []  # 只读字段
    exclude: List[str] = []  # 排除的字段
    per_page: int = 10  # 每页显示数量
    
    def __init__(self, model: Type[Model]):
        self.model = model
        
    async def get_queryset(self, search_term: str = None):
        """获取查询集"""
        queryset = self.model.all()
        if search_term and self.search_fields:
            # 构建搜索条件
            from tortoise.expressions import Q
            search_conditions = Q()
            for field in self.search_fields:
                search_conditions |= Q(**{f"{field}__icontains": search_term})
            queryset = queryset.filter(search_conditions)
        return queryset
        
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

    def serialize_object(self, obj):
        """将模型对象序列化为字典"""
        fields = self.get_list_fields()
        return {
            field_name: str(getattr(obj, field_name))
            for field_name in fields
        }

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
                    "SameSite=Lax",     # 防止CSRF攻击
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
            
            # 从查询参数获取搜索词
            search_term = request.query_params.get("search")
            
            # 获取数据列表
            queryset = await model_admin.get_queryset(search_term)
            objects = await queryset.limit(model_admin.per_page)
            
            # 序列化对象列表
            serialized_objects = [model_admin.serialize_object(obj) for obj in objects]
            
            # 获取字段列表
            fields = model_admin.get_list_fields()
            form_fields = model_admin.get_form_fields()
            
            context = {
                "model_name": model_name,
                "models": self.models,
                "objects": serialized_objects,
                "fields": fields,
                "form_fields": form_fields,  # 添加表单字段
                "user": user,
                "search_fields": model_admin.search_fields,
                "search_term": search_term,
                "readonly_fields": model_admin.readonly_fields
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
                    headers={"Location": f"/{self.name}/{model_name}"}
                )
            
            try:
                # 获取要编辑的对象
                obj = await model_admin.get_object(object_id)
                if not obj:
                    return Response(
                        status_code=404, 
                        description="记录不存在",
                        headers={"Location": f"/{self.name}/{model_name}"}
                    )
                
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
                
                # 更新对象
                for field, value in filtered_data.items():
                    setattr(obj, field, value)
                await obj.save()
                
                return Response(
                    status_code=200,
                    description="更新成功",
                    headers={"Location": f"/{self.name}/{model_name}"}
                )
            except Exception as e:
                print(f"更新失败: {str(e)}")
                return Response(
                    status_code=400,
                    description=f"更新失败: {str(e)}",
                    headers={"Location": f"/{self.name}/{model_name}"}
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
                
                # 删除对象
                await obj.delete()
                
                return Response(
                    status_code=200,
                    description="删除成功",
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