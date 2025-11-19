"""DuckDB database operations for MyRunStreak.com."""

import logging
import os
from pathlib import Path
from typing import Any

import boto3
import duckdb  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)


class DuckDBManager:
    """
    Manages DuckDB database connections and operations.

    Handles both local file-based databases and S3-hosted databases.
    For S3 paths, downloads to /tmp, works locally, then uploads back.
    """

    def __init__(self, database_path: str | Path, read_only: bool = False) -> None:
        """
        Initialize DuckDB manager.

        Args:
            database_path: Path to the DuckDB database file (local or S3 path)
            read_only: If True, open database in read-only mode
        """
        self.original_path = str(database_path)
        self.read_only = read_only
        self._connection: duckdb.DuckDBPyConnection | None = None
        self._is_s3 = self.original_path.startswith("s3://")
        self._local_path: str | None = None
        self._s3_client = None

        if self._is_s3:
            # Parse S3 path
            self._s3_bucket, self._s3_key = self._parse_s3_path(self.original_path)
            # Use /tmp for Lambda
            self._local_path = f"/tmp/{Path(self._s3_key).name}"
            self._s3_client = boto3.client("s3")

    @staticmethod
    def _parse_s3_path(s3_path: str) -> tuple[str, str]:
        """Parse s3://bucket/key into bucket and key."""
        path = s3_path.replace("s3://", "")
        bucket, key = path.split("/", 1)
        return bucket, key

    def connect(self) -> duckdb.DuckDBPyConnection:
        """
        Establish connection to the DuckDB database.

        For S3 paths, downloads the database first.

        Returns:
            DuckDB connection object
        """
        if self._connection is None:
            if self._is_s3:
                self._download_from_s3()
                database_path: str | Path = self._local_path or self.original_path
            else:
                database_path = self.original_path

            logger.info(f"Connecting to DuckDB at {database_path}")
            self._connection = duckdb.connect(database_path, read_only=self.read_only)

        return self._connection

    def _download_from_s3(self) -> None:
        """Download database from S3 to local tmp directory."""
        if not self._s3_client or not self._local_path:
            raise RuntimeError("S3 client not initialized")

        try:
            logger.info(f"Downloading database from s3://{self._s3_bucket}/{self._s3_key}")
            self._s3_client.download_file(self._s3_bucket, self._s3_key, self._local_path)
            logger.info(f"Downloaded to {self._local_path}")
        except self._s3_client.exceptions.NoSuchKey:
            logger.info(f"Database not found in S3, will create new one at {self._local_path}")
        except Exception as e:
            logger.error(f"Failed to download from S3: {e}")
            raise

    def _upload_to_s3(self) -> None:
        """Upload local database back to S3."""
        if not self._is_s3 or not self._s3_client or not self._local_path:
            return

        if not os.path.exists(self._local_path):
            logger.warning(f"Local database {self._local_path} not found, skipping upload")
            return

        try:
            logger.info(f"Uploading database to s3://{self._s3_bucket}/{self._s3_key}")
            self._s3_client.upload_file(self._local_path, self._s3_bucket, self._s3_key)
            logger.info("Upload complete")
        except Exception as e:
            logger.error(f"Failed to upload to S3: {e}")
            raise

    def close(self) -> None:
        """Close the database connection and upload to S3 if needed."""
        if self._connection is not None:
            logger.info("Closing DuckDB connection")
            self._connection.close()
            self._connection = None

            # Upload to S3 if using S3 storage
            if self._is_s3:
                self._upload_to_s3()

    def __enter__(self) -> duckdb.DuckDBPyConnection:
        """Context manager entry."""
        return self.connect()

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def initialize_schema(self, schema_path: str | Path | None = None) -> None:
        """
        Initialize database schema from SQL file.

        Args:
            schema_path: Path to schema.sql file. If None, uses default schema.
        """
        if schema_path is None:
            schema_path = Path(__file__).parent / "schema.sql"
        else:
            schema_path = Path(schema_path)

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        logger.info(f"Initializing schema from {schema_path}")

        with open(schema_path) as f:
            schema_sql = f.read()

        conn = self.connect()
        conn.execute(schema_sql)
        conn.commit()

        logger.info("Schema initialized successfully")

    def execute_query(self, query: str, parameters: dict[str, Any] | None = None) -> Any:
        """
        Execute a SQL query.

        Args:
            query: SQL query string
            parameters: Optional query parameters

        Returns:
            Query results
        """
        conn = self.connect()

        if parameters:
            return conn.execute(query, parameters).fetchall()
        return conn.execute(query).fetchall()

    def execute_script(self, script: str) -> None:
        """
        Execute a SQL script (multiple statements).

        Args:
            script: SQL script with multiple statements
        """
        conn = self.connect()
        conn.execute(script)
        conn.commit()

    def get_schema_version(self) -> int | None:
        """
        Get current schema version.

        Returns:
            Current schema version number, or None if schema_version table doesn't exist
        """
        conn = self.connect()

        try:
            result = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
            return result[0] if result else None
        except duckdb.CatalogException:
            # schema_version table doesn't exist yet
            return None

    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the database.

        Args:
            table_name: Name of the table to check

        Returns:
            True if table exists, False otherwise
        """
        conn = self.connect()

        result = conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = ?
            """,
            [table_name],
        ).fetchone()

        return bool(result and result[0] > 0)
