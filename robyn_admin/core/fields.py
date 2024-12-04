from enum import Enum
from typing import Any, Optional, Union, Callable, List, Dict, Type
from dataclasses import dataclass
from tortoise import Model
import asyncio
from .filters import FilterType

class DisplayType(Enum):
    """显示类型枚举"""
    TEXT = 'text'
    DATE = 'date'
    DATETIME = 'datetime'
    IMAGE = 'image'
    PICTURE_UPLOAD = 'picture_upload'
    FILE_UPLOAD = 'file_upload'
    DRAGGER_UPLOAD = 'dragger_upload'
    STATUS = 'status'
    BOOLEAN = 'boolean'
    LINK = 'link'
    HTML = 'html'
    CUSTOM = 'custom'
    PASSWORD = 'password'
    EMAIL = 'email'
    SELECT = 'select'
    
@dataclass
class TableField:
    """表格字段配置"""
    name: str                    # 字段名称
    label: Optional[str] = None  # 显示标签
    display_type: Optional[DisplayType] = None
    sortable: bool = False
    searchable: bool = False
    filterable: bool = False
    editable: bool = False
    readonly: bool = False
    visible: bool = True
    is_link: bool = False
    width: Optional[Union[int, str]] = None
    formatter: Optional[Callable] = None
    hidden: bool = False
    
    # 关联字段配置
    related_model: Optional[Type[Model]] = None  # 关联的模型
    related_key: Optional[str] = None           # 关联的外键字段
    
    def __post_init__(self):
        if self.label is None:
            self.label = self.name.replace('_', ' ').title()
            
        # 处理关联字段名称
        if self.related_model and self.related_key:
            # 从字段名中解析要显示的关联字段
            parts = self.name.split('_')
            if len(parts) > 1:
                self.related_field = parts[-1]  # 使用最后一部分作为关联字段名
                self.display_name = self.name   # 保持原始名称作为显示名
            else:
                self.related_field = 'id'  # 默认使用 id
                self.display_name = self.name
        else:
            self.display_name = self.name
            
    async def format_value(self, value: Any, instance: Optional[Model] = None) -> str:
        """格式化值用于显示"""
        if value is None:
            return ''
            
        # 如果是关联字段
        if self.related_model and self.related_key and instance:
            try:
                # 获取外键值
                fk_value = getattr(instance, self.related_key)
                if not fk_value:
                    return ''
                    
                # 查询关联对象
                related_obj = await self.related_model.get(id=fk_value)
                if related_obj:
                    # 获取关联字段的值
                    related_value = getattr(related_obj, self.related_field)
                    return str(related_value) if related_value is not None else ''
                return ''
            except Exception as e:
                print(f"Error getting related value: {str(e)}")
                return ''
                
        # 使用自定义格式化函数
        if self.formatter:
            try:
                if asyncio.iscoroutinefunction(self.formatter):
                    return await self.formatter(value)
                return self.formatter(value)
            except Exception as e:
                print(f"Error formatting value: {str(e)}")
                return str(value)
                
        return str(value)
    
    def to_dict(self) -> dict:
        """转换为字典，用于JSON序列化"""
        data = {
            'name': self.display_name,
            'label': self.label,
            'display_type': self.display_type.value if self.display_type else 'text',
            'sortable': self.sortable,
            'searchable': self.searchable,
            'filterable': self.filterable,
            'editable': self.editable,
            'readonly': self.readonly,
            'visible': self.visible,
            'is_link': self.is_link,
            'width': self.width,
            'hidden': self.hidden,
            'has_formatter': bool(self.formatter)
        }
        
        if self.related_model and self.related_key:
            data.update({
                'related_model': self.related_model.__name__,
                'related_key': self.related_key,
                'related_field': self.related_field
            })
            
        return data
    
@dataclass
class FormField:
    """表单字段配置"""
    name: str
    label: Optional[str] = None
    field_type: Optional[DisplayType] = None
    required: bool = False
    readonly: bool = False
    help_text: Optional[str] = None
    placeholder: Optional[str] = None
    validators: List[Callable] = None
    choices: Optional[Dict[Any, str]] = None
    default: Any = None
    processor: Optional[Callable] = None  # 添加数据处理函数
    upload_path: Optional[str] = None  # 静态资源存储路径
    accept: Optional[str] = None  # 接受的文件类型
    max_size: Optional[int] = None  # 最大文件大小（字节）
    multiple: bool = False  # 是否支持多文件上传
    preview: bool = True  # 是否显示预览
    drag_text: Optional[str] = None  # 拖拽区域提示文本
    
    def __post_init__(self):
        if self.label is None:
            self.label = self.name.replace('_', ' ').title()
        self.validators = self.validators or []
    
    def process_value(self, value: Any) -> Any:
        """处理字段值"""
        if self.processor:
            return self.processor(value)
        return value
    
    def to_dict(self) -> dict:
        """转换为字典，用于JSON序列化"""
        return {
            'name': self.name,
            'label': self.label,
            'field_type': self.field_type.value if self.field_type else None,
            'required': self.required,
            'readonly': self.readonly,
            'help_text': self.help_text,
            'placeholder': self.placeholder,
            'choices': self.choices,
            'default': self.default,
            'upload_path': self.upload_path,
            'accept': self.accept,
            'max_size': self.max_size,
            'multiple': self.multiple,
            'preview': self.preview,
            'drag_text': self.drag_text
        }
    
