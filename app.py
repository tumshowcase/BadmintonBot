import os

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
            "reset\n"
            "reset balance"
        )

    elif text.lower() == "reset":

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

    elif session.get("step") == "player_count":

        if not text.isdigit():

            reply_text = "กรุณาพิมพ์เป็นตัวเลขเท่านั้น"

        else:

            count = int(text)

            if count <= 0 or count > len(default_members):

                reply_text = (
                    f"กรุณาเลือก 1-{len(default_members)} คน"
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

            indexes = [int(n) for n in numbers]

            selected_players = []

            for i in indexes:

                if i < 1 or i > len(default_members):
                    raise Exception()

                selected_players.append(default_members[i - 1])

            if len(selected_players) != session["player_count"]:

                reply_text = (
                    f"กรุณาเลือก {session['player_count']} คน"
                )

            else:

                session["players"] = selected_players

                session["step"] = "court_cost"

                reply_text = "🏸 ค่าคอร์ท (บาท)"

        except:

            reply_text = (
                "กรุณาเลือกเลขให้ถูกต้อง\n\n"
                f"{build_player_list(default_members)}"
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
            "📋 กรุณาตรวจสอบข้อมูล\n\n"
            f"👥 ผู้เล่น: {', '.join(session['players'])}\n\n"
            f"🏸 ค่าคอร์ท: {session['court_cost']} บาท\n"
            f"🎾 ค่าลูก: {session['shuttle_cost']} บาท\n\n"
            f"💳 คนจ่ายค่าคอร์ท: {session['court_payer']}\n"
            f"💳 คนจ่ายค่าลูก: {session['shuttle_payer']}\n\n"
            f"📝 หมายเหตุ: {session['comment']}\n\n"
            f"📊 รวมทั้งหมด: {total} บาท\n"
            f"👤 คนละ: {share} บาท\n\n"
            "พิมพ์ ok เพื่อยืนยัน\n"
            "หรือพิมพ์ reset เพื่อยกเลิก"
        )

        session["step"] = "confirm"

        reply_text = summary

    elif session.get("step") == "confirm":

        if text.lower() != "ok":

            reply_text = (
                "พิมพ์ ok เพื่อยืนยัน\n"
                "หรือ reset เพื่อยกเลิก"
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

                update_balance(player, amount)

                round_result[player] = amount

                sign = "+" if amount >= 0 else ""

                result_lines.append(
                    f"{player}: {sign}{amount} บาท"
                )

            save_round(
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

            now = thailand_time().strftime("%d/%m/%Y %H:%M")

            latest_round_text = ""

            for player, amount in round_result.items():

                icon = "🟢" if amount >= 0 else "🔴"

                latest_round_text += (
                    f"{player.ljust(8)} "
                    f"{icon} {amount:+}\n"
                )

            balance_text = ""

            rank_icons = [
                "🥇",
                "🥈",
                "🥉",
                "4️⃣",
                "5️⃣",
                "6️⃣",
                "7️⃣",
                "8️⃣"
            ]

            for i, (name, balance) in enumerate(balances):

                icon = "🟢" if balance >= 0 else "🔴"

                rank = (
                    rank_icons[i]
                    if i < len(rank_icons)
                    else f"{i+1}."
                )

                balance_text += (
                    f"{rank} "
                    f"{name.ljust(8)} "
                    f"{icon} {balance:+}\n"
                )

            reply_text = (
                "✅ บันทึกรอบเรียบร้อย\n\n"
                f"📅 {now}\n\n"
                "📊 รอบล่าสุด\n\n"
                f"{latest_round_text}\n"
                "━━━━━━━━━━━━━━\n\n"
                "📈 ยอดสะสมทั้งหมด\n\n"
                f"{balance_text}"
            )

    else:

        reply_text = (
            "พิมพ์ 'คำสั่ง' เพื่อดูเมนู"
        )

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
