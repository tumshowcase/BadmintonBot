import os
import psycopg2
import json
from contextlib import closing
from psycopg2.extras import Json

DATABASE_URL = os.getenv("DATABASE_URL")


def json_value(value):
    return Json(value, dumps=lambda obj: json.dumps(obj, ensure_ascii=False))

def get_conn():

    return psycopg2.connect(DATABASE_URL)


def init_db():


    with closing(get_conn()) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""

CREATE TABLE IF NOT EXISTS balances(

    id SERIAL PRIMARY KEY,

    name TEXT UNIQUE,

    balance INTEGER DEFAULT 0

    )

    """)

                cur.execute("""

CREATE TABLE IF NOT EXISTS rounds(

    id SERIAL PRIMARY KEY,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    players TEXT,

    court_cost INTEGER,

    shuttle_cost INTEGER,

    court_payer TEXT,

    shuttle_payer TEXT,

    share INTEGER,

    result TEXT,

    comment TEXT

    )

    """)

                migrations = [
                    "ALTER TABLE balances ADD COLUMN IF NOT EXISTS name TEXT UNIQUE",
                    "ALTER TABLE balances ADD COLUMN IF NOT EXISTS balance INTEGER DEFAULT 0",
                    "ALTER TABLE rounds ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                    "ALTER TABLE rounds ADD COLUMN IF NOT EXISTS players TEXT",
                    "ALTER TABLE rounds ADD COLUMN IF NOT EXISTS court_cost INTEGER",
                    "ALTER TABLE rounds ADD COLUMN IF NOT EXISTS shuttle_cost INTEGER",
                    "ALTER TABLE rounds ADD COLUMN IF NOT EXISTS court_payer TEXT",
                    "ALTER TABLE rounds ADD COLUMN IF NOT EXISTS shuttle_payer TEXT",
                    "ALTER TABLE rounds ADD COLUMN IF NOT EXISTS share INTEGER",
                    'ALTER TABLE rounds ADD COLUMN IF NOT EXISTS "result" TEXT',
                    "ALTER TABLE rounds ADD COLUMN IF NOT EXISTS comment TEXT",
                ]

                for sql in migrations:
                    cur.execute(sql)

                cur.execute("""

CREATE UNIQUE INDEX IF NOT EXISTS balances_name_unique
ON balances(name)

""")

    print("database ready")


def get_all_balances():

    conn = get_conn()

    cur = conn.cursor()

    cur.execute("""

    SELECT
    name,
    balance

    FROM balances

    ORDER BY balance DESC

    """)

    rows = cur.fetchall()

    cur.close()

    conn.close()

    # Group "วี" and "พร" into "ครอบครัว วี & พร"
    grouped_balances = []
    family_balance = 0
    has_family = False

    for name, balance in rows:
        if name in ("วี", "พร"):
            family_balance += balance
            has_family = True
        else:
            grouped_balances.append((name, balance))

    if has_family:
        grouped_balances.append(("วี & พร", family_balance))

    # Re-sort by balance descending
    grouped_balances.sort(key=lambda x: x[1], reverse=True)

    return grouped_balances

def update_balance(
name,
amount
):

    conn = get_conn()

    cur = conn.cursor()

    cur.execute("""

INSERT INTO balances(

    name,
    balance

)

VALUES(

    %s,
    %s

)

ON CONFLICT(name)

DO UPDATE SET

balance = balances.balance + %s

""",(name, amount, amount))

    conn.commit()

    cur.close()

    conn.close()


def save_round_with_balances(
players,
court_cost,
shuttle_cost,
court_payer,
shuttle_payer,
share,
result,
comment
):
    with closing(get_conn()) as conn:
        with conn:
            with conn.cursor() as cur:
                for name, amount in result.items():
                    # --- เพิ่มเงื่อนไขบรรทัดนี้: ถ้าชื่อเริ่มด้วย G ให้ข้ามไปเลย ---
                    if name.upper().startswith("G"):
                        continue
                    # --------------------------------------------------
                    cur.execute("""
INSERT INTO balances(
    name,
    balance
)
VALUES(
    %s,
    %s
)
ON CONFLICT(name)
DO UPDATE SET
balance = balances.balance + %s
""",(name, amount, amount))

                cur.execute("""

INSERT INTO rounds(

    players,
    court_cost,
    shuttle_cost,
    court_payer,
    shuttle_payer,
    share,
    "result",
    comment

)

VALUES(

    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s

)

""",(

    json_value(players),

    court_cost,

    shuttle_cost,

    court_payer,

    shuttle_payer,

    share,

    json_value(result),

    comment

))


def reset_all_balances():


    conn = get_conn()

    cur = conn.cursor()

    cur.execute("""

    UPDATE balances

    SET balance = 0

    """)

    conn.commit()

    cur.close()

    conn.close()


def save_round(
players,
court_cost,
shuttle_cost,
court_payer,
shuttle_payer,
share,
result,
comment
):

    conn = get_conn()

    cur = conn.cursor()

    cur.execute("""

INSERT INTO rounds(

    players,
    court_cost,
    shuttle_cost,
    court_payer,
    shuttle_payer,
    share,
    "result",
    comment

)

VALUES(

    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s

)

""",(

    json_value(players),

    court_cost,

    shuttle_cost,

    court_payer,

    shuttle_payer,

    share,

    json_value(result),

    comment

))

    conn.commit()

    cur.close()

    conn.close()

def get_latest_round():

    conn = get_conn()

    cur = conn.cursor()

    cur.execute("""

    SELECT
    created_at,
    "result",
    comment

    FROM rounds

    ORDER BY id DESC

    LIMIT 1

    """)

    row = cur.fetchone()

    cur.close()

    conn.close()

    if row is None:

        return None

    created_at, result_json, comment = row

    if isinstance(result_json, str):
        result = json.loads(result_json)
    else:
        result = result_json

    text = f"📅 {created_at}\\n\\n"

    for name, amount in result.items():

        sign = "+" if amount >= 0 else ""

        text += f"{name}: {sign}{amount} บาท\\n"

    text += f"\\n📝 หมายเหตุ: {comment}"

    return text
