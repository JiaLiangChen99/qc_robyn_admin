from datetime import datetime
from typing import Dict, Any

from setting.setting import DATABASE_URL
from model.table import US_Trademark, US_DocumentRecord

from robyn_admin.core import (
    AdminSite, ModelAdmin, MenuItem,
    TableField, SearchField, DisplayType
)
from robyn_admin.core.filters import InputFilter, SelectFilter
from robyn import Robyn


class US_TrademarkAdmin(ModelAdmin):
    verbose_name = "商标信息"
    menu_group = "商标管理"
    menu_icon = "bi bi-trademark"
    menu_order = 1

    table_fields = [
        TableField(
            name="id", label="ID", display_type=DisplayType.TEXT, editable=False, hidden=True
        ),
        TableField(
            "mark_name", label="商标名", display_type=DisplayType.TEXT, sortable=True, formatter=lambda x: str(x)
        ),
        TableField(
            "serial_number", label="序列号", display_type=DisplayType.TEXT, sortable=True, formatter=lambda x: str(x)
        ),
        TableField(
            "registration_number", label="注册号", display_type=DisplayType.TEXT, sortable=True, formatter=lambda x:  str(x) if x else None
        ),
        TableField(
            'status', label='状态', display_type=DisplayType.TEXT, sortable=True, formatter=lambda x: str(x)
        )
    ]
    search_fields = [
        SearchField(name="mark_name", label="商标名", placeholder="请输入商标名")
    ]
    filter_fields = [
        InputFilter("mark_name", label="商标名", placeholder="请输入商标名"),
        # 添加其他需要的过滤字段
    ]
    default_ordering = ["-serial_number"]
    enable_edit = True


class DocumentWithTrademarkAdmin(ModelAdmin):
    """带商标序列号的状态信息管理"""
    verbose_name = "商标状态详情"
    menu_group = "商标管理"
    menu_icon = "bi bi-trademark"
    menu_order = 2

    table_fields = [
        TableField(
            "id", 
            label="ID", 
            display_type=DisplayType.TEXT, 
            editable=False, 
            hidden=True
        ),
        TableField(
            "US_Trademark_serial_number",
            label="商标序列号",
            related_model=US_Trademark,
            related_key="trademark",
            sortable=True
        ),
        TableField(
            "US_Trademark_status",
            label="状态",
            related_model=US_Trademark,
            related_key="trademark",
            sortable=True
        ),
        TableField(
            "document_description", 
            label="文档描述", 
            display_type=DisplayType.TEXT, 
            sortable=True, 
            formatter=lambda x: str(x)
        ),
        TableField(
            "create_mail_date", 
            label="创建时间", 
            display_type=DisplayType.DATETIME, 
            sortable=True, 
            formatter=lambda x: x
        )
    ]
    
    # search_fields = [
    #     SearchField(
    #         name="trademark_id",
    #         label="商标序列号",
    #         placeholder="请输入商标序列号",
    #         related_model=US_Trademark,
    #         related_field="serial_number"
    #     )]
    # filter_fields = [
    #     InputFilter(
    #         name="trademark_id",
    #         label="商标序列号",
    #         placeholder="请输入商标序列号",
    #         related_model=US_Trademark,
    #         related_field="serial_number"
    #     )
    # ]
    default_ordering = ["-create_mail_date"]
    enable_edit = False


def register_admin_site(app: Robyn):
    admin_site = AdminSite(
        app,
        db_url=DATABASE_URL,
        modules={
            "models": ["model.table", "robyn_admin.models"]
        },
        generate_schemas=True
    )

    # 注册菜单
    admin_site.register_menu(MenuItem(
        name="商标管理",
        icon="bi bi-trademark",
        order=1
    ))

    # 注册所有模型
    admin_site.register_model(US_Trademark, US_TrademarkAdmin)
    # admin_site.register_model(US_DocumentRecord, US_DocumentAdmin)
    admin_site.register_model(US_DocumentRecord, DocumentWithTrademarkAdmin)