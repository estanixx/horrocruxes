"""
SQL Reasoning Module for Structured Data

Parses natural language questions into SQL operations (filter, sort, aggregate, compare)
and executes them against CSV data via DuckDB.

Trigger keywords: potions, spells, characters, dialogs
Operations: filter, sort, aggregate, compare
"""

import re
from typing import Optional


class SQLIntent:
    """Parsed SQL intent from a natural language query."""
    def __init__(
        self,
        operation: str,  # "select", "filter", "sort", "aggregate", "compare"
        table: Optional[str] = None,
        columns: list[str] = None,
        where_clause: Optional[str] = None,
        order_by: Optional[str] = None,
        order_dir: str = "ASC",
        aggregate_func: Optional[str] = None,
        aggregate_col: Optional[str] = None,
        limit: int = 10,
    ):
        self.operation = operation
        self.table = table
        self.columns = columns or ["*"]
        self.where_clause = where_clause
        self.order_by = order_by
        self.order_dir = order_dir.upper()  # ASC or DESC
        self.aggregate_func = aggregate_func
        self.aggregate_col = aggregate_col
        self.limit = limit

    def to_sql(self) -> str:
        """Convert intent to SQL query string."""
        cols = ", ".join(self.columns) if self.columns else "*"
        
        # Handle aggregate functions
        if self.aggregate_func == "COUNT":
            return f"SELECT COUNT(*) as result FROM df"
        elif self.aggregate_func in ("SUM", "AVG", "MIN", "MAX") and self.aggregate_col:
            func = self.aggregate_func.upper()
            return f"SELECT {func}({self.aggregate_col}) as result FROM df"
        
        # Handle SELECT with WHERE and ORDER BY
        sql = f"SELECT {cols} FROM df"
        
        if self.where_clause:
            sql += f" WHERE {self.where_clause}"
        
        if self.order_by:
            sql += f" ORDER BY {self.order_by} {self.order_dir}"
        
        if self.limit:
            sql += f" LIMIT {self.limit}"
        
        return sql


# Column mappings for Harry Potter CSV data
COLUMN_MAPPINGS = {
    "name": ["name", "spell_name", "character_name", "potion_name", "dialogue", "line"],
    "type": ["type", "category", "spell_type", "effect_type"],
    "level": ["level", "difficulty", "power_level"],
    "cost": ["cost", "price", "gold"],
    "time": ["time", "duration", "brewing_time"],
    "effect": ["effect", "description", "result"],
    "house": ["house", "house_name"],
    "character": ["character", "speaker", "person"],
    "dialogue": ["dialogue", "line", "quote", "text"],
}


def _find_column(columns: list[str], keywords: list[str]) -> Optional[str]:
    """Find a column that matches any of the keywords."""
    for kw in keywords:
        kw_lower = kw.lower()
        for col in columns:
            col_lower = col.lower()
            if kw_lower in col_lower:
                return col
    return None


def _detect_filter(text: str, columns: list[str]) -> Optional[str]:
    """Detect WHERE clause from natural language."""
    text_lower = text.lower()
    
    def find_best_column():
        col = _find_column(columns, ["type", "category", "effect", "description"])
        if col:
            return col
        col = _find_column(columns, ["name", "spell_name", "character_name"])
        if col:
            return col
        return columns[0] if columns else None
    
    # Dark/unforgivable detection
    if "dark" in text_lower:
        col = find_best_column()
        if col:
            return f"{col} LIKE '%dark%' OR {col} LIKE '%unforgivable%'"
    
    if "unforgivable" in text_lower:
        col = find_best_column()
        if col:
            return f"{col} LIKE '%unforgivable%'"
    
    # Level filter
    level_match = re.search(r"level\s+(\d+)", text_lower)
    if level_match:
        col = _find_column(columns, ["level", "difficulty"])
        if col:
            return f"{col} = {level_match.group(1)}"
    
    # House filters
    for house in ["gryffindor", "slytherin", "hufflepuff", "ravenclaw"]:
        if house in text_lower:
            col = _find_column(columns, ["house", "house_name"])
            if col:
                return f"{col} = '{house.title()}'"
    
    # Love potions
    if "love" in text_lower:
        col = _find_column(columns, ["type", "category", "effect"])
        if col:
            return f"{col} LIKE '%love%'"
    
    return None


