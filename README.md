# SUT Fiyat Hesaplayıcı

SGK SUT (Sağlık Uygulama Tebliği) kodları için otomatik fiyat hesaplama sistemi. NLP tabanlı başlık eşleştirme ile gelişmiş kural motoru.

## 🚀 Özellikler

- **Otomatik Fiyat Hesaplama**: SUT kodlarına göre KDV dahil fiyat hesaplama
- **Paket Fiyatlandırma**: Branş paketi aktifken istisna kuralları uygulama
- **NLP Başlık Eşleşmesi**: Fuzzy matching ile EK-2A-2 başlık referanslarını bulma
- **Derin Arama**: Belirli başlıklar için alt başlıklar dahil kod tarama
- **Web Arayüzü**: Streamlit tabanlı kullanıcı dostu arayüz
- **REST API**: FastAPI ile entegrasyon için API desteği

## 📁 Proje Yapısı
```
Sut-Kural-Motoru-main/
├── App/
│   ├── app.py              # Streamlit web arayüzü
│   ├── sut_api.py          # FastAPI REST API
│   └── sut_nlp.py          # NLP modülü (fuzzy matching)
├── SUT Kuralları/
│   ├── EK-2A AYAKTAN BAŞVURULARDA ÖDEME LİSTESİ (Yür.11.05.2024).xlsx
│   ├── EK-2A-2 AYAKTAN BAŞ. İLAVE OL. FAT. İŞ. LİSTESİ (Yür. 01.06.2021).xlsx
│   ├── EK-2B HİZMET BAŞI İŞLEM PUAN LİSTESİ (Yür.11.05.2024).xlsx
│   └── EK-2C TANIYA DAYALI İŞLEM PUAN LİSTESİ (Yür.11.05.2024).xlsx
├── requirements.txt
└── README.md
```

## ⚙️ Kurulum

### 1. Gereksinimler

- Python 3.8+
- pip

### 2. Bağımlılıkları Yükle
```bash
pip install -r requirements.txt
```

### 3. requirements.txt
```
streamlit
fastapi
uvicorn
pandas
openpyxl
rapidfuzz
```

## 🖥️ Çalıştırma

### Web Arayüzü (Streamlit)
```bash
streamlit run App/app.py
```

Tarayıcıda açılır: http://localhost:8501

### REST API (FastAPI)
```bash
uvicorn App.sut_api:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 📊 Fiyatlandırma Kuralları

### Sabitler

| Parametre | Değer |
|-----------|-------|
| KDV Oranı | %10 (1.10) |
| Puan Katsayısı | 0.593 |

### Fiyat Formülleri

| Kaynak | Formül |
|--------|--------|
| EK-2A (Fiyat) | `Fiyat × 1.10` |
| EK-2B / EK-2C (Puan) | `Puan × 0.593 × 1.10` |

### Paket İstisna Kuralları

Paket aktifken (branş kodu veya P kodu varsa), aşağıdaki kurallardan **biri** sağlanırsa EK-2B'den fiyat hesaplanır:

| Sıra | Kural | Açıklama |
|------|-------|----------|
| 1 | EK-2A-2 Listesi | Kod direkt EK-2A-2'de var |
| 2 | R Kuralı | Kod 'R' ile başlıyor |
| 3 | NLP Eşleşmesi | Kod, EK-2A-2 başlık referansı altında |

Hiçbir kural sağlanmazsa → **0₺** (Pakete dahil)

### NLP Başlık Eşleşmesi

EK-2A-2'de bazı satırlarda SUT kodu yerine başlık referansı bulunur:

> "SUT eki EK-2/B Listesinde yer alan "Aminoasitler ve Türevleri" başlığındaki tetkikler"

Bu başlıklar fuzzy matching ile EK-2B'de bulunur ve altındaki tüm kodlar paket istisnası olarak değerlendirilir.

#### Desteklenen Başlıklar

- 10. TÜRKİYE HALK SAĞLIĞI KURUMU MERKEZ LABORATUVARI PANELİ (Derin Arama)
- 9.C.1. ONKOLOJİK MOLEKÜLER TETKİKLER
- 9.C. MOLEKÜLER GENETİK TETKİKLER
- 9.B.1. MOLEKÜLER SİTOGENETİK TETKİKLER
- 9.B. SİTOGENETİK TETKİKLER
- 9.A-Moleküler Mikrobiyoloji
- 8.3.1. BİLGİSAYARLI TOMOGRAFİ (BT)
- 8.3.2. MANYETİK REZONANS GÖRÜNTÜLEME (MRG)
- Aminoasitler ve Türevleri
- Alerji Testleri
- Monoklonal Antikor (Akım sitometresi)
- Kortizol-İnsülin Uyarı Testi
- Büyüme hormonu-İnsülin Uyarı Testi
- TSH-TRH Uyarı Testi
- ... ve diğerleri

## 🔌 API Endpoints

### Genel

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/` | GET | API bilgisi |
| `/health` | GET | Sistem sağlık kontrolü |

### Fiyat Hesaplama

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/hesapla` | POST | Toplu fiyat hesaplama |
| `/tek/{sut_kodu}` | GET | Tek kod hesaplama |

### NLP Debug

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/nlp/debug` | GET | Başlık eşleşme detayları |
| `/nlp/kodlar` | GET | NLP ile eşleşen kodlar |

### Örnek İstekler

**POST /hesapla**
```json
{
  "kodlar": ["1000", "L109350", "R100010", "700050"]
}
```

**Yanıt:**
```json
{
  "items": [
    {
      "sut_kodu": "1000",
      "fiyat": 68.42,
      "durum": "basarili",
      "aciklama": "EK-2A'dan hesaplandı (Branş Paketi)"
    },
    {
      "sut_kodu": "L109350",
      "fiyat": 14.36,
      "durum": "basarili",
      "aciklama": "EK-2B'den hesaplandı (NLP başlık eşleşmesi)"
    }
  ],
  "ozet": {
    "toplam_tutar": 82.78,
    "toplam_kod": 4,
    "basarili": 4,
    "hatali": 0
  }
}
```

**GET /tek/L109350**
```json
{
  "sut_kodu": "L109350",
  "fiyat": 14.36,
  "durum": "basarili",
  "aciklama": "EK-2B'den hesaplandı (NLP başlık eşleşmesi)"
}
```

## 🛠️ Geliştirme

### Yeni Başlık Ekleme

`sut_nlp.py` dosyasındaki `EK2A2_REFERENCE_HEADERS` listesine ekle:
```python
EK2A2_REFERENCE_HEADERS = [
    # ... mevcut başlıklar ...
    "Yeni Başlık Adı",
]
```

### Derin Arama Başlığı Ekleme

Alt başlıklar dahil taranması gereken başlıklar için `DEEP_SEARCH_HEADERS` listesine ekle:
```python
DEEP_SEARCH_HEADERS = [
    "10. TÜRKİYE HALK SAĞLIĞI KURUMU MERKEZ LABORATUVARI (REFİK SAYDAM HIFZISSIHHA) PANELİ",
    "Yeni Derin Arama Başlığı",  # Yeni
]
```

## 📝 Lisans

Bu proje dahili kullanım içindir.

## 📌 Versiyon

v5.0 - NLP Başlık Eşleşmesi Desteği