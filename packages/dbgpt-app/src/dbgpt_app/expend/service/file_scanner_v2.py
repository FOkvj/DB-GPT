import hashlib
import json
import logging
import os
import shutil
from datetime import datetime
from ftplib import FTP
from pathlib import Path
from typing import Dict, Optional, List

from dbgpt import BaseComponent, SystemApp
from dbgpt.component import ComponentType
from dbgpt_app.expend.dao.data_manager import SQLiteConfig, initialize_expend_db
from dbgpt_app.expend.dao.file_scan_dao_v2 import ScanConfigDao, FileTypeDao, ProcessedFileDao, GlobalSettingDao


class FileScanner(BaseComponent):
    """文件扫描器核心类"""

    name = ComponentType.FILE_SCANNER

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 初始化 DAO
        self.scan_config_dao = ScanConfigDao()
        self.file_type_dao = FileTypeDao()
        self.processed_file_dao = ProcessedFileDao()
        self.global_setting_dao = GlobalSettingDao()

        self.setup_logging()
        self._init_default_settings()

    def init_app(self, system_app: SystemApp):
        pass

    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('file_scanner.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _init_default_settings(self):
        """初始化默认设置"""
        current_target = self.get_global_setting('target_dir')
        if not current_target:
            self.set_global_setting('target_dir', './target')

        # 初始化文件大小限制 (100MB)
        current_max_size = self.get_global_setting('max_file_size_mb')
        if not current_max_size:
            self.set_global_setting('max_file_size_mb', '100')

        # 初始化默认文件类型
        default_types = [
            ('.xlsx', 'Excel文件'),
            ('.mp3', 'mp3音频文件')
        ]

        for ext, desc in default_types:
            self.add_file_type(ext, desc)

    # ==================== 全局设置管理 ====================

    def set_global_setting(self, key: str, value: str):
        """设置全局配置"""
        try:
            self.global_setting_dao.set_setting(key, value)
        except Exception as e:
            self.logger.error(f"设置全局配置失败: {e}")

    def get_global_setting(self, key: str, default_value: str = None) -> Optional[str]:
        """获取全局配置"""
        try:
            result = self.global_setting_dao.get_setting(key)
            return result.value if result else default_value
        except Exception as e:
            self.logger.error(f"获取全局配置失败: {e}")
            return default_value

    def set_target_directory(self, target_dir: str):
        """设置目标目录"""
        self.set_global_setting('target_dir', target_dir)
        self.logger.info(f"目标目录已设置为: {target_dir}")

    def get_target_directory(self) -> str:
        """获取目标目录"""
        return self.get_global_setting('target_dir', './target')

    def set_max_file_size(self, max_size_mb: int):
        """设置文件大小限制（MB）"""
        self.set_global_setting('max_file_size_mb', str(max_size_mb))
        self.logger.info(f"文件大小限制已设置为: {max_size_mb}MB")

    def get_max_file_size(self) -> int:
        """获取文件大小限制（MB）"""
        return int(self.get_global_setting('max_file_size_mb', '100'))

    # ==================== 文件类型管理 ====================

    def add_file_type(self, extension: str, description: str = "", enabled: bool = True) -> bool:
        """添加文件类型"""
        try:
            result = self.file_type_dao.add_file_type(extension.lower(), description, enabled)
            return result is not None
        except Exception as e:
            self.logger.error(f"添加文件类型失败: {e}")
            return False

    def update_file_type(self, extension: str, description: str = None, enabled: bool = None) -> bool:
        """更新文件类型"""
        try:
            result = self.file_type_dao.update_file_type(extension.lower(), description, enabled)
            return result is not None
        except Exception as e:
            self.logger.error(f"更新文件类型失败: {e}")
            return False

    def remove_file_type(self, extension: str) -> bool:
        """删除文件类型"""
        try:
            return self.file_type_dao.remove_file_type(extension.lower())
        except Exception as e:
            self.logger.error(f"删除文件类型失败: {e}")
            return False

    def get_file_types(self, enabled_only: bool = False) -> List[Dict]:
        """获取文件类型列表"""
        try:
            if enabled_only:
                results = self.file_type_dao.get_enabled_file_types()
            else:
                results = self.file_type_dao.get_list({})

            return [result.dict() for result in results]
        except Exception as e:
            self.logger.error(f"获取文件类型列表失败: {e}")
            return []

    # ==================== 扫描配置管理 ====================

    def add_local_directory(self, name: str, directory_path: str, enabled: bool = True) -> bool:
        """添加本地目录配置"""
        config = {
            'path': directory_path,
            'recursive': True
        }
        return self._add_scan_config(name, 'local', config, enabled)

    def add_ftp_server(self, name: str, host: str, username: str, password: str,
                       port: int = 21, remote_dir: str = "/", enabled: bool = True) -> bool:
        """添加FTP服务器配置"""
        config = {
            'host': host,
            'port': port,
            'username': username,
            'password': password,
            'remote_dir': remote_dir
        }
        return self._add_scan_config(name, 'ftp', config, enabled)

    def _add_scan_config(self, name: str, config_type: str, config: Dict, enabled: bool = True) -> bool:
        """添加扫描配置"""
        try:
            result = self.scan_config_dao.upsert_config(name, config_type, json.dumps(config), enabled)
            self.logger.info(f"扫描配置已添加: {name} ({config_type})")
            return result is not None
        except Exception as e:
            self.logger.error(f"添加扫描配置失败: {e}")
            return False

    def update_scan_config(self, name: str, enabled: bool) -> bool:
        """更新扫描配置状态"""
        try:
            result = self.scan_config_dao.update_config_status(name, enabled)
            return result is not None
        except Exception as e:
            self.logger.error(f"更新扫描配置失败: {e}")
            return False

    def remove_scan_config(self, name: str) -> bool:
        """删除扫描配置"""
        try:
            result = self.scan_config_dao.remove_config(name)
            self.logger.info(f"扫描配置已删除: {name}")
            return result
        except Exception as e:
            self.logger.error(f"删除扫描配置失败: {e}")
            return False

    def get_scan_configs(self, enabled_only: bool = False) -> List[Dict]:
        """获取扫描配置列表"""
        try:
            if enabled_only:
                results = self.scan_config_dao.get_enabled_configs()
            else:
                results = self.scan_config_dao.get_list({})

            configs = []
            for result in results:
                config = result.dict()
                config['config'] = json.loads(config['config'])
                configs.append(config)
            return configs
        except Exception as e:
            self.logger.error(f"获取扫描配置列表失败: {e}")
            return []

    # ==================== 文件处理相关 ====================

    def get_file_hash(self, filepath: str) -> Optional[str]:
        """获取文件MD5哈希值"""
        hash_md5 = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            self.logger.error(f"计算文件哈希失败 {filepath}: {e}")
            return None

    def is_valid_file(self, filepath: str, file_size: int = None) -> tuple[bool, str]:
        """
        检查文件是否符合监控条件
        返回: (是否有效, 原因)
        """
        # 检查文件扩展名
        file_ext = Path(filepath).suffix.lower()
        valid_extensions = [ft['extension'] for ft in self.get_file_types(enabled_only=True)]

        if not valid_extensions:
            return False, "没有启用的文件类型"

        if file_ext not in valid_extensions:
            return False, f"文件扩展名 {file_ext} 不在允许列表中"

        # 检查文件大小
        if file_size is not None:
            max_size_mb = self.get_max_file_size()
            max_size_bytes = max_size_mb * 1024 * 1024

            if file_size > max_size_bytes:
                return False, f"文件大小 {file_size / 1024 / 1024:.2f}MB 超过限制 {max_size_mb}MB"

        return True, "文件有效"

    def is_file_processed(self, file_id: str) -> bool:
        """检查文件是否已被处理"""
        try:
            return self.processed_file_dao.is_file_processed(file_id)
        except Exception as e:
            self.logger.error(f"检查文件处理状态失败: {e}")
            return False

    def mark_file_processed(self, file_id: str, source_type: str, source_path: str,
                            file_name: str, file_size: int, file_hash: str, target_path: str):
        """标记文件为已处理"""
        try:
            self.processed_file_dao.mark_file_processed(
                file_id, source_type, source_path, file_name, file_size, file_hash, target_path
            )
        except Exception as e:
            self.logger.error(f"标记文件处理状态失败: {e}")

    # ==================== 扫描功能 ====================

    def scan_local_directory(self, config: Dict) -> List[Dict]:
        """扫描本地目录"""
        new_files = []
        directory_path = config['path']

        # 获取启用的文件扩展名列表，提前过滤
        valid_extensions = [ft['extension'] for ft in self.get_file_types(enabled_only=True)]
        if not valid_extensions:
            self.logger.warning("没有启用的文件类型，跳过扫描")
            return new_files

        self.logger.info(f"开始扫描本地目录: {directory_path}, 支持的文件类型: {valid_extensions}")

        try:
            if not os.path.exists(directory_path):
                self.logger.warning(f"本地目录不存在: {directory_path}")
                return new_files

            scanned_count = 0
            valid_count = 0

            for root, dirs, files in os.walk(directory_path):
                for file in files:
                    scanned_count += 1
                    filepath = os.path.join(root, file)

                    # 先检查扩展名，避免不必要的文件操作
                    file_ext = Path(filepath).suffix.lower()
                    if file_ext not in valid_extensions:
                        continue

                    try:
                        file_size = os.path.getsize(filepath)
                        is_valid, reason = self.is_valid_file(filepath, file_size)

                        if not is_valid:
                            self.logger.debug(f"跳过文件 {filepath}: {reason}")
                            continue

                        valid_count += 1
                        file_hash = self.get_file_hash(filepath)
                        if file_hash:
                            file_id = f"local_{filepath}_{file_hash}"

                            if not self.is_file_processed(file_id):
                                file_info = {
                                    'file_id': file_id,
                                    'source_type': 'local',
                                    'source_path': filepath,
                                    'file_name': file,
                                    'file_size': file_size,
                                    'file_hash': file_hash,
                                    'mtime': os.path.getmtime(filepath)
                                }
                                new_files.append(file_info)
                    except OSError as e:
                        self.logger.debug(f"无法访问文件 {filepath}: {e}")
                        continue

            self.logger.info(f"扫描完成: 总文件数={scanned_count}, 符合条件={valid_count}, 新文件={len(new_files)}")

        except Exception as e:
            self.logger.error(f"扫描本地目录失败 {directory_path}: {e}")

        return new_files

    def scan_ftp_directory(self, config: Dict) -> List[Dict]:
        """扫描FTP目录"""
        new_files = []
        ftp = None

        # 获取启用的文件扩展名列表，提前过滤
        valid_extensions = [ft['extension'] for ft in self.get_file_types(enabled_only=True)]
        if not valid_extensions:
            self.logger.warning("没有启用的文件类型，跳过FTP扫描")
            return new_files

        self.logger.info(f"开始扫描FTP服务器: {config['host']}, 支持的文件类型: {valid_extensions}")

        try:
            ftp = FTP()
            ftp.connect(config['host'], config.get('port', 21))
            ftp.login(config['username'], config['password'])

            if config.get('remote_dir'):
                ftp.cwd(config['remote_dir'])

            file_list = []
            ftp.retrlines('LIST', file_list.append)

            scanned_count = 0
            valid_count = 0

            for line in file_list:
                parts = line.split()
                if len(parts) >= 9 and not line.startswith('d'):
                    scanned_count += 1
                    filename = ' '.join(parts[8:])

                    # 先检查扩展名
                    file_ext = Path(filename).suffix.lower()
                    if file_ext not in valid_extensions:
                        continue

                    try:
                        file_size = int(parts[4])
                        is_valid, reason = self.is_valid_file(filename, file_size)

                        if not is_valid:
                            self.logger.debug(f"跳过FTP文件 {filename}: {reason}")
                            continue

                        valid_count += 1
                        file_time = ' '.join(parts[5:8])

                        file_id = f"ftp_{config['host']}_{filename}_{file_size}_{file_time}"

                        if not self.is_file_processed(file_id):
                            file_info = {
                                'file_id': file_id,
                                'source_type': 'ftp',
                                'source_path': f"{config['host']}{config.get('remote_dir', '/')}{filename}",
                                'file_name': filename,
                                'file_size': file_size,
                                'file_hash': '',
                                'ftp_config': config
                            }
                            new_files.append(file_info)
                    except ValueError as e:
                        self.logger.debug(f"无法解析FTP文件大小 {filename}: {e}")
                        continue

            self.logger.info(f"FTP扫描完成: 总文件数={scanned_count}, 符合条件={valid_count}, 新文件={len(new_files)}")

        except Exception as e:
            self.logger.error(f"扫描FTP目录失败 {config['host']}: {e}")
        finally:
            if ftp:
                try:
                    ftp.quit()
                except:
                    pass

        return new_files

    def process_file(self, file_info: Dict) -> bool:
        """处理单个文件"""
        target_dir = self.get_target_directory()
        os.makedirs(target_dir, exist_ok=True)

        filename = file_info['file_name']
        file_size = file_info['file_size']

        # 再次检查文件大小（防止配置在扫描过程中被修改）
        max_size_mb = self.get_max_file_size()
        max_size_bytes = max_size_mb * 1024 * 1024

        if file_size > max_size_bytes:
            self.logger.warning(
                f"跳过处理文件 {filename}: 大小 {file_size / 1024 / 1024:.2f}MB 超过限制 {max_size_mb}MB")
            return False

        target_path = os.path.join(target_dir, filename)

        # 处理文件名冲突
        if os.path.exists(target_path):
            name, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_path = os.path.join(target_dir, f"{name}_{timestamp}{ext}")

        success = False

        if file_info['source_type'] == 'local':
            success = self._copy_local_file(file_info['source_path'], target_path)
        elif file_info['source_type'] == 'ftp':
            success = self._download_ftp_file(file_info, target_path)

        if success:
            self.mark_file_processed(
                file_info['file_id'],
                file_info['source_type'],
                file_info['source_path'],
                file_info['file_name'],
                file_info['file_size'],
                file_info.get('file_hash', ''),
                target_path
            )
            self.logger.info(f"成功处理文件: {filename} ({file_size / 1024 / 1024:.2f}MB)")

        return success

    def _copy_local_file(self, source_path: str, target_path: str) -> bool:
        """复制本地文件"""
        try:
            shutil.copy2(source_path, target_path)
            self.logger.info(f"已复制本地文件: {source_path} -> {target_path}")
            return True
        except Exception as e:
            self.logger.error(f"复制本地文件失败: {e}")
            return False

    def _download_ftp_file(self, file_info: Dict, target_path: str) -> bool:
        """下载FTP文件"""
        ftp = None
        try:
            config = file_info['ftp_config']
            ftp = FTP()
            ftp.connect(config['host'], config.get('port', 21))
            ftp.login(config['username'], config['password'])

            if config.get('remote_dir'):
                ftp.cwd(config['remote_dir'])

            with open(target_path, 'wb') as f:
                ftp.retrbinary(f'RETR {file_info["file_name"]}', f.write)

            self.logger.info(f"已下载FTP文件: {file_info['file_name']} -> {target_path}")
            return True

        except Exception as e:
            self.logger.error(f"下载FTP文件失败: {e}")
            return False
        finally:
            if ftp:
                try:
                    ftp.quit()
                except:
                    pass

    # ==================== 主扫描方法 ====================

    def scan_and_sync(self) -> Dict:
        """执行完整的扫描和同步"""
        start_time = datetime.now()
        all_new_files = []

        # 获取所有启用的扫描配置
        scan_configs = self.get_scan_configs(enabled_only=True)

        for config in scan_configs:
            if config['type'] == 'local':
                new_files = self.scan_local_directory(config['config'])
                all_new_files.extend(new_files)
                self.logger.info(f"本地目录 {config['name']} 发现 {len(new_files)} 个新文件")

            elif config['type'] == 'ftp':
                new_files = self.scan_ftp_directory(config['config'])
                all_new_files.extend(new_files)
                self.logger.info(f"FTP服务器 {config['name']} 发现 {len(new_files)} 个新文件")

        # 处理新文件
        success_count = 0
        for file_info in all_new_files:
            if self.process_file(file_info):
                success_count += 1

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        result = {
            'total_new_files': len(all_new_files),
            'success_count': success_count,
            'failed_count': len(all_new_files) - success_count,
            'scan_duration': duration,
            'message': f"扫描完成: 发现{len(all_new_files)}个新文件, 成功处理{success_count}个"
        }

        self.logger.info(result['message'])
        return result

    # ==================== 查询和统计 ====================

    def get_processed_files(self, limit: int = 100) -> List[Dict]:
        """获取已处理文件列表"""
        try:
            # 使用分页查询获取最新的处理文件
            pagination_result = self.processed_file_dao.get_list_page(
                {}, page=1, page_size=limit, desc_order_column="processed_at"
            )
            return [item.dict() for item in pagination_result.items]
        except Exception as e:
            self.logger.error(f"获取已处理文件列表失败: {e}")
            return []

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        try:
            stats = {}

            # 已处理文件总数
            all_processed_files = self.processed_file_dao.get_list({})
            stats['total_processed_files'] = len(all_processed_files)

            # 按源类型统计
            source_type_stats = {}
            for file_record in all_processed_files:
                source_type = file_record.source_type
                source_type_stats[source_type] = source_type_stats.get(source_type, 0) + 1
            stats['by_source_type'] = source_type_stats

            # 配置统计
            active_scan_configs = self.scan_config_dao.get_enabled_configs()
            stats['active_scan_configs'] = len(active_scan_configs)

            active_file_types = self.file_type_dao.get_enabled_file_types()
            stats['active_file_types'] = len(active_file_types)

            return stats
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {}

    def clear_processed_files(self) -> bool:
        """清空已处理文件记录（重置状态）"""
        try:
            result = self.processed_file_dao.clear_all_processed_files()
            if result:
                self.logger.info("已清空所有已处理文件记录")
            return result
        except Exception as e:
            self.logger.error(f"清空已处理文件记录失败: {e}")
            return False


def main():
    """使用示例"""
    # 创建扫描器实例
    scanner = FileScanner()

    print("=== 配置文件扫描器 ===")

    # 设置目标目录
    scanner.set_target_directory("./downloads")

    # 设置文件大小限制为50MB
    scanner.set_max_file_size(50)

    # 添加文件类型
    scanner.add_file_type(".xlsx", "Excel文件")
    scanner.add_file_type(".csv", "CSV文件")
    scanner.add_file_type(".txt", "txt")
    scanner.add_file_type(".py", "py")

    # 添加本地目录
    # scanner.add_local_directory("测试目录1",
    #                             "/Users/dzc/Desktop/dbgpt_PR/DB-GPT/packages/dbgpt-app/src/dbgpt_app/expend/router")

    # 添加FTP服务器
    scanner.add_ftp_server("FTP服务器1", "localhost", "t10", "1234", remote_dir="/")

    print("=== 执行扫描 ===")

    # 执行扫描
    result = scanner.scan_and_sync()

    print(f"扫描结果:")
    print(f"- 发现新文件: {result['total_new_files']}")
    print(f"- 成功处理: {result['success_count']}")
    print(f"- 失败: {result['failed_count']}")
    print(f"- 耗时: {result['scan_duration']:.2f}秒")

    # 查看统计信息
    stats = scanner.get_statistics()
    print(f"\n统计信息:")
    print(f"- 总处理文件数: {stats['total_processed_files']}")
    print(f"- 活跃扫描配置: {stats['active_scan_configs']}")
    print(f"- 活跃文件类型: {stats['active_file_types']}")


if __name__ == "__main__":
    sqlite_config = SQLiteConfig(sqlite_path="test_expend.db", echo=True)
    print(f"SQLite配置: {sqlite_config.model_dump()}")
    print(f"数据库URL: {sqlite_config.get_database_url()}")
    print(f"引擎参数: {sqlite_config.get_engine_args()}")

    # 初始化数据库
    init_db = initialize_expend_db(sqlite_config)
    main()