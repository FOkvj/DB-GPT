from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Union, Type
from urllib.parse import quote_plus as urlquote

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import DeclarativeMeta
from sqlalchemy.pool import QueuePool

from dbgpt.storage.metadata import DatabaseManager, BaseDao, create_model
from dbgpt.storage.metadata._base_dao import T, REQ, RES

expend_db = DatabaseManager()
ExpendModel: Type = create_model(expend_db)

class ExpendBaseDao(BaseDao[T, REQ, RES]):
    """Expend"""
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
    ) -> None:
        """Create a BaseDao instance."""
        super().__init__(db_manager)
        self._db_manager = db_manager or expend_db


"""
Expend数据库配置和初始化模块
"""



class DBType(Enum):
    """数据库类型枚举"""
    SQLITE = "sqlite"
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"


class BaseDBConfig(BaseModel, ABC):
    """数据库配置基类"""

    # 通用引擎配置
    pool_size: int = Field(default=10, ge=1, le=100, description="连接池大小")
    max_overflow: int = Field(default=20, ge=0, le=100, description="连接池最大溢出")
    pool_timeout: int = Field(default=30, ge=1, le=300, description="连接池超时时间(秒)")
    pool_recycle: int = Field(default=3600, ge=60, description="连接回收时间(秒)")
    pool_pre_ping: bool = Field(default=True, description="是否启用连接预检")
    echo: bool = Field(default=False, description="是否打印SQL语句")
    try_to_create_db: bool = Field(default=True, description="是否尝试创建数据库表")
    custom_engine_args: Dict = Field(default_factory=dict, description="自定义引擎参数")

    class Config:
        use_enum_values = True
        validate_assignment = True

    @abstractmethod
    def get_database_url(self) -> str:
        """获取数据库连接URL"""
        pass

    @abstractmethod
    def get_db_type(self) -> DBType:
        """获取数据库类型"""
        pass

    def get_engine_args(self) -> Dict:
        """获取引擎参数"""
        base_args = {
            "echo": self.echo,
        }

        # SQLite通常不需要连接池配置
        if self.get_db_type() != DBType.SQLITE:
            base_args.update({
                "poolclass": QueuePool,
                "pool_size": self.pool_size,
                "max_overflow": self.max_overflow,
                "pool_timeout": self.pool_timeout,
                "pool_recycle": self.pool_recycle,
                "pool_pre_ping": self.pool_pre_ping,
            })

        # 合并自定义参数
        base_args.update(self.custom_engine_args)

        return base_args


