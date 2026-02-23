import threading, time, os, re, random, requests, json
from flask import Flask, render_template_string, jsonify
from bs4 import BeautifulSoup
from datetime import datetime

app = Flask(__name__)

# === CONFIGURATION (SET DI SECRETS) ===
FIREBASE_URL = os.getenv("FIREBASE_URL", "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app").strip().rstrip('/')
MY_COOKIE = os.getenv("MY_COOKIE", "").strip()      # Cookie CallTime lo
MY_UA = os.getenv("MY_UA", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36").strip()
TELE_TOKEN = os.getenv("TELE_TOKEN", "").strip()
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID", "").strip()

# Global State
IS_MONITORING = True
LOGS = []
STATS = {"total_sms": 0, "last_grab": "-", "uptime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

def add_log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    LOGS.append(f"[{timestamp}] {msg}")
    if len(LOGS) > 50: LOGS.pop(0)

def send_tele(text):
    if not TELE_TOKEN or not TELE_CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        # OTP/Nomor dibuat monospaced biar klik salin
        otp_match = re.search(r'\b\d{4,8}\b', text)
        if otp_match:
            otp = otp_match.group(0)
            text = text.replace(otp, f"<code>{otp}</code>")
        requests.post(url, data={'chat_id': TELE_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
    except: pass

def get_only_digits(text):
    return re.sub(r'\D', '', str(text))

# ==========================================
# 🛰️ ENGINE 1: ALLOCATE & RETURN (MANAGER)
# ==========================================

def get_token_rd(url):
    """Ambil token rd wajib CallTime"""
    try:
        res = requests.get(url, headers={'Cookie': MY_COOKIE, 'User-Agent': MY_UA}, timeout=10)
        match = re.search(r'name="rd" value="([a-f0-9]+)"', res.text)
        if not match: match = re.search(r"rd=([a-f0-9]+)", res.text)
        return match.group(1) if match else ""
    except: return ""

def run_manager():
    add_log("🚀 Manager CallTime Aktif")
    while True:
        try:
            # 1. CEK ANTRIAN BELI NOMOR
            r = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if r and isinstance(r, dict):
                inv = requests.get(f"{FIREBASE_URL}/inventory.json").json()
                for cmd_id, val in r.items():
                    m_id, m_name = val.get('memberId'), val.get('memberName', 'User')
                    inv_id = val.get('inventoryId')
                    item = inv.get(inv_id) if inv else None
                    
                    if item:
                        token = get_token_rd("https://www.calltimepanel.com/yeni/AllocateSMS/")
                        params = {
                            'payout': '7/1', 'allocate': item['id'], 'f1': item.get('f1','0.014'),
                            'f2': item.get('f2','0.0145'), 'cost': item.get('cost','0.02'), 
                            'rd': token, 'Countryi': item['serviceName'], 'size': val.get('size', '1')
                        }
                        res_order = requests.get("https://www.calltimepanel.com/yeni/AllocateSMS/", params=params, headers={'Cookie': MY_COOKIE, 'User-Agent': MY_UA}, timeout=20)
                        if "/yeni/MySmsNumbers/" in res_order.url:
                            add_log(f"✅ {m_name} sukses beli {item['serviceName']}")
                    requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")

            # 2. CEK ANTRIAN RETURN (HAPUS)
            ret = requests.get(f"{FIREBASE_URL}/perintah_return.json").json()
            if ret and isinstance(ret, dict):
                token = get_token_rd("https://www.calltimepanel.com/yeni/MySmsNumbers/")
                for rid, rval in ret.items():
                    num_to_del = get_only_digits(rval['number'])
                    # Cari ID Checkbox
                    res_page = requests.get("https://www.calltimepanel.com/yeni/MySmsNumbers/", headers={'Cookie': MY_COOKIE}, timeout=15)
                    soup = BeautifulSoup(res_page.text, 'html.parser')
                    found_id = None
                    for row in soup.select('table tr'):
                        if num_to_del in get_only_digits(row.get_text()):
                            cb = row.find('input', type='checkbox')
                            if cb: found_id = cb.get('value'); break
                    
                    if found_id:
                        payload = [('rd', token), ('altolay', ''), ('chk[]', found_id), ('sec[]', found_id), ('butReturn', 'Return to Pool')]
                        requests.post("https://www.calltimepanel.com/yeni/MySmsNumbers/", data=payload, headers={'Cookie': MY_COOKIE}, timeout=15)
                        add_log(f"🗑️ Nomor {num_to_del} dikembalikan")
                        # Hapus dari dashboard anggota
                        requests.delete(f"{FIREBASE_URL}/members/{rval['memberId']}/active_numbers/{num_to_del}.json")
                    requests.delete(f"{FIREBASE_URL}/perintah_return/{rid}.json")
            
            time.sleep(2)
        except Exception as e:
            add_log(f"Error Manager: {str(e)[:30]}")
            time.sleep(5)

# ==========================================
# 📡 ENGINE 2: GRABBER SMS (OTP SCANNER)
# ==========================================
def run_grabber():
    add_log("📡 SMS Grabber Aktif")
    done_ids = set()
    while True:
        if not IS_MONITORING: time.sleep(5); continue
        try:
            res = requests.get("https://www.calltimepanel.com/yeni/SMS/", headers={'Cookie': MY_COOKIE}, timeout=15)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                for r in soup.select('table tr'):
                    tds = r.find_all('td')
                    if len(tds) < 4: continue
                    raw_n = tds[1].text.strip()
                    num = get_only_digits(raw_n)[-11:] 
                    msg = tds[2].text.strip().replace('u003c#u003e', '<#>').replace('u003e', '>').strip()
                    uid = f"ct_{num}_{msg[:15]}"
                    
                    if uid not in done_ids:
                        # Cari Nama Pemilik Nomor
                        owner_name = "ADMIN"
                        r_owner = requests.get(f"{FIREBASE_URL}/active_numbers_lookup/{num}.json").json()
                        if r_owner: owner_name = r_owner.get('name', 'ADMIN')

                        # Push ke Firebase buat Dashboard Web
                        requests.post(f"{FIREBASE_URL}/messages.json", json={"liveSms": num, "messageContent": msg, "timestamp": int(time.time()*1000)})
                        
                        # Notif Telegram Format Sesuai Request Lo
                        app_name = "FACEBOOK" if "FACEBOOK" in msg.upper() or "FB" in msg.upper() else "APPS"
                        text_tele = (
                            f"📩 <b>SMS DITERIMA!</b>\n\n"
                            f"👤 <b>Nama :</b> {owner_name}\n"
                            f"📱 <b>Nomor :</b> <code>{num}</code>\n"
                            f"📌 <b>Apps :</b> {app_name}\n"
                            f"🌍 <b>Negara :</b> {raw_n.split(' - ')[0]}\n"
                            f"💬 <b>Pesan :</b> {msg}"
                        )
                        send_tele(text_tele)
                        done_ids.add(uid)
                        STATS["total_sms"] += 1
            time.sleep(3)
        except: time.sleep(5)

# ==========================================
# 📊 ENGINE 3: RADAR GACOR (TESTSMS)
# ==========================================
def run_radar():
    add_log("🛰️ Radar History Aktif")
    done_ids = set()
    while True:
        try:
            res = requests.get("https://www.calltimepanel.com/yeni/TestSMS/", headers={'Cookie': MY_COOKIE}, timeout=15)
            soup = BeautifulSoup(res.content.decode('windows-1254', 'ignore'), 'html.parser')
            for r in soup.select('table tr')[1:11]:
                tds = r.find_all('td')
                if len(tds) >= 5:
                    msg_id = tds[0].text.strip()
                    if msg_id not in done_ids:
                        msg = tds[3].text.strip()
                        # Filter Khusus FB
                        if "FACEBOOK" in msg.upper() or "FB" in msg.upper():
                            phone = get_only_digits(tds[2].text)
                            requests.post(f"{FIREBASE_URL}/live_test_history.json", json={
                                "service": tds[2].text.split(' - ')[0],
                                "range": phone[:7],
                                "number": phone,
                                "content": msg,
                                "category": "FACEBOOK",
                                "receivedTime": tds[4].text.split(' ')[1]
                            })
                        done_ids.add(msg_id)
            time.sleep(10)
        except: time.sleep(15)

# ==========================================
# 💻 ADMIN DASHBOARD (WEB CONTROL)
# ==========================================
@app.route('/')
def index():
    return render_template_string(HTML_UI)

@app.route('/api/status')
def api_status():
    return jsonify({"monitoring": IS_MONITORING, "logs": LOGS[::-1], "stats": STATS})

@app.route('/api/toggle')
def api_control():
    global IS_MONITORING
    IS_MONITORING = not IS_MONITORING
    return jsonify({"status": IS_MONITORING})

HTML_UI = """
<!DOCTYPE html>
<html>
<head>
    <title>TASK-SMS ADMIN</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #020617; color: #f8fafc; font-family: 'Inter', sans-serif; }
        .glass { background: rgba(15, 23, 42, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.05); }
    </style>
</head>
<body class="p-8">
    <div class="max-w-6xl mx-auto">
        <div class="flex justify-between items-center mb-10">
            <h1 class="text-3xl font-black text-cyan-400 tracking-tighter">🤖 CALLTIME <span class="text-white">COMMANDER</span></h1>
            <button onclick="fetch('/api/toggle')" class="bg-red-600 px-6 py-2 rounded-2xl font-bold text-xs">STOP/START BOT</button>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="glass p-6 rounded-[2rem] text-center">
                <p class="text-[10px] font-bold text-slate-500 uppercase">SMS Grabbed</p>
                <p id="st_sms" class="text-3xl font-black text-white">0</p>
            </div>
            <div class="lg:col-span-2 glass p-6 rounded-[2rem] h-[400px] flex flex-col">
                <div id="logs" class="flex-1 overflow-y-auto font-mono text-[11px] text-cyan-500/70 space-y-1"></div>
            </div>
        </div>
    </div>
    <script>
        setInterval(async () => {
            const r = await fetch('/api/status'); const d = await r.json();
            document.getElementById('st_sms').innerText = d.stats.total_sms;
            document.getElementById('logs').innerHTML = d.logs.map(l => `<div>${l}</div>`).join('');
        }, 2000);
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    threading.Thread(target=run_manager, daemon=True).start()
    threading.Thread(target=run_grabber, daemon=True).start()
    threading.Thread(target=run_radar, daemon=True).start()
    app.run(host='0.0.0.0', port=7860)
