from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Any, Optional, Dict

from dbgpt.core.schema.api import Result
from dbgpt_app.expend.dependencies import get_scanner
from dbgpt_app.expend.model.file_scan import (
    LocalDirectoryConfig, ScanConfigUpdate, FTPServerConfig,
    ScanConfigResponse, FileTypeResponse, FileTypeModel,
    GlobalSettingModel, ScanResult, StatisticsResponse,
    ProcessedFileResponse
)
from dbgpt_app.expend.service.file_scanner import FileScanner

router = APIRouter()


@router.get("/settings", summary="获取全局设置", response_model=Result[Dict[str, Any]])
async def get_settings(scanner: FileScanner = Depends(get_scanner)):
    """获取全局设置"""
    try:
        settings = {
            "target_dir": scanner.get_target_directory()
        }
        return Result.succ(settings)
    except Exception as e:
        return Result.failed(f"获取设置失败: {str(e)}", "E0010")


@router.put("/settings", summary="更新全局设置", response_model=Result[Dict[str, Any]])
async def update_settings(settings: GlobalSettingModel, scanner: FileScanner = Depends(get_scanner)):
    """更新全局设置"""
    try:
        scanner.set_target_directory(settings.target_dir)
        return Result.succ({"message": "设置已更新", "target_dir": settings.target_dir})
    except Exception as e:
        return Result.failed(f"更新设置失败: {str(e)}", "E0011")


@router.get("/file-types", summary="获取文件类型列表", response_model=Result[List[FileTypeResponse]])
async def get_file_types(enabled_only: bool = False, scanner: FileScanner = Depends(get_scanner)):
    """获取支持的文件类型列表"""
    try:
        file_types = scanner.get_file_types(enabled_only=enabled_only)
        return Result.succ(file_types)
    except Exception as e:
        return Result.failed(f"获取文件类型失败: {str(e)}", "E0020")


@router.post("/file-types", summary="添加文件类型", response_model=Result[Dict[str, Any]])
async def add_file_type(file_type: FileTypeModel, scanner: FileScanner = Depends(get_scanner)):
    """添加新的文件类型"""
    try:
        success = scanner.add_file_type(file_type.extension, file_type.description, file_type.enabled)
        if success:
            return Result.succ({"message": f"文件类型 {file_type.extension} 已添加"})
        else:
            return Result.failed("添加文件类型失败", "E0021")
    except Exception as e:
        return Result.failed(f"添加文件类型失败: {str(e)}", "E0022")


@router.put("/file-types/{extension}", summary="更新文件类型", response_model=Result[Dict[str, Any]])
async def update_file_type(extension: str, file_type: FileTypeModel, scanner: FileScanner = Depends(get_scanner)):
    """更新文件类型配置"""
    try:
        success = scanner.update_file_type(extension, file_type.description, file_type.enabled)
        if success:
            return Result.succ({"message": f"文件类型 {extension} 已更新"})
        else:
            return Result.failed("文件类型不存在", "E0023")
    except Exception as e:
        return Result.failed(f"更新文件类型失败: {str(e)}", "E0024")


@router.delete("/file-types/{extension}", summary="删除文件类型", response_model=Result[Dict[str, Any]])
async def delete_file_type(extension: str, scanner: FileScanner = Depends(get_scanner)):
    """删除文件类型"""
    try:
        success = scanner.remove_file_type(extension)
        if success:
            return Result.succ({"message": f"文件类型 {extension} 已删除"})
        else:
            return Result.failed("文件类型不存在", "E0025")
    except Exception as e:
        return Result.failed(f"删除文件类型失败: {str(e)}", "E0026")


@router.get("/scan-configs", summary="获取扫描配置列表", response_model=Result[List[ScanConfigResponse]])
async def get_scan_configs(enabled_only: bool = False, scanner: FileScanner = Depends(get_scanner)):
    """获取所有扫描配置"""
    try:
        configs = scanner.get_scan_configs(enabled_only=enabled_only)
        return Result.succ(configs)
    except Exception as e:
        return Result.failed(f"获取扫描配置失败: {str(e)}", "E0030")


@router.post("/scan-configs/local", summary="添加本地目录配置", response_model=Result[Dict[str, Any]])
async def add_local_directory(config: LocalDirectoryConfig, scanner: FileScanner = Depends(get_scanner)):
    """添加本地目录扫描配置"""
    try:
        success = scanner.add_local_directory(config.name, config.path, config.enabled)
        if success:
            return Result.succ({"message": f"本地目录配置 {config.name} 已添加"})
        else:
            return Result.failed("添加本地目录配置失败", "E0031")
    except Exception as e:
        return Result.failed(f"添加本地目录配置失败: {str(e)}", "E0032")


@router.post("/scan-configs/ftp", summary="添加FTP服务器配置", response_model=Result[Dict[str, Any]])
async def add_ftp_server(config: FTPServerConfig, scanner: FileScanner = Depends(get_scanner)):
    """添加FTP服务器扫描配置"""
    try:
        success = scanner.add_ftp_server(
            config.name, config.host, config.username, config.password,
            config.port, config.remote_dir, config.enabled
        )
        if success:
            return Result.succ({"message": f"FTP服务器配置 {config.name} 已添加"})
        else:
            return Result.failed("添加FTP服务器配置失败", "E0033")
    except Exception as e:
        return Result.failed(f"添加FTP服务器配置失败: {str(e)}", "E0034")


