// app/static/js/dashboard.js

document.addEventListener('DOMContentLoaded', () => {
    
    // --- ELEMENTY DOM, MODALE, FORMULARZE ---
    let latestDashboardData = {}; // Globalne przechowywanie danych
    const reaktoryContainer = document.getElementById('reaktory-container');
    const beczkiBrudneContainer = document.getElementById('beczki-brudne-container');
    const beczkiCzysteContainer = document.getElementById('beczki-czyste-container');
    const alarmsContainer = document.getElementById('alarms-container');
    const activeOperationsContainer = document.getElementById('active-operations-log'); // Nowy element
    const lastUpdatedTime = document.getElementById('last-updated-time');
    const stockSummaryContainer = document.getElementById('stock-summary-container');

    const modals = {
        planTransfer: new bootstrap.Modal(document.getElementById('plan-transfer-modal')),
        startHeating: new bootstrap.Modal(document.getElementById('start-heating-modal')),
        simulationSettings: new bootstrap.Modal(document.getElementById('simulation-settings-modal')),
        transferTankToTank: new bootstrap.Modal(document.getElementById('transfer-tank-to-tank-modal')),
        startFiltration: new bootstrap.Modal(document.getElementById('start-filtration-modal')),
        ocenaProbki: new bootstrap.Modal(document.getElementById('ocena-probki-modal')),
        przelewDest: new bootstrap.Modal(document.getElementById('przelew-dest-modal')),
        naMagazyn: new bootstrap.Modal(document.getElementById('na-magazyn-modal')),
        dmuchanieChangeDest: new bootstrap.Modal(document.getElementById('dmuchanie-change-dest-modal')),
        dobielanie: new bootstrap.Modal(document.getElementById('dobielanie-modal')),
        filtracjaNaPlacku: new bootstrap.Modal(document.getElementById('filtracja-na-placku-modal')),
        dmuchanieCzyszczenie: new bootstrap.Modal(document.getElementById('dmuchanie-czyszczenie-modal')),
        dmuchanieRurociagu: new bootstrap.Modal(document.getElementById('dmuchanie-rurociagu-modal')),
        wyborDmuchania: new bootstrap.Modal(document.getElementById('wybor-dmuchania-modal'))
    };
    const forms = {
        planTransfer: document.getElementById('plan-transfer-form'),
        startHeating: document.getElementById('start-heating-form'),
        simulationSettings: document.getElementById('simulation-settings-form'),
        transferTankToTank: document.getElementById('transfer-tank-to-tank-form'),
        startFiltration: document.getElementById('start-filtration-form'),
        ocenaProbki: document.getElementById('ocena-probki-form'),
        przelewDest: document.getElementById('przelew-dest-form'),
        naMagazyn: document.getElementById('na-magazyn-form'),
        dmuchanieChangeDest: document.getElementById('dmuchanie-change-dest-form'),
        dobielanie: document.getElementById('dobielanie-form'),
        dmuchanieCzyszczenie: document.getElementById('dmuchanie-czyszczenie-form'),
        dmuchanieRurociagu: document.getElementById('dmuchanie-rurociagu-form'),
        wyborDmuchania: document.getElementById('wybor-dmuchania-form'),
        filtracjaNaPlacku: document.getElementById('filtracja-na-placku-form')
    };

    const formatValue = (value, unit = '', decimalPlaces = 1) => {
        if (value === null || typeof value === 'undefined') {
            return 'B/D';
        }
        if (typeof value === 'number') {
            return `${value.toFixed(decimalPlaces)}${unit}`;
        }
        return `${value}${unit}`;
    };
    
    // --- SOCKET.IO ---
    const socket = io();
    socket.on('connect', () => console.log("Połączono z dashboardem przez WebSocket."));
    
    socket.on('dashboard_update', (data) => {
        console.log("Otrzymano aktualizację dashboardu:", data);
        latestDashboardData = data; // Zapisz najnowsze dane
        updateUI(data);
    });

    socket.on('heating_completed', (data) => {
        console.log("Otrzymano powiadomienie o zakończeniu podgrzewania:", data);
        
        // Wyświetl powiadomienie toast
        showToast(
            data.message || `Reaktor ${data.nazwa} osiągnął temperaturę docelową!`,
            'success', // Użyj stylu 'success' dla zielonego koloru
            false
        );
        
        // Opcjonalnie: możemy dodać wizualne wyróżnienie na karcie reaktora
        const reactorCard = document.getElementById(`reaktor-card-${data.sprzet_id}`); // Zakładając, że karty mają ID
        if (reactorCard) {
            reactorCard.classList.add('border-success', 'border-3');
            // Usuń wyróżnienie po kilku sekundach
            setTimeout(() => {
                reactorCard.classList.remove('border-success', 'border-3');
            }, 10000); // 10 sekund
        }
    });

    // --- GŁÓWNA FUNKCJA AKTUALIZUJĄCA UI ---
    function updateUI(data) {
        renderReaktory(data.all_reactors);
        renderBeczki(data.beczki_brudne, beczkiBrudneContainer, true);
        renderBeczki(data.beczki_czyste, beczkiCzysteContainer, false);
        renderAlarms(data.alarmy);
        renderStockSummary(data.stock_summary);
        renderActiveOperations(data.active_operations); // Nowe wywołanie
        lastUpdatedTime.textContent = `Ostatnia aktualizacja: ${new Date().toLocaleTimeString()}`;
    }

    // --- FUNKCJE RENDERUJĄCE ---
    function renderReaktory(reaktory) {
        reaktoryContainer.innerHTML = '';
        if (!reaktory || reaktory.length === 0) {
            reaktoryContainer.innerHTML = '<div class="col"><p class="text-muted">Brak reaktorów w systemie.</p></div>';
            return;
        }

        reaktory.forEach(r => {
            
            // --- LOGIKA DLA PRZYCISKÓW ---
            let actionButtonsHTML = `
                <button class="btn btn-primary action-btn" 
                        data-action="show-details" 
                        data-sprzet-id="${r.id}"
                        data-sprzet-nazwa="${r.nazwa}">
                    <i class="fas fa-info-circle"></i>
                </button>
                <button class="btn btn-secondary action-btn" 
                        data-action="open-simulation-settings" 
                        data-sprzet-id="${r.id}"
                        data-sprzet-nazwa="${r.nazwa}">
                    <i class="fas fa-sliders-h"></i>
                </button>
            `;
            
            // Przycisk "Przelej" - zawsze widoczny
            actionButtonsHTML += `
            <button class="btn btn-info action-btn" 
                    data-action="open-transfer-modal" 
                    data-sprzet-id="${r.id}"
                    data-sprzet-nazwa="${r.nazwa}"
                    data-partia-waga="${r.partia ? r.partia.waga_kg : '0'}">
                <i class="fas fa-exchange-alt"></i>
            </button>`;

            // Mieszanina zawiera tylko batche WYDMUCH – ukryj dobielanie i filtrację
            const isOnlyWydmuch = r.partia && r.partia.sklad && r.partia.sklad.length > 0 &&
                r.partia.sklad.every(item => (item.material_type || '').toUpperCase() === 'WYDMUCH');

            // Przycisk Dobielanie – gdy process_status: SUROWY, PODGRZEWANY, DO_PONOWNEJ_FILTRACJI, FILTRACJA_PRZELEW_PRZERWANE (nie gdy tylko WYDMUCH)
            const canDobielanie = r.partia && !isOnlyWydmuch && ['SUROWY', 'PODGRZEWANY', 'DO_PONOWNEJ_FILTRACJI', 'FILTRACJA_PRZELEW_PRZERWANE'].includes(r.partia.process_status);
            if (canDobielanie) {
                actionButtonsHTML += `
                    <button class="btn btn-warning action-btn" 
                            data-action="open-dobielanie-modal" 
                            data-sprzet-id="${r.id}"
                            data-sprzet-nazwa="${r.nazwa}"
                            data-mix-id="${r.partia.id}"
                            title="Zarejestruj dodanie ziemi bielącej">
                        <i class="fas fa-cube me-1"></i>Dobielanie
                    </button>`;
            }
            // Sprawdź, czy należy dodać przycisk kontekstowy
            if (r.partia && r.partia.process_status === 'SUROWY') {
                actionButtonsHTML += `
                    <button class="btn btn-warning action-btn" 
                            data-action="start-heating" 
                            data-sprzet-id="${r.id}"
                            data-sprzet-nazwa="${r.nazwa}">
                        Wlącz palnik(INFO)
                    </button>`;
            }
            // Przyciski filtracji – warunkowe na podstawie process_status (ukryte gdy mix zawiera tylko WYDMUCH)
            if (r.partia && !isOnlyWydmuch) {
                const ps = r.partia.process_status;

                if (ps === 'DOBIELONY_OCZEKUJE') {
                    // Standardowa filtracja po dobielaniu
                    actionButtonsHTML += `
                        <button class="btn btn-success action-btn" 
                                data-action="open-start-filtration-modal" 
                                data-sprzet-id="${r.id}"
                                data-sprzet-nazwa="${r.nazwa}"
                                data-mix-id="${r.partia.id}"
                                title="Rozpocznij cykl filtracji po dobielaniu">
                            <i class="fas fa-filter me-1"></i>Start filtracji
                        </button>`;
                } else if (ps === 'FILTRACJA_KOLO' || ps === 'OCZEKUJE_NA_OCENE') {
                    // Kolejny cykl filtracji kołowej
                    actionButtonsHTML += `
                        <button class="btn btn-success action-btn" 
                                data-action="open-start-filtration-modal" 
                                data-sprzet-id="${r.id}"
                                data-sprzet-nazwa="${r.nazwa}"
                                data-mix-id="${r.partia.id}"
                                title="Rozpocznij kolejny cykl filtracji kołowej">
                            <i class="fas fa-filter me-1"></i>Start filtracji (koło)
                        </button>`;
                }

                // FILTRACJA_NA_PLACKU – dostępna dla każdego statusu OPRÓCZ DOBIELONY_OCZEKUJE
                // i statusów aktywnej filtracji (operacja już trwa)
                const AKTYWNA_FILTRACJA = [
                    'DOBIELONY_OCZEKUJE',
                    'FILTRACJA_PLACEK_KOLO', 'FILTRACJA_PLACEK_PRZELEW',
                    'FILTRACJA_PRZELEW', 'FILTRACJA_WYDMUCH', 'FILTRACJA_NA_PLACKU',
                ];
                if (!AKTYWNA_FILTRACJA.includes(ps)) {
                    actionButtonsHTML += `
                        <button class="btn action-btn" 
                                style="background-color:#6f42c1;border-color:#6f42c1;color:#fff;"
                                data-action="open-filtracja-na-placku-modal" 
                                data-sprzet-id="${r.id}"
                                data-sprzet-nazwa="${r.nazwa}"
                                data-mix-id="${r.partia.id}"
                                title="Filtracja na placku – odfiltrowanie wydmuchów, następny etap: FILTRACJA_KOLO">
                            <i class="fas fa-filter me-1"></i>Filtracja na placku
                        </button>`;
                }
            }
            // Przycisk Na magazyn – gdy mieszanina zatwierdzona (można przelewać do beczki czystej)
            if (r.partia && r.partia.process_status === 'ZATWIERDZONA') {
                actionButtonsHTML += `
                    <button class="btn btn-warning action-btn" 
                            data-action="open-transfer-modal" 
                            data-sprzet-id="${r.id}"
                            data-sprzet-nazwa="${r.nazwa}"
                            data-partia-waga="${r.partia ? r.partia.waga_kg : '0'}"
                            title="Przelej na magazyn (beczka czysta)">
                        <i class="fas fa-warehouse me-1"></i>Na magazyn
                    </button>`;
            }
            
            // --- Logika dla statusu ---
            const isEmpty = !r.partia;
            const statusClass = r.stan_sprzetu === 'W transferze' ? 'status-alarm' : (r.partia ? 'status-ok' : 'status-idle');
            
            // --- TYP MATERIAŁU - WYEKSPONOWANY ---
            let materialTypeHTML = '';
            if (r.partia && r.partia.sklad && r.partia.sklad.length > 0) {
                const materialTypes = [...new Set(r.partia.sklad.map(item => item.material_type))];
                const materialTypesText = materialTypes.join(' + ');
                
                materialTypeHTML = `
                    <div class="text-center p-3 rounded-3 mb-3 shadow-sm" style="background-color: #f5deb3;">
                        <div class="d-flex align-items-center justify-content-center">
                            <i class="fas fa-flask fs-3 me-3" style="color: #856404;"></i>
                            <h3 class="mb-0 fw-bold" style="color: #856404;">${materialTypesText}</h3>
                        </div>
                    </div>
                `;
            }

            // --- WAGA - WYEKSPONOWANA Z PROGRESS BAREM ---
            let wagaHTML = '';
            let capacityProgressHTML = '';
            
            if (r.partia && r.partia.waga_kg > 0) {
                const wagaTonnes = (r.partia.waga_kg / 1000).toFixed(2);
                const pojemnoscTonnes = r.pojemnosc_kg ? (r.pojemnosc_kg / 1000).toFixed(2) : null;
                
                wagaHTML = `
                    <div class="bg-light p-3 rounded-3 mb-3 border border-primary border-opacity-25">
                        <div class="d-flex justify-content-between align-items-center">
                            <div class="d-flex align-items-center">
                                <i class="fas fa-weight-hanging text-primary fs-4 me-2"></i>
                                <span class="text-muted">Waga:</span>
                            </div>
                            <div class="text-end">
                                <span class="fs-3 fw-bold text-primary">${wagaTonnes} t</span>
                                ${pojemnoscTonnes ? `<span class="text-muted" style="font-weight: normal; opacity: 0.7;"> / ${pojemnoscTonnes} t</span>` : ''}
                            </div>
                        </div>
                    </div>
                `;
                
                // Progress bar zapełnienia reaktora
                if (r.pojemnosc_kg && r.pojemnosc_kg > 0) {
                    const fillPercent = (r.partia.waga_kg / r.pojemnosc_kg) * 100;
                    let fillColorClass = 'bg-info';
                    if (fillPercent > 95) fillColorClass = 'bg-danger';
                    else if (fillPercent > 80) fillColorClass = 'bg-warning';
                    
                    capacityProgressHTML = `
                        <div class="mb-3">
                            <div class="d-flex justify-content-between mb-1">
                                <small class="text-muted"><i class="fas fa-chart-line me-1"></i>Zapełnienie reaktora</small>
                                <small class="fw-bold text-primary">${fillPercent.toFixed(1)}%</small>
                            </div>
                            <div class="progress" style="height: 10px;">
                                <div class="progress-bar ${fillColorClass}" role="progressbar" 
                                     style="width: ${fillPercent}%;" 
                                     aria-valuenow="${fillPercent}" aria-valuemin="0" aria-valuemax="100"></div>
                            </div>
                        </div>
                    `;
                }
            }

            // --- KOD PARTII I STATUS PROCESU ---
            const partiaHTML = r.partia ? `
                <div class="d-flex align-items-center mb-2">
                    <i class="fas fa-barcode text-muted me-2"></i>
                    <span class="text-muted me-2">Partia:</span>
                    <span class="fw-semibold">${r.partia.kod}</span>
                </div>
                <div class="d-flex align-items-center mb-3">
                    <span class="text-muted me-2 small">Status procesu:</span>
                    <span class="badge bg-secondary text-wrap">${r.partia.process_status || '—'}</span>
                </div>
            ` : '<p class="text-center text-muted fst-italic mb-3"><i class="fas fa-inbox me-2"></i>Reaktor pusty</p>';
            
            // --- TEMPERATURA Z PROGRESS BAREM ---
            let tempPercent = (r.temperatura_aktualna && r.temperatura_max) ? (r.temperatura_aktualna / r.temperatura_max) * 100 : 0;
            let tempColorClass = 'bg-success';
            if (tempPercent > 95) tempColorClass = 'bg-danger';
            else if (tempPercent > 80) tempColorClass = 'bg-warning';
            
            const tempProgressBar = `
                <div class="mb-3">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <small class="text-muted"><i class="fas fa-thermometer-half me-1"></i>Temperatura</small>
                        <small class="fw-semibold">${r.temperatura_aktualna ? r.temperatura_aktualna.toFixed(4) : 'N/A'}°C / ${r.temperatura_docelowa || 'N/A'}°C</small>
                    </div>
                    <div class="progress" style="height: 10px;">
                        <div class="progress-bar ${tempColorClass}" role="progressbar" style="width: ${tempPercent}%;"></div>
                    </div>
                </div>
            `;
            
            // --- CIŚNIENIE Z PROGRESS BAREM ---
            let pressurePercent = (r.cisnienie_aktualne && r.cisnienie_max) ? (r.cisnienie_aktualne / r.cisnienie_max) * 100 : 0;
            let pressureColorClass = 'bg-success';
            if (pressurePercent > 95) pressureColorClass = 'bg-danger';
            else if (pressurePercent > 80) pressureColorClass = 'bg-warning';
            
            const pressureProgressBar = `
                <div class="mb-3">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <small class="text-muted"><i class="fas fa-tachometer-alt me-1"></i>Ciśnienie</small>
                        <small class="fw-semibold">${r.cisnienie_aktualne || 'N/A'} bar</small>
                    </div>
                    <div class="progress" style="height: 10px;">
                        <div class="progress-bar ${pressureColorClass}" role="progressbar" style="width: ${pressurePercent}%;"></div>
                    </div>
                </div>
            `;
            

            let levelProgressBar = '';
            if (r.odczyt_mm != null) {
                if (r.poziom_tony != null) {
                    // Wyświetl wagę w tonach z kalibracji
                    levelProgressBar = `
                        <div class="mb-3">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <small class="text-muted"><i class="fas fa-weight me-1"></i>Poziom (czujnik)</small>
                                <small class="fw-semibold">${formatValue(r.poziom_tony, ' t', 2)}</small>
                            </div>
                            <small class="text-muted">Odczyt: ${formatValue((r.odczyt_mm / 10), ' cm', 0)}</small>
                        </div>
                    `;
                } else if (r.ma_kalibracje === false) {
                    // Ostrzeżenie, że zbiornik nie ma kalibracji
                    levelProgressBar = `
                        <div class="alert alert-warning alert-sm py-1 px-2 mb-3">
                            <small><i class="fas fa-exclamation-triangle me-1"></i>Brak kalibracji</small>
                        </div>
                        <small class="text-muted">Odczyt: ${formatValue((r.odczyt_mm / 10), ' cm', 0)}</small>
                    `;
                } else {
                    // Fallback: pokaż odczyt bez konwersji
                    levelProgressBar = `
                        <div class="mb-3">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <small class="text-muted"><i class="fas fa-ruler-vertical me-1"></i>Poziom (czujnik)</small>
                                <small class="fw-semibold"><span class="text-muted fw-normal">(${formatValue((r.odczyt_mm / 10), ' cm', 0)})</span></small>
                            </div>
                        </div>
                    `;
                }
            }


            // --- PALNIK Z IKONĄ ---
            const isBurnerOn = r.stan_palnika === 'WLACZONY';
            const burnerSwitchHTML = `
                <div class="d-flex justify-content-between align-items-center mt-3 p-2 bg-light rounded">
                    <div class="form-check form-switch mb-0">
                        <input class="form-check-input action-btn" type="checkbox" role="switch" id="burner-switch-${r.id}"
                               data-action="toggle-burner" data-sprzet-id="${r.id}" ${isBurnerOn ? 'checked' : ''}>
                        <label class="form-check-label" for="burner-switch-${r.id}">
                            Palnik ${isBurnerOn ? '<span class="text-danger fw-bold">WŁĄCZONY</span>' : '<span class="text-muted">WYŁĄCZONY</span>'}
                        </label>
                    </div>
                    <i class="fas fa-fire ${isBurnerOn ? 'text-danger' : 'text-muted'} fs-4"></i>
                </div>`;

        // --- Kompletny szablon karty ---
        const cardHTML = `
            <div class="col-xl-4 col-lg-6 mb-4" id="reaktor-card-${r.id}">
                <div class="card h-100 card-reaktor shadow-sm">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5 class="mb-0"><span class="status-indicator ${statusClass}"></span>${r.nazwa}</h5>
                        <span class="badge ${isEmpty ? 'bg-secondary' : 'bg-success'}">${r.stan_sprzetu || 'Gotowy'}</span>
                    </div>
                    <div class="card-body">
                        ${materialTypeHTML}
                        ${wagaHTML}
                        ${capacityProgressHTML}
                        ${partiaHTML}
                        ${tempProgressBar}
                        ${pressureProgressBar}
                        ${levelProgressBar}
                        ${burnerSwitchHTML}
                    </div>
                    <div class="card-footer p-2">
                        <div class="btn-group w-100" role="group" aria-label="Akcje dla reaktora">
                            ${actionButtonsHTML}
                        </div>
                    </div>
                </div>
            </div>`;
            reaktoryContainer.innerHTML += cardHTML;
        });
    }

    function renderBeczki(beczki, container, isBrudna) {
        container.innerHTML = '';
        if (!beczki || beczki.length === 0) {
            container.innerHTML = '<div class="col"><p class="text-muted">Brak danych.</p></div>';
            return;
        }
        
        beczki.forEach(b => {
            // Określ status wizualny beczki
            const isEmpty = !b.partia || !b.partia.waga_kg || b.partia.waga_kg === 0;
            const statusClass = isEmpty ? 'border-secondary' : (isBrudna ? 'border-danger' : 'border-success');
            const statusBgClass = isEmpty ? 'bg-light' : (isBrudna ? 'bg-danger bg-opacity-10' : 'bg-success bg-opacity-10');
            const statusIcon = isEmpty ? 'fa-circle text-secondary' : (isBrudna ? 'fa-circle text-danger' : 'fa-circle text-success');
            
            // Typ materiału
            let materialTypeHTML = '';
            if (b.partia && b.partia.sklad && b.partia.sklad.length > 0) {
                const materialTypes = [...new Set(b.partia.sklad.map(item => item.material_type))];
                const materialTypesText = materialTypes.join(' + ');
                materialTypeHTML = `
                    <div class="text-center bg-white p-2 rounded mb-2 border border-primary border-opacity-25">
                        <h5 class="mb-0 text-primary fw-bold">${materialTypesText}</h5>
                    </div>
                `;
            }

            // Waga w tonach i progress bar
            let wagaHTML = '';
            let progressBarHTML = '';
            
            if (b.partia && b.partia.waga_kg > 0) {
                const wagaTonnes = (b.partia.waga_kg / 1000).toFixed(2);
                const pojemnoscTonnes = b.pojemnosc_kg ? (b.pojemnosc_kg / 1000).toFixed(2) : 'N/A';
                
                wagaHTML = `
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="text-muted"><i class="fas fa-weight-hanging me-2"></i>Waga:</span>
                        <span class="fs-5 fw-bold">${wagaTonnes} t ${b.pojemnosc_kg ? `<span style="font-weight: normal; opacity: 0.7;">/ ${pojemnoscTonnes} t</span>` : ''}</span>
                    </div>
                `;
                
                // Progress bar zapełnienia
                if (b.pojemnosc_kg && b.pojemnosc_kg > 0) {
                    const fillPercent = (b.partia.waga_kg / b.pojemnosc_kg) * 100;
                    let fillColorClass = 'bg-success';
                    if (fillPercent > 95) fillColorClass = 'bg-danger';
                    else if (fillPercent > 80) fillColorClass = 'bg-warning';
                    
                    progressBarHTML = `
                        <div class="mb-3">
                            <div class="d-flex justify-content-between mb-1">
                                <small class="text-muted"><i class="fas fa-chart-bar me-1"></i>Zapełnienie</small>
                                <small class="fw-bold text-primary">${fillPercent.toFixed(1)}%</small>
                            </div>
                            <div class="progress" style="height: 12px;">
                                <div class="progress-bar ${fillColorClass}" role="progressbar" 
                                     style="width: ${fillPercent}%;" 
                                     aria-valuenow="${fillPercent}" aria-valuemin="0" aria-valuemax="100"></div>
                            </div>
                        </div>
                    `;
                }
            }

            let levelProgressBar = '';
            if (b.odczyt_mm != null) {
                if (b.poziom_tony != null) {
                    // Wyświetl wagę w tonach z kalibracji
                    levelProgressBar = `
                        <div class="mb-2">
                            <div class="d-flex justify-content-between mb-1">
                                <small class="text-muted"><i class="fas fa-weight me-1"></i>Poziom (czujnik)</small>
                                <small class="fw-semibold">${formatValue(b.poziom_tony, ' t', 2)}</small>
                            </div>
                            <small class="text-muted">Odczyt: ${formatValue((b.odczyt_mm / 10), ' cm', 0)}</small>
                        </div>
                    `;
                } else if (b.ma_kalibracje === false) {
                    // Ostrzeżenie, że zbiornik nie ma kalibracji
                    levelProgressBar = `
                        <div class="alert alert-warning alert-sm py-1 px-2 mb-2">
                            <small><i class="fas fa-exclamation-triangle me-1"></i>Brak kalibracji</small>
                        </div>
                        <small class="text-muted">Odczyt: ${formatValue((b.odczyt_mm / 10), ' cm', 0)}</small>
                    `;
                } else {
                    // Fallback: pokaż odczyt bez konwersji
                    levelProgressBar = `
                        <div class="mb-2">
                            <div class="d-flex justify-content-between mb-1">
                                <small class="text-muted"><i class="fas fa-ruler-vertical me-1"></i>Poziom (czujnik)</small>
                                <small class="fw-semibold"><span class="text-muted fw-normal">(${formatValue((b.odczyt_mm / 10), ' cm', 0)})</span></small>
                            </div>
                        </div>
                    `;
                }
            }


            // Kod partii
            const partiaHTML = b.partia && b.partia.kod ? `
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="text-muted"><i class="fas fa-barcode me-2"></i>Partia:</span>
                    <span class="fw-semibold">${b.partia.kod}</span>
                </div>
            ` : '<p class="text-center text-muted fst-italic mb-2"><i class="fas fa-inbox me-2"></i>Pusta</p>';

            const cardHTML = `
                <div class="col-xl-3 col-lg-4 col-md-6">
                    <div class="card h-100 shadow-sm ${statusClass} border-2 ${statusBgClass}">
                        <div class="card-header ${statusBgClass} d-flex justify-content-between align-items-center">
                            <h6 class="mb-0 fw-bold">
                                <i class="fas ${statusIcon} me-2"></i>
                                ${b.nazwa}
                            </h6>
                            <span class="badge ${isEmpty ? 'bg-secondary' : (isBrudna ? 'bg-danger' : 'bg-success')}">
                                ${b.stan_sprzetu || 'Gotowy'}
                            </span>
                        </div>
                        <div class="card-body">
                            ${materialTypeHTML}
                            ${partiaHTML}
                            ${wagaHTML}
                            ${progressBarHTML}
                            ${levelProgressBar}
                        </div>
                        <div class="card-footer p-2">
                            <button class="btn btn-info w-100 action-btn"
                                     data-action="open-transfer-modal"
                                     data-sprzet-id="${b.id}"
                                     data-sprzet-nazwa="${b.nazwa}"
                                     data-partia-waga="${b.partia ? b.partia.waga_kg : '0'}">
                                <i class="fas fa-exchange-alt me-1"></i>Przelej
                            </button>
                        </div>
                    </div>
                </div>
            `;
            container.innerHTML += cardHTML;
        });
    }

    function renderAlarms(alarmy) {
        alarmsContainer.innerHTML = '';
        if (!alarmy || alarmy.length === 0) return;
        alarmy.forEach(a => {
            const alarmHTML = `
                <div class="alert alert-danger alert-dismissible fade show" role="alert">
                    <strong>ALARM ${a.typ}!</strong> W urządzeniu <strong>${a.sprzet}</strong> zanotowano wartość ${a.wartosc} (limit: ${a.limit}).
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>`;
            alarmsContainer.innerHTML += alarmHTML;
        });
    }

    function renderStockSummary(summaryData) {
        stockSummaryContainer.innerHTML = '';
        if (!summaryData || summaryData.length === 0) {
            stockSummaryContainer.innerHTML = '<p class="text-muted">Brak surowców w magazynach.</p>';
            return;
        }

        let tableHTML = `
            <table class="table table-hover stock-summary-table">
                <thead>
                    <tr class="table-dark">
                        <th class="align-middle" style="width: 35%;">
                            <i class="fas fa-flask me-2 text-white"></i>
                            <span class="text-white">Typ Surowca</span>
                        </th>
                        <th class="text-center bg-danger bg-opacity-25" style="width: 16.25%;">
                            <i class="fas fa-warehouse me-1 text-danger"></i>
                            <div class="text-dark fw-semibold">Strefa Brudna</div>
                            <small class="text-muted">(tony)</small>
                        </th>
                        <th class="text-center" style="width: 16.25%; background-color: rgba(245, 222, 179, 0.4) !important;">
                            <i class="fas fa-industry me-1" style="color: #856404;"></i>
                            <div class="text-dark fw-semibold">W Reaktorach</div>
                            <small class="text-muted">(tony)</small>
                        </th>
                        <th class="text-center bg-success bg-opacity-25" style="width: 16.25%;">
                            <i class="fas fa-check-circle me-1 text-success"></i>
                            <div class="text-dark fw-semibold">Strefa Czysta</div>
                            <small class="text-muted">(tony)</small>
                        </th>
                        <th class="text-center bg-primary bg-opacity-25" style="width: 16.25%;">
                            <i class="fas fa-calculator me-1 text-primary"></i>
                            <div class="text-dark fw-bold">SUMA</div>
                            <small class="text-muted">(tony)</small>
                        </th>
                    </tr>
                </thead>
                <tbody>
        `;

        summaryData.sort((a, b) => a.material_type.localeCompare(b.material_type));

        let totalDirty = 0;
        let totalClean = 0;
        let totalReactors = 0;
        let grandTotal = 0;

        summaryData.forEach((item, index) => {
            const dirtyTonnes = (item.dirty_stock_kg || 0) / 1000;
            const cleanTonnes = (item.clean_stock_kg || 0) / 1000;
            const reactorsTonnes = (item.reactors_stock_kg || 0) / 1000;
            const rowTotal = dirtyTonnes + cleanTonnes + reactorsTonnes;

            totalDirty += dirtyTonnes;
            totalClean += cleanTonnes;
            totalReactors += reactorsTonnes;
            grandTotal += rowTotal;

            // Oblicz procenty dla progress bara
            const dirtyPercent = rowTotal > 0 ? (dirtyTonnes / rowTotal * 100) : 0;
            const reactorsPercent = rowTotal > 0 ? (reactorsTonnes / rowTotal * 100) : 0;
            const cleanPercent = rowTotal > 0 ? (cleanTonnes / rowTotal * 100) : 0;

            const rowClass = index % 2 === 0 ? 'table-row-even' : 'table-row-odd';
            const rowBgColor = index % 2 === 0 ? 'background-color: rgba(0, 0, 0, 0.03);' : 'background-color: white;';

            tableHTML += `
                <tr class="${rowClass}" style="${rowBgColor}">
                    <td class="align-middle">
                        <div class="d-flex align-items-center justify-content-between">
                            <span class="badge fs-5 py-2 px-3 me-3" style="min-width: 80px; background-color: #f5deb3; color: #856404; font-weight: 600;">${item.material_type}</span>
                            <div class="progress" style="height: 10px; width: 200px;">
                                <div class="progress-bar" style="width: ${dirtyPercent}%; background-color: #dc3545;" title="Brudna: ${dirtyPercent.toFixed(1)}%"></div>
                                <div class="progress-bar" style="width: ${reactorsPercent}%; background-color: #f5deb3;" title="Reaktory: ${reactorsPercent.toFixed(1)}%"></div>
                                <div class="progress-bar" style="width: ${cleanPercent}%; background-color: #28a745;" title="Czysta: ${cleanPercent.toFixed(1)}%"></div>
                            </div>
                        </div>
                    </td>
                    <td class="text-center bg-danger bg-opacity-10 align-middle">
                        <span class="fs-5 fw-bold text-danger">${dirtyTonnes.toFixed(0)}</span>
                    </td>
                    <td class="text-center align-middle" style="background-color: rgba(245, 222, 179, 0.25);">
                        <span class="fs-5 fw-bold" style="color: #856404;">${reactorsTonnes.toFixed(0)}</span>
                    </td>
                    <td class="text-center bg-success bg-opacity-10 align-middle">
                        <span class="fs-5 fw-bold text-success">${cleanTonnes.toFixed(0)}</span>
                    </td>
                    <td class="text-center bg-primary bg-opacity-10 align-middle">
                        <span class="fs-4 fw-bold text-primary">${rowTotal.toFixed(0)}</span>
                    </td>
                </tr>
            `;
        });

        // Oblicz procenty dla wiersza sum
        const totalDirtyPercent = grandTotal > 0 ? (totalDirty / grandTotal * 100) : 0;
        const totalReactorsPercent = grandTotal > 0 ? (totalReactors / grandTotal * 100) : 0;
        const totalCleanPercent = grandTotal > 0 ? (totalClean / grandTotal * 100) : 0;

        tableHTML += `
                </tbody>
                <tfoot>
                    <tr class="table-dark border-top border-3">
                        <td class="align-middle py-3">
                            <div class="d-flex align-items-center justify-content-between">
                                <div class="d-flex align-items-center">
                                    <i class="fas fa-chart-pie me-2 fs-5 text-white"></i>
                                    <strong class="fs-5 text-white">SUMA CAŁKOWITA</strong>
                                </div>
                                <div class="progress" style="height: 12px; width: 200px;">
                                    <div class="progress-bar" style="width: ${totalDirtyPercent}%; background-color: #dc3545;" title="Brudna: ${totalDirtyPercent.toFixed(1)}%"></div>
                                    <div class="progress-bar" style="width: ${totalReactorsPercent}%; background-color: #f5deb3;" title="Reaktory: ${totalReactorsPercent.toFixed(1)}%"></div>
                                    <div class="progress-bar" style="width: ${totalCleanPercent}%; background-color: #28a745;" title="Czysta: ${totalCleanPercent.toFixed(1)}%"></div>
                                </div>
                            </div>
                        </td>
                        <td class="text-center text-white py-3" style="background-color: #dc3545;">
                            <div class="fs-4 fw-bold">${totalDirty.toFixed(0)}</div>
                            <small>${totalDirtyPercent.toFixed(1)}%</small>
                        </td>
                        <td class="text-center py-3" style="background-color: #d4a574;">
                            <div class="fs-4 fw-bold" style="color: #4a2f0f;">${totalReactors.toFixed(0)}</div>
                            <small style="color: #4a2f0f;">${totalReactorsPercent.toFixed(1)}%</small>
                        </td>
                        <td class="text-center bg-success text-white py-3">
                            <div class="fs-4 fw-bold">${totalClean.toFixed(0)}</div>
                            <small>${totalCleanPercent.toFixed(1)}%</small>
                        </td>
                        <td class="text-center bg-primary text-white py-3">
                            <div class="fs-3 fw-bold">${grandTotal.toFixed(0)}</div>
                            <small>100%</small>
                        </td>
                    </tr>
                </tfoot>
            </table>
        `;
        stockSummaryContainer.innerHTML = tableHTML;
    }

    // NOWA FUNKCJA: Renderowanie logu aktywnych operacji
    function renderActiveOperations(operations) {
        activeOperationsContainer.innerHTML = '';
        if (!operations || operations.length === 0) {
            activeOperationsContainer.innerHTML = '<div class="list-group-item"><p class="text-muted mb-0">Brak aktywnych operacji.</p></div>';
            return;
        }

        operations.forEach(op => {
            const startTime = new Date(op.czas_rozpoczecia);
            const timeSince = Math.round((new Date() - startTime) / 1000 / 60); // minuty temu
            const typ = (op.typ_operacji || '').toString().trim();
            const canContinueToPrzelew = typ === 'FILTRACJA_PLACEK_KOLO' || typ === 'FILTRACJA_WYDMUCH';
            const canContinueToKolo = typ === 'FILTRACJA_PRZELEW' || typ === 'FILTRACJA_PLACEK_PRZELEW' || typ === 'FILTRACJA_NA_PLACKU';
            const canContinueToOcena = typ === 'FILTRACJA_KOLO';
            const canContinueToMagazyn = typ === 'FILTRACJA_KOLO_ZATWIERDZONA';
            const canContinueToDmuchanie =
                typ === 'NA_MAGAZYN' ||
                typ === 'FILTRACJA_KOLO_DO_PONOWNEJ' ||
                (op.opis && (String(op.opis).indexOf('NA_MAGAZYN') === 0 || String(op.opis).indexOf('FILTRACJA_KOLO_DO_PONOWNEJ') === 0));
            const isDmuchanie = typ === 'DMUCHANIE' || (op.opis && String(op.opis).indexOf('DMUCHANIE:') === 0);
            const isDmuchanieCzyszczenie = typ === 'DMUCHANIE_CZYSZCZENIE';
            const isDmuchanieRurociagu = typ === 'DMUCHANIE_RUROCIAGU';
            let continueBtn = '';
            let changeDestBtn = '';
            if (canContinueToPrzelew) {
                continueBtn = `<button type="button" class="btn btn-sm btn-outline-primary continue-to-przelew-btn" data-op-id="${op.id}" data-zrodlo="${(op.zrodlo || '').replace(/"/g, '&quot;')}" title="Zakończ ten etap i rozpocznij FILTRACJA_PRZELEW (wybór reaktora docelowego)">
                        <i class="fas fa-forward me-1"></i>Następny etap (FILTRACJA_PRZELEW)
                    </button>`;
            } else if (canContinueToKolo) {
                continueBtn = `<button type="button" class="btn btn-sm btn-outline-primary continue-to-kolo-btn" data-op-id="${op.id}" title="Zakończ ten etap i rozpocznij FILTRACJA_KOLO">
                        <i class="fas fa-forward me-1"></i>Następny etap (FILTRACJA_KOLO)
                    </button>`;
            } else if (canContinueToOcena) {
                continueBtn = `<button type="button" class="btn btn-sm btn-outline-primary continue-to-ocena-btn" data-op-id="${op.id}" title="Ocena próbki – wynik OK lub do ponownej filtracji">
                        <i class="fas fa-vial me-1"></i>Następny etap (Ocena próbki)
                    </button>`;
            } else if (canContinueToMagazyn) {
                continueBtn = `<button type="button" class="btn btn-sm btn-outline-success continue-to-magazyn-btn" data-op-id="${op.id}" title="Wybierz beczkę czystą i przelej na magazyn (operacja pozostanie aktywna)">
                        <i class="fas fa-warehouse me-1"></i>Następny etap (NA_MAGAZYN)
                    </button>`;
            } else if (canContinueToDmuchanie) {
                continueBtn = `<button type="button" class="btn btn-sm btn-outline-secondary continue-to-dmuchanie-btn"
                        data-op-id="${op.id}"
                        data-zrodlo-nazwa="${(op.zrodlo || '').replace(/"/g, '&quot;')}"
                        data-id-zrodla="${op.id_sprzetu_zrodlowego || ''}"
                        title="Wybierz rodzaj dmuchania i cel">
                        <i class="fas fa-wind me-1"></i>Przejdź do DMUCHANIE
                    </button>`;
            }
            if (isDmuchanie) {
                const zrodloAttr = `data-zrodlo-nazwa="${(op.zrodlo || '').replace(/"/g, '&quot;')}" data-id-zrodla="${op.id_sprzetu_zrodlowego || ''}"`;
                changeDestBtn = `<button type="button" class="btn btn-sm btn-outline-primary dmuchanie-change-dest-btn" data-op-id="${op.id}" title="Zmień cel operacji i wyznacz nową trasę">
                        <i class="fas fa-route me-1"></i>Zmień cel
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-warning konwersja-dmuchanie-btn" data-op-id="${op.id}" ${zrodloAttr} title="Przekształć DMUCHANIE na DMUCHANIE_CZYSZCZENIE z wyborem celu i wpływem na mix">
                        <i class="fas fa-exchange-alt me-1"></i>Zmień na czyszczenie
                    </button>`;
            }

            // Dedykowane przyciski "Zakończ" dla typów z własną logiką finish
            let endBtn = '';
            if (isDmuchanieCzyszczenie) {
                endBtn = `<button type="button" class="btn btn-sm btn-outline-warning finish-dmuchanie-czyszczenie-btn" data-op-id="${op.id}" title="Zakończ czyszczenie filtra – utworzy partię W-P-... i oznaczy mix jako wydmuch">
                        <i class="fas fa-check-circle me-1"></i>Zakończ czyszczenie
                    </button>`;
            } else if (isDmuchanieRurociagu) {
                endBtn = `<button type="button" class="btn btn-sm btn-outline-secondary finish-dmuchanie-rurociagu-btn" data-op-id="${op.id}" title="Zakończ dmuchanie rurociągu – zwolni trasę">
                        <i class="fas fa-check-circle me-1"></i>Zakończ rurociąg
                    </button>`;
            } else {
                endBtn = `<button type="button" class="btn btn-sm btn-outline-danger end-operation-btn" data-op-id="${op.id}" title="Zakończ operację">
                        <i class="fas fa-stop-circle me-1"></i>Zakończ
                    </button>`;
            }

            const itemHTML = `
                <div class="list-group-item d-flex justify-content-between align-items-center flex-wrap gap-2">
                    <div class="flex-grow-1">
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1 text-info">${op.opis}</h6>
                            <small class="text-muted">${timeSince} min temu</small>
                        </div>
                        <p class="mb-0 small">
                            <span class="badge bg-secondary">${op.zrodlo}</span>
                            <i class="fas fa-long-arrow-alt-right mx-2"></i>
                            <span class="badge bg-success">${op.cel}</span>
                        </p>
                    </div>
                    <div class="d-flex gap-1">
                        ${continueBtn}
                        ${changeDestBtn}
                        ${endBtn}
                    </div>
                </div>`;
            activeOperationsContainer.innerHTML += itemHTML;
        });
    }

    // --- OBSŁUGA ZDARZEŃ ---
    if (!reaktoryContainer) {
        if (console && console.error) {
            console.error('reaktoryContainer nie został znaleziony!');
        }
        return;
    }
    
    reaktoryContainer.addEventListener('click', (e) => {
        if (console && console.log) {
            console.log('Kliknięto w reaktoryContainer:', e.target);
        }
        const targetElement = e.target.closest('.action-btn');
        if (console && console.log) {
            console.log('Znaleziony targetElement:', targetElement);
        }
        if (!targetElement) return;
        
        const action = targetElement.dataset.action;
        const sprzetId = targetElement.dataset.sprzetId;
        const sprzetNazwa = targetElement.dataset.sprzetNazwa;
        
        if (console && console.log) {
            console.log(`Action: ${action}, SprzetId: ${sprzetId}, SprzetNazwa: ${sprzetNazwa}`);
        }

        if (action === 'show-details') {
            handleShowDetails(sprzetId, sprzetNazwa);
        } else if (action === 'toggle-burner') {
            const isChecked = targetElement.checked;
            const newState = isChecked ? 'WLACZONY' : 'WYLACZONY';
            handleToggleBurner(sprzetId, newState);
        } else if (action === 'open-simulation-settings') {
            handleOpenSimulationSettings(sprzetId, sprzetNazwa);
        } else if (action === 'open-transfer-modal') { // NOWA AKCJA
            const wagaPartii = targetElement.dataset.partiaWaga;
            handleOpenTransferModal(sprzetId, sprzetNazwa, wagaPartii);
        } else if (action === 'open-start-filtration-modal') {
            const mixId = targetElement.dataset.mixId;
            handleOpenStartFiltrationModal(mixId, sprzetNazwa, sprzetId);
        } else if (action === 'open-filtracja-na-placku-modal') {
            const idZrodla = sprzetId;
            document.getElementById('filtracja-na-placku-id-zrodla').value = idZrodla;
            document.getElementById('filtracja-na-placku-zrodlo-name').textContent = sprzetNazwa || '—';
            document.getElementById('filtracja-na-placku-error').classList.add('d-none');
            const container = document.getElementById('filtracja-na-placku-destinations-container');
            container.innerHTML = '<div class="list-group-item text-muted">Ładowanie celów (puste, z możliwą trasą)...</div>';
            modals.filtracjaNaPlacku.show();
            fetch(`/api/operations/filtracja-na-placku-destinations?id_sprzetu_zrodlowego=${idZrodla}`)
                .then(res => res.ok ? res.json() : Promise.reject(new Error('Błąd ładowania')))
                .then(data => {
                    const destinations = data.destinations || [];
                    container.innerHTML = '';
                    if (destinations.length === 0) {
                        container.innerHTML = '<p class="text-muted mb-0 p-2">Brak pustych reaktorów z możliwą trasą przelewu (źródło → filtr → cel).</p>';
                        return;
                    }
                    destinations.forEach((item, index) => {
                        const radioId = `fnp-dest-${item.id}`;
                        const label = document.createElement('label');
                        label.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
                        label.setAttribute('for', radioId);
                        label.innerHTML = `<span><input class="form-check-input me-2" type="radio" name="fnp-destination" value="${item.id}" id="${radioId}" ${index === 0 ? 'checked' : ''}> ${item.nazwa_unikalna || item.id}</span><span class="badge bg-success">Pusty</span>`;
                        container.appendChild(label);
                    });
                })
                .catch(() => {
                    container.innerHTML = '<p class="text-danger mb-0 p-2">Nie udało się załadować listy reaktorów.</p>';
                });
        } else if (action === 'open-dobielanie-modal') {
            const mixId = targetElement.dataset.mixId;
            document.getElementById('dobielanie-mix-id').value = mixId || '';
            document.getElementById('dobielanie-reaktor-name').textContent = sprzetNazwa || '—';
            document.getElementById('dobielanie-bags').value = 6;
            document.getElementById('dobielanie-weight').value = 25;
            document.getElementById('dobielanie-error').classList.add('d-none');
            modals.dobielanie.show();
        }
    });

    // Ujednolicona obsługa kliknięć dla obu typów beczek
    const handleTankClick = (e) => {
        const button = e.target.closest('.action-btn');
        if (!button) return;
    
        const action = button.dataset.action;
        if (action === 'open-transfer-modal') {
            const sprzetId = button.dataset.sprzetId;
            const sprzetNazwa = button.dataset.sprzetNazwa;
            const wagaPartii = button.dataset.partiaWaga;
            handleOpenTransferModal(sprzetId, sprzetNazwa, wagaPartii);
        }
    };
    
    beczkiBrudneContainer.addEventListener('click', handleTankClick);
    beczkiCzysteContainer.addEventListener('click', handleTankClick);

    // Zakończ operację – klik w przycisk w Logu Aktywnych Operacji
    activeOperationsContainer.addEventListener('click', async (e) => {
        const endBtn = e.target.closest('.end-operation-btn');
        const continueKoloBtn = e.target.closest('.continue-to-kolo-btn');
        const continueOcenaBtn = e.target.closest('.continue-to-ocena-btn');
        const continueMagazynBtn = e.target.closest('.continue-to-magazyn-btn');

        if (continueOcenaBtn) {
            e.preventDefault();
            const opId = continueOcenaBtn.getAttribute('data-op-id');
            if (!opId) return;
            document.getElementById('ocena-probki-id-operacji').value = opId;
            document.querySelector('#ocena-ok').checked = true;
            document.getElementById('ocena-powod').value = '';
            document.getElementById('ocena-powod-wrap').classList.add('d-none');
            document.getElementById('ocena-probki-error').classList.add('d-none');
            modals.ocenaProbki.show();
            return;
        }
        const continuePrzelewBtn = e.target.closest('.continue-to-przelew-btn');
        if (continuePrzelewBtn) {
            e.preventDefault();
            const opId = continuePrzelewBtn.getAttribute('data-op-id');
            const zrodlo = continuePrzelewBtn.getAttribute('data-zrodlo') || '';
            if (!opId) return;
            document.getElementById('przelew-dest-id-operacji').value = opId;
            document.getElementById('przelew-dest-zrodlo-name').textContent = zrodlo || '—';
            document.getElementById('przelew-dest-error').classList.add('d-none');
            const container = document.getElementById('przelew-dest-container');
            container.innerHTML = '<div class="list-group-item text-muted">Ładowanie celów (puste, z możliwą trasą)...</div>';
            modals.przelewDest.show();
            fetch(`/api/operations/przelew-destinations?id_operacji=${opId}`)
                .then(res => res.ok ? res.json() : Promise.reject(new Error('Błąd ładowania')))
                .then(data => {
                    const destinations = data.destinations || [];
                    container.innerHTML = '';
                    if (destinations.length === 0) {
                        container.innerHTML = '<p class="text-muted mb-0">Brak pustych reaktorów z możliwą trasą przelewu (źródło → filtr → cel).</p>';
                        return;
                    }
                    destinations.forEach((item, index) => {
                        const radioId = `przelew-dest-${item.id}`;
                        const label = document.createElement('label');
                        label.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
                        label.setAttribute('for', radioId);
                        label.innerHTML = `<span><input class="form-check-input me-2" type="radio" name="przelew-dest-reaktor" value="${item.id}" id="${radioId}" data-nazwa="${(item.nazwa_unikalna || '').replace(/"/g, '&quot;')}" ${index === 0 ? 'checked' : ''}> ${item.nazwa_unikalna || item.id}</span><span class="badge bg-success">Pusty</span>`;
                        container.appendChild(label);
                    });
                })
                .catch(() => {
                    container.innerHTML = '<p class="text-danger mb-0">Nie udało się załadować listy celów.</p>';
                });
            return;
        }
        if (continueMagazynBtn) {
            e.preventDefault();
            const opId = continueMagazynBtn.getAttribute('data-op-id');
            if (!opId) return;
            document.getElementById('na-magazyn-id-operacji').value = opId;
            document.getElementById('na-magazyn-error').classList.add('d-none');
            const container = document.getElementById('na-magazyn-destinations-container');
            const beczkiCzyste = (latestDashboardData && latestDashboardData.beczki_czyste) ? latestDashboardData.beczki_czyste : [];
            container.innerHTML = '';
            if (beczkiCzyste.length === 0) {
                container.innerHTML = '<p class="text-muted mb-0">Brak beczek czystych w systemie.</p>';
            } else {
                beczkiCzyste.forEach((b, index) => {
                    let zawartosc = 'Pusty';
                    if (b.partia && b.partia.sklad && b.partia.sklad.length > 0) {
                        const wagaTon = b.partia.waga_kg ? (b.partia.waga_kg / 1000).toFixed(2) : '0';
                        const types = b.partia.sklad.map(c => c.material_type || c).join(', ');
                        zawartosc = `${wagaTon} t, ${types}`;
                    } else if (b.partia && b.partia.waga_kg > 0.01) {
                        zawartosc = (b.partia.waga_kg / 1000).toFixed(2) + ' t';
                    }
                    const radioId = `na-magazyn-dest-${b.id}`;
                    const label = document.createElement('label');
                    label.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-start';
                    label.setAttribute('for', radioId);
                    label.innerHTML = `<span class="me-2"><input class="form-check-input" type="radio" name="na-magazyn-destination" value="${b.id}" id="${radioId}" ${index === 0 ? 'checked' : ''}></span><span class="flex-grow-1"><strong>${b.nazwa || b.id}</strong><br><small class="text-muted">${zawartosc}</small></span>`;
                    container.appendChild(label);
                });
            }
            modals.naMagazyn.show();
            return;
        }
        const continueDmuchanieBtn = e.target.closest('.continue-to-dmuchanie-btn');
        if (continueDmuchanieBtn) {
            e.preventDefault();
            const opId = continueDmuchanieBtn.getAttribute('data-op-id');
            const zrodloNazwa = continueDmuchanieBtn.getAttribute('data-zrodlo-nazwa') || '—';
            const idZrodla = continueDmuchanieBtn.getAttribute('data-id-zrodla') || '';
            if (!opId) return;
            // Otwórz modal wyboru rodzaju dmuchania
            document.getElementById('wybor-dmuchania-id-operacji').value = opId;
            document.getElementById('wybor-dmuchania-id-zrodla').value = idZrodla;
            document.getElementById('wybor-dmuchania-mode').value = 'continue';
            document.getElementById('wybor-dmuchania-zrodlo-info').textContent = zrodloNazwa;
            document.getElementById('dmuchanie-typ-standard').checked = true;
            // Pokaż/ukryj wybór rodzaju (w trybie continue jest dostępny)
            document.getElementById('wybor-dmuchania-cel-wrap').style.display = 'none';
            document.querySelectorAll('.wybor-dmuchania-typ-wrap').forEach(el => el.style.display = '');
            document.getElementById('wybor-dmuchania-error').classList.add('d-none');
            // Wypełnij select celu tylko reaktorami
            fillReaktoryCelSelect('wybor-dmuchania-cel');
            modals.wyborDmuchania.show();
            return;
        }
        const dmuchanieChangeDestBtn = e.target.closest('.dmuchanie-change-dest-btn');
        if (dmuchanieChangeDestBtn) {
            e.preventDefault();
            const opId = dmuchanieChangeDestBtn.getAttribute('data-op-id');
            if (!opId) return;
            document.getElementById('dmuchanie-change-dest-id-operacji').value = opId;
            document.getElementById('dmuchanie-change-dest-error').classList.add('d-none');
            const container = document.getElementById('dmuchanie-change-dest-container');
            container.innerHTML = '<div class="list-group-item text-muted">Ładowanie celów...</div>';
            modals.dmuchanieChangeDest.show();
            fetch(`/api/operations/dmuchanie-destinations?id_operacji=${opId}`)
                .then(res => res.ok ? res.json() : Promise.reject(new Error('Błąd ładowania')))
                .then(data => {
                    const destinations = data.destinations || [];
                    container.innerHTML = '';
                    if (destinations.length === 0) {
                        container.innerHTML = '<p class="text-muted mb-0">Brak celów z możliwą trasą.</p>';
                        return;
                    }
                    destinations.forEach((item, index) => {
                        const radioId = `dmuchanie-dest-${item.id}`;
                        const typBadge = item.typ_sprzetu === 'beczka_czysta' ? 'beczka czysta' : 'reaktor';
                        const label = document.createElement('label');
                        label.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
                        label.setAttribute('for', radioId);
                        label.innerHTML = `<span><input class="form-check-input me-2" type="radio" name="dmuchanie-change-dest" value="${item.id}" id="${radioId}" data-nazwa="${(item.nazwa_unikalna || '').replace(/"/g, '&quot;')}" ${index === 0 ? 'checked' : ''}> ${item.nazwa_unikalna || item.id}</span><span class="badge bg-secondary">${typBadge}</span>`;
                        container.appendChild(label);
                    });
                })
                .catch(() => {
                    container.innerHTML = '<p class="text-danger mb-0">Nie udało się załadować listy celów.</p>';
                });
            return;
        }
        const konwersjaDmuchanieBtn = e.target.closest('.konwersja-dmuchanie-btn');
        if (konwersjaDmuchanieBtn) {
            e.preventDefault();
            const opId = konwersjaDmuchanieBtn.getAttribute('data-op-id');
            const zrodloNazwa = konwersjaDmuchanieBtn.getAttribute('data-zrodlo-nazwa') || '—';
            const idZrodla = konwersjaDmuchanieBtn.getAttribute('data-id-zrodla') || '';
            if (!opId) return;
            document.getElementById('wybor-dmuchania-id-operacji').value = opId;
            document.getElementById('wybor-dmuchania-id-zrodla').value = idZrodla;
            document.getElementById('wybor-dmuchania-mode').value = 'convert';
            document.getElementById('wybor-dmuchania-zrodlo-info').textContent = zrodloNazwa;
            // Tryb konwersji: ukryj radio (zawsze DMUCHANIE_CZYSZCZENIE), pokaż cel
            document.querySelectorAll('.wybor-dmuchania-typ-wrap').forEach(el => el.style.display = 'none');
            document.getElementById('dmuchanie-typ-czyszczenie').checked = true;
            document.getElementById('wybor-dmuchania-cel-wrap').style.display = '';
            document.getElementById('wybor-dmuchania-error').classList.add('d-none');
            // Załaduj cele (reaktory z trasą od filtra poprzedniej operacji) z API – id_operacji dla filtra z segmentów
            const celSelect = document.getElementById('wybor-dmuchania-cel');
            if (celSelect && opId) {
                celSelect.innerHTML = '<option value="">Ładowanie celów...</option>';
                celSelect.disabled = true;
                fetch(`/api/operations/dmuchanie-czyszczenie-destinations?id_operacji=${opId}`)
                    .then(res => res.ok ? res.json() : { destinations: [] })
                    .then(data => {
                        const destinations = data.destinations || [];
                        celSelect.innerHTML = '<option value="">-- wybierz reaktor --</option>';
                        destinations.forEach(d => {
                            const opt = document.createElement('option');
                            opt.value = d.id;
                            opt.textContent = (d.nazwa_unikalna || d.id) + (d.material_types_text ? ` (${d.material_types_text})` : '');
                            celSelect.appendChild(opt);
                        });
                        if (destinations.length === 0) {
                            celSelect.innerHTML = '<option value="">Brak reaktorów z możliwą trasą od filtra</option>';
                        }
                        celSelect.disabled = false;
                    })
                    .catch(() => {
                        celSelect.innerHTML = '<option value="">Błąd ładowania</option>';
                        celSelect.disabled = false;
                    });
            } else {
                fillReaktoryCelSelect('wybor-dmuchania-cel');
            }
            modals.wyborDmuchania.show();
            return;
        }
        const finishCzyszczenieBtn = e.target.closest('.finish-dmuchanie-czyszczenie-btn');
        if (finishCzyszczenieBtn) {
            e.preventDefault();
            const opId = finishCzyszczenieBtn.getAttribute('data-op-id');
            if (!opId) return;
            finishCzyszczenieBtn.disabled = true;
            finishCzyszczenieBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Oczekuj...';
            try {
                const response = await fetch('/api/operations/finish-dmuchanie-czyszczenie', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id_operacji: parseInt(opId, 10), operator: 'GUI' })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || result.error || 'Błąd serwera');
                showToast(result.message || 'DMUCHANIE_CZYSZCZENIE zakończone.', 'success');
                initialLoad();
            } catch (err) {
                console.error('Błąd finish-dmuchanie-czyszczenie:', err);
                showToast(err.message, 'error');
                finishCzyszczenieBtn.disabled = false;
                finishCzyszczenieBtn.innerHTML = '<i class="fas fa-check-circle me-1"></i>Zakończ czyszczenie';
            }
            return;
        }
        const finishRurociaguBtn = e.target.closest('.finish-dmuchanie-rurociagu-btn');
        if (finishRurociaguBtn) {
            e.preventDefault();
            const opId = finishRurociaguBtn.getAttribute('data-op-id');
            if (!opId) return;
            finishRurociaguBtn.disabled = true;
            finishRurociaguBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Oczekuj...';
            try {
                const response = await fetch('/api/operations/finish-dmuchanie-rurociagu', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id_operacji: parseInt(opId, 10), operator: 'GUI' })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || result.error || 'Błąd serwera');
                showToast(result.message || 'DMUCHANIE_RUROCIAGU zakończone.', 'success');
                initialLoad();
            } catch (err) {
                console.error('Błąd finish-dmuchanie-rurociagu:', err);
                showToast(err.message, 'error');
                finishRurociaguBtn.disabled = false;
                finishRurociaguBtn.innerHTML = '<i class="fas fa-check-circle me-1"></i>Zakończ rurociąg';
            }
            return;
        }
        if (continueKoloBtn) {
            e.preventDefault();
            const opId = continueKoloBtn.getAttribute('data-op-id');
            if (!opId) return;
            continueKoloBtn.disabled = true;
            continueKoloBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Oczekuj...';
            try {
                const response = await fetch('/api/operations/continue-to-kolo', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id_operacji: parseInt(opId, 10) })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || result.error || 'Błąd serwera');
                showToast(result.message || 'Rozpoczęto FILTRACJA_KOLO.', 'success');
                initialLoad();
            } catch (err) {
                console.error('Błąd continue-to-kolo:', err);
                showToast(err.message, 'error');
                continueKoloBtn.disabled = false;
                continueKoloBtn.innerHTML = '<i class="fas fa-forward me-1"></i>Następny etap (FILTRACJA_KOLO)';
            }
            return;
        }
        if (!endBtn) return;
        e.preventDefault();
        const opId = endBtn.getAttribute('data-op-id');
        if (!opId) return;
        endBtn.disabled = true;
        endBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Zakończ';
        try {
            const response = await fetch('/api/operations/zakoncz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id_operacji: parseInt(opId, 10) })
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.message || result.error || 'Błąd serwera');
            }
            showToast(result.message || 'Operacja zakończona.', 'success');
            initialLoad();
        } catch (err) {
            console.error('Błąd zakończenia operacji:', err);
            showToast(err.message, 'error');
            endBtn.disabled = false;
            endBtn.innerHTML = '<i class="fas fa-stop-circle me-1"></i>Zakończ';
        }
    });

    // --- FUNKCJE OBSŁUGUJĄCE AKCJE ---

    // Przeniesiona definicja funkcji, aby zapewnić jej dostępność
    async function handleOpenTransferModal(sourceId, sourceName, wagaPartii) {
        // Ustaw wartości w modalu
        document.getElementById('transfer-source-id').value = sourceId;
        document.getElementById('transfer-source-name').textContent = sourceName;
        // Ustaw domyślną ilość, ale tylko jeśli jest większa od zera
        document.getElementById('transfer-quantity').value = parseFloat(wagaPartii) > 0 ? wagaPartii : '';
        
        const destinationSelect = document.getElementById('transfer-destination-id');
        destinationSelect.innerHTML = '<option>Ładowanie celów...</option>';
        destinationSelect.disabled = true;

        modals.transferTankToTank.show();

        try {
            const response = await fetch('/api/sprzet/dostepne-cele');
            if (!response.ok) throw new Error('Błąd ładowania listy celów');
            
            const destinations = await response.json();
            
            destinationSelect.innerHTML = '<option value="">-- Wybierz cel --</option>';

            // Grupuj cele
            const groupedDestinations = destinations.reduce((acc, dest) => {
                // Nie pokazuj samego siebie jako celu
                if (dest.id.toString() === sourceId.toString()) {
                    return acc;
                }
                const type = dest.typ_sprzetu;
                if (!acc[type]) {
                    acc[type] = [];
                }
                acc[type].push(dest);
                return acc;
            }, {});
            
            // Renderuj opcje
            for (const type in groupedDestinations) {
                const optgroup = document.createElement('optgroup');
                optgroup.label = type;
                groupedDestinations[type].forEach(dest => {
                    const option = document.createElement('option');
                    option.value = dest.id;
                    
                    let label = dest.nazwa_unikalna;
                    if (dest.mix_info && dest.mix_info.total_weight > 0.01) {
                        const waga_w_tonach = (dest.mix_info.total_weight / 1000).toFixed(2);
                        const materialTypes = dest.mix_info.components.map(c => c.material_type).join(', ');
                        label += ` (${waga_w_tonach} t, ${materialTypes})`;
                    } else {
                        label += ` (Pusty)`;
                    }
                    option.textContent = label;

                    optgroup.appendChild(option);
                });
                destinationSelect.appendChild(optgroup);
            }

            destinationSelect.disabled = false;

        } catch (error) {
            console.error(error);
            destinationSelect.innerHTML = `<option value="">Błąd: ${error.message}</option>`;
            showToast(error.message, 'error');
        }
    }
    
    function handleShowDetails(id, nazwa) {
        window.location.href = `/sprzet/${id}/details`;
    }

    async function handleToggleBurner(id, newState) {
        if (console && console.log) {
            console.log(`Wysyłanie żądania zmiany stanu palnika dla ID ${id} na ${newState}`);
        }
        try {
            const response = await fetch(`/api/sprzet/${id}/palnik`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newState })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Wystąpił nieznany błąd');
        } catch (error) {
            if (console && console.error) {
                console.error('Błąd podczas zmiany stanu palnika:', error);
            }
            window.location.reload();
        }
    }



    function handlePlanTransfer(sourceId, sourceName) {
        document.getElementById('plan-transfer-source-id').value = sourceId;
        document.getElementById('plan-transfer-source-name').textContent = sourceName;
        const container = document.getElementById('plan-transfer-destinations-container');
        container.innerHTML = '<p>Ładowanie...</p>';
        const pusteReaktory = Array.from(pusteReaktoryContainer.querySelectorAll('.badge'));
        if (pusteReaktory.length > 0) {
            container.innerHTML = '';
            pusteReaktory.forEach((badge, index) => {
                const nazwa = badge.textContent;
                container.innerHTML += `
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="destination-reactor" 
                               value="${nazwa}" id="dest-${nazwa}" ${index === 0 ? 'checked' : ''}>
                        <label class="form-check-label" for="dest-${nazwa}">${nazwa}</label>
                    </div>`;
            });
        } else {
            container.innerHTML = '<p class="text-danger">Brak wolnych reaktorów!</p>';
        }
        modals.planTransfer.show();
    }

    function handleStartHeating(id, nazwa) {
        document.getElementById('start-heating-sprzet-id').value = id;
        document.getElementById('start-heating-sprzet-name').textContent = nazwa;
        forms.startHeating.reset();
        modals.startHeating.show();
    }

    async function handleOpenStartFiltrationModal(mixId, reaktorNazwa, idReaktoraZrodlowego) {
        document.getElementById('start-filtration-mix-id').value = mixId;
        document.getElementById('start-filtration-reaktor-name').textContent = reaktorNazwa;
        document.getElementById('start-filtration-reaktor-nazwa').value = reaktorNazwa;
        const container = document.getElementById('start-filtration-destinations-container');
        container.innerHTML = '<div class="list-group-item text-muted">Ładowanie celów...</div>';
        document.getElementById('start-filtration-error').classList.add('d-none');
        modals.startFiltration.show();

        if (!idReaktoraZrodlowego) {
            container.innerHTML = '<p class="text-danger mb-0">Brak reaktora źródłowego.</p>';
            return;
        }
        try {
            const response = await fetch(`/api/operations/start-filtration-destinations?id_reaktora_zrodlowego=${idReaktoraZrodlowego}`);
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.message || 'Błąd ładowania listy celów');
            }
            const data = await response.json();
            const destinations = data.destinations || [];
            container.innerHTML = '';
            if (destinations.length === 0) {
                container.innerHTML = '<p class="text-muted mb-0">Brak celów z możliwą trasą (tylko puste reaktory z trasą Pathfinder).</p>';
                return;
            }
            destinations.forEach((item, index) => {
                const title = item.is_same_reactor ? `${item.nazwa_unikalna} (koło)` : item.nazwa_unikalna;
                const subtitle = item.is_same_reactor ? 'Ten sam reaktor' : 'Pusty';
                const labelContent = `<div class="d-flex w-100 justify-content-between"><h6 class="mb-1">${title}</h6><small class="text-muted">${subtitle}</small></div>`;
                const radioId = `start-filtration-dest-${item.id}`;
                const label = document.createElement('label');
                label.htmlFor = radioId;
                label.className = 'list-group-item list-group-item-action';
                label.innerHTML = `<input class="form-check-input me-2" type="radio" name="start-filtration-destination" value="${item.id}" id="${radioId}" data-nazwa="${item.nazwa_unikalna}" ${index === 0 ? 'checked' : ''}>${labelContent}`;
                container.appendChild(label);
            });
        } catch (error) {
            console.error('Błąd ładowania celów filtracji:', error);
            container.innerHTML = '<p class="text-danger mb-0">' + (error.message || 'Nie udało się załadować listy reaktorów.') + '</p>';
        }
    }

    // --- OBSŁUGA FORMULARZY ---
    forms.startHeating.addEventListener('submit', async (e) => {
        e.preventDefault();
        const sprzetId = document.getElementById('start-heating-sprzet-id').value;
        const temp = document.getElementById('start-heating-temp').value;

        try {
            const response = await fetch(`/api/sprzet/${sprzetId}/rozpocznij-podgrzewanie`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ start_temperature: temp })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error);

            showToast(`Rozpoczęto podgrzewanie. Szacowany czas: ${Math.round(result.data.estimated_minutes_remaining)} min.`);
            modals.startHeating.hide();
        } catch (error) {
            showToast(error.message, 'error');
        }
    });

    forms.planTransfer.addEventListener('submit', (e) => {
        e.preventDefault();
        const sourceId = document.getElementById('plan-transfer-source-id').value;
        const destNameInput = document.querySelector('input[name="destination-reactor"]:checked');
        if (!destNameInput) {
            alert("Proszę wybrać reaktor docelowy.");
            return;
        }
        const destName = destNameInput.value;
        alert(`TODO: Rozpocznij transfer z ID ${sourceId} do reaktora o nazwie ${destName}`);
        modals.planTransfer.hide();
    });

    forms.simulationSettings.addEventListener('submit', async (e) => {
        e.preventDefault();
        const sprzetId = document.getElementById('simulation-settings-sprzet-id').value;
        const newHeating = document.getElementById('simulation-heating-speed').value;
        const newCooling = document.getElementById('simulation-cooling-speed').value;
        const newTargetTemp = document.getElementById('simulation-target-temp').value;
        const newCurrentTemp = document.getElementById('simulation-current-temp').value;

        try {
            const response = await fetch(`/api/sprzet/${sprzetId}/simulation-params`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    szybkosc_grzania: newHeating,
                    szybkosc_chlodzenia: newCooling,
                    temperatura_docelowa: newTargetTemp,
                    temperatura_aktualna: newCurrentTemp
                })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Wystąpił nieznany błąd');
            
            showToast('Parametry symulacji zaktualizowane!', 'success');
            modals.simulationSettings.hide();
        } catch (error) {
            console.error('Błąd podczas aktualizacji parametrów symulacji:', error);
            if (window.showToast) {
                showToast(`Błąd: ${error.message}`, 'error');
            } else {
                alert(`Błąd: ${error.message}`);
            }
        }
    });

    // NOWA OBSŁUGA FORMULARZA: Przelej między zbiornikami
    forms.transferTankToTank.addEventListener('submit', async (e) => {
        e.preventDefault();
        const sourceId = document.getElementById('transfer-source-id').value;
        const destinationId = document.getElementById('transfer-destination-id').value;
        const quantity = document.getElementById('transfer-quantity').value;

        if (!destinationId) {
            showToast('Proszę wybrać zbiornik docelowy.', 'error');
            return;
        }

        const payload = {
            source_tank_id: parseInt(sourceId),
            destination_tank_id: parseInt(destinationId),
            quantity_kg: parseFloat(quantity)
        };

        try {
            const response = await fetch('/api/batches/transfer/tank-to-tank', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const result = await response.json();
            if (!response.ok) throw new Error(result.message || 'Błąd serwera');

            showToast(`Transfer z ID ${sourceId} do ID ${destinationId} został pomyślnie zainicjowany.`, 'success');
            modals.transferTankToTank.hide();
        } catch (error) {
            console.error('Błąd podczas transferu:', error);
            showToast(`Błąd transferu: ${error.message}`, 'error');
        }
    });

    // Obsługa formularza Start filtracji (tylko wybór celu; start/cel/zawory/operator – automatycznie)
    if (forms.startFiltration) {
        forms.startFiltration.addEventListener('submit', async (e) => {
            e.preventDefault();
            const mixId = document.getElementById('start-filtration-mix-id').value;
            const reaktorNazwa = document.getElementById('start-filtration-reaktor-nazwa').value.trim();
            const selectedRadio = document.querySelector('input[name="start-filtration-destination"]:checked');
            const errorDiv = document.getElementById('start-filtration-error');

            if (!selectedRadio) {
                errorDiv.textContent = 'Wybierz reaktor docelowy.';
                errorDiv.classList.remove('d-none');
                return;
            }
            errorDiv.classList.add('d-none');
            const celNazwa = selectedRadio.getAttribute('data-nazwa');
            const startPoint = `${reaktorNazwa}_OUT`;
            const endPoint = `${celNazwa}_IN`;

            const payload = { start: startPoint, cel: endPoint };

            try {
                const response = await fetch(`/api/workflow/mix/${mixId}/start-filtration`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || 'Błąd serwera');

                showToast('Filtracja została uruchomiona.', 'success');
                modals.startFiltration.hide();
                initialLoad();
            } catch (error) {
                console.error('Błąd startu filtracji:', error);
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('d-none');
            }
        });
    }

    // Przełączanie widoczności pola "Powód" przy ocenie próbki
    document.querySelectorAll('input[name="ocena-wynik"]').forEach(radio => {
        radio.addEventListener('change', () => {
            const wrap = document.getElementById('ocena-powod-wrap');
            if (document.getElementById('ocena-do-ponownej').checked) {
                wrap.classList.remove('d-none');
            } else {
                wrap.classList.add('d-none');
            }
        });
    });

    // Obsługa formularza wyboru reaktora docelowego dla FILTRACJA_PRZELEW
    if (forms.przelewDest) {
        forms.przelewDest.addEventListener('submit', async (e) => {
            e.preventDefault();
            const idOperacji = document.getElementById('przelew-dest-id-operacji').value;
            const selected = document.querySelector('input[name="przelew-dest-reaktor"]:checked');
            const errorDiv = document.getElementById('przelew-dest-error');
            if (!idOperacji || !selected) {
                errorDiv.textContent = 'Wybierz reaktor docelowy.';
                errorDiv.classList.remove('d-none');
                return;
            }
            const idReaktoraDocelowego = parseInt(selected.value, 10);
            errorDiv.classList.add('d-none');
            try {
                const response = await fetch('/api/operations/continue-to-przelew', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id_operacji: parseInt(idOperacji, 10), id_reaktora_docelowego: idReaktoraDocelowego })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || result.error || 'Błąd serwera');
                showToast(result.message || 'Rozpoczęto FILTRACJA_PRZELEW.', 'success');
                modals.przelewDest.hide();
                initialLoad();
            } catch (error) {
                console.error('Błąd continue-to-przelew:', error);
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('d-none');
            }
        });
    }

    // Obsługa formularza NA_MAGAZYN – wybór beczki czystej, zakończenie etapu i przelew
    if (forms.naMagazyn) {
        forms.naMagazyn.addEventListener('submit', async (e) => {
            e.preventDefault();
            const idOperacji = document.getElementById('na-magazyn-id-operacji').value;
            const selected = document.querySelector('input[name="na-magazyn-destination"]:checked');
            const errorDiv = document.getElementById('na-magazyn-error');
            if (!idOperacji || !selected) {
                errorDiv.textContent = 'Wybierz beczkę czystą (cel przelewu).';
                errorDiv.classList.remove('d-none');
                return;
            }
            const idBeczkiCzystej = parseInt(selected.value, 10);
            errorDiv.classList.add('d-none');
            try {
                const response = await fetch('/api/operations/continue-to-magazyn', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id_operacji: parseInt(idOperacji, 10),
                        id_beczki_czystej: idBeczkiCzystej,
                        operator: 'GUI'
                    })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || result.error || 'Błąd serwera');
                showToast(result.message || 'Mieszanina przelana na magazyn. Operacja aktywna – możesz przejść do DMUCHANIE.', 'success');
                modals.naMagazyn.hide();
                initialLoad();
            } catch (error) {
                console.error('Błąd continue-to-magazyn:', error);
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('d-none');
            }
        });
    }

    // Obsługa formularza DMUCHANIE – zmiana celu
    if (forms.dmuchanieChangeDest) {
        forms.dmuchanieChangeDest.addEventListener('submit', async (e) => {
            e.preventDefault();
            const idOperacji = document.getElementById('dmuchanie-change-dest-id-operacji').value;
            const selected = document.querySelector('input[name="dmuchanie-change-dest"]:checked');
            const errorDiv = document.getElementById('dmuchanie-change-dest-error');
            if (!idOperacji || !selected) {
                errorDiv.textContent = 'Wybierz cel operacji.';
                errorDiv.classList.remove('d-none');
                return;
            }
            const idSprzetuDocelowego = parseInt(selected.value, 10);
            errorDiv.classList.add('d-none');
            try {
                const response = await fetch('/api/operations/dmuchanie-change-destination', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id_operacji: parseInt(idOperacji, 10),
                        id_sprzetu_docelowego: idSprzetuDocelowego,
                        operator: 'GUI'
                    })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || result.error || 'Błąd serwera');
                showToast(result.message || 'Cel operacji DMUCHANIE zaktualizowany.', 'success');
                modals.dmuchanieChangeDest.hide();
                initialLoad();
            } catch (error) {
                console.error('Błąd dmuchanie-change-destination:', error);
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('d-none');
            }
        });
    }

    // -----------------------------------------------------------------------
    // Modal wyboru rodzaju dmuchania (z NA_MAGAZYN / FILTRACJA_KOLO_DO_PONOWNEJ)
    // -----------------------------------------------------------------------
    document.querySelectorAll('input[name="wybor-dmuchania-typ"]').forEach(radio => {
        radio.addEventListener('change', async () => {
            const celWrap = document.getElementById('wybor-dmuchania-cel-wrap');
            const celSelect = document.getElementById('wybor-dmuchania-cel');
            if (celWrap) {
                celWrap.style.display = radio.value === 'DMUCHANIE_CZYSZCZENIE' ? '' : 'none';
            }
            // Gdy wybrano DMUCHANIE_CZYSZCZENIE – załaduj cele (reaktory z trasą od filtra) – id_operacji dla filtra z segmentów
            if (radio.value === 'DMUCHANIE_CZYSZCZENIE' && celSelect) {
                const idOperacji = document.getElementById('wybor-dmuchania-id-operacji').value;
                const idZrodla = document.getElementById('wybor-dmuchania-id-zrodla').value;
                const url = idOperacji
                    ? `/api/operations/dmuchanie-czyszczenie-destinations?id_operacji=${idOperacji}`
                    : idZrodla
                        ? `/api/operations/dmuchanie-czyszczenie-destinations?id_sprzetu_zrodlowego=${idZrodla}`
                        : null;
                if (url) {
                    celSelect.innerHTML = '<option value="">Ładowanie celów...</option>';
                    celSelect.disabled = true;
                    try {
                        const res = await fetch(url);
                        const data = res.ok ? await res.json() : { destinations: [] };
                        const destinations = data.destinations || [];
                        celSelect.innerHTML = '<option value="">-- wybierz reaktor --</option>';
                        destinations.forEach(d => {
                            const opt = document.createElement('option');
                            opt.value = d.id;
                            opt.textContent = (d.nazwa_unikalna || d.id) + (d.material_types_text ? ` (${d.material_types_text})` : '');
                            celSelect.appendChild(opt);
                        });
                        if (destinations.length === 0) {
                            celSelect.innerHTML = '<option value="">Brak reaktorów z możliwą trasą</option>';
                        }
                    } catch {
                        celSelect.innerHTML = '<option value="">Błąd ładowania</option>';
                    }
                    celSelect.disabled = false;
                } else {
                    fillReaktoryCelSelect('wybor-dmuchania-cel');
                }
            }
        });
    });

    if (forms.wyborDmuchania) {
        forms.wyborDmuchania.addEventListener('submit', async (e) => {
            e.preventDefault();
            const idOperacji = document.getElementById('wybor-dmuchania-id-operacji').value;
            const mode = document.getElementById('wybor-dmuchania-mode').value;
            const errorDiv = document.getElementById('wybor-dmuchania-error');
            const selectedTyp = document.querySelector('input[name="wybor-dmuchania-typ"]:checked');
            if (!idOperacji) {
                errorDiv.textContent = 'Brak ID operacji.';
                errorDiv.classList.remove('d-none');
                return;
            }
            errorDiv.classList.add('d-none');

            if (mode === 'convert') {
                // Konwersja aktywnego DMUCHANIE → DMUCHANIE_CZYSZCZENIE
                const idCelu = document.getElementById('wybor-dmuchania-cel').value;
                if (!idCelu) {
                    errorDiv.textContent = 'Wybierz reaktor docelowy.';
                    errorDiv.classList.remove('d-none');
                    return;
                }
                try {
                    const response = await fetch('/api/operations/convert-dmuchanie-to-czyszczenie', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            id_operacji: parseInt(idOperacji, 10),
                            id_sprzetu_docelowego: parseInt(idCelu, 10),
                            operator: 'GUI'
                        })
                    });
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.message || result.error || 'Błąd serwera');
                    showToast(result.message || 'DMUCHANIE przekształcone w DMUCHANIE_CZYSZCZENIE.', 'success');
                    modals.wyborDmuchania.hide();
                    initialLoad();
                } catch (err) {
                    errorDiv.textContent = err.message;
                    errorDiv.classList.remove('d-none');
                }
                return;
            }

            // Tryb "continue" – z NA_MAGAZYN lub FILTRACJA_KOLO_DO_PONOWNEJ
            const typ = selectedTyp ? selectedTyp.value : 'DMUCHANIE';
            if (typ === 'DMUCHANIE') {
                try {
                    const response = await fetch('/api/operations/continue-to-dmuchanie', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ id_operacji: parseInt(idOperacji, 10), operator: 'GUI' })
                    });
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.message || result.error || 'Błąd serwera');
                    showToast(result.message || 'Rozpoczęto operację DMUCHANIE.', 'success');
                    modals.wyborDmuchania.hide();
                    initialLoad();
                } catch (err) {
                    errorDiv.textContent = err.message;
                    errorDiv.classList.remove('d-none');
                }
            } else if (typ === 'DMUCHANIE_CZYSZCZENIE') {
                const idCelu = document.getElementById('wybor-dmuchania-cel').value;
                if (!idCelu) {
                    errorDiv.textContent = 'Wybierz reaktor docelowy.';
                    errorDiv.classList.remove('d-none');
                    return;
                }
                try {
                    const response = await fetch('/api/operations/continue-to-dmuchanie-czyszczenie', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            id_operacji: parseInt(idOperacji, 10),
                            id_sprzetu_docelowego: parseInt(idCelu, 10),
                            operator: 'GUI'
                        })
                    });
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.message || result.error || 'Błąd serwera');
                    showToast(result.message || 'Rozpoczęto operację DMUCHANIE_CZYSZCZENIE.', 'success');
                    modals.wyborDmuchania.hide();
                    initialLoad();
                } catch (err) {
                    errorDiv.textContent = err.message;
                    errorDiv.classList.remove('d-none');
                }
            }
        });
    }

    // -----------------------------------------------------------------------
    // Helpery do wypełniania selectów sprzętu w nowych modalach
    // -----------------------------------------------------------------------
    function fillReaktoryCelSelect(selectId) {
        const data = latestDashboardData || {};
        const reaktory = (data.all_reactors || []).map(r => ({ id: r.id, nazwa: r.nazwa || r.nazwa_unikalna || String(r.id) }));
        const sel = document.getElementById(selectId);
        if (!sel) return;
        sel.innerHTML = '<option value="">-- wybierz reaktor --</option>';
        reaktory.forEach(r => {
            const opt = document.createElement('option');
            opt.value = r.id;
            opt.textContent = r.nazwa;
            sel.appendChild(opt);
        });
    }

    function fillSprzetSelects(zrodloSelectId, celSelectId) {
        const data = latestDashboardData || {};
        const allSprzet = [
            ...(data.all_reactors || []).map(r => ({ id: r.id, nazwa: r.nazwa || r.nazwa_unikalna || String(r.id) })),
            ...(data.beczki_czyste || []).map(b => ({ id: b.id, nazwa: b.nazwa || b.nazwa_unikalna || String(b.id) })),
            ...(data.beczki_brudne || []).map(b => ({ id: b.id, nazwa: b.nazwa || b.nazwa_unikalna || String(b.id) }))
        ];
        [zrodloSelectId, celSelectId].forEach(selectId => {
            const sel = document.getElementById(selectId);
            if (!sel) return;
            const currentVal = sel.value;
            sel.innerHTML = '<option value="">-- wybierz --</option>';
            allSprzet.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.nazwa;
                sel.appendChild(opt);
            });
            if (currentVal) sel.value = currentVal;
        });
    }

    // Obsługa globalnego przycisku DMUCHANIE – czyszczenie
    const openDmuchanieCzyszczenieBtn = document.getElementById('open-dmuchanie-czyszczenie-btn');
    if (openDmuchanieCzyszczenieBtn) {
        openDmuchanieCzyszczenieBtn.addEventListener('click', async () => {
            const zrodloSelect = document.getElementById('dmuchanie-czyszczenie-zrodlo');
            const celSelect = document.getElementById('dmuchanie-czyszczenie-cel');
            const data = latestDashboardData || {};
            const allSprzet = [
                ...(data.all_reactors || []).map(r => ({ id: r.id, nazwa: (r.nazwa || r.nazwa_unikalna || String(r.id)) + ' (reaktor)' })),
                ...(data.beczki_czyste || []).map(b => ({ id: b.id, nazwa: (b.nazwa || b.nazwa_unikalna || String(b.id)) + ' (beczka)' })),
                ...(data.beczki_brudne || []).map(b => ({ id: b.id, nazwa: (b.nazwa || b.nazwa_unikalna || String(b.id)) + ' (beczka)' }))
            ];
            try {
                const res = await fetch('/api/sprzet/filtry');
                const filtry = res.ok ? await res.json() : [];
                filtry.forEach(f => {
                    allSprzet.push({ id: f.id, nazwa: (f.nazwa_unikalna || f.id) + ' (filtr)' });
                });
            } catch (_) {}
            if (zrodloSelect) {
                zrodloSelect.innerHTML = '<option value="">-- wybierz źródło (zalecane: filtr) --</option>';
                allSprzet.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s.id;
                    opt.textContent = s.nazwa;
                    zrodloSelect.appendChild(opt);
                });
            }
            if (celSelect) {
                celSelect.innerHTML = '<option value="">-- wybierz najpierw źródło --</option>';
            }
            document.getElementById('dmuchanie-czyszczenie-error').classList.add('d-none');
            modals.dmuchanieCzyszczenie.show();
        });
    }

    // Gdy zmieni się źródło w DMUCHANIE_CZYSZCZENIE – załaduj cele (puste reaktory z trasą)
    const dmuchanieCzyszczenieZrodlo = document.getElementById('dmuchanie-czyszczenie-zrodlo');
    if (dmuchanieCzyszczenieZrodlo) {
        dmuchanieCzyszczenieZrodlo.addEventListener('change', async () => {
            const idZrodla = dmuchanieCzyszczenieZrodlo.value;
            const celSelect = document.getElementById('dmuchanie-czyszczenie-cel');
            if (!celSelect) return;
            if (!idZrodla) {
                celSelect.innerHTML = '<option value="">-- wybierz najpierw źródło --</option>';
                return;
            }
            celSelect.innerHTML = '<option value="">Ładowanie celów...</option>';
            celSelect.disabled = true;
            try {
                const res = await fetch(`/api/operations/dmuchanie-czyszczenie-destinations?id_sprzetu_zrodlowego=${idZrodla}`);
                const data = res.ok ? await res.json() : { destinations: [] };
                const destinations = data.destinations || [];
                celSelect.innerHTML = '<option value="">-- wybierz cel --</option>';
                destinations.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d.id;
                    opt.textContent = (d.nazwa_unikalna || d.id) + (d.material_types_text ? ` (${d.material_types_text})` : '');
                    celSelect.appendChild(opt);
                });
                if (destinations.length === 0) {
                    celSelect.innerHTML = '<option value="">Brak reaktorów z możliwą trasą</option>';
                }
            } catch {
                celSelect.innerHTML = '<option value="">Błąd ładowania</option>';
            }
            celSelect.disabled = false;
        });
    }

    // Obsługa globalnego przycisku DMUCHANIE rurociągu
    const openDmuchanieRurociaguBtn = document.getElementById('open-dmuchanie-rurociagu-btn');
    if (openDmuchanieRurociaguBtn) {
        openDmuchanieRurociaguBtn.addEventListener('click', () => {
            fillSprzetSelects('dmuchanie-rurociagu-zrodlo', 'dmuchanie-rurociagu-cel');
            document.getElementById('dmuchanie-rurociagu-error').classList.add('d-none');
            modals.dmuchanieRurociagu.show();
        });
    }

    // Obsługa formularza FILTRACJA_NA_PLACKU
    if (forms.filtracjaNaPlacku) {
        forms.filtracjaNaPlacku.addEventListener('submit', async (e) => {
            e.preventDefault();
            const idZrodla = document.getElementById('filtracja-na-placku-id-zrodla').value;
            const selected = document.querySelector('input[name="fnp-destination"]:checked');
            const errorDiv = document.getElementById('filtracja-na-placku-error');
            if (!idZrodla || !selected) {
                errorDiv.textContent = 'Wybierz reaktor docelowy.';
                errorDiv.classList.remove('d-none');
                return;
            }
            errorDiv.classList.add('d-none');
            try {
                const response = await fetch('/api/operations/start-filtracja-na-placku', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id_sprzetu_zrodlowego: parseInt(idZrodla, 10),
                        id_sprzetu_docelowego: parseInt(selected.value, 10),
                        operator: 'GUI'
                    })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || result.error || 'Błąd serwera');
                showToast(result.message || 'Filtracja na placku rozpoczęta.', 'success');
                modals.filtracjaNaPlacku.hide();
                initialLoad();
            } catch (error) {
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('d-none');
            }
        });
    }

    // Obsługa formularza DMUCHANIE_CZYSZCZENIE
    if (forms.dmuchanieCzyszczenie) {
        forms.dmuchanieCzyszczenie.addEventListener('submit', async (e) => {
            e.preventDefault();
            const idZrodla = document.getElementById('dmuchanie-czyszczenie-zrodlo').value;
            const idCelu = document.getElementById('dmuchanie-czyszczenie-cel').value;
            const errorDiv = document.getElementById('dmuchanie-czyszczenie-error');
            if (!idZrodla || !idCelu) {
                errorDiv.textContent = 'Wybierz sprzęt źródłowy i docelowy.';
                errorDiv.classList.remove('d-none');
                return;
            }
            errorDiv.classList.add('d-none');
            try {
                const response = await fetch('/api/operations/start-dmuchanie-czyszczenie', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id_sprzetu_zrodlowego: parseInt(idZrodla, 10),
                        id_sprzetu_docelowego: parseInt(idCelu, 10),
                        operator: 'GUI'
                    })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || result.error || 'Błąd serwera');
                showToast(result.message || 'Operacja DMUCHANIE_CZYSZCZENIE rozpoczęta.', 'success');
                modals.dmuchanieCzyszczenie.hide();
                initialLoad();
            } catch (error) {
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('d-none');
            }
        });
    }

    // Obsługa formularza DMUCHANIE_RUROCIAGU
    if (forms.dmuchanieRurociagu) {
        forms.dmuchanieRurociagu.addEventListener('submit', async (e) => {
            e.preventDefault();
            const idZrodla = document.getElementById('dmuchanie-rurociagu-zrodlo').value;
            const idCelu = document.getElementById('dmuchanie-rurociagu-cel').value;
            const errorDiv = document.getElementById('dmuchanie-rurociagu-error');
            if (!idZrodla || !idCelu) {
                errorDiv.textContent = 'Wybierz sprzęt źródłowy i docelowy.';
                errorDiv.classList.remove('d-none');
                return;
            }
            errorDiv.classList.add('d-none');
            try {
                const response = await fetch('/api/operations/start-dmuchanie-rurociagu', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id_sprzetu_zrodlowego: parseInt(idZrodla, 10),
                        id_sprzetu_docelowego: parseInt(idCelu, 10),
                        operator: 'GUI'
                    })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || result.error || 'Błąd serwera');
                showToast(result.message || 'Operacja DMUCHANIE_RUROCIAGU rozpoczęta.', 'success');
                modals.dmuchanieRurociagu.hide();
                initialLoad();
            } catch (error) {
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('d-none');
            }
        });
    }

    // Obsługa formularza Dobielanie
    if (forms.dobielanie) {
        forms.dobielanie.addEventListener('submit', async (e) => {
            e.preventDefault();
            const mixId = document.getElementById('dobielanie-mix-id').value;
            const bags = parseInt(document.getElementById('dobielanie-bags').value, 10);
            const weight = parseFloat(document.getElementById('dobielanie-weight').value);
            const errorDiv = document.getElementById('dobielanie-error');
            if (!mixId || bags < 1 || !weight || weight <= 0) {
                errorDiv.textContent = 'Wprowadź poprawną ilość worków i wagę worka (kg).';
                errorDiv.classList.remove('d-none');
                return;
            }
            errorDiv.classList.add('d-none');
            try {
                const response = await fetch(`/api/workflow/mix/${mixId}/add-bleach`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        bags_count: bags,
                        bag_weight: weight,
                        operator: 'GUI'
                    })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || result.message || 'Błąd serwera');
                showToast(result.message || 'Dobielanie zarejestrowane.', 'success');
                modals.dobielanie.hide();
                initialLoad();
            } catch (error) {
                console.error('Błąd dobielania:', error);
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('d-none');
            }
        });
    }

    // Obsługa formularza Ocena próbki (wynik OK / do ponownej filtracji)
    if (forms.ocenaProbki) {
        forms.ocenaProbki.addEventListener('submit', async (e) => {
            e.preventDefault();
            const idOperacji = document.getElementById('ocena-probki-id-operacji').value;
            const wynikRadio = document.querySelector('input[name="ocena-wynik"]:checked');
            const errorDiv = document.getElementById('ocena-probki-error');
            if (!idOperacji || !wynikRadio) {
                errorDiv.textContent = 'Wybierz wynik oceny.';
                errorDiv.classList.remove('d-none');
                return;
            }
            const wynik = wynikRadio.value;
            const powod = document.getElementById('ocena-powod').value.trim();
            errorDiv.classList.add('d-none');
            try {
                const payload = { id_operacji: parseInt(idOperacji, 10), wynik_oceny: wynik };
                if (powod) payload.powod = powod;
                const response = await fetch('/api/operations/continue-to-ocena', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || result.error || 'Błąd serwera');
                showToast(result.message || 'Wynik oceny zapisany.', 'success');
                modals.ocenaProbki.hide();
                initialLoad();
            } catch (error) {
                console.error('Błąd oceny próbki:', error);
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('d-none');
            }
        });
    }

    // --- INICJALIZACJA ---
    async function initialLoad() {
        try {
            const response = await fetch('/api/dashboard/main-status');
            if (!response.ok) throw new Error('Błąd pobierania danych z API');
            const data = await response.json();
            latestDashboardData = data; // Zapisz najnowsze dane
            updateUI(data);
            // await loadSchedulerStatus(); // USUNIĘTE
        } catch (error) {
            console.error(error);
            reaktoryContainer.innerHTML = '<p class="text-danger">Nie udało się załadować danych.</p>';
        }
    }
    initialLoad();

    async function handleOpenSimulationSettings(sprzetId, sprzetNazwa) {
        // Ustaw ID i nazwę w modalu
        document.getElementById('simulation-settings-sprzet-id').value = sprzetId;
        document.getElementById('simulation-settings-sprzet-name').textContent = sprzetNazwa;
        
        const heatingInput = document.getElementById('simulation-heating-speed');
        const coolingInput = document.getElementById('simulation-cooling-speed');
        const targetTempInput = document.getElementById('simulation-target-temp');
        const currentTempInput = document.getElementById('simulation-current-temp');

        // Pokaż stan ładowania
        heatingInput.value = 'Ładowanie...';
        coolingInput.value = 'Ładowanie...';
        targetTempInput.value = 'Ładowanie...';
        currentTempInput.value = 'Ładowanie...';
        heatingInput.disabled = true;
        coolingInput.disabled = true;
        targetTempInput.disabled = true;
        currentTempInput.disabled = true;

        // Pokaż modal
        modals.simulationSettings.show();

        try {
            // Pobierz aktualne dane prosto z bazy
            const response = await fetch(`/api/sprzet/${sprzetId}/simulation-params`);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Błąd pobierania danych');
            }
            const data = await response.json();

            // Wypełnij formularz aktualnymi wartościami
            heatingInput.value = data.szybkosc_grzania || '0.50';
            coolingInput.value = data.szybkosc_chlodzenia || '0.10';
            targetTempInput.value = data.temperatura_docelowa || '';
            currentTempInput.value = data.temperatura_aktualna || '';

        } catch (error) {
            console.error('Błąd podczas pobierania parametrów symulacji:', error);
            showToast(error.message, 'error');
            // W przypadku błędu, zamknij modal
            modals.simulationSettings.hide();
        } finally {
            // Zawsze włączaj pola po zakończeniu operacji
            heatingInput.disabled = false;
            coolingInput.disabled = false;
            targetTempInput.disabled = false;
            currentTempInput.disabled = false;
        }
    }

    // Funkcja do wyświetlania powiadomień
    function showToast(message, type = 'info', autoClose = true) {
        // Sprawdź czy Bootstrap Toast jest dostępny
        if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
            // Dynamicznie określ klasę koloru na podstawie typu
            const bgClass = type === 'error' ? 'bg-danger' : type === 'success' ? 'bg-success' : 'bg-info';
            
            // Zbuduj HTML dla toasta
            const toastHTML = `
                <div class="toast align-items-center text-white ${bgClass} border-0" role="alert" aria-live="assertive" aria-atomic="true">
                    <div class="d-flex">
                        <div class="toast-body">
                            ${message}
                        </div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                    </div>
                </div>
            `;
            
            // Stwórz kontener, jeśli jeszcze nie istnieje
            let toastContainer = document.querySelector('.toast-container');
            if (!toastContainer) {
                toastContainer = document.createElement('div');
                toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
                toastContainer.style.zIndex = '9999';
                document.body.appendChild(toastContainer);
            }
            
            // Dodaj nowy toast do kontenera
            const toastWrapper = document.createElement('div');
            toastWrapper.innerHTML = toastHTML;
            const toastElement = toastWrapper.querySelector('.toast');
            toastContainer.appendChild(toastElement);
            
            // === KLUCZOWA ZMIANA JEST TUTAJ ===
            // Stwórz obiekt opcji dla konstruktora Bootstrap Toast
            const bootstrapToastOptions = {
                autohide: autoClose, // Użyj bezpośrednio parametru funkcji
                delay: 5000          // Domyślny czas znikania, jeśli autohide=true
            };

            // Zainicjuj i pokaż toast z odpowiednimi opcjami
            const toast = new bootstrap.Toast(toastElement, bootstrapToastOptions);
            toast.show();
            
            // Usuń element toasta z DOM po jego ukryciu, aby nie zaśmiecać
            toastElement.addEventListener('hidden.bs.toast', () => {
                toastElement.remove();
            });
        } else {
            // Fallback - użyj alert jeśli Bootstrap lub Toastify nie są dostępne
            alert(message);
        }
    }   

    // === FUNKCJONALNOŚĆ HARMONOGRAMU ZADAŃ ===
    
    // Elementy DOM dla harmonogramu
    const schedulerBtn = document.getElementById('scheduler-btn');
    const schedulerModal = new bootstrap.Modal(document.getElementById('scheduler-modal'));
    const editIntervalModal = new bootstrap.Modal(document.getElementById('edit-interval-modal'));
    const schedulerTasksTbody = document.getElementById('scheduler-tasks-tbody');
    const intervalOptions = document.getElementById('interval-options');
    const customIntervalInput = document.getElementById('custom-interval');
    const saveIntervalBtn = document.getElementById('save-interval-btn');
    
    let currentTaskId = null;
    let predefinedIntervals = [];

    // Obsługa przycisku harmonogramu
    schedulerBtn.addEventListener('click', () => {
        loadSchedulerTasks();
        schedulerModal.show();
    });

    // Obsługa przycisku zapisywania interwału
    saveIntervalBtn.addEventListener('click', async () => {
        await saveTaskInterval();
    });

    // Obsługa klawisza Enter w polu własnego interwału
    customIntervalInput.addEventListener('keypress', async (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            // Sprawdź czy pole nie jest puste i ma prawidłową wartość
            const value = parseInt(customIntervalInput.value);
            if (value && value > 0) {
                await saveTaskInterval();
            } else {
                showToast('Wprowadź prawidłowy interwał (minimum 1 sekunda)', 'error');
                customIntervalInput.focus();
            }
        }
    });

    // Obsługa klawisza Escape do zamknięcia modala
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && editIntervalModal._isShown) {
            editIntervalModal.hide();
        }
    });

    // Funkcja do ładowania zadań harmonogramu
    async function loadSchedulerTasks() {
        try {
            const response = await fetch('/api/scheduler/tasks');
            if (!response.ok) throw new Error('Błąd pobierania zadań');
            
            const tasks = await response.json();
            renderSchedulerTasks(tasks);
        } catch (error) {
            console.error('Błąd ładowania zadań:', error);
            showToast('Błąd ładowania zadań harmonogramu', 'error');
        }
    }

    // Funkcja do renderowania zadań w tabeli
    function renderSchedulerTasks(tasks) {
        schedulerTasksTbody.innerHTML = '';
        
        if (tasks.length === 0) {
            schedulerTasksTbody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center text-muted">Brak zadań w harmonogramie</td>
                </tr>
            `;
            return;
        }

        tasks.forEach(task => {
            const statusBadge = task.enabled ? 
                '<span class="badge bg-success">Włączone</span>' : 
                '<span class="badge bg-secondary">Wyłączone</span>';
            
            const intervalText = formatInterval(task.interval_seconds);
            const lastRun = task.last_run_at ? new Date(task.last_run_at).toLocaleString() : 'Nigdy';
            const nextRun = task.next_run_at ? new Date(task.next_run_at).toLocaleString() : 'Nie zaplanowano';
            
            const row = `
                <tr>
                    <td><strong>${task.name}</strong></td>
                    <td>
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" role="switch" 
                                   id="task-switch-${task.id}" ${task.enabled ? 'checked' : ''}
                                   onchange="toggleTask(${task.id}, this.checked)">
                            <label class="form-check-label" for="task-switch-${task.id}">
                                ${task.enabled ? '<span class="text-success fw-bold">Włączone</span>' : '<span class="text-muted">Wyłączone</span>'}
                            </label>
                        </div>
                    </td>
                    <td>${intervalText}</td>
                    <td>${lastRun}</td>
                    <td>${nextRun}</td>
                    <td>${task.total_run_count}</td>
                    <td>
                        <button class="btn btn-outline-primary btn-sm" 
                                onclick="editTaskInterval(${task.id}, '${task.name}', ${task.interval_seconds})">
                            <i class="fas fa-edit me-1"></i>Edytuj
                        </button>
                    </td>
                </tr>
            `;
            schedulerTasksTbody.innerHTML += row;
        });
    }

    // Funkcja do formatowania interwału
    function formatInterval(seconds) {
        if (seconds < 60) {
            return `${seconds}s`;
        } else if (seconds < 3600) {
            const minutes = Math.floor(seconds / 60);
            return `${minutes}m`;
        } else {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            return `${hours}h ${minutes}m`;
        }
    }

    // Funkcja do przełączania stanu zadania
    async function toggleTask(taskId, enabled) {
        try {
            const response = await fetch(`/api/scheduler/tasks/${taskId}/toggle`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled })
            });
            
            const result = await response.json();
            if (!response.ok) throw new Error(result.error);
            
            showToast(result.message, 'success');
            loadSchedulerTasks(); // Odśwież listę
        } catch (error) {
            console.error('Błąd przełączania zadania:', error);
            showToast(error.message, 'error');
            // W przypadku błędu, przywróć poprzedni stan switch'a
            const switchElement = document.getElementById(`task-switch-${taskId}`);
            if (switchElement) {
                switchElement.checked = !enabled;
            }
        }
    }

    // Funkcja do edycji interwału zadania
    async function editTaskInterval(taskId, taskName, currentInterval) {
        currentTaskId = taskId;
        document.getElementById('edit-task-id').value = taskId;
        document.getElementById('edit-task-name').value = taskName;
        
        // Załaduj predefiniowane interwały
        await loadPredefinedIntervals();
        
        const saveButton = document.getElementById('save-interval-btn');
        
        // Ustaw aktualny interwał jako wybrany
        const currentIntervalRadio = document.querySelector(`input[name="interval"][value="${currentInterval}"]`);
        if (currentIntervalRadio) {
            currentIntervalRadio.checked = true;
            saveButton.style.display = 'none'; // Ukryj przycisk dla predefiniowanych
        } else {
            // Jeśli aktualny interwał nie jest predefiniowany, wybierz opcję "własny"
            const customRadio = document.querySelector('input[name="interval"][value="custom"]');
            customRadio.checked = true;
            customIntervalInput.value = currentInterval;
            customIntervalInput.disabled = false;
            saveButton.style.display = 'inline-block'; // Pokaż przycisk dla własnego interwału
        }
        
        editIntervalModal.show();
    }

    // Funkcja do ładowania predefiniowanych interwałów
    async function loadPredefinedIntervals() {
        try {
            const response = await fetch('/api/scheduler/predefined-intervals');
            if (!response.ok) throw new Error('Błąd pobierania interwałów');
            
            predefinedIntervals = await response.json();
            renderIntervalOptions();
        } catch (error) {
            console.error('Błąd ładowania interwałów:', error);
            showToast('Błąd ładowania predefiniowanych interwałów', 'error');
        }
    }

    // Funkcja do renderowania opcji interwałów
    function renderIntervalOptions() {
        intervalOptions.innerHTML = '';
        
        predefinedIntervals.forEach(interval => {
            const option = `
                <input type="radio" class="btn-check" name="interval" 
                       value="${interval.value}" id="interval-${interval.value}" autocomplete="off">
                <label class="btn btn-outline-primary btn-lg mb-2 me-2" for="interval-${interval.value}">
                    <i class="fas fa-clock me-2"></i>
                    ${interval.label}
                </label>
            `;
            intervalOptions.innerHTML += option;
        });
        
        // Dodaj opcję "własny interwał"
        const customOption = `
            <input type="radio" class="btn-check" name="interval" 
                   value="custom" id="interval-custom" autocomplete="off">
            <label class="btn btn-outline-warning btn-lg mb-2" for="interval-custom">
                <i class="fas fa-edit me-2"></i>
                Własny interwał
            </label>
        `;
        intervalOptions.innerHTML += customOption;
        
        // Obsługa zmiany wyboru interwału
        document.querySelectorAll('input[name="interval"]').forEach(radio => {
            radio.addEventListener('change', async (e) => {
                const saveButton = document.getElementById('save-interval-btn');
                
                if (e.target.value === 'custom') {
                    customIntervalInput.disabled = false;
                    customIntervalInput.focus();
                    saveButton.style.display = 'inline-block'; // Pokaż przycisk dla własnego interwału
                } else {
                    customIntervalInput.disabled = true;
                    customIntervalInput.value = '';
                    saveButton.style.display = 'none'; // Ukryj przycisk dla predefiniowanych
                    
                    // Automatyczne zapisanie dla predefiniowanych interwałów
                    const intervalSeconds = parseInt(e.target.value);
                    await saveTaskIntervalDirect(intervalSeconds);
                }
            });
        });
    }

    // Funkcja do bezpośredniego zapisywania interwału (dla predefiniowanych)
    async function saveTaskIntervalDirect(intervalSeconds) {
        try {
            const response = await fetch(`/api/scheduler/tasks/${currentTaskId}/interval`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ interval_seconds: intervalSeconds })
            });
            
            const result = await response.json();
            if (!response.ok) throw new Error(result.error);
            
            showToast(result.message, 'success');
            editIntervalModal.hide();
            loadSchedulerTasks(); // Odśwież listę
        } catch (error) {
            console.error('Błąd zapisywania interwału:', error);
            showToast(error.message, 'error');
        }
    }

    // Funkcja do zapisywania interwału zadania (dla własnego interwału)
    async function saveTaskInterval() {
        const selectedInterval = document.querySelector('input[name="interval"]:checked');
        if (!selectedInterval) {
            showToast('Wybierz interwał', 'error');
            return;
        }
        
        let intervalSeconds;
        if (selectedInterval.value === 'custom') {
            intervalSeconds = parseInt(customIntervalInput.value);
            if (!intervalSeconds || intervalSeconds <= 0) {
                showToast('Wprowadź prawidłowy interwał', 'error');
                return;
            }
        } else {
            intervalSeconds = parseInt(selectedInterval.value);
        }
        
        await saveTaskIntervalDirect(intervalSeconds);
    }

    // Eksportuj funkcje do globalnego zakresu
    window.toggleTask = toggleTask;
    window.editTaskInterval = editTaskInterval;
    window.showToast = showToast;
});