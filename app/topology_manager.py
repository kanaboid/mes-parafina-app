# app/topology_manager.py
# type: ignore

import mysql.connector
from flask import current_app, jsonify
from datetime import datetime
from .db import get_db_connection
import json

class TopologyManager:
    """Menedżer do zarządzania cyfrową mapą rurociągu w systemie MES Parafina"""
    
    def __init__(self):
        pass
    
    # ================== ZAWORY ==================
    
    def get_zawory(self, include_segments=False):
        """Pobiera listę wszystkich zaworów"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT z.*
                FROM zawory z
                ORDER BY z.nazwa_zaworu
            """)
            zawory = cursor.fetchall()
            
            if include_segments:
                for zawor in zawory:
                    cursor.execute("""
                        SELECT s.id, s.nazwa_segmentu 
                        FROM segmenty s 
                        WHERE s.id_zaworu = %s
                    """, (zawor['id'],))
                    zawor['segments'] = cursor.fetchall()
                    zawor['segments_count'] = len(zawor['segments'])
            else:
                for zawor in zawory:
                    zawor['segments_count'] = 0
            
            return zawory
        finally:
            cursor.close()
            conn.close()
    
    def get_zawor(self, zawor_id):
        """Pobiera szczegóły konkretnego zaworu"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM zawory WHERE id = %s", (zawor_id,))
            zawor = cursor.fetchone()
            
            if zawor:
                # Pobierz segmenty używające tego zaworu
                cursor.execute("""
                    SELECT s.id, s.nazwa_segmentu,
                           ps_start.nazwa_portu as port_startowy,
                           ps_end.nazwa_portu as port_koncowy,
                           ws_start.nazwa_wezla as wezel_startowy,
                           ws_end.nazwa_wezla as wezel_koncowy
                    FROM segmenty s
                    LEFT JOIN porty_sprzetu ps_start ON s.id_portu_startowego = ps_start.id
                    LEFT JOIN porty_sprzetu ps_end ON s.id_portu_koncowego = ps_end.id
                    LEFT JOIN wezly_rurociagu ws_start ON s.id_wezla_startowego = ws_start.id
                    LEFT JOIN wezly_rurociagu ws_end ON s.id_wezla_koncowego = ws_end.id
                    WHERE s.id_zaworu = %s
                """, (zawor_id,))
                zawor['segments'] = cursor.fetchall()
            
            return zawor
        finally:
            cursor.close()
            conn.close()
    
    def create_zawor(self, nazwa_zaworu, stan='ZAMKNIETY'):
        """Tworzy nowy zawór"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO zawory (nazwa_zaworu, stan)
                VALUES (%s, %s)
            """, (nazwa_zaworu, stan))
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()
    
    def update_zawor(self, zawor_id, nazwa_zaworu=None, stan=None):
        """Aktualizuje zawór"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            updates = []
            params = []
            
            if nazwa_zaworu is not None:
                updates.append("nazwa_zaworu = %s")
                params.append(nazwa_zaworu)
            
            if stan is not None:
                updates.append("stan = %s")
                params.append(stan)
            
            if updates:
                params.append(zawor_id)
                cursor.execute(f"""
                    UPDATE zawory 
                    SET {', '.join(updates)}
                    WHERE id = %s
                """, params)
                conn.commit()
                return cursor.rowcount > 0
            return False
        finally:
            cursor.close()
            conn.close()
    
    def delete_zawor(self, zawor_id):
        """Usuwa zawór (tylko jeśli nie jest używany w segmentach)"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Sprawdź czy zawór jest używany
            cursor.execute("SELECT COUNT(*) as count FROM segmenty WHERE id_zaworu = %s", (zawor_id,))
            if cursor.fetchone()['count'] > 0:
                return False, "Zawór jest używany w segmentach i nie może być usunięty"
            
            cursor.execute("DELETE FROM zawory WHERE id = %s", (zawor_id,))
            conn.commit()
            return True, "Zawór został usunięty"
        finally:
            cursor.close()
            conn.close()
    
    # ================== WĘZŁY ==================
    
    def get_wezly(self, include_segments=False):
        """Pobiera listę wszystkich węzłów"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM wezly_rurociagu ORDER BY nazwa_wezla")
            wezly = cursor.fetchall()
            
            if include_segments:
                for wezel in wezly:
                    cursor.execute("""
                        SELECT s.id, s.nazwa_segmentu,
                               CASE 
                                   WHEN s.id_wezla_startowego = %s THEN 'START'
                                   WHEN s.id_wezla_koncowego = %s THEN 'END'
                               END as pozycja
                        FROM segmenty s 
                        WHERE s.id_wezla_startowego = %s OR s.id_wezla_koncowego = %s
                    """, (wezel['id'], wezel['id'], wezel['id'], wezel['id']))
                    wezel['segments'] = cursor.fetchall()
            
            return wezly
        finally:
            cursor.close()
            conn.close()
    
    def get_wezel(self, wezel_id):
        """Pobiera szczegóły konkretnego węzła"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM wezly_rurociagu WHERE id = %s", (wezel_id,))
            wezel = cursor.fetchone()
            
            if wezel:
                # Pobierz segmenty połączone z tym węzłem
                cursor.execute("""
                    SELECT s.id, s.nazwa_segmentu, z.nazwa_zaworu, z.stan as stan_zaworu,
                           CASE 
                               WHEN s.id_wezla_startowego = %s THEN 'START'
                               WHEN s.id_wezla_koncowego = %s THEN 'END'
                           END as pozycja,
                           CASE 
                               WHEN s.id_wezla_startowego = %s THEN 
                                   COALESCE(ps_end.nazwa_portu, ws_end.nazwa_wezla)
                               WHEN s.id_wezla_koncowego = %s THEN 
                                   COALESCE(ps_start.nazwa_portu, ws_start.nazwa_wezla)
                           END as drugi_koniec
                    FROM segmenty s
                    JOIN zawory z ON s.id_zaworu = z.id
                    LEFT JOIN porty_sprzetu ps_start ON s.id_portu_startowego = ps_start.id
                    LEFT JOIN porty_sprzetu ps_end ON s.id_portu_koncowego = ps_end.id
                    LEFT JOIN wezly_rurociagu ws_start ON s.id_wezla_startowego = ws_start.id
                    LEFT JOIN wezly_rurociagu ws_end ON s.id_wezla_koncowego = ws_end.id
                    WHERE s.id_wezla_startowego = %s OR s.id_wezla_koncowego = %s
                """, (wezel_id, wezel_id, wezel_id, wezel_id, wezel_id, wezel_id))
                wezel['segments'] = cursor.fetchall()
            
            return wezel
        finally:
            cursor.close()
            conn.close()
    
    def create_wezel(self, nazwa_wezla):
        """Tworzy nowy węzeł"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO wezly_rurociagu (nazwa_wezla)
                VALUES (%s)
            """, (nazwa_wezla,))
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()
    
    def update_wezel(self, wezel_id, nazwa_wezla):
        """Aktualizuje węzeł"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE wezly_rurociagu 
                SET nazwa_wezla = %s
                WHERE id = %s
            """, (nazwa_wezla, wezel_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
            conn.close()
    
    def delete_wezel(self, wezel_id):
        """Usuwa węzeł (tylko jeśli nie jest używany w segmentach)"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Sprawdź czy węzeł jest używany
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM segmenty 
                WHERE id_wezla_startowego = %s OR id_wezla_koncowego = %s
            """, (wezel_id, wezel_id))
            if cursor.fetchone()['count'] > 0:
                return False, "Węzeł jest używany w segmentach i nie może być usunięty"
            
            cursor.execute("DELETE FROM wezly_rurociagu WHERE id = %s", (wezel_id,))
            conn.commit()
            return True, "Węzeł został usunięty"
        finally:
            cursor.close()
            conn.close()
    
    # ================== SEGMENTY ==================
    
    def get_segmenty(self, include_details=False):
        """Pobiera listę wszystkich segmentów"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT s.*, z.nazwa_zaworu, z.stan as stan_zaworu,
                       ps_start.nazwa_portu as port_startowy,
                       ps_end.nazwa_portu as port_koncowy,
                       ws_start.nazwa_wezla as wezel_startowy,
                       ws_end.nazwa_wezla as wezel_koncowy,
                       sp_start.nazwa_unikalna as sprzet_startowy,
                       sp_end.nazwa_unikalna as sprzet_koncowy
                FROM segmenty s
                JOIN zawory z ON s.id_zaworu = z.id
                LEFT JOIN porty_sprzetu ps_start ON s.id_portu_startowego = ps_start.id
                LEFT JOIN porty_sprzetu ps_end ON s.id_portu_koncowego = ps_end.id
                LEFT JOIN wezly_rurociagu ws_start ON s.id_wezla_startowego = ws_start.id
                LEFT JOIN wezly_rurociagu ws_end ON s.id_wezla_koncowego = ws_end.id
                LEFT JOIN sprzet sp_start ON ps_start.id_sprzetu = sp_start.id
                LEFT JOIN sprzet sp_end ON ps_end.id_sprzetu = sp_end.id
                ORDER BY s.nazwa_segmentu
            """)
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()
    
    def get_segment(self, segment_id):
        """Pobiera szczegóły konkretnego segmentu"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT s.*, z.nazwa_zaworu, z.stan as stan_zaworu,
                       ps_start.nazwa_portu as port_startowy,
                       ps_end.nazwa_portu as port_koncowy,
                       ws_start.nazwa_wezla as wezel_startowy,
                       ws_end.nazwa_wezla as wezel_koncowy,
                       sp_start.nazwa_unikalna as sprzet_startowy,
                       sp_start.typ_sprzetu as typ_sprzetu_startowego,
                       sp_end.nazwa_unikalna as sprzet_koncowy,
                       sp_end.typ_sprzetu as typ_sprzetu_koncowego
                FROM segmenty s
                JOIN zawory z ON s.id_zaworu = z.id
                LEFT JOIN porty_sprzetu ps_start ON s.id_portu_startowego = ps_start.id
                LEFT JOIN porty_sprzetu ps_end ON s.id_portu_koncowego = ps_end.id
                LEFT JOIN wezly_rurociagu ws_start ON s.id_wezla_startowego = ws_start.id
                LEFT JOIN wezly_rurociagu ws_end ON s.id_wezla_koncowego = ws_end.id
                LEFT JOIN sprzet sp_start ON ps_start.id_sprzetu = sp_start.id
                LEFT JOIN sprzet sp_end ON ps_end.id_sprzetu = sp_end.id
                WHERE s.id = %s
            """, (segment_id,))
            return cursor.fetchone()
        finally:
            cursor.close()
            conn.close()
    
    def create_segment(self, nazwa_segmentu, id_zaworu, id_portu_startowego=None, 
                      id_wezla_startowego=None, id_portu_koncowego=None, id_wezla_koncowego=None):
        """Tworzy nowy segment"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Walidacja - każdy segment musi mieć punkt startowy i końcowy
            if not ((id_portu_startowego or id_wezla_startowego) and 
                    (id_portu_koncowego or id_wezla_koncowego)):
                return None, "Segment musi mieć zdefiniowany punkt startowy i końcowy"
            
            cursor.execute("""
                INSERT INTO segmenty 
                (nazwa_segmentu, id_portu_startowego, id_wezla_startowego, 
                 id_portu_koncowego, id_wezla_koncowego, id_zaworu)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (nazwa_segmentu, id_portu_startowego, id_wezla_startowego,
                  id_portu_koncowego, id_wezla_koncowego, id_zaworu))
            conn.commit()
            return cursor.lastrowid, "Segment został utworzony"
        finally:
            cursor.close()
            conn.close()
    
    def update_segment(self, segment_id, **kwargs):
        """Aktualizuje segment"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            allowed_fields = ['nazwa_segmentu', 'id_portu_startowego', 'id_wezla_startowego',
                             'id_portu_koncowego', 'id_wezla_koncowego', 'id_zaworu']
            
            updates = []
            params = []
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    updates.append(f"{field} = %s")
                    params.append(value)
            
            if updates:
                params.append(segment_id)
                cursor.execute(f"""
                    UPDATE segmenty 
                    SET {', '.join(updates)}
                    WHERE id = %s
                """, params)
                conn.commit()
                return cursor.rowcount > 0, "Segment został zaktualizowany"
            return False, "Brak danych do aktualizacji"
        finally:
            cursor.close()
            conn.close()
    
    def delete_segment(self, segment_id):
        """Usuwa segment"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM segmenty WHERE id = %s", (segment_id,))
            conn.commit()
            return cursor.rowcount > 0, "Segment został usunięty"
        finally:
            cursor.close()
            conn.close()
    
    # ================== PORTY I SPRZĘT ==================
    
    def get_porty_sprzetu(self):
        """Pobiera listę wszystkich portów sprzętu"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT p.*, s.nazwa_unikalna, s.typ_sprzetu
                FROM porty_sprzetu p
                JOIN sprzet s ON p.id_sprzetu = s.id
                ORDER BY s.nazwa_unikalna, p.nazwa_portu
            """)
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()
    
    def get_sprzet(self):
        """Pobiera listę całego sprzętu"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT s.*, 
                       COUNT(p.id) as porty_count
                FROM sprzet s
                LEFT JOIN porty_sprzetu p ON s.id = p.id_sprzetu
                GROUP BY s.id
                ORDER BY s.nazwa_unikalna
            """)
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()
    
    # ================== WIZUALIZACJA TOPOLOGII ==================
    
    def get_topology_graph(self):
        """Zwraca dane topologii w formacie grafu dla wizualizacji"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Pobierz wszystkie węzły (sprzęt + węzły rurociągu)
            nodes = []
            edges = []
            
            # Dodaj sprzęt jako węzły
            cursor.execute("""
                SELECT id, nazwa_unikalna as name, typ_sprzetu as type, 
                       'equipment' as category, stan_sprzetu as status
                FROM sprzet
            """)
            equipment = cursor.fetchall()
            for eq in equipment:
                nodes.append({
                    'id': f"eq_{eq['id']}",
                    'name': eq['name'],
                    'type': eq['type'],
                    'category': 'equipment',
                    'status': eq['status']
                })
            
            # Dodaj węzły rurociągu
            cursor.execute("SELECT id, nazwa_wezla as name FROM wezly_rurociagu")
            wezly = cursor.fetchall()
            for wezel in wezly:
                nodes.append({
                    'id': f"node_{wezel['id']}",
                    'name': wezel['name'],
                    'type': 'junction',
                    'category': 'junction'
                })
            
            # Dodaj krawędzie (segmenty)
            cursor.execute("""
                SELECT s.id, s.nazwa_segmentu, z.stan as stan_zaworu,
                       s.id_portu_startowego, s.id_wezla_startowego,
                       s.id_portu_koncowego, s.id_wezla_koncowego,
                       ps_start.id_sprzetu as sprzet_start_id,
                       ps_end.id_sprzetu as sprzet_end_id
                FROM segmenty s
                JOIN zawory z ON s.id_zaworu = z.id
                LEFT JOIN porty_sprzetu ps_start ON s.id_portu_startowego = ps_start.id
                LEFT JOIN porty_sprzetu ps_end ON s.id_portu_koncowego = ps_end.id
            """)
            segments = cursor.fetchall()
            
            for segment in segments:
                # Określ węzeł startowy
                if segment['id_portu_startowego']:
                    source = f"eq_{segment['sprzet_start_id']}"
                else:
                    source = f"node_{segment['id_wezla_startowego']}"
                
                # Określ węzeł końcowy
                if segment['id_portu_koncowego']:
                    target = f"eq_{segment['sprzet_end_id']}"
                else:
                    target = f"node_{segment['id_wezla_koncowego']}"
                
                edges.append({
                    'id': f"seg_{segment['id']}",
                    'source': source,
                    'target': target,
                    'name': segment['nazwa_segmentu'],
                    'valve_state': segment['stan_zaworu'],
                    'active': segment['stan_zaworu'] == 'OTWARTY'
                })
            
            return {
                'nodes': nodes,
                'edges': edges,
                'timestamp': datetime.now().isoformat()
            }
        finally:
            cursor.close()
            conn.close()
    
    def get_topology_text(self):
        """Zwraca tekstowy opis topologii"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT s.nazwa_segmentu, z.nazwa_zaworu, z.stan as stan_zaworu,
                       COALESCE(ps_start.nazwa_portu, ws_start.nazwa_wezla) as punkt_startowy,
                       COALESCE(ps_end.nazwa_portu, ws_end.nazwa_wezla) as punkt_koncowy,
                       COALESCE(sp_start.nazwa_unikalna, '') as sprzet_startowy,
                       COALESCE(sp_end.nazwa_unikalna, '') as sprzet_koncowy
                FROM segmenty s
                JOIN zawory z ON s.id_zaworu = z.id
                LEFT JOIN porty_sprzetu ps_start ON s.id_portu_startowego = ps_start.id
                LEFT JOIN porty_sprzetu ps_end ON s.id_portu_koncowego = ps_end.id
                LEFT JOIN wezly_rurociagu ws_start ON s.id_wezla_startowego = ws_start.id
                LEFT JOIN wezly_rurociagu ws_end ON s.id_wezla_koncowego = ws_end.id
                LEFT JOIN sprzet sp_start ON ps_start.id_sprzetu = sp_start.id
                LEFT JOIN sprzet sp_end ON ps_end.id_sprzetu = sp_end.id
                ORDER BY s.nazwa_segmentu
            """)
            segments = cursor.fetchall()
            
            text_lines = ["=== MAPA TOPOLOGII RUROCIĄGU ===", ""]
            
            for seg in segments:
                start_desc = f"{seg['sprzet_startowy']}:{seg['punkt_startowy']}" if seg['sprzet_startowy'] else seg['punkt_startowy']
                end_desc = f"{seg['sprzet_koncowy']}:{seg['punkt_koncowy']}" if seg['sprzet_koncowy'] else seg['punkt_koncowy']
                valve_status = "🟢 OTWARTY" if seg['stan_zaworu'] == 'OTWARTY' else "🔴 ZAMKNIĘTY"
                
                text_lines.append(f"{seg['nazwa_segmentu']}: {start_desc} ←→ {end_desc}")
                text_lines.append(f"  Zawór: {seg['nazwa_zaworu']} ({valve_status})")
                text_lines.append("")
            
            return "\n".join(text_lines)
        finally:
            cursor.close()
            conn.close()
