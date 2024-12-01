from robyn_admin.core.admin import ModelAdmin
from robyn_admin.core.fields import DisplayType
from robyn_admin.core.fields import FieldType
from robyn_admin.core.fields import TableMapping

class ProductAdmin(ModelAdmin):
    """
    Example of product administration with image and status handling.
    
    Features:
    - Image display with custom size
    - Status management with visual indicators
    - Price and stock inline editing
    - Product search and filtering
    """
    list_display = ['id', 'name', 'price', 'stock', 'status', 'image']
    list_display_links = ['name']
    search_fields = ['name', 'description']
    list_filter = ['status']
    list_editable = ['price', 'stock', 'status']
    
    field_types = {
        'image': DisplayType.IMAGE,
        'status': DisplayType.STATUS,
        'created_at': DisplayType.DATETIME
    }
    
    # 自定义图片显示尺寸
    image_width = 80
    image_height = 80
    
    def __init__(self, model):
        super().__init__(model)
        # 配置图片显示
        self.options.set_table_mapping(
            'image',
            TableMapping(
                field_type=FieldType.IMAGE,
                formatter=self.format_image
            )
        ) 