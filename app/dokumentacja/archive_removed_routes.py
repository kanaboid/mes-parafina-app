@bp.route('/rozpocznij_trase', methods=['POST'])
def rozpocznij_trase():
    dane = request.get_json()
    if not dane or not all(k in dane for k in ['start', 'cel', 'otwarte_zawory', 'typ_operacji']):
        return jsonify({"status": "error", "message": "Brak wymaganych pól: start, cel, otwarte_zawory, typ_operacji."}), 400

    start_point = dane['start']
    end_point = dane['cel']
    open_valves_list = dane['otwarte_zawory']
    typ_operacji = dane['typ_operacji']
    sprzet_posredni = dane.get('sprzet_posredni')
    
    pathfinder = get_pathfinder()
    znaleziona_sciezka_nazwy = []

    # --- Logika PathFinder (teraz kompletna) ---
    if sprzet_posredni:
        # Jeśli jest sprzęt pośredni (np. filtr), szukamy trasy w dwóch częściach.
        posredni_in = f"{sprzet_posredni}_IN"
        posredni_out = f"{sprzet_posredni}_OUT"

        sciezka_1 = pathfinder.find_path(start_point, posredni_in, open_valves_list)
        if not sciezka_1:
            return jsonify({"status": "error", "message": f"Nie znaleziono ścieżki z {start_point} do {posredni_in}."}), 404
        
        sciezka_wewnetrzna = pathfinder.find_path(posredni_in, posredni_out, open_valves_list)
        if not sciezka_wewnetrzna:
            return jsonify({"status": "error", "message": f"Nie znaleziono ścieżki wewnętrznej w {sprzet_posredni} (z {posredni_in} do {posredni_out})."}), 404

        sciezka_2 = pathfinder.find_path(posredni_out, end_point, open_valves_list)
        if not sciezka_2:
            return jsonify({"status": "error", "message": f"Nie znaleziono ścieżki z {posredni_out} do {end_point}."}), 404

        znaleziona_sciezka_nazwy = sciezka_1 + sciezka_wewnetrzna + sciezka_2
    else:
        # Jeśli nie ma punktu pośredniego, szukamy jednej, ciągłej ścieżki.
        znaleziona_sciezka_nazwy = pathfinder.find_path(start_point, end_point, open_valves_list)

    if not znaleziona_sciezka_nazwy:
        return jsonify({
            "status": "error",
            "message": f"Nie znaleziono kompletnej ścieżki z {start_point} do {end_point}."
        }), 404

    # --- Logika interakcji z bazą danych (WERSJA ORM) ---
    try:
        # Krok 1: Znajdź partię w reaktorze startowym
        partia_query = db.select(PartieSurowca).join(PartieSurowca.sprzet).join(Sprzet.porty_sprzetu).where(PortySprzetu.nazwa_portu == start_point)
        partia = db.session.execute(partia_query).scalar_one_or_none()

        if not partia:
            return jsonify({"status": "error", "message": f"W urządzeniu startowym ({start_point}) nie znaleziono żadnej partii."}), 404
        
        # Krok 2: Sprawdź konflikty
        konflikt_query = db.select(Segmenty.nazwa_segmentu).join(Segmenty.operacje_log).where(
            OperacjeLog.status_operacji == 'aktywna',
            Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy)
        )
        konflikty = db.session.execute(konflikt_query).scalars().all()

        if konflikty:
            return jsonify({
                "status": "error", "message": "Konflikt zasobów.",
                "zajete_segmenty": konflikty
            }), 409

        # Krok 3: Uruchomienie operacji w jednej transakcji
        db.session.execute(
            db.update(Zawory)
            .where(Zawory.nazwa_zaworu.in_(open_valves_list))
            .values(stan='OTWARTY')
        )

        opis_operacji = f"Operacja {typ_operacji} z {start_point} do {end_point}"
        nowa_operacja = OperacjeLog(
            typ_operacji=typ_operacji,
            id_partii_surowca=partia.id,
            status_operacji='aktywna',
            czas_rozpoczecia=dt.now(timezone.utc),
            opis=opis_operacji,
            punkt_startowy=start_point,
            punkt_docelowy=end_point
        )
        db.session.add(nowa_operacja)

        segmenty_trasy_query = db.select(Segmenty).where(Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy))
        segmenty_trasy = db.session.execute(segmenty_trasy_query).scalars().all()
        
        nowa_operacja.segmenty = segmenty_trasy

        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Operacja została pomyślnie rozpoczęta.",
            "id_operacji": nowa_operacja.id,
            "trasa": {
                "start": start_point,
                "cel": end_point,
                "uzyte_segmenty": znaleziona_sciezka_nazwy
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Błąd wewnętrzny serwera: {str(e)}"}), 500


@bp.route('/zakoncz', methods=['POST'])
def zakoncz_operacje():
    dane = request.get_json()
    if not dane or 'id_operacji' not in dane:
        return jsonify({"status": "error", "message": "Brak wymaganego pola: id_operacji."}), 400

    id_operacji = dane['id_operacji']
    try:
        # Krok 1: Znajdź operację w bazie za pomocą SQLAlchemy
        operacja = db.session.get(OperacjeLog, id_operacji)

        if not operacja:
            return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
        if operacja.status_operacji != 'aktywna':
            return jsonify({
                "status": "error", 
                "message": f"Nie można zakończyć operacji, która nie jest aktywna (status: {operacja.status_operacji})."
            }), 409

        # Krok 2: Zmień status operacji
        operacja.status_operacji = 'zakonczona'
        operacja.czas_zakonczenia = dt.now(timezone.utc) # Używamy aliasu `dt`

        # Krok 3: Znajdź i zamknij zawory (korzystając z relacji)
        zawory_do_zamkniecia_nazwy = []
        if operacja.segmenty:
            zawory_do_zamkniecia_nazwy = [segment.zawory.nazwa_zaworu for segment in operacja.segmenty if segment.zawory]
            for segment in operacja.segmenty:
                if segment.zawory:
                    segment.zawory.stan = 'ZAMKNIETY'
        
        # Krok 4: Aktualizacja lokalizacji partii i stanu sprzętu
        if operacja.partie_surowca and operacja.id_sprzetu_zrodlowego and operacja.id_sprzetu_docelowego and operacja.id_sprzetu_zrodlowego != operacja.id_sprzetu_docelowego:
            sprzet_docelowy = operacja.sprzet_docelowy
            sprzet_zrodlowy = operacja.sprzet_zrodlowy
            
            if sprzet_docelowy and sprzet_zrodlowy:
                operacja.partie_surowca.id_sprzetu = sprzet_docelowy.id
                sprzet_docelowy.stan_sprzetu = 'Zatankowany'
                sprzet_zrodlowy.stan_sprzetu = 'Pusty'

        # Krok 5: Zatwierdź transakcję
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": f"Operacja o ID {id_operacji} została pomyślnie zakończona.",
            "zamkniete_zawory": zawory_do_zamkniecia_nazwy
        }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Błąd wewnętrzny serwera: {str(e)}"}), 500


