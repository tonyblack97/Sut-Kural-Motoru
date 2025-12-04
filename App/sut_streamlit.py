# -*- coding: utf-8 -*-
"""
SUT Fiyat Hesaplayıcı - Streamlit Arayüzü
Dosya Yolu: App/sut_streamlit.py

Kullanım: streamlit run App/sut_streamlit.py
"""

from sut_nlp import get_nlp_implied_codes, is_code_in_implied

import streamlit as st
import pandas as pd

# Servis katmanını import et
from services import load_dataframes, get_prices
from Rules.rules import KDV_ORANI, PUAN_KATSAYISI

# ==============================================================================
# SAYFA YAPILANDIRMASI
# ==============================================================================

st.set_page_config(
    page_title="SUT Fiyat Hesaplayıcı",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# CSS STİLLERİ
# ==============================================================================

st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2c3e50;
        text-align: center;
        padding: 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .result-box {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #667eea;
    }
    .total-box {
        background-color: #28a745;
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        font-size: 1.75rem;
        font-weight: 700;
        text-align: center;
        margin-top: 1rem;
    }
    .error-box {
        background-color: #f8d7da;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #dc3545;
    }
    </style>
""", unsafe_allow_html=True)


# ==============================================================================
# VERİ YÜKLEME (Cached) - GÜNCELLEME
# ==============================================================================

@st.cache_data
def load_data():
    """Verileri yükle ve cache'le."""
    dataframes, error = load_dataframes()

    if dataframes and not error:
        # NLP ile implied codes ekle
        dataframes['nlp_implied_codes'] = get_nlp_implied_codes(
            dataframes['ek2b'],
            threshold=85
        )

    return dataframes, error


# ==============================================================================
# ANA UYGULAMA
# ==============================================================================

def main():
    st.markdown('<div class="main-header">🏥 SUT Fiyat Hesaplayıcı</div>', unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.header("📋 Bilgilendirme")
        st.info("**v4.1 - Modüler Yapı**")
        st.info("""
        **Kullanım:**
        1. SUT kodlarını girin (her satıra bir kod)
        2. "Fiyatları Hesapla" butonuna tıklayın
        3. Sonuçları görüntüleyin

        **Özellikler:**
        - EK-2A, EK-2A-2, EK-2B, EK-2C kontrolü
        - Otomatik KDV hesaplama
        - Kapsamlı paket fiyatlandırması
        - Toplam tutar hesaplama

        **Her Zaman EK-2B'den Fiyatlanan Kodlar:**
        - 'R' ile başlayan kodlar
        - '912' ile başlayan kodlar
        - 'G1' ile başlayan kodlar
        - 908111-908339 aralığındaki kodlar
        - Belirli 'L' kod aralıkları
        """)

        st.header("⚙️ Ayarlar")
        show_details = st.checkbox("Detaylı açıklamaları göster", value=True)

        st.markdown("---")
        st.caption(f"KDV Oranı: %{int((KDV_ORANI - 1) * 100)} | Puan Katsayısı: {PUAN_KATSAYISI}")

        st.markdown("---")
        st.header("🔗 API Erişimi")
        st.code("http://localhost:8000/docs", language=None)
        st.caption("API çalışıyorsa Swagger UI için yukarıdaki linki kullanın.")

    # Veri yükleme
    with st.spinner("📂 Veriler yükleniyor..."):
        dataframes, error = load_data()

    if error:
        st.error(f"❌ **Hata:** {error}")
        st.warning("""
        **Lütfen kontrol edin:**
        - Ana dizinde "SUT Kuralları" klasörü var mı?
        - Excel dosyaları doğru isimde mi?
        - Dosyalar okunabilir mi?
        """)
        st.stop()
    else:
        st.success("✅ Veriler başarıyla yüklendi!")

    # Ana içerik
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📝 SUT Kodları Girişi")
        kod_input = st.text_area(
            "Her satıra bir SUT kodu yazın:",
            height=300,
            placeholder="1000 (Branş Kodu)\nL114800 (Özel L aralığı)\n908200 (Özel 90x aralığı)\nG10001 (G1 kodu)\n912001 (912 kodu)"
        )
        hesapla_btn = st.button("💰 Fiyatları Hesapla", type="primary", use_container_width=True)

    with col2:
        st.subheader("📊 Sonuçlar")

        if hesapla_btn:
            if not kod_input.strip():
                st.warning("⚠️ Lütfen en az bir SUT kodu girin!")
            else:
                kodlar = [kod.strip() for kod in kod_input.split('\n') if kod.strip()]

                with st.spinner(f"⏳ {len(kodlar)} kod hesaplanıyor..."):
                    results, details = get_prices(kodlar, dataframes)

                toplam = 0
                sonuc_data = []

                for kod in kodlar:
                    fiyat = results.get(kod, "Bulunamadı")
                    detay = details.get(kod, "-")

                    if isinstance(fiyat, (int, float)):
                        toplam += fiyat
                        sonuc_data.append({
                            "SUT Kodu": kod,
                            "Fiyat (TL)": f"{fiyat:.2f}",
                            "Açıklama": detay if show_details else "-"
                        })
                    else:
                        sonuc_data.append({
                            "SUT Kodu": kod,
                            "Fiyat (TL)": "HATA",
                            "Açıklama": fiyat
                        })

                df_sonuc = pd.DataFrame(sonuc_data)

                if not show_details:
                    df_sonuc = df_sonuc.drop(columns=['Açıklama'])

                st.dataframe(df_sonuc, use_container_width=True, hide_index=True)
                st.markdown(f'<div class="total-box">💵 TOPLAM TUTAR: {toplam:.2f} TL</div>', unsafe_allow_html=True)

                st.markdown("---")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Toplam Kod", len(kodlar))
                with col_b:
                    st.metric("Başarılı", sum(1 for r in results.values() if isinstance(r, (int, float))))
                with col_c:
                    st.metric("Hatalı", len(kodlar) - sum(1 for r in results.values() if isinstance(r, (int, float))))
        else:
            st.info("👈 Sol taraftan SUT kodlarını girin ve 'Fiyatları Hesapla' butonuna tıklayın")

    st.markdown("---")
    st.caption("SUT Fiyat Hesaplayıcı v4.1 | Modüler Yapı")


if __name__ == "__main__":
    main()