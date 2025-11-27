# -*- coding: utf-8 -*-
import pandas as pd
import os
import re
import random

def clean_col_names(df, file_identifier):
    """Cleans DataFrame column names based on the file type."""
    df.columns = [re.sub(r'\s+', ' ', str(col)).strip() for col in df.columns]

    rename_map = {}
    if file_identifier == 'ek2a':
        rename_map = {df.columns[0]: 'SUT KODU', df.columns[10]: 'Fiyat'}
    elif file_identifier == 'ek2a2':
        rename_map = {'İŞLEM KODU': 'SUT KODU'}
    elif file_identifier in ['ek2b', 'ek2c']:
        rename_map = {'İŞLEM KODU': 'SUT KODU', 'İŞLEM PUANI': 'Puan'}
        
    df.rename(columns=rename_map, inplace=True)
    if file_identifier in ['ek2b', 'ek2c']:
        if 'İŞLEM PUANI' in df.columns and 'Puan' not in df.columns:
             df.rename(columns={'İŞLEM PUANI': 'Puan'}, inplace=True)
    return df

# @st.cache_data # This decorator is for Streamlit app, not standalone script
def load_dataframes():
    """
    Loads all SUT Excel files into pandas DataFrames.
    This function is designed to be imported by a Streamlit app.
    """
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

        df_ek2a = pd.read_excel(paths["ek2a"], header=2)
        dataframes['ek2a'] = clean_col_names(df_ek2a, 'ek2a')
        dataframes['ek2a']['SUT KODU'] = dataframes['ek2a']['SUT KODU'].astype(str).str.strip()

        df_ek2a2 = pd.read_excel(paths["ek2a2"], header=1)
        dataframes['ek2a2'] = clean_col_names(df_ek2a2, 'ek2a2')
        dataframes['ek2a2']['SUT KODU'] = dataframes['ek2a2']['SUT KODU'].astype(str).str.strip()

        df_ek2b = pd.read_excel(paths["ek2b"], header=1)
        dataframes['ek2b'] = clean_col_names(df_ek2b, 'ek2b')
        dataframes['ek2b']['SUT KODU'] = dataframes['ek2b']['SUT KODU'].astype(str).str.strip()

        df_ek2c = pd.read_excel(paths["ek2c"], header=1)
        dataframes['ek2c'] = clean_col_names(df_ek2c, 'ek2c')
        dataframes['ek2c']['SUT KODU'] = dataframes['ek2c']['SUT KODU'].astype(str).str.strip()
        
        # Return format expected by the Streamlit app
        return dataframes, None

    except FileNotFoundError as e:
        return None, f"Dosya bulunamadi: {e.filename}"
    except Exception as e:
        return None, f"Veri yuklenirken hata olustu: {str(e)}"

def get_prices(sut_codes_list, dataframes):
    """
    Calculates prices and returns details for the Streamlit app.
    """
    if dataframes is None: return {"hata": "Veri setleri yuklenemedi."}, {}

    df_ek2a, df_ek2a2, df_ek2b, df_ek2c = dataframes['ek2a'], dataframes['ek2a2'], dataframes['ek2b'], dataframes['ek2c']
    
    # Clean up the input list
    sut_codes_list = [str(code).strip() for code in sut_codes_list]

    ek2a_codes_set = set(df_ek2a['SUT KODU'])
    ek2a2_codes_set = set(df_ek2a2['SUT KODU'])
    
    # Yeni kural: Paket mantigini hem 'P' kodlari hem de EK-2A'daki ana muayeneler tetikler.
    package_trigger_codes = {code for code in sut_codes_list if code in ek2a_codes_set or code.startswith('P')}
    has_package = bool(package_trigger_codes)
    
    results = {}
    details = {}
    KDV_ORANI = 1.10
    PUAN_KATSAYISI = 0.593

    for code in sut_codes_list:
        if has_package and code not in ek2a2_codes_set and code not in package_trigger_codes:
            results[code] = 0.0
            details[code] = "Pakete dahil (ucretsiz)"
            continue

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
                    details[code] = "EK-2A'dan hesaplandi" if pd.notna(base_price) else "Hata"
                else:
                    results[code] = "P Kodu bulunamadi"
                    details[code] = "Hata"
        
        elif code in ek2a_codes_set:
            price_row = df_ek2a[df_ek2a['SUT KODU'] == code]
            if not price_row.empty:
                base_price = pd.to_numeric(price_row['Fiyat'].iloc[0], errors='coerce')
                results[code] = round(base_price * KDV_ORANI, 2) if pd.notna(base_price) else "Fiyat (EK-2A) bulunamadi"
                details[code] = "EK-2A'dan hesaplandi" if pd.notna(base_price) else "Hata"
            else:
                 results[code] = "Kod EK-2A'da bulunamadi"
                 details[code] = "Hata"
        else:
            price_row = df_ek2b[df_ek2b['SUT KODU'] == code]
            if not price_row.empty:
                puan = pd.to_numeric(price_row['Puan'].iloc[0], errors='coerce')
                results[code] = round(puan * PUAN_KATSAYISI * KDV_ORANI, 2) if pd.notna(puan) else "Puan (EK-2B) bulunamadi"
                details[code] = f"EK-2B'den hesaplandi (Puan: {puan})" if pd.notna(puan) else "Hata"
            else:
                results[code] = "Kod hicbir listede bulunamadi"
                details[code] = "Hata"

    return results, details

# Test block for specific codes
if __name__ == "__main__":
    all_dataframes, load_error = load_dataframes()
    
    if load_error:
        print(f"Hata: Veriler yuklenemedi. {load_error}")
    elif all_dataframes:
        test_sut_codes = ['1000', 'L101850', 'L107020', 'R100320']
        
        print(f"--- TEST EDILECEK SUT KODLARI: {test_sut_codes} ---\n")
        
        results, details = get_prices(test_sut_codes, all_dataframes)
        
        print("--- HESAPLANAN FIYATLAR ---")
        for code in test_sut_codes:
            price_str = f"{results.get(code, 'Bulunamadi'):.2f} TL" if isinstance(results.get(code), (int, float)) else results.get(code, 'Bulunamadi')
            print(f"SUT Kodu: {code}, Fiyat: {price_str}, Aciklama: {details.get(code, 'Aciklama yok')}")
        
        total_price = sum(v for v in results.values() if isinstance(v, (int, float)))
        print(f"\nTOPLAM FIYAT: {total_price:.2f} TL")
    else:
        print("Veriler yuklenemedi.")
