import os
from dotenv import load_dotenv

from flask import Flask, request

from linebot.v3 import WebhookHandler

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)

from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

from datetime import datetime, timedelta

from database import *

load_dotenv()

app = Flask(__name__)

configuration = Configuration(
    access_token=os.getenv("CHANNEL_ACCESS_TOKEN")
)

handler = WebhookHandler(
    os.getenv("CHANNEL_SECRET")
)

init_db()

user_sessions = {}

default_members = [
    "ตั้ม",
    "วี",
    "พร",
    "อ๊ะ",
    "หนุ่ม"
]


def thailand_time():
    return datetime.utcnow() + timedelta(hours=7)


def build_player_list(players):
    result = ""
    for i, name in enumerate(players, start=1):
        result += f"{i}. {name}\n"
    return result.strip()


def format_round_amount(amount):
    if amount >= 0:
        return f"+{amount} บาท"
    return f"-{abs(amount)} บาท"


def format_balance_amount(amount):
    if amount >= 0:
        return f"เครดิต +{amount} บาท"
    return f"ค้างจ่าย {abs(amount)} บาท"


def build_round_result_text(result):
    lines = []
    for name, amount in result.items():
        icon = "🟢" if amount >= 0 else "🔴"
        lines.append(f"{icon} {name}: {format_round_amount(amount)}")
    return "\n".join(lines)


def build_balance_text(balances):
    lines = []
    for i, (name, balance) in enumerate(balances, start=1):
        rank = f"{i}."
        icon = "🟢" if balance >= 0 else "🔴"
        lines.append(f"{rank} {icon} {name}: {format_balance_amount(balance)}")
    return "\n".join(lines)


def build_debt_minimization_text(balances):
    lines = []
    debtors = {name: -balance for name, balance in balances if balance < 0}
    creditors = {name: balance for name, balance in balances if balance > 0}

    transactions = []

    v_porn_balance = 0
    if "วี" in debtors: 
        v_porn_balance -= debtors["วี"]
        del debtors["วี"]
    elif "วี" in creditors: 
        v_porn_balance += creditors["วี"]
        del creditors["วี"]

    if "พร" in debtors: 
        v_porn_balance -= debtors["พร"]
        del debtors["พร"]
    elif "พร" in creditors: 
        v_porn_balance += creditors["พร"]
        del creditors["พร"]

    if v_porn_balance != 0:
        if v_porn_balance < 0:
            debtors["วี & พร"] = -v_porn_balance
        else:
            creditors["วี & พร"] = v_porn_balance

    debtors_list = sorted(debtors.items(), key=lambda item: item[1], reverse=True)
    creditors_list = sorted(creditors.items(), key=lambda item: item[1], reverse=True)

    while debtors_list and creditors_list:
        debtor_name, debtor_amount = debtors_list.pop(0)
        creditor_name, creditor_amount = creditors_list.pop(0)

        transfer_amount = min(debtor_amount, creditor_amount)
        transactions.append(f"💸 {debtor_name}  ➡️  {creditor_name} : {transfer_amount} บาท")

        debtor_amount -= transfer_amount
        creditor_amount -= transfer_amount

        if debtor_amount > 0:
            debtors_list.insert(0, (debtor_name, debtor_amount))
        if creditor_amount > 0:
            creditors_list.insert(0, (creditor_name, creditor_amount))

    if not transactions:
        return (
            "💡 แนะนำการโอนเงิน\n"
            "━━━━━━━━━━━━\n"
            "✅ ตอนนี้ทุกคนเคลียร์ยอดครบหมดแล้วครับ!"
        )

    return (
        "💡 แนะนำการโอนเงิน\n"
        "━━━━━━━━━━━━\n"
        + "\n".join(transactions) +
        "\n\n✨ (จ่ายตามนี้ง่ายสุด)"
    )


