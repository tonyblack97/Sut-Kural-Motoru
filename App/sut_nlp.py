# sut_nlp.py
# -*- coding: utf-8 -*-
"""
SUT NLP Modülü
EK-2A-2'de başlık referansı olarak verilen SUT kodlarını 
EK-2B'de fuzzy matching ile bulur.
"""

import re
import pandas as pd
from rapidfuzz import fuzz, process

# ==============================================================================
# EK-2A-2'DE BAŞLIK REFERANSI OLARAK VERİLEN BAŞLIKLAR
# ==============================================================================

EK2A2_REFERENCE_HEADERS = [
    "10. TÜRKİYE HALK SAĞLIĞI KURUMU MERKEZ LABORATUVARI (REFİK SAYDAM HIFZISSIHHA) PANELİ",
    "9.C.1. ONKOLOJİK MOLEKÜLER TETKİKLER",
    "9.C. MOLEKÜLER GENETİK TETKİKLER",
    "9.B.1. MOLEKÜLER SİTOGENETİK TETKİKLER",
    "9.B. SİTOGENETİK TETKİKLER",
    "9.A-Moleküler Mikrobiyoloji",
    "Kortizol-İnsülin Uyarı Testi",
    "Büyüme hormonu-İnsülin Uyarı Testi",
    "TSH-TRH Uyarı Testi",
    "Prolaktin-TRH Uyarı Testi",
    "Prolaktin-L-DOPA Baskılama Testi",
    "LH-LHRH Uyarı Testi",
    "FSH-LHRH Uyarı Testi",
    "C peptid-Glukagon Uyarı Testi",
    "Aminoasitler ve Türevleri",
    "Alerji Testleri",
    "Monoklonal Antikor (Akım sitometresi)",
    "17-OH Progesteron-ACTH Uyarı Testi",
    "Kortizol-ACTH Uyarı Testi",
    "DHEA-SO4-ACTH Uyarı Testi",
    "Testosteron-ACTH Uyarı Testi",
    "11-Deoksikortizol-ACTH Uyarı Testi",
    "Androstenedion-ACTH Uyarı Testi",
    "ACTH-Glukagon Uyarı Testi",
    "Kortizol-Glukagon Uyarı Testi",
    "Büyüme hormonu-Glukagon Uyarı Testi",
    "8.3.1. BİLGİSAYARLI TOMOGRAFİ (BT)",
    "8.3.2. MANYETİK REZONANS GÖRÜNTÜLEME (MRG)",
]

# Bu başlıklar için alt başlıklar dahil, sonraki ANA başlığa kadar al
DEEP_SEARCH_HEADERS = [
    "10. TÜRKİYE HALK SAĞLIĞI KURUMU MERKEZ LABORATUVARI (REFİK SAYDAM HIFZISSIHHA) PANELİ",
    "Alerji Testleri"
]


# ==============================================================================
# NORMALİZASYON FONKSİYONU
# ==============================================================================

def normalize_text(text):
    """
    Metni normalize eder:
    - Büyük harfe çevirir
    - Türkçe karakterleri ASCII'ye dönüştürür
    - Noktalama işaretlerini temizler
    - Fazla boşlukları kaldırır
    """
    if not text or pd.isna(text):
        return ""

    text = str(text).strip().upper()

    # Türkçe karakterleri ASCII'ye çevir
    tr_map = {
        'İ': 'I', 'ı': 'I',
        'Ş': 'S', 'ş': 'S',
        'Ğ': 'G', 'ğ': 'G',
        'Ü': 'U', 'ü': 'U',
        'Ö': 'O', 'ö': 'O',
        'Ç': 'C', 'ç': 'C',
    }
    for tr_char, ascii_char in tr_map.items():
        text = text.replace(tr_char, ascii_char)

    # Noktalama ve özel karakterleri boşluğa çevir
    text = re.sub(r'[^\w\s]', ' ', text)

    # Çoklu boşlukları tek boşluğa indir
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


# ==============================================================================
# YARDIMCI FONKSİYONLAR
# ==============================================================================

