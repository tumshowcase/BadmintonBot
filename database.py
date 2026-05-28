import os
import psycopg2
import json

DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():

    return psycopg2.connect(DATABASE_URL)


def init_db():


    conn = get_conn()

    cur = conn.cursor()

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

    conn.commit()

    cur.close()

    conn.close()

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

    return rows

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
    result,
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

    json.dumps(players, ensure_ascii=False),

    court_cost,

    shuttle_cost,

    court_payer,

    shuttle_payer,

    share,

    json.dumps(result, ensure_ascii=False),

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
    result,
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

    result = json.loads(result_json)

    text = f"📅 {created_at}\\n\\n"

    for name, amount in result.items():

        sign = "+" if amount >= 0 else ""

        text += f"{name}: {sign}{amount} บาท\\n"

    text += f"\\n📝 หมายเหตุ: {comment}"

    return text