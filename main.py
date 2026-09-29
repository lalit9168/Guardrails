from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
import sqlite3
import os
import uuid


# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(
    title="Order Management Tool",
    description="Order Management API for Microsoft Foundry Guardrails demo",
    version="2.0.0"
)


# ============================================================
# Database Configuration
# ============================================================

# Local:
#   orders.db
#
# Render:
#   /data/orders.db
#
# The DB_PATH environment variable can be configured in Render.
DB_PATH = os.getenv("DB_PATH", "orders.db")


# ============================================================
# Database Connection
# ============================================================

def get_db_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


# ============================================================
# Initialize Database
# ============================================================

def init_database():

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            product TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT NOT NULL,
            shipping_address TEXT,
            cancellation_reason TEXT,
            created_at TEXT NOT NULL
        )
    """)

    connection.commit()

    # --------------------------------------------------------
    # Insert initial demo data only if table is empty
    # --------------------------------------------------------

    cursor.execute("SELECT COUNT(*) AS count FROM orders")
    count = cursor.fetchone()["count"]

    if count == 0:

        demo_orders = [
            (
                "ORD12345",
                "Rahul",
                "Laptop",
                2,
                "Shipped",
                "Pune, Maharashtra",
                None,
                datetime.utcnow().isoformat()
            ),
            (
                "ORD67890",
                "Amit",
                "Mobile",
                1,
                "Processing",
                "Mumbai, Maharashtra",
                None,
                datetime.utcnow().isoformat()
            ),
            (
                "ORD11111",
                "Priya",
                "Headphones",
                1,
                "Delivered",
                "Nashik, Maharashtra",
                None,
                datetime.utcnow().isoformat()
            )
        ]

        cursor.executemany("""
            INSERT INTO orders (
                order_id,
                customer_name,
                product,
                quantity,
                status,
                shipping_address,
                cancellation_reason,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, demo_orders)

        connection.commit()

    connection.close()


# Initialize database when application starts
init_database()


# ============================================================
# Request Models
# ============================================================

class GetOrderRequest(BaseModel):

    order_id: str = Field(
        ...,
        description="Order ID, for example ORD12345"
    )


class CreateOrderRequest(BaseModel):

    customer_name: str = Field(
        ...,
        description="Customer name"
    )

    product: str = Field(
        ...,
        description="Product name"
    )

    quantity: int = Field(
        ...,
        gt=0,
        description="Number of products"
    )

    shipping_address: str = Field(
        ...,
        description="Customer shipping address"
    )


class CancelOrderRequest(BaseModel):

    order_id: str = Field(
        ...,
        description="Order ID to cancel"
    )

    reason: str = Field(
        ...,
        description="Reason for cancelling the order"
    )


# ============================================================
# Helper Function
# ============================================================

def convert_order(row):

    if row is None:
        return None

    return {
        "order_id": row["order_id"],
        "customer_name": row["customer_name"],
        "product": row["product"],
        "quantity": row["quantity"],
        "status": row["status"],
        "shipping_address": row["shipping_address"],
        "cancellation_reason": row["cancellation_reason"],
        "created_at": row["created_at"]
    }


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "service": "Order Management Tool",
        "status": "running",
        "version": "2.0.0",
        "database": "SQLite"
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    try:

        connection = get_db_connection()

        connection.execute(
            "SELECT 1"
        )

        connection.close()

        return {
            "status": "healthy",
            "database": "connected"
        }

    except Exception as e:

        return {
            "status": "unhealthy",
            "database": "error",
            "message": str(e)
        }


# ============================================================
# GET ALL ORDERS
# ============================================================

@app.get(
    "/get-all-orders",
    operation_id="get_all_orders"
)
def get_all_orders():

    connection = get_db_connection()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM orders
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()

    connection.close()

    orders = [
        convert_order(row)
        for row in rows
    ]

    return {
        "success": True,
        "total_orders": len(orders),
        "orders": orders
    }


# ============================================================
# GET ORDER
# ============================================================

@app.post(
    "/get-order",
    operation_id="get_order"
)
def get_order(request: GetOrderRequest):

    connection = get_db_connection()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM orders
        WHERE order_id = ?
    """, (request.order_id,))

    row = cursor.fetchone()

    connection.close()

    if row is None:

        raise HTTPException(
            status_code=404,
            detail=f"Order {request.order_id} not found"
        )

    return {
        "success": True,
        "message": "Order found",
        "order": convert_order(row)
    }


# ============================================================
# CREATE ORDER
# ============================================================

@app.post(
    "/create-order",
    operation_id="create_order"
)
def create_order(request: CreateOrderRequest):

    order_id = "ORD" + str(
        uuid.uuid4().int
    )[:6]

    created_at = datetime.utcnow().isoformat()

    connection = get_db_connection()

    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO orders (
            order_id,
            customer_name,
            product,
            quantity,
            status,
            shipping_address,
            cancellation_reason,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_id,
        request.customer_name,
        request.product,
        request.quantity,
        "Created",
        request.shipping_address,
        None,
        created_at
    ))

    connection.commit()

    cursor.execute("""
        SELECT *
        FROM orders
        WHERE order_id = ?
    """, (order_id,))

    row = cursor.fetchone()

    connection.close()

    return {
        "success": True,
        "message": "Order created successfully",
        "order": convert_order(row)
    }


# ============================================================
# CANCEL ORDER
# ============================================================

@app.post(
    "/cancel-order",
    operation_id="cancel_order"
)
def cancel_order(request: CancelOrderRequest):

    connection = get_db_connection()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM orders
        WHERE order_id = ?
    """, (request.order_id,))

    row = cursor.fetchone()

    if row is None:

        connection.close()

        raise HTTPException(
            status_code=404,
            detail=f"Order {request.order_id} not found"
        )

    if row["status"] == "Cancelled":

        connection.close()

        return {
            "success": False,
            "message": "Order is already cancelled",
            "order": convert_order(row)
        }

    if row["status"] == "Delivered":

        connection.close()

        return {
            "success": False,
            "message": "Delivered orders cannot be cancelled",
            "order": convert_order(row)
        }

    cursor.execute("""
        UPDATE orders
        SET
            status = ?,
            cancellation_reason = ?
        WHERE order_id = ?
    """, (
        "Cancelled",
        request.reason,
        request.order_id
    ))

    connection.commit()

    cursor.execute("""
        SELECT *
        FROM orders
        WHERE order_id = ?
    """, (request.order_id,))

    updated_row = cursor.fetchone()

    connection.close()

    return {
        "success": True,
        "message": f"Order {request.order_id} cancelled successfully",
        "order": convert_order(updated_row)
    }