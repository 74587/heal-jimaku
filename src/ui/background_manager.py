#!/usr/bin/env python3
"""
背景管理器 - 负责随机选择和管理背景图片
支持自动检测和用户自定义背景图片文件夹
"""

import os
import random
import glob
from typing import List, Optional
from pathlib import Path

from PyQt6.QtGui import QPixmap
from utils.file_utils import resource_path


class BackgroundManager:
    """背景图片管理器"""

    def __init__(self):
        self.default_background_folder = "background"
        self.custom_background_folder: Optional[str] = None
        self.last_background_path: Optional[str] = None

    def set_custom_background_folder(self, folder_path: str) -> bool:
        """
        设置自定义背景文件夹

        Args:
            folder_path: 自定义背景文件夹路径

        Returns:
            bool: 设置是否成功
        """
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            self.custom_background_folder = folder_path
            return True
        return False

    def clear_custom_background_folder(self):
        """清除自定义背景文件夹设置"""
        self.custom_background_folder = None

    def get_available_backgrounds(self) -> List[str]:
        """
        获取所有可用的背景图片路径

        Returns:
            List[str]: 背景图片路径列表
        """
        backgrounds = []

        # 确定要检查的文件夹
        folders_to_check = []

        if self.custom_background_folder:
            # 如果有自定义文件夹，只使用自定义文件夹
            folders_to_check.append(self.custom_background_folder)
        else:
            # 否则使用默认文件夹
            default_bg_path = resource_path(self.default_background_folder)
            if default_bg_path and os.path.exists(default_bg_path):
                folders_to_check.append(default_bg_path)

        # 最后检查单张背景图（向后兼容）
        single_bg_path = resource_path("background.png")
        if single_bg_path and os.path.exists(single_bg_path):
            backgrounds.append(single_bg_path)

        # 检查文件夹中的所有图片
        supported_extensions = ['*.png', '*.jpg', '*.jpeg', '*.bmp', '*.gif']

        for folder in folders_to_check:
            if not os.path.exists(folder):
                continue

            for ext in supported_extensions:
                pattern = os.path.join(folder, ext)
                backgrounds.extend(glob.glob(pattern))

                # 也检查大写扩展名
                pattern_upper = os.path.join(folder, ext.upper())
                backgrounds.extend(glob.glob(pattern_upper))

        # 去重并排序
        backgrounds = list(set(backgrounds))
        backgrounds.sort()

        return backgrounds

    def get_random_background(self) -> Optional[str]:
        """
        随机选择一个背景图片

        Returns:
            Optional[str]: 随机背景图片路径，如果没有找到则返回None
        """
        backgrounds = self.get_available_backgrounds()

        if not backgrounds:
            return None

        # 如果只有一张图片，直接返回
        if len(backgrounds) == 1:
            self.last_background_path = backgrounds[0]
            return backgrounds[0]

        # 随机选择，避免和上次相同
        available_for_random = [bg for bg in backgrounds if bg != self.last_background_path]

        # 如果所有图片都和上次一样（极端情况），就从全部中随机选择
        if not available_for_random:
            available_for_random = backgrounds

        selected = random.choice(available_for_random)
        self.last_background_path = selected

        return selected

    def load_random_background_pixmap(self) -> Optional[QPixmap]:
        """
        加载随机背景图片为QPixmap

        Returns:
            Optional[QPixmap]: 背景图片的QPixmap对象，如果没有找到则返回None
        """
        bg_path = self.get_random_background()

        if bg_path and os.path.exists(bg_path):
            try:
                pixmap = QPixmap(bg_path)
                if not pixmap.isNull():
                    return pixmap
                else:
                    print(f"警告: 背景图片文件损坏或格式不支持 {bg_path}")
            except Exception as e:
                print(f"警告: 无法加载背景图片 {bg_path}: {e}")
        elif bg_path:
            print(f"警告: 背景图片文件不存在 {bg_path}")

        return None

    def load_specific_background_pixmap(self, path: str) -> Optional[QPixmap]:
        """
        加载指定路径的背景图片为QPixmap

        Args:
            path: 图片文件路径

        Returns:
            Optional[QPixmap]: 背景图片的QPixmap对象，如果加载失败则返回None
        """
        if not path:
            return None

        if not os.path.exists(path):
            print(f"警告: 指定的背景图片文件不存在 {path}")
            return None

        try:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                return pixmap
            else:
                print(f"警告: 背景图片文件损坏或格式不支持 {path}")
        except Exception as e:
            print(f"警告: 无法加载指定的背景图片 {path}: {e}")

        return None

    def validate_background_folder(self, folder_path: str) -> tuple:
        """
        验证背景文件夹的有效性

        Args:
            folder_path: 文件夹路径

        Returns:
            tuple: (is_valid, error_message, image_count)
                - is_valid: 文件夹是否有效
                - error_message: 错误信息（如果无效）
                - image_count: 找到的有效图片数量
        """
        if not folder_path:
            return False, "文件夹路径为空", 0

        if not os.path.exists(folder_path):
            return False, f"文件夹不存在: {folder_path}", 0

        if not os.path.isdir(folder_path):
            return False, f"指定的路径不是文件夹: {folder_path}", 0

        # 检查文件夹中的图片文件
        supported_extensions = ['*.png', '*.jpg', '*.jpeg', '*.bmp', '*.gif']
        image_count = 0
        found_images = []

        try:
            for ext in supported_extensions:
                # 检查小写扩展名
                pattern = os.path.join(folder_path, ext)
                images = glob.glob(pattern)
                found_images.extend(images)

                # 检查大写扩展名
                pattern_upper = os.path.join(folder_path, ext.upper())
                images_upper = glob.glob(pattern_upper)
                found_images.extend(images_upper)

            # 去重
            found_images = list(set(found_images))
            image_count = len(found_images)

            if image_count == 0:
                return False, f"文件夹中没有找到支持的图片文件 (支持格式: PNG, JPG, JPEG, BMP, GIF)", 0

            # 验证图片文件是否可以正常加载
            valid_images = []
            for img_path in found_images:
                try:
                    pixmap = QPixmap(img_path)
                    if not pixmap.isNull():
                        valid_images.append(img_path)
                except Exception:
                    continue

            if len(valid_images) != image_count:
                actual_count = len(valid_images)
                if actual_count == 0:
                    return False, f"文件夹中的图片文件都无法加载", 0
                else:
                    print(f"警告: 文件夹中有 {image_count - actual_count} 个图片文件无法正常加载，实际可用 {actual_count} 个")
                    image_count = actual_count

        except Exception as e:
            return False, f"扫描文件夹时出错: {e}", 0

        return True, f"找到 {image_count} 个有效图片文件", image_count

    def get_background_count(self) -> int:
        """
        获取可用背景图片数量

        Returns:
            int: 可用背景图片数量
        """
        return len(self.get_available_backgrounds())

    def get_background_info(self) -> dict:
        """
        获取背景管理器信息

        Returns:
            dict: 包含背景管理器状态信息的字典
        """
        backgrounds = self.get_available_backgrounds()

        info = {
            'total_backgrounds': len(backgrounds),
            'custom_folder_enabled': self.custom_background_folder is not None,
            'custom_folder_path': self.custom_background_folder,
            'last_background_path': self.last_background_path,
            'available_backgrounds': backgrounds
        }

        return info