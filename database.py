import os
import psycopg2
import json
from contextlib import closing
from psycopg2.extras import Json
from datetime import datetime, timedelta

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
                cur.execute("""
CREATE TABLE IF NOT EXISTS payment_history(
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    payer TEXT,
    payee TEXT,
    amount INTEGER
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
                    try:
                        cur.execute(sql)
                    except Exception:
                        pass

                cur.execute("""
CREATE UNIQUE INDEX IF NOT EXISTS balances_name_unique
ON balances(name)
""")
    print("database ready")

def get_all_balances():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT name, balance FROM balances ORDER BY balance DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

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

    grouped_balances.sort(key=lambda x: x[1], reverse=True)
    return grouped_balances

def process_payment(payer, payee, amount):
    with closing(get_conn()) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO balances(name, balance) VALUES (%s, %s)
                    ON CONFLICT(name) DO UPDATE SET balance = balances.balance + %s
                """, (payer, amount, amount))
                cur.execute("""
                    INSERT INTO balances(name, balance) VALUES (%s, %s)
                    ON CONFLICT(name) DO UPDATE SET balance = balances.balance - %s
                """, (payee, -amount, amount))
                cur.execute("""
                    INSERT INTO payment_history(payer, payee, amount)
                    VALUES (%s, %s, %s)
                """, (payer, payee, amount))

def update_balance(name, amount):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
INSERT INTO balances(name, balance) VALUES(%s, %s)
ON CONFLICT(name) DO UPDATE SET balance = balances.balance + %s
""",(name, amount, amount))
    conn.commit()
    cur.close()
    conn.close()

def save_round_with_balances(players, court_cost, shuttle_cost, court_payer, shuttle_payer, share, result, comment):
    with closing(get_conn()) as conn:
        with conn:
            with conn.cursor() as cur:
                for name, amount in result.items():
                    if name.upper().startswith("G"):
                        continue
                    cur.execute("""
INSERT INTO balances(name, balance) VALUES(%s, %s)
ON CONFLICT(name) DO UPDATE SET balance = balances.balance + %s
""",(name, amount, amount))

                cur.execute("""
