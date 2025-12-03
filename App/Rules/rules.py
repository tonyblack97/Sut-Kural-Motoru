# -*- coding: utf-8 -*-
"""
SUT Fiyat Hesaplayıcı - Kurallar Modülü
Dosya Yolu: App/Rules/rules.py

Bu dosya tüm fiyatlandırma kurallarını ve sabitlerini içerir.
"""

# ==============================================================================
# SABİTLER
# ==============================================================================

KDV_ORANI = 1.10
PUAN_KATSAYISI = 0.593

# ==============================================================================
# L KODU ÖZEL ARALIKLARI
# Her tuple: (alt_sinir, ust_sinir)
# ==============================================================================

L_CODE_RANGES = [
    (114790, 119670),
    (112940, 113100),
    (112100, 112530),
    (111100, 111800),
    (109350, 110870),
    (107640, 107820),
]

# ==============================================================================
# 90X KODU ÖZEL ARALIKLARI
# ==============================================================================

CODE_90X_RANGE = (908111, 908339)

# ==============================================================================
# ÖZEL KOD PREFİXLERİ (Her zaman EK-2B'den fiyatlanır)
# ==============================================================================

SPECIAL_PREFIXES = ['912', 'G1', 'R']


# ==============================================================================
# FONKSİYONLAR
# ==============================================================================

def is_in_l_code_range(numeric_value):
    """
    Verilen sayısal değerin L kodu özel aralıklarından birinde olup olmadığını kontrol eder.

    Args:
        numeric_value (int): L kodunun sayısal kısmı

    Returns:
        bool: Aralıkta ise True, değilse False
    """
    for lower, upper in L_CODE_RANGES:
        if lower <= numeric_value <= upper:
            return True
    return False


def is_in_90x_range(numeric_value):
    """
    Verilen sayısal değerin 90x özel aralığında olup olmadığını kontrol eder.

    Args:
        numeric_value (int): Kod değeri

    Returns:
        bool: Aralıkta ise True, değilse False
    """
    lower, upper = CODE_90X_RANGE
    return lower <= numeric_value <= upper


def is_special_ek2b_code(code):
    """
    Belirli kurallara uyan kodları kontrol eder.
    Bu kodlar paket aktif olsa bile her zaman EK-2B'den fiyatlanır.

    Kurallar:
    - '90' ile başlayan ve 908111-908339 aralığındaki kodlar
    - '912' ile başlayan tüm kodlar
    - 'G1' ile başlayan tüm kodlar
    - 'R' ile başlayan tüm kodlar
    - 'L' ile başlayan ve belirli sayısal aralıklardaki kodlar

    Args:
        code: SUT kodu (string veya sayısal)

    Returns:
        tuple: (is_special: bool, detail_message: str veya None)
    """
    code_str = str(code).strip()

    # Kural 1: '90' ile başlayan kodlar - özel aralık kontrolü
    if code_str.startswith('90'):
        try:
            code_int = int(code_str)
            if is_in_90x_range(code_int):
                return True, "EK-2B (90x Özel Aralık)"
        except ValueError:
            pass

    # Kural 2: '912' ile başlayan kodlar
    if code_str.startswith('912'):
        return True, "EK-2B (912 Kodu)"

    # Kural 3: 'G1' ile başlayan kodlar
    if code_str.startswith('G1'):
        return True, "EK-2B (G1 Kodu)"

    # Kural 4: 'R' ile başlayan kodlar
    if code_str.startswith('R'):
        return True, "EK-2B (R Kodu)"

    # Kural 5: 'L' ile başlayan kodlar - belirli aralıklar
    if code_str.startswith('L'):
        try:
            numeric_part = code_str[1:]  # L harfini kaldır
            code_int = int(numeric_part)

            if is_in_l_code_range(code_int):
                return True, "EK-2B (L Özel Aralık)"
        except ValueError:
            pass

    return False, None


def is_package_trigger(code, ek2a_codes_set):
    """
    Kodun paket tetikleyici olup olmadığını kontrol eder.

    Args:
        code: SUT kodu
        ek2a_codes_set: EK-2A'daki kodların seti

    Returns:
        bool: Paket tetikleyici ise True
    """
    code_str = str(code).strip()
    return code_str in ek2a_codes_set or code_str.startswith('P')


def calculate_price_from_puan(puan):
    """
    Puandan KDV dahil fiyat hesaplar.

    Args:
        puan: İşlem puanı

    Returns:
        float: KDV dahil fiyat (yuvarlanmış)
    """
    return round(puan * PUAN_KATSAYISI * KDV_ORANI, 2)


def calculate_price_from_base(base_price):
    """
    Baz fiyattan KDV dahil fiyat hesaplar.

    Args:
        base_price: Baz fiyat (KDV hariç)

    Returns:
        float: KDV dahil fiyat (yuvarlanmış)
    """
    return round(base_price * KDV_ORANI, 2)