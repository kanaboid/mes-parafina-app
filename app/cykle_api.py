# app/cykle_api.py
"""
Dodatkowe API endpoints dla zarządzania cyklami filtracyjnymi
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from .db import get_db_connection
import mysql.connector

cykle_bp = Blueprint('cykle', __name__, url_prefix='/api')

@cykle_bp.route('/cykle-filtracyjne/<int:id_partii>')
def get_cykle_partii(id_partii):
    """Pobiera historię wszystkich cykli filtracyjnych dla danej partii."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT cf.*, 
                   ps.unikalny_kod, ps.typ_surowca, ps.nazwa_partii,
                   TIMESTAMPDIFF(MINUTE, cf.czas_rozpoczecia, cf.czas_zakonczenia) as rzeczywisty_czas_minut
            FROM cykle_filtracyjne cf
            JOIN partie_surowca ps ON cf.id_partii = ps.id
            WHERE cf.id_partii = %s
            ORDER BY cf.numer_cyklu, cf.czas_rozpoczecia
        """, (id_partii,))
        
        cykle = cursor.fetchall()
        return jsonify(cykle)
        
    finally:
        cursor.close()
        conn.close()

@cykle_bp.route('/partie/aktualny-stan')
def get_partie_aktualny_stan():
    """Pobiera aktualny stan wszystkich partii w systemie z szczegółami procesu."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT ps.*,
                   s.nazwa_unikalna as nazwa_reaktora,
                   s.typ_sprzetu,
                   CASE 
                       WHEN ps.planowany_czas_zakonczenia IS NOT NULL 
                       THEN TIMESTAMPDIFF(MINUTE, NOW(), ps.planowany_czas_zakonczenia)
                       ELSE NULL
                   END as pozostale_minuty,
                   CASE 
                       WHEN ps.planowany_czas_zakonczenia IS NOT NULL AND NOW() > ps.planowany_czas_zakonczenia
                       THEN TRUE
                       ELSE FALSE
                   END as przekroczony_czas
            FROM partie_surowca ps
            LEFT JOIN sprzet s ON ps.id_aktualnego_sprzetu = s.id
            WHERE ps.status_partii NOT IN ('W magazynie czystym', 'Gotowy do wysłania')
            ORDER BY ps.czas_rozpoczecia_etapu DESC
        """)
        
        partie = cursor.fetchall()
        return jsonify(partie)
        
    finally:
        cursor.close()
        conn.close()

@cykle_bp.route('/filtry/szczegolowy-status')
def get_filtry_szczegolowy_status():
    """Pobiera szczegółowy status filtrów z informacjami o partiach i cyklach."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Podstawowe informacje o filtrach
        cursor.execute("""
            SELECT id, nazwa_unikalna as nazwa_filtra, stan_sprzetu, typ_sprzetu
            FROM sprzet 
            WHERE typ_sprzetu = 'filtr'
            ORDER BY nazwa_unikalna
        """)
        filtry = cursor.fetchall()
        
        filtry_lista = []
        for filtr in filtry:
            filtr_dict = dict(filtr)
            
            # Sprawdź czy filtr ma aktywną operację
            cursor.execute("""
                SELECT ol.*, 
                       ps.unikalny_kod, ps.nazwa_partii, ps.typ_surowca,
                       ps.aktualny_etap_procesu, ps.numer_cyklu_aktualnego,
                       ps.czas_rozpoczecia_etapu, ps.planowany_czas_zakonczenia,
                       s_start.nazwa_unikalna as reaktor_startowy,
                       s_cel.nazwa_unikalna as reaktor_docelowy,
                       CASE 
                           WHEN ps.planowany_czas_zakonczenia IS NOT NULL 
                           THEN TIMESTAMPDIFF(MINUTE, NOW(), ps.planowany_czas_zakonczenia)
                           ELSE NULL
                       END as pozostale_minuty
                FROM operacje_log ol
                JOIN partie_surowca ps ON ol.id_partii_surowca = ps.id
                LEFT JOIN sprzet s_start ON ol.id_sprzetu_zrodlowego = s_start.id
                LEFT JOIN sprzet s_cel ON ol.id_sprzetu_docelowego = s_cel.id
                WHERE ol.status_operacji = 'aktywna' 
                AND ps.id_aktualnego_filtra = %s
                ORDER BY ol.czas_rozpoczecia DESC
                LIMIT 1
            """, (filtr_dict['nazwa_filtra'],))
            
            aktywna_operacja = cursor.fetchone()
            filtr_dict['aktywna_operacja'] = aktywna_operacja
            
            # Jeśli nie ma aktywnej operacji, sprawdź czy ktoś czeka na ten filtr
            if not aktywna_operacja:
                cursor.execute("""
                    SELECT ps.*, s.nazwa_unikalna as nazwa_reaktora
                    FROM partie_surowca ps
                    JOIN sprzet s ON ps.id_aktualnego_sprzetu = s.id
                    WHERE ps.id_aktualnego_filtra = %s 
                    AND ps.aktualny_etap_procesu IN ('surowy', 'gotowy')
                    ORDER BY ps.czas_rozpoczecia_etapu ASC
                    LIMIT 3
                """, (filtr_dict['nazwa_filtra'],))
                
                filtr_dict['kolejka_oczekujacych'] = cursor.fetchall()
            else:
                filtr_dict['kolejka_oczekujacych'] = []
            
            filtry_lista.append(filtr_dict)
        
        return jsonify(filtry_lista)
        
    finally:
        cursor.close()
        conn.close()

