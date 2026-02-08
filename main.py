import threading
import time
from calltime_bot import run_calltime
from xmnit_bot import run_xmnit

if __name__ == "__main__":
    print("🚀 SISTEM BOT MULTI-PANEL AKTIF!")
    
    # Menyiapkan Thread untuk masing-masing bot
    t1 = threading.Thread(target=run_calltime)
    t2 = threading.Thread(target=run_xmnit)

    # Menjalankan bot secara bersamaan
    t1.start()
    t2.start()

    # Menjaga agar main script tetap hidup
    t1.join()
    t2.join()
