from enum import Enum
from typing import Any, Optional, Dict, List, Callable
from dataclasses import dataclass
from datetime import datetime

class FilterType(Enum):
    """过滤器类型"""
    INPUT = 'input'         # 输入框
    SELECT = 'select'       # 下拉选择框
    DATE_RANGE = 'date'     # 日期范围
    NUMBER_RANGE = 'number' # 数字范围
    BOOLEAN = 'boolean'     # 布尔选择

@dataclass
class FilterField:
    """过滤字段基类"""
    name: str              # 字段名
    label: str            # 显示标签
    filter_type: FilterType  # 过滤器类型
    placeholder: Optional[str] = None  # 占位文本
    default_value: Any = None  # 默认值
    width: Optional[str] = None  # 宽度
    dependent_field: Optional[str] = None  # 依赖字段
    choices_loader: Optional[Callable] = None  # 动态选项加载器
    operator: str = 'icontains'  # 过滤操作符

    def to_dict(self) -> dict:
        """转换为字典，用于前端渲染"""
        return {
            'name': self.name,
            'label': self.label,
            'type': self.filter_type.value,
            'placeholder': self.placeholder,
            'default_value': self.default_value,
            'width': self.width,
            'choices': getattr(self, 'choices', None),
            'dependent_field': self.dependent_field,
            'min_value': getattr(self, 'min_value', None),
            'max_value': getattr(self, 'max_value', None),
            'operator': self.operator
        }

@dataclass
class InputFilter(FilterField):
    """输入框过滤器"""
    def __init__(
        self, 
        name: str, 
        label: str, 
        operator: str = 'icontains',  # 默认使用包含匹配
        **kwargs
    ):
        super().__init__(
            name=name,
            label=label,
            filter_type=FilterType.INPUT,
            operator=operator,
            **kwargs
        )

@dataclass
class SelectFilter(FilterField):
    """下拉选择过滤器"""
    choices: Optional[Dict[str, Any]] = None  # 静态选项

    def __init__(self, name: str, label: str, choices=None, **kwargs):
        super().__init__(
            name=name,
            label=label,
            filter_type=FilterType.SELECT,
            **kwargs
        )
        self.choices = choices

@dataclass
class DateRangeFilter(FilterField):
    """日期范围过滤器"""
    def __init__(self, name: str, label: str, **kwargs):
        super().__init__(
            name=name,
            label=label,
            filter_type=FilterType.DATE_RANGE,
            **kwargs
        )

@dataclass
class NumberRangeFilter(FilterField):
    """数字范围过滤器"""
    min_value: Optional[float] = None
    max_value: Optional[float] = None

    def __init__(self, name: str, label: str, **kwargs):
        super().__init__(
            name=name,
            label=label,
            filter_type=FilterType.NUMBER_RANGE,
            **kwargs
        )

@dataclass
class BooleanFilter(FilterField):
    """布尔过滤器"""
    def __init__(self, name: str, label: str, **kwargs):
        super().__init__(
            name=name,
            label=label,
            filter_type=FilterType.BOOLEAN,
            choices={'是': True, '否': False},
            **kwargs
        )