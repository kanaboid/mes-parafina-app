// app/static/js/aktywne_partie.js
// JavaScript dla zarządzania aktywnymi partiami w systemie

document.addEventListener('DOMContentLoaded', () => {
    // Globalne zmienne
    let wszystkiePartie = [];
    let filtrowanePartie = [];
    let wybranePartie = new Set();
    let aktualnaSortBy = 'data_utworzenia';
    let aktualnySortOrder = 'desc';
    
    // Elementy DOM
    const partieTableBody = document.getElementById('partie-table-body');
    const statsContainer = document.getElementById('stats-container');
    const detailsPanel = document.getElementById('details-panel');
    const searchInput = document.getElementById('search-input');
    const statusFilter = document.getElementById('status-filter');
    const typFilter = document.getElementById('typ-filter');
    const lokalizacjaFilter = document.getElementById('lokalizacja-filter');
    const operacjaFilter = document.getElementById('operacja-filter');
    
    // === FUNKCJE POMOCNICZE ===
    
    function showToast(message, type = 'info') {
        const options = {
            text: message,
            duration: 3000,
            gravity: "top",
            position: "right",
            stopOnFocus: true,
        };
        if (type === 'success') options.style = { background: "linear-gradient(to right, #00b09b, #96c93d)" };
        else if (type === 'error') options.style = { background: "linear-gradient(to right, #ff5f6d, #ffc371)" };
        else if (type === 'warning') options.style = { background: "linear-gradient(to right, #ff9a56, #ffad56)" };
        Toastify(options).showToast();
    }
    
    function formatWaga(wagaPoczatkowa, wagaAktualna) {
        const roznica = wagaAktualna - wagaPoczatkowa;
        const znak = roznica >= 0 ? '+' : '';
        return {
            aktualna: parseFloat(wagaAktualna).toLocaleString('pl-PL') + ' kg',
            poczatkowa: parseFloat(wagaPoczatkowa).toLocaleString('pl-PL') + ' kg',
            roznica: znak + parseFloat(roznica).toLocaleString('pl-PL') + ' kg',
            procent: Math.round((wagaAktualna / wagaPoczatkowa) * 100)
        };
    }
    
    function formatCzas(minuty) {
        if (!minuty) return '---';
        
        const dni = Math.floor(minuty / (24 * 60));
        const godziny = Math.floor((minuty % (24 * 60)) / 60);
        const min = minuty % 60;
        
        if (dni > 0) {
            return `${dni}d ${godziny}h ${min}m`;
        } else if (godziny > 0) {
            return `${godziny}h ${min}m`;
        } else {
            return `${min}m`;
        }
    }
    
    function getCzasClass(minuty) {
        if (!minuty) return '';
        
        const dni = minuty / (24 * 60);
        if (dni > 7) return 'time-danger';
        if (dni > 3) return 'time-warning';
        return 'time-success';
    }
    
    function getStatusBadgeClass(status) {
        const statusMap = {
            'W magazynie brudnym': 'bg-secondary',
            'Surowy w reaktorze': 'bg-info',
            'Budowanie placka': 'bg-warning',
            'Przelewanie': 'bg-primary',
            'Filtrowanie': 'bg-success',
            'Oczekiwanie na ocenę': 'bg-warning',
            'Do ponownej filtracji': 'bg-danger',
            'Dobielanie': 'bg-info',
            'Gotowy do wysłania': 'bg-success'
        };
        return statusMap[status] || 'bg-secondary';
    }
    
    function getOperationStatus(partia) {
        if (partia.id_operacji && partia.status_operacji === 'aktywna') {
            return {
                class: 'operation-active',
                text: partia.typ_operacji,
                icon: 'bi-gear-fill'
            };
        } else if (partia.status_partii === 'Oczekiwanie na ocenę') {
            return {
                class: 'operation-waiting',
                text: 'Oczekuje',
                icon: 'bi-clock'
            };
        } else {
            return {
                class: 'operation-none',
                text: 'Brak',
                icon: 'bi-dash-circle'
            };
        }
    }
    
    // === ŁADOWANIE I WYŚWIETLANIE DANYCH ===
    
    async function zaladujPartie() {
        try {
            pokazSkeletonTable();
            
            const response = await fetch('/api/partie/aktywne');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            wszystkiePartie = await response.json();
            aktualizujFiltry();
            zastosujFiltry();
            aktualizujStatystyki();
            
            showToast(`Załadowano ${wszystkiePartie.length} aktywnych partii`, 'success');
            
        } catch (error) {
            console.error('Błąd ładowania partii:', error);
            showToast('Błąd ładowania partii: ' + error.message, 'error');
            partieTableBody.innerHTML = '<tr><td colspan="10" class="text-center text-danger">Błąd ładowania danych</td></tr>';
        }
    }
    
    function pokazSkeletonTable() {
        const skeletonHTML = Array(5).fill(0).map(() => `
            <tr>
                <td><div class="loading-skeleton" style="height: 20px; width: 20px; border-radius: 3px;"></div></td>
                <td><div class="loading-skeleton" style="height: 20px; width: 100%;"></div></td>
                <td><div class="loading-skeleton" style="height: 20px; width: 80%;"></div></td>
                <td><div class="loading-skeleton" style="height: 20px; width: 60%;"></div></td>
                <td><div class="loading-skeleton" style="height: 20px; width: 90%;"></div></td>
                <td><div class="loading-skeleton" style="height: 20px; width: 70%;"></div></td>
                <td><div class="loading-skeleton" style="height: 20px; width: 80%;"></div></td>
                <td><div class="loading-skeleton" style="height: 20px; width: 70%;"></div></td>
                <td><div class="loading-skeleton" style="height: 20px; width: 60%;"></div></td>
                <td><div class="loading-skeleton" style="height: 20px; width: 100%;"></div></td>
            </tr>
        `).join('');
        
        partieTableBody.innerHTML = skeletonHTML;
    }
    
    function wyswietlPartie(partie) {
        if (!partie || partie.length === 0) {
            partieTableBody.innerHTML = '<tr><td colspan="10" class="text-center">Brak partii spełniających kryteria</td></tr>';
            return;
        }
        
        partieTableBody.innerHTML = '';
        
        partie.forEach(partia => {
            const row = utworzWierszPartii(partia);
            partieTableBody.appendChild(row);
        });
        
        // Odznacz checkbox "select all" jeśli nie wszystkie są wybrane
        const selectAllCheckbox = document.getElementById('select-all');
        selectAllCheckbox.checked = wybranePartie.size > 0 && wybranePartie.size === partie.length;
        selectAllCheckbox.indeterminate = wybranePartie.size > 0 && wybranePartie.size < partie.length;
    }
    
    function utworzWierszPartii(partia) {
        const row = document.createElement('tr');
        row.className = 'partia-row';
        row.dataset.partiaId = partia.id;
        
        if (wybranePartie.has(partia.id)) {
            row.classList.add('selected');
        }
        
        const waga = formatWaga(partia.waga_poczatkowa_kg, partia.waga_aktualna_kg);
        const operationStatus = getOperationStatus(partia);
        const czasClass = getCzasClass(partia.wiek_partii_minuty);
        
        row.innerHTML = `
            <td>
                <input type="checkbox" class="row-checkbox" value="${partia.id}" 
                       onchange="toggleRowSelection(${partia.id})" 
                       ${wybranePartie.has(partia.id) ? 'checked' : ''}>
            </td>
            <td>
                <strong onclick="pokazSzczegoly(${partia.id})" class="text-primary" style="cursor: pointer;">
                    ${highlightSearch(partia.unikalny_kod)}
                </strong>
                <br>
                <small class="text-muted">${formatCzas(partia.wiek_partii_minuty)}</small>
            </td>
            <td>
                <div>${highlightSearch(partia.nazwa_partii || 'N/A')}</div>
                <small class="text-muted">${partia.zrodlo_pochodzenia}</small>
            </td>
            <td>
                <span class="badge bg-light text-dark">${highlightSearch(partia.typ_surowca || 'N/A')}</span>
            </td>
            <td>
                <span class="badge ${getStatusBadgeClass(partia.status_partii)} status-badge">
                    ${partia.status_partii}
                </span>
            </td>
            <td>
                <div class="fw-bold">${waga.aktualna}</div>
                <div class="waga-progress">
                    <div class="waga-progress-bar" style="width: ${Math.min(waga.procent, 100)}%"></div>
                </div>
                <small class="text-muted">${waga.roznica}</small>
            </td>
            <td>
                <div class="fw-bold">${highlightSearch(partia.nazwa_sprzetu || 'Nieznana')}</div>
                <small class="text-muted">${partia.typ_sprzetu || 'N/A'}</small>
            </td>
            <td>
                <div class="time-info ${czasClass}">
                    <span class="time-value">${formatCzas(partia.wiek_partii_minuty)}</span>
                </div>
                <small class="text-muted">od utworzenia</small>
            </td>
            <td>
                <span class="operation-indicator ${operationStatus.class}"></span>
                <span class="fw-bold">${operationStatus.text}</span>
                ${partia.czas_trwania_operacji_minuty ? `<br><small class="text-muted">Trwa: ${formatCzas(partia.czas_trwania_operacji_minuty)}</small>` : ''}
            </td>
            <td>
                <div class="action-buttons">
                    <button class="btn btn-outline-primary btn-sm" onclick="pokazSzczegoly(${partia.id})" title="Pokaż szczegóły">
                        <i class="bi bi-eye"></i>
                    </button>
                    <button class="btn btn-outline-warning btn-sm" onclick="edytujStatus(${partia.id})" title="Zmień status">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-outline-info btn-sm" onclick="pokazHistorie(${partia.id})" title="Historia operacji">
                        <i class="bi bi-clock-history"></i>
                    </button>
                    ${partia.id_operacji && partia.status_operacji === 'aktywna' ? `
                        <button class="btn btn-outline-danger btn-sm" onclick="zatrzymajOperacje(${partia.id_operacji})" title="Zatrzymaj operację">
                            <i class="bi bi-stop"></i>
                        </button>
                    ` : ''}
                </div>
            </td>
        `;
        
        // Dodaj event listener do całego wiersza dla podświetlania
        row.addEventListener('click', (e) => {
            if (e.target.type !== 'checkbox' && !e.target.closest('button')) {
                document.querySelectorAll('.partia-row').forEach(r => r.classList.remove('selected'));
                row.classList.add('selected');
            }
        });
        
        return row;
    }
    
    function highlightSearch(text) {
        const searchTerm = searchInput.value.trim().toLowerCase();
        if (!searchTerm || !text) return text;
        
        const regex = new RegExp(`(${searchTerm})`, 'gi');
        return text.replace(regex, '<span class="search-highlight">$1</span>');
    }
    
    // === FILTROWANIE I WYSZUKIWANIE ===
    
    function aktualizujFiltry() {
        // Aktualizuj opcje filtra typu surowca
        const typy = [...new Set(wszystkiePartie.map(p => p.typ_surowca).filter(Boolean))];
        typFilter.innerHTML = '<option value="">Wszystkie</option>' +
            typy.map(typ => `<option value="${typ}">${typ}</option>`).join('');
        
        // Aktualizuj opcje filtra lokalizacji
        const lokalizacje = [...new Set(wszystkiePartie.map(p => p.nazwa_sprzetu).filter(Boolean))];
        lokalizacjaFilter.innerHTML = '<option value="">Wszystkie</option>' +
            lokalizacje.map(lok => `<option value="${lok}">${lok}</option>`).join('');
    }
    
    function zastosujFiltry() {
        let filtered = [...wszystkiePartie];
        
        // Filtr tekstowy
        const searchTerm = searchInput.value.trim().toLowerCase();
        if (searchTerm) {
            filtered = filtered.filter(partia => 
                partia.unikalny_kod.toLowerCase().includes(searchTerm) ||
                (partia.nazwa_partii && partia.nazwa_partii.toLowerCase().includes(searchTerm)) ||
                (partia.typ_surowca && partia.typ_surowca.toLowerCase().includes(searchTerm)) ||
                (partia.nazwa_sprzetu && partia.nazwa_sprzetu.toLowerCase().includes(searchTerm))
            );
        }
        
        // Filtr statusu
        const statusValue = statusFilter.value;
        if (statusValue) {
            filtered = filtered.filter(partia => partia.status_partii === statusValue);
        }
        
        // Filtr typu surowca
        const typValue = typFilter.value;
        if (typValue) {
            filtered = filtered.filter(partia => partia.typ_surowca === typValue);
        }
        
        // Filtr lokalizacji
        const lokalizacjaValue = lokalizacjaFilter.value;
        if (lokalizacjaValue) {
            filtered = filtered.filter(partia => partia.nazwa_sprzetu === lokalizacjaValue);
        }
        
        // Filtr operacji
        const operacjaValue = operacjaFilter.value;
        if (operacjaValue === 'aktywna') {
            filtered = filtered.filter(partia => partia.id_operacji && partia.status_operacji === 'aktywna');
        } else if (operacjaValue === 'brak') {
            filtered = filtered.filter(partia => !partia.id_operacji || partia.status_operacji !== 'aktywna');
        }
        
        filtrowanePartie = filtered;
        wyswietlPartie(filtrowanePartie);
    }
    
    // === STATYSTYKI ===
    
    function aktualizujStatystyki() {
        const stats = obliczStatystyki(wszystkiePartie);
        statsContainer.innerHTML = `
            <div class="stats-card">
                <div class="number">${stats.total}</div>
                <div class="label">Wszystkich partii</div>
            </div>
            <div class="stats-card">
                <div class="number">${stats.aktywneOperacje}</div>
                <div class="label">Aktywnych operacji</div>
            </div>
            <div class="stats-card">
                <div class="number">${stats.wagaLaczna.toLocaleString('pl-PL')} kg</div>
                <div class="label">Łączna waga</div>
            </div>
            <div class="stats-card">
                <div class="number">${stats.sredniatWiek}</div>
                <div class="label">Średni wiek</div>
            </div>
            <div class="stats-card">
                <div class="number">${stats.najczestszaLokalizacja}</div>
                <div class="label">Najczęstsza lokalizacja</div>
            </div>
        `;
    }
    
    function obliczStatystyki(partie) {
        if (!partie || partie.length === 0) {
            return {
                total: 0,
                aktywneOperacje: 0,
                wagaLaczna: 0,
                sredniatWiek: '0m',
                najczestszaLokalizacja: 'N/A'
            };
        }
        
        const total = partie.length;
        const aktywneOperacje = partie.filter(p => p.id_operacji && p.status_operacji === 'aktywna').length;
        const wagaLaczna = partie.reduce((sum, p) => sum + parseFloat(p.waga_aktualna_kg || 0), 0);
        const sredniatWiek = formatCzas(Math.round(partie.reduce((sum, p) => sum + (p.wiek_partii_minuty || 0), 0) / total));
        
        // Znajdź najczęstszą lokalizację
        const lokalizacje = {};
        partie.forEach(p => {
            if (p.nazwa_sprzetu) {
                lokalizacje[p.nazwa_sprzetu] = (lokalizacje[p.nazwa_sprzetu] || 0) + 1;
            }
        });
        const najczestszaLokalizacja = Object.keys(lokalizacje).reduce((a, b) => 
            lokalizacje[a] > lokalizacje[b] ? a : b, 'N/A'
        );
        
        return {
            total,
            aktywneOperacje,
            wagaLaczna,
            sredniatWiek,
            najczestszaLokalizacja
        };
    }
    
    // === AKCJE UŻYTKOWNIKA ===
    
    window.odswiezPartie = function() {
        wybranePartie.clear();
        zaladujPartie();
    };
    
    window.wyczyscFiltry = function() {
        searchInput.value = '';
        statusFilter.value = '';
        typFilter.value = '';
        lokalizacjaFilter.value = '';
        operacjaFilter.value = '';
        zastosujFiltry();
    };
    
    window.toggleSelectAll = function() {
        const selectAllCheckbox = document.getElementById('select-all');
        const checkboxes = document.querySelectorAll('.row-checkbox');
        
        checkboxes.forEach(checkbox => {
            checkbox.checked = selectAllCheckbox.checked;
            const partiaId = parseInt(checkbox.value);
            if (selectAllCheckbox.checked) {
                wybranePartie.add(partiaId);
            } else {
                wybranePartie.delete(partiaId);
            }
        });
        
        aktualizujWyborWierszy();
    };
    
    window.toggleRowSelection = function(partiaId) {
        if (wybranePartie.has(partiaId)) {
            wybranePartie.delete(partiaId);
        } else {
            wybranePartie.add(partiaId);
        }
        aktualizujWyborWierszy();
    };
    
    function aktualizujWyborWierszy() {
        // Aktualizuj klasy CSS wierszy
        document.querySelectorAll('.partia-row').forEach(row => {
            const partiaId = parseInt(row.dataset.partiaId);
            if (wybranePartie.has(partiaId)) {
                row.classList.add('selected');
            } else {
                row.classList.remove('selected');
            }
        });
        
        // Aktualizuj checkbox "select all"
        const selectAllCheckbox = document.getElementById('select-all');
        const visibleRows = document.querySelectorAll('.row-checkbox').length;
        selectAllCheckbox.checked = wybranePartie.size > 0 && wybranePartie.size === visibleRows;
        selectAllCheckbox.indeterminate = wybranePartie.size > 0 && wybranePartie.size < visibleRows;
    }
    
    // === SZCZEGÓŁY PARTII ===
    
    window.pokazSzczegoly = async function(partiaId) {
        try {
            const response = await fetch(`/api/partie/szczegoly/${partiaId}`);
            if (!response.ok) throw new Error('Nie udało się pobrać szczegółów');
            
            const partia = await response.json();
            wyswietlSzczegoly(partia);
            
        } catch (error) {
            showToast('Błąd ładowania szczegółów: ' + error.message, 'error');
        }
    };
    
    function wyswietlSzczegoly(partia) {
        document.getElementById('details-title').textContent = `Szczegóły partii: ${partia.unikalny_kod}`;
        
        const waga = formatWaga(partia.waga_poczatkowa_kg, partia.waga_aktualna_kg);
        
        let historiaHTML = '';
        if (partia.historia_operacji && partia.historia_operacji.length > 0) {
            historiaHTML = '<div class="historia-timeline">';
            partia.historia_operacji.forEach((op, index) => {
                const isActive = op.status_operacji === 'aktywna';
                const isCompleted = op.status_operacji === 'zakonczona';
                historiaHTML += `
                    <div class="timeline-item ${isActive ? 'active' : isCompleted ? 'completed' : ''}">
                        <div class="d-flex justify-content-between">
                            <strong>${op.typ_operacji}</strong>
                            <span class="badge ${isActive ? 'bg-warning' : isCompleted ? 'bg-success' : 'bg-secondary'}">
                                ${op.status_operacji}
                            </span>
                        </div>
                        <div class="mt-1">
                            <small class="text-muted">
                                ${op.czas_rozpoczecia} 
                                ${op.czas_zakonczenia ? ` - ${op.czas_zakonczenia}` : ''}
                                ${op.czas_trwania_min ? ` (${formatCzas(op.czas_trwania_min)})` : ''}
                            </small>
                        </div>
                        ${op.opis ? `<div class="mt-1">${op.opis}</div>` : ''}
                        ${op.punkt_startowy && op.punkt_docelowy ? 
                            `<div class="mt-1"><small>Trasa: ${op.punkt_startowy} → ${op.punkt_docelowy}</small></div>` : ''
                        }
                    </div>
                `;
            });
            historiaHTML += '</div>';
        } else {
            historiaHTML = '<p class="text-muted">Brak historii operacji</p>';
        }
        
        let cykleHTML = '';
        if (partia.cykle_filtracyjne && partia.cykle_filtracyjne.length > 0) {
            cykleHTML = `
                <div class="table-responsive mt-3">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>Cykl</th>
                                <th>Typ</th>
                                <th>Filtr</th>
                                <th>Czas</th>
                                <th>Wynik</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${partia.cykle_filtracyjne.map(cykl => `
                                <tr>
                                    <td>${cykl.numer_cyklu}</td>
                                    <td>${cykl.typ_cyklu}</td>
                                    <td>${cykl.id_filtra}</td>
                                    <td>${cykl.rzeczywisty_czas_minut ? formatCzas(cykl.rzeczywisty_czas_minut) : 'W trakcie'}</td>
                                    <td>
                                        <span class="badge ${cykl.wynik_oceny === 'pozytywna' ? 'bg-success' : 
                                                              cykl.wynik_oceny === 'negatywna' ? 'bg-danger' : 'bg-warning'}">
                                            ${cykl.wynik_oceny}
                                        </span>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        }
        
        document.getElementById('details-content').innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <h5>Informacje podstawowe</h5>
                    <table class="table table-sm">
                        <tr><th>Kod partii:</th><td>${partia.unikalny_kod}</td></tr>
                        <tr><th>Nazwa:</th><td>${partia.nazwa_partii || 'N/A'}</td></tr>
                        <tr><th>Typ surowca:</th><td>${partia.typ_surowca || 'N/A'}</td></tr>
                        <tr><th>Źródło:</th><td>${partia.zrodlo_pochodzenia}</td></tr>
                        <tr><th>Status:</th><td><span class="badge ${getStatusBadgeClass(partia.status_partii)}">${partia.status_partii}</span></td></tr>
                        <tr><th>Data utworzenia:</th><td>${partia.data_utworzenia}</td></tr>
                        <tr><th>Cykle filtracyjne:</th><td>${partia.ilosc_cykli_filtracyjnych}</td></tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h5>Informacje o wadze i lokalizacji</h5>
                    <table class="table table-sm">
                        <tr><th>Waga początkowa:</th><td>${waga.poczatkowa}</td></tr>
                        <tr><th>Waga aktualna:</th><td>${waga.aktualna}</td></tr>
                        <tr><th>Różnica:</th><td>${waga.roznica}</td></tr>
                        <tr><th>Procent:</th><td>${waga.procent}%</td></tr>
                        <tr><th>Lokalizacja:</th><td>${partia.nazwa_sprzetu || 'Nieznana'}</td></tr>
                        <tr><th>Typ sprzętu:</th><td>${partia.typ_sprzetu || 'N/A'}</td></tr>
                        <tr><th>Stan sprzętu:</th><td>${partia.stan_sprzetu || 'N/A'}</td></tr>
                    </table>
                </div>
            </div>
            
            <div class="row mt-4">
                <div class="col-12">
                    <h5>Historia operacji</h5>
                    ${historiaHTML}
                </div>
            </div>
            
            ${cykleHTML ? `
                <div class="row mt-4">
                    <div class="col-12">
                        <h5>Cykle filtracyjne</h5>
                        ${cykleHTML}
                    </div>
                </div>
            ` : ''}
        `;
        
        detailsPanel.classList.add('show');
    }
    
    window.zamknijSzczegoly = function() {
        detailsPanel.classList.remove('show');
    };
    
    // === EDYCJA STATUSU ===
    
    window.edytujStatus = function(partiaId) {
        const partia = wszystkiePartie.find(p => p.id === partiaId);
        if (!partia) return;
        
        document.getElementById('edit-partia-id').value = partiaId;
        document.getElementById('edit-current-code').textContent = partia.unikalny_kod;
        document.getElementById('edit-new-status').value = partia.status_partii;
        document.getElementById('edit-comment').value = '';
        
        const modal = new bootstrap.Modal(document.getElementById('editStatusModal'));
        modal.show();
    };
    
    window.zapiszZmianeStatusu = async function() {
        const partiaId = document.getElementById('edit-partia-id').value;
        const nowyStatus = document.getElementById('edit-new-status').value;
        const komentarz = document.getElementById('edit-comment').value;
        
        if (!nowyStatus) {
            showToast('Wybierz nowy status', 'warning');
            return;
        }
        
        try {
            const response = await fetch('/api/partie/aktualizuj-status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id_partii: parseInt(partiaId),
                    nowy_status: nowyStatus,
                    komentarz: komentarz
                })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                showToast(result.message, 'success');
                bootstrap.Modal.getInstance(document.getElementById('editStatusModal')).hide();
                zaladujPartie(); // Przeładuj dane
            } else {
                showToast(result.error, 'error');
            }
        } catch (error) {
            showToast('Błąd sieciowy: ' + error.message, 'error');
        }
    };
    
    // === POZOSTAŁE AKCJE ===
    
    window.pokazHistorie = function(partiaId) {
        // Ta funkcja jest już zaimplementowana w pokazSzczegoly
        pokazSzczegoly(partiaId);
    };
    
    window.zatrzymajOperacje = async function(operacjaId) {
        if (!confirm('Czy na pewno chcesz zatrzymać tę operację?')) return;
        
        try {
            const response = await fetch('/api/operacje/zakoncz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id_operacji: operacjaId })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                showToast(result.message, 'success');
                zaladujPartie();
            } else {
                showToast(result.message, 'error');
            }
        } catch (error) {
            showToast('Błąd zatrzymywania operacji: ' + error.message, 'error');
        }
    };
    
    window.exportujCSV = function() {
        if (filtrowanePartie.length === 0) {
            showToast('Brak danych do eksportu', 'warning');
            return;
        }
        
        const headers = ['Kod Partii', 'Nazwa', 'Typ Surowca', 'Status', 'Waga Aktualna', 'Lokalizacja', 'Czas w Systemie'];
        const csvContent = [
            headers.join(';'),
            ...filtrowanePartie.map(partia => [
                partia.unikalny_kod,
                partia.nazwa_partii || '',
                partia.typ_surowca || '',
                partia.status_partii,
                partia.waga_aktualna_kg,
                partia.nazwa_sprzetu || '',
                formatCzas(partia.wiek_partii_minuty)
            ].join(';'))
        ].join('\n');
        
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `aktywne_partie_${new Date().toISOString().split('T')[0]}.csv`;
        link.click();
        
        showToast('Eksport CSV rozpoczęty', 'success');
    };
    
    // === EVENT LISTENERY ===
    
    searchInput.addEventListener('input', zastosujFiltry);
    statusFilter.addEventListener('change', zastosujFiltry);
    typFilter.addEventListener('change', zastosujFiltry);
    lokalizacjaFilter.addEventListener('change', zastosujFiltry);
    operacjaFilter.addEventListener('change', zastosujFiltry);
    
    // === INICJALIZACJA ===
    
    zaladujPartie();
    
    // Automatyczne odświeżanie co 60 sekund
    setInterval(() => {
        if (!detailsPanel.classList.contains('show')) {
            zaladujPartie();
        }
    }, 60000);
});
