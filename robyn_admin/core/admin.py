from typing import Type, Optional, List, Dict, Union, Callable, Any
from urllib.parse import unquote
from tortoise.models import Model
from tortoise import fields
from tortoise.queryset import QuerySet
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
)
from .filters import (
    FilterField, SelectFilter, DateRangeFilter, 
    NumberRangeFilter, BooleanFilter, FilterType
)
from ..i18n.translations import get_text
from .menu import MenuManager  # 确保导入 MenuManager
from .inline import InlineModelAdmin

from tortoise.expressions import Q
import operator
from functools import reduce

@dataclass
class MenuItem:
    """菜单项配置"""
    name: str                    # 菜单名称
    icon: str = ""              # 图标类名 (Bootstrap Icons)
    parent: Optional[str] = None # 父菜单名称
    order: int = 0              # 排序值
    

def trace_method(func):
    def wrapper(*args, **kwargs):
        print(f"\n>>> Calling {func.__name__} <<<")
        result = func(*args, **kwargs)
        print(f">>> Finished {func.__name__} <<<\n")
        return result
    return wrapper

class ModelAdmin:
    """管理类
    verbose_name: 

    enable_edit: 是否可编辑

    menu_icon: bootstrap icon class

    menu_order: int 排序位置  
    """
    
    
    # 添加内联配置
    inlines: List[Type[InlineModelAdmin]] = []
    
    def __init__(self, model: Type[Model]):

        self.model = model
        self.is_inline = False  # 添加标识
        
        # 确保基本属性被设置
        self.verbose_name = getattr(self, 'verbose_name', model.__name__)
        self.enable_edit = getattr(self, 'enable_edit', True)
        self.allow_add = getattr(self, 'allow_add', True)
        self.allow_delete = getattr(self, 'allow_delete', True)
        self.allow_export = getattr(self, 'allow_export', True)
        self.per_page = getattr(self, 'per_page', 10)
        self.default_ordering = getattr(self, 'default_ordering', [])
        self.add_form_title = getattr(self, 'add_form_title', f"添加{self.verbose_name}")
        self.edit_form_title = getattr(self, 'edit_form_title', f"编辑{self.verbose_name}")
        # 初始化其他配置
        if not hasattr(self, 'table_fields'):
            self.table_fields = []
        if not hasattr(self, 'form_fields'):
            self.form_fields = []
        if not hasattr(self, 'add_form_fields'):
            self.add_form_fields = []
        if not hasattr(self, 'search_fields'):
            self.search_fields = []
        if not hasattr(self, 'filter_fields'):
            self.filter_fields = []
        
        # 如果没有设置菜单组使用默认分组
        if not hasattr(self, 'menu_group') or not self.menu_group:
            self.menu_group = "系统管理"
            
        self._process_fields()
        
        # 初始化内联管理类
        self._inline_instances = [
            inline_class(self.model) for inline_class in self.inlines
        ]
    
    def _process_fields(self):
        """处理字段配置，生成便捷属性"""
        # if not init for table_fields, auto create table_fields from model
        if not self.table_fields:
            self.table_fields = [
                TableField(name=field_name)
                for field_name in self.model._meta.fields_map.keys()
            ]
        # process table field display config
        for field in self.table_fields:
            model_field = self.model._meta.fields_map.get(field.name)
            if model_field and model_field.pk:
                field.readonly = True
                field.editable = False
            elif isinstance(model_field, fields.DatetimeField):
                field.readonly = True
                field.sortable = True
                if not field.display_type:
                    field.display_type = DisplayType.DATETIME
            # all column editable is False
            if not hasattr(field, 'editable') or field.editable is None:
                field.editable = False
        
        # create table field map
        self.table_field_map = {field.name: field for field in self.table_fields}
            
        # if not init for form_fields, create form_fields from table_fields
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
        
        # create convenient properties  
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
    
    async def get_queryset(self, request: Request, params: dict) -> QuerySet:
        """geting tortoise queryset"""
        queryset = self.model.all()
        print("queryset init is", queryset)
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
        print("final queryset", queryset)
        return queryset
        
    def get_field_label(self, field_name: str) -> str:
        for field in self.table_fields:
            if field.name == field_name and field.label:
                return field.label
        return field_name.replace('_', ' ').title()
        
    def get_list_display_links(self) -> List[str]:
        if self.list_display_links:
            return self.list_display_links
        if self.list_display:
            return [self.list_display[0]]
        return ['id']
        
    def is_field_editable(self, field_name: str) -> bool:
        for field in self.table_fields:
            if field.name == field_name:
                return field.editable and not field.readonly
        return False

    def get_filter_choices(self, field_name: str) -> List[tuple]:
        # 从 filter_fields 中获取选
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
        return await self.model.get(id=pk)
        
    def get_form_fields(self) -> List[str]:
        return [
            field.name for field in self.form_fields
            if not field.readonly and field.name != 'id'
        ]

    def get_list_fields(self) -> List[str]:
        return self.list_display or [field.name for field in self.table_fields]

    def format_field_value(self, obj: Model, field_name: str) -> str:
        field = self.get_field(field_name)
        if not field:
            return str(getattr(obj, field_name, ''))
        return field.format_value(getattr(obj, field_name, ''))

    async def serialize_object(self, obj: Model, for_display: bool = True) -> dict:
        """序列化对象"""
        result = {}
        fields_to_serialize = self.table_fields
        for field in fields_to_serialize:
            try:
                # 获取字段值
                value = getattr(obj, field.name, None)
                
                # 处理 switch 类型字段
                if field.display_type == DisplayType.SWITCH:
                    print(f"Serializing switch field {field.name}: {value}, type: {type(value)}")
                    result[field.name] = value
                    continue
                
                # 处理关联字段
                if field.related_model and field.related_key:
                    try:
                        # 获取外键值
                        fk_value = getattr(obj, field.related_key)
                        if fk_value:
                            # 查询关联对象
                            related_obj = await field.related_model.get(id=fk_value)
                            if related_obj:
                                # 从字段名中解析要显示的关联字段
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
                        result[field.name] = ''
                        continue
                
                # 处理普通字段
                if for_display and field.formatter and value is not None:
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
                
            except Exception as e:
                print(f"Error serializing field {field.name}: {str(e)}")
                result[field.name] = ''
                
        return result

    def serialize_field(self, field: TableField) -> Dict[str, Any]:
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
        return [field.name for field in self.search_fields]

    def get_ordering_fields(self) -> List[str]:
        return [field.name for field in self.table_fields if field.sortable]

    async def get_filter_fields(self) -> List[FilterField]:
        return self.filter_fields

    async def get_search_fields(self) -> list[SearchField]:
        return self.search_fields

    @trace_method
    async def get_frontend_config(self) -> dict:
        """获取前端配置"""
        form_fields = await self.get_form_fields()
        add_form_fields = await self.get_add_form_fields()
        # 异步获取过滤���段
        filter_fields = await self.get_filter_fields()
        search_fields = await self.get_search_fields()
        config = {
            "tableFields": [field.to_dict() for field in self.table_fields],
            "modelName": self.model.__name__,
            "route_id": self.route_id,
            "pageSize": self.per_page,
            "formFields": [field.to_dict() for field in form_fields],
            "addFormFields": [field.to_dict() for field in add_form_fields],
            "addFormTitle": self.add_form_title or f"添加{self.verbose_name}",
            "editFormTitle": self.edit_form_title or f"编辑{self.verbose_name}",
            "searchFields": [field.to_dict() for field in search_fields],
            "filterFields": [field.to_dict() for field in filter_fields],  # 使用异步获取的filter_fields
            "enableEdit": self.enable_edit,
            "allowAdd": self.allow_add,
            "allowDelete": self.allow_delete,
            "allowExport": self.allow_export,
            "verbose_name": self.verbose_name,
            "is_inline": self.is_inline,
            "inlines": [
                {
                    "model": inline.model.__name__,
                    "fields": [field.to_dict() for field in inline.table_fields],
                    "title": getattr(inline.model.Meta, 'description', inline.verbose_name)
                }
                for inline in getattr(self, 'inlines', [])
            ]
        }
        
        print("Frontend config:", config)  # 添加调试信息
        print("Filter fields:", config["filterFields"])  # 添加过滤字段调试信息
        return config

    async def get_inline_formsets(self, instance=None):
        """获取内联表单集配置"""
        formsets = []
        for inline in self._inline_instances:
            formset = inline.get_formset()
            if instance:
                # 获取现有数据
                queryset = await inline.get_queryset(instance)
                formset['initial_data'] = [
                    await self.serialize_object(obj, for_display=False)
                    for obj in await queryset
                ]
            formsets.append(formset)
        return formsets

    async def get_inline_data(self, parent_id: str, inline_model: str):
        """获取内联数据"""
        try:
            # 找到对应的内联实例
            inline = next((i for i in self._inline_instances if i.model.__name__ == inline_model), None)
            if not inline:
                print(f"No inline instance found for model: {inline_model}")
                return []
            # 获取父实例
            parent_instance = await self.model.get(id=parent_id)
            if not parent_instance:
                print(f"No parent instance found with id: {parent_id}")
                return []
            # 获取关联单记录
            queryset = await inline.get_queryset(parent_instance)
            data = []
            async for obj in queryset:
                try:
                    # 使用内联模型的序列化方法
                    serialized = await inline.serialize_object(obj)
                    data.append({
                        'data': serialized,
                        'display': serialized
                    })
                except Exception as e:
                    print(f"Error serializing object: {str(e)}")
                    traceback.print_exc()
                    continue
            return data
        except Exception as e:
            print(f"Error in get_inline_data: {str(e)}")
            traceback.print_exc()
            return []

    async def get_list_config(self) -> dict:
        """获取列表页面配置"""
        # 获取基础配置
        config = await self.get_frontend_config()
        
        # 只在列表页面添加内联配置
        inlines = []
        for inline in self._inline_instances:
            inline_config = inline.get_formset()
            # 从 Meta 类或模型名称获取标题
            if hasattr(inline.model, 'Meta') and hasattr(inline.model.Meta, 'description'):
                inline_config['title'] = inline.model.Meta.description
            else:
                inline_config['title'] = getattr(inline, 'verbose_name', inline.model.__name__)
            inlines.append(inline_config)
        
        config["inlines"] = inlines
        
        return config

    async def get_form_fields(self):
        """获取表单字段配置，支持动态获取"""
        if hasattr(self, 'form_fields'):
            return self.form_fields
        return []
        
    async def get_add_form_fields(self):
        """获取添加表单字段配置，支持动态获取"""
        if hasattr(self, 'add_form_fields'):
            return self.add_form_fields
        return await self.get_form_fields()

