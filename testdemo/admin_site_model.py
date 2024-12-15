from qc_robyn_admin.core import (ModelAdmin,  TableField, DisplayType, FormField,
                                 SearchField, InputFilter, DateRangeFilter, SelectFilter
                                 )
from .table import Author, Publisher, Category, Book, BookReview, BookInventory
from typing import Dict

# 获取前一百个字符
def get_biography(self, value):
    return value[:100]

# 作者管理
class AuthorAdmin(ModelAdmin):
    # 显示名称
    verbose_name = "作者管理页面"

    # 菜单配置
    menu_group = "后台管理"    # 所属菜单组
    menu_icon = "bi bi-people" # Bootstrap 图标
    menu_order = 1            # 菜单排序

    # 功能开关
    enable_edit = True       # 允许编辑
    allow_add = True        # 允许添加
    allow_delete = True     # 允许删除
    allow_export = True     # 允许导出
    allow_import = True    # 允许导入


    # 编辑表单标题
    edit_form_title = "编辑作者表单"
    add_form_title = "添加作者表单"

    # 表格字段配置
    table_fields = [
        # need to insert pk field to
        TableField(
            name="id", label="ID", display_type=DisplayType.TEXT, editable=False, hidden=True
        ),
        TableField(
            "name", label="作者名称", display_type=DisplayType.TEXT, sortable=True, formatter=lambda x: str(x)
        ),
        TableField(
            "avatar", label="头像", display_type=DisplayType.IMAGE, 
            sortable=True, 
            formatter=lambda x:  '<img src={} width="100" height="100">'.format(x) if x else None
        ),
        TableField(
            'biography', label='简介', display_type=DisplayType.TEXT, 
            sortable=True, formatter=lambda x: str(x)
        ),
        TableField(
            'email', label='作者邮箱', display_type=DisplayType.TEXT, 
            sortable=True, formatter=lambda x: str(x)
        ),
        TableField(
            'created_at', label='创建日期', display_type=DisplayType.DATETIME, 
            sortable=True, formatter=lambda x: x.strftime("%Y-%m-%d %H:%M:%S")
        )
    ]
    
    

    # 编辑表单字段
    form_fields = [
        FormField("name", label="作者名称", required=True),
        FormField("avatar", label="头像", field_type=DisplayType.SELECT,
                  choices={"1":"1","2":"2"}),
    ]
    
    
    
    # 添加数据表单
    add_form_fields = [
        FormField("name", label="作者名称", required=True),
        FormField("avatar", label="头像", field_type=DisplayType.FILE_UPLOAD,upload_path="static/avatars", accept="image/*", max_size=1024*1024*10),
        FormField(
            'biography', label='简介', field_type=DisplayType.TEXT, 
            processor=lambda x: get_biography(x)
        )
    ]

    # 过滤器
    filter_fields = [
        InputFilter(
            "email", label="邮箱查询", 
            placeholder="请输入邮箱"
        ),
        DateRangeFilter(
            "created_at", label="创建日期"
        )
    ]

    default_ordering = ["-created_at"]

    import_fields = [
        "name",
        "email",
        "biography"
    ]


# 书本
class BookAdmin(ModelAdmin):
    # 显示名称
    verbose_name = "书籍查询页面"

    # 菜单配置
    menu_group = "后台管理"    # 所属菜单组
    menu_icon = "bi bi-people" # Bootstrap 图标
    menu_order = 2            # 菜单排序

    # 功能开关
    enable_edit = True       # 允许编辑
    allow_add = True        # 允许添加
    allow_delete = True     # 允许删除
    allow_export = True     # 允许导出
    allow_import = True    # 允许导入



    # 表格字段配置
    table_fields = [
        # need to insert pk field to
        TableField(
            name="id", label="ID", display_type=DisplayType.TEXT, editable=False, hidden=True
        ),
        TableField(
            "title", label="书名", display_type=DisplayType.TEXT, sortable=True, formatter=lambda x: str(x)
        ),
        TableField(
            "isbn", label="isbn号", display_type=DisplayType.IMAGE, 
            sortable=True, 
            formatter=lambda x:  '<a href={}>{}</a>'.format(x, x) if x else None
        ),
        TableField(
            'description', label='图书描述', display_type=DisplayType.TEXT, 
            sortable=True, formatter=lambda x: str(x)
        ),
        TableField(
            'price', label='价格', display_type=DisplayType.TEXT, 
            sortable=True, formatter=lambda x: str(x)
        ),
        TableField(
            'Publisher_name', label='出版社', display_type=DisplayType.TEXT, 
            related_model=Publisher, related_key="publisher_id"
        )
    ]
    
    default_ordering = ["-created_at"]


    async def get_status_choices(self) -> Dict[str, str]:
        """获取状态选项"""
        # 从数据库中获取所有不重复的状态值
        status_choices = await Publisher.all().values_list('name', flat=True)
        # 转换为选项字典
        return {status: status for status in status_choices if status}
    
    async def get_filter_fields(self):
        """获取过滤字段配置"""
        # 动态获取状态选项
        status_choices = await self.get_status_choices()        
        filters = [
            # 动态选项的下拉框过滤器
            SelectFilter(
                "Publisher_name", 
                label="出版社",  
                choices=status_choices,
                related_key="publisher_id",
                related_model=Publisher
            )
        ]
        return filters