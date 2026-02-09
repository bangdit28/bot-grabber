import requests, time, os, sys
from bs4 import BeautifulSoup

# Ambil settingan dari Cloud Koyeb
MY_COOKIE = os.getenv("MY_COOKIE")
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")
URL_FIRE = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app/messages.json"
URL_BASE = "https://www.calltimepanel.com/yeni/SMS/"

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    'Cookie': MY_COOKIE
})

def kirim_tele(pesan):
    try:
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        requests.post(url, data={'chat_id': TELE_CHAT_ID, 'text': pesan})
    except: pass

def start_grabber():
    print("BOT STARTED...")
    kirim_tele("🚀 Bot Grabber Aktif di Cloud!")
    done_ids = []
    
    while True:
        try:
            res = s.get(f"{URL_BASE}?_={int(time.time()*1000)}", timeout=15)
            if "login" in res.url.lower() or "Sign in" in res.text:
                kirim_tele("⚠️ COOKIE MATI! Ganti di Koyeb sekarang.")
                break 

            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.select('table tbody tr') or soup.select('table tr')

            for r in rows:
                c = r.find_all('td')
                if len(c) < 4: continue
                rcv, msg, date = c[1].text.strip(), c[2].text.strip(), c[3].text.strip()
                num = rcv.split('-')[-1].strip()
                uid = f"{num}_{''.join(filter(str.isdigit, date))}"
                
                if uid not in done_ids and len(num) > 5:
                    data = {"liveSms": num, "fullLabel": rcv, "messageContent": msg, "smsDate": date, "source": "Cloud-VIP"}
                    requests.post(URL_FIRE, json=data)
                    kirim_tele(f"📩 SMS BARU!\nNomor: {num}\nPesan: {msg}")
                    done_ids.append(uid)
            
            if len(done_ids) > 100: done_ids = done_ids[-50:]
            time.sleep(2) # Jeda 2 detik biar kenceng tapi aman
        except Exception as e:
            time.sleep(5)

if __name__ == "__main__":
    start_grabber()
