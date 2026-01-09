import os
from gtts import gTTS
import subprocess

# Lokasi simpan audio
OUTPUT_FOLDER = "static/audio"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Senarai perkataan yang diperlukan
audio_list = {
    # Nombor 0-9
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
    
    # Ayat Tambahan
    "intro": "Nombor giliran",
    "kaunter": "Sila ke kaunter",
    "silake": "Sila ke",
    "sebutan_kaunter": "Kaunter",
}

print("Mula menjana audio Bahasa Melayu...")

for filename, text in audio_list.items():
    print(f"Generating: {text} -> {filename}.mp3")
    
    # 1. Generate Audio guna Google (Bahasa Melayu)
    tts = gTTS(text=text, lang='ms', slow=False)
    temp_file = f"{OUTPUT_FOLDER}/temp_{filename}.mp3"
    final_file = f"{OUTPUT_FOLDER}/{filename}.mp3"
    
    tts.save(temp_file)
    
    # 2. Guna FFmpeg untuk potong senyap (silence) di awal/akhir & normalize volume
    # Ini penting supaya audio bunyi pantas (takde gap lama)
    command = [
        "ffmpeg", "-y", "-i", temp_file,
        "-af", "silenceremove=start_periods=1:start_duration=0:start_threshold=-50dB:detection=peak,areverse,silenceremove=start_periods=1:start_duration=0:start_threshold=-50dB:detection=peak,areverse,volume=1.5",
        "-acodec", "libmp3lame", "-b:a", "128k",
        final_file
    ]
    
    try:
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.remove(temp_file) # Buang fail temp
    except Exception as e:
        print(f"Error processing {filename}: {e}")
        # Kalau ffmpeg error, rename je file asal
        os.rename(temp_file, final_file)

print("\nSIAP! Semua fail audio ada di folder static/audio/")
