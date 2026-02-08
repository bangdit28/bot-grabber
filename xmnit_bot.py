import requests, time, os

# AMBIL DATA DARI KOYEB ENVIRONMENT
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MNIT_EMAIL = os.getenv("MNIT_EMAIL")
MNIT_PASS = os.getenv("MNIT_PASS")
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

# Session Global agar Cookie tersimpan otomatis
s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Content-Type': 'application/json'
})

def kirim_tele(pesan):
    try:
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        requests.post(url, data={'chat_id': TELE_CHAT_ID, 'text': pesan})
    except: pass

def login_mnit():
    """Fungsi Login Otomatis ke X-MNIT"""
    print("LOG: Mencoba Login ke X-MNIT...")
    login_api_url = "https://x.mnitnetwork.com/mapi/v1/mauth/login"
    
    payload = {
        "email": MNIT_EMAIL, 
        "password": MNIT_PASS
    }
    
    try:
        res = s.post(login_api_url, json=payload, timeout=15)
        # Biasanya respon 200 atau 201 artinya sukses
        if res.status_code in [200, 201]:
            print("✅ Login Sukses! Bot siap menerima perintah.")
            return True
        else:
            print(f"❌ Login Gagal ({res.status_code}): {res.text}")
            return False
    except Exception as e:
        print(f"⚠️ Error saat Login: {e}")
        return False

def tembak_get_number(range_num):
    """Fungsi untuk meminta nomor baru berdasarkan range"""
    # Berdasarkan SS lo, ini endpoint untuk dashboard get
    api_url = "https://x.mnitnetwork.com/api/v1/mdashboard/get" 
    payload = {"range": range_num}
    
    try:
        res = s.post(api_url, json=payload, timeout=15)
        
        # Jika Unauthorized (Cookie basi), coba login ulang sekali
        if res.status_code == 401:
            print("🔄 Session expired, mencoba login ulang...")
            if login_mnit():
                res = s.post(api_url, json=payload, timeout=15)
        
        data = res.json()
        # Mengambil nomor dari respon API
        # Kita coba ambil dari 'number' atau 'data.number' sesuai struktur umum API mereka
        num = data.get('number') or data.get('data', {}).get('number')
        return num
    except Exception as e:
        print(f"⚠️ Error Get Number: {e}")
        return None

def run_xmnit():
    print("LOG: X-MNIT Service Started...")
    # Login pertama kali saat bot baru nyala
    login_mnit()
    
    while True:
        try:
            # Ambil perintah dari Firebase yang dikirim Web App lo
            req = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            
            if req:
                for req_id, val in req.items():
                    target = val.get('range')
                    if not target: continue
                    
                    print(f"🚀 Perintah Masuk: Get Number {target}")
                    nomor_baru = tembak_get_number(target)
                    
                    if nomor_baru:
                        # Masukkan ke list Active Numbers di Firebase agar muncul di UI Web lo
                        requests.post(f"{FIREBASE_URL}/active_numbers.json", json={
                            "number": nomor_baru,
                            "range": target,
                            "timestamp": int(time.time())
                        })
                        kirim_tele(f"✅ X-MNIT: Nomor Didapat!\nNomor: {nomor_baru}\nRange: {target}")
                        print(f"✅ Berhasil mendapatkan nomor: {nomor_baru}")
                    else:
                        kirim_tele(f"❌ X-MNIT: Gagal dapet nomor untuk {target}. Cek saldo/panel.")
                    
                    # Hapus perintah dari Firebase supaya tidak diproses terus-menerus
                    requests.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            
            time.sleep(1.5) # Jeda pengecekan Firebase
        except Exception as e:
            print(f"Error Loop MNIT: {e}")
            time.sleep(5)
