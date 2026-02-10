from curl_cffi import requests as curl_req
import requests as normal_req
import time, os, re, threading

FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MNIT_COOKIE = os.getenv("MNIT_COOKIE")
MNIT_TOKEN = os.getenv("MNIT_TOKEN")
MY_UA = os.getenv("MY_UA")
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

def kirim_notif(member_name, num, country, msg):
    # OTP dibuat supaya bisa diklik (Monospace)
    # Cari angka OTP di dalam pesan
    otp = re.search(r'\d{4,8}', msg)
    if otp:
        msg = msg.replace(otp.group(0), f"<code>{otp.group(0)}</code>")

    text = (
        f"📩 <b>SMS BARU!</b>\n\n"
        f"👤 <b>Nama :</b> {member_name}\n"
        f"📱 <b>Nomor :</b> <code>{num}</code>\n"
        f"🌍 <b>Negara :</b> {country}\n"
        f"💬 <b>Pesan :</b> {msg}"
    )
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    normal_req.post(url, data={'chat_id': TELE_CHAT_ID, 'text': text, 'parse_mode': 'HTML'})

def cari_pemilik(nomor):
    m_data = normal_req.get(f"{FIREBASE_URL}/members.json").json()
    if m_data:
        for m_id, val in m_data.items():
            active = val.get('active_numbers', {})
            for k, v in active.items():
                if nomor in str(v.get('number')):
                    return m_id, v.get('name', 'X-MNIT')
    return "Admin", "X-MNIT"

def run_xmnit():
    done_ids = []
    headers = {'cookie': MNIT_COOKIE,'mauthtoken': MNIT_TOKEN,'user-agent': MY_UA}
    while True:
        for tgl in [time.strftime("%Y-%m-%d"), time.strftime("%Y-%m-%d", time.localtime(time.time()-86400))]:
            url = f"https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info?date={tgl}&page=1&search=&status="
            try:
                res = curl_req.get(url, headers=headers, impersonate="chrome", timeout=30)
                items = res.json().get('data', {}).get('data', [])
                for item in items:
                    num, code = item.get('copy'), item.get('code')
                    if num and code:
                        clean_code = re.sub('<[^<]+?>', '', str(code)).strip()
                        uid = f"{num}_{clean_code}"
                        if uid not in done_ids:
                            m_id, c_name = cari_pemilik(num)
                            full_msg = f"Your Facebook code is {clean_code}"
                            normal_req.post(f"{FIREBASE_URL}/messages.json", json={"liveSms": num, "messageContent": full_msg})
                            kirim_notif(m_id, num, c_name, full_msg)
                            done_ids.append(uid)
            except: pass
        time.sleep(4)
