from dataclasses import dataclass, field
from typing import Type, Optional, Any, Callable, Union
from tortoise import Model

from .fields import TableField, DisplayType

@dataclass
class RelatedField:
    """关联字段配置"""
    model: Type[Model]          # 关联的模型
    foreign_key: str           # 当前模型中的外键字段名
    display_field: str         # 要显示的关联模型字段名
    name: str = field(init=False)  # 字段名（将在 __post_init__ 中设置）
    label: Optional[str] = None
    display_type: DisplayType = DisplayType.TEXT
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
    
    def __post_init__(self):
        """初始化后处理"""
        # 使用外键字段名作为字段名
        self.name = self.foreign_key
        
        # 如果未提供标签，使用显示字段名作为标签
        if self.label is None:
            self.label = self.display_field.replace('_', ' ').title()

    async def get_related_value(self, instance: Model) -> str:
        """获取关联对象的显示值"""
        try:
            # 获取外键值
            fk_value = getattr(instance, self.foreign_key)
            if not fk_value:
                return ''
            
            # 查询关联对象
            related_obj = await self.model.get(id=fk_value)
            if not related_obj:
                return ''
            
            # 获取显示字段的值
            display_value = getattr(related_obj, self.display_field)
            return str(display_value) if display_value is not None else ''
            
        except Exception as e:
            print(f"Error getting related value: {str(e)}")
            return ''

    def to_dict(self) -> dict:
        """转换为字典，用于JSON序列化"""
        return {
            'name': self.name,
            'label': self.label,
            'display_type': self.display_type.value,
            'sortable': self.sortable,
            'foreign_key': self.foreign_key,
            'model': self.model.__name__,
            'display_field': self.display_field
        }