def is_main_header(header_text):
    """
    Ana başlık mı kontrol eder.
    Ana başlık = Numara ile başlayan (örn: "10.", "9.", "8.3.1.")
    """
    if not header_text:
        return False
    return bool(re.match(r'^\d+\.', header_text.strip()))


def is_deep_search_header(header):
    """Bu başlık için derin arama yapılacak mı?"""
    normalized_header = normalize_text(header)
    for deep_header in DEEP_SEARCH_HEADERS:
        if normalize_text(deep_header) in normalized_header or normalized_header in normalize_text(deep_header):
            return True
    return False


# ==============================================================================
# EK-2B BAŞLIK HARİTASI OLUŞTURMA
# ==============================================================================

def build_ek2b_header_code_map(df_ek2b):
    """
    EK-2B'de her başlık altındaki SUT kodlarını harita olarak döndürür.

    Başlık satırı: SUT KODU boş, İŞLEM ADI dolu
    Bir sonraki başlığa kadar olan satırlar o başlığa ait

    Returns:
        dict: {başlık_adı: set(sut_kodları)}
    """
    header_map = {}
    current_header = None

    sut_kodu_col = 'SUT KODU'
    islem_adi_col = df_ek2b.columns[1]  # İŞLEM ADI

    for idx, row in df_ek2b.iterrows():
        sut_kodu = str(row[sut_kodu_col]).strip() if pd.notna(row[sut_kodu_col]) else ""
        islem_adi = str(row[islem_adi_col]).strip() if pd.notna(row[islem_adi_col]) else ""

        # SUT kodu boş VE işlem adı var → Başlık satırı
        if (not sut_kodu or sut_kodu == 'nan') and islem_adi and islem_adi != 'nan':
            current_header = islem_adi
            if current_header not in header_map:
                header_map[current_header] = set()

        # SUT kodu var → Bu başlığa ait işlem
        elif sut_kodu and sut_kodu != 'nan' and current_header:
            header_map[current_header].add(sut_kodu)

    return header_map


def get_deep_search_codes(df_ek2b, target_header, threshold=85):
    """
    Belirli bir başlık için derin arama yapar.
    Alt başlıklar dahil, sonraki ANA başlığa kadar tüm kodları alır.

    Args:
        df_ek2b: EK-2B DataFrame
        target_header: Hedef başlık
        threshold: Eşleşme eşiği

    Returns:
        set: Bulunan SUT kodları
    """
    codes = set()
    sut_kodu_col = 'SUT KODU'
    islem_adi_col = df_ek2b.columns[1]

    normalized_target = normalize_text(target_header)
    found_header = False

    for idx, row in df_ek2b.iterrows():
        sut_kodu = str(row[sut_kodu_col]).strip() if pd.notna(row[sut_kodu_col]) else ""
        islem_adi = str(row[islem_adi_col]).strip() if pd.notna(row[islem_adi_col]) else ""

        # Başlık satırı mı?
        is_header_row = (not sut_kodu or sut_kodu == 'nan') and islem_adi and islem_adi != 'nan'

        if is_header_row:
            normalized_islem = normalize_text(islem_adi)

            # Hedef başlığı bulduk mu?
            if not found_header:
                # Fuzzy matching ile kontrol
                score = fuzz.token_set_ratio(normalized_target, normalized_islem)
                if score >= threshold:
                    found_header = True
                    continue
            else:
                # Hedef başlığı bulduk, şimdi sonraki ANA başlığı arıyoruz
                # Eğer bu bir ANA başlık ise (numara ile başlıyor) dur
                if is_main_header(islem_adi):
                    break
                # Alt başlık ise devam et

        # Hedef başlık bulunduysa ve bu bir kod satırı ise ekle
        elif found_header and sut_kodu and sut_kodu != 'nan':
            codes.add(sut_kodu)

    return codes


# ==============================================================================
# FUZZY MATCHING
# ==============================================================================

