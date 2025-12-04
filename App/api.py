# -*- coding: utf-8 -*-
"""
SUT Fiyat Hesaplayıcı - REST API
Dosya Yolu: App/api.py

Kullanım: uvicorn App.api:app --reload --host 0.0.0.0 --port 8000
Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from contextlib import asynccontextmanager

# Servis katmanını import et
from services import load_dataframes, get_prices, format_price_response
from Rules.rules import KDV_ORANI, PUAN_KATSAYISI, L_CODE_RANGES, CODE_90X_RANGE

# ==============================================================================
# GLOBAL DEĞİŞKENLER
# ==============================================================================

dataframes = None
data_error = None


# ==============================================================================
# LIFECYCLE (Startup/Shutdown)
# ==============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başlatıldığında verileri yükle."""
    global dataframes, data_error
    print("📂 SUT verileri yükleniyor...")
    dataframes, data_error = load_dataframes()
    if data_error:
        print(f"❌ Hata: {data_error}")
    else:
        print("✅ Veriler başarıyla yüklendi!")
    yield
    print("👋 API kapatılıyor...")


# ==============================================================================
# FASTAPI UYGULAMASI
# ==============================================================================

app = FastAPI(
    title="SUT Fiyat Hesaplayıcı API",
    description="""
## 🏥 SUT (Sağlık Uygulama Tebliği) Fiyat Hesaplama API'si

Bu API, Türkiye'deki özel hastanelerin SGK ile anlaşmalı ayaktan tedavi hizmetleri için 
SUT kodlarına göre fiyat hesaplaması yapar.

### Özellikler:
- **EK-2A**: Branş paket fiyatları
- **EK-2A-2**: Paket istisna listesi
- **EK-2B**: Hizmet başı işlem puanları
- **EK-2C**: Tanıya dayalı işlem puanları (P kodları)

### Fiyatlama Kuralları:
- Paket tetikleyici kod varsa (branş kodu veya P kodu), paket modu aktif olur
- Paket modunda: EK-2A-2'de olan veya özel kodlar (R, 912, G1, belirli L ve 90x aralıkları) EK-2B'den fiyatlanır
- Paket modunda: Diğer kodlar pakete dahil (0 TL)
- Standalone modda: Tüm kodlar EK-2B'den fiyatlanır

### Formül:
`Fiyat = Puan × 0.593 × 1.10 (KDV dahil)`
    """,
    version="4.1.0",
    contact={
        "name": "SUT Fiyat Hesaplayıcı",
    },
    license_info={
        "name": "MIT",
    },
    lifespan=lifespan
)

# CORS ayarları (tüm originlere izin ver - production'da kısıtla)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# PYDANTIC MODELLER
# ==============================================================================

class SUTCodeRequest(BaseModel):
    """SUT kodu hesaplama isteği."""
    kodlar: List[str] = Field(
        ...,
        description="Hesaplanacak SUT kodları listesi",
        example=["1000", "L111820", "R100010", "908200"]
    )

    class Config:
        json_schema_extra = {
            "example": {
                "kodlar": ["1000", "L111820", "R100010"]
            }
        }


class PriceItem(BaseModel):
    """Tek bir SUT kodunun fiyat bilgisi."""
    sut_kodu: str = Field(..., description="SUT kodu")
    fiyat: Optional[float] = Field(None, description="Hesaplanan fiyat (TL)")
    durum: str = Field(..., description="İşlem durumu: 'basarili' veya 'hata'")
    aciklama: str = Field(..., description="Fiyatlandırma detayı")


class PriceSummary(BaseModel):
    """Fiyat hesaplama özeti."""
    toplam_tutar: float = Field(..., description="Toplam tutar (TL)")
    toplam_kod: int = Field(..., description="Toplam kod sayısı")
    basarili: int = Field(..., description="Başarılı hesaplama sayısı")
    hatali: int = Field(..., description="Hatalı hesaplama sayısı")


class PriceResponse(BaseModel):
    """Fiyat hesaplama yanıtı."""
    items: List[PriceItem] = Field(..., description="Her kodun fiyat detayı")
    ozet: PriceSummary = Field(..., description="Hesaplama özeti")


class HealthResponse(BaseModel):
    """Sağlık kontrolü yanıtı."""
    status: str
    message: str
    data_loaded: bool
    version: str


class RulesResponse(BaseModel):
    """Kurallar bilgisi yanıtı."""
    kdv_orani: float
    puan_katsayisi: float
    l_kod_araliklari: List[dict]
    kod_90x_araligi: dict
    ozel_prefixler: List[str]


# ==============================================================================
# ENDPOINTS
# ==============================================================================

