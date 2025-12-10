# -*- coding: utf-8 -*-
"""
SUT Fiyat Hesaplayıcı - Basitleştirilmiş Versiyon
"""

import streamlit as st
import pandas as pd
import os
import re

from sut_nlp import get_nlp_implied_codes
from sut_cleaner import clean_all_files, preview_all_files
from services import get_prices

# Sabitler (Sadece arayüzde göstermek için. Asıl hesaplama services.py içinde)
KDV_ORANI = 1.10
PUAN_KATSAYISI = 0.593


# ... (mevcut sabitler ve CSS aynı) ...



st.set_page_config(
    page_title="SUT Fiyat Hesaplayıcı",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# app.py içinde CSS kısmına ekle (mevcut CSS'in içine)

st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        padding: 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
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

    /* YENİ: Loading Overlay */
    .loading-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.7);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 9999;
    }
    .loading-box {
        background: white;
        padding: 2rem 3rem;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        animation: pulse 1s infinite;
    }
    .loading-box h2 {
        color: #667eea;
        margin-bottom: 1rem;
    }
    .loading-box p {
        color: #666;
        margin-bottom: 1.5rem;
    }
    .loading-spinner {
        width: 50px;
        height: 50px;
        border: 5px solid #f3f3f3;
        border-top: 5px solid #667eea;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin: 0 auto;
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.02); }
    }
    </style>
