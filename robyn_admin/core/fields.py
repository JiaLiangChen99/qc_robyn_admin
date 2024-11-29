from enum import Enum
from typing import Any, Dict, Optional, Union, Callable

class FieldType(Enum):
    TEXT = 'text'
    NUMBER = 'number'
    DATE = 'date'
    DATETIME = 'datetime'
    BOOLEAN = 'boolean'
    SELECT = 'select'
    RADIO = 'radio'
    IMAGE = 'image'
    RICH_TEXT = 'rich_text'
    CUSTOM = 'custom'
    STATUS = 'status'

class FieldMapping:
    """字段映射基类"""
    def __init__(
        self,
        field_type: FieldType,
        choices: Optional[Dict[Any, str]] = None,
        formatter: Optional[Callable] = None,
        display_format: Optional[str] = None,
        html_attrs: Optional[Dict[str, str]] = None
    ):
        self.field_type = field_type
        self.choices = choices or {}
        self.formatter = formatter
        self.display_format = display_format
        self.html_attrs = html_attrs or {}

    def format_value(self, value: Any) -> str:
        """格式化值"""
        if self.formatter:
            return self.formatter(value)
        if self.choices and value in self.choices:
            return self.choices[value]
        return str(value)

class TableMapping(FieldMapping):
    """表格显示映射"""
    def __init__(
        self,
        field_type: FieldType,
        choices: Optional[Dict[Any, str]] = None,
        formatter: Optional[Callable] = None,
        display_format: Optional[str] = None,
        html_attrs: Optional[Dict[str, str]] = None,
        cell_template: Optional[str] = None
    ):
        super().__init__(field_type, choices, formatter, display_format, html_attrs)
        self.cell_template = cell_template

class FormMapping(FieldMapping):
    """表单显示映射"""
    def __init__(
        self,
        field_type: FieldType,
        choices: Optional[Dict[Any, str]] = None,
        formatter: Optional[Callable] = None,
        display_format: Optional[str] = None,
        html_attrs: Optional[Dict[str, str]] = None,
        widget: Optional[str] = None,
        validators: Optional[list] = None
    ):
        super().__init__(field_type, choices, formatter, display_format, html_attrs)
        self.widget = widget
        self.validators = validators or []

class FilterMapping(FieldMapping):
    """过滤器显示映射"""
    def __init__(
        self,
        field_type: FieldType,
        choices: Optional[Dict[Any, str]] = None,
        formatter: Optional[Callable] = None,
        display_format: Optional[str] = None,
        html_attrs: Optional[Dict[str, str]] = None,
        filter_type: str = 'select'
    ):
        super().__init__(field_type, choices, formatter, display_format, html_attrs)
        self.filter_type = filter_type 