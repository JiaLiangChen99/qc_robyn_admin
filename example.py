from datetime import datetime
from typing import Dict, Any, List
from functools import cached_property
from functools import reduce
import operator
from robyn import Request, Response
from urllib.parse import unquote
from tortoise.queryset import QuerySet
from setting.setting import DATABASE_URL
from model.table import PushStatus, US_Trademark, US_DocumentRecord

from robyn_admin.core import (
    AdminSite, ModelAdmin, MenuItem,
    TableField, SearchField, DisplayType
)
from robyn_admin.core.filters import InputFilter, SelectFilter, FilterField
from robyn import Robyn
from robyn_admin.core.inline import InlineModelAdmin, FormField
from robyn_admin.core.fields import TableAction

class DocumentInline(InlineModelAdmin):
    model = US_DocumentRecord
    fk_field = 'trademark'
    extra = 1
    verbose_name = "文档记录"
    
    table_fields = [
        TableField(
            "document_description", 
            label="文档描述", 
            editable=False,
            sortable=True
        ),
        TableField(
            "create_mail_date", 
            label="创建时间", 
            display_type=DisplayType.DATETIME, 
            editable=False, 
            formatter=lambda x: x.strftime('%Y-%m-%d') if x else '',
            sortable=True
        ),
        TableField(
            "document_link", 
            label="文档链接", 
            editable=False, 
            display_type=DisplayType.LINK,
            formatter=lambda x: f'<a href="{x}" target="_blank">点击跳转</a>' if x else ''
        )
    ]
    form_fields = [
        FormField("document_description", label="文档描述", required=True, field_type=DisplayType.SELECT, choices={}),
        FormField("create_mail_date", label="创建时间", field_type=DisplayType.DATETIME),
        FormField("document_link", label="文档链接")
    ]
    default_ordering = ["-create_mail_date"]

    class Meta:
        description = "文档记录"  # 用于显示标题



class US_TrademarkAdmin(ModelAdmin):
    verbose_name = "美国商标信息"
    menu_group = "商标管理"
    menu_icon = "bi bi-trademark"
    menu_order = 1
    # 明确设置权限
    enable_edit = False
    allow_add = False
    allow_delete = False
    allow_export = True
    
    async def get_status_choices(self) -> Dict[str, str]:
        """获取状态选项"""
        status_choices = await US_Trademark.all().values_list('status', flat=True)
        return {status: status for status in status_choices if status}
    
    async def get_filter_fields(self) -> List[FilterField]:
        """获取过滤字段配置"""
        status_choices = await self.get_status_choices()        
        filters = [
            InputFilter(
                "mark_name", 
                label="商标名", 
                placeholder="请输入商标名",
                operator="icontains"
            ),
            SelectFilter(
                "status", 
                label="状态",  
                choices=status_choices,
            )
        ]
        return filters
    
    table_fields = [
        TableField(
            name="id", label="ID", display_type=DisplayType.TEXT, editable=False, hidden=True
        ),
        TableField(
            "mark_name", label="商标名", display_type=DisplayType.TEXT, sortable=True, formatter=lambda x: str(x)
        ),
        TableField(
            "serial_number", label="序列号", display_type=DisplayType.TEXT, sortable=True, formatter=lambda x: str(x)
        ),
        TableField(
            "registration_number", label="注册号", display_type=DisplayType.TEXT, sortable=True, formatter=lambda x:  str(x) if x else None
        ),
        TableField(
            'status', label='状态', display_type=DisplayType.TEXT, sortable=True, formatter=lambda x: str(x)
        ),
        TableField(
            'owner_name', label='所有人', display_type=DisplayType.TEXT, sortable=True, formatter=lambda x: str(x)
        ),
        TableField(
            'international_classes', label='国际分类号', display_type=DisplayType.TEXT, sortable=True, formatter=lambda x: str(x)
        ),
        TableField(
            'us_classes', label='美国服务分类号', display_type=DisplayType.TEXT, sortable=True, formatter=lambda x: str(x)
        )
    ]
    search_fields = [
        SearchField(
            name="serial_number", 
            label="序列号", 
            placeholder="请输入序列号",
            operator="exact"  # 使用精确匹配而不是模糊匹配
        )
    ]
    # 
    
    default_ordering = ["-serial_number"]

    inlines = [DocumentInline]


