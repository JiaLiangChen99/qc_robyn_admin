from abc import ABC, abstractmethod
from typing import Any, Dict
from ..core.fields import FieldType, FormMapping

class BaseRenderer(ABC):
    """渲染器基类"""
    
    @abstractmethod
    def render(self, value: Any, context: Dict[str, Any] = None) -> str:
        """渲染值"""
        pass

class TableRenderer(BaseRenderer):
    """表格渲染器"""
    def render(self, value: Any, context: Dict[str, Any] = None) -> str:
        mapping = context.get('mapping')
        if not mapping:
            return str(value)
        return mapping.format_value(value)

class FormRenderer(BaseRenderer):
    """表单渲染器"""
    def render(self, value: Any, context: Dict[str, Any] = None) -> str:
        mapping = context.get('mapping')
        if not mapping:
            return f'<input type="text" value="{value}">'
        # 根据不同的widget类型渲染不同的表单元素
        return self._render_widget(value, mapping)

    def _render_widget(self, value: Any, mapping: FormMapping) -> str:
        if mapping.field_type == FieldType.SELECT:
            return self._render_select(value, mapping)
        elif mapping.field_type == FieldType.RADIO:
            return self._render_radio(value, mapping)
        # ... 其他类型的渲染
        
    def _render_select(self, value: Any, mapping: FormMapping) -> str:
        """渲染下拉选择框"""
        options = []
        for choice_value, choice_label in mapping.choices.items():
            selected = 'selected' if str(value) == str(choice_value) else ''
            options.append(f'<option value="{choice_value}" {selected}>{choice_label}</option>')
        
        attrs = ' '.join([f'{k}="{v}"' for k, v in mapping.html_attrs.items()])
        return f'<select {attrs}>\n{"".join(options)}\n</select>'
        
    def _render_radio(self, value: Any, mapping: FormMapping) -> str:
        """渲染单选框组"""
        radios = []
        for choice_value, choice_label in mapping.choices.items():
            checked = 'checked' if str(value) == str(choice_value) else ''
            radio_id = f"{mapping.html_attrs.get('name', '')}_{choice_value}"
            radios.append(
                f'<div class="form-check">\n'
                f'  <input type="radio" id="{radio_id}" value="{choice_value}" {checked} '
                f'class="form-check-input" name="{mapping.html_attrs.get("name", "")}">\n'
                f'  <label class="form-check-label" for="{radio_id}">{choice_label}</label>\n'
                f'</div>'
            )
        return '\n'.join(radios)