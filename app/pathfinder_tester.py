# app/pathfinder_tester.py
# type: ignore

import mysql.connector
from flask import current_app, jsonify
from datetime import datetime, timezone
from .db import get_db_connection
from .pathfinder_service import PathFinder
import json

class PathFinderTester:
    """Tester połączeń PathFinder do analizy dostępności tras i optymalizacji ścieżek"""
    
    def __init__(self):
        self.pathfinder = None
    
    def get_pathfinder(self):
        """Pobiera instancję PathFinder"""
        if not self.pathfinder:
            try:
                self.pathfinder = current_app.extensions.get('pathfinder')
            except:
                # Fallback - tworzenie nowej instancji
                self.pathfinder = PathFinder()
        return self.pathfinder
    
    def test_connection_availability(self, start_point, end_point, valve_states=None):
        """Testuje dostępność połączenia między dwoma punktami"""
        try:
            pathfinder = self.get_pathfinder()
            
            # Jeśli podano stany zaworów, zastosuj je tymczasowo
            original_states = {}
            if valve_states:
                original_states = self._apply_valve_states(valve_states)
            
            # Znajdź ścieżkę
            path = pathfinder.find_path(start_point, end_point)
            
            # Przywróć oryginalne stany zaworów
            if valve_states:
                self._restore_valve_states(original_states)
            
            if path:
                return {
                    'available': True,
                    'path': path,
                    'path_length': len(path),
                    'segments_used': self._get_segments_for_path(path),
                    'message': f"Znaleziono ścieżkę z {start_point} do {end_point}"
                }
            else:
                return {
                    'available': False,
                    'path': None,
                    'path_length': 0,
                    'segments_used': [],
                    'message': f"Brak dostępnej ścieżki z {start_point} do {end_point}"
                }
        except Exception as e:
            return {
                'available': False,
                'path': None,
                'error': str(e),
                'message': f"Błąd podczas testowania połączenia: {str(e)}"
            }
    
    def find_all_paths(self, start_point, end_point, max_paths=5):
        """Znajduje wszystkie możliwe ścieżki między punktami"""
        try:
            pathfinder = self.get_pathfinder()
            
            # Znajdź główną ścieżkę
            main_path = pathfinder.find_path(start_point, end_point)
            if not main_path:
                return {
                    'paths': [],
                    'count': 0,
                    'message': f"Brak dostępnych ścieżek z {start_point} do {end_point}"
                }
            
            paths = [main_path]
            
            # Spróbuj znaleźć alternatywne ścieżki poprzez blokowanie segmentów głównej ścieżki
            for i in range(1, max_paths):
                # Tymczasowo zablokuj niektóre segmenty z poprzednich ścieżek
                blocked_segments = self._get_segments_to_block(paths)
                alt_path = self._find_alternative_path(start_point, end_point, blocked_segments)
                
                if alt_path and alt_path not in paths:
                    paths.append(alt_path)
                else:
                    break
            
            return {
                'paths': [
                    {
                        'path': path,
                        'length': len(path),
                        'segments': self._get_segments_for_path(path),
                        'estimated_cost': self._calculate_path_cost(path)
                    } for path in paths
                ],
                'count': len(paths),
                'message': f"Znaleziono {len(paths)} ścieżek z {start_point} do {end_point}"
            }
        except Exception as e:
            return {
                'paths': [],
                'count': 0,
                'error': str(e),
                'message': f"Błąd podczas wyszukiwania ścieżek: {str(e)}"
            }
    
    def simulate_valve_states(self, valve_changes):
        """Symuluje zmiany stanów zaworów i testuje wpływ na dostępność tras"""
        try:
            results = []
            
            # Zapisz oryginalne stany zaworów
            original_states = self._get_current_valve_states()
            
            for test_case in valve_changes:
                valve_name = test_case.get('valve_name')
                new_state = test_case.get('new_state')
                test_routes = test_case.get('test_routes', [])
                
                # Zastosuj zmianę stanu zaworu
                self._set_valve_state(valve_name, new_state)
                
                # Przetestuj wpływ na trasy
                route_results = []
                for route in test_routes:
                    start = route.get('start')
                    end = route.get('end')
                    
                    result = self.test_connection_availability(start, end)
                    route_results.append({
                        'route': f"{start} -> {end}",
                        'available': result['available'],
                        'path_length': result['path_length'],
                        'message': result['message']
                    })
                
                results.append({
                    'valve_change': f"{valve_name}: {new_state}",
                    'route_results': route_results,
                    'overall_impact': self._assess_valve_impact(route_results)
                })
            
            # Przywróć oryginalne stany zaworów
            self._restore_valve_states(original_states)
            
            return {
                'simulation_results': results,
                'message': f"Wykonano symulację dla {len(valve_changes)} zmian zaworów"
            }
        except Exception as e:
            # Upewnij się, że stany zaworów są przywrócone nawet w przypadku błędu
            try:
                self._restore_valve_states(original_states)
            except:
                pass
            
            return {
                'simulation_results': [],
                'error': str(e),
                'message': f"Błąd podczas symulacji: {str(e)}"
            }
    
    def analyze_critical_valves(self):
        """Analizuje krytyczne zawory - których zamknięcie blokuje najwięcej tras"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Pobierz wszystkie zawory i możliwe trasy
            cursor.execute("SELECT * FROM zawory ORDER BY nazwa_zaworu")
            zawory = cursor.fetchall()
            
            # Pobierz wszystkie możliwe punkty początkowe i końcowe
            cursor.execute("""
                SELECT DISTINCT nazwa_portu as punkt FROM porty_sprzetu
                UNION
                SELECT DISTINCT nazwa_wezla as punkt FROM wezly_rurociagu
                ORDER BY punkt
            """)
            punkty = [row['punkt'] for row in cursor.fetchall()]
            
            cursor.close()
            conn.close()
            
            # Analizuj każdy zawór
            critical_analysis = []
            
            for zawor in zawory:
                if zawor['stan'] == 'OTWARTY':
                    # Symuluj zamknięcie tego zaworu
                    blocked_routes = 0
                    affected_routes = []
                    
                    # Tymczasowo zamknij zawór
                    self._set_valve_state(zawor['nazwa_zaworu'], 'ZAMKNIETY')
                    
                    # Testuj losowe pary punktów
                    for i, start in enumerate(punkty[:10]):  # Ograniczamy do 10 punktów dla wydajności
                        for end in punkty[i+1:11]:  # Testuj z następnymi punktami
                            if start != end:
                                result = self.test_connection_availability(start, end)
                                if not result['available']:
                                    blocked_routes += 1
                                    affected_routes.append(f"{start} -> {end}")
                    
                    # Przywróć stan zaworu
                    self._set_valve_state(zawor['nazwa_zaworu'], 'OTWARTY')
                    
                    critical_analysis.append({
                        'valve_name': zawor['nazwa_zaworu'],
                        'blocked_routes_count': blocked_routes,
                        'affected_routes': affected_routes[:5],  # Pokaż tylko pierwsze 5
                        'criticality_score': blocked_routes,
                        'is_critical': blocked_routes > 0
                    })
            
            # Sortuj według krytyczności
            critical_analysis.sort(key=lambda x: x['criticality_score'], reverse=True)
            
            return {
                'critical_valves': critical_analysis,
                'most_critical': critical_analysis[0] if critical_analysis else None,
                'total_valves_analyzed': len(zawory),
                'message': f"Przeanalizowano {len(zawory)} zaworów pod kątem krytyczności"
            }
        except Exception as e:
            return {
                'critical_valves': [],
                'error': str(e),
                'message': f"Błąd podczas analizy krytycznych zaworów: {str(e)}"
            }
    
    def get_test_history(self, limit=50):
        """Pobiera historię testów PathFinder"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Sprawdź czy istnieje tabela z historią testów
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM information_schema.tables 
                WHERE table_schema = 'mes_parafina_db' 
                AND table_name = 'pathfinder_test_history'
            """)
            
            if cursor.fetchone()['count'] == 0:
                # Utwórz tabelę jeśli nie istnieje
                cursor.execute("""
                    CREATE TABLE pathfinder_test_history (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        test_type VARCHAR(50) NOT NULL,
                        start_point VARCHAR(100),
                        end_point VARCHAR(100),
                        test_parameters JSON,
                        result JSON,
                        success BOOLEAN,
                        execution_time_ms INT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
            
            # Pobierz historię testów
            cursor.execute("""
                SELECT * FROM pathfinder_test_history 
                ORDER BY created_at DESC 
                LIMIT %s
            """, (limit,))
            
            history = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return {
                'test_history': history,
                'count': len(history),
                'message': f"Pobrano {len(history)} zapisów z historii testów"
            }
        except Exception as e:
            return {
                'test_history': [],
                'error': str(e),
                'message': f"Błąd podczas pobierania historii testów: {str(e)}"
            }
    
    def save_test_result(self, test_type, start_point, end_point, test_parameters, result, success, execution_time_ms):
        """Zapisuje wynik testu do historii"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO pathfinder_test_history 
                (test_type, start_point, end_point, test_parameters, result, success, execution_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (test_type, start_point, end_point, json.dumps(test_parameters), 
                  json.dumps(result), success, execution_time_ms))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
        except Exception as e:
            return False
    
    # ================== METODY POMOCNICZE ==================
    
    def _apply_valve_states(self, valve_states):
        """Stosuje tymczasowe stany zaworów i zwraca oryginalne stany"""
        original_states = {}
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            for valve_name, new_state in valve_states.items():
                # Pobierz oryginalny stan
                cursor.execute("SELECT stan FROM zawory WHERE nazwa_zaworu = %s", (valve_name,))
                result = cursor.fetchone()
                if result:
                    original_states[valve_name] = result['stan']
                    
                    # Ustaw nowy stan
                    cursor.execute("""
                        UPDATE zawory SET stan = %s WHERE nazwa_zaworu = %s
                    """, (new_state, valve_name))
            
            conn.commit()
            return original_states
        finally:
            cursor.close()
            conn.close()
    
    def _restore_valve_states(self, original_states):
        """Przywraca oryginalne stany zaworów"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            for valve_name, original_state in original_states.items():
                cursor.execute("""
                    UPDATE zawory SET stan = %s WHERE nazwa_zaworu = %s
                """, (original_state, valve_name))
            
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def _get_current_valve_states(self):
        """Pobiera aktualne stany wszystkich zaworów"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("SELECT nazwa_zaworu, stan FROM zawory")
            results = cursor.fetchall()
            return {row['nazwa_zaworu']: row['stan'] for row in results}
        finally:
            cursor.close()
            conn.close()
    
    def _set_valve_state(self, valve_name, new_state):
        """Ustawia stan zaworu"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE zawory SET stan = %s WHERE nazwa_zaworu = %s
            """, (new_state, valve_name))
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def _get_segments_for_path(self, path):
        """Pobiera segmenty dla danej ścieżki"""
        if not path or len(path) < 2:
            return []
        
        segments = []
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            for i in range(len(path) - 1):
                start_point = path[i]
                end_point = path[i + 1]
                
                # Znajdź segment łączący te punkty
                cursor.execute("""
                    SELECT s.nazwa_segmentu, z.nazwa_zaworu, z.stan
                    FROM segmenty s
                    JOIN zawory z ON s.id_zaworu = z.id
                    LEFT JOIN porty_sprzetu ps_start ON s.id_portu_startowego = ps_start.id
                    LEFT JOIN porty_sprzetu ps_end ON s.id_portu_koncowego = ps_end.id
                    LEFT JOIN wezly_rurociagu ws_start ON s.id_wezla_startowego = ws_start.id
                    LEFT JOIN wezly_rurociagu ws_end ON s.id_wezla_koncowego = ws_end.id
                    WHERE (
                        (ps_start.nazwa_portu = %s AND ps_end.nazwa_portu = %s) OR
                        (ps_start.nazwa_portu = %s AND ps_end.nazwa_portu = %s) OR
                        (ps_start.nazwa_portu = %s AND ws_end.nazwa_wezla = %s) OR
                        (ws_start.nazwa_wezla = %s AND ps_end.nazwa_portu = %s) OR
                        (ws_start.nazwa_wezla = %s AND ws_end.nazwa_wezla = %s) OR
                        (ws_start.nazwa_wezla = %s AND ws_end.nazwa_wezla = %s)
                    )
                """, (start_point, end_point, end_point, start_point,
                      start_point, end_point, start_point, end_point,
                      start_point, end_point, end_point, start_point))
                
                segment = cursor.fetchone()
                if segment:
                    segments.append({
                        'segment_name': segment['nazwa_segmentu'],
                        'valve_name': segment['nazwa_zaworu'],
                        'valve_state': segment['stan']
                    })
            
            return segments
        finally:
            cursor.close()
            conn.close()
    
    def _get_segments_to_block(self, existing_paths):
        """Określa segmenty do zablokowania dla znajdowania alternatywnych ścieżek"""
        segments_to_block = []
        for path in existing_paths:
            path_segments = self._get_segments_for_path(path)
            for segment in path_segments:
                if segment['segment_name'] not in segments_to_block:
                    segments_to_block.append(segment['segment_name'])
        return segments_to_block[:2]  # Blokuj maksymalnie 2 segmenty
    
    def _find_alternative_path(self, start_point, end_point, blocked_segments):
        """Znajduje alternatywną ścieżkę z pominięciem zablokowanych segmentów"""
        # Tymczasowo zamknij zawory w blokowanych segmentach
        original_states = {}
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            for segment_name in blocked_segments:
                cursor.execute("""
                    SELECT z.nazwa_zaworu, z.stan 
                    FROM segmenty s
                    JOIN zawory z ON s.id_zaworu = z.id
                    WHERE s.nazwa_segmentu = %s
                """, (segment_name,))
                
                result = cursor.fetchone()
                if result:
                    original_states[result['nazwa_zaworu']] = result['stan']
                    cursor.execute("""
                        UPDATE zawory SET stan = 'ZAMKNIETY' WHERE nazwa_zaworu = %s
                    """, (result['nazwa_zaworu'],))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            # Znajdź alternatywną ścieżkę
            pathfinder = self.get_pathfinder()
            alternative_path = pathfinder.find_path(start_point, end_point)
            
            return alternative_path
        except Exception as e:
            return None
        finally:
            # Przywróć oryginalne stany zaworów
            self._restore_valve_states(original_states)
    
    def _calculate_path_cost(self, path):
        """Oblicza szacunkowy koszt ścieżki (im krótsze, tym lepsze)"""
        if not path:
            return float('inf')
        
        # Prosty koszt bazowany na długości ścieżki
        base_cost = len(path) - 1
        
        # Dodaj koszt za wykorzystanie krytycznych segmentów
        segments = self._get_segments_for_path(path)
        critical_penalty = sum(1 for seg in segments if seg['valve_state'] == 'ZAMKNIETY')
        
        return base_cost + critical_penalty * 10
    
    def _assess_valve_impact(self, route_results):
        """Ocenia ogólny wpływ zmiany stanu zaworu"""
        if not route_results:
            return 'brak_danych'
        
        total_routes = len(route_results)
        blocked_routes = sum(1 for result in route_results if not result['available'])
        
        if blocked_routes == 0:
            return 'brak_wpływu'
        elif blocked_routes < total_routes / 2:
            return 'umiarkowany_wpływ'
        else:
            return 'duży_wpływ'
