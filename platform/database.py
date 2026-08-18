
"""SQL Server database connection and helpers."""

import os
import pyodbc
import json
from typing import Dict, Any


def get_connection():
    """Get a SQL Server connection using the same config as your MCP server."""
    server = os.getenv("WIN_DB_SERVER")
    database = os.getenv("WIN_DB_NAME")
    driver = os.getenv("WIN_DB_DRIVER")
    auth_type = os.getenv("WIN_DB_AUTH_TYPE")


    conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )

    return pyodbc.connect(conn_str)


def dict_to_json(d: Dict[str, Any]) -> str:
    """Convert dict to JSON string."""
    return json.dumps(d, default=str)


def json_to_dict(s: str) -> Dict[str, Any]:
    """Convert JSON string to dict."""
    if not s:
        return {}
    return json.loads(s)