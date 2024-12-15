from faker import Faker
from datetime import datetime, timedelta
import random
from decimal import Decimal
from .table import Author, Publisher, Category, Book, BookReview, BookInventory

fake = Faker(['zh_CN'])  # 使用中文数据

async def generate_test_data():
    # 生成作者数据
    authors = []
    for _ in range(20):
        author = await Author.create(
            name=fake.name(),
            avatar=f"/static/avatars/{fake.uuid4()}.jpg",
            biography=fake.text(max_nb_chars=500),
            email=fake.email()
        )
        authors.append(author)

    # 生成出版社数据
    publishers = []
    for _ in range(10):
        publisher = await Publisher.create(
            name=fake.company() + "出版社",
            address=fake.address(),
            website=fake.url()
        )
        publishers.append(publisher)

    # 生成分类数据
    main_categories = ["文学", "科技", "教育", "艺术", "历史", "经济", "哲学", "计算机"]
    categories = []
    
    # 创建主分类
    for cat_name in main_categories:
        category = await Category.create(name=cat_name)
        categories.append(category)
        
        # 为每个主分类创建2-3个子分类
        for _ in range(random.randint(2, 3)):
            sub_category = await Category.create(
                name=f"{cat_name}-{fake.word()}",
                parent=category
            )
            categories.append(sub_category)

    # 生成图书数据
    books = []
    for _ in range(100):
        book = await Book.create(
            title=fake.sentence(nb_words=4)[:-1],  # 去掉句号
            isbn=str(fake.random_number(digits=13, fix_len=True)),
            cover_image=f"/static/covers/{fake.uuid4()}.jpg",
            description=fake.text(max_nb_chars=200),
            content=fake.text(max_nb_chars=1000),
            price=Decimal(str(random.uniform(20.0, 199.9))).quantize(Decimal('0.00')),
            publication_date=fake.date_between(start_date='-5y', end_date='today'),
            publisher=random.choice(publishers),
            category=random.choice(categories)
        )
        
        # 为每本书添加1-3个作者
        for author in random.sample(authors, random.randint(1, 3)):
            await book.authors.add(author)
        
        books.append(book)

    # 生成图书评论数据
    for book in books:
        # 为每本书生成0-5条评论
        for _ in range(random.randint(0, 5)):
            await BookReview.create(
                book=book,
                reviewer_name=fake.name(),
                rating=random.randint(1, 5),
                review_text=fake.text(max_nb_chars=200)
            )

    # 生成图书库存数据
    for book in books:
        await BookInventory.create(
            book=book,
            quantity=random.randint(0, 100),
            location=f"{random.choice('ABCDEF')}-{random.randint(1,20)}-{random.randint(1,10)}",
            last_check_date=datetime.now() - timedelta(days=random.randint(0, 30))
        )

    print("测试数据生成完成！") 