@bp.route('/dobielanie', methods=['POST'])
def dobielanie():
    dane = request.get_json()
    if not dane or not all(k in dane for k in ['id_reaktora', 'ilosc_workow', 'waga_worka_kg']):
        return jsonify({"status": "error", "message": "Brak wymaganych pól: id_reaktora, ilosc_workow, waga_worka_kg."}), 400

    id_reaktora = dane['id_reaktora']
    ilosc_workow = dane['ilosc_workow']
    waga_worka_kg = dane['waga_worka_kg']
    dodana_waga = ilosc_workow * waga_worka_kg

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Znajdź partię w podanym reaktorze
        cursor.execute("SELECT id FROM partie_surowca WHERE id_sprzetu = %s", (id_reaktora,))
        partia = cursor.fetchone()
        if not partia:
            return jsonify({"status": "error", "message": f"W reaktorze o ID {id_reaktora} nie znaleziono żadnej partii."}), 404
        
        id_partii = partia['id']

        # --- Transakcja ---
        write_cursor = conn.cursor()

        # 1. Dodaj wpis do operacje_log
        opis = f"Dodano {ilosc_workow} worków ziemi ({dodana_waga} kg) do partii {id_partii}"
        sql_log = "INSERT INTO operacje_log (typ_operacji, id_partii_surowca, czas_rozpoczecia, status_operacji, opis, ilosc_kg) VALUES ('DOBIELANIE', %s, NOW(), 'zakonczona', %s, %s)"
        write_cursor.execute(sql_log, (id_partii, opis, dodana_waga))

        # 2. Zaktualizuj wagę partii
        sql_waga = "UPDATE partie_surowca SET waga_aktualna_kg = waga_aktualna_kg + %s WHERE id = %s"
        write_cursor.execute(sql_waga, (dodana_waga, id_partii))

        # 3. Dodaj status "Dobielony" do partii
        # Załóżmy, że ID statusu "Dobielony" to 3
        # Używamy INSERT IGNORE, aby uniknąć błędu, jeśli partia już ma ten status
        sql_status = "INSERT IGNORE INTO partie_statusy (id_partii, id_statusu) VALUES (%s, 3)"
        write_cursor.execute(sql_status, (id_partii,))
        
        conn.commit()

        return jsonify({"status": "success", "message": opis}), 200

    except mysql.connector.Error as err:
        if conn: conn.rollback()
        return jsonify({"status": "error", "message": f"Błąd bazy danych: {err}"}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@sprzet_bp.route('/', methods=['GET'], endpoint='api_get_sprzet_sprzet')
def get_sprzet():
    """Zwraca listę całego sprzętu WRAZ z informacją o znajdującej się w nim partii."""
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Używamy LEFT JOIN, aby pokazać sprzęt nawet jeśli jest pusty
    query = """
        SELECT 
            s.id, s.nazwa_unikalna, s.typ_sprzetu, s.stan_sprzetu,
            /* Używamy ANY_VALUE() dla wszystkich kolumn z tabeli 'p', 
               które nie są w GROUP BY ani w funkcji agregującej */
            ANY_VALUE(p.id) as id_partii, 
            ANY_VALUE(p.unikalny_kod) as unikalny_kod, 
            ANY_VALUE(p.typ_surowca) as typ_surowca, 
            ANY_VALUE(p.waga_aktualna_kg) as waga_aktualna_kg,
            
            /* Ta kolumna już jest zagregowana, więc jej nie ruszamy */
            GROUP_CONCAT(st.nazwa_statusu SEPARATOR ', ') AS statusy_partii
        FROM sprzet s
        LEFT JOIN partie_surowca p ON s.id = p.id_sprzetu
        LEFT JOIN partie_statusy ps ON p.id = ps.id_partii
        LEFT JOIN statusy st ON ps.id_statusu = st.id
        GROUP BY s.id  /* Grupowanie pozostaje bez zmian */
        ORDER BY s.typ_sprzetu, s.nazwa_unikalna;
    """
    cursor.execute(query)
    sprzet_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify(sprzet_list)


@sprzet_bp.route('/beczki-brudne', methods=['GET'])
def get_beczki_brudne():
    """Zwraca listę beczek brudnych dostępnych do tankowania"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, nazwa_unikalna, stan_sprzetu
            FROM sprzet 
            WHERE typ_sprzetu = 'beczka_brudna'
            ORDER BY nazwa_unikalna
        """)
        beczki = cursor.fetchall()
        return jsonify(beczki)
    except Exception as e:
        return jsonify({'error': f'Błąd pobierania beczek: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@sprzet_bp.route('/reaktory-puste', methods=['GET'])
def get_reaktory_puste():
    """Zwraca listę reaktorów w stanie 'Pusty' dostępnych do tankowania"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, nazwa_unikalna, stan_sprzetu
            FROM sprzet 
            WHERE typ_sprzetu = 'reaktor' AND stan_sprzetu = 'Pusty'
            ORDER BY nazwa_unikalna
        """)
        reaktory = cursor.fetchall()
        return jsonify(reaktory)
    except Exception as e:
        return jsonify({'error': f'Błąd pobierania reaktorów: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@sprzet_bp.route('/reaktory-z-surowcem', methods=['GET'])
def get_reaktory_z_surowcem():
    """Zwraca listę reaktorów ze stanem innym niż 'Pusty' (zawierających surowiec)"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, nazwa_unikalna, stan_sprzetu
            FROM sprzet 
            WHERE typ_sprzetu = 'reaktor' AND stan_sprzetu != 'Pusty'
            ORDER BY nazwa_unikalna
        """)
        reaktory = cursor.fetchall()
        return jsonify(reaktory)
    except Exception as e:
        return jsonify({'error': f'Błąd pobierania reaktorów z surowcem: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@sprzet_bp.route('/dostepne-zrodla', methods=['GET'])
def get_dostepne_zrodla():
    """Zwraca listę dostępnych źródeł do transferu (Apollo + beczki brudne z zawartością)"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Apollo z aktywnymi sesjami
        apollo_query = """
            SELECT DISTINCT s.id, s.nazwa_unikalna, s.typ_sprzetu, 
                   'apollo' as kategoria_zrodla,
                   aps.typ_surowca,
                   'Aktywna sesja wytapiania' as opis_stanu
            FROM sprzet s
            JOIN apollo_sesje aps ON s.id = aps.id_sprzetu
            WHERE s.typ_sprzetu = 'apollo' AND aps.status_sesji = 'aktywna'
        """
        
        # Beczki brudne z partiami
        beczki_query = """
            SELECT DISTINCT s.id, s.nazwa_unikalna, s.typ_sprzetu,
                   'beczka_brudna' as kategoria_zrodla,
                   ps.typ_surowca,
                   CONCAT('Partia: ', ps.unikalny_kod, ' (', ps.waga_aktualna_kg, 'kg)') as opis_stanu
            FROM sprzet s
            JOIN partie_surowca ps ON s.id = ps.id_sprzetu
            WHERE s.typ_sprzetu = 'beczka_brudna' AND ps.status_partii NOT IN ('W magazynie czystym', 'Gotowy do wysłania')
        """
        
        # Reaktory z partiami
        reaktory_query = """
            SELECT DISTINCT s.id, s.nazwa_unikalna, s.typ_sprzetu,
                   'reaktor' as kategoria_zrodla,
                   ps.typ_surowca,
                   CONCAT('Partia: ', ps.unikalny_kod, ' (', ps.waga_aktualna_kg, 'kg)') as opis_stanu
            FROM sprzet s
            JOIN partie_surowca ps ON s.id = ps.id_sprzetu
            WHERE s.typ_sprzetu = 'reaktor' AND ps.status_partii NOT IN ('W magazynie czystym', 'Gotowy do wysłania')
        """
        
        cursor.execute(f"{apollo_query} UNION ALL {beczki_query} UNION ALL {reaktory_query} ORDER BY kategoria_zrodla, nazwa_unikalna")
        zrodla = cursor.fetchall()
        
        # Dla Apollo dodaj informacje o dostępnej ilości
        for zrodlo in zrodla:
            if zrodlo.get('kategoria_zrodla') == 'apollo':
                zrodlo_id = zrodlo.get('id')
                if zrodlo_id:
                    stan = ApolloService.oblicz_aktualny_stan_apollo(zrodlo_id)
                    zrodlo['dostepne_kg'] = stan.get('dostepne_kg')
                    zrodlo['opis_stanu'] = f"Dostępne: {stan.get('dostepne_kg')}kg {stan.get('typ_surowca')}"
        
        return jsonify(zrodla)
        
    except Exception as e:
        return jsonify({'error': f'Błąd pobierania źródeł: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()



@sprzet_bp.route('/stan-partii', methods=['GET'])
def get_stan_partii_w_sprzecie():
    """
    Zwraca stan całego sprzętu, który może przechowywać partie, 
    wraz z informacjami o aktualnie znajdującej się w nim partii.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Pobierz cały sprzęt, który nas interesuje, wraz z dołączonymi partiami
        query = """
            SELECT
                s.id, s.nazwa_unikalna, s.typ_sprzetu, s.stan_sprzetu,
                p.id AS partia_id, p.unikalny_kod, p.typ_surowca, p.waga_aktualna_kg
            FROM sprzet s
            LEFT JOIN partie_surowca p ON s.id = p.id_sprzetu
            WHERE s.typ_sprzetu IN ('reaktor', 'beczka_brudna', 'beczka_czysta')
            ORDER BY s.typ_sprzetu, s.nazwa_unikalna;
        """
        cursor.execute(query)
        wyniki = cursor.fetchall()
        
        # Przygotuj strukturę odpowiedzi
        odpowiedz = {
            'reaktory': [],
            'beczki_brudne': [],
            'beczki_czyste': []
        }

        for row in wyniki:
            sprzet_info = {
                'id': row['id'],
                'nazwa_unikalna': row['nazwa_unikalna'],
                'typ_sprzetu': row['typ_sprzetu'],
                'stan_sprzetu': row['stan_sprzetu'],
                'partia': None
            }
            if row['partia_id']:
                partia_info = {
                    'id': row['partia_id'],
                    'unikalny_kod': row['unikalny_kod'],
                    'typ_surowca': row['typ_surowca'],
                    'waga_aktualna_kg': float(row['waga_aktualna_kg']),
                    'sklad': None  # Domyślnie brak składu
                }

                # Jeśli partia jest mieszaniną, oblicz jej skład
                if partia_info['typ_surowca'].startswith('MIX('):
                    from .routes import get_base_components_recursive
                    sklad_dict = get_base_components_recursive(partia_info['id'], cursor)
                    total_waga_skladu = sum(sklad_dict.values())
                    
                    if total_waga_skladu > 0:
                        sklad_list = []
                        for typ, waga in sklad_dict.items():
                            procent = (waga / total_waga_skladu) * 100
                            sklad_list.append({
                                'typ_surowca': typ,
                                'waga_kg': round(waga, 2),
                                'procent': round(procent, 2)
                            })
                        partia_info['sklad'] = sorted(sklad_list, key=lambda x: x['typ_surowca'])

                sprzet_info['partia'] = partia_info
            
            if row['typ_sprzetu'] == 'reaktor':
                odpowiedz['reaktory'].append(sprzet_info)
            elif row['typ_sprzetu'] == 'beczka_brudna':
                odpowiedz['beczki_brudne'].append(sprzet_info)
            elif row['typ_sprzetu'] == 'beczka_czysta':
                odpowiedz['beczki_czyste'].append(sprzet_info)

        return jsonify(odpowiedz)

    except mysql.connector.Error as err:
        return jsonify({'error': f'Błąd bazy danych: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()