"""Excel to MySQL data import utility."""
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, BinaryIO

import pandas as pd

from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import ViewMetadata, OperatorCategory, Parameter, IOField, ui
from dbgpt.core.awel.util.parameter_util import OptionValue
from dbgpt.core.interface.file import FileStorageClient, FileMetadata
from dbgpt.util.i18n_utils import _
from dbgpt_ext.datasource.rdbms.conn_mysql import MySQLConnector, MySQLParameters
from typing import Any, Dict, List, Optional

import json
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import ViewMetadata, OperatorCategory, Parameter, IOField, ui
from dbgpt.core.interface.file import FileStorageClient, FileMetadata

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class ExtendedMySQLConnector(MySQLConnector):
    """Extended MySQL connector with auto database creation feature."""

    @classmethod
    def from_uri_db(
            cls,
            host: str,
            port: int,
            user: str,
            pwd: str,
            db_name: str,
            auto_create: bool = False,
            engine_args: Optional[dict] = None,
            **kwargs: Any,
    ) -> "ExtendedMySQLConnector":
        """Construct a SQLAlchemy engine from uri database with optional auto-creation.

        Args:
            host (str): database host.
            port (int): database port.
            user (str): database user.
            pwd (str): database password.
            db_name (str): database name.
            auto_create (bool): automatically create database if it doesn't exist.
            engine_args (Optional[dict]): other engine_args.
        """
        # If auto_create is True, check if the database exists and create it if needed
        if auto_create:
            try:
                # Connect to MySQL server without specifying a database
                base_url = f"mysql+pymysql://{user}:{pwd}@{host}:{port}"
                engine = create_engine(base_url)

                # Check if database exists
                with engine.connect() as conn:
                    result = conn.execute(text(f"SHOW DATABASES LIKE '{db_name}'"))
                    if not result.fetchone():
                        logger.info(f"Database '{db_name}' does not exist. Creating it...")
                        conn.execute(
                            text(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                        logger.info(f"Database '{db_name}' created successfully")

                engine.dispose()
            except SQLAlchemyError as e:
                logger.warning(f"Failed to check/create database: {e}")
                # Continue with regular connection, in case the error is temporary or permission-related

        # Create the connector with the specified database
        db_url: str = f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db_name}"
        return cls.from_uri(db_url, engine_args, **kwargs)


@dataclass
class ExcelToMysqlParameters:
    """Parameters for Excel to MySQL import."""

    __type__ = "excel_to_mysql"

    excel_file_path: str = field(
        metadata={"help": _("Path to the Excel file to import")}
    )

    auto_create: bool = field(
        default=False,
        metadata={"help": _("Automatically create database and tables if they don't exist")}
    )

    sheet_names: Optional[List[str]] = field(
        default=None,
        metadata={"help": _("List of sheet names to import. If None, import all sheets")}
    )

    table_prefix: str = field(
        default="",
        metadata={"help": _("Prefix to add to table names (if auto-creating tables)")}
    )

    table_mapping: Optional[Dict[str, str]] = field(
        default=None,
        metadata={"help": _("Mapping of sheet names to table names (overrides table_prefix)")}
    )

    chunk_size: int = field(
        default=1000,
        metadata={"help": _("Number of rows to insert at once")}
    )

    if_exists: str = field(
        default="replace",
        metadata={"help": _("What to do if the table exists: 'fail', 'replace', or 'append'")}
    )

    column_mapping: Optional[Dict[str, Dict[str, str]]] = field(
        default=None,
        metadata={"help": _("Mapping of sheet columns to table columns")}
    )

    def create_importer(self) -> "ExcelToMysql":
        """Create an ExcelToMysql instance from these parameters."""
        return ExcelToMysql.from_parameters(self)


class ExcelToMysql:
    """Utility for importing Excel data into MySQL tables."""

    def __init__(
        self,
        connector: MySQLConnector,
        excel_path_buffer: str,
        auto_create: bool = False,
        sheet_names: Optional[List[str]] = None,
        table_prefix: str = "",
        table_mapping: Optional[Dict[str, str]] = None,
        chunk_size: int = 1000,
        if_exists: str = "replace",
        column_mapping: Optional[Dict[str, Dict[str, str]]] = None,
    ):
        """Initialize the Excel to MySQL importer.

        Args:
            connector: MySQL connector instance
            excel_file_path: Path to the Excel file
            auto_create: Whether to automatically create databases and tables
            sheet_names: List of sheet names to import (if None, import all)
            table_prefix: Prefix to add to table names (if auto-creating)
            table_mapping: Mapping of sheet names to table names
            chunk_size: Number of rows to insert at once
            if_exists: What to do if table exists ('fail', 'replace', 'append')
            column_mapping: Mapping of sheet columns to table columns
        """
        self.connector = connector
        self.excel_file_path = excel_path_buffer
        self.auto_create = auto_create
        self.sheet_names = sheet_names
        self.table_prefix = table_prefix
        self.table_mapping = table_mapping or {}
        self.chunk_size = chunk_size
        self.if_exists = if_exists
        self.column_mapping = column_mapping or {}

        # Validate
        if isinstance(excel_path_buffer, str) and not os.path.exists(excel_path_buffer):
            raise FileNotFoundError(f"Excel file not found: {excel_path_buffer}")
        if isinstance(excel_path_buffer, bytes) and not excel_path_buffer:
            raise ValueError("Excel file buffer is empty")

        if if_exists not in ["fail", "replace", "append"]:
            raise ValueError("if_exists must be one of 'fail', 'replace', or 'append'")


    @classmethod
    def from_connector(
        cls,
        connector: MySQLConnector,
        excel_path_buffer,
        auto_create: bool = False,
        sheet_names: Optional[List[str]] = None,
        table_prefix: str = "",
        table_mapping: Optional[Dict[str, str]] = None,
        chunk_size: int = 1000,
        if_exists: str = "replace",
        column_mapping: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> "ExcelToMysql":
        """Create an instance from an existing connector.

        This is useful when you already have a configured connector
        instance that you want to reuse.

        Args:
            connector: An existing MySQLConnector instance
            excel_file_path: Path to the Excel file
            auto_create: Whether to automatically create databases and tables
            sheet_names: List of sheet names to import (if None, import all)
            table_prefix: Prefix to add to table names (if auto-creating)
            table_mapping: Mapping of sheet names to table names
            chunk_size: Number of rows to insert at once
            if_exists: What to do if table exists ('fail', 'replace', 'append')
            column_mapping: Mapping of sheet columns to table columns

        Returns:
            ExcelToMysql: A new instance using the provided connector
        """
        return cls(
            connector=connector,
            excel_path_buffer=excel_path_buffer,
            auto_create=auto_create,
            sheet_names=sheet_names,
            table_prefix=table_prefix,
            table_mapping=table_mapping,
            chunk_size=chunk_size,
            if_exists=if_exists,
            column_mapping=column_mapping,
        )

    def _get_sheet_names(self) -> List[str]:
        """Get the sheet names to process."""
        excel = pd.ExcelFile(self.excel_file_path)
        available_sheets = excel.sheet_names

        if not self.sheet_names:
            return available_sheets

        # Validate that all requested sheets exist
        missing_sheets = set(self.sheet_names) - set(available_sheets)
        if missing_sheets:
            raise ValueError(f"Sheets not found in Excel file: {missing_sheets}")

        return self.sheet_names

    def _get_table_name(self, sheet_name: str) -> str:
        """Get the table name for a sheet."""
        # Check if there's a mapping for this sheet
        if self.table_mapping and sheet_name in self.table_mapping:
            return self.table_mapping[sheet_name]

        # Apply prefix if specified
        return f"{self.table_prefix}{sheet_name}"

    def _map_column_names(self, sheet_name: str, df: pd.DataFrame) -> pd.DataFrame:
        """Map column names according to column_mapping."""
        if not self.column_mapping or sheet_name not in self.column_mapping:
            return df

        mapping = self.column_mapping[sheet_name]
        # Create a copy to avoid modifying the original dataframe
        df_copy = df.copy()

        # Rename columns according to mapping
        columns_to_rename = {col: mapping[col] for col in mapping if col in df_copy.columns}
        if columns_to_rename:
            df_copy.rename(columns=columns_to_rename, inplace=True)

        return df_copy

    def _infer_mysql_data_type(self, column: pd.Series) -> str:
        """Infer MySQL data type from pandas Series."""
        dtype = column.dtype

        # Check for nulls
        has_nulls = column.isna().any()
        null_clause = "" if has_nulls else " NOT NULL"

        # Numeric types
        if pd.api.types.is_integer_dtype(dtype):
            if column.min() >= -128 and column.max() <= 127:
                return f"TINYINT{null_clause}"
            elif column.min() >= -32768 and column.max() <= 32767:
                return f"SMALLINT{null_clause}"
            elif column.min() >= -8388608 and column.max() <= 8388607:
                return f"MEDIUMINT{null_clause}"
            elif column.min() >= -2147483648 and column.max() <= 2147483647:
                return f"INT{null_clause}"
            else:
                return f"BIGINT{null_clause}"

        elif pd.api.types.is_float_dtype(dtype):
            return f"DOUBLE{null_clause}"

        # String types
        elif pd.api.types.is_string_dtype(dtype):
            max_length = column.astype(str).str.len().max()
            if max_length <= 255:
                return f"VARCHAR({max_length}){null_clause}"
            elif max_length <= 65535:
                return f"TEXT{null_clause}"
            elif max_length <= 16777215:
                return f"MEDIUMTEXT{null_clause}"
            else:
                return f"LONGTEXT{null_clause}"

        # Date types
        elif pd.api.types.is_datetime64_dtype(dtype):
            if (column.dt.microsecond != 0).any():
                return f"DATETIME{null_clause}"
            else:
                return f"DATE{null_clause}"

        # Boolean types
        elif pd.api.types.is_bool_dtype(dtype):
            return f"BOOLEAN{null_clause}"

        # Default
        return f"VARCHAR(255){null_clause}"

    def _create_table_from_dataframe(self, df: pd.DataFrame, table_name: str) -> bool:
        """Create a table schema based on a dataframe."""
        column_definitions = []

        for column in df.columns:
            column_type = self._infer_mysql_data_type(df[column])
            # Replace spaces with underscores in column names
            safe_column_name = column.replace(" ", "_")
            column_definitions.append(f"`{safe_column_name}` {column_type}")

        # Add a primary key if there's an 'id' column, otherwise use first column
        if "id" in df.columns:
            column_definitions.append("PRIMARY KEY (`id`)")

        create_table_sql = f"""
        CREATE TABLE `{table_name}` (
            {','.join(column_definitions)}
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """

        try:
            with self.connector.session_scope() as session:
                session.execute(text(create_table_sql))
                return True
        except SQLAlchemyError as e:
            logger.error(f"Error creating table {table_name}: {e}")
            return False

    def _create_database_if_needed(self) -> bool:
        """Create the database if it doesn't exist and auto_create is True."""
        if not self.auto_create:
            return True

        db_name = self.connector.get_current_db_name()
        if not db_name:
            db_name = self.connector._engine.url.database

        try:
            # Connect to MySQL server without specifying a database
            engine_args = self.connector._engine.url._query_args
            temp_url = (
                f"{self.connector.driver}://"
                f"{self.connector._engine.url.username}:"
                f"{self.connector._engine.url.password}@"
                f"{self.connector._engine.url.host}:"
                f"{self.connector._engine.url.port}"
            )
            temp_engine = create_engine(temp_url, **engine_args)

            # Check if database exists
            with temp_engine.connect() as conn:
                result = conn.execute(text(f"SHOW DATABASES LIKE '{db_name}'"))
                if not result.fetchone():
                    # Create database
                    conn.execute(text(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                    logger.info(f"Created database: {db_name}")

            temp_engine.dispose()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error creating database {db_name}: {e}")
            return False

    def _check_and_create_table(self, sheet_name: str, df: pd.DataFrame) -> bool:
        """Check if table exists and create it if needed."""
        table_name = self._get_table_name(sheet_name)

        inspector = inspect(self.connector._engine)
        table_exists = table_name in inspector.get_table_names()

        if table_exists:
            if self.if_exists == "fail":
                raise ValueError(f"Table '{table_name}' already exists")
            elif self.if_exists == "replace":
                # Drop existing table
                with self.connector.session_scope() as session:
                    session.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
                # Create new table
                return self._create_table_from_dataframe(df, table_name)
            else:  # append
                return True
        elif self.auto_create:
            # Table doesn't exist, create it
            return self._create_table_from_dataframe(df, table_name)
        else:
            raise ValueError(f"Table '{table_name}' does not exist and auto_create is False")

    def _insert_dataframe(self, df: pd.DataFrame, table_name: str) -> int:
        """Insert dataframe data into a table."""
        row_count = 0

        # Convert column names with spaces to underscores to match table schema
        df.columns = [col.replace(" ", "_") for col in df.columns]

        try:
            # Use the SQLAlchemy connection directly for better performance
            with self.connector._engine.connect() as conn:
                # Insert in chunks
                for i in range(0, len(df), self.chunk_size):
                    chunk = df.iloc[i:i+self.chunk_size]

                    # Convert to records (list of dicts)
                    records = chunk.to_dict(orient="records")

                    if records:
                        # Build insert statement
                        columns = ", ".join([f"`{col}`" for col in chunk.columns])
                        placeholders = ", ".join([f":{col}" for col in chunk.columns])

                        insert_stmt = text(f"INSERT INTO `{table_name}` ({columns}) VALUES ({placeholders})")

                        # Execute with many parameters
                        conn.execute(insert_stmt, records)
                        row_count += len(records)

                conn.commit()

            return row_count
        except SQLAlchemyError as e:
            logger.error(f"Error inserting data into {table_name}: {e}")
            raise

    def import_sheet(self, sheet_name: str) -> Dict[str, Any]:
        """Import a single sheet into a table."""
        logger.info(f"Importing sheet: {sheet_name}")
        result = {
            "sheet_name": sheet_name,
            "success": False,
            "rows_processed": 0,
            "rows_imported": 0,
            "errors": []
        }

        try:
            # Read the sheet
            df = pd.read_excel(self.excel_file_path, sheet_name=sheet_name)
            result["rows_processed"] = len(df)

            if df.empty:
                result["errors"].append("Sheet is empty")
                return result

            # Map column names
            df = self._map_column_names(sheet_name, df)

            # Get table name
            table_name = self._get_table_name(sheet_name)

            # Check and create table if needed
            if not self._check_and_create_table(sheet_name, df):
                result["errors"].append(f"Failed to create or prepare table {table_name}")
                return result

            # Insert data
            rows_imported = self._insert_dataframe(df, table_name)
            result["rows_imported"] = rows_imported
            result["success"] = True

            logger.info(f"Successfully imported {rows_imported} rows into {table_name}")

        except Exception as e:
            error_msg = f"Error importing sheet {sheet_name}: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)

        return result

    def import_excel(self) -> Dict[str, Any]:
        """Import all specified sheets into tables."""
        logger.info(f"Starting import of Excel file: {self.excel_file_path}")

        sheet_names = self._get_sheet_names()

        results = {
            "success": True,
            "file_path": self.excel_file_path,
            "sheets": {}
        }

        for sheet_name in sheet_names:
            sheet_result = self.import_sheet(sheet_name)
            results["sheets"][sheet_name] = sheet_result

            # Mark overall success as False if any sheet fails
            if not sheet_result["success"]:
                results["success"] = False

        # Add summary
        total_processed = sum(result["rows_processed"] for result in results["sheets"].values())
        total_imported = sum(result["rows_imported"] for result in results["sheets"].values())
        results["summary"] = {
            "total_sheets": len(sheet_names),
            "successful_sheets": sum(1 for result in results["sheets"].values() if result["success"]),
            "total_rows_processed": total_processed,
            "total_rows_imported": total_imported
        }

        return results


