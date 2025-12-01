import os
import shutil
from typing import Tuple

def check_legacy_data() -> bool:
    """检查是否存在旧版本数据"""
    import config
    return (
        os.path.exists(config.OLD_CONFIG_DIR) or
        os.path.exists(config.OLD_LOGS_DIR) or
        os.path.exists(os.path.join(os.path.expanduser("~"), ".heal_jimaku", "fixed_backgrounds"))
    )

def migrate_legacy_data() -> Tuple[bool, str]:
    """
    简化的数据迁移：只迁移最重要的用户配置和固定背景
    迁移完成后可以手动删除旧目录

    Returns:
        Tuple[bool, str]: (是否成功, 结果消息)
    """
    try:
        import config

        # 创建新目录结构
        if not os.path.exists(config.BASE_DIR):
            os.makedirs(config.BASE_DIR, exist_ok=True)

        if not os.path.exists(config.CONFIG_DIR):
            os.makedirs(config.CONFIG_DIR, exist_ok=True)

        if not os.path.exists(config.LOGS_DIR):
            os.makedirs(config.LOGS_DIR, exist_ok=True)

        fixed_bg_dir = os.path.join(config.BASE_DIR, "backgrounds", "fixed")
        if not os.path.exists(fixed_bg_dir):
            os.makedirs(fixed_bg_dir, exist_ok=True)

        migrated_count = 0

        # 1. 迁移配置文件（最重要的用户设置）
        old_config_file = os.path.join(config.OLD_CONFIG_DIR, "config.json")
        if os.path.exists(old_config_file) and not os.path.exists(config.CONFIG_FILE):
            shutil.copy2(old_config_file, config.CONFIG_FILE)
            migrated_count += 1

        # 2. 迁移固定背景图片（用户保存的背景）
        old_fixed_bg_dir = os.path.join(os.path.expanduser("~"), ".heal_jimaku", "fixed_backgrounds")
        if os.path.exists(old_fixed_bg_dir):
            for filename in os.listdir(old_fixed_bg_dir):
                old_file = os.path.join(old_fixed_bg_dir, filename)
                new_file = os.path.join(fixed_bg_dir, filename)
                if not os.path.exists(new_file):
                    shutil.copy2(old_file, new_file)
                    migrated_count += 1

        if migrated_count > 0:
            return True, f"成功迁移 {migrated_count} 个文件到新目录结构"
        else:
            return True, "未找到需要迁移的数据"

    except Exception as e:
        return False, f"数据迁移失败: {str(e)}"