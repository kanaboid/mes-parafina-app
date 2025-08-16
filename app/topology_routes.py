# app/topology_routes.py
# type: ignore

from flask import Blueprint, jsonify, request, render_template
from datetime import datetime, timezone
from .topology_manager import TopologyManager
from .pathfinder_tester import PathFinderTester
from .db import get_db_connection
import time
import json

# Tworzenie blueprint dla topologii
topology_bp = Blueprint('topology', __name__, url_prefix='/topology')

# Inicjalizacja menedżerów
topology_manager = TopologyManager()
pathfinder_tester = PathFinderTester()

# ================== WIDOKI HTML ==================

@topology_bp.route('/')
def topology_index():
    """Główna strona zarządzania topologią"""
    return render_template('topology/index.html')

@topology_bp.route('/zawory')
def zawory_view():
    """Strona zarządzania zaworami"""
    zawory = topology_manager.get_zawory(include_segments=True)
    return render_template('topology/zawory.html', zawory=zawory)

@topology_bp.route('/wezly')
def wezly_view():
    """Strona zarządzania węzłami"""
    wezly = topology_manager.get_wezly(include_segments=True)
    return render_template('topology/wezly.html', wezly=wezly)

@topology_bp.route('/segmenty')
def segmenty_view():
    """Strona zarządzania segmentami"""
    segmenty = topology_manager.get_segmenty(include_details=True)
    return render_template('topology/segmenty.html', segmenty=segmenty)

@topology_bp.route('/visualization')
def visualization_view():
    """Strona wizualizacji topologii"""
    return render_template('topology/visualization.html')

