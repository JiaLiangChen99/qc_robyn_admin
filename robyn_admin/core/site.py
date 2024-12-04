from typing import Type, Optional, Dict, List, Union
from types import ModuleType
from tortoise import Model, Tortoise
from robyn import Robyn, Request, Response, jsonify
from robyn.templating import JinjaTemplate
from pathlib import Path
import os
import json
from datetime import datetime
import traceback
from urllib.parse import parse_qs, unquote

from .model_admin import ModelAdmin
from .menu import MenuManager, MenuItem
from ..models import AdminUser
from ..i18n.translations import get_text

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
        self.app = app
        self.name = name
        self.models: Dict[str, ModelAdmin] = {}
        self.default_language = default_language
        self.menu_manager = MenuManager()
        
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
        @self.app.startup_handler
        async def init_admin():
            # 如果没有提供配置,尝试获取已有配置
            if not self.db_url:
                if not Tortoise._inited:
                    raise Exception("数据库未初始化,请配置数据库或提供db_url参数")
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
                else:
                    self.modules["models"] = ["robyn_admin.models", self.modules["models"]]
            else:
                self.modules["models"] = ["robyn_admin.models"]

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
                print(f"创建管理账号失败: {str(e)}")

    async def _get_current_user(self, request: Request) -> Optional[AdminUser]:
        """获取当前登录用户"""
        try:
            # 从cookie中获取session
            session_data = request.headers.get('Cookie')
            if not session_data:
                return None
            session_dict = {}
            for item in session_data.split(";"):
                if "=" in item:
                    key, value = item.split("=")
                    session_dict[key.strip()] = value.strip()
            session = session_dict.get("session")
            if not session:
                return None
            user_id = json.loads(session).get("user_id")
            if not user_id:
                return None
            # 通过user_id获取用户
            user = await AdminUser.get(id=user_id)
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
                if "=" in item:
                    key, value = item.split("=", 1)
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

    def _setup_routes(self):
        """设置路由"""
        # 处理路径和带斜杠的路径
        @self.app.get(f"/{self.name}")
        async def admin_index(request: Request):
            user = await self._get_current_user(request)
            if not user:
                return Response(status_code=307, headers={"Location": f"/{self.name}/login"}, description="")
            
            language = await self._get_language(request)
            context = {
                "site_title": get_text("admin_title", language),
                "models": self.models,
                "menus": self.menu_manager.get_menu_tree(),  # 使用menu_manager获取菜单树
                "user": user,
                "language": language
            }
            return self.jinja_template.render_template("admin/index.html", **context)
            
        @self.app.get(f"/{self.name}/login")
        async def admin_login(request: Request):
            user = await self._get_current_user(request)
            if user:
                return Response(status_code=307, headers={"Location": f"/{self.name}"}, description="")
            
            language = await self._get_language(request)
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
                    "HttpOnly",
                    "SameSite=Lax",
                    "Path=/",
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
                context = {
                    "error": "用户名或密码错误",
                    "user": None
                }
                return self.jinja_template.render_template("admin/login.html", **context)
                
        @self.app.get(f"/{self.name}/logout")
        async def admin_logout(request: Request):
            cookie_attrs = [
                "session=",
                "HttpOnly",
                "SameSite=Lax",
                "Path=/",
                "Max-Age=0"
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
            """模型搜索接口"""
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
            
            search_values = {
                field.name: unquote(request.query_params.get(f"search_{field.name}"))
                for field in model_admin.search_fields
                if request.query_params.get(f"search_{field.name}")
            }
            
            queryset = await model_admin.get_queryset(None, search_values)
            objects = await queryset.limit(model_admin.per_page)
            
            result = {
                "data": [
                    {
                        'display': await model_admin.serialize_object(obj, for_display=True),
                        'data': await model_admin.serialize_object(obj, for_display=False)
                    }
                    for obj in objects
                ]
            }
            return jsonify(result)

        @self.app.get(f"/{self.name}/:model_name")
        async def model_list(request: Request):
            """模型列表页"""
            try:
                model_name: str = request.path_params.get("model_name")
                user = await self._get_current_user(request)
                if not user:
                    return Response(status_code=303, headers={"Location": f"/{self.name}/login"})
                
                model_admin = self.models.get(model_name)
                if not model_admin:
                    return Response(status_code=404, description="模型不存在")
                
                language = await self._get_language(request)
                
                frontend_config = model_admin.get_frontend_config()
                frontend_config["language"] = language                
                filters = [field.to_dict() for field in model_admin.filter_fields]
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
                    "search": get_text("search", language),
                    "reset": get_text("reset", language),
                    "filter": get_text("filter", language),
                    "all": get_text("all", language),
                }
                
                context = {
                    "site_title": get_text("admin_title", language),
                    "models": self.models,
                    "menus": self.menu_manager.get_menu_tree(),
                    "user": user,
                    "language": language,
                    "current_model": model_name,
                    "verbose_name": model_admin.verbose_name,
                    "frontend_config": frontend_config,
                    "filters": filters,
                    "translations": translations
                }
                
                return self.jinja_template.render_template("admin/model_list.html", **context)
                
            except Exception as e:
                print(f"Error in model_list: {str(e)}")
                traceback.print_exc()
                return Response(
                    status_code=500,
                    description=f"获取列表页失败: {str(e)}",
                    headers={"Content-Type": "application/json"}
                )

        @self.app.get(f"/{self.name}/:model_name/data")
        async def model_data(request: Request):
            """获取模型数据，支持分页、搜索和排序"""
            try:
                model_name = request.path_params.get("model_name")
                model_admin = self.models.get(model_name)
                if not model_admin:
                    return Response(status_code=404, description="模型不存在", headers={"Content-Type": "application/json"})

                query_params = request.query_params
                limit = int(query_params.get('limit', str(model_admin.per_page)))
                offset = int(query_params.get('offset', '0'))
                
                params = {
                    'search': query_params.get('search', ''),
                    'sort': query_params.get('sort', ''),
                    'order': query_params.get('order', 'asc')
                }
                
                for filter_field in model_admin.filter_fields:
                    field_value = query_params.get(filter_field.name)
                    if field_value:
                        params[filter_field.name] = field_value
                
                base_queryset = await model_admin.get_queryset(request, params)
                total = await base_queryset.count()
                objects = await base_queryset.offset(offset).limit(limit)
                
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
                    return Response(status_code=401, description="未登录")
                
                model_admin = self.models.get(model_name)
                if not model_admin:
                    return Response(status_code=404, description="模型不存在")
                
                data = request.body
                params = parse_qs(data)
                ids = params.get('ids[]', [])
                
                if not ids:
                    return jsonify({
                        "code": 400,
                        "message": "未选择要删除的记录",
                        "success": False
                    })
                
                deleted_count = 0
                for id in ids:
                    try:
                        obj = await model_admin.get_object(id)
                        if obj:
                            await obj.delete()
                            deleted_count += 1
                    except Exception as e:
                        print(f"删除记录 {id} 失败: {str(e)}")
                
                return jsonify({
                    "code": 200,
                    "message": f"成功删除 {deleted_count} 条记录",
                    "success": True
                })
                
            except Exception as e:
                print(f"批量删除失败: {str(e)}")
                return jsonify({
                    "code": 500,
                    "message": f"批量删除失败: {str(e)}",
                    "success": False
                })

        @self.app.post(f"/{self.name}/upload")
        async def file_upload(request: Request):
            """处理文件上传"""
            try:
                user = await self._get_current_user(request)
                if not user:
                    return jsonify({
                        "code": 401,
                        "message": "未登录",
                        "success": False
                    })

                files = request.files
                if not files:
                    return jsonify({
                        "code": 400,
                        "message": "没有上传文件",
                        "success": False
                    })

                upload_path = request.form_data.get('upload_path', 'static/uploads')
                uploaded_files = []
                for file_name, file_bytes in files.items():
                    if not file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        return jsonify({
                            "code": 400,
                            "message": "不支持的文件类型，仅支持jpg、jpeg、png、gif格式",
                            "success": False
                        })

                    import uuid
                    safe_filename = f"{uuid.uuid4().hex}{os.path.splitext(file_name)[1]}"
                    os.makedirs(upload_path, exist_ok=True)
                    file_path = os.path.join(upload_path, safe_filename)
                    
                    with open(file_path, 'wb') as f:
                        f.write(file_bytes)
                    
                    file_url = f"/{file_path.replace(os.sep, '/')}"
                    uploaded_files.append({
                        "original_name": file_name,
                        "saved_name": safe_filename,
                        "url": file_url
                    })
                
                return jsonify({
                    "code": 200,
                    "message": "上传成功",
                    "success": True,
                    "data": uploaded_files[0] if uploaded_files else None
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
                
                session_data = request.headers.get('Cookie')
                session_dict = {}
                if session_data:
                    for item in session_data.split(";"):
                        if "=" in item:
                            key, value = item.split("=")
                            session_dict[key.strip()] = value.strip()
                        
                session = session_dict.get("session", "{}")
                data = json.loads(session)
                data["language"] = language
                
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
                return Response(status_code=500, description="Set language failed", headers={"Content-Type": "application/json"})

    def register_model(self, model: Type[Model], admin_class: Optional[Type[ModelAdmin]] = None):
        """注册模型到admin站点"""
        if admin_class is None:
            admin_class = ModelAdmin
        self.models[model.__name__] = admin_class(model)
        
    def register_menu(self, menu_item: MenuItem):
        """注册菜单项"""
        self.menu_manager.register_menu(menu_item)