# test_nlp.py
import pandas as pd
import os
from sut_nlp import normalize_text, find_best_match, build_ek2b_header_code_map

# EK-2B yükle
script_dir = os.path.dirname(__file__)
base_path = os.path.dirname(script_dir)
sut_dir_path = os.path.join(base_path, "SUT Kuralları")

df_ek2b = pd.read_excel(
    os.path.join(sut_dir_path, "EK-2B HİZMET BAŞI İŞLEM PUAN LİSTESİ (Yür.11.05.2024).xlsx"),
    header=1
)
df_ek2b.columns = [str(col).strip() for col in df_ek2b.columns]
df_ek2b.rename(columns={'İŞLEM KODU': 'SUT KODU'}, inplace=True)
df_ek2b['SUT KODU'] = df_ek2b['SUT KODU'].astype(str).str.strip()

# Başlık haritası
header_map = build_ek2b_header_code_map(df_ek2b)

# Test başlığı
test_header = "9.B.1. MOLEKÜLER SİTOGENETİK TETKİKLER"
print(f"Aranan: {test_header}")
print(f"Normalized: {normalize_text(test_header)}")
print()



# EK-2B'deki başlıkları ara
ek2b_headers = list(header_map.keys())
print("EK-2B'de benzer başlıklar:")
for h in ek2b_headers:
    if "MOLEKÜLER" in h.upper() or "SİTOGENETİK" in h.upper() or "SITOGENETIK" in h.upper() or "9.B" in h:
        print(f"  - {h}")
        print(f"    Normalized: {normalize_text(h)}")
        print(f"    Kod sayısı: {len(header_map[h])}")
print()

# Eşleşme bul
best_match, score = find_best_match(test_header, ek2b_headers, threshold=70)
print(f"En iyi eşleşme: {best_match}")
print(f"Skor: {score}")