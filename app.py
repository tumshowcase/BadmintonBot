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
    # Separate people who owe and people who are owed
    debtors = {name: -balance for name, balance in balances if balance < 0}
    creditors = {name: balance for name, balance in balances if balance > 0}

    transactions = []

    # Handle "วี" and "พร" as a single entity if both are present
    # The logic below ensures that if both V and Porn are debtors, their total debt is assigned to V
    # Similarly, if both are creditors, their total credit is assigned to V
    # If one is a debtor and the other is a creditor, their net balance is assigned to V

    v_porn_balance = 0
    if "วี" in debtors: # if V owes money
        v_porn_balance -= debtors["วี"]
        del debtors["วี"]
    elif "วี" in creditors: # if V is owed money
        v_porn_balance += creditors["วี"]
        del creditors["วี"]

    if "พร" in debtors: # if Porn owes money
        v_porn_balance -= debtors["พร"]
        del debtors["พร"]
    elif "พร" in creditors: # if Porn is owed money
        v_porn_balance += creditors["พร"]
        del creditors["พร"]

    if v_porn_balance != 0:
        if v_porn_balance < 0:
            debtors["วี"] = -v_porn_balance
        else:
            creditors["วี"] = v_porn_balance

    # Minimize transactions
    debtors_list = sorted(debtors.items(), key=lambda item: item[1], reverse=True)
    creditors_list = sorted(creditors.items(), key=lambda item: item[1], reverse=True)

    while debtors_list and creditors_list:
        debtor_name, debtor_amount = debtors_list.pop(0)
        creditor_name, creditor_amount = creditors_list.pop(0)

        transfer_amount = min(debtor_amount, creditor_amount)

        transactions.append(f"- {debtor_name} โอนให้ {creditor_name} จำนวน {transfer_amount} บาท")

        debtor_amount -= transfer_amount
        creditor_amount -= transfer_amount

        if debtor_amount > 0:
            debtors_list.insert(0, (debtor_name, debtor_amount))
        if creditor_amount > 0:
            creditors_list.insert(0, (creditor_name, creditor_amount))

    if not transactions:
        return "💸 สรุปการโอนเงินเคลียร์หนี้:\nไม่มีการโอนเงินที่จำเป็น"

    return "💸 สรุปการโอนเงินเคลียร์หนี้:\n" + "\n".join(transactions)


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

    if text.lower() == "คำสั่ง":

        reply_text = (
            "คำสั่ง\n\n"
            "คิดเงิน\n"
            "ยอดทั้งหมด\n"
            "รอบล่าสุด\n"
            "เคลียร์หนี้\n"
            "reset balance"
        )

    elif text.lower() == "no":

        user_sessions[user_id] = {}

        reply_text = "ล้าง flow ปัจจุบันแล้ว"

    elif text.lower() == "reset balance":

        reset_all_balances()

        reply_text = "ล้างยอดสะสมทั้งหมดแล้ว"

    elif text.lower() == "ยอดทั้งหมด":

        balances = get_all_balances()

        reply_text = "ยอดสะสมทั้งหมด\n\n"

        for name, balance in balances:
            reply_text += f"{name}: {balance} บาท\n"

    elif text.lower() == "เคลียร์หนี้":

        reply_text = build_debt_minimization_text(get_all_balances())

    elif text.lower() == "รอบล่าสุด":

        latest = get_latest_round()

        if latest is None:
            reply_text = "ยังไม่มีข้อมูล"

        else:
            reply_text = latest

    elif text.lower() == "คิดเงิน":

        user_sessions[user_id] = {
            "step": "player_count"
        }

        reply_text = (
            "🏸 วันนี้มีกี่คน?\n\n"
            "กรุณาพิมพ์เป็นตัวเลข"
        )

    elif text.lower() == "จ่ายเงิน":

        user_sessions[user_id] = {
            "step": "wait_for_payment"
        }

        reply_text = (
            "พิมพ์รูปแบบ: [ใคร] จ่าย [ใคร] [เท่าไร]\n"
            "เช่น: วี จ่าย ตั้ม 100\n"
            "(พิมพ์ no เพื่อยกเลิก)"
        )

    elif session.get("step") == "wait_for_payment":

        parts = text.split()

        if len(parts) == 4 and parts[1] in ["จ่าย", "โอน"]:
            payer = parts[0]
            payee = parts[2]
            amount_str = parts[3]

            if payer not in default_members or payee not in default_members:
                reply_text = (
                    "❌ ชื่อไม่ถูกต้อง กรุณาใช้ชื่อ: ตั้ม, วี, พร, อ๊ะ, หนุ่ม\n"
                    "(พิมพ์ no เพื่อยกเลิก)"
                )
            elif not amount_str.isdigit():
                reply_text = "⚠️ จำนวนเงินต้องเป็นตัวเลขเท่านั้น\n(พิมพ์ no เพื่อยกเลิก)"
            else:
                session["payment_payer"] = payer
                session["payment_payee"] = payee
                session["payment_amount"] = int(amount_str)
                session["step"] = "confirm_payment"

                reply_text = (
                    f"❓ {payer} จ่ายให้ {payee} {amount_str} บาท\n"
                    "(พิมพ์ ok เพื่อยืนยัน / พิมพ์ no เพื่อยกเลิก)"
                )
        else:
            reply_text = (
                "⚠️ รูปแบบไม่ถูกต้อง กรุณาพิมพ์ใหม่\n"
                "เช่น: วี จ่าย ตั้ม 100\n"
                "(พิมพ์ no เพื่อยกเลิก)"
            )

    elif session.get("step") == "confirm_payment":

        if text.lower() == "ok":
            payer = session["payment_payer"]
            payee = session["payment_payee"]
            amount = session["payment_amount"]

            # ระบบแปลงชื่อ พร เป็น วี อัตโนมัติเวลาบันทึกยอด
            db_payer = "วี" if payer == "พร" else payer
            db_payee = "วี" if payee == "พร" else payee

            try:
                process_payment(db_payer, db_payee, amount)
                balances = get_all_balances()

                reply_text = (
                    "✅ บันทึกการโอนเงินเรียบร้อย\n"
                    f"💸 {payer} โอนให้ {payee} จำนวน {amount} บาท\n\n"
                    "🏦 ยอดสะสมล่าสุด\n"
                    "━━━━━━━━━━━━\n"
                    f"{build_balance_text(balances)}"
                )
                user_sessions[user_id] = {}
            except Exception as e:
                reply_text = "❌ เกิดข้อผิดพลาดในการบันทึกข้อมูล กรุณาลองใหม่"
                user_sessions[user_id] = {}

        elif text.lower() == "no":
            user_sessions[user_id] = {}
            reply_text = "ยกเลิกรายการแล้ว"
        else:
            reply_text = "⚠️ พิมพ์ ok เพื่อยืนยัน หรือ no เพื่อยกเลิก"

    elif session.get("step") == "player_count":

        if not text.isdigit():

            reply_text = "กรุณาพิมพ์เป็นตัวเลขเท่านั้น"

        else:

            count = int(text)

            if count <= 0 or count > 15:

                reply_text = (
                    "กรุณาเลือก 1-15 คน"
                )

            else:

                session["player_count"] = count

                session["step"] = "choose_players"

                reply_text = (
                    "👥 เลือกผู้เล่น\n\n"
                    f"{build_player_list(default_members)}\n\n"
                    "เช่น: 1 2 3"
                )

    elif session.get("step") == "choose_players":
        try:
            numbers = text.split()
            selected_players = []
            allowed_guests = ["G1", "G2", "G3", "G4", "G5"]

            for n in numbers:
                val = n.upper()
                
                # 1. เช็กว่าเป็นขาจร (G) ไหม
                if val.startswith("G"):
                    if val not in allowed_guests:
                        raise Exception("guest_error")
                    if val in selected_players:
                        raise Exception("duplicate_error")
                    selected_players.append(val)
                    
                # 2. เช็กว่าเป็นตัวเลขสมาชิกหลักไหม
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
                reply_text = (
                    f"กรุณาเลือกให้ครบ {session['player_count']} คน "
                    f"(คุณระบุมา {len(selected_players)} คน)"
                )
            else:
                session["players"] = selected_players
                session["step"] = "court_cost"
                reply_text = "🏸 ค่าคอร์ท (บาท)"

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
                "ตัวอย่างที่ถูกต้อง: 1 2 3 G1 G2"
            )

    elif session.get("step") == "court_cost":

        if not text.isdigit():

            reply_text = "กรุณาพิมพ์จำนวนเงินเท่านั้น"

        else:

            session["court_cost"] = int(text)

            session["step"] = "shuttle_cost"

            reply_text = "🎾 ค่าลูก (บาท)"

    elif session.get("step") == "shuttle_cost":

        if not text.isdigit():

            reply_text = "กรุณาพิมพ์จำนวนเงินเท่านั้น"

        else:

            session["shuttle_cost"] = int(text)

            players = session["players"]

            session["step"] = "court_payer"

            reply_text = (
                "💳 ใครจ่ายค่าคอร์ท?\n\n"
                f"{build_player_list(players)}"
            )

    elif session.get("step") == "court_payer":

        if not text.isdigit():

            reply_text = (
                "กรุณาเลือกเลขให้ถูกต้อง\n\n"
                f"{build_player_list(session['players'])}"
            )

        else:

            index = int(text)

            players = session["players"]

            if index < 1 or index > len(players):

                reply_text = (
                    "กรุณาเลือกเลขให้ถูกต้อง\n\n"
                    f"{build_player_list(players)}"
                )

            else:

                session["court_payer"] = players[index - 1]

                session["step"] = "shuttle_payer"

                reply_text = (
                    "💳 ใครจ่ายค่าลูก?\n\n"
                    f"{build_player_list(players)}"
                )

    elif session.get("step") == "shuttle_payer":

        if not text.isdigit():

            reply_text = (
                "กรุณาเลือกเลขให้ถูกต้อง\n\n"
                f"{build_player_list(session['players'])}"
            )

        else:

            index = int(text)

            players = session["players"]

            if index < 1 or index > len(players):

                reply_text = (
                    "กรุณาเลือกเลขให้ถูกต้อง\n\n"
                    f"{build_player_list(players)}"
                )

            else:

                session["shuttle_payer"] = players[index - 1]

                session["step"] = "comment"

                reply_text = (
                    "📝 หมายเหตุ\n\n"
                    "ถ้าไม่มี พิมพ์ -"
                )

    elif session.get("step") == "comment":

        session["comment"] = text

        total = (
            session["court_cost"] +
            session["shuttle_cost"]
        )

        share = total // len(session["players"])

        summary = (
            "🏸 กรุณาตรวจสอบข้อมูล\n"
            "━━━━━━━━━━━━\n\n"
            f"👥 ผู้เล่น({len(session['players'])}คน)\n"
            f"{' • '.join(session['players'])}\n\n"
            "💸 ค่าใช้จ่าย\n"
            f"• ค่าคอร์ท: {session['court_cost']} บาท\n"
            f"• ค่าลูก: {session['shuttle_cost']} บาท\n"
            f"• รวมทั้งหมด: {total} บาท\n"
            f"• เฉลี่ยคนละ: {share} บาท\n\n"
            "💳 คนออกเงินก่อน\n"
            f"• ค่าคอร์ท: {session['court_payer']}\n"
            f"• ค่าลูก: {session['shuttle_payer']}\n\n"
            f"📝 หมายเหตุ: {session['comment']}\n\n"
            "✅ พิมพ์ ok เพื่อบันทึก\n"
            "↩️ พิมพ์ no เพื่อยกเลิก"
        )

        session["step"] = "confirm"

        reply_text = summary

    elif session.get("step") == "confirm":

        if text.lower() != "ok":

            reply_text = (
                "พิมพ์ ok เพื่อยืนยัน\n"
                "หรือ no เพื่อยกเลิก"
            )

        else:

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

                sign = "+" if amount >= 0 else ""

                result_lines.append(
                    f"{player}: {sign}{amount} บาท"
                )

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

                reply_text = (
                    "บันทึกไม่สำเร็จครับ ฐานข้อมูลมีปัญหาตอนบันทึกรอบ\n\n"
                    "ลองพิมพ์ ok อีกครั้งได้เลย หรือพิมพ์ no เพื่อยกเลิก"
                )

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

            balance_text = build_balance_text(balances)

            reply_text = (
                "✅ บันทึกเรียบร้อย\n"
                f"🕘 {now}\n\n"
                "🏸 สรุปค่าใช้จ่าย\n"
                "━━━━━━━━━━━━\n"
                f"{latest_round_text}\n\n"
                "🏦 ยอดสะสม\n"
                "━━━━━━━━━━━━\n"
                f"{balance_text}"
            )
            user_sessions[user_id] = {}

    else:

        # ถ้าไม่ใช่คำสั่งของบอท และไม่ได้ค้าง session อะไรอยู่ ให้จบการทำงานเงียบๆ ไม่ต้องตอบอะไร
        return "OK", 200

    with ApiClient(configuration) as api_client:

        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)