INSERT INTO rounds(
    players, court_cost, shuttle_cost, court_payer, shuttle_payer, share, "result", comment
) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)
""",(
    json_value(players), court_cost, shuttle_cost, court_payer, shuttle_payer, share, json_value(result), comment
))

def reset_all_balances():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE balances SET balance = 0")
    conn.commit()
    cur.close()
    conn.close()

def get_latest_round():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT created_at, players, court_cost, shuttle_cost, court_payer, shuttle_payer, share, "result", comment
    FROM rounds ORDER BY id DESC LIMIT 1
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row is None:
        return None

    created_at, players_json, court_cost, shuttle_cost, court_payer, shuttle_payer, share, result_json, comment = row
    players = json.loads(players_json) if isinstance(players_json, str) else players_json
    result = json.loads(result_json) if isinstance(result_json, str) else result_json

    if isinstance(created_at, datetime):
        local_time = created_at + timedelta(hours=7)
        time_str = local_time.strftime("%d/%m/%Y %H:%M")
    else:
        try:
            time_obj = datetime.strptime(str(created_at).split('.')[0], "%Y-%m-%d %H:%M:%S")
            local_time = time_obj + timedelta(hours=7)
            time_str = local_time.strftime("%d/%m/%Y %H:%M")
        except:
            time_str = str(created_at).split('.')[0]

    total = court_cost + shuttle_cost
    text = (
        "🕘 บิลรอบล่าสุด\n"
        "━━━━━━━━━━━━\n"
        f"📅 {time_str}\n\n"
        f"👥 ผู้เล่น ({len(players)} คน)\n"
        f"{' • '.join(players)}\n\n"
        "💸 ค่าใช้จ่าย\n"
        f"• ค่าคอร์ท: {court_cost} บาท\n"
        f"• ค่าลูก: {shuttle_cost} บาท\n"
        f"• รวมทั้งหมด: {total} บาท\n"
        f"• เฉลี่ยคนละ: {share} บาท\n\n"
        "💳 คนออกเงินก่อน\n"
        f"• ค่าคอร์ท: {court_payer}\n"
        f"• ค่าลูก: {shuttle_payer}\n\n"
        "🔄 สรุปยอด\n"
    )
    for name, amount in result.items():
        icon = "🟢" if amount >= 0 else "🔴"
        sign = "+" if amount >= 0 else ""
        text += f"{icon} {name}: {sign}{amount} บาท\n"
    text += f"\n📝 หมายเหตุ: {comment}"
    return text

def get_recent_rounds(limit=5):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT id, created_at, comment
    FROM rounds
    ORDER BY id DESC
    LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    results = []
    for row in rows:
        round_id, created_at, comment = row
        if isinstance(created_at, datetime):
            local_time = created_at + timedelta(hours=7)
            time_str = local_time.strftime("%d/%m/%Y %H:%M")
        else:
            try:
                time_obj = datetime.strptime(str(created_at).split('.')[0], "%Y-%m-%d %H:%M:%S")
                local_time = time_obj + timedelta(hours=7)
                time_str = local_time.strftime("%d/%m/%Y %H:%M")
            except:
                time_str = str(created_at).split('.')[0]
        results.append({"id": round_id, "time_str": time_str, "comment": comment})
    return results

def get_round_by_id(round_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT created_at, players, court_cost, shuttle_cost, court_payer, shuttle_payer, share, "result", comment
    FROM rounds WHERE id = %s
    """, (round_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row is None:
        return None

    created_at, players_json, court_cost, shuttle_cost, court_payer, shuttle_payer, share, result_json, comment = row
    players = json.loads(players_json) if isinstance(players_json, str) else players_json
    result = json.loads(result_json) if isinstance(result_json, str) else result_json

    if isinstance(created_at, datetime):
        local_time = created_at + timedelta(hours=7)
        time_str = local_time.strftime("%d/%m/%Y %H:%M")
    else:
        try:
            time_obj = datetime.strptime(str(created_at).split('.')[0], "%Y-%m-%d %H:%M:%S")
            local_time = time_obj + timedelta(hours=7)
            time_str = local_time.strftime("%d/%m/%Y %H:%M")
        except:
            time_str = str(created_at).split('.')[0]

    total = court_cost + shuttle_cost
    text = (
        f"📅 บิลวันที่ {time_str}\n"
        "━━━━━━━━━━━━\n"
        f"👥 ผู้เล่น ({len(players)} คน)\n"
        f"{' • '.join(players)}\n\n"
        "💸 ค่าใช้จ่าย\n"
        f"• ค่าคอร์ท: {court_cost} บาท\n"
        f"• ค่าลูก: {shuttle_cost} บาท\n"
        f"• รวมทั้งหมด: {total} บาท\n"
        f"• เฉลี่ยคนละ: {share} บาท\n\n"
        "💳 คนออกเงินก่อน\n"
        f"• ค่าคอร์ท: {court_payer}\n"
        f"• ค่าลูก: {shuttle_payer}\n\n"
        "🔄 สรุปยอด\n"
    )
    for name, amount in result.items():
        icon = "🟢" if amount >= 0 else "🔴"
        sign = "+" if amount >= 0 else ""
        text += f"{icon} {name}: {sign}{amount} บาท\n"
    text += f"\n📝 หมายเหตุ: {comment}"
    return text

def undo_latest_round():
    with closing(get_conn()) as conn:
        with conn:
            with conn.cursor() as cur:
                # 1. ดึงข้อมูลรอบล่าสุด
                cur.execute('SELECT id, "result" FROM rounds ORDER BY id DESC LIMIT 1')
                row = cur.fetchone()
                if not row:
                    return False
                
                round_id, result_json = row
                result = json.loads(result_json) if isinstance(result_json, str) else result_json

                # 2. คืนยอดสะสมให้ทุกคน (บวกกลับด้วยค่าที่เคยถูกหัก หรือหักด้วยค่าที่เคยได้)
                for name, amount in result.items():
                    if name.upper().startswith("G"):
                        continue
                    cur.execute("""
                        UPDATE balances SET balance = balance - %s WHERE name = %s
                    """, (amount, name))

                # 3. ลบบิลนั้นทิ้งไป
                cur.execute("DELETE FROM rounds WHERE id = %s", (round_id,))
                return True

def get_statistics():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*), SUM(court_cost), SUM(shuttle_cost), MIN(created_at) FROM rounds')
    stats = cur.fetchone()
    if not stats or stats[0] == 0:
        cur.close()
        conn.close()
        return None
    total_rounds, total_court, total_shuttle, first_date = stats
    
    cur.execute('SELECT players, share FROM rounds')
    rows = cur.fetchall()
    member_stats = {}
    for players_json, share in rows:
        # 🛠️ ป้องกัน Error: ตรวจสอบว่ามีข้อมูลรายชื่อผู้เล่นในบิลรอบนั้นๆ หรือไม่
        if not players_json:
            continue
            
        try:
            players = json.loads(players_json) if isinstance(players_json, str) else players_json
            if not players:
                continue
        except Exception:
            continue

        for p in players:
            if p.upper().startswith("G"):
                continue
            if p not in member_stats:
                member_stats[p] = {"count": 0, "total_paid": 0}
            member_stats[p]["count"] += 1
            member_stats[p]["total_paid"] += (share or 0)
            
    cur.close()
    conn.close()
    
    thai_first_date = first_date + timedelta(hours=7) if first_date else datetime.utcnow() + timedelta(hours=7)
    
    return {
        "total_rounds": total_rounds,
        "total_court": total_court or 0,
        "total_shuttle": total_shuttle or 0,
        "first_date": thai_first_date.strftime("%d/%m/%Y"),
        "member_stats": member_stats
    }