class US_DocumentRecordAdmin(ModelAdmin):
    """带商标序列号的状态信息管理"""
    verbose_name = "流程部重要美国商标状态"
    menu_group = "商标管理"
    menu_icon = "bi bi-trademark"
    menu_order = 2
    
    allow_delete = False
    enable_edit = True
    allow_add = False

    async def get_queryset(self, request: Request, params: dict) -> QuerySet:
        """geting tortoise queryset"""
        print("调用自定义的更新函数", type(self.model))
        queryset = self.model.all()
        # 我需要根据每个id,查询出每个id的create_mail_date为最新的记录
        queryset = queryset.filter(push_to_process=True)
        # 这里需要对params里面的数据进行url解码, params是dict类型
        for key, value in params.items():
            if isinstance(value, str):
                params[key] = unquote(value)
        # 处理外键过滤 - 从内联配置中获取外键字段名
        for inline in self._inline_instances:
            if inline.model == self.model:  # 如果当前模型是内联模型
                parent_id = params.get(inline.fk_field)  # 使用配置的外键字段名
                if parent_id:
                    queryset = queryset.filter(**{f"{inline.fk_field}_id": parent_id})
                    print(f"Filtered by {inline.fk_field}_id =", parent_id)
                    break
        # 处理搜索
        search = params.get('search', '')
        if search and self.search_fields:
            search_conditions = []
            for field in self.search_fields:
                try:
                    # 使用 SearchField 的 build_search_query 方法构建查询
                    query_dict = await field.build_search_query(search)
                    print(f"Search field {field.name} query:", query_dict)
                    if query_dict:
                        if len(query_dict) == 1 and "id" in query_dict and query_dict["id"] is None:
                            continue  # 跳过没有匹配结果的关联搜索
                        if "_q_object" in query_dict:
                            search_conditions.append(query_dict["_q_object"])
                        else:
                            search_conditions.append(Q(**query_dict))
                except Exception as e:
                    print(f"Error building search query for {field.name}: {str(e)}")
                    continue
                
            if search_conditions:
                combined_q = reduce(operator.or_, search_conditions)
                queryset = queryset.filter(combined_q)
                print("After search queryset:", queryset)
        # 处理过滤器
        filter_fields = await self.get_filter_fields()
        for filter_field in filter_fields:
            filter_value = params.get(filter_field.name)
            if filter_value:
                try:
                    query_dict = await filter_field.build_filter_query(filter_value)
                    print(f"Filter field {filter_field.name} query:", query_dict)
                    if query_dict:
                        if len(query_dict) == 1 and "id" in query_dict and query_dict["id"] is None:
                            continue
                        if "_q_object" in query_dict:
                            # 如果是Q对象，直接使用filter
                            queryset = queryset.filter(query_dict["_q_object"])
                        else:
                            # 否则使用关键字参数
                            queryset = queryset.filter(**query_dict)
                        print("Updated queryset:", queryset)
                except Exception as e:
                    print(f"Error building filter query for {filter_field.name}: {str(e)}")
                    continue
        return queryset

    table_fields = [
        TableField(
            "id", 
            label="ID", 
            display_type=DisplayType.TEXT, 
            editable=True, 
            hidden=True
        ),
        TableField(
            "US_Trademark_mark_name",
            label="商标",
            related_model=US_Trademark,
            related_key="trademark_id",
            sortable=True
        ),
        TableField(
            "US_Trademark_serial_number",
            label="商标序列号",
            related_model=US_Trademark,
            related_key="trademark_id",
            sortable=True
        ),
        TableField(
            "document_description", 
            label="文档描述", 
            display_type=DisplayType.TEXT, 
            sortable=True, 
            formatter=lambda x: x
        ),
        TableField(
            "create_mail_date", 
            label="创建时间", 
            display_type=DisplayType.DATETIME, 
            sortable=True, 
            formatter=lambda x: x.strftime('%Y-%m-%d') if x else ''
        ),
        TableField(
            "document_link", 
            label="文档链接", 
            display_type=DisplayType.LINK,
            sortable=True,
            formatter=lambda x: f'<a href="{x}" target="_blank">查看文件</a>' if x else ''
        )
    ]
    
    default_ordering = ["id"]
    
    search_fields = [
        SearchField(
            name="document_description",
            label="商标序列号",
            placeholder="请输入商标序列号",
        )
    ]
    filter_fields = [
        SelectFilter(
            name="push_to_process_done",
            label="处理情况",
            choices={True: "已处理", False: "未处理"}
        )
    ]

    form_fields = [
        FormField(
            "push_to_process_done",
            label="代办事项",
            field_type=DisplayType.SELECT,
            readonly=True,
            choices={False:"未处理", True: "已处理"}
        )
    ]


