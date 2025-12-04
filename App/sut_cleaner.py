# sut_cleaner.py
# -*- coding: utf-8 -*-
"""
SUT Excel Temizleyici
EK-2A-2, EK-2B, EK-2C dosyalarındaki "(Değişik ...)" satırlarını temizler.
"""

import pandas as pd
import re
import os
import shutil
from datetime import datetime

# ==============================================================================
# DOSYA YAPILANDIRMASI
# ==============================================================================

FILE_CONFIG = {
    'ek2a2': {
        'filename': 'EK-2A-2 AYAKTAN BAŞ. İLAVE OL. FAT. İŞ. LİSTESİ (Yür. 01.06.2021).xlsx',
        'header_row': 1,
        'title': 'AYAKTAN BAŞVURULARDA İLAVE OLARAK FATURALANDIRILABİLECEK İŞLEMLER LİSTESİ (EK-2/A-2)'
    },
    'ek2b': {
        'filename': 'EK-2B HİZMET BAŞI İŞLEM PUAN LİSTESİ (Yür.11.05.2024).xlsx',
        'header_row': 1,
        'title': 'HİZMET BAŞI İŞLEM PUAN LİSTESİ (EK-2/B)'
    },
    'ek2c': {
        'filename': 'EK-2C TANIYA DAYALI İŞLEM PUAN LİSTESİ (Yür.11.05.2024).xlsx',
        'header_row': 1,
        'title': 'TANIYA DAYALI İŞLEM PUAN LİSTESİ (EK-2/C)'
    }
}


# ==============================================================================
# TEMİZLEME FONKSİYONLARI
# ==============================================================================

def get_sut_dir():
    """SUT Kuralları klasör yolunu döndürür."""
    script_dir = os.path.dirname(__file__)
    base_path = os.path.dirname(script_dir)
    return os.path.join(base_path, "SUT Kuralları")


def clean_single_file(file_path, header_row, title, backup=True):
    """
    Tek bir dosyadaki "(Değişik ...)" satırlarını temizler.

    Returns:
        dict: İşlem sonucu
    """
    result = {
        'success': False,
        'message': '',
        'deleted_rows': 0,
        'cleaned_cells': 0,
        'backup_path': None,
        'output_path': None
    }

    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_dir = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        name_without_ext = os.path.splitext(filename)[0]

        # 1. BACKUP AL
        if backup:
            backup_filename = f"{name_without_ext}_BACKUP_{timestamp}.xlsx"
            backup_path = os.path.join(base_dir, backup_filename)
            shutil.copy2(file_path, backup_path)
            result['backup_path'] = backup_path

        # 2. Dosyayı oku
        df = pd.read_excel(file_path, header=header_row)
        islem_kodu_col = df.columns[0]

        # 3. "(Değişik" içeren satırları bul
        degisik_mask = df[islem_kodu_col].astype(str).str.contains(r'\(Değişik', case=False, na=False)
        degisik_indices = df[degisik_mask].index.tolist()

        if not degisik_indices:
            result['success'] = True
            result['message'] = 'Temizlenecek satır bulunamadı.'
            return result

        # 4. Silinecek satırları belirle
        rows_to_delete = []
        for idx in degisik_indices:
            if idx > 0:
                prev_idx = idx - 1
                if prev_idx not in rows_to_delete and prev_idx not in degisik_indices:
                    rows_to_delete.append(prev_idx)

        # 5. Parantezleri temizle
        cleaned_count = 0
        for idx in degisik_indices:
            original_value = str(df.at[idx, islem_kodu_col])
            cleaned_value = re.sub(r'\s*\([^)]*\)\s*', '', original_value).strip()
            df.at[idx, islem_kodu_col] = cleaned_value
            cleaned_count += 1

        # 6. Satırları sil
        df = df.drop(index=rows_to_delete)
        df = df.reset_index(drop=True)

        # 7. Kaydet
        try:
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, startrow=1)
                worksheet = writer.sheets['Sheet1']
                worksheet.cell(row=1, column=1, value=title)

            result['output_path'] = file_path

        except PermissionError:
            new_filename = f"{name_without_ext}_UPDATED_{timestamp}.xlsx"
            new_path = os.path.join(base_dir, new_filename)

            with pd.ExcelWriter(new_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, startrow=1)
                worksheet = writer.sheets['Sheet1']
                worksheet.cell(row=1, column=1, value=title)

            result['output_path'] = new_path
            result[
                'message'] = f'{len(rows_to_delete)} satır silindi, {cleaned_count} hücre temizlendi. (Yeni dosyaya kaydedildi)'
            result['success'] = True
            result['deleted_rows'] = len(rows_to_delete)
            result['cleaned_cells'] = cleaned_count
            return result

        result['success'] = True
        result['message'] = f'{len(rows_to_delete)} satır silindi, {cleaned_count} hücre temizlendi.'
        result['deleted_rows'] = len(rows_to_delete)
        result['cleaned_cells'] = cleaned_count

    except Exception as e:
        result['success'] = False
        result['message'] = f'Hata: {str(e)}'

    return result


