from .filters import FilterField, TextFilter, SelectFilter, DateRangeFilter, NumberRangeFilter, BooleanFilter

class OrdersAdmin(ModelAdmin):
    # ... 其他配置保持不变 ...
    
    # 添加过滤器配置
    filter_fields = [
        TextFilter(
            name="order_no",
            label="订单号",
            placeholder="请输入订单号"
        ),
        SelectFilter(
            name="status",
            label="订单状态",
            choices={
                0: "待支付",
                1: "已支付",
                2: "已发货",
                3: "已完成",
                4: "已取消"
            }
        ),
        DateRangeFilter(
            name="created_at",
            label="创建时间"
        ),
        NumberRangeFilter(
            name="total_amount",
            label="订单金额",
            min_value=0
        ),
        SelectFilter(
            name="user",
            label="用户",
            choices_loader=lambda: Users.all().values('id', 'username')
        )
    ]