@topology_bp.route('/pathfinder')
def pathfinder_view():
    """Strona testera PathFinder"""
    # Pobierz dostępne punkty do testowania
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT DISTINCT nazwa_portu as punkt, 'port' as typ FROM porty_sprzetu
            UNION
            SELECT DISTINCT nazwa_wezla as punkt, 'wezel' as typ FROM wezly_rurociagu
            ORDER BY punkt
        """)
        punkty = cursor.fetchall()
        
        # Pobierz zawory do selecta
        cursor.execute("SELECT id, nazwa_zaworu, stan FROM zawory ORDER BY nazwa_zaworu")
        zawory = cursor.fetchall()
        
        # Pobierz historię testów
        history = pathfinder_tester.get_test_history(limit=20)
        
        return render_template('topology/pathfinder.html', 
                             punkty=punkty, 
                             zawory=zawory,
                             test_history=history.get('test_history', []))
    finally:
        cursor.close()
        conn.close()

# ================== API ZAWORY ==================

@topology_bp.route('/api/zawory', methods=['GET'])
def api_get_zawory():
    """API: Pobiera listę zaworów"""
    include_segments = request.args.get('include_segments', 'false').lower() == 'true'
    zawory = topology_manager.get_zawory(include_segments=include_segments)
    return jsonify({
        'success': True,
        'data': zawory,
        'count': len(zawory)
    })

@topology_bp.route('/api/zawory/<int:zawor_id>', methods=['GET'])
def api_get_zawor(zawor_id):
    """API: Pobiera szczegóły zaworu"""
    zawor = topology_manager.get_zawor(zawor_id)
    if zawor:
        return jsonify({
            'success': True,
            'data': zawor
        })
    return jsonify({
        'success': False,
        'message': 'Zawór nie został znaleziony'
    }), 404

@topology_bp.route('/api/zawory', methods=['POST'])
def api_create_zawor():
    """API: Tworzy nowy zawór"""
    data = request.get_json()
    if not data or 'nazwa_zaworu' not in data:
        return jsonify({
            'success': False,
            'message': 'Wymagana jest nazwa zaworu'
        }), 400
    
    try:
        zawor_id = topology_manager.create_zawor(
            nazwa_zaworu=data['nazwa_zaworu'],
            stan=data.get('stan', 'ZAMKNIETY')
        )
        
        return jsonify({
            'success': True,
            'data': {'id': zawor_id},
            'message': 'Zawór został utworzony'
        }), 201
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas tworzenia zaworu: {str(e)}'
        }), 500

@topology_bp.route('/api/zawory/<int:zawor_id>', methods=['PUT'])
def api_update_zawor(zawor_id):
    """API: Aktualizuje zawór"""
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': 'Brak danych do aktualizacji'
        }), 400
    
    try:
        success = topology_manager.update_zawor(
            zawor_id=zawor_id,
            nazwa_zaworu=data.get('nazwa_zaworu'),
            stan=data.get('stan')
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Zawór został zaktualizowany'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Zawór nie został znaleziony lub brak zmian'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas aktualizacji zaworu: {str(e)}'
        }), 500

@topology_bp.route('/api/zawory/<int:zawor_id>', methods=['DELETE'])
def api_delete_zawor(zawor_id):
    """API: Usuwa zawór"""
    try:
        success, message = topology_manager.delete_zawor(zawor_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas usuwania zaworu: {str(e)}'
        }), 500

# ================== API WĘZŁY ==================

@topology_bp.route('/api/wezly', methods=['GET'])
def api_get_wezly():
    """API: Pobiera listę węzłów"""
    include_segments = request.args.get('include_segments', 'false').lower() == 'true'
    wezly = topology_manager.get_wezly(include_segments=include_segments)
    return jsonify({
        'success': True,
        'data': wezly,
        'count': len(wezly)
    })

@topology_bp.route('/api/wezly/<int:wezel_id>', methods=['GET'])
def api_get_wezel(wezel_id):
    """API: Pobiera szczegóły węzła"""
    wezel = topology_manager.get_wezel(wezel_id)
    if wezel:
        return jsonify({
            'success': True,
            'data': wezel
        })
    return jsonify({
        'success': False,
        'message': 'Węzeł nie został znaleziony'
    }), 404

@topology_bp.route('/api/wezly', methods=['POST'])
def api_create_wezel():
    """API: Tworzy nowy węzeł"""
    data = request.get_json()
    if not data or 'nazwa_wezla' not in data:
        return jsonify({
            'success': False,
            'message': 'Wymagana jest nazwa węzła'
        }), 400
    
    try:
        wezel_id = topology_manager.create_wezel(data['nazwa_wezla'])
        
        return jsonify({
            'success': True,
            'data': {'id': wezel_id},
            'message': 'Węzeł został utworzony'
        }), 201
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas tworzenia węzła: {str(e)}'
        }), 500

@topology_bp.route('/api/wezly/<int:wezel_id>', methods=['PUT'])
def api_update_wezel(wezel_id):
    """API: Aktualizuje węzeł"""
    data = request.get_json()
    if not data or 'nazwa_wezla' not in data:
        return jsonify({
            'success': False,
            'message': 'Wymagana jest nazwa węzła'
        }), 400
    
    try:
        success = topology_manager.update_wezel(wezel_id, data['nazwa_wezla'])
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Węzeł został zaktualizowany'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Węzeł nie został znaleziony'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas aktualizacji węzła: {str(e)}'
        }), 500

@topology_bp.route('/api/wezly/<int:wezel_id>', methods=['DELETE'])
def api_delete_wezel(wezel_id):
    """API: Usuwa węzeł"""
    try:
        success, message = topology_manager.delete_wezel(wezel_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas usuwania węzła: {str(e)}'
        }), 500

# ================== API SEGMENTY ==================

@topology_bp.route('/api/segmenty', methods=['GET'])
def api_get_segmenty():
    """API: Pobiera listę segmentów"""
    include_details = request.args.get('include_details', 'true').lower() == 'true'
    segmenty = topology_manager.get_segmenty(include_details=include_details)
    return jsonify({
        'success': True,
        'data': segmenty,
        'count': len(segmenty)
    })

@topology_bp.route('/api/segmenty/<int:segment_id>', methods=['GET'])
def api_get_segment(segment_id):
    """API: Pobiera szczegóły segmentu"""
    segment = topology_manager.get_segment(segment_id)
    if segment:
        return jsonify({
            'success': True,
            'data': segment
        })
    return jsonify({
        'success': False,
        'message': 'Segment nie został znaleziony'
    }), 404

@topology_bp.route('/api/segmenty', methods=['POST'])
def api_create_segment():
    """API: Tworzy nowy segment"""
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': 'Brak danych'
        }), 400
    
    required_fields = ['nazwa_segmentu', 'id_zaworu']
    if not all(field in data for field in required_fields):
        return jsonify({
            'success': False,
            'message': 'Wymagane pola: nazwa_segmentu, id_zaworu'
        }), 400
    
    try:
        segment_id, message = topology_manager.create_segment(
            nazwa_segmentu=data['nazwa_segmentu'],
            id_zaworu=data['id_zaworu'],
            id_portu_startowego=data.get('id_portu_startowego'),
            id_wezla_startowego=data.get('id_wezla_startowego'),
            id_portu_koncowego=data.get('id_portu_koncowego'),
            id_wezla_koncowego=data.get('id_wezla_koncowego')
        )
        
        if segment_id:
            return jsonify({
                'success': True,
                'data': {'id': segment_id},
                'message': message
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas tworzenia segmentu: {str(e)}'
        }), 500

@topology_bp.route('/api/segmenty/<int:segment_id>', methods=['PUT'])
def api_update_segment(segment_id):
    """API: Aktualizuje segment"""
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': 'Brak danych do aktualizacji'
        }), 400
    
    try:
        success, message = topology_manager.update_segment(segment_id, **data)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas aktualizacji segmentu: {str(e)}'
        }), 500

@topology_bp.route('/api/segmenty/<int:segment_id>', methods=['DELETE'])
def api_delete_segment(segment_id):
    """API: Usuwa segment"""
    try:
        success, message = topology_manager.delete_segment(segment_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas usuwania segmentu: {str(e)}'
        }), 500

# ================== API WIZUALIZACJA ==================

@topology_bp.route('/api/visualization/graph', methods=['GET'])
def api_topology_graph():
    """API: Pobiera dane topologii w formacie grafu"""
    try:
        graph_data = topology_manager.get_topology_graph()
        return jsonify({
            'success': True,
            'data': graph_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas generowania grafu: {str(e)}'
        }), 500

@topology_bp.route('/api/visualization/text', methods=['GET'])
def api_topology_text():
    """API: Pobiera tekstowy opis topologii"""
    try:
        text_description = topology_manager.get_topology_text()
        return jsonify({
            'success': True,
            'data': {
                'text': text_description,
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas generowania opisu: {str(e)}'
        }), 500

# ================== API PATHFINDER ==================

@topology_bp.route('/api/pathfinder/test-connection', methods=['POST'])
def api_test_connection():
    """API: Testuje połączenie między punktami"""
    data = request.get_json()
    print(f"DEBUG: PathFinder API called with data: {data}")
    
    if not data or 'start_point' not in data or 'end_point' not in data:
        return jsonify({
            'success': False,
            'message': 'Wymagane pola: start_point, end_point'
        }), 400
    
    start_time = time.time()
    
    try:
        result = pathfinder_tester.test_connection_availability(
            start_point=data['start_point'],
            end_point=data['end_point'],
            valve_states=data.get('valve_states')
        )
        
        print(f"DEBUG: PathFinder result: {result}")
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Zapisz wynik do historii
        pathfinder_tester.save_test_result(
            test_type='connection_test',
            start_point=data['start_point'],
            end_point=data['end_point'],
            test_parameters={'valve_states': data.get('valve_states')},
            result=result,
            success=result.get('available', False),
            execution_time_ms=execution_time
        )
        
        return jsonify({
            'success': True,
            'data': result,
            'execution_time_ms': execution_time
        })
    except Exception as e:
        print(f"DEBUG: PathFinder API error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Błąd podczas testowania połączenia: {str(e)}'
        }), 500

@topology_bp.route('/api/pathfinder/find-paths', methods=['POST'])
def api_find_paths():
    """API: Znajduje wszystkie ścieżki między punktami"""
    data = request.get_json()
    if not data or 'start_point' not in data or 'end_point' not in data:
        return jsonify({
            'success': False,
            'message': 'Wymagane pola: start_point, end_point'
        }), 400
    
    start_time = time.time()
    
    try:
        result = pathfinder_tester.find_all_paths(
            start_point=data['start_point'],
            end_point=data['end_point'],
            max_paths=data.get('max_paths', 5)
        )
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Zapisz wynik do historii
        pathfinder_tester.save_test_result(
            test_type='find_paths',
            start_point=data['start_point'],
            end_point=data['end_point'],
            test_parameters={'max_paths': data.get('max_paths', 5)},
            result=result,
            success=result.get('count', 0) > 0,
            execution_time_ms=execution_time
        )
        
        return jsonify({
            'success': True,
            'data': result,
            'execution_time_ms': execution_time
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas wyszukiwania ścieżek: {str(e)}'
        }), 500

@topology_bp.route('/api/pathfinder/simulate-valves', methods=['POST'])
def api_simulate_valves():
    """API: Symuluje zmiany stanów zaworów"""
    data = request.get_json()
    if not data or 'valve_changes' not in data:
        return jsonify({
            'success': False,
            'message': 'Wymagane pole: valve_changes'
        }), 400
    
    start_time = time.time()
    
    try:
        result = pathfinder_tester.simulate_valve_states(data['valve_changes'])
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Zapisz wynik do historii
        pathfinder_tester.save_test_result(
            test_type='valve_simulation',
            start_point=None,
            end_point=None,
            test_parameters={'valve_changes': data['valve_changes']},
            result=result,
            success=len(result.get('simulation_results', [])) > 0,
            execution_time_ms=execution_time
        )
        
        return jsonify({
            'success': True,
            'data': result,
            'execution_time_ms': execution_time
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas symulacji zaworów: {str(e)}'
        }), 500

@topology_bp.route('/api/pathfinder/critical-valves', methods=['GET'])
def api_critical_valves():
    """API: Analizuje krytyczne zawory"""
    start_time = time.time()
    
    try:
        result = pathfinder_tester.analyze_critical_valves()
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return jsonify({
            'success': True,
            'data': result,
            'execution_time_ms': execution_time
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas analizy krytycznych zaworów: {str(e)}'
        }), 500

@topology_bp.route('/api/pathfinder/history', methods=['GET'])
def api_pathfinder_history():
    """API: Pobiera historię testów PathFinder"""
    limit = request.args.get('limit', 50, type=int)
    
    try:
        result = pathfinder_tester.get_test_history(limit=limit)
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas pobierania historii: {str(e)}'
        }), 500

# ================== API POMOCNICZE ==================

@topology_bp.route('/api/porty', methods=['GET'])
def api_get_porty():
    """API: Pobiera listę portów sprzętu"""
    try:
        porty = topology_manager.get_porty_sprzetu()
        return jsonify({
            'success': True,
            'data': porty,
            'count': len(porty)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas pobierania portów: {str(e)}'
        }), 500

@topology_bp.route('/api/sprzet', methods=['GET'])
def api_get_sprzet():
    """API: Pobiera listę sprzętu"""
    try:
        sprzet = topology_manager.get_sprzet()
        return jsonify({
            'success': True,
            'data': sprzet,
            'count': len(sprzet)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas pobierania sprzętu: {str(e)}'
        }), 500

@topology_bp.route('/api/points', methods=['GET'])
def api_get_points():
    """API: Pobiera wszystkie dostępne punkty (porty + węzły)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT p.nazwa_portu as name, 'port' as type, s.nazwa_unikalna as equipment,
                   s.typ_sprzetu as equipment_type, p.typ_portu as port_type
            FROM porty_sprzetu p
            JOIN sprzet s ON p.id_sprzetu = s.id
            UNION
            SELECT w.nazwa_wezla as name, 'junction' as type, NULL as equipment,
                   NULL as equipment_type, NULL as port_type
            FROM wezly_rurociagu w
            ORDER BY name
        """)
        
        points = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': points,
            'count': len(points)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas pobierania punktów: {str(e)}'
        }), 500

@topology_bp.route('/api/sprzet/<int:sprzet_id>/porty', methods=['GET'])
def api_get_sprzet_ports(sprzet_id):
    """API: Pobiera porty dla konkretnego sprzętu"""
    try:
        porty = topology_manager.get_porty_dla_sprzetu(sprzet_id)
        return jsonify({
            'success': True,
            'data': porty,
            'count': len(porty)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas pobierania portów sprzętu: {str(e)}'
        }), 500

# ================== API DIAGNOSTYCZNE ==================

@topology_bp.route('/api/health-check', methods=['GET'])
def api_health_check():
    """API: Sprawdza stan zdrowia topologii i wykrywa problemy"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        health_issues = []
        warnings = []
        
        # Sprawdź zawory bez segmentów
        cursor.execute("""
            SELECT z.nazwa_zaworu 
            FROM zawory z 
            LEFT JOIN segmenty s ON z.id = s.id_zaworu 
            WHERE s.id IS NULL
        """)
        orphaned_valves = cursor.fetchall()
        if orphaned_valves:
            warnings.append({
                'type': 'orphaned_valves',
                'message': f'Znaleziono {len(orphaned_valves)} zaworów bez segmentów',
                'items': [v['nazwa_zaworu'] for v in orphaned_valves]
            })
        
        # Sprawdź segmenty bez zaworów
        cursor.execute("""
            SELECT s.nazwa_segmentu 
            FROM segmenty s 
            LEFT JOIN zawory z ON s.id_zaworu = z.id 
            WHERE z.id IS NULL
        """)
        segments_without_valves = cursor.fetchall()
        if segments_without_valves:
            health_issues.append({
                'type': 'segments_without_valves',
                'message': f'Znaleziono {len(segments_without_valves)} segmentów bez zaworów',
                'items': [s['nazwa_segmentu'] for s in segments_without_valves]
            })
        
        # Sprawdź węzły bez połączeń
        cursor.execute("""
            SELECT w.nazwa_wezla 
            FROM wezly_rurociagu w 
            LEFT JOIN segmenty s1 ON w.id = s1.id_wezla_startowego 
            LEFT JOIN segmenty s2 ON w.id = s2.id_wezla_koncowego 
            WHERE s1.id IS NULL AND s2.id IS NULL
        """)
        isolated_nodes = cursor.fetchall()
        if isolated_nodes:
            warnings.append({
                'type': 'isolated_nodes',
                'message': f'Znaleziono {len(isolated_nodes)} izolowanych węzłów',
                'items': [n['nazwa_wezla'] for n in isolated_nodes]
            })
        
        # Sprawdź sprzęt bez portów
        cursor.execute("""
            SELECT s.nazwa_unikalna 
            FROM sprzet s 
            LEFT JOIN porty_sprzetu p ON s.id = p.id_sprzetu 
            WHERE p.id IS NULL
        """)
        equipment_without_ports = cursor.fetchall()
        if equipment_without_ports:
            warnings.append({
                'type': 'equipment_without_ports',
                'message': f'Znaleziono {len(equipment_without_ports)} sprzętów bez portów',
                'items': [e['nazwa_unikalna'] for e in equipment_without_ports]
            })
        
        # Oblicz ogólny stan zdrowia
        total_issues = len(health_issues)
        total_warnings = len(warnings)
        
        if total_issues > 0:
            status = 'critical'
            status_message = f'Krytyczne problemy w topologii: {total_issues}'
        elif total_warnings > 0:
            status = 'warning'
            status_message = f'Ostrzeżenia w topologii: {total_warnings}'
        else:
            status = 'healthy'
            status_message = 'Topologia w dobrym stanie'
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'status': status,
                'message': status_message,
                'issues': health_issues,
                'warnings': warnings,
                'summary': {
                    'total_issues': total_issues,
                    'total_warnings': total_warnings,
                    'checked_at': datetime.now(timezone.utc).isoformat()
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas sprawdzania stanu topologii: {str(e)}'
        }), 500

