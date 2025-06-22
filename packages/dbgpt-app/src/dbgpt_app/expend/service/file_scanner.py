# import hashlib
# import json
# import logging
# import os
# import shutil
# from datetime import datetime
# from ftplib import FTP
# from pathlib import Path
# from typing import Dict, Optional, List
#
# from dbgpt import BaseComponent, SystemApp
# from dbgpt.component import ComponentType
# from dbgpt_app.expend.dao.file_scan_dao import FileScanDatabaseManager
#
#
# class FileScanner(BaseComponent):
#     """文件扫描器核心类"""
#
#     name = ComponentType.FILE_SCANNER
#
#     def __init__(self, db_path="file_scanner.db", **kwargs):
#         super().__init__(**kwargs)
#         self.db_manager = FileScanDatabaseManager(db_path)
#         self.setup_logging()
#         self._init_default_settings()
#
#     def init_app(self, system_app: SystemApp):
#         pass
#
#     def setup_logging(self):
#         """设置日志"""
#         logging.basicConfig(
#             level=logging.INFO,
#             format='%(asctime)s - %(levelname)s - %(message)s',
#             handlers=[
#                 logging.FileHandler('file_scanner.log', encoding='utf-8'),
#                 logging.StreamHandler()
#             ]
#         )
#         self.logger = logging.getLogger(__name__)
#
#     def _init_default_settings(self):
#         """初始化默认设置"""
#         current_target = self.get_global_setting('target_dir')
#         if not current_target:
#             self.set_global_setting('target_dir', './target')
#
#         # 初始化文件大小限制 (100MB)
#         current_max_size = self.get_global_setting('max_file_size_mb')
#         if not current_max_size:
#             self.set_global_setting('max_file_size_mb', '100')
#
#         # 初始化默认文件类型
#         default_types = [
#             ('.xlsx', 'Excel文件'),
#             ('.mp3', 'mp3音频文件')
#         ]
#
#         for ext, desc in default_types:
#             self.add_file_type(ext, desc)
#
#     # ==================== 全局设置管理 ====================
#
#     def set_global_setting(self, key: str, value: str):
#         """设置全局配置"""
#         with self.db_manager.get_connection() as conn:
#             conn.execute('''
#                 INSERT OR REPLACE INTO global_settings (key, value, updated_at)
#                 VALUES (?, ?, CURRENT_TIMESTAMP)
#             ''', (key, value))
#             conn.commit()
#
#     def get_global_setting(self, key: str, default_value: str = None) -> Optional[str]:
#         """获取全局配置"""
#         with self.db_manager.get_connection() as conn:
#             result = conn.execute(
#                 'SELECT value FROM global_settings WHERE key = ?', (key,)
#             ).fetchone()
#             return result['value'] if result else default_value
#
#     def set_target_directory(self, target_dir: str):
#         """设置目标目录"""
#         self.set_global_setting('target_dir', target_dir)
#         self.logger.info(f"目标目录已设置为: {target_dir}")
#
#     def get_target_directory(self) -> str:
#         """获取目标目录"""
#         return self.get_global_setting('target_dir', './target')
#
#     def set_max_file_size(self, max_size_mb: int):
#         """设置文件大小限制（MB）"""
#         self.set_global_setting('max_file_size_mb', str(max_size_mb))
#         self.logger.info(f"文件大小限制已设置为: {max_size_mb}MB")
#
#     def get_max_file_size(self) -> int:
#         """获取文件大小限制（MB）"""
#         return int(self.get_global_setting('max_file_size_mb', '100'))
#
#     # ==================== 文件类型管理 ====================
#
#     def add_file_type(self, extension: str, description: str = "", enabled: bool = True) -> bool:
#         """添加文件类型"""
#         try:
#             with self.db_manager.get_connection() as conn:
#                 conn.execute('''
#                     INSERT OR IGNORE INTO file_types (extension, description, enabled)
#                     VALUES (?, ?, ?)
#                 ''', (extension.lower(), description, int(enabled)))
#                 conn.commit()
#                 return True
#         except Exception as e:
#             self.logger.error(f"添加文件类型失败: {e}")
#             return False
#
#     def update_file_type(self, extension: str, description: str = None, enabled: bool = None) -> bool:
#         """更新文件类型"""
#         try:
#             with self.db_manager.get_connection() as conn:
#                 updates = []
#                 params = []
#
#                 if description is not None:
#                     updates.append("description = ?")
#                     params.append(description)
#
#                 if enabled is not None:
#                     updates.append("enabled = ?")
#                     params.append(int(enabled))
#
#                 if updates:
#                     updates.append("updated_at = CURRENT_TIMESTAMP")
#                     params.append(extension.lower())
#
#                     sql = f"UPDATE file_types SET {', '.join(updates)} WHERE extension = ?"
#                     conn.execute(sql, params)
#                     conn.commit()
#
#                 return True
#         except Exception as e:
#             self.logger.error(f"更新文件类型失败: {e}")
#             return False
#
#     def remove_file_type(self, extension: str) -> bool:
#         """删除文件类型"""
#         try:
#             with self.db_manager.get_connection() as conn:
#                 result = conn.execute('DELETE FROM file_types WHERE extension = ?', (extension.lower(),))
#                 conn.commit()
#                 return result.rowcount > 0
#         except Exception as e:
#             self.logger.error(f"删除文件类型失败: {e}")
#             return False
#
#     def get_file_types(self, enabled_only: bool = False) -> List[Dict]:
#         """获取文件类型列表"""
#         with self.db_manager.get_connection() as conn:
#             sql = 'SELECT * FROM file_types'
#             if enabled_only:
#                 sql += ' WHERE enabled = 1'
#             sql += ' ORDER BY extension'
#
#             results = conn.execute(sql).fetchall()
#             return [dict(row) for row in results]
#
#     # ==================== 扫描配置管理 ====================
#
#     def add_local_directory(self, name: str, directory_path: str, enabled: bool = True) -> bool:
#         """添加本地目录配置"""
#         config = {
#             'path': directory_path,
#             'recursive': True
#         }
#         return self._add_scan_config(name, 'local', config, enabled)
#
#     def add_ftp_server(self, name: str, host: str, username: str, password: str,
#                        port: int = 21, remote_dir: str = "/", enabled: bool = True) -> bool:
#         """添加FTP服务器配置"""
#         config = {
#             'host': host,
#             'port': port,
#             'username': username,
#             'password': password,
#             'remote_dir': remote_dir
#         }
#         return self._add_scan_config(name, 'ftp', config, enabled)
#
#     def _add_scan_config(self, name: str, config_type: str, config: Dict, enabled: bool = True) -> bool:
#         """添加扫描配置"""
#         try:
#             with self.db_manager.get_connection() as conn:
#                 conn.execute('''
#                     INSERT OR REPLACE INTO scan_configs (name, type, config, enabled, updated_at)
#                     VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
#                 ''', (name, config_type, json.dumps(config), int(enabled)))
#                 conn.commit()
#                 self.logger.info(f"扫描配置已添加: {name} ({config_type})")
#                 return True
#         except Exception as e:
#             self.logger.error(f"添加扫描配置失败: {e}")
#             return False
#
#     def update_scan_config(self, name: str, enabled: bool) -> bool:
#         """更新扫描配置状态"""
#         try:
#             with self.db_manager.get_connection() as conn:
#                 result = conn.execute('''
#                     UPDATE scan_configs SET enabled = ?, updated_at = CURRENT_TIMESTAMP
#                     WHERE name = ?
#                 ''', (int(enabled), name))
#                 conn.commit()
#                 return result.rowcount > 0
#         except Exception as e:
#             self.logger.error(f"更新扫描配置失败: {e}")
#             return False
#
#     def remove_scan_config(self, name: str) -> bool:
#         """删除扫描配置"""
#         try:
#             with self.db_manager.get_connection() as conn:
#                 result = conn.execute('DELETE FROM scan_configs WHERE name = ?', (name,))
#                 conn.commit()
#                 self.logger.info(f"扫描配置已删除: {name}")
#                 return result.rowcount > 0
#         except Exception as e:
#             self.logger.error(f"删除扫描配置失败: {e}")
#             return False
#
#     def get_scan_configs(self, enabled_only: bool = False) -> List[Dict]:
#         """获取扫描配置列表"""
#         with self.db_manager.get_connection() as conn:
#             sql = 'SELECT * FROM scan_configs'
#             if enabled_only:
#                 sql += ' WHERE enabled = 1'
#             sql += ' ORDER BY name'
#
#             results = conn.execute(sql).fetchall()
#             configs = []
#             for row in results:
#                 config = dict(row)
#                 config['config'] = json.loads(config['config'])
#                 configs.append(config)
#             return configs
#
#     # ==================== 文件处理相关 ====================
#
#     def get_file_hash(self, filepath: str) -> Optional[str]:
#         """获取文件MD5哈希值"""
#         hash_md5 = hashlib.md5()
#         try:
#             with open(filepath, "rb") as f:
#                 for chunk in iter(lambda: f.read(4096), b""):
#                     hash_md5.update(chunk)
#             return hash_md5.hexdigest()
#         except Exception as e:
#             self.logger.error(f"计算文件哈希失败 {filepath}: {e}")
#             return None
#
#     def is_valid_file(self, filepath: str, file_size: int = None) -> tuple[bool, str]:
#         """
#         检查文件是否符合监控条件
#         返回: (是否有效, 原因)
#         """
#         # 检查文件扩展名
#         file_ext = Path(filepath).suffix.lower()
#         valid_extensions = [ft['extension'] for ft in self.get_file_types(enabled_only=True)]
#
#         if not valid_extensions:
#             return False, "没有启用的文件类型"
#
#         if file_ext not in valid_extensions:
#             return False, f"文件扩展名 {file_ext} 不在允许列表中"
#
#         # 检查文件大小
#         if file_size is not None:
#             max_size_mb = self.get_max_file_size()
#             max_size_bytes = max_size_mb * 1024 * 1024
#
#             if file_size > max_size_bytes:
#                 return False, f"文件大小 {file_size / 1024 / 1024:.2f}MB 超过限制 {max_size_mb}MB"
#
#         return True, "文件有效"
#
#     def is_file_processed(self, file_id: str) -> bool:
#         """检查文件是否已被处理"""
#         with self.db_manager.get_connection() as conn:
#             result = conn.execute(
#                 'SELECT id FROM processed_files WHERE file_id = ?', (file_id,)
#             ).fetchone()
#             return result is not None
#
#     def mark_file_processed(self, file_id: str, source_type: str, source_path: str,
#                             file_name: str, file_size: int, file_hash: str, target_path: str):
#         """标记文件为已处理"""
#         try:
#             with self.db_manager.get_connection() as conn:
#                 conn.execute('''
#                     INSERT OR REPLACE INTO processed_files
#                     (file_id, source_type, source_path, file_name, file_size, file_hash, target_path)
#                     VALUES (?, ?, ?, ?, ?, ?, ?)
#                 ''', (file_id, source_type, source_path, file_name, file_size, file_hash, target_path))
#                 conn.commit()
#         except Exception as e:
#             self.logger.error(f"标记文件处理状态失败: {e}")
#
#     # ==================== 扫描功能 ====================
#
#     def scan_local_directory(self, config: Dict) -> List[Dict]:
#         """扫描本地目录"""
#         new_files = []
#         directory_path = config['path']
#
#         # 获取启用的文件扩展名列表，提前过滤
#         valid_extensions = [ft['extension'] for ft in self.get_file_types(enabled_only=True)]
#         if not valid_extensions:
#             self.logger.warning("没有启用的文件类型，跳过扫描")
#             return new_files
#
#         self.logger.info(f"开始扫描本地目录: {directory_path}, 支持的文件类型: {valid_extensions}")
#
#         try:
#             if not os.path.exists(directory_path):
#                 self.logger.warning(f"本地目录不存在: {directory_path}")
#                 return new_files
#
#             scanned_count = 0
#             valid_count = 0
#
#             for root, dirs, files in os.walk(directory_path):
#                 for file in files:
#                     scanned_count += 1
#                     filepath = os.path.join(root, file)
#
#                     # 先检查扩展名，避免不必要的文件操作
#                     file_ext = Path(filepath).suffix.lower()
#                     if file_ext not in valid_extensions:
#                         continue
#
#                     try:
#                         file_size = os.path.getsize(filepath)
#                         is_valid, reason = self.is_valid_file(filepath, file_size)
#
#                         if not is_valid:
#                             self.logger.debug(f"跳过文件 {filepath}: {reason}")
#                             continue
#
#                         valid_count += 1
#                         file_hash = self.get_file_hash(filepath)
#                         if file_hash:
#                             file_id = f"local_{filepath}_{file_hash}"
#
#                             if not self.is_file_processed(file_id):
#                                 file_info = {
#                                     'file_id': file_id,
#                                     'source_type': 'local',
#                                     'source_path': filepath,
#                                     'file_name': file,
#                                     'file_size': file_size,
#                                     'file_hash': file_hash,
#                                     'mtime': os.path.getmtime(filepath)
#                                 }
#                                 new_files.append(file_info)
#                     except OSError as e:
#                         self.logger.debug(f"无法访问文件 {filepath}: {e}")
#                         continue
#
#             self.logger.info(f"扫描完成: 总文件数={scanned_count}, 符合条件={valid_count}, 新文件={len(new_files)}")
#
#         except Exception as e:
#             self.logger.error(f"扫描本地目录失败 {directory_path}: {e}")
#
#         return new_files
#
#     def scan_ftp_directory(self, config: Dict) -> List[Dict]:
#         """扫描FTP目录"""
#         new_files = []
#         ftp = None
#
#         # 获取启用的文件扩展名列表，提前过滤
#         valid_extensions = [ft['extension'] for ft in self.get_file_types(enabled_only=True)]
#         if not valid_extensions:
#             self.logger.warning("没有启用的文件类型，跳过FTP扫描")
#             return new_files
#
#         self.logger.info(f"开始扫描FTP服务器: {config['host']}, 支持的文件类型: {valid_extensions}")
#
#         try:
#             ftp = FTP()
#             ftp.connect(config['host'], config.get('port', 21))
#             ftp.login(config['username'], config['password'])
#
#             if config.get('remote_dir'):
#                 ftp.cwd(config['remote_dir'])
#
#             file_list = []
#             ftp.retrlines('LIST', file_list.append)
#
#             scanned_count = 0
#             valid_count = 0
#
#             for line in file_list:
#                 parts = line.split()
#                 if len(parts) >= 9 and not line.startswith('d'):
#                     scanned_count += 1
#                     filename = ' '.join(parts[8:])
#
#                     # 先检查扩展名
#                     file_ext = Path(filename).suffix.lower()
#                     if file_ext not in valid_extensions:
#                         continue
#
#                     try:
#                         file_size = int(parts[4])
#                         is_valid, reason = self.is_valid_file(filename, file_size)
#
#                         if not is_valid:
#                             self.logger.debug(f"跳过FTP文件 {filename}: {reason}")
#                             continue
#
#                         valid_count += 1
#                         file_time = ' '.join(parts[5:8])
#
#                         file_id = f"ftp_{config['host']}_{filename}_{file_size}_{file_time}"
#
#                         if not self.is_file_processed(file_id):
#                             file_info = {
#                                 'file_id': file_id,
#                                 'source_type': 'ftp',
#                                 'source_path': f"{config['host']}{config.get('remote_dir', '/')}{filename}",
#                                 'file_name': filename,
#                                 'file_size': file_size,
#                                 'file_hash': '',
#                                 'ftp_config': config
#                             }
#                             new_files.append(file_info)
#                     except ValueError as e:
#                         self.logger.debug(f"无法解析FTP文件大小 {filename}: {e}")
#                         continue
#
#             self.logger.info(f"FTP扫描完成: 总文件数={scanned_count}, 符合条件={valid_count}, 新文件={len(new_files)}")
#
#         except Exception as e:
#             self.logger.error(f"扫描FTP目录失败 {config['host']}: {e}")
#         finally:
#             if ftp:
#                 try:
#                     ftp.quit()
#                 except:
#                     pass
#
#         return new_files
#
#     def process_file(self, file_info: Dict) -> bool:
#         """处理单个文件"""
#         target_dir = self.get_target_directory()
#         os.makedirs(target_dir, exist_ok=True)
#
#         filename = file_info['file_name']
#         file_size = file_info['file_size']
#
#         # 再次检查文件大小（防止配置在扫描过程中被修改）
#         max_size_mb = self.get_max_file_size()
#         max_size_bytes = max_size_mb * 1024 * 1024
#
#         if file_size > max_size_bytes:
#             self.logger.warning(
#                 f"跳过处理文件 {filename}: 大小 {file_size / 1024 / 1024:.2f}MB 超过限制 {max_size_mb}MB")
#             return False
#
#         target_path = os.path.join(target_dir, filename)
#
#         # 处理文件名冲突
#         if os.path.exists(target_path):
#             name, ext = os.path.splitext(filename)
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#             target_path = os.path.join(target_dir, f"{name}_{timestamp}{ext}")
#
#         success = False
#
#         if file_info['source_type'] == 'local':
#             success = self._copy_local_file(file_info['source_path'], target_path)
#         elif file_info['source_type'] == 'ftp':
#             success = self._download_ftp_file(file_info, target_path)
#
#         if success:
#             self.mark_file_processed(
#                 file_info['file_id'],
#                 file_info['source_type'],
#                 file_info['source_path'],
#                 file_info['file_name'],
#                 file_info['file_size'],
#                 file_info.get('file_hash', ''),
#                 target_path
#             )
#             self.logger.info(f"成功处理文件: {filename} ({file_size / 1024 / 1024:.2f}MB)")
#
#         return success
#
#     def _copy_local_file(self, source_path: str, target_path: str) -> bool:
#         """复制本地文件"""
#         try:
#             shutil.copy2(source_path, target_path)
#             self.logger.info(f"已复制本地文件: {source_path} -> {target_path}")
#             return True
#         except Exception as e:
#             self.logger.error(f"复制本地文件失败: {e}")
#             return False
#
#     def _download_ftp_file(self, file_info: Dict, target_path: str) -> bool:
#         """下载FTP文件"""
#         ftp = None
#         try:
#             config = file_info['ftp_config']
#             ftp = FTP()
#             ftp.connect(config['host'], config.get('port', 21))
#             ftp.login(config['username'], config['password'])
#
#             if config.get('remote_dir'):
#                 ftp.cwd(config['remote_dir'])
#
#             with open(target_path, 'wb') as f:
#                 ftp.retrbinary(f'RETR {file_info["file_name"]}', f.write)
#
#             self.logger.info(f"已下载FTP文件: {file_info['file_name']} -> {target_path}")
#             return True
#
#         except Exception as e:
#             self.logger.error(f"下载FTP文件失败: {e}")
#             return False
#         finally:
#             if ftp:
#                 try:
#                     ftp.quit()
#                 except:
#                     pass
#
#     # ==================== 主扫描方法 ====================
#
#     def scan_and_sync(self) -> Dict:
#         """执行完整的扫描和同步"""
#         start_time = datetime.now()
#         all_new_files = []
#
#         # 获取所有启用的扫描配置
#         scan_configs = self.get_scan_configs(enabled_only=True)
#
#         for config in scan_configs:
#             if config['type'] == 'local':
#                 new_files = self.scan_local_directory(config['config'])
#                 all_new_files.extend(new_files)
#                 self.logger.info(f"本地目录 {config['name']} 发现 {len(new_files)} 个新文件")
#
#             elif config['type'] == 'ftp':
#                 new_files = self.scan_ftp_directory(config['config'])
#                 all_new_files.extend(new_files)
#                 self.logger.info(f"FTP服务器 {config['name']} 发现 {len(new_files)} 个新文件")
#
#         # 处理新文件
#         success_count = 0
#         for file_info in all_new_files:
#             if self.process_file(file_info):
#                 success_count += 1
#
#         end_time = datetime.now()
#         duration = (end_time - start_time).total_seconds()
#
#         result = {
#             'total_new_files': len(all_new_files),
#             'success_count': success_count,
#             'failed_count': len(all_new_files) - success_count,
#             'scan_duration': duration,
#             'message': f"扫描完成: 发现{len(all_new_files)}个新文件, 成功处理{success_count}个"
#         }
#
#         self.logger.info(result['message'])
#         return result
#
#     # ==================== 查询和统计 ====================
#
#     def get_processed_files(self, limit: int = 100) -> List[Dict]:
#         """获取已处理文件列表"""
#         with self.db_manager.get_connection() as conn:
#             results = conn.execute('''
#                 SELECT * FROM processed_files
#                 ORDER BY processed_at DESC
#                 LIMIT ?
#             ''', (limit,)).fetchall()
#             return [dict(row) for row in results]
#
#     def get_statistics(self) -> Dict:
#         """获取统计信息"""
#         with self.db_manager.get_connection() as conn:
#             stats = {}
#
#             # 已处理文件总数
#             result = conn.execute('SELECT COUNT(*) as count FROM processed_files').fetchone()
#             stats['total_processed_files'] = result['count']
#
#             # 按源类型统计
#             results = conn.execute('''
#                 SELECT source_type, COUNT(*) as count
#                 FROM processed_files
#                 GROUP BY source_type
#             ''').fetchall()
#             stats['by_source_type'] = {row['source_type']: row['count'] for row in results}
#
#             # 配置统计
#             result = conn.execute('SELECT COUNT(*) as count FROM scan_configs WHERE enabled = 1').fetchone()
#             stats['active_scan_configs'] = result['count']
#
#             result = conn.execute('SELECT COUNT(*) as count FROM file_types WHERE enabled = 1').fetchone()
#             stats['active_file_types'] = result['count']
#
#             return stats
#
#     def clear_processed_files(self) -> bool:
#         """清空已处理文件记录（重置状态）"""
#         try:
#             with self.db_manager.get_connection() as conn:
#                 conn.execute('DELETE FROM processed_files')
#                 conn.commit()
#                 self.logger.info("已清空所有已处理文件记录")
#                 return True
#         except Exception as e:
#             self.logger.error(f"清空已处理文件记录失败: {e}")
#             return False
#
#
# def main():
#     """使用示例"""
#     # 创建扫描器实例
#     scanner = FileScanner("file_scanner.db")
#
#     print("=== 配置文件扫描器 ===")
#
#     # 设置目标目录
#     scanner.set_target_directory("./downloads")
#
#     # 设置文件大小限制为50MB
#     scanner.set_max_file_size(50)
#
#     # 添加文件类型
#     scanner.add_file_type(".xlsx", "Excel文件")
#     scanner.add_file_type(".csv", "CSV文件")
#     scanner.add_file_type(".txt", "txt")
#     scanner.add_file_type(".java", "java")
#
#     # 添加本地目录
#     scanner.add_local_directory("测试目录1",
#                                 "/Users/dzc/Desktop/dbgpt_PR/DB-GPT/packages/dbgpt-app/src/dbgpt_app/expend/router")
#
#     # 添加FTP服务器
#     scanner.add_ftp_server("FTP服务器1", "localhost", "t10", "1234", remote_dir="/")
#
#     print("=== 执行扫描 ===")
#
#     # 执行扫描
#     result = scanner.scan_and_sync()
#
#     print(f"扫描结果:")
#     print(f"- 发现新文件: {result['total_new_files']}")
#     print(f"- 成功处理: {result['success_count']}")
#     print(f"- 失败: {result['failed_count']}")
#     print(f"- 耗时: {result['scan_duration']:.2f}秒")
#
#     # 查看统计信息
#     stats = scanner.get_statistics()
#     print(f"\n统计信息:")
#     print(f"- 总处理文件数: {stats['total_processed_files']}")
#     print(f"- 活跃扫描配置: {stats['active_scan_configs']}")
#     print(f"- 活跃文件类型: {stats['active_file_types']}")
#
#
# if __name__ == "__main__":
#     main()
