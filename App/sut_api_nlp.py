# -*- coding: utf-8 -*-
"""
SUT Fiyat Hesaplayıcı - API
Kurallar:
  1. EK-2A-2'de direkt var mı?
  2. R ile başlıyor mu?
  3. NLP başlık eşleşmesi var mı?

Çalıştırma: uvicorn sut_api:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import os
import re

from sut_nlp import get_nlp_implied_codes

# ==============================================================================
# SABİTLER
# ==============================================================================

KDV_ORANI = 1.10
PUAN_KATSAYISI = 0.593

# ==============================================================================
# FASTAPI UYGULAMASI
# ==============================================================================

app = FastAPI(
    title="SUT Fiyat Hesaplayıcı API",
    description="SUT kodları için fiyat hesaplama servisi (NLP destekli)",
    version="5.0"
)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# PYDANTIC MODELLERİ
# ==============================================================================

class SutRequest(BaseModel):
    kodlar: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "kodlar": ["1000", "L109350", "R100010", "700050"]
            }
        }


class SutItem(BaseModel):
    sut_kodu: str
    fiyat: Optional[float]
    durum: str
    aciklama: str


class SutOzet(BaseModel):
    toplam_tutar: float
    toplam_kod: int
    basarili: int
    hatali: int


class SutResponse(BaseModel):
    items: List[SutItem]
    ozet: SutOzet


class HealthResponse(BaseModel):
    status: str
    nlp_kod_sayisi: int
    ek2a_kod_sayisi: int
    ek2a2_kod_sayisi: int
    ek2b_kod_sayisi: int


# ==============================================================================
# VERİ İŞLEME FONKSİYONLARI
# ==============================================================================

def clean_col_names(df, file_identifier):
    """Excel sütun isimlerini standartlaştırır."""
    df.columns = [re.sub(r'\s+', ' ', str(col)).strip() for col in df.columns]
    rename_map = {}

    if file_identifier == 'ek2a':
        rename_map = {df.columns[0]: 'SUT KODU', df.columns[10]: 'Fiyat'}
    elif file_identifier == 'ek2a2':
        rename_map = {'İŞLEM KODU': 'SUT KODU'}
    elif file_identifier in ['ek2b', 'ek2c']:
        rename_map = {'İŞLEM KODU': 'SUT KODU', 'İŞLEM PUANI': 'Puan'}

    df.rename(columns=rename_map, inplace=True)

    if file_identifier in ['ek2b', 'ek2c'] and 'İŞLEM PUANI' in df.columns and 'Puan' not in df.columns:
        df.rename(columns={'İŞLEM PUANI': 'Puan'}, inplace=True)

    return df


def load_dataframes():
    """Tüm SUT Excel dosyalarını yükler."""
    script_dir = os.path.dirname(__file__)
    base_path = os.path.dirname(script_dir)
    sut_dir_path = os.path.join(base_path, "SUT Kuralları")

    paths = {
        "ek2a": os.path.join(sut_dir_path, "EK-2A AYAKTAN BAŞVURULARDA ÖDEME LİSTESİ (Yür.11.05.2024).xlsx"),
        "ek2a2": os.path.join(sut_dir_path, "EK-2A-2 AYAKTAN BAŞ. İLAVE OL. FAT. İŞ. LİSTESİ (Yür. 01.06.2021).xlsx"),
        "ek2b": os.path.join(sut_dir_path, "EK-2B HİZMET BAŞI İŞLEM PUAN LİSTESİ (Yür.11.05.2024).xlsx"),
        "ek2c": os.path.join(sut_dir_path, "EK-2C TANIYA DAYALI İŞLEM PUAN LİSTESİ (Yür.11.05.2024).xlsx")
    }

    dataframes = {}
    try:
        import warnings
        warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

        for key, path in paths.items():
            header_row = 2 if key == 'ek2a' else 1
            df = pd.read_excel(path, header=header_row)
            dataframes[key] = clean_col_names(df, key)
            dataframes[key]['SUT KODU'] = dataframes[key]['SUT KODU'].astype(str).str.strip()

        # NLP ile implied codes ekle
        try:
            nlp_codes, nlp_debug = get_nlp_implied_codes(
                dataframes['ek2b'],
                threshold=85,
                debug=True
            )
            dataframes['nlp_implied_codes'] = nlp_codes
            dataframes['nlp_debug'] = nlp_debug
        except Exception as e:
            dataframes['nlp_implied_codes'] = set()
            dataframes['nlp_debug'] = {}
            print(f"NLP yükleme hatası: {e}")

        return dataframes, None
    except FileNotFoundError as e:
        return None, f"Dosya bulunamadı: {e.filename}"
    except Exception as e:
        return None, f"Veri yüklenirken hata oluştu: {str(e)}"


# ==============================================================================
# FİYAT HESAPLAMA
# ==============================================================================

def get_prices(sut_codes_list, dataframes):
    """
    Verilen SUT kodları için fiyatları hesaplar.

    Kurallar:
    1. EK-2A-2'de direkt var mı?
    2. R ile başlıyor mu?
    3. NLP başlık eşleşmesi var mı?
    """
    if dataframes is None:
        return {"hata": "Veri setleri yüklenemedi."}, {}

    df_ek2a = dataframes['ek2a']
    df_ek2a2 = dataframes['ek2a2']
    df_ek2b = dataframes['ek2b']
    df_ek2c = dataframes['ek2c']
    nlp_implied_codes = dataframes.get('nlp_implied_codes', set())

    sut_codes_list = [str(code).strip() for code in sut_codes_list]

    ek2a_codes_set = set(df_ek2a['SUT KODU'])
    ek2a2_codes_set = set(df_ek2a2['SUT KODU'])

    # Paket tetikleyicileri: EK-2A'da var veya P ile başlıyor
    package_trigger_codes = {
        code for code in sut_codes_list
        if code in ek2a_codes_set or code.startswith('P')
    }
    is_package_active = bool(package_trigger_codes)

    results, details = {}, {}

    for code in sut_codes_list:
        is_trigger = code in package_trigger_codes

        if is_trigger:
            # === PAKET TETİKLEYİCİ KOD ===
            if code.startswith('P'):
                price_row_c = df_ek2c[df_ek2c['SUT KODU'] == code]
                if not price_row_c.empty:
                    puan = pd.to_numeric(price_row_c['Puan'].iloc[0], errors='coerce')
                    if pd.notna(puan):
                        results[code] = round(puan * PUAN_KATSAYISI * KDV_ORANI, 2)
                        details[code] = f"EK-2C'den hesaplandı (Puan: {puan})"
                    else:
                        results[code] = "Puan (EK-2C) bulunamadı"
                        details[code] = "Hata"
                else:
                    price_row_a = df_ek2a[df_ek2a['SUT KODU'] == code]
                    if not price_row_a.empty:
                        base_price = pd.to_numeric(price_row_a['Fiyat'].iloc[0], errors='coerce')
                        if pd.notna(base_price):
                            results[code] = round(base_price * KDV_ORANI, 2)
                            details[code] = "EK-2A'dan hesaplandı (P kodu)"
                        else:
                            results[code] = "Fiyat (EK-2A) bulunamadı"
                            details[code] = "Hata"
                    else:
                        results[code] = "P Kodu bulunamadı"
                        details[code] = "Hata"
            else:
                price_row_a = df_ek2a[df_ek2a['SUT KODU'] == code]
                if not price_row_a.empty:
                    base_price = pd.to_numeric(price_row_a['Fiyat'].iloc[0], errors='coerce')
                    if pd.notna(base_price):
                        results[code] = round(base_price * KDV_ORANI, 2)
                        details[code] = "EK-2A'dan hesaplandı (Branş Paketi)"
                    else:
                        results[code] = "Fiyat (EK-2A) bulunamadı"
                        details[code] = "Hata"
                else:
                    results[code] = "Kod EK-2A'da bulunamadı"
                    details[code] = "Hata"
        else:
            # === NORMAL HİZMET KODU ===
            if is_package_active:
                in_ek2a2 = code in ek2a2_codes_set
                starts_with_r = code.startswith('R')
                in_nlp = code in nlp_implied_codes

                if in_ek2a2 or starts_with_r or in_nlp:
                    price_row_b = df_ek2b[df_ek2b['SUT KODU'] == code]
                    if not price_row_b.empty:
                        puan = pd.to_numeric(price_row_b['Puan'].iloc[0], errors='coerce')
                        if pd.notna(puan):
                            results[code] = round(puan * PUAN_KATSAYISI * KDV_ORANI, 2)
                            if in_nlp:
                                details[code] = "EK-2B'den hesaplandı (NLP başlık eşleşmesi)"
                            elif starts_with_r:
                                details[code] = "EK-2B'den hesaplandı (R kodu)"
                            else:
                                details[code] = "EK-2B'den hesaplandı (EK-2A-2 listesi)"
                        else:
                            results[code] = "Puan (EK-2B) bulunamadı"
                            details[code] = "Hata"
                    else:
                        results[code] = "Kod EK-2B'de bulunamadı"
                        details[code] = "Hata"
                else:
                    results[code] = 0.0
                    details[code] = "Pakete dahil (ücretsiz)"
            else:
                price_row_b = df_ek2b[df_ek2b['SUT KODU'] == code]
                if not price_row_b.empty:
                    puan = pd.to_numeric(price_row_b['Puan'].iloc[0], errors='coerce')
                    if pd.notna(puan):
                        results[code] = round(puan * PUAN_KATSAYISI * KDV_ORANI, 2)
                        details[code] = "EK-2B'den hesaplandı (Standalone)"
                    else:
                        results[code] = "Puan (EK-2B) bulunamadı"
                        details[code] = "Hata"
                else:
                    results[code] = "Kod EK-2B'de bulunamadı"
                    details[code] = "Hata"

    return results, details


# ==============================================================================
# VERİ YÜKLEME (Startup)
# ==============================================================================

dataframes = None
startup_error = None


@app.on_event("startup")
async def startup_event():
    """Uygulama başlarken verileri yükle."""
    global dataframes, startup_error
    dataframes, startup_error = load_dataframes()

    if startup_error:
        print(f"❌ Veri yükleme hatası: {startup_error}")
    else:
        nlp_count = len(dataframes.get('nlp_implied_codes', set()))
        print(f"✅ Veriler yüklendi! ({nlp_count} NLP eşleşmeli kod)")


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@app.get("/", tags=["Genel"])
async def root():
    """API ana sayfası."""
    return {
        "mesaj": "SUT Fiyat Hesaplayıcı API",
        "versiyon": "5.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["Genel"])
async def health_check():
    """Sistem sağlık kontrolü."""
    if startup_error:
        raise HTTPException(status_code=503, detail=startup_error)

    return HealthResponse(
        status="healthy",
        nlp_kod_sayisi=len(dataframes.get('nlp_implied_codes', set())),
        ek2a_kod_sayisi=len(dataframes['ek2a']),
        ek2a2_kod_sayisi=len(dataframes['ek2a2']),
        ek2b_kod_sayisi=len(dataframes['ek2b'])
    )


@app.post("/hesapla", response_model=SutResponse, tags=["Fiyat Hesaplama"])
async def hesapla_fiyat(request: SutRequest):
    """
    SUT kodları için fiyat hesaplar.

    **Kurallar:**
    1. EK-2A-2'de direkt var mı?
    2. R ile başlıyor mu?
    3. NLP başlık eşleşmesi var mı?

    Bu kurallardan biri sağlanırsa → EK-2B'den fiyat
    Hiçbiri sağlanmazsa → 0₺ (Pakete dahil)
    """
    if startup_error:
        raise HTTPException(status_code=503, detail=startup_error)

    if not request.kodlar:
        raise HTTPException(status_code=400, detail="En az bir SUT kodu gerekli")

    results, details = get_prices(request.kodlar, dataframes)

    items = []
    toplam = 0.0
    basarili = 0
    hatali = 0

    for kod in request.kodlar:
        fiyat = results.get(kod, "Bulunamadı")
        detay = details.get(kod, "-")

        if isinstance(fiyat, (int, float)):
            toplam += fiyat
            basarili += 1
            items.append(SutItem(
                sut_kodu=kod,
                fiyat=round(fiyat, 2),
                durum="basarili",
                aciklama=detay
            ))
        else:
            hatali += 1
            items.append(SutItem(
                sut_kodu=kod,
                fiyat=None,
                durum="hata",
                aciklama=str(fiyat)
            ))

    return SutResponse(
        items=items,
        ozet=SutOzet(
            toplam_tutar=round(toplam, 2),
            toplam_kod=len(request.kodlar),
            basarili=basarili,
            hatali=hatali
        )
    )


@app.get("/tek/{sut_kodu}", tags=["Fiyat Hesaplama"])
async def tek_kod_hesapla(sut_kodu: str):
    """Tek bir SUT kodu için fiyat hesaplar."""
    if startup_error:
        raise HTTPException(status_code=503, detail=startup_error)

    results, details = get_prices([sut_kodu], dataframes)

    fiyat = results.get(sut_kodu, "Bulunamadı")
    detay = details.get(sut_kodu, "-")

    if isinstance(fiyat, (int, float)):
        return {
            "sut_kodu": sut_kodu,
            "fiyat": round(fiyat, 2),
            "durum": "basarili",
            "aciklama": detay
        }
    else:
        return {
            "sut_kodu": sut_kodu,
            "fiyat": None,
            "durum": "hata",
            "aciklama": str(fiyat)
        }


@app.get("/nlp/debug", tags=["NLP"])
async def nlp_debug():
    """NLP başlık eşleşme detaylarını gösterir."""
    if startup_error:
        raise HTTPException(status_code=503, detail=startup_error)

    nlp_debug_info = dataframes.get('nlp_debug', {})

    matched = []
    not_matched = []

    for ref, info in nlp_debug_info.items():
        if info['matched_to']:
            matched.append({
                "referans": ref,
                "eslesen": info['matched_to'],
                "skor": info['score'],
                "kod_sayisi": info['code_count']
            })
        else:
            not_matched.append({
                "referans": ref,
                "eslesen": None,
                "skor": 0,
                "kod_sayisi": 0
            })

    return {
        "toplam_baslik": len(nlp_debug_info),
        "eslesen": len(matched),
        "eslesmeyen": len(not_matched),
        "detay": {
            "eslesen_basliklar": matched,
            "eslesmeyen_basliklar": not_matched
        }
    }


@app.get("/nlp/kodlar", tags=["NLP"])
async def nlp_kodlar():
    """NLP ile eşleşen tüm SUT kodlarını listeler."""
    if startup_error:
        raise HTTPException(status_code=503, detail=startup_error)

    nlp_codes = dataframes.get('nlp_implied_codes', set())

    return {
        "toplam": len(nlp_codes),
        "kodlar": sorted(list(nlp_codes))
    }


# ==============================================================================
# ÇALIŞTIRMA
# ==============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)