class US_DocumentRecord_Rita_Admin(ModelAdmin):
    """带商标序列号的状态信息管理"""
    verbose_name = "客服部重要美国商标状态"
    menu_group = "商标管理"
    menu_icon = "bi bi-trademark"
    menu_order = 3
    enable_edit = False
    allow_add = False
    allow_delete = False
    allow_export = True
    
    async def get_filter_fields(self) -> List[FilterField]:
        """获取过滤字段配置"""
        filters = [
            SelectFilter(
                "push_to_customer_done", 
                label="处理情况",  
                choices={"已处理": True, "未处理": False},
            ),
        ]
        return filters

    async def get_queryset(self, request: Request, params: dict) -> QuerySet:
        """获取查询集"""
        print("调用自定义的更新函数", type(self.model))
        
        # 使用 select_related 预加载关联的 US_Trademark 数据
        queryset = self.model.all().select_related("trademark")
        
        # 基本过滤条件
        queryset = queryset.filter(
            push_to_customer=True,
            push_to_customer_done=False
        )
        
        # 添加关联表的过滤条件
        queryset = queryset.filter(
            trademark__deal_customer="Rita"  # 使用双下划线访问关联表字段
        )
        
        # URL 解码
        for key, value in params.items():
            if isinstance(value, str):
                params[key] = unquote(value)
            
        # 处理外键过滤
        for inline in self._inline_instances:
            if inline.model == self.model:
                parent_id = params.get(inline.fk_field)
                if parent_id:
                    queryset = queryset.filter(**{f"{inline.fk_field}_id": parent_id})
                    print(f"Filtered by {inline.fk_field}_id =", parent_id)
                    break
                
        # 处理搜索
        search = params.get('search', '')
        if search and self.search_fields:
            search_conditions = []
            for field in self.search_fields:
                try:
                    query_dict = await field.build_search_query(search)
                    print(f"Search field {field.name} query:", query_dict)
                    if query_dict:
                        if len(query_dict) == 1 and "id" in query_dict and query_dict["id"] is None:
                            continue
                        if "_q_object" in query_dict:
                            search_conditions.append(query_dict["_q_object"])
                        else:
                            search_conditions.append(Q(**query_dict))
                except Exception as e:
                    print(f"Error building search query for {field.name}: {str(e)}")
                    continue
            
            if search_conditions:
                combined_q = reduce(operator.or_, search_conditions)
                queryset = queryset.filter(combined_q)
                print("After search queryset:", queryset)
            
        # 处理过滤器
        filter_fields = await self.get_filter_fields()
        for filter_field in filter_fields:
            filter_value = params.get(filter_field.name)
            if filter_value:
                try:
                    query_dict = await filter_field.build_filter_query(filter_value)
                    print(f"Filter field {filter_field.name} query:", query_dict)
                    if query_dict:
                        if len(query_dict) == 1 and "id" in query_dict and query_dict["id"] is None:
                            continue
                        if "_q_object" in query_dict:
                            queryset = queryset.filter(query_dict["_q_object"])
                        else:
                            queryset = queryset.filter(**query_dict)
                        print("Updated queryset:", queryset)
                except Exception as e:
                    print(f"Error building filter query for {filter_field.name}: {str(e)}")
                    continue
                
        print("Final queryset:", queryset.sql())  # 打印最终的 SQL 查询
        return queryset

    table_fields = [
        TableField(
            "id", 
            label="ID", 
            display_type=DisplayType.TEXT, 
            editable=True, 
            hidden=True
        ),
        TableField(
            "US_Trademark_mark_name",
            label="商标",
            related_model=US_Trademark,
            related_key="trademark_id",
            sortable=True
        ),
        TableField(
            "US_Trademark_serial_number",
            label="商标序列号",
            related_model=US_Trademark,
            related_key="trademark_id",
            sortable=True
        ),
        TableField(
            "document_description", 
            label="文档描述", 
            display_type=DisplayType.TEXT, 
            sortable=True, 
            formatter=lambda x: x
        ),
        TableField(
            "create_mail_date", 
            label="创建时间", 
            display_type=DisplayType.DATETIME, 
            sortable=True, 
            formatter=lambda x: x.strftime('%Y-%m-%d') if x else ''
        ),
        TableField(
            "document_link", 
            label="文档链接", 
            display_type=DisplayType.LINK,
            sortable=True,
            formatter=lambda x: f'<a href="{x}" target="_blank">查看文件</a>' if x else ''
        ),
        TableField(
            "push_to_customer_done", 
            label="处理情况",
            display_type=DisplayType.SWITCH,
            editable=True,
            sortable=True,
            labels={True: "已处理", False: "未处理"},
            choices={True: True, False: False}
        )
    ]
    
    default_ordering = ["id"]
    
    search_fields = [
        SearchField(
            name="US_Trademark_mark_name",
            label="商标",
            placeholder="请输入名",
            related_model=US_Trademark,
            related_key="trademark_id",
        ),
        SearchField(
            name="US_Trademark_serial_number",
            label="序列号",
            placeholder="序列号",
            related_model=US_Trademark,
            related_key="trademark_id",
        )
    ]

