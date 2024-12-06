from tortoise import fields, models
from typing import Optional
import hashlib
import os

class AdminUser(models.Model):
    """后台管理用户模型"""
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=150, unique=True)
    password = fields.CharField(max_length=128)  # 存储哈希后的密码
    email = fields.CharField(max_length=254, null=True)
    is_active = fields.BooleanField(default=True)
    is_superuser = fields.BooleanField(default=False)
    last_login = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    
    # 添加角色关联
    roles = fields.ManyToManyField(
        'models.Role', 
        through='models.UserRole',
        related_name='users'
    )
    
    @classmethod
    def hash_password(cls, password: str) -> str:
        """对密码进行哈希"""
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return salt.hex() + key.hex()
    
    @classmethod
    def verify_password(cls, stored_password: str, provided_password: str) -> bool:
        """验证密码"""
        try:
            salt = bytes.fromhex(stored_password[:64])
            stored_key = bytes.fromhex(stored_password[64:])
            key = hashlib.pbkdf2_hmac(
                'sha256',
                provided_password.encode('utf-8'),
                salt,
                100000
            )
            return stored_key == key
        except Exception:
            return False

    @classmethod
    async def authenticate(cls, username: str, password: str) -> Optional['AdminUser']:
        """验证用户"""
        try:
            user = await cls.get(username=username)
            if user.is_active and cls.verify_password(user.password, password):
                return user
            return None
        except Exception:
            return None

    class Meta:
        table = "robyn_admin_users" 