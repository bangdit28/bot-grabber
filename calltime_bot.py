import requests, time, os
from bs4 import BeautifulSoup

# Ambil settingan khusus CallTime
MY_COOKIE = os.getenv("MY_COOKIE")
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"

def run_calltime():
    print("LOG: CallTime Service Started...")
    s = requests.Session()
    s.headers.update({'Cookie': MY_COOKIE})
    done_ids = []
    
    while True:
        try:
            res = s.get(f"https://www.calltimepanel.com/yeni/SMS/?_={int(time.time()*1000)}", timeout=15)
            if "login" in res.url.lower():
                print("⚠️ Cookie CallTime Mati")
                time.sleep(60); continue
                
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.select('table tbody tr') or soup.select('table tr')
            for r in rows:
                c = r.find_all('td')
                if len(c) < 4: continue
                rcv, msg, date = c[1].text.strip(), c[2].text.strip(), c[3].text.strip()
                num = rcv.split('-')[-1].strip()
                uid = f"{num}_{''.join(filter(str.isdigit, date))}"
                
                if uid not in done_ids and len(num) > 5:
                    data = {"liveSms": num, "fullLabel": rcv, "messageContent": msg, "smsDate": date}
                    requests.post(f"{FIREBASE_URL}/messages.json", json=data)
                    done_ids.append(uid)
            
            if len(done_ids) > 100: done_ids = done_ids[-50:]
            time.sleep(2)
        except: time.sleep(5)
