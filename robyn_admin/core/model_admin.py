from typing import Type, Optional, List, Dict, Any
from tortoise.models import Model
from tortoise import fields
from dataclasses import dataclass
import asyncio

from .fields import TableField, FormField, SearchField, FilterField, DisplayType
from .filters import FilterType

class ModelAdmin:
    """模型管理类"""
    # 表格相关配置
    table_fields: List[TableField] = []
    enable_edit: bool = True
    per_page: int = 10
    default_ordering: List[str] = []
    
    # 表单相关配置
    form_fields: List[FormField] = []
    add_form_fields: List[FormField] = []
    add_form_title: Optional[str] = None
    edit_form_title: Optional[str] = None
    
    # 搜索和过滤配置
    search_fields: List[SearchField] = []
    filter_fields: List[FilterField] = []
    
    # 模型显示名称
    verbose_name: str = ""
    
    # 菜单配置
    menu_group: str = ""
    menu_icon: str = ""
    menu_order: int = 0
    
    def __init__(self, model: Type[Model]):
        self.model = model
        if not self.verbose_name:
            self.verbose_name = model.__name__
        
        # 添加关联模型映射
        self.related_models = {}
        self._collect_related_models()
        
        self._process_fields()
        
        if not self.menu_group:
            self.menu_group = "系统管理"
    
    def _collect_related_models(self):
        """收集所有关联模型信息"""
        for field in self.table_fields:
            if field.related_model and field.related_key:
                model_name = field.related_model.__name__
                if model_name not in self.related_models:
                    self.related_models[model_name] = {
                        'model': field.related_model,
                        'fields': {}
                    }
                # 记录字段映射
                if field.name.startswith(f"{model_name}_"):
                    actual_field = field.name[len(model_name) + 1:]
                    self.related_models[model_name]['fields'][field.name] = {
                        'actual_field': actual_field,
                        'related_key': field.related_key
                    }
    
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
                    
            # 默认所有字段都不可编辑，除非明确指定
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
                            continue
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
                            continue
                        queryset = queryset.filter(**query_dict)
                except Exception as e:
                    print(f"Error building filter query for {filter_field.name}: {str(e)}")
                    continue
        
        # 处理排序
        sort = params.get('sort', '')
        order = params.get('order', 'asc')
        if sort:
            # 检查是否是关联字段
            for model_name, model_info in self.related_models.items():
                if sort.startswith(f"{model_name}_"):
                    field_info = model_info['fields'].get(sort)
                    if field_info:
                        try:
                            # 构建关联查询
                            queryset = queryset.select_related(field_info['related_key']).order_by(
                                f"{'-' if order == 'desc' else ''}{field_info['related_key']}__{field_info['actual_field']}"
                            )
                            break
                        except Exception as e:
                            print(f"Error in related field sorting: {str(e)}")
                            print(f"Related model: {model_name}, Field info: {field_info}")
                            continue
            else:
                # 如果不是关联字段，使用普通排序
                order_by = f"{'-' if order == 'desc' else ''}{sort}"
                queryset = queryset.order_by(order_by)
        elif self.default_ordering:
            queryset = queryset.order_by(*self.default_ordering)
        
        return queryset

    async def get_object(self, pk):
        """获取单个对象"""
        return await self.model.get(id=pk)

    async def serialize_object(self, obj: Model, for_display: bool = True) -> dict:
        """序列化对象"""
        result = {}
        result['id'] = str(getattr(obj, 'id', ''))
        
        for field in self.table_fields:
            try:
                if field.related_model and field.related_key:
                    model_name = field.related_model.__name__
                    model_info = self.related_models.get(model_name)
                    if model_info and field.name in model_info['fields']:
                        try:
                            # 获取关联对象
                            related_obj = await getattr(obj, model_info['fields'][field.name]['related_key'])
                            if related_obj:
                                actual_field = model_info['fields'][field.name]['actual_field']
                                related_value = getattr(related_obj, actual_field)
                                result[field.name] = str(related_value) if related_value is not None else ''
                            else:
                                result[field.name] = ''
                        except Exception as e:
                            print(f"Error getting related object for field {field.name}: {str(e)}")
                            result[field.name] = ''
                else:
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