import threading
import time
import os
from calltime_bot import run_calltime
from xmnit_bot import run_xmnit
from manager import bot_manager_run

if __name__ == "__main__":
    print("🔥 TASK SMS MULTI-TEAM SYSTEM STARTING...")
    
    # 1. Mesin Pengatur Antrian (Manager)
    threading.Thread(target=bot_manager_run, daemon=True).start()
    
    # 2. Mesin Grabber CallTime
    threading.Thread(target=run_calltime, daemon=True).start()
    
    # 3. Mesin Grabber X-MNIT
    threading.Thread(target=run_xmnit, daemon=True).start()

    print("✅ SEMUA SERVICE AKTIF! PC BOLEH MATI.")
    
    while True:
        time.sleep(10)
