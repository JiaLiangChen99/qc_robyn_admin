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

from .admin import ModelAdmin
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
        self.menu_manager = MenuManager()  # 使用 MenuManager 来管理菜单
        
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
        """设置板目录"""
        current_dir = Path(__file__).parent.parent
        template_dir = os.path.join(current_dir, 'templates')
        self.template_dir = template_dir
        # 创建 Jinja2 环境并添加全局函数
        self.jinja_template = JinjaTemplate(template_dir)
        self.jinja_template.env.globals.update({
            'get_text': get_text
        })

    def _init_admin_db(self):
        """初始化admin数据"""
        from tortoise import Tortoise
        
        @self.app.startup_handler
        async def init_admin():
            # 如果没有提供配置,试获取已有配置
            if not self.db_url:
                if not Tortoise._inited:
                    raise Exception("数据库未始化,配置数据库或提供db_url参数")
                # 复用现有配置
                current_config = Tortoise.get_connection("default").config
                self.db_url = current_config.get("credentials", {}).get("dsn")
                
            if not self.modules:
                if not Tortoise._inited:
                    raise Exception("数据库未初始化,请先配置数据库或提供modules参数")
                # 用现有modules配
                self.modules = dict(Tortoise.apps)
            # 确保admin模型和用户模都被加载
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
                print(f"创建管理账号败: {str(e)}")

    def _setup_routes(self):
        """设置路由"""
        # 处理路径和带斜杠的路径
        @self.app.get(f"/{self.name}")
        async def admin_index(request: Request):
            user = await self._get_current_user(request)
            if not user:
                return Response(status_code=307, headers={"Location": f"/{self.name}/login"}, description="user not login")
            
            language = await self._get_language(request)  # 获取语言设置
            context = {
                "site_title": get_text("admin_title", language),
                "models": self.models,
                "menus": self.menu_manager.get_menu_tree(),  # 添加menus到上下文
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
            # 清除cookie时也需要设置同的属性
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
            
            # 获取索参数， 同时还要进url解码
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
            try:
                model_name: str = request.path_params.get("model_name")  
                user = await self._get_current_user(request)
                if not user:
                    return Response(status_code=303, description="", headers={"Location": f"/{self.name}/login"})
                model_admin = self.models.get(model_name)
                if not model_admin:
                    return Response(status_code=404, description="模型不存在", headers={"Location": f"/{self.name}/login"})
                # 获取前端配置
                frontend_config = await model_admin.get_list_config()
                language = await self._get_language(request)
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
                    "menus": self.menu_manager.get_menu_tree(),
                    "user": user,
                    "language": language,
                    "current_model": model_name,
                    "verbose_name": model_admin.verbose_name,
                    "frontend_config": frontend_config,
                    "filters": filters,  # 加过滤器配置到上下文
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
                # 获取当前语言设置
                language = await self._get_language(request)
                
                # 构建完整的上下文
                context = {
                    "models": self.models,
                    "model_name": model_name,
                    "fields": model_admin.get_form_fields(),
                    "user": user,
                    "action": "add",
                    "error": str(e),
                    "form_data": form_data,
                    "menus": self.menu_manager.get_menu_tree(),  # 添加菜单数据
                    "language": language,  # 添加语言设置
                    "site_title": get_text("admin_title", language)  # 添加站点标题
                }
                return self.jinja_template.render_template("admin/model_form.html", **context)

        @self.app.post(f"/{self.name}/:model_name/:id/edit")
        async def model_edit_post(request: Request):
            """处理编辑记录"""
            model_name: str = request.path_params.get("model_name")
            object_id: str = request.path_params.get("id")
            print("编辑的表单数据", object_id)
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
                
                # 解析表单数���
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
                print(f"除失败: {str(e)}")
                return Response(status_code=500, description=f"删除失败: {str(e)}", headers={"Location": f"/{self.name}/{model_name}"}  )
        
        @self.app.get(f"/{self.name}/:model_name/data")
        async def model_data(request: Request):
            """获取模型数据"""
            try:
                model_name: str = request.path_params.get("model_name")
                print(f"Handling data request for model: {model_name}")
                model_admin = self.get_model_admin(model_name)
                if not model_admin:
                    print(f"Model admin not found for: {model_name}")
                    print(f"Available models: {list(self.models.keys())}")
                    return jsonify({"error": "Model not found"}, status_code=404)
                # 解析查询参数
                params: dict = request.query_params.to_dict()
                query_params = {
                    'limit': int(params.get('limit', ['10'])[0]),
                    'offset': int(params.get('offset', ['0'])[0]),
                    'search': params.get('search', [''])[0],
                    'sort': params.get('sort', [''])[0],
                    'order': params.get('order', ['asc'])[0],
                }
                
                # 添加其他过滤参数
                for key, value in params.items():
                    if key not in ['limit', 'offset', 'search', 'sort', 'order', '_']:
                        query_params[key] = value[0]                
                # 获取查询集
                base_queryset = await model_admin.get_queryset(request, query_params)
                
                # 处理排序
                if query_params['sort']:
                    order_by = f"{'-' if query_params['order'] == 'desc' else ''}{query_params['sort']}"
                    base_queryset = base_queryset.order_by(order_by)
                elif model_admin.default_ordering:
                    base_queryset = base_queryset.order_by(*model_admin.default_ordering)
                    
                # 获取总记录数
                total = await base_queryset.count()
                
                # 分页
                queryset = base_queryset.offset(query_params['offset']).limit(query_params['limit'])
                
                # 列化数据
                data = []
                async for obj in queryset:
                    try:
                        serialized = await model_admin.serialize_object(obj)
                        data.append({
                            'data': serialized,
                            'display': serialized
                        })
                    except Exception as e:
                        print(f"Error serializing object: {str(e)}")
                        continue
                
                return jsonify({
                    "total": total,
                    "data": data
                })
                
            except Exception as e:
                print(f"Error in model_data: {str(e)}")
                traceback.print_exc()
                return jsonify({"error": str(e)})
        
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
                # 获取上传路参数
                upload_path = request.form_data.get('upload_path', 'static/uploads')
                # 处理上传的文件
                uploaded_files = []
                for file_name, file_bytes in files.items():
                    # 验证文件类型
                    if not file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        return jsonify({
                            "code": 400,
                            "message": "不支文类型，支持jpgjpeg、png、gif格式",
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
                    "data": uploaded_files[0] if uploaded_files else None  # 返回一个文件的信息
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
        
        @self.app.get(f"/{self.name}/:model_name/inline_data")
        async def get_inline_data(request: Request):
            try:
                model_name = request.path_params['model_name']
                model_admin = self.get_model_admin(model_name)
                if not model_admin:
                    print(f"Model admin not found for: {model_name}")
                    return jsonify({"error": "Model not found"}, status_code=404)
                
                params: dict = request.query_params.to_dict()
                parent_id = params.get('parent_id', [''])[0]
                inline_model = params.get('inline_model', [''])[0]
                
                print(f"Getting inline data for {model_name}, parent_id: {parent_id}, inline_model: {inline_model}")
                
                if not parent_id or not inline_model:
                    print("Missing required parameters")
                    return jsonify({"error": "Missing parameters"})
                
                data = await model_admin.get_inline_data(parent_id, inline_model)
                print(f"Got {len(data)} records")
                
                return jsonify({
                    "success": True,
                    "data": data,
                    "total": len(data)
                })
                
            except Exception as e:
                print(f"Error in get_inline_data: {str(e)}")
                traceback.print_exc()
                return jsonify({"error": str(e)})
        
    def register_model(self, model: Type[Model], admin_class: Optional[Type[ModelAdmin]] = None):
        """注册型到admin点"""
        if admin_class is None:
            admin_class = ModelAdmin
        instance = admin_class(model)
        print(f"\n=== Registering Model ===")
        print(f"Model: {model.__name__}")
        print(f"Admin Class: {admin_class.__name__}")
        print("========================\n")
        self.models[model.__name__] = instance
        
    async def _get_current_user(self, request: Request) -> Optional[AdminUser]:
        """获取当前登录用户"""
        try:
            # 从cookie中获取session
            session_data = request.headers.get('Cookie')
            # session={"user_id": 1};xxxx={"xx":"xx"}
            if not session_data:
                return None
            session_dict = {}
            for item in session_data.split(";"):
                key, value = item.split("=")
                session_dict[key.strip()] = value.strip()
            session = session_dict.get("session")
            user_id = json.loads(session).get("user_id")
            if not user_id:
                return None
            # 通过user_id获取用户
            user = await AdminUser.get(id=user_id)
            return user
        except Exception as e:
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
                    key, value = item.split("=", 1)  # 只分割一个等号
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
        """注册菜单项"""
        self.menu_manager.register_menu(menu_item)  # 使用 menu_manager 注册菜单

    def get_model_admin(self, model_name: str) -> Optional[ModelAdmin]:
        """获取模型管理器"""
        return self.models.get(model_name)