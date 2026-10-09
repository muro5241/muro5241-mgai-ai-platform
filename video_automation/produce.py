"""Standalone illustrated vertical video producer; no TikTok publishing."""
import argparse
import asyncio
import json
import math
import random
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import edge_tts

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
TOPICS = {
    "ParaRadar": [
        ("Bitcoin neden dalgalanır?", "Bitcoin fiyatı arz, talep ve piyasa beklentilerine göre değişir. Tek bir yükseliş kesin kazanç anlamına gelmez. İşlem yapmadan önce riskleri araştır."),
        ("Kripto güvenliği", "Kripto varlıklarında güvenlik önemlidir. Kurtarma kelimelerini kimseyle paylaşma. İki aşamalı doğrulamayı etkinleştir ve bilinmeyen bağlantılara dikkat et."),
    ],
    "AI Radar": [
        ("Yapay zekâ ne yapabilir?", "Yapay zekâ metin, ses ve görsel üretiminde yardımcı olabilir. Ancak sonuçları kontrol etmek gerekir. Özellikle önemli kararları yalnızca yapay zekâya bırakma."),
        ("AI ile verimlilik", "Tekrarlayan görevler otomasyonla hızlandırılabilir. Önce küçük bir süreç seç, çıktıları kontrol et ve işe yarayan adımları geliştir."),
    ],
    "Tarih Radar": [
        ("Tarihi kaynaklar", "Bir tarihi olayı anlamak için birden fazla kaynağa bakmak gerekir. Dönemin koşulları ve kaynakların güvenilirliği sonucu etkiler."),
        ("Haritalar neden değişir?", "Sınırlar tarih boyunca savaşlar, anlaşmalar ve siyasi değişimlerle yeniden şekillendi. Bir haritayı yorumlarken tarihini kontrol et."),
    ],
    "Bilgi Radar": [
        ("Bilgi doğrulama", "İnternette gördüğün şaşırtıcı bir iddiayı hemen paylaşma. Kaynağını, tarihini ve başka güvenilir kaynaklarda doğrulanıp doğrulanmadığını incele."),
        ("Alışkanlıkların gücü", "Küçük ama düzenli tekrarlar öğrenmeyi kolaylaştırabilir. Gerçekçi bir hedef belirle ve ilerlemeni haftalık olarak takip et."),
    ],
    "Ekonomi Radar": [
        ("Enflasyon nedir?", "Enflasyon genel fiyat seviyesinin zaman içinde artmasıdır. Aynı parayla daha az ürün alınmasına yol açabilir. Fiyat değişimini tek bir ürüne bakarak ölçmek yanıltıcıdır."),
        ("Bütçe planı", "Gelir ve giderleri ayrı ayrı yazmak bütçeyi görmeyi kolaylaştırır. Acil durumlar için birikim hedefi belirlemek beklenmedik harcamalara karşı yardımcı olabilir."),
    ],
}

def font(size):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def draw_frame(path, title, brand, index):
    w, h = 720, 1280
    im = Image.new("RGB", (w, h), (8, 15, 33))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((35, 55, 685, 130), radius=18, fill=(21, 44, 73))
    d.text((65, 75), brand.upper(), font=font(30), fill=(104, 244, 208))
    words = title.split()
    lines, line = [], ""
    for word in words:
        trial = (line + " " + word).strip()
        if d.textbbox((0,0), trial, font=font(55))[2] > 600 and line:
            lines.append(line)
            line = word
        else:
            line = trial
    if line: lines.append(line)
    for j, text in enumerate(lines[:3]):
        d.text((55, 190 + 76*j), text, font=font(55), fill="white")
    for y in range(540, 1030, 80):
        d.line((55, y, 670, y), fill=(29, 53, 78), width=2)
    for x in range(55, 671, 80):
        d.line((x, 530, x, 1040), fill=(29, 53, 78), width=2)
    rng = random.Random(index * 917 + len(title))
    points, value = [], 800
    for k in range(30):
        value += rng.randint(-65, 65)
        value = max(570, min(990, value))
        points.append((65 + k*20, value))
    d.line(points, fill=(73, 232, 184), width=8, joint="curve")
    for x,y in points[::5]:
        d.ellipse((x-7,y-7,x+7,y+7), fill=(230, 244, 249))
    d.text((65, 1110), "TEMSiLi GRAFiK  •  BiLGiLENDiRME", font=font(23), fill=(172,190,211))
    im.save(path)

async def voice(text, path):
    await edge_tts.Communicate(text, "tr-TR-AhmetNeural").save(str(path))

def duration(audio):
    p = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(audio)],capture_output=True,text=True,check=True)
    return float(p.stdout.strip())

async def make_one(index, brand, title, script):
    slug = f"{index:03d}_{brand.lower()}"
    mp4, audio, image = OUT / (slug + ".mp4"), OUT / (slug + ".mp3"), OUT / (slug + ".png")
    if mp4.exists() and mp4.stat().st_size > 10000:
        return str(mp4), "existing"
    draw_frame(image, title, brand, index)
    await voice(script, audio)
    seconds = max(8.0, duration(audio) + 1.0)
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-loop","1","-framerate","25","-i",str(image),"-i",str(audio),"-vf","zoompan=z='min(zoom+0.00045,1.12)':d=1:s=720x1280:fps=25,format=yuv420p","-t",str(seconds),"-c:v","libx264","-preset","veryfast","-crf","25","-c:a","aac","-b:a","128k","-movflags","+faststart",str(mp4)],check=True)
    return str(mp4), "created"

async def main(count):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("FFmpeg and ffprobe must be on PATH")
    OUT.mkdir(parents=True, exist_ok=True)
    entries = [(brand, title, script) for brand, topics in TOPICS.items() for title, script in topics]
    manifest = OUT / "manifest.jsonl"
    for i in range(count):
        brand, title, script = entries[i % len(entries)]
        try:
            path, status = await make_one(i+1, brand, title, script)
            record = {"index":i+1,"project":brand,"title":title,"status":status,"path":path}
            print(f"[{i+1}/{count}] {status}: {path}",flush=True)
        except Exception as exc:
            record = {"index":i+1,"project":brand,"title":title,"status":"error","error":str(exc)}
            print(f"[{i+1}/{count}] ERROR: {exc}",flush=True)
        with manifest.open("a",encoding="utf-8") as f:
            f.write(json.dumps(record,ensure_ascii=False)+"\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count",type=int,default=10)
    args = parser.parse_args()
    asyncio.run(main(args.count))