@dataclass
class SearchField:
    """搜索字段配置"""
    name: str
    label: Optional[str] = None
    placeholder: str = ""
    operator: str = 'icontains'  # 搜索操作符
    
    # 添加关联字段支持
    related_model: Optional[Type[Model]] = None  # 关联的模型
    related_field: Optional[str] = None         # 要搜索的关联模型字段
    
    def __post_init__(self):
        if self.label is None:
            self.label = self.name.replace('_', ' ').title()
        if not self.placeholder:
            self.placeholder = f"输入{self.label}搜索"
            
    def to_dict(self) -> dict:
        """转换为字典，用于JSON序列化"""
        data = {
            'name': self.name,
            'label': self.label,
            'placeholder': self.placeholder,
            'operator': self.operator
        }
        
        if self.related_model and self.related_field:
            data.update({
                'related_model': self.related_model.__name__,
                'related_field': self.related_field
            })
            
        return data

    async def build_search_query(self, search_value: str) -> dict:
        """构建搜索查询条件"""
        if not search_value:
            return {}
            
        if self.related_model and self.related_field:
            # 先查询关联模型
            try:
                related_objects = await self.related_model.filter(
                    **{f"{self.related_field}__{self.operator}": search_value}
                )
                if not related_objects:
                    return {"id": None}  # 确保没有匹配结果
                    
                # 获取所有匹配的ID
                related_ids = [str(obj.id) for obj in related_objects]
                return {f"{self.name}__in": related_ids}
                
            except Exception as e:
                print(f"Error in related search: {str(e)}")
                return {"id": None}
        else:
            # 直接搜索当前字段
            return {f"{self.name}__{self.operator}": search_value}
    
@dataclass
class FilterField:
    """过滤字段配置"""
    name: str
    label: Optional[str] = None
    filter_type: FilterType = FilterType.INPUT  # 添加默认过滤器类型
    choices: Optional[Dict[Any, str]] = None
    multiple: bool = False
    placeholder: Optional[str] = None
    operator: str = 'icontains'  # 添加操作符
    
    # 添加关联字段支持
    related_model: Optional[Type[Model]] = None  # 关联的模型
    related_field: Optional[str] = None         # 要过滤的关联模型字段
    
    def __post_init__(self):
        if self.label is None:
            self.label = self.name.replace('_', ' ').title()
            
    def to_dict(self) -> dict:
        """转换为字典，用于JSON序列化"""
        data = {
            'name': self.name,
            'label': self.label,
            'type': self.filter_type.value,
            'choices': self.choices,
            'placeholder': self.placeholder,
            'multiple': self.multiple,
            'operator': self.operator
        }
        
        if self.related_model and self.related_field:
            data.update({
                'related_model': self.related_model.__name__,
                'related_field': self.related_field
            })
            
        return data

    async def build_filter_query(self, filter_value: str) -> dict:
        """构建过滤查询条件"""
        if not filter_value:
            return {}
            
        if self.related_model and self.related_field:
            # 先查询关联模型
            try:
                related_objects = await self.related_model.filter(
                    **{f"{self.related_field}__{self.operator}": filter_value}
                )
                if not related_objects:
                    return {"id": None}  # 确保没有匹配结果
                    
                # 获取所有匹配的ID
                related_ids = [str(obj.id) for obj in related_objects]
                return {f"{self.name}__in": related_ids}
                
            except Exception as e:
                print(f"Error in related filter: {str(e)}")
                return {"id": None}
        else:
            # 直接过滤当前字段
            return {f"{self.name}__{self.operator}": filter_value}
    
@dataclass
class Action:
    """操作按钮配置"""
    name: str
    label: str
    type: str = 'primary'  # 按钮类型：primary/secondary/success/danger/warning
    icon: Optional[str] = None  # 图标类名
    confirm: Optional[str] = None  # 确认提示文本
    permissions: List[str] = None  # 所需权限
    
    def __post_init__(self):
        self.permissions = self.permissions or []
    
@dataclass
class RowAction:
    """行操作配置"""
    name: str  # 操作名称
    label: str  # 显示文本
    type: str = 'primary'  # 按钮类型：primary/secondary/success/danger/warning
    icon: Optional[str] = None  # 图标类名
    confirm: Optional[str] = None  # 确认提示文本
    enabled: bool = True  # 是否启用
    permissions: List[str] = None  # 所需权限
    
    def __post_init__(self):
        self.permissions = self.permissions or []
        
    def to_dict(self) -> dict:
        """转换为字典，用于JSON序列化"""
        return {
            'name': self.name,
            'label': self.label,
            'type': self.type,
            'icon': self.icon,
            'confirm': self.confirm,
            'enabled': self.enabled,
            'permissions': self.permissions
        }