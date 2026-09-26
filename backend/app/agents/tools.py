import json

from strands import tool

from app.db import get_conn


@tool
def get_latest_invoice(customer_id: str) -> str:
    """Look up the latest invoice and plan of a customer.

    Args:
        customer_id: Customer ID, e.g. C-1024
    """
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
def check_account_status(customer_id: str) -> str:
    """Check account status (locked or not, lock reason, number of failed logins).

    Args:
        customer_id: Customer ID, e.g. C-1024
    """
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
