from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class MenuItem:
    """菜单项配置"""
    name: str                    # 菜单名称
    icon: str = ""              # 图标类名 (Bootstrap Icons)
    parent: Optional[str] = None # 父菜单名称
    order: int = 0              # 排序值

class MenuManager:
    """菜单管理器"""
    def __init__(self):
        self.menus: Dict[str, MenuItem] = {}
        
    def register_menu(self, menu_item: MenuItem):
        """注册菜单项"""
        self.menus[menu_item.name] = menu_item
        
    def get_menu_tree(self) -> Dict[str, Dict]:
        """获取菜单树结构"""
        menu_tree = {}
        # 先添加父菜单
        for menu in sorted(self.menus.values(), key=lambda x: x.order):
            if not menu.parent:
                menu_tree[menu.name] = {
                    'item': menu,
                    'children': {}
                }
                
        # 再添加子菜单
        for menu in self.menus.values():
            if menu.parent and menu.parent in menu_tree:
                menu_tree[menu.parent]['children'][menu.name] = {
                    'item': menu,
                    'children': {}
                }
                
        return menu_tree 