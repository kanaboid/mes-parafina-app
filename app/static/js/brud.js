// app/static/js/dashboard.js

document.addEventListener('DOMContentLoaded', () => {
    
    // --- ELEMENTY DOM, MODALE, FORMULARZE ---
    let latestDashboardData = {}; 
    const reaktoryContainer = document.getElementById('reaktory-container');
    const beczkiBrudneContainer = document.getElementById('beczki-brudne-container');
    const beczkiCzysteContainer = document.getElementById('beczki-czyste-container');
    const alarmsContainer = document.getElementById('alarms-container');
    const activeOperationsContainer = document.getElementById('active-operations-log');
    const lastUpdatedTime = document.getElementById('last-updated-time');
    const stockSummaryContainer = document.getElementById('stock-summary-container');

    const modals = {
        // ... (bez zmian)
    };
    const forms = {
        // ... (bez zmian)
    };
    
    // --- NOWA FUNKCJA POMOCNICZA ---
    const formatValue = (value, unit = '', decimalPlaces = 1) => {
        if (value === null || typeof value === 'undefined') {
            return 'B/D';
        }
        if (typeof value === 'number') {
            return `${value.toFixed(decimalPlaces)}${unit}`;
        }
        return `${value}${unit}`;
    };
    // --- KONIEC NOWEJ FUNKCJI ---

    // --- SOCKET.IO ---
    const socket = io();
    socket.on('connect', () => console.log("Połączono z dashboardem przez WebSocket."));
    
    socket.on('dashboard_update', (data) => {
        console.log("Otrzymano aktualizację dashboardu:", data);
        latestDashboardData = data;
        updateUI(data);
    });

    socket.on('heating_completed', (data) => {
        // ... (bez zmian)
    });

    // --- GŁÓWNA FUNKCJA AKTUALIZUJĄCA UI ---
    function updateUI(data) {
        renderReaktory(data.all_reactors);
        renderBeczki(data.beczki_brudne, beczkiBrudneContainer, true);
        renderBeczki(data.beczki_czyste, beczkiCzysteContainer, false);
        renderAlarms(data.alarmy);
        renderStockSummary(data.stock_summary);
        renderActiveOperations(data.active_operations);
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
            let actionButtonsHTML = `
                <button class="btn btn-primary action-btn" data-action="show-details" data-sprzet-id="${r.id}" data-sprzet-nazwa="${r.nazwa}"><i class="fas fa-info-circle"></i></button>
                <button class="btn btn-secondary action-btn" data-action="open-simulation-settings" data-sprzet-id="${r.id}" data-sprzet-nazwa="${r.nazwa}"><i class="fas fa-sliders-h"></i></button>
                <button class="btn btn-info action-btn" data-action="open-transfer-modal" data-sprzet-id="${r.id}" data-sprzet-nazwa="${r.nazwa}" data-partia-waga="${r.partia ? r.partia.waga_kg : '0'}"><i class="fas fa-exchange-alt"></i></button>
            `;
            if (r.partia && r.partia.process_status === 'SUROWY') {
                actionButtonsHTML += `<button class="btn btn-warning action-btn" data-action="start-heating" data-sprzet-id="${r.id}" data-sprzet-nazwa="${r.nazwa}">Włącz palnik(INFO)</button>`;
            }
            
            const isEmpty = !r.partia;
            const statusClass = r.stan_sprzetu === 'W transferze' ? 'status-alarm' : (r.partia ? 'status-ok' : 'status-idle');
            
            let materialTypeHTML = '';
            if (r.partia && r.partia.sklad && r.partia.sklad.length > 0) {
                const materialTypes = [...new Set(r.partia.sklad.map(item => item.material_type))];
                materialTypeHTML = `<div class="text-center p-3 rounded-3 mb-3 shadow-sm" style="background-color: #f5deb3;"><div class="d-flex align-items-center justify-content-center"><i class="fas fa-flask fs-3 me-3" style="color: #856404;"></i><h3 class="mb-0 fw-bold" style="color: #856404;">${materialTypes.join(' + ')}</h3></div></div>`;
            }

            let wagaHTML = '';
            let capacityProgressHTML = '';
            if (r.partia && r.partia.waga_kg > 0) {
                const wagaTonnes = (r.partia.waga_kg / 1000).toFixed(2);
                const pojemnoscTonnes = r.pojemnosc_kg ? (r.pojemnosc_kg / 1000).toFixed(2) : null;
                wagaHTML = `<div class="bg-light p-3 rounded-3 mb-3 border border-primary border-opacity-25"><div class="d-flex justify-content-between align-items-center"><div class="d-flex align-items-center"><i class="fas fa-weight-hanging text-primary fs-4 me-2"></i><span class="text-muted">Waga:</span></div><div class="text-end"><span class="fs-3 fw-bold text-primary">${wagaTonnes} t</span>${pojemnoscTonnes ? `<span class="text-muted" style="font-weight: normal; opacity: 0.7;"> / ${pojemnoscTonnes} t</span>` : ''}</div></div></div>`;
                if (r.pojemnosc_kg && r.pojemnosc_kg > 0) {
                    const fillPercent = (r.partia.waga_kg / r.pojemnosc_kg) * 100;
                    let fillColorClass = 'bg-info';
                    if (fillPercent > 95) fillColorClass = 'bg-danger';
                    else if (fillPercent > 80) fillColorClass = 'bg-warning';
                    capacityProgressHTML = `<div class="mb-3"><div class="d-flex justify-content-between mb-1"><small class="text-muted"><i class="fas fa-chart-line me-1"></i>Zapełnienie reaktora</small><small class="fw-bold text-primary">${fillPercent.toFixed(1)}%</small></div><div class="progress" style="height: 10px;"><div class="progress-bar ${fillColorClass}" role="progressbar" style="width: ${fillPercent}%;" aria-valuenow="${fillPercent}" aria-valuemin="0" aria-valuemax="100"></div></div></div>`;
                }
            }

            const partiaHTML = r.partia ? `<div class="d-flex align-items-center mb-3"><i class="fas fa-barcode text-muted me-2"></i><span class="text-muted me-2">Partia:</span><span class="fw-semibold">${r.partia.kod}</span></div>` : '<p class="text-center text-muted fst-italic mb-3"><i class="fas fa-inbox me-2"></i>Reaktor pusty</p>';
            
            let tempPercent = (r.temperatura_aktualna && r.temperatura_max) ? (r.temperatura_aktualna / r.temperatura_max) * 100 : 0;
            let tempColorClass = 'bg-success';
            if (tempPercent > 95) tempColorClass = 'bg-danger';
            else if (tempPercent > 80) tempColorClass = 'bg-warning';
            
            const tempProgressBar = `<div class="mb-3"><div class="d-flex justify-content-between align-items-center mb-1"><small class="text-muted"><i class="fas fa-thermometer-half me-1"></i>Temperatura</small><small class="fw-semibold">${formatValue(r.temperatura_aktualna, '°C', 1)} / ${formatValue(r.temperatura_docelowa, '°C', 0)}</small></div><div class="progress" style="height: 10px;"><div class="progress-bar ${tempColorClass}" role="progressbar" style="width: ${tempPercent}%;"></div></div></div>`;
            
            let pressurePercent = (r.cisnienie_aktualne && r.cisnienie_max) ? (r.cisnienie_aktualne / r.cisnienie_max) * 100 : 0;
            let pressureColorClass = 'bg-success';
            if (pressurePercent > 95) pressureColorClass = 'bg-danger';
            else if (pressurePercent > 80) pressureColorClass = 'bg-warning';
            
            const pressureProgressBar = `<div class="mb-3"><div class="d-flex justify-content-between align-items-center mb-1"><small class="text-muted"><i class="fas fa-tachometer-alt me-1"></i>Ciśnienie</small><small class="fw-semibold">${formatValue(r.cisnienie_aktualne, ' bar', 2)}</small></div><div class="progress" style="height: 10px;"><div class="progress-bar ${pressureColorClass}" role="progressbar" style="width: ${pressurePercent}%;"></div></div></div>`;

            // --- ZMODYFIKOWANA SEKCJA POZIOMU ---
            let levelProgressBar = '';
            if (r.poziom_procent != null) {
                const levelPercent = r.poziom_procent;
                let levelColorClass = 'bg-info';
                if (levelPercent > 95) levelColorClass = 'bg-danger';
                else if (levelPercent > 80) levelColorClass = 'bg-warning';

                levelProgressBar = `
                    <div class="mb-3">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <small class="text-muted"><i class="fas fa-ruler-vertical me-1"></i>Poziom (czujnik)</small>
                            <small class="fw-semibold">${formatValue(levelPercent, '%')} <span class="text-muted fw-normal">(${formatValue(r.odczyt_mm, 'mm', 0)})</span></small>
                        </div>
                        <div class="progress" style="height: 10px;">
                            <div class="progress-bar ${levelColorClass}" role="progressbar" style="width: ${levelPercent}%;"></div>
                        </div>
                    </div>
                `;
            }
            // --- KONIEC ZMIAN ---

            const isBurnerOn = r.stan_palnika === 'WLACZONY';
            const burnerSwitchHTML = `<div class="d-flex justify-content-between align-items-center mt-3 p-2 bg-light rounded"><div class="form-check form-switch mb-0"><input class="form-check-input action-btn" type="checkbox" role="switch" id="burner-switch-${r.id}" data-action="toggle-burner" data-sprzet-id="${r.id}" ${isBurnerOn ? 'checked' : ''}><label class="form-check-label" for="burner-switch-${r.id}">Palnik ${isBurnerOn ? '<span class="text-danger fw-bold">WŁĄCZONY</span>' : '<span class="text-muted">WYŁĄCZONY</span>'}</label></div><i class="fas fa-fire ${isBurnerOn ? 'text-danger' : 'text-muted'} fs-4"></i></div>`;

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
            const isEmpty = !b.partia || !b.partia.waga_kg || b.partia.waga_kg === 0;
            const statusClass = isEmpty ? 'border-secondary' : (isBrudna ? 'border-danger' : 'border-success');
            const statusBgClass = isEmpty ? 'bg-light' : (isBrudna ? 'bg-danger bg-opacity-10' : 'bg-success bg-opacity-10');
            const statusIcon = isEmpty ? 'fa-circle text-secondary' : (isBrudna ? 'fa-circle text-danger' : 'fa-circle text-success');
            
            let materialTypeHTML = '';
            if (b.partia && b.partia.sklad && b.partia.sklad.length > 0) {
                const materialTypes = [...new Set(b.partia.sklad.map(item => item.material_type))];
                materialTypeHTML = `<div class="text-center bg-white p-2 rounded mb-2 border border-primary border-opacity-25"><h5 class="mb-0 text-primary fw-bold">${materialTypes.join(' + ')}</h5></div>`;
            }

            let wagaHTML = '';
            let progressBarHTML = '';
            if (b.partia && b.partia.waga_kg > 0) {
                const wagaTonnes = (b.partia.waga_kg / 1000).toFixed(2);
                const pojemnoscTonnes = b.pojemnosc_kg ? (b.pojemnosc_kg / 1000).toFixed(2) : 'N/A';
                wagaHTML = `<div class="d-flex justify-content-between align-items-center mb-2"><span class="text-muted"><i class="fas fa-weight-hanging me-2"></i>Waga:</span><span class="fs-5 fw-bold">${wagaTonnes} t ${b.pojemnosc_kg ? `<span style="font-weight: normal; opacity: 0.7;">/ ${pojemnoscTonnes} t</span>` : ''}</span></div>`;
                if (b.pojemnosc_kg && b.pojemnosc_kg > 0) {
                    const fillPercent = (b.partia.waga_kg / b.pojemnosc_kg) * 100;
                    let fillColorClass = 'bg-success';
                    if (fillPercent > 95) fillColorClass = 'bg-danger';
                    else if (fillPercent > 80) fillColorClass = 'bg-warning';
                    progressBarHTML = `<div class="mb-3"><div class="d-flex justify-content-between mb-1"><small class="text-muted"><i class="fas fa-chart-bar me-1"></i>Zapełnienie</small><small class="fw-bold text-primary">${fillPercent.toFixed(1)}%</small></div><div class="progress" style="height: 12px;"><div class="progress-bar ${fillColorClass}" role="progressbar" style="width: ${fillPercent}%;" aria-valuenow="${fillPercent}" aria-valuemin="0" aria-valuemax="100"></div></div></div>`;
                }
            }

            // --- ZMODYFIKOWANA SEKCJA POZIOMU DLA BECZEK ---
            let levelProgressBar = '';
            if (b.poziom_procent != null) {
                const levelPercent = b.poziom_procent;
                let levelColorClass = isBrudna ? 'bg-danger' : 'bg-success';
                if (levelPercent > 95) levelColorClass = 'bg-warning';

                levelProgressBar = `
                    <div class="mb-2">
                        <div class="d-flex justify-content-between mb-1">
                            <small class="text-muted"><i class="fas fa-ruler-vertical me-1"></i>Poziom (czujnik)</small>
                            <small class="fw-semibold">${formatValue(levelPercent, '%')} <span class="text-muted fw-normal">(${formatValue(b.odczyt_mm, 'mm', 0)})</span></small>
                        </div>
                        <div class="progress" style="height: 12px;">
                            <div class="progress-bar ${levelColorClass}" role="progressbar" style="width: ${levelPercent}%;"></div>
                        </div>
                    </div>
                `;
            }
            // --- KONIEC ZMIAN ---

            const partiaHTML = b.partia && b.partia.kod ? `<div class="d-flex justify-content-between align-items-center mb-2"><span class="text-muted"><i class="fas fa-barcode me-2"></i>Partia:</span><span class="fw-semibold">${b.partia.kod}</span></div>` : '<p class="text-center text-muted fst-italic mb-2"><i class="fas fa-inbox me-2"></i>Pusta</p>';

            const cardHTML = `
                <div class="col-xl-3 col-lg-4 col-md-6">
                    <div class="card h-100 shadow-sm ${statusClass} border-2 ${statusBgClass}">
                        <div class="card-header ${statusBgClass} d-flex justify-content-between align-items-center">
                            <h6 class="mb-0 fw-bold"><i class="fas ${statusIcon} me-2"></i>${b.nazwa}</h6>
                            <span class="badge ${isEmpty ? 'bg-secondary' : (isBrudna ? 'bg-danger' : 'bg-success')}">${b.stan_sprzetu || 'Gotowy'}</span>
                        </div>
                        <div class="card-body">
                            ${materialTypeHTML}
                            ${partiaHTML}
                            ${wagaHTML}
                            ${progressBarHTML}
                            ${levelProgressBar}
                        </div>
                        <div class="card-footer p-2">
                            <button class="btn btn-info w-100 action-btn" data-action="open-transfer-modal" data-sprzet-id="${b.id}" data-sprzet-nazwa="${b.nazwa}" data-partia-waga="${b.partia ? b.partia.waga_kg : '0'}"><i class="fas fa-exchange-alt me-1"></i>Przelej</button>
                        </div>
                    </div>
                </div>
            `;
            container.innerHTML += cardHTML;
        });
    }
    
    // ... (reszta pliku dashboard.js bez żadnych zmian) ...
});