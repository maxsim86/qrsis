import os
from gtts import gTTS
import subprocess

# Lokasi simpan audio
OUTPUT_FOLDER = "static/audio"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Senarai perkataan yang diperlukan
audio_list = {
    # --- NOMBOR (0-9) ---
    "0": "Kosong",
    "1": "Satu",
    "2": "Dua",
    "3": "Tiga",
    "4": "Empat",
    "5": "Lima",
    "6": "Enam",
    "7": "Tujuh",
    "8": "Lapan",
    "9": "Sembilan",

    # --- HURUF KATEGORI (Multi-Service) ---
    # Tips: Google kadang-kadang baca 'A' sebagai 'Ah'. 
    # Kalau nak bunyi English 'Ei', boleh tukar text jadi 'Ei'.
    # Tapi untuk standard Melayu, kita guna huruf biasa dulu.
    "a": "A", 
    "b": "B",
    "c": "C",
    
    # --- AYAT TAMBAHAN ---
    "intro": "Nombor giliran",
    "kaunter": "Sila ke kaunter",
    "silake": "Sila ke",
    "sebutan_kaunter": "Kaunter",
}

print("==========================================")
print("   MULA MENJANA AUDIO BAHASA MELAYU")
print("==========================================")

# Semak adakah FFmpeg dipasang
try:
    subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ffmpeg_available = True
    print("✅ FFmpeg dikesan. Audio akan dipotong (trim silence) supaya lebih laju.")
except FileNotFoundError:
    ffmpeg_available = False
    print("⚠️ FFmpeg TIDAK dikesan. Audio akan dijana tanpa pemotongan silence.")

print("-" * 40)

for filename, text in audio_list.items():
    print(f"🔊 Generating: '{text}' -> {filename}.mp3")
    
    # 1. Generate Audio guna Google (Bahasa Melayu)
    try:
        tts = gTTS(text=text, lang='ms', slow=False)
        temp_file = f"{OUTPUT_FOLDER}/temp_{filename}.mp3"
        final_file = f"{OUTPUT_FOLDER}/{filename}.mp3"
        
        tts.save(temp_file)
        
        # 2. Proses Audio (Jika FFmpeg ada)
        if ffmpeg_available:
            # Command untuk buang senyap (silence) di awal/akhir & kuatkan volume
            command = [
                "ffmpeg", "-y", "-i", temp_file,
                "-af", "silenceremove=start_periods=1:start_duration=0:start_threshold=-50dB:detection=peak,areverse,silenceremove=start_periods=1:start_duration=0:start_threshold=-50dB:detection=peak,areverse,volume=1.5",
                "-acodec", "libmp3lame", "-b:a", "128k",
                final_file
            ]
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Buang fail temp jika conversion berjaya
            if os.path.exists(final_file):
                os.remove(temp_file)
            else:
                # Fallback jika ffmpeg gagal senyap-senyap
                os.rename(temp_file, final_file)
        else:
            # Jika tiada FFmpeg, terus rename temp ke final
            if os.path.exists(final_file):
                os.remove(final_file) # Buang file lama jika ada
            os.rename(temp_file, final_file)
            
    except Exception as e:
        print(f"❌ Error processing {filename}: {e}")

print("-" * 40)
print(f"✅ SIAP! Semua fail audio ada di folder: {OUTPUT_FOLDER}/")
print("   Pastikan fail 'chime.mp3' (Ding Dong) dimasukkan secara manual.")
print("==========================================")