def find_best_match(query, candidates, threshold=85):
    """
    Verilen sorgu için aday listesinden en iyi eşleşmeyi bulur.
    """
    if not query or not candidates:
        return None, 0

    normalized_query = normalize_text(query)

    # Normalize edilmiş adaylar
    normalized_candidates = {}
    for c in candidates:
        norm_c = normalize_text(c)
        if norm_c:
            normalized_candidates[norm_c] = c

    if not normalized_candidates:
        return None, 0

    # 1. BİREBİR EŞLEŞME (en yüksek öncelik)
    if normalized_query in normalized_candidates:
        return normalized_candidates[normalized_query], 100

    # 2. FUZZY MATCHING (ratio öncelikli)
    best_match = None
    best_score = 0

    for norm_candidate, original_candidate in normalized_candidates.items():
        # ratio: Kesin benzerlik (uzunluk dahil)
        ratio_score = fuzz.ratio(normalized_query, norm_candidate)

        # token_sort_ratio: Kelime sırası farklı olabilir
        token_sort_score = fuzz.token_sort_ratio(normalized_query, norm_candidate)

        # İki skorun ortalaması (token_set_ratio kullanmıyoruz)
        avg_score = (ratio_score + token_sort_score) / 2

        if avg_score > best_score:
            best_score = avg_score
            best_match = original_candidate

    if best_score >= threshold:
        return best_match, best_score

    return None, 0


# ==============================================================================
# ANA FONKSİYON: IMPLIED CODES
# ==============================================================================

def get_nlp_implied_codes(df_ek2b, reference_headers=None, threshold=85, debug=False):
    """
    EK-2A-2'de başlık referansı olarak verilen SUT kodlarını NLP ile bulur.

    Args:
        df_ek2b: EK-2B DataFrame
        reference_headers: Aranacak başlık listesi (None ise varsayılan liste kullanılır)
        threshold: Minimum eşleşme skoru (0-100)
        debug: True ise eşleşme detaylarını döndürür

    Returns:
        set: Bulunan SUT kodları
        dict: (debug=True ise) Eşleşme detayları
    """
    if reference_headers is None:
        reference_headers = EK2A2_REFERENCE_HEADERS

    # EK-2B'den başlık haritası oluştur (normal arama için)
    header_map = build_ek2b_header_code_map(df_ek2b)
    ek2b_headers = list(header_map.keys())

    implied_codes = set()
    match_details = {}

    for ref_header in reference_headers:
        # Bu başlık için derin arama mı yapılacak?
        if is_deep_search_header(ref_header):
            # Derin arama: Alt başlıklar dahil, sonraki ANA başlığa kadar
            codes = get_deep_search_codes(df_ek2b, ref_header, threshold)
            implied_codes.update(codes)

            if debug:
                match_details[ref_header] = {
                    'matched_to': f"{ref_header} (Derin Arama)",
                    'score': 100,
                    'code_count': len(codes),
                    'deep_search': True
                }
        else:
            # Normal arama: Sadece bu başlık altındaki kodlar
            best_match, score = find_best_match(ref_header, ek2b_headers, threshold)

            if best_match:
                codes = header_map[best_match]
                implied_codes.update(codes)

                if debug:
                    match_details[ref_header] = {
                        'matched_to': best_match,
                        'score': score,
                        'code_count': len(codes),
                        'deep_search': False
                    }
            else:
                if debug:
                    match_details[ref_header] = {
                        'matched_to': None,
                        'score': 0,
                        'code_count': 0,
                        'deep_search': False
                    }

    if debug:
        return implied_codes, match_details

    return implied_codes


# ==============================================================================
# YARDIMCI: SUT KODU KONTROLÜ
# ==============================================================================

def is_code_in_implied(code, implied_codes):
    """
    Verilen SUT kodunun implied codes içinde olup olmadığını kontrol eder.
    """
    return str(code).strip() in implied_codes


# ==============================================================================
# TEST / DEBUG
# ==============================================================================

if __name__ == "__main__":
    print("SUT NLP Modülü Test")
    print("=" * 50)

    # Test
    test_headers = ["Aminoasitler ve Türevleri", "10. TÜRKİYE HALK SAĞLIĞI KURUMU"]

    for h in test_headers:
        print(f"Header: {h}")
        print(f"  Derin Arama: {is_deep_search_header(h)}")
        print(f"  Ana Başlık: {is_main_header(h)}")
        print()
