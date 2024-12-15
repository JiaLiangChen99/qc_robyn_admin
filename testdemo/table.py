from tortoise import fields, models

class Author(models.Model):
    """作者模型"""
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, description="作者姓名")
    avatar = fields.CharField(max_length=255, null=True, description="作者头像路径")
    biography = fields.TextField(null=True, description="作者简介")
    email = fields.CharField(max_length=100, null=True, description="作者邮箱")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "authors"

class Publisher(models.Model):
    """出版社模型"""
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, description="出版社名称")
    address = fields.CharField(max_length=255, null=True, description="出版社地址")
    website = fields.CharField(max_length=255, null=True, description="出版社网站")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "publishers"

class Category(models.Model):
    """图书分类模型"""
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, description="分类名称")
    parent = fields.ForeignKeyField(
        'models.Category', 
        related_name='children', 
        null=True, 
        description="父分类"
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "categories"

class Book(models.Model):
    """图书模型"""
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=200, description="书名")
    isbn = fields.CharField(max_length=13, unique=True, description="ISBN号")
    cover_image = fields.CharField(max_length=255, null=True, description="封面图片路径")
    description = fields.TextField(description="图书描述", null=True)
    content = fields.TextField(description="图书内容摘要", null=True)
    price = fields.DecimalField(max_digits=10, decimal_places=2, description="价格")
    publication_date = fields.DateField(description="出版日期")
    
    # 关联字段
    publisher = fields.ForeignKeyField(
        'models.Publisher', 
        related_name='books',
        description="出版社"
    )
    authors = fields.ManyToManyField(
        'models.Author',
        related_name='books',
        through='book_authors',
        description="作者"
    )
    category = fields.ForeignKeyField(
        'models.Category',
        related_name='books',
        description="分类"
    )
    
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "books"

class BookReview(models.Model):
    """图书评论模型"""
    id = fields.IntField(pk=True)
    book = fields.ForeignKeyField(
        'models.Book',
        related_name='reviews',
        description="评论的图书"
    )
    reviewer_name = fields.CharField(max_length=100, description="评论者姓名")
    rating = fields.IntField(description="评分(1-5)")
    review_text = fields.TextField(description="评论内容")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "book_reviews"

class BookInventory(models.Model):
    """图书库存模型 - 与图书一对一关系"""
    id = fields.IntField(pk=True)
    book = fields.OneToOneField(
        'models.Book',
        related_name='inventory',
        description="关联的图书"
    )
    quantity = fields.IntField(description="库存数量")
    location = fields.CharField(max_length=100, description="存放位置")
    last_check_date = fields.DatetimeField(description="最新盘点日期")
    
    class Meta:
        table = "book_inventories"