@app.route("/")
def home():
    return "Badminton Bot Running"


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    handler.handle(body, signature)
    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    reply_text = ""

    if user_id not in user_sessions:
        user_sessions[user_id] = {}

    session = user_sessions[user_id]

    # ==========================================
    # ระบบคีย์ลัดอัจฉริยะ (ตัวเลข 1-7 ทำงานเฉพาะหน้าเมนู)
    # ==========================================
    if session.get("step") == "waiting_menu_choice":
        if text == "1":
            text = "/คิดเงิน"
            user_sessions[user_id] = {}
            session = {}
        elif text == "2":
            text = "/จ่ายเงิน"
            user_sessions[user_id] = {}
            session = {}
        elif text == "3":
            text = "/ยอดสะสม"
            user_sessions[user_id] = {}
            session = {}
        elif text == "4":
            text = "/แนะนำจ่าย"
            user_sessions[user_id] = {}
            session = {}
        elif text == "5":
            text = "/รอบล่าสุด"
            user_sessions[user_id] = {}
            session = {}
        elif text == "6":
            text = "/ประวัติย้อนหลัง"
            user_sessions[user_id] = {}
            session = {}
        elif text == "7":
            text = "/ยกเลิกรอบล่าสุด"
            user_sessions[user_id] = {}
            session = {}
        elif text == "0" or text.lower() in ["cancel", "/cancel", "ยกเลิก", "/ยกเลิก", "no", "/no", "ออก", "/ออก"]:
            text = "/cancel"
        else:
            user_sessions[user_id] = {}
            session = {}
            return "OK", 200

    if text == "0" and session.get("step"):
        text = "/cancel"

    # ==========================================
    # หมวดคำสั่งหลัก
    # ==========================================
    if text.lower() in ["/เมนู", "/menu", "เมนู", "menu"]:
        user_sessions[user_id] = {"step": "waiting_menu_choice"}
        reply_text = (
            "🏸 ระบบจัดการก๊วนแบด\n"
            "━━━━━━━━━━━━\n"
            "กด 1 : 🏸 คิดเงิน\n"
            "กด 2 : 💸 จ่ายเงิน\n"
            "กด 3 : 🏦 ยอดสะสม\n"
            "กด 4 : 💡 แนะนำจ่าย\n"
            "กด 5 : 🕘 รอบล่าสุด\n"
            "กด 6 : 📜 ประวัติย้อนหลัง\n"
            "กด 7 : ⏪ ยกเลิกรอบล่าสุด\n"
            "กด 0 : 🔴 ออก\n\n"
            "👉 พิมพ์ตัวเลขเพื่อสั่งงานได้เลยครับ"
        )

    elif text.lower() in ["cancel", "/cancel", "ยกเลิก", "/ยกเลิก", "no", "/no", "ออก", "/ออก"]:
        step = session.get("step")
        if step or text.lower() in ["/cancel", "/ยกเลิก", "/ออก"]:
            user_sessions[user_id] = {}
            if step in ["waiting_menu_choice", "waiting_history_choice", "viewing_history_detail", "confirm_undo"]:
                reply_text = (
                    "🔴 ออกจากเมนูเรียบร้อย\n"
                    "ไว้เจอกันใหม่รอบหน้าครับ Bye! 👋🏸"
                )
            else:
                reply_text = "❌ ยกเลิกรายการเรียบร้อยแล้ว"
        else:
            return "OK", 200

    elif text.lower() == "/reset balance":
        reset_all_balances()
        reply_text = "ล้างยอดสะสมทั้งหมดแล้ว"

    elif text.lower() == "/ยอดสะสม":
        balances = get_all_balances()
        balance_text = build_balance_text(balances)
        debt_text = build_debt_minimization_text(balances)
        reply_text = (
            "🏦 ยอดสะสม\n"
            "━━━━━━━━━━━━\n"
            f"{balance_text}\n\n"
            f"{debt_text}"
        )

    elif text.lower() == "/แนะนำจ่าย":
        reply_text = build_debt_minimization_text(get_all_balances())

    elif text.lower() == "/รอบล่าสุด":
        latest = get_latest_round()
        if latest is None:
            reply_text = "ยังไม่มีข้อมูล"
        else:
            reply_text = latest

    elif text.lower() == "/ยกเลิกรอบล่าสุด":
        latest_text = get_latest_round()
        if not latest_text:
            reply_text = "ไม่มีบิลให้ยกเลิกครับ"
        else:
            user_sessions[user_id] = {"step": "confirm_undo"}
            preview_text = latest_text.replace("🕘 บิลรอบล่าสุด", "📌 บิลที่จะถูกยกเลิก")
            reply_text = (
                "⚠️ คุณต้องการยกเลิกบิลนี้ใช่หรือไม่?\n"
                "━━━━━━━━━━━━\n"
                f"{preview_text}\n\n"
                "🚨 คำเตือน: ยอดสะสมของทุกคนจะถูกหักออกและกลับไปเป็นค่าเดิม\n\n"
                "👉 พิมพ์ ok เพื่อยืนยัน\n"
                "🔴 พิมพ์ 0 เพื่อออก"
            )

    elif text.lower() == "/ประวัติย้อนหลัง":
        recent_rounds = get_recent_rounds(5)
        if not recent_rounds:
            reply_text = "ยังไม่มีประวัติการเล่นครับ"
            user_sessions[user_id] = {}
        else:
            user_sessions[user_id] = {
                "step": "waiting_history_choice",
                "recent_rounds": recent_rounds
            }
            lines = ["📜 เลือกดูประวัติย้อนหลัง", "━━━━━━━━━━━━"]
            for i, r in enumerate(recent_rounds, start=1):
                cmt = r['comment'] if r['comment'] != '-' else 'ไม่มี'
                lines.append(f"กด {i} : 📅 {r['time_str']} ({cmt})")
            
            lines.append("\n👉 พิมพ์ตัวเลขเพื่อดูรายละเอียด")
            lines.append("กด 0 : 🔴 ออก")
            reply_text = "\n".join(lines)

    elif text.lower() == "/คิดเงิน":
        user_sessions[user_id] = {"step": "player_count"}
        reply_text = (
            "🏸 วันนี้มีกี่คน?\n\n"
            "กรุณาพิมพ์เป็นตัวเลข\n"
            "(พิมพ์ 0 เพื่อยกเลิก)"
        )

    elif text.lower() == "/จ่ายเงิน":
        user_sessions[user_id] = {"step": "wait_for_payment"}
        reply_text = (
            "💸 แจ้งโอนเงินตัดยอด\n"
            "━━━━━━━━━━━━\n"
            "👉 พิมพ์ตามรูปแบบนี้ครับ:\n"
            "[ใคร] จ่าย [ใคร] [จำนวนเงิน]\n\n"
            "📝 ตัวอย่าง: วี จ่าย ตั้ม 100\n\n"
            "❌ พิมพ์ 0 เพื่อยกเลิก"
        )

    # ==========================================
    # หมวดการทำงานใน Session (พิมพ์ปกติได้เลย)
    # ==========================================
    
    # --- ส่วนของการยืนยันยกเลิกรอบล่าสุด ---
    elif session.get("step") == "confirm_undo":
        if text.lower() == "ok":
            success = undo_latest_round()
            if success:
                reply_text = "✅ ยกเลิกรอบล่าสุดและคืนยอดเรียบร้อยแล้ว"
            else:
                reply_text = "❌ ไม่พบข้อมูลบิลให้ยกเลิกครับ"
            user_sessions[user_id] = {}
        else:
            reply_text = "⚠️ พิมพ์ ok เพื่อยืนยัน หรือพิมพ์ 0 เพื่อออกครับ"

    # --- ส่วนของเมนูประวัติย้อนหลัง ---
    elif session.get("step") == "waiting_history_choice":
        if text.isdigit():
            choice = int(text)
            recent_rounds = session.get("recent_rounds", [])
            
            if 1 <= choice <= len(recent_rounds):
                round_id = recent_rounds[choice - 1]["id"]
                detail_text = get_round_by_id(round_id)
                
                if detail_text:
                    session["step"] = "viewing_history_detail"
                    reply_text = (
                        detail_text + 
                        "\n\n━━━━━━━━━━━━\n"
                        "กด 9 : 🔙 ย้อนกลับหน้าเลือกวัน\n"
                        "กด 0 : 🔴 ออก"
                    )
                else:
                    reply_text = "❌ ไม่พบข้อมูลรอบนี้ กรุณาลองใหม่\n(กด 0 เพื่อออก)"
            else:
                reply_text = f"⚠️ กรุณาเลือกตัวเลข 1-{len(recent_rounds)}\n(กด 0 เพื่อออก)"
        else:
            reply_text = "⚠️ กรุณาพิมพ์เป็นตัวเลข\n(กด 0 เพื่อออก)"
            
    elif session.get("step") == "viewing_history_detail":
        if text == "9":
            recent_rounds = get_recent_rounds(5)
            session["step"] = "waiting_history_choice"
            session["recent_rounds"] = recent_rounds
            
            lines = ["📜 เลือกดูประวัติย้อนหลัง", "━━━━━━━━━━━━"]
            for i, r in enumerate(recent_rounds, start=1):
                cmt = r['comment'] if r['comment'] != '-' else 'ไม่มี'
                lines.append(f"กด {i} : 📅 {r['time_str']} ({cmt})")
            
            lines.append("\n👉 พิมพ์ตัวเลขเพื่อดูรายละเอียด")
            lines.append("กด 0 : 🔴 ออก")
            reply_text = "\n".join(lines)
        else:
            reply_text = "⚠️ พิมพ์ 9 เพื่อย้อนกลับ หรือพิมพ์ 0 เพื่อออกครับ"

    # --- ส่วนของการจ่ายเงิน ---
    elif session.get("step") == "wait_for_payment":
        parts = text.split()
        if len(parts) == 4 and parts[1] in ["จ่าย", "โอน"]:
            payer = parts[0]
            payee = parts[2]
            amount_str = parts[3]

            if payer not in default_members or payee not in default_members:
                reply_text = "❌ ชื่อไม่ถูกต้อง กรุณาใช้ชื่อ: ตั้ม, วี, พร, อ๊ะ, หนุ่ม\n(พิมพ์ 0 เพื่อยกเลิก)"
            else:
                check_payer = "วี" if payer == "พร" else payer
                check_payee = "วี" if payee == "พร" else payee

                if payer == payee:
                    reply_text = "⚠️ ไม่สามารถโอนเงินให้ตัวเองได้ครับ\n(พิมพ์ 0 เพื่อยกเลิก)"
                elif check_payer == check_payee:
                    reply_text = (
                        "⚠️ รายการนี้ไม่มีผลต่อยอดสะสม\n\n"
                        "เนื่องจาก วี และ พร ถูกนับเป็นครอบครัวเดียวกัน\n"
                        "(พิมพ์ 0 เพื่อยกเลิก)"
                    )
                elif not amount_str.isdigit() or int(amount_str) <= 0:
                    reply_text = "⚠️ จำนวนเงินต้องเป็นตัวเลขที่มากกว่า 0 เท่านั้น\n(พิมพ์ 0 เพื่อยกเลิก)"
                else:
                    session["payment_payer"] = payer
                    session["payment_payee"] = payee
                    session["payment_amount"] = int(amount_str)
                    session["step"] = "confirm_payment"
                    reply_text = (
                        f"❓ {payer} จ่ายให้ {payee} {amount_str} บาท\n\n"
                        "👉 พิมพ์ ok เพื่อยืนยัน\n"
                        "👉 พิมพ์ 0 เพื่อยกเลิก"
                    )
        else:
            reply_text = (
                "⚠️ รูปแบบไม่ถูกต้อง กรุณาพิมพ์ใหม่ครับ\n"
                "━━━━━━━━━━━━\n"
                "📝 ตัวอย่าง: วี จ่าย ตั้ม 100\n\n"
                "❌ พิมพ์ 0 เพื่อยกเลิก"
            )

    elif session.get("step") == "confirm_payment":
        if text.lower() == "ok":
            payer = session["payment_payer"]
            payee = session["payment_payee"]
            amount = session["payment_amount"]
            db_payer = "วี" if payer == "พร" else payer
            db_payee = "วี" if payee == "พร" else payee

            try:
                process_payment(db_payer, db_payee, amount)
                balances = get_all_balances()
                balance_text = build_balance_text(balances)
                debt_text = build_debt_minimization_text(balances)

                reply_text = (
                    "✅ บันทึกการโอนเงินเรียบร้อย\n"
                    f"💸 {payer} โอนให้ {payee} จำนวน {amount} บาท\n\n"
                    "🏦 ยอดสะสมล่าสุด\n"
                    "━━━━━━━━━━━━\n"
                    f"{balance_text}\n\n"
                    f"{debt_text}"
                )
                user_sessions[user_id] = {}
            except Exception as e:
                reply_text = "❌ เกิดข้อผิดพลาดในการบันทึกข้อมูล กรุณาลองใหม่"
                user_sessions[user_id] = {}
        else:
            reply_text = "⚠️ พิมพ์ ok เพื่อยืนยัน หรือพิมพ์ 0 เพื่อยกเลิก"

    # --- ส่วนของการคิดเงิน ---
    elif session.get("step") == "player_count":
        if not text.isdigit():
            reply_text = "กรุณาพิมพ์เป็นตัวเลขเท่านั้น (หรือพิมพ์ 0 เพื่อยกเลิก)"
        else:
            count = int(text)
            if count <= 0 or count > 15:
                reply_text = "กรุณาเลือก 1-15 คน"
            else:
                session["player_count"] = count
                session["step"] = "choose_players"
                reply_text = (
                    "👥 เลือกผู้เล่น\n\n"
                    f"{build_player_list(default_members)}\n\n"
                    "เช่น: 1 2 3\n"
                    "(พิมพ์ 0 เพื่อยกเลิก)"
                )

    elif session.get("step") == "choose_players":
        try:
            numbers = text.split()
            selected_players = []
            allowed_guests = ["G1", "G2", "G3", "G4", "G5"]

            for n in numbers:
                val = n.upper()
                if val.startswith("G"):
                    if val not in allowed_guests:
                        raise Exception("guest_error")
                    if val in selected_players:
                        raise Exception("duplicate_error")
                    selected_players.append(val)
                elif n.isdigit():
                    i = int(n)
                    if i < 1 or i > len(default_members):
                        raise Exception("index_error")
                    member_name = default_members[i - 1]
                    if member_name in selected_players:
                        raise Exception("duplicate_error")
                    selected_players.append(member_name)
                else:
                    raise Exception("format_error")

            if len(selected_players) != session["player_count"]:
                reply_text = f"กรุณาเลือกให้ครบ {session['player_count']} คน (คุณระบุมา {len(selected_players)} คน)"
            else:
                session["players"] = selected_players
                session["step"] = "court_cost"
                reply_text = "🏸 ค่าคอร์ท (บาท)\n(พิมพ์ 0 เพื่อยกเลิก)"
        except Exception as e:
            err = str(e)
            if err == "duplicate_error":
                alert_msg = "⚠️ ห้ามใส่ชื่อคนเล่นซ้ำกันครับ"
            elif err == "guest_error":
                alert_msg = "⚠️ ขาจรใช้ได้แค่ G1, G2, G3, G4, G5 เท่านั้นครับ"
            else:
                alert_msg = "⚠️ กรุณาพิมพ์รูปแบบให้ถูกต้อง"

            reply_text = (
                f"{alert_msg}\n\n"
                f"{build_player_list(default_members)}\n\n"
                "ตัวอย่างที่ถูกต้อง: 1 2 3 G1 G2\n"
                "(พิมพ์ 0 เพื่อยกเลิก)"
            )

    elif session.get("step") == "court_cost":
        if not text.isdigit():
            reply_text = "กรุณาพิมพ์จำนวนเงินเท่านั้น (หรือพิมพ์ 0 เพื่อยกเลิก)"
        else:
            session["court_cost"] = int(text)
            session["step"] = "court_payer"
            reply_text = (
                "💳 ใครจ่ายค่าคอร์ท?\n\n"
                f"{build_player_list(session['players'])}\n\n"
                "(พิมพ์เลขเพื่อเลือก / พิมพ์ 0 ยกเลิก)"
            )

    elif session.get("step") == "court_payer":
        if not text.isdigit():
            reply_text = f"กรุณาเลือกเลขให้ถูกต้อง\n\n{build_player_list(session['players'])}"
        else:
            index = int(text)
            players = session["players"]
            if index < 1 or index > len(players):
                reply_text = f"กรุณาเลือกเลขให้ถูกต้อง\n\n{build_player_list(players)}"
            else:
                session["court_payer"] = players[index - 1]
                session["step"] = "shuttle_cost"
                reply_text = "🎾 ค่าลูก (บาท)\n(พิมพ์ 0 เพื่อยกเลิก)"

    elif session.get("step") == "shuttle_cost":
        if not text.isdigit():
            reply_text = "กรุณาพิมพ์จำนวนเงินเท่านั้น (หรือพิมพ์ 0 เพื่อยกเลิก)"
        else:
            session["shuttle_cost"] = int(text)
            players = session["players"]
            session["step"] = "shuttle_payer"
            reply_text = (
                "💳 ใครจ่ายค่าลูก?\n\n"
                f"{build_player_list(players)}\n\n"
                "(พิมพ์เลขเพื่อเลือก / พิมพ์ 0 ยกเลิก)"
            )

    elif session.get("step") == "shuttle_payer":
        if not text.isdigit():
            reply_text = f"กรุณาเลือกเลขให้ถูกต้อง\n\n{build_player_list(session['players'])}"
        else:
            index = int(text)
            players = session["players"]
            if index < 1 or index > len(players):
                reply_text = f"กรุณาเลือกเลขให้ถูกต้อง\n\n{build_player_list(players)}"
            else:
                session["shuttle_payer"] = players[index - 1]
                
                has_guest = any(p.startswith("G") for p in players)
                if has_guest:
                    session["step"] = "guest_collector"
                    reply_text = (
                        "🙋‍♂️ ขาจร (Guest) จ่ายเงินให้ใคร?\n\n"
                        f"{build_player_list(players)}\n\n"
                        "(พิมพ์เลขเพื่อเลือก / พิมพ์ 0 ยกเลิก)"
                    )
                else:
                    session["step"] = "comment"
                    reply_text = "📝 หมายเหตุ\n\nถ้าไม่มี พิมพ์ -\n(พิมพ์ 0 เพื่อยกเลิก)"

    elif session.get("step") == "guest_collector":
        if not text.isdigit():
            reply_text = f"กรุณาเลือกเลขให้ถูกต้อง\n\n{build_player_list(session['players'])}"
        else:
            index = int(text)
            players = session["players"]
            if index < 1 or index > len(players):
                reply_text = f"กรุณาเลือกเลขให้ถูกต้อง\n\n{build_player_list(players)}"
            else:
                selected = players[index - 1]
                if selected.startswith("G"):
                    reply_text = (
                        "⚠️ ขาจรเก็บเงินเข้าตัวเองไม่ได้ครับ กรุณาเลือกสมาชิกหลัก\n\n"
                        f"{build_player_list(players)}"
                    )
                else:
                    session["guest_collector"] = selected
                    session["step"] = "comment"
                    reply_text = "📝 หมายเหตุ\n\nถ้าไม่มี พิมพ์ -\n(พิมพ์ 0 เพื่อยกเลิก)"

    elif session.get("step") == "comment":
        session["comment"] = text
        total = session["court_cost"] + session["shuttle_cost"]
        share = total // len(session["players"])

        summary = (
            "🏸 กรุณาตรวจสอบข้อมูล\n"
            "━━━━━━━━━━━━\n\n"
            f"👥 ผู้เล่น ({len(session['players'])} คน)\n"
            f"{' • '.join(session['players'])}\n\n"
            "💸 ค่าใช้จ่าย\n"
            f"• ค่าคอร์ท: {session['court_cost']} บาท\n"
            f"• ค่าลูก: {session['shuttle_cost']} บาท\n"
            f"• รวมทั้งหมด: {total} บาท\n"
            f"• เฉลี่ยคนละ: {share} บาท\n\n"
            "💳 คนออกเงินก่อน\n"
            f"• ค่าคอร์ท: {session['court_payer']}\n"
            f"• ค่าลูก: {session['shuttle_payer']}\n"
        )
        
        if "guest_collector" in session:
            summary += f"• รับเงินขาจร: {session['guest_collector']}\n"

        summary += (
            f"\n📝 หมายเหตุ: {session['comment']}\n\n"
            "✅ พิมพ์ ok เพื่อบันทึก\n"
            "❌ พิมพ์ 0 เพื่อยกเลิก"
        )

        session["step"] = "confirm"
        reply_text = summary

    elif session.get("step") == "confirm":
        if text.lower() == "ok":
            players = session["players"]
            court_cost = session["court_cost"]
            shuttle_cost = session["shuttle_cost"]
            court_payer = session["court_payer"]
            shuttle_payer = session["shuttle_payer"]
            comment = session["comment"]
            total = court_cost + shuttle_cost
            share = total // len(players)

            result_lines = []
            round_result = {}

            for player in players:
                amount = -share
                if player == court_payer:
                    amount += court_cost
                if player == shuttle_payer:
                    amount += shuttle_cost
                round_result[player] = amount

            if "guest_collector" in session:
                guest_debt = 0
                collector = session["guest_collector"]
                for p, amt in round_result.items():
                    if p.startswith("G"):
                        guest_debt += amt
                round_result[collector] += guest_debt

            try:
                save_round_with_balances(
                    players,
                    court_cost,
                    shuttle_cost,
                    court_payer,
                    shuttle_payer,
                    share,
                    round_result,
                    comment
                )
                balances = get_all_balances()

            except Exception:
                app.logger.exception("Failed to save badminton round")
                reply_text = "บันทึกไม่สำเร็จครับ ฐานข้อมูลมีปัญหาตอนบันทึกรอบ\n\nลองพิมพ์ ok อีกครั้งได้เลย หรือพิมพ์ 0 เพื่อยกเลิก"
                with ApiClient(configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=reply_text)]
                        )
                    )
                return

            now = thailand_time().strftime("%d/%m/%Y %H:%M")
            latest_round_text = build_round_result_text(round_result)
            
            if "guest_collector" in session:
                latest_round_text += f"\n\n*(ยอดของ {session['guest_collector']} ได้รวมการรับเงินสดจากขาจรแล้ว)*"

            balance_text = build_balance_text(balances)
            debt_text = build_debt_minimization_text(balances)

            reply_text = (
                "✅ บันทึกเรียบร้อย\n"
                f"🕘 {now}\n\n"
                "🏸 สรุปค่าใช้จ่าย\n"
                "━━━━━━━━━━━━\n"
                f"{latest_round_text}\n\n"
                "🏦 ยอดสะสม\n"
                "━━━━━━━━━━━━\n"
                f"{balance_text}\n\n"
                f"{debt_text}"
            )
            user_sessions[user_id] = {}

        else:
            reply_text = "⚠️ พิมพ์ ok เพื่อยืนยัน หรือพิมพ์ 0 เพื่อยกเลิก"

    else:
        return "OK", 200

    if reply_text:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
    
    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)