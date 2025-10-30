"""DuckDB database operations for MyRunStreak.com."""

import logging
from pathlib import Path
from typing import Any

import duckdb

logger = logging.getLogger(__name__)


class DuckDBManager:
    """
    Manages DuckDB database connections and operations.

    Handles both local file-based databases and S3-hosted databases.
    """

    def __init__(self, database_path: str | Path, read_only: bool = False) -> None:
        """
        Initialize DuckDB manager.

        Args:
            database_path: Path to the DuckDB database file (local or S3 path)
            read_only: If True, open database in read-only mode
        """
        self.database_path = str(database_path)
        self.read_only = read_only
        self._connection: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> duckdb.DuckDBPyConnection:
        """
        Establish connection to the DuckDB database.

        Returns:
            DuckDB connection object
        """
        if self._connection is None:
            logger.info(f"Connecting to DuckDB at {self.database_path}")
            self._connection = duckdb.connect(self.database_path, read_only=self.read_only)

            # Configure S3 access if using S3 path
            if self.database_path.startswith("s3://"):
                self._configure_s3()

        return self._connection

    def _configure_s3(self) -> None:
        """Configure S3 extension and credentials for S3-hosted databases."""
        if self._connection is None:
            raise RuntimeError("Connection must be established before configuring S3")

        logger.info("Configuring DuckDB S3 extension")

        # Install and load S3 extension
        self._connection.execute("INSTALL httpfs;")
        self._connection.execute("LOAD httpfs;")

        # S3 credentials will be loaded from AWS environment variables
        # or IAM role when running in Lambda
        logger.info("S3 extension configured successfully")

    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            logger.info("Closing DuckDB connection")
            self._connection.close()
            self._connection = None

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
            result = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
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