@topology_bp.route('/api/isolated-nodes', methods=['GET'])
def api_isolated_nodes():
    """API: Znajduje izolowane węzły w topologii"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Znajdź węzły bez połączeń
        cursor.execute("""
            SELECT w.id, w.nazwa_wezla, w.opis,
                   COUNT(s1.id) + COUNT(s2.id) as connections_count
            FROM wezly_rurociagu w 
            LEFT JOIN segmenty s1 ON w.id = s1.id_wezla_startowego 
            LEFT JOIN segmenty s2 ON w.id = s2.id_wezla_koncowego 
            GROUP BY w.id, w.nazwa_wezla, w.opis
            HAVING connections_count = 0
            ORDER BY w.nazwa_wezla
        """)
        isolated_nodes = cursor.fetchall()
        
        # Znajdź węzły z tylko jednym połączeniem (martwe końce)
        cursor.execute("""
            SELECT w.id, w.nazwa_wezla, w.opis,
                   COUNT(s1.id) + COUNT(s2.id) as connections_count
            FROM wezly_rurociagu w 
            LEFT JOIN segmenty s1 ON w.id = s1.id_wezla_startowego 
            LEFT JOIN segmenty s2 ON w.id = s2.id_wezla_koncowego 
            GROUP BY w.id, w.nazwa_wezla, w.opis
            HAVING connections_count = 1
            ORDER BY w.nazwa_wezla
        """)
        dead_end_nodes = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'isolated_nodes': isolated_nodes,
                'dead_end_nodes': dead_end_nodes,
                'summary': {
                    'isolated_count': len(isolated_nodes),
                    'dead_end_count': len(dead_end_nodes),
                    'analyzed_at': datetime.now(timezone.utc).isoformat()
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Błąd podczas analizy izolowanych węzłów: {str(e)}'
        }), 500
