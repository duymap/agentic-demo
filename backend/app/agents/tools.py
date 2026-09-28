import json
from typing import Annotated

from agent_framework import tool
from pydantic import Field

from app.db import get_conn

CustomerId = Annotated[str, Field(description="Customer ID, e.g. C-1024")]


@tool
def get_latest_invoice(customer_id: CustomerId) -> str:
    """Look up the latest invoice and plan of a customer."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT i.id, i.customer_id, c.name, c.plan, i.amount_usd, i.status, i.due_date
               FROM invoices i JOIN customers c ON c.id = i.customer_id
               WHERE i.customer_id = ? ORDER BY i.due_date DESC LIMIT 1""",
            (customer_id,),
        ).fetchone()
    if not row:
        return json.dumps({"error": f"No invoice found for {customer_id}"}, ensure_ascii=False)
    return json.dumps(dict(row), ensure_ascii=False)


@tool
def check_account_status(customer_id: CustomerId) -> str:
    """Check account status (locked or not, lock reason, number of failed logins)."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT a.customer_id, c.name, a.locked, a.lock_reason, a.failed_logins
               FROM accounts a JOIN customers c ON c.id = a.customer_id
               WHERE a.customer_id = ?""",
            (customer_id,),
        ).fetchone()
    if not row:
        return json.dumps({"error": f"No account found for {customer_id}"}, ensure_ascii=False)
    return json.dumps(dict(row), ensure_ascii=False)
