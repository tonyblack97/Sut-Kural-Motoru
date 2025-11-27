# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import os
import re

# Sayfa yapılandırması
st.set_page_config(
    page_title="SUT Fiyat Hesaplayıcı",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS ile özel stil
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
    /* Diğer stiller aynı kalacak */
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# YENİ SENARYOYA GÖRE GÜNCELLENMİŞ FONKSİYONLAR
# ==============================================================================

def clean_col_names(df, file_identifier):
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

@st.cache_data
def load_dataframes():
    """Loads all SUT Excel files into pandas DataFrames."""
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    sut_dir_path = os.path.join(desktop_path, "SUT Kuralları")

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
        
        return dataframes, None
    except FileNotFoundError as e:
        return None, f"Dosya bulunamadi: {e.filename}"
    except Exception as e:
        return None, f"Veri yuklenirken hata olustu: {str(e)}"

def get_prices(sut_codes_list, dataframes):
    if dataframes is None: return {"hata": "Veri setleri yuklenemedi."}, {}

    df_ek2a, df_ek2a2, df_ek2b, df_ek2c = dataframes['ek2a'], dataframes['ek2a2'], dataframes['ek2b'], dataframes['ek2c']
    
    sut_codes_list = [str(code).strip() for code in sut_codes_list]
    ek2a_codes_set = set(df_ek2a['SUT KODU'])
    ek2a2_codes_set = set(df_ek2a2['SUT KODU'])
    
    package_trigger_codes = {code for code in sut_codes_list if code in ek2a_codes_set or code.startswith('P')}
    is_package_active = bool(package_trigger_codes)
    
    results, details = {}, {}
    KDV_ORANI, PUAN_KATSAYISI = 1.10, 0.593

    for code in sut_codes_list:
        is_trigger = code in package_trigger_codes

        if is_trigger:
            if code.startswith('P'):
                price_row_c = df_ek2c[df_ek2c['SUT KODU'] == code]
                if not price_row_c.empty:
                    puan = pd.to_numeric(price_row_c['Puan'].iloc[0], errors='coerce')
                    results[code] = round(puan * PUAN_KATSAYISI * KDV_ORANI, 2) if pd.notna(puan) else "Puan (EK-2C) bulunamadi"
                    details[code] = f"EK-2C'den hesaplandi (Puan: {puan})" if pd.notna(puan) else "Hata"
                else:
                    price_row_a = df_ek2a[df_ek2a['SUT KODU'] == code]
                    if not price_row_a.empty:
                        base_price = pd.to_numeric(price_row_a['Fiyat'].iloc[0], errors='coerce')
                        results[code] = round(base_price * KDV_ORANI, 2) if pd.notna(base_price) else "Fiyat (EK-2A) bulunamadi"
                        details[code] = "EK-2A'dan hesaplandi (P kodu)" if pd.notna(base_price) else "Hata"
                    else:
                        results[code], details[code] = "P Kodu bulunamadi", "Hata"
            else: # EK-2A trigger
                price_row_a = df_ek2a[df_ek2a['SUT KODU'] == code]
                if not price_row_a.empty:
                    base_price = pd.to_numeric(price_row_a['Fiyat'].iloc[0], errors='coerce')
                    results[code] = round(base_price * KDV_ORANI, 2) if pd.notna(base_price) else "Fiyat (EK-2A) bulunamadi"
                    details[code] = "EK-2A'dan hesaplandi (Branş Paketi)" if pd.notna(base_price) else "Hata"
                else:
                    results[code], details[code] = "Kod EK-2A'da bulunamadi", "Hata"
        else: # Trigger olmayan hizmetler
            if is_package_active:
                if code in ek2a2_codes_set:
                    price_row_b = df_ek2b[df_ek2b['SUT KODU'] == code]
                    if not price_row_b.empty:
                        puan = pd.to_numeric(price_row_b['Puan'].iloc[0], errors='coerce')
                        results[code] = round(puan * PUAN_KATSAYISI * KDV_ORANI, 2) if pd.notna(puan) else "Puan (EK-2B) bulunamadi"
                        details[code] = f"EK-2B'den hesaplandi (Paket istisnasi)" if pd.notna(puan) else "Hata"
                    else:
                        results[code], details[code] = "Kod EK-2B'de bulunamadi", "Hata"
                else:
                    results[code], details[code] = 0.0, "Pakete dahil (ucretsiz)"
            else: # Standalone hizmetler
                price_row_b = df_ek2b[df_ek2b['SUT KODU'] == code]
                if not price_row_b.empty:
                    puan = pd.to_numeric(price_row_b['Puan'].iloc[0], errors='coerce')
                    results[code] = round(puan * PUAN_KATSAYISI * KDV_ORANI, 2) if pd.notna(puan) else "Puan (EK-2B) bulunamadi"
                    details[code] = f"EK-2B'den hesaplandi (Standalone)" if pd.notna(puan) else "Hata"
                else:
                    results[code], details[code] = "Kod EK-2B'de bulunamadi", "Hata"

    return results, details

# ==============================================================================
# ANA UYGULAMA (Değişiklik yok)
# ==============================================================================
st.markdown('<div class="main-header">🏥 SUT Fiyat Hesaplayıcı</div>', unsafe_allow_html=True)
# ... (kalan UI kodu öncekiyle aynı)
with st.sidebar:
    st.header("📋 Bilgilendirme")
    st.info("v3.0 - Son Senaryo Uyumlu")
    st.info("""
    **Kullanım:**
    1. SUT kodlarını girin (her satıra bir kod)
    2. "Fiyatları Hesapla" butonuna tıklayın
    3. Sonuçları görüntüleyin
    """)
    st.header("⚙️ Ayarlar")
    show_details = st.checkbox("Detaylı açıklamaları göster", value=True)
    st.markdown("---")
    st.caption("Desktop/SUT Kuralları klasöründen veri çekiyor")

with st.spinner("📂 Veriler yükleniyor..."):
    dataframes, error = load_dataframes()

if error:
    st.error(f"❌ **Hata:** {error}")
    st.stop()
else:
    st.success("✅ Veriler başarıyla yüklendi!")

col1, col2 = st.columns([1, 1])
with col1:
    st.subheader("📝 SUT Kodları Girişi")
    kod_input = st.text_area("Her satıra bir SUT kodu yazın:", height=300, placeholder="1000 (Branş Kodu)\n700050 (İstisna)\n801170 (Pakete Dahil Olacak)")
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
                    sonuc_data.append({"SUT Kodu": kod, "Fiyat (TL)": f"{fiyat:.2f}", "Açıklama": detay if show_details else "-"})
                else:
                    sonuc_data.append({"SUT Kodu": kod, "Fiyat (TL)": "HATA", "Açıklama": fiyat})
            df_sonuc = pd.DataFrame(sonuc_data)
            if not show_details:
                df_sonuc = df_sonuc.drop(columns=['Açıklama'])
            st.dataframe(df_sonuc, use_container_width=True, hide_index=True)
            st.markdown(f'<div class="total-box">💵 TOPLAM TUTAR: {toplam:.2f} TL</div>', unsafe_allow_html=True)
            st.markdown("---")
            col_a, col_b, col_c = st.columns(3)
            with col_a: st.metric("Toplam Kod", len(kodlar))
            with col_b: st.metric("Başarılı", sum(1 for r in results.values() if isinstance(r, (int, float))))
            with col_c: st.metric("Hatalı", len(kodlar) - sum(1 for r in results.values() if isinstance(r, (int, float))))
    else:
        st.info("👈 Sol taraftan SUT kodlarını girin ve 'Fiyatları Hesapla' butonuna tıklayın")
st.markdown("---")
st.caption("SUT Fiyat Hesaplayıcı v3.0 | Son Senaryo Entegre Edildi")