def _detect_sort(text: str, columns: list[str]) -> tuple[Optional[str], str]:
    """Detect ORDER BY clause and direction."""
    text_lower = text.lower()
    
    order_dir = "DESC"
    if any(kw in text_lower for kw in ["least", "lowest", "smallest", "cheapest"]):
        order_dir = "ASC"
    
    # Column detection
    if any(kw in text_lower for kw in ["expensive", "cost", "price", "gold"]):
        col = _find_column(columns, ["cost", "price", "gold"])
        if col:
            return col, order_dir
    
    if any(kw in text_lower for kw in ["powerful", "strong", "dangerous", "power"]):
        col = _find_column(columns, ["level", "difficulty", "power"])
        if col:
            return col, order_dir
    
    if any(kw in text_lower for kw in ["alphabetically", "name", "sorted"]):
        col = _find_column(columns, ["name"])
        if col:
            return col, "ASC"
    
    return None, order_dir


def _detect_aggregate(text: str, columns: list[str]) -> tuple[Optional[str], Optional[str]]:
    """Detect aggregate operations (COUNT, SUM, AVG, MIN, MAX)."""
    text_lower = text.lower()
    
    # Count operations
    if any(kw in text_lower for kw in ["how many", "how much", "number of", "total number"]):
        # Check if filtering by type
        for kw in ["dark", "unforgivable", "love", "potion", "spell"]:
            if kw in text_lower:
                col = _find_column(columns, ["type", "category", "effect"])
                if col:
                    return "COUNT", col
        return "COUNT", None
    
    # Sum operations
    if "total" in text_lower:
        col = _find_column(columns, ["cost", "points", "price"])
        if col:
            return "SUM", col
    
    # Average
    if "average" in text_lower:
        col = _find_column(columns, ["level", "cost", "points"])
        if col:
            return "AVG", col
    
    # Max/Min
    if any(kw in text_lower for kw in ["most", "highest", "largest"]):
        col = _find_column(columns, ["level", "cost", "points"])
        if col:
            return "MAX", col
    
    if any(kw in text_lower for kw in ["least", "lowest", "fewest"]):
        col = _find_column(columns, ["level", "cost", "points"])
        if col:
            return "MIN", col
    
    return None, None


def parse_sql_intent(query: str, sample_columns: list[str]) -> Optional[SQLIntent]:
    """
    Parse a natural language query into SQLIntent.
    Returns None if query doesn't require SQL operations.
    """
    query_lower = query.lower()
    columns = sample_columns.copy()
    
    # Check if this is a data analysis query
    data_keywords = [
        # Data types
        "potion", "spell", "character", "dialogue", "dialog", "quote", "line",
        # Operations
        "how many", "how much", "count", "number of", "total", "sum", "average",
        "show me", "list all", "which", "what are", "most", "least", 
        "highest", "lowest", "expensive", "powerful", "dark", "unforgivable",
    ]
    
    needs_sql = any(kw in query_lower for kw in data_keywords)
    
    if not needs_sql:
        return None
    
    # Parse intent
    intent = SQLIntent(operation="select")
    
    # Detect aggregation first (highest priority for counting)
    agg_func, agg_col = _detect_aggregate(query, columns)
    if agg_func:
        intent.aggregate_func = agg_func
        intent.aggregate_col = agg_col if agg_col else (columns[0] if columns else None)
        return intent
    
    # Detect sorting
    order_by, order_dir = _detect_sort(query, columns)
    if order_by:
        intent.order_by = order_by
        intent.order_dir = order_dir
    
    # Detect filtering
    where_clause = _detect_filter(query, columns)
    if where_clause:
        intent.where_clause = where_clause
    
    # Set limit
    if "list" in query_lower or "all" in query_lower:
        intent.limit = 50
    else:
        intent.limit = 10
    
    return intent


def execute_sql_intent(df, intent: SQLIntent) -> list[dict]:
    """Execute SQL intent against a pandas DataFrame."""
    import duckdb
    
    duckdb.register("df", df)
    sql = intent.to_sql()
    
    try:
        result = duckdb.query(sql).df()
        return result.to_dict(orient="records")
    except Exception as e:
        # Fallback to simple select
        try:
            fallback_sql = "SELECT * FROM df LIMIT 10"
            result = duckdb.query(fallback_sql).df()
            return result.to_dict(orient="records")
        except:
            return []