def clean_all_files(backup=True):
    """
    EK-2A-2, EK-2B, EK-2C dosyalarını temizler.

    Returns:
        dict: Tüm dosyaların işlem sonuçları
    """
    sut_dir = get_sut_dir()
    results = {}

    for key, config in FILE_CONFIG.items():
        file_path = os.path.join(sut_dir, config['filename'])

        if os.path.exists(file_path):
            results[key] = clean_single_file(
                file_path=file_path,
                header_row=config['header_row'],
                title=config['title'],
                backup=backup
            )
            results[key]['filename'] = config['filename']
        else:
            results[key] = {
                'success': False,
                'message': 'Dosya bulunamadı',
                'filename': config['filename'],
                'deleted_rows': 0,
                'cleaned_cells': 0
            }

    return results


def preview_single_file(file_path, header_row):
    """Tek dosya için önizleme."""
    preview = {
        'degisik_rows': [],
        'rows_to_delete': [],
        'total_changes': 0
    }

    try:
        df = pd.read_excel(file_path, header=header_row)
        islem_kodu_col = df.columns[0]
        islem_adi_col = df.columns[1] if len(df.columns) > 1 else None

        degisik_mask = df[islem_kodu_col].astype(str).str.contains(r'\(Değişik', case=False, na=False)
        degisik_indices = df[degisik_mask].index.tolist()

        for idx in degisik_indices:
            current_value = str(df.at[idx, islem_kodu_col])
            cleaned_value = re.sub(r'\s*\([^)]*\)\s*', '', current_value).strip()
            islem_adi = str(df.at[idx, islem_adi_col]) if islem_adi_col else ""

            preview['degisik_rows'].append({
                'index': idx,
                'original': current_value,
                'cleaned': cleaned_value,
                'islem_adi': islem_adi[:50] + "..." if len(islem_adi) > 50 else islem_adi
            })

            if idx > 0:
                prev_idx = idx - 1
                prev_value = str(df.at[prev_idx, islem_kodu_col])
                prev_islem_adi = str(df.at[prev_idx, islem_adi_col]) if islem_adi_col else ""

                if prev_idx not in [r['index'] for r in preview['rows_to_delete']]:
                    preview['rows_to_delete'].append({
                        'index': prev_idx,
                        'islem_kodu': prev_value,
                        'islem_adi': prev_islem_adi[:50] + "..." if len(prev_islem_adi) > 50 else prev_islem_adi
                    })

        preview['total_changes'] = len(preview['degisik_rows']) + len(preview['rows_to_delete'])

    except Exception as e:
        preview['error'] = str(e)

    return preview


def preview_all_files():
    """
    Tüm dosyalar için önizleme.

    Returns:
        dict: Her dosya için önizleme bilgileri
    """
    sut_dir = get_sut_dir()
    previews = {}
    total_changes = 0

    for key, config in FILE_CONFIG.items():
        file_path = os.path.join(sut_dir, config['filename'])

        if os.path.exists(file_path):
            preview = preview_single_file(file_path, config['header_row'])
            preview['filename'] = config['filename']
            preview['display_name'] = key.upper().replace('EK2', 'EK-2')
            previews[key] = preview
            total_changes += preview.get('total_changes', 0)
        else:
            previews[key] = {
                'error': 'Dosya bulunamadı',
                'filename': config['filename'],
                'display_name': key.upper().replace('EK2', 'EK-2'),
                'total_changes': 0
            }

    previews['_summary'] = {
        'total_files': len(FILE_CONFIG),
        'total_changes': total_changes
    }

    return previews