@cykle_bp.route('/cykle/rozpocznij', methods=['POST'])
def rozpocznij_cykl_filtracyjny():
    """Rozpoczyna nowy cykl filtracyjny dla partii."""
    data = request.get_json()
    
    required_fields = ['id_partii', 'typ_cyklu', 'id_filtra', 'reaktor_startowy']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Brak wymaganych pól'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Pobierz aktualny numer cyklu partii
        cursor.execute("SELECT numer_cyklu_aktualnego FROM partie_surowca WHERE id = %s", (data['id_partii'],))
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Nie znaleziono partii'}), 404
        
        numer_cyklu = result['numer_cyklu_aktualnego'] + 1
        
        # Oblicz planowany czas zakończenia
        durations = {
            'placek': 30,
            'filtracja': 15,
            'dmuchanie': 45
        }
        
        planowany_czas = datetime.now() + timedelta(minutes=durations.get(data['typ_cyklu'], 30))
        
        # Wstaw nowy cykl
        cursor.execute("""
            INSERT INTO cykle_filtracyjne 
            (id_partii, numer_cyklu, typ_cyklu, id_filtra, reaktor_startowy, 
             reaktor_docelowy, czas_rozpoczecia, wynik_oceny)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), 'oczekuje')
        """, (data['id_partii'], numer_cyklu, data['typ_cyklu'], data['id_filtra'], 
              data['reaktor_startowy'], data.get('reaktor_docelowy')))
        
        cykl_id = cursor.lastrowid
        
        # Aktualizuj partię
        etap_mapping = {
            'placek': 'placek',
            'filtracja': 'w_kole', 
            'dmuchanie': 'dmuchanie'
        }
        
        cursor.execute("""
            UPDATE partie_surowca 
            SET numer_cyklu_aktualnego = %s,
                aktualny_etap_procesu = %s,
                czas_rozpoczecia_etapu = NOW(),
                planowany_czas_zakonczenia = %s,
                id_aktualnego_filtra = %s,
                reaktor_docelowy = %s
            WHERE id = %s
        """, (numer_cyklu, etap_mapping[data['typ_cyklu']], planowany_czas,
              data['id_filtra'], data.get('reaktor_docelowy'), data['id_partii']))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Rozpoczęto cykl {data["typ_cyklu"]} dla partii',
            'cykl_id': cykl_id,
            'numer_cyklu': numer_cyklu
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Błąd rozpoczynania cyklu: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@cykle_bp.route('/cykle/zakoncz', methods=['POST'])
def zakoncz_cykl_filtracyjny():
    """Kończy aktualny cykl filtracyjny i przechodzi do następnego etapu."""
    data = request.get_json()
    
    if 'id_partii' not in data:
        return jsonify({'error': 'Brak ID partii'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Pobierz aktualny stan partii
        cursor.execute("""
            SELECT * FROM partie_surowca WHERE id = %s
        """, (data['id_partii'],))
        
        partia = cursor.fetchone()
        if not partia:
            return jsonify({'error': 'Nie znaleziono partii'}), 404
        
        # Zakończ aktualny cykl
        cursor.execute("""
            UPDATE cykle_filtracyjne 
            SET czas_zakonczenia = NOW(),
                czas_trwania_minut = TIMESTAMPDIFF(MINUTE, czas_rozpoczecia, NOW()),
                wynik_oceny = %s,
                komentarz = %s
            WHERE id_partii = %s 
            AND numer_cyklu = %s 
            AND czas_zakonczenia IS NULL
        """, (data.get('wynik_oceny', 'oczekuje'), data.get('komentarz', ''),
              data['id_partii'], partia['numer_cyklu_aktualnego']))
        
        # Określ następny etap na podstawie aktualnego
        next_etap = 'gotowy'
        next_filtr = None
        
        if partia['aktualny_etap_procesu'] == 'placek':
            next_etap = 'przelew'
        elif partia['aktualny_etap_procesu'] == 'przelew':
            next_etap = 'w_kole'
        elif partia['aktualny_etap_procesu'] == 'w_kole':
            next_etap = 'ocena_probki'
        elif partia['aktualny_etap_procesu'] == 'dmuchanie':
            next_etap = 'gotowy'
            next_filtr = None
        
        # Aktualizuj partię
        cursor.execute("""
            UPDATE partie_surowca 
            SET aktualny_etap_procesu = %s,
                czas_rozpoczecia_etapu = NOW(),
                planowany_czas_zakonczenia = NULL,
                id_aktualnego_filtra = %s
            WHERE id = %s
        """, (next_etap, next_filtr, data['id_partii']))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Zakończono cykl. Partia przeszła do etapu: {next_etap}',
            'next_etap': next_etap
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Błąd kończenia cyklu: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()