class SQLiteConfig(BaseDBConfig):
    """SQLite数据库配置"""

    sqlite_path: str = Field(default="expend.db", description="SQLite数据库文件路径")

    @field_validator('sqlite_path')
    def validate_sqlite_path(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("SQLite路径不能为空")
        return v

    def get_database_url(self) -> str:
        """获取SQLite数据库连接URL"""
        return f"sqlite:///{self.sqlite_path}"

    def get_db_type(self) -> DBType:
        """获取数据库类型"""
        return DBType.SQLITE


class MySQLConfig(BaseDBConfig):
    """MySQL数据库配置"""

    host: str = Field(default="localhost", description="MySQL主机地址")
    port: int = Field(default=3306, ge=1, le=65535, description="MySQL端口")
    username: str = Field(..., description="MySQL用户名")
    password: str = Field(default="", description="MySQL密码")
    database: str = Field(..., description="MySQL数据库名")
    charset: str = Field(default="utf8mb4", description="字符集")

    @field_validator('host')
    def validate_host(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("主机地址不能为空")
        return v

    @field_validator('username')
    def validate_username(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("用户名不能为空")
        return v

    @field_validator('database')
    def validate_database(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("数据库名不能为空")
        return v

    def get_database_url(self) -> str:
        """获取MySQL数据库连接URL"""
        return (
            f"mysql+pymysql://{self.username}:{urlquote(self.password)}"
            f"@{self.host}:{self.port}/{self.database}?charset={self.charset}"
        )

    def get_db_type(self) -> DBType:
        """获取数据库类型"""
        return DBType.MYSQL


class PostgreSQLConfig(BaseDBConfig):
    """PostgreSQL数据库配置"""

    host: str = Field(default="localhost", description="PostgreSQL主机地址")
    port: int = Field(default=5432, ge=1, le=65535, description="PostgreSQL端口")
    username: str = Field(..., description="PostgreSQL用户名")
    password: str = Field(default="", description="PostgreSQL密码")
    database: str = Field(..., description="PostgreSQL数据库名")

    @field_validator('host')
    def validate_host(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("主机地址不能为空")
        return v

    @field_validator('username')
    def validate_username(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("用户名不能为空")
        return v

    @field_validator('database')
    def validate_database(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("数据库名不能为空")
        return v

    def get_database_url(self) -> str:
        """获取PostgreSQL数据库连接URL"""
        return (
            f"postgresql+psycopg2://{self.username}:{urlquote(self.password)}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    def get_db_type(self) -> DBType:
        """获取数据库类型"""
        return DBType.POSTGRESQL


# 统一的配置类型
ExpendDatabaseConfig = Union[SQLiteConfig, MySQLConfig, PostgreSQLConfig]


def initialize_expend_db(
        config: ExpendDatabaseConfig,
        base: Optional[DeclarativeMeta] = None,
        session_options: Optional[Dict] = None,
) -> DatabaseManager:
    """初始化Expend数据库

    Args:
        config: 数据库配置对象
        base: 数据库模型基类
        session_options: 会话选项

    Returns:
        DatabaseManager: 初始化后的数据库管理器

    Examples:
        # SQLite示例
        >>> config = SQLiteConfig(sqlite_path="my_expend.db")
        >>> initialize_expend_db(config)

        # MySQL示例
        >>> config = MySQLConfig(
        ...     host="localhost",
        ...     username="root",
        ...     password="password",
        ...     database="expend_db"
        ... )
        >>> initialize_expend_db(config)

        # PostgreSQL示例
        >>> config = PostgreSQLConfig(
        ...     host="localhost",
        ...     username="postgres",
        ...     password="password",
        ...     database="expend_db",
        ...     pool_size=20
        ... )
        >>> initialize_expend_db(config)
    """
    try:
        # 获取数据库URL和引擎参数
        db_url = config.get_database_url()
        engine_args = config.get_engine_args()

        print(f"正在初始化Expend数据库...")
        print(f"数据库类型: {config.get_db_type().value}")
        print(f"数据库URL: {db_url.split('://')[0]}://{'*' * 10}")  # 隐藏敏感信息

        # 初始化数据库
        expend_db.init_db(
            db_url=db_url,
            engine_args=engine_args,
            base=base,
            session_options=session_options
        )

        print("Expend数据库连接已建立")

        # 尝试创建表
        if config.try_to_create_db:
            expend_db.create_all()
            print("Expend数据库表已创建/更新")

        return expend_db

    except Exception as e:
        print(f"初始化Expend数据库失败: {e}")
        raise



# 便捷的初始化函数
def init_expend_sqlite(sqlite_path: str = "expend.db", **kwargs) -> DatabaseManager:
    """初始化SQLite Expend数据库"""
    config = SQLiteConfig(sqlite_path=sqlite_path, **kwargs)
    return initialize_expend_db(config)


def init_expend_mysql(
        host: str = "localhost",
        port: int = 3306,
        username: str = "root",
        password: str = "",
        database: str = "expend_db",
        **kwargs
) -> DatabaseManager:
    """初始化MySQL Expend数据库"""
    config = MySQLConfig(
        host=host, port=port, username=username,
        password=password, database=database, **kwargs
    )
    return initialize_expend_db(config)


def init_expend_postgresql(
        host: str = "localhost",
        port: int = 5432,
        username: str = "postgres",
        password: str = "",
        database: str = "expend_db",
        **kwargs
) -> DatabaseManager:
    """初始化PostgreSQL Expend数据库"""
    config = PostgreSQLConfig(
        host=host, port=port, username=username,
        password=password, database=database, **kwargs
    )
    return initialize_expend_db(config)


# 使用示例和配置验证
if __name__ == "__main__":

    # 示例1: SQLite配置
    print("=== SQLite配置示例 ===")
    try:
        sqlite_config = SQLiteConfig(sqlite_path="test_expend.db", echo=True)
        print(f"SQLite配置: {sqlite_config.model_dump()}")
        print(f"数据库URL: {sqlite_config.get_database_url()}")
        print(f"引擎参数: {sqlite_config.get_engine_args()}")

        # 初始化数据库
        init_db = initialize_expend_db(sqlite_config)
        print("SQLite数据库初始化成功")

    except Exception as e:
        print(f"SQLite配置错误: {e}")

    # 示例2: MySQL配置
    print("\n=== MySQL配置示例 ===")
    try:
        mysql_config = MySQLConfig(
            host="localhost",
            port=3307,
            username="root",
            password="1234",
            database="expend_test",
            pool_size=15,
            echo=True,
            charset="utf8mb4"
        )
        print(f"MySQL配置: {mysql_config.model_dump()}")
        print(f"数据库URL: {mysql_config.get_database_url()}")
        print(f"引擎参数: {mysql_config.get_engine_args()}")

        # 不实际连接，只验证配置
        print("MySQL配置验证成功")

    except Exception as e:
        print(f"MySQL配置错误: {e}")