class US_DocumentRecord_Kayden_Admin(ModelAdmin):
    """带商标序列号的状态信息管理"""
    verbose_name = "客服部重要美国商标状态"
    menu_group = "商标管理"
    menu_icon = "bi bi-trademark"
    menu_order = 4
    enable_edit = False
    allow_add = False
    allow_delete = False
    allow_export = True
    
    async def get_filter_fields(self) -> List[FilterField]:
        """获取过滤字段配置"""
        filters = [
            SelectFilter(
                "push_to_customer_done", 
                label="处理情况",  
                choices={"已处理": True, "未处理": False},
            ),
        ]
        return filters

    async def get_queryset(self, request: Request, params: dict) -> QuerySet:
        """获取查询集"""
        print("调用自定义的更新函数", type(self.model))
        
        # 使用 select_related 预加载关联的 US_Trademark 数据
        queryset = self.model.all().select_related("trademark")
        
        # 基本过滤条件
        queryset = queryset.filter(
            push_to_customer=True,
            push_to_customer_done=False
        )
        
        # 添加关联表的过滤条件
        queryset = queryset.filter(
            trademark__deal_customer="Kayden"  # 使用双下划线访问关联表字段
        )
        
        # URL 解码
        for key, value in params.items():
            if isinstance(value, str):
                params[key] = unquote(value)
            
        # 处理外键过滤
        for inline in self._inline_instances:
            if inline.model == self.model:
                parent_id = params.get(inline.fk_field)
                if parent_id:
                    queryset = queryset.filter(**{f"{inline.fk_field}_id": parent_id})
                    print(f"Filtered by {inline.fk_field}_id =", parent_id)
                    break
                
        # 处理搜索
        search = params.get('search', '')
        if search and self.search_fields:
            search_conditions = []
            for field in self.search_fields:
                try:
                    query_dict = await field.build_search_query(search)
                    print(f"Search field {field.name} query:", query_dict)
                    if query_dict:
                        if len(query_dict) == 1 and "id" in query_dict and query_dict["id"] is None:
                            continue
                        if "_q_object" in query_dict:
                            search_conditions.append(query_dict["_q_object"])
                        else:
                            search_conditions.append(Q(**query_dict))
                except Exception as e:
                    print(f"Error building search query for {field.name}: {str(e)}")
                    continue
            
            if search_conditions:
                combined_q = reduce(operator.or_, search_conditions)
                queryset = queryset.filter(combined_q)
                print("After search queryset:", queryset)
            
        # 处理过滤器
        filter_fields = await self.get_filter_fields()
        for filter_field in filter_fields:
            filter_value = params.get(filter_field.name)
            if filter_value:
                try:
                    query_dict = await filter_field.build_filter_query(filter_value)
                    print(f"Filter field {filter_field.name} query:", query_dict)
                    if query_dict:
                        if len(query_dict) == 1 and "id" in query_dict and query_dict["id"] is None:
                            continue
                        if "_q_object" in query_dict:
                            queryset = queryset.filter(query_dict["_q_object"])
                        else:
                            queryset = queryset.filter(**query_dict)
                        print("Updated queryset:", queryset)
                except Exception as e:
                    print(f"Error building filter query for {filter_field.name}: {str(e)}")
                    continue
                
        print("Final queryset:", queryset.sql())  # 打印最终的 SQL 查询
        return queryset

    table_fields = [
        TableField(
            "id", 
            label="ID", 
            display_type=DisplayType.TEXT, 
            editable=True, 
            hidden=True
        ),
        TableField(
            "US_Trademark_mark_name",
            label="商标",
            related_model=US_Trademark,
            related_key="trademark_id",
            sortable=True
        ),
        TableField(
            "US_Trademark_serial_number",
            label="商标序列号",
            related_model=US_Trademark,
            related_key="trademark_id",
            sortable=True
        ),
        TableField(
            "document_description", 
            label="文档描述", 
            display_type=DisplayType.TEXT, 
            sortable=True, 
            formatter=lambda x: x
        ),
        TableField(
            "create_mail_date", 
            label="创建时间", 
            display_type=DisplayType.DATETIME, 
            sortable=True, 
            formatter=lambda x: x.strftime('%Y-%m-%d') if x else ''
        ),
        TableField(
            "document_link", 
            label="文档链接", 
            display_type=DisplayType.LINK,
            sortable=True,
            formatter=lambda x: f'<a href="{x}" target="_blank">查看文件</a>' if x else ''
        ),
        TableField(
            "push_to_customer_done", 
            label="处理情况",
            display_type=DisplayType.SWITCH,
            editable=True,
            sortable=True,
            labels={True: "已处理", False: "未处理"},
            choices={True: True, False: False}
        )
    ]
    
    default_ordering = ["id"]
    
    search_fields = [
        SearchField(
            name="US_Trademark_mark_name",
            label="商标",
            placeholder="请输入名",
            related_model=US_Trademark,
            related_key="trademark_id",
        ),
        SearchField(
            name="US_Trademark_serial_number",
            label="序列号",
            placeholder="序列号",
            related_model=US_Trademark,
            related_key="trademark_id",
        )
    ]

