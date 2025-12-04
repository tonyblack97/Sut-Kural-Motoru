# -*- coding: utf-8 -*-
"""
SUT Fiyat Hesaplayıcı - Servis Katmanı
Dosya Yolu: App/services.py

Bu dosya veri yükleme ve fiyat hesaplama fonksiyonlarını içerir.
Hem Streamlit hem de API tarafından kullanılır.
"""

import pandas as pd
import os
import re
import sys

# Rules klasörünü Python path'e ekle
current_dir = os.path.dirname(__file__)
rules_dir = os.path.join(current_dir, "Rules")
sys.path.insert(0, rules_dir)

from Rules.rules import (
    is_special_ek2b_code,
    is_package_trigger,
    calculate_price_from_puan,
    calculate_price_from_base,
)


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


def load_dataframes(base_path=None):
    """
    Tüm SUT Excel dosyalarını yükler.

    Args:
        base_path: Ana dizin yolu. None ise otomatik bulur.

    Returns:
        tuple: (dataframes dict, error message veya None)
    """
    if base_path is None:
        current_dir = os.path.dirname(__file__)
        base_path = os.path.dirname(current_dir)  # Sut-Kural-Motoru-main

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

        return dataframes, None
    except FileNotFoundError as e:
        return None, f"Dosya bulunamadı: {e.filename}"
    except Exception as e:
        return None, f"Veri yüklenirken hata oluştu: {str(e)}"


# ==============================================================================
# FİYAT HESAPLAMA FONKSİYONU
# ==============================================================================

def get_prices(sut_codes_list, dataframes):
    """
    Verilen SUT kodları için fiyatları hesaplar.

    Args:
        sut_codes_list: SUT kodları listesi
        dataframes: Yüklenmiş Excel verilerini içeren dict

    Returns:
        tuple: (results dict, details dict)
    """
    if dataframes is None:
        return {"hata": "Veri setleri yüklenemedi."}, {}

    df_ek2a = dataframes['ek2a']
    df_ek2a2 = dataframes['ek2a2']
    df_ek2b = dataframes['ek2b']
    df_ek2c = dataframes['ek2c']

    # Kodları temizle
    sut_codes_list = [str(code).strip() for code in sut_codes_list]

    # Kod setlerini oluştur
    ek2a_codes_set = set(df_ek2a['SUT KODU'])
    ek2a2_codes_set = set(df_ek2a2['SUT KODU'])

    # Paket tetikleyicilerini bul
    package_trigger_codes = {
        code for code in sut_codes_list
        if is_package_trigger(code, ek2a_codes_set)
    }
    is_package_active = bool(package_trigger_codes)

    results, details = {}, {}

    for code in sut_codes_list:
        is_trigger = code in package_trigger_codes
        is_special, special_detail = is_special_ek2b_code(code)

        if is_trigger:
            # === PAKET TETİKLEYİCİ KOD ===
            if code.startswith('P'):
                # P kodu: Önce EK-2C, sonra EK-2A
                price_row_c = df_ek2c[df_ek2c['SUT KODU'] == code]
                if not price_row_c.empty:
                    puan = pd.to_numeric(price_row_c['Puan'].iloc[0], errors='coerce')
                    if pd.notna(puan):
                        results[code] = calculate_price_from_puan(puan)
                        details[code] = f"EK-2C'den hesaplandı (Puan: {puan})"
                    else:
                        results[code] = "Puan (EK-2C) bulunamadı"
                        details[code] = "Hata"
                else:
                    price_row_a = df_ek2a[df_ek2a['SUT KODU'] == code]
                    if not price_row_a.empty:
                        base_price = pd.to_numeric(price_row_a['Fiyat'].iloc[0], errors='coerce')
                        if pd.notna(base_price):
                            results[code] = calculate_price_from_base(base_price)
                            details[code] = "EK-2A'dan hesaplandı (P kodu)"
                        else:
                            results[code] = "Fiyat (EK-2A) bulunamadı"
                            details[code] = "Hata"
                    else:
                        results[code] = "P Kodu bulunamadı"
                        details[code] = "Hata"
            else:
                # Branş kodu: EK-2A'dan fiyat
                price_row_a = df_ek2a[df_ek2a['SUT KODU'] == code]
                if not price_row_a.empty:
                    base_price = pd.to_numeric(price_row_a['Fiyat'].iloc[0], errors='coerce')
                    if pd.notna(base_price):
                        results[code] = calculate_price_from_base(base_price)
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
                if code in ek2a2_codes_set or is_special:
                    price_row_b = df_ek2b[df_ek2b['SUT KODU'] == code]
                    if not price_row_b.empty:
                        puan = pd.to_numeric(price_row_b['Puan'].iloc[0], errors='coerce')
                        if pd.notna(puan):
                            results[code] = calculate_price_from_puan(puan)
                            if is_special:
                                details[code] = f"{special_detail} - Paket istisnası"
                            else:
                                details[code] = "EK-2B'den hesaplandı (Paket istisnası)"
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
                        results[code] = calculate_price_from_puan(puan)
                        if is_special:
                            details[code] = f"{special_detail} - Standalone"
                        else:
                            details[code] = "EK-2B'den hesaplandı (Standalone)"
                    else:
                        results[code] = "Puan (EK-2B) bulunamadı"
                        details[code] = "Hata"
                else:
                    results[code] = "Kod EK-2B'de bulunamadı"
                    details[code] = "Hata"

    return results, details


# ==============================================================================
# YARDIMCI FONKSİYONLAR
# ==============================================================================

def format_price_response(sut_codes_list, results, details):
    """
    Fiyat sonuçlarını API response formatına dönüştürür.

    Returns:
        dict: Formatlanmış response
    """
    items = []
    toplam = 0.0
    basarili = 0
    hatali = 0

    for code in sut_codes_list:
        fiyat = results.get(code, "Bulunamadı")
        detay = details.get(code, "-")

        if isinstance(fiyat, (int, float)):
            toplam += fiyat
            basarili += 1
            items.append({
                "sut_kodu": code,
                "fiyat": round(fiyat, 2),
                "durum": "basarili",
                "aciklama": detay
            })
        else:
            hatali += 1
            items.append({
                "sut_kodu": code,
                "fiyat": None,
                "durum": "hata",
                "aciklama": fiyat
            })

    return {
        "items": items,
        "ozet": {
            "toplam_tutar": round(toplam, 2),
            "toplam_kod": len(sut_codes_list),
            "basarili": basarili,
            "hatali": hatali
        }
    }