@router.put("/scan-configs/{name}", summary="更新扫描配置状态", response_model=Result[Dict[str, Any]])
async def update_scan_config(name: str, update: ScanConfigUpdate, scanner: FileScanner = Depends(get_scanner)):
    """启用或禁用扫描配置"""
    try:
        success = scanner.update_scan_config(name, update.enabled)
        if success:
            status = "启用" if update.enabled else "禁用"
            return Result.succ({"message": f"扫描配置 {name} 已{status}"})
        else:
            return Result.failed("扫描配置不存在", "E0035")
    except Exception as e:
        return Result.failed(f"更新扫描配置失败: {str(e)}", "E0036")


@router.delete("/scan-configs/{name}", summary="删除扫描配置", response_model=Result[Dict[str, Any]])
async def delete_scan_config(name: str, scanner: FileScanner = Depends(get_scanner)):
    """删除扫描配置"""
    try:
        success = scanner.remove_scan_config(name)
        if success:
            return Result.succ({"message": f"扫描配置 {name} 已删除"})
        else:
            return Result.failed("扫描配置不存在", "E0037")
    except Exception as e:
        return Result.failed(f"删除扫描配置失败: {str(e)}", "E0038")


@router.post("/scan", summary="执行扫描", response_model=Result[ScanResult])
async def execute_scan(scanner: FileScanner = Depends(get_scanner)):
    """同步执行文件扫描和同步"""
    try:
        result = scanner.scan_and_sync()
        return Result.succ(ScanResult(**result))
    except Exception as e:
        return Result.failed(f"扫描失败: {str(e)}", "E0040")


@router.post("/scan/async", summary="异步执行扫描", response_model=Result[Dict[str, Any]])
async def execute_scan_async(background_tasks: BackgroundTasks, scanner: FileScanner = Depends(get_scanner)):
    """异步执行文件扫描和同步"""
    try:
        background_tasks.add_task(scanner.scan_and_sync)
        return Result.succ({"message": "扫描任务已提交，正在后台执行"})
    except Exception as e:
        return Result.failed(f"提交异步扫描任务失败: {str(e)}", "E0041")


@router.post("/scan/test", summary="测试扫描配置", response_model=Result[Dict[str, Any]])
async def test_scan_configs(scanner: FileScanner = Depends(get_scanner)):
    """测试扫描配置是否正确"""
    try:
        configs = scanner.get_scan_configs(enabled_only=True)
        test_results = []

        for config in configs:
            test_result = {
                "name": config["name"],
                "type": config["type"],
                "status": "success",
                "message": ""
            }

            try:
                if config["type"] == "local":
                    import os
                    path = config["config"]["path"]
                    if not os.path.exists(path):
                        test_result["status"] = "error"
                        test_result["message"] = f"目录不存在: {path}"
                    elif not os.access(path, os.R_OK):
                        test_result["status"] = "error"
                        test_result["message"] = f"目录无读取权限: {path}"
                    else:
                        test_result["message"] = "目录访问正常"

                elif config["type"] == "ftp":
                    from ftplib import FTP
                    ftp_config = config["config"]
                    try:
                        ftp = FTP()
                        ftp.connect(ftp_config["host"], ftp_config.get("port", 21))
                        ftp.login(ftp_config["username"], ftp_config["password"])
                        if ftp_config.get("remote_dir"):
                            ftp.cwd(ftp_config["remote_dir"])
                        ftp.quit()
                        test_result["message"] = "FTP连接正常"
                    except Exception as e:
                        test_result["status"] = "error"
                        test_result["message"] = f"FTP连接失败: {str(e)}"

            except Exception as e:
                test_result["status"] = "error"
                test_result["message"] = f"测试失败: {str(e)}"

            test_results.append(test_result)

        return Result.succ({"test_results": test_results})
    except Exception as e:
        return Result.failed(f"测试扫描配置失败: {str(e)}", "E0042")


@router.get("/statistics", summary="获取统计信息", response_model=Result[StatisticsResponse])
async def get_statistics(scanner: FileScanner = Depends(get_scanner)):
    """获取系统统计信息"""
    try:
        stats = scanner.get_statistics()
        return Result.succ(StatisticsResponse(**stats))
    except Exception as e:
        return Result.failed(f"获取统计信息失败: {str(e)}", "E0050")


@router.get("/processed-files", summary="获取已处理文件列表", response_model=Result[List[ProcessedFileResponse]])
async def get_processed_files(limit: int = 100, scanner: FileScanner = Depends(get_scanner)):
    """获取已处理文件列表"""
    try:
        files = scanner.get_processed_files(limit=limit)
        return Result.succ(files)
    except Exception as e:
        return Result.failed(f"获取已处理文件列表失败: {str(e)}", "E0051")


@router.delete("/processed-files", summary="清空已处理文件记录", response_model=Result[Dict[str, Any]])
async def clear_processed_files(scanner: FileScanner = Depends(get_scanner)):
    """清空所有已处理文件记录（重置扫描状态）"""
    try:
        success = scanner.clear_processed_files()
        if success:
            return Result.succ({"message": "已清空所有已处理文件记录"})
        else:
            return Result.failed("清空失败", "E0052")
    except Exception as e:
        return Result.failed(f"清空已处理文件记录失败: {str(e)}", "E0053")