class US_DocumentRecord_Robyn_Admin(ModelAdmin):
    """带商标序列号的状态信息管理"""
    verbose_name = "客服部重要美国商标状态"
    menu_group = "商标管理"
    menu_icon = "bi bi-trademark"
    menu_order = 5
    enable_edit = False
    allow_add = False
    allow_delete = False
    allow_export = True
    
    async def get_filter_fields(self) -> List[FilterField]:
        """获取过滤字段配置"""
        filters = [
            SelectFilter(
                "push_to_customer_done", 
                label="处理情况",  
                choices={"已处理": True, "未处理": False},
            ),
        ]
        return filters

    async def get_queryset(self, request: Request, params: dict) -> QuerySet:
        """获取查询集"""
        print("调用自定义的更新函数", type(self.model))
        
        # 使用 select_related 预加载关联的 US_Trademark 数据
        queryset = self.model.all().select_related("trademark")
        
        # 基本过滤条件
        queryset = queryset.filter(
            push_to_customer=True,
            push_to_customer_done=False
        )
        
        # 添加关联表的过滤条件
        queryset = queryset.filter(
            trademark__deal_customer="Robyn"  # 使用双下划线访问关联表字段
        )
        
        # URL 解码
        for key, value in params.items():
            if isinstance(value, str):
                params[key] = unquote(value)
            
        # 处理外键过滤
        for inline in self._inline_instances:
            if inline.model == self.model:
                parent_id = params.get(inline.fk_field)
                if parent_id:
                    queryset = queryset.filter(**{f"{inline.fk_field}_id": parent_id})
                    print(f"Filtered by {inline.fk_field}_id =", parent_id)
                    break
                
        # 处理搜索
        search = params.get('search', '')
        if search and self.search_fields:
            search_conditions = []
            for field in self.search_fields:
                try:
                    query_dict = await field.build_search_query(search)
                    print(f"Search field {field.name} query:", query_dict)
                    if query_dict:
                        if len(query_dict) == 1 and "id" in query_dict and query_dict["id"] is None:
                            continue
                        if "_q_object" in query_dict:
                            search_conditions.append(query_dict["_q_object"])
                        else:
                            search_conditions.append(Q(**query_dict))
                except Exception as e:
                    print(f"Error building search query for {field.name}: {str(e)}")
                    continue
            
            if search_conditions:
                combined_q = reduce(operator.or_, search_conditions)
                queryset = queryset.filter(combined_q)
                print("After search queryset:", queryset)
            
        # 处理过滤器
        filter_fields = await self.get_filter_fields()
        for filter_field in filter_fields:
            filter_value = params.get(filter_field.name)
            if filter_value:
                try:
                    query_dict = await filter_field.build_filter_query(filter_value)
                    print(f"Filter field {filter_field.name} query:", query_dict)
                    if query_dict:
                        if len(query_dict) == 1 and "id" in query_dict and query_dict["id"] is None:
                            continue
                        if "_q_object" in query_dict:
                            queryset = queryset.filter(query_dict["_q_object"])
                        else:
                            queryset = queryset.filter(**query_dict)
                        print("Updated queryset:", queryset)
                except Exception as e:
                    print(f"Error building filter query for {filter_field.name}: {str(e)}")
                    continue
                
        print("Final queryset:", queryset.sql())  # 打印最终的 SQL 查询
        return queryset

    table_fields = [
        TableField(
            "id", 
            label="ID", 
            display_type=DisplayType.TEXT, 
            editable=True, 
            hidden=True
        ),
        TableField(
            "US_Trademark_mark_name",
            label="商标",
            related_model=US_Trademark,
            related_key="trademark_id",
            sortable=True
        ),
        TableField(
            "US_Trademark_serial_number",
            label="商标序列号",
            related_model=US_Trademark,
            related_key="trademark_id",
            sortable=True
        ),
        TableField(
            "document_description", 
            label="文档描述", 
            display_type=DisplayType.TEXT, 
            sortable=True, 
            formatter=lambda x: x
        ),
        TableField(
            "create_mail_date", 
            label="创建时间", 
            display_type=DisplayType.DATETIME, 
            sortable=True, 
            formatter=lambda x: x.strftime('%Y-%m-%d') if x else ''
        ),
        TableField(
            "document_link", 
            label="文档链接", 
            display_type=DisplayType.LINK,
            sortable=True,
            formatter=lambda x: f'<a href="{x}" target="_blank">查看文件</a>' if x else ''
        ),
        TableField(
            "push_to_customer_done", 
            label="处理情况",
            display_type=DisplayType.SWITCH,
            editable=True,
            sortable=True,
            labels={True: "已处理", False: "未处理"},
            choices={True: True, False: False}
        )
    ]
    
    default_ordering = ["id"]
    
    search_fields = [
        SearchField(
            name="US_Trademark_mark_name",
            label="商标",
            placeholder="请输入名",
            related_model=US_Trademark,
            related_key="trademark_id",
        ),
        SearchField(
            name="US_Trademark_serial_number",
            label="序列号",
            placeholder="序列号",
            related_model=US_Trademark,
            related_key="trademark_id",
        )
    ]


def register_admin_site(app: Robyn):
    admin_site = AdminSite(
        app,
        title="商标监测系统",
        prefix="admin",
        copyright="© 2024 乘风国际 版权所有",  # 设置版权信息
        db_url=DATABASE_URL,
        modules={
            "models": ["model.table", "robyn_admin.models"]
        },
        default_language="zh_CN",
        generate_schemas=True
    )

    # 注册菜单
    admin_site.register_menu(MenuItem(
        name="商标管理",
        icon="bi bi-trademark",
        order=1
    ))

    
    
    # 注册业务模型
    admin_site.register_model(US_Trademark, US_TrademarkAdmin)
    admin_site.register_model(US_DocumentRecord, US_DocumentRecordAdmin)
    admin_site.register_model(US_DocumentRecord, US_DocumentRecord_Rita_Admin)
    admin_site.register_model(US_DocumentRecord, US_DocumentRecord_Kayden_Admin)
    admin_site.register_model(US_DocumentRecord, US_DocumentRecord_Robyn_Admin)
    return admin_site  # 确保返回 admin_site 实例
