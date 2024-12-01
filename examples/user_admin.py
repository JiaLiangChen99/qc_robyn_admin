from robyn_admin.core.admin import ModelAdmin
from robyn_admin.core.fields import DisplayType

class UserAdmin(ModelAdmin):
    """用户管理示例"""
    list_display = ['id', 'username', 'email', 'is_active', 'created_at']
    list_display_links = ['username']
    search_fields = ['username', 'email']
    list_filter = ['is_active']
    
    # 字段显示名称
    field_labels = {
        'username': '用户名',
        'email': '邮箱',
        'is_active': '状态',
        'created_at': '创建时间'
    }
    
    # 字段显示类型
    field_types = {
        'is_active': DisplayType.STATUS,
        'created_at': DisplayType.DATETIME
    }
    
    # 状态显示映射
    status_choices = {
        'is_active': {
            True: '<span class="badge bg-success">激活</span>',
            False: '<span class="badge bg-danger">禁用</span>'
        }
    } 