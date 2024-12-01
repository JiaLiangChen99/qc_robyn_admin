from enum import Enum
from typing import Any, Optional, Union, Callable, List, Dict
from dataclasses import dataclass

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
    name: str
    label: Optional[str] = None
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
    hidden: bool = False  # 是否在表格中隐藏
    
    def __post_init__(self):
        if self.label is None:
            self.label = self.name.replace('_', ' ').title()
            
    def format_value(self, value: Any) -> str:
        """格式化值用于显示
        
        按以下优先级处理值：
        1. 如果设置了formatter，使用formatter处理
        2. 直接返回原始值的字符串表示
        """
        if value is None:
            return ''
        if self.formatter:
            return self.formatter(value)
        return str(value)
    
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
    placeholder: str = ""  # 修改为空字符串默认值
    operator: str = 'icontains'  # 搜索操作符
    
    def __post_init__(self):
        if self.label is None:
            self.label = self.name.replace('_', ' ').title()
        if not self.placeholder:
            self.placeholder = f"输入{self.label}搜索"
            
    def to_dict(self) -> dict:
        """转换为字典，用于JSON序列化"""
        return {
            'name': self.name,
            'label': self.label,
            'placeholder': self.placeholder,
            'operator': self.operator
        }
    
@dataclass
class FilterField:
    """过滤字段配置"""
    name: str
    label: Optional[str] = None
    choices: Optional[Dict[Any, str]] = None
    multiple: bool = False
    placeholder: Optional[str] = None
    
    def __post_init__(self):
        if self.label is None:
            self.label = self.name.replace('_', ' ').title()
    
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