import requests, time, os
from bs4 import BeautifulSoup

FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MY_COOKIE = os.getenv("MY_COOKIE")
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

def kirim_notif(member_name, num, country, msg):
    # Format Klik untuk Salin pake HTML <code>
    text = (
        f"📩 <b>SMS BARU!</b>\n\n"
        f"👤 <b>Nama :</b> {member_name}\n"
        f"📱 <b>Nomor :</b> <code>{num}</code>\n"
        f"🌍 <b>Negara :</b> {country}\n"
        f"💬 <b>Pesan :</b> {msg}"
    )
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': TELE_CHAT_ID, 'text': text, 'parse_mode': 'HTML'})

def cari_pemilik_nomor(nomor):
    # Cari di Firebase siapa yang pegang nomor ini
    members = requests.get(f"{FIREBASE_URL}/members.json").json()
    if members:
        for m_id, data in members.items():
            active = data.get('active_numbers', {})
            for k, v in active.items():
                if nomor in str(v.get('number')):
                    return m_id, v.get('name', 'Unknown')
    return "Admin", "Unknown Country"

def run_calltime():
    s = requests.Session()
    s.headers.update({'Cookie': MY_COOKIE})
    done_ids = []
    while True:
        try:
            res = s.get(f"https://www.calltimepanel.com/yeni/SMS/?_={int(time.time()*1000)}", timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.select('table tbody tr') or soup.select('table tr')
            for r in rows:
                c = r.find_all('td')
                if len(c) < 4: continue
                num = c[1].text.strip().split('-')[-1].strip()
                msg = c[2].text.strip()
                uid = f"{num}_{msg[:10]}"
                if uid not in done_ids:
                    member_id, country = cari_pemilik_nomor(num)
                    requests.post(f"{FIREBASE_URL}/messages.json", json={"liveSms": num, "messageContent": msg})
                    kirim_notif(member_id, num, country, msg)
                    done_ids.append(uid)
            time.sleep(3)
        except: time.sleep(5)
