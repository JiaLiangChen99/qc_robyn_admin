from typing import Dict, Any, Optional
from .fields import TableMapping, FormMapping, FilterMapping, FieldType

class ModelAdminOptions:
    """ModelAdmin配置选项"""
    def __init__(self):
        self.table_mappings: Dict[str, TableMapping] = {}
        self.form_mappings: Dict[str, FormMapping] = {}
        self.filter_mappings: Dict[str, FilterMapping] = {}
        
    def set_table_mapping(self, field_name: str, mapping: TableMapping):
        """设置表格映射"""
        self.table_mappings[field_name] = mapping
        
    def set_form_mapping(self, field_name: str, mapping: FormMapping):
        """设置表单映射"""
        self.form_mappings[field_name] = mapping
        
    def set_filter_mapping(self, field_name: str, mapping: FilterMapping):
        """设置过滤器映射"""
        self.filter_mappings[field_name] = mapping 