""", unsafe_allow_html=True)


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


def get_ek2b_path():
    """EK-2B dosya yolunu döndürür."""
    script_dir = os.path.dirname(__file__)
    base_path = os.path.dirname(script_dir)
    return os.path.join(base_path, "SUT Kuralları", "EK-2B HİZMET BAŞI İŞLEM PUAN LİSTESİ (Yür.11.05.2024).xlsx")


@st.cache_data
def load_dataframes():
    """Tüm SUT Excel dosyalarını yükler."""

    # Streamlit'te daha güvenilir
    if hasattr(st, 'runtime'):
        # Streamlit çalışırken
        script_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        # Geliştirme ortamında
        script_dir = os.getcwd()

    # Veya daha basit:
    # script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()

    base_path = os.path.dirname(script_dir)
    sut_dir_path = os.path.join(base_path, "SUT Kuralları")

    paths = {
        "ek2a": os.path.join(sut_dir_path, "EK-2A AYAKTAN BAŞVURULARDA ÖDEME LİSTESİ (Yür. 19.09.2025).xlsx"),
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
# FİYAT HESAPLAMA (Mevcut kod aynı)
# ==============================================================================




# ==============================================================================
# ANA UYGULAMA
# ==============================================================================

def main():
    st.markdown('<div class="main-header">🏥 SUT Fiyat Hesaplayıcı</div>', unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.header("📋 Bilgilendirme")
        st.info("**v5.1 - Kural Güncelleme Desteği**")
        st.info("""
        **Paket İstisna Kuralları:**
        1. EK-2A-2'de direkt var mı?
        2. R ile başlıyor mu?
        3. NLP başlık eşleşmesi var mı?
        """)

        st.header("⚙️ Ayarlar")
        show_details = st.checkbox("Detaylı açıklamaları göster", value=True)

        st.markdown("---")
        st.caption(f"KDV: %{int((KDV_ORANI - 1) * 100)} | Katsayı: {PUAN_KATSAYISI}")

        # ================================================================
        # KURAL GÜNCELLEME BÖLÜMÜ
        # ================================================================
        st.markdown("---")
        st.header("🔄 Kural Güncelleme")
        st.caption("EK-2A-2, EK-2B, EK-2C dosyalarındaki '(Değişik...)' satırlarını temizler.")

        if st.button("📋 Önizleme Göster", use_container_width=True):
            with st.spinner("Dosyalar taranıyor..."):
                previews = preview_all_files()

            if previews['_summary']['total_changes'] == 0:
                st.success("✅ Temizlenecek satır bulunamadı.")
            else:
                st.session_state['previews'] = previews
                st.session_state['show_preview'] = True

        # Önizleme varsa göster
        if st.session_state.get('show_preview') and st.session_state.get('previews'):
            previews = st.session_state['previews']
            summary = previews['_summary']

            st.warning(f"⚠️ Toplam {summary['total_changes']} değişiklik yapılacak")

            for key, preview in previews.items():
                if key == '_summary':
                    continue

                display_name = preview.get('display_name', key)
                total = preview.get('total_changes', 0)

                if 'error' in preview:
                    st.error(f"❌ {display_name}: {preview['error']}")
                elif total == 0:
                    st.info(f"✅ {display_name}: Temizlenecek satır yok")
                else:
                    with st.expander(f"📄 {display_name} ({total} değişiklik)", expanded=False):
                        col1, col2 = st.columns(2)

                        with col1:
                            st.write(f"**Temizlenecek ({len(preview['degisik_rows'])})**")
                            for row in preview['degisik_rows'][:5]:
                                st.code(f"{row['original']}\n→ {row['cleaned']}", language=None)
                            if len(preview['degisik_rows']) > 5:
                                st.caption(f"... +{len(preview['degisik_rows']) - 5} satır")

                        with col2:
                            st.write(f"**Silinecek ({len(preview['rows_to_delete'])})**")
                            for row in preview['rows_to_delete'][:5]:
                                st.code(f"{row['islem_kodu']}", language=None)
                            if len(preview['rows_to_delete']) > 5:
                                st.caption(f"... +{len(preview['rows_to_delete']) - 5} satır")

            # Uygula butonu
            st.markdown("---")
            if st.button("🚀 Yeni Kuralları Uygula", type="primary", use_container_width=True):

                # Loading overlay göster
                loading_placeholder = st.empty()
                loading_placeholder.markdown("""
                    <div class="loading-overlay">
                        <div class="loading-box">
                            <h2>⏳ Lütfen Bekleyiniz</h2>
                            <p>Yeni kurallar uygulanıyor...</p>
                            <div class="loading-spinner"></div>
                            <p style="margin-top: 1rem; font-size: 0.9rem; color: #999;">
                                EK-2A-2, EK-2B, EK-2C dosyaları güncelleniyor
                            </p>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                # İşlemi yap
                results = clean_all_files(backup=True)

                # Loading'i kaldır
                loading_placeholder.empty()

                # Sonuçları göster
                all_success = True
                total_deleted = 0
                total_cleaned = 0

                for key, result in results.items():
                    total_deleted += result.get('deleted_rows', 0)
                    total_cleaned += result.get('cleaned_cells', 0)

                    if result['success']:
                        if result['deleted_rows'] > 0 or result['cleaned_cells'] > 0:
                            st.success(f"✅ {result['filename']}: {result['message']}")
                        else:
                            st.info(f"ℹ️ {result['filename']}: {result['message']}")
                    else:
                        st.error(f"❌ {result['filename']}: {result['message']}")
                        all_success = False

                if all_success and (total_deleted > 0 or total_cleaned > 0):
                    # Başarı mesajı
                    st.balloons()  # Konfeti efekti

                    st.markdown(f"""
                        <div style="background: linear-gradient(135deg, #28a745, #20c997); 
                                    color: white; padding: 1.5rem; border-radius: 20px; 
                                    text-align: center; margin: 1rem 0;">
                            <h3>🎉 Tüm Kurallar Başarıyla Uygulandı!</h3>
                            <p>Toplam {total_deleted} satır silindi, {total_cleaned} hücre temizlendi</p>
                        </div>
                    """, unsafe_allow_html=True)

                    # Cache'i temizle
                    st.cache_data.clear()
                    st.session_state['show_preview'] = False
                    st.session_state['previews'] = None

                    st.info("🔄 Sayfa 3 saniye içinde yenilenecek...")

                    import time
                    time.sleep(3)
                    st.rerun()

                elif all_success:
                    st.info("ℹ️ Temizlenecek satır bulunamadı.")

    # Veri yükleme
    with st.spinner("📂 Veriler yükleniyor..."):
        dataframes, error = load_dataframes()

    if error:
        st.error(f"❌ **Hata:** {error}")
        st.stop()
    else:
        nlp_count = len(dataframes.get('nlp_implied_codes', set()))
        st.success(f"✅ Veriler yüklendi! ({nlp_count} NLP eşleşmeli kod)")

        # NLP Debug
        with st.sidebar:
            st.markdown("---")
            if st.checkbox("🔍 NLP Eşleşmelerini Göster"):
                nlp_debug = dataframes.get('nlp_debug', {})
                if nlp_debug:
                    matched = sum(1 for v in nlp_debug.values() if v['matched_to'])
                    st.write(f"**Eşleşen: {matched}/{len(nlp_debug)}**")

                    for ref, info in nlp_debug.items():
                        if info['matched_to']:
                            with st.expander(f"✅ {ref[:30]}...", expanded=False):
                                st.write(f"→ {info['matched_to']}")
                                st.write(f"Skor: {info['score']}% | Kod: {info['code_count']}")

    # Ana içerik
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📝 SUT Kodları Girişi")
        kod_input = st.text_area(
            "Her satıra bir SUT kodu yazın:",
            height=300,
            placeholder="1000 (Branş Kodu)\nL109350 (NLP - Aminoasit)\nR100010 (R kodu)"
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
                st.markdown(f'<div class="total-box">💵 TOPLAM: {toplam:.2f} TL</div>', unsafe_allow_html=True)

                st.markdown("---")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Toplam", len(kodlar))
                with col_b:
                    st.metric("Başarılı", sum(1 for r in results.values() if isinstance(r, (int, float))))
                with col_c:
                    st.metric("Hatalı", len(kodlar) - sum(1 for r in results.values() if isinstance(r, (int, float))))
        else:
            st.info("👈 SUT kodlarını girin ve 'Fiyatları Hesapla' butonuna tıklayın")

    st.markdown("---")
    st.caption("SUT Fiyat Hesaplayıcı v5.1 | NLP + Kural Güncelleme")


if __name__ == "__main__":
    main()