@app.get(
    "/",
    summary="Ana Sayfa",
    description="API'nin çalıştığını doğrular.",
    tags=["Genel"]
)
async def root():
    """API ana sayfası."""
    return {
        "message": "🏥 SUT Fiyat Hesaplayıcı API'sine hoş geldiniz!",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health"
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Sağlık Kontrolü",
    description="API'nin durumunu ve verilerin yüklenip yüklenmediğini kontrol eder.",
    tags=["Genel"]
)
async def health_check():
    """API sağlık kontrolü."""
    return HealthResponse(
        status="healthy" if dataframes else "unhealthy",
        message="Veriler yüklendi" if dataframes else f"Veri yükleme hatası: {data_error}",
        data_loaded=dataframes is not None,
        version="4.1.0"
    )


@app.get(
    "/rules",
    response_model=RulesResponse,
    summary="Fiyatlandırma Kuralları",
    description="Mevcut fiyatlandırma kurallarını ve sabitlerini döndürür.",
    tags=["Bilgi"]
)
async def get_rules():
    """Fiyatlandırma kurallarını döndürür."""
    return RulesResponse(
        kdv_orani=KDV_ORANI,
        puan_katsayisi=PUAN_KATSAYISI,
        l_kod_araliklari=[
            {"alt": r[0], "ust": r[1]} for r in L_CODE_RANGES
        ],
        kod_90x_araligi={"alt": CODE_90X_RANGE[0], "ust": CODE_90X_RANGE[1]},
        ozel_prefixler=["R", "912", "G1"]
    )


@app.post(
    "/calculate",
    response_model=PriceResponse,
    summary="Fiyat Hesapla",
    description="""
SUT kodları için fiyat hesaplar.

**Örnek İstek:**
```json
{
    "kodlar": ["1000", "L111820", "R100010"]
}
```

**Kurallar:**
- Branş kodu (örn: 1000) veya P kodu varsa paket modu aktif olur
- Paket modunda sadece istisnalar (EK-2A-2, R, 912, G1, özel L/90x aralıkları) fiyatlanır
- Diğer kodlar pakete dahil (0 TL)
    """,
    tags=["Fiyatlandırma"]
)
async def calculate_prices(request: SUTCodeRequest):
    """SUT kodları için fiyat hesaplar."""
    if not dataframes:
        raise HTTPException(
            status_code=503,
            detail=f"Veri setleri yüklenemedi: {data_error}"
        )

    if not request.kodlar:
        raise HTTPException(
            status_code=400,
            detail="En az bir SUT kodu gerekli"
        )

    if len(request.kodlar) > 100:
        raise HTTPException(
            status_code=400,
            detail="Tek seferde en fazla 100 kod hesaplanabilir"
        )

    # Fiyat hesapla
    results, details = get_prices(request.kodlar, dataframes)

    # Response formatla
    response = format_price_response(request.kodlar, results, details)

    return PriceResponse(**response)


@app.get(
    "/calculate",
    response_model=PriceResponse,
    summary="Fiyat Hesapla (GET)",
    description="""
GET metodu ile fiyat hesaplama. Kodları query parameter olarak gönder.

**Örnek:** `/calculate?kodlar=1000&kodlar=L111820&kodlar=R100010`
    """,
    tags=["Fiyatlandırma"]
)
async def calculate_prices_get(
        kodlar: List[str] = Query(
            ...,
            description="Hesaplanacak SUT kodları",
            example=["1000", "L111820"]
        )
):
    """GET metodu ile fiyat hesaplama."""
    if not dataframes:
        raise HTTPException(
            status_code=503,
            detail=f"Veri setleri yüklenemedi: {data_error}"
        )

    if not kodlar:
        raise HTTPException(
            status_code=400,
            detail="En az bir SUT kodu gerekli"
        )

    if len(kodlar) > 100:
        raise HTTPException(
            status_code=400,
            detail="Tek seferde en fazla 100 kod hesaplanabilir"
        )

    results, details = get_prices(kodlar, dataframes)
    response = format_price_response(kodlar, results, details)

    return PriceResponse(**response)


@app.get(
    "/code/{sut_kodu}",
    response_model=PriceItem,
    summary="Tek Kod Sorgula",
    description="Tek bir SUT kodunun fiyatını sorgular (standalone mod).",
    tags=["Fiyatlandırma"]
)
async def get_single_code(sut_kodu: str):
    """Tek bir SUT kodunun fiyatını sorgular."""
    if not dataframes:
        raise HTTPException(
            status_code=503,
            detail=f"Veri setleri yüklenemedi: {data_error}"
        )

    results, details = get_prices([sut_kodu], dataframes)

    fiyat = results.get(sut_kodu)
    detay = details.get(sut_kodu, "-")

    if isinstance(fiyat, (int, float)):
        return PriceItem(
            sut_kodu=sut_kodu,
            fiyat=round(fiyat, 2),
            durum="basarili",
            aciklama=detay
        )
    else:
        return PriceItem(
            sut_kodu=sut_kodu,
            fiyat=None,
            durum="hata",
            aciklama=fiyat if fiyat else "Kod bulunamadı"
        )


# ==============================================================================
# ANA GİRİŞ NOKTASI
# ==============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )