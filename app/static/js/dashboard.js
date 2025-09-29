// app/static/js/dashboard.js

document.addEventListener('DOMContentLoaded', () => {
    
    // --- ELEMENTY DOM, MODALE, FORMULARZE ---
    let latestDashboardData = {}; // Globalne przechowywanie danych
    const reaktoryContainer = document.getElementById('reaktory-container');
    const beczkiBrudneContainer = document.getElementById('beczki-brudne-container');
    const beczkiCzysteContainer = document.getElementById('beczki-czyste-container');
    const alarmsContainer = document.getElementById('alarms-container');
    const lastUpdatedTime = document.getElementById('last-updated-time');
    const stockSummaryContainer = document.getElementById('stock-summary-container');

    const modals = {
        planTransfer: new bootstrap.Modal(document.getElementById('plan-transfer-modal')),
        startHeating: new bootstrap.Modal(document.getElementById('start-heating-modal')),
        simulationSettings: new bootstrap.Modal(document.getElementById('simulation-settings-modal')),
        transferTankToTank: new bootstrap.Modal(document.getElementById('transfer-tank-to-tank-modal')) // NOWY MODAL
    };
    const forms = {
        planTransfer: document.getElementById('plan-transfer-form'),
        startHeating: document.getElementById('start-heating-form'),
        simulationSettings: document.getElementById('simulation-settings-form'),
        transferTankToTank: document.getElementById('transfer-tank-to-tank-form') // NOWY FORMULARZ
    };
    
    // --- SOCKET.IO ---
    const socket = io();
    socket.on('connect', () => console.log("Połączono z dashboardem przez WebSocket."));
    
    socket.on('dashboard_update', (data) => {
        console.log("Otrzymano aktualizację dashboardu:", data);
        latestDashboardData = data; // Zapisz najnowsze dane
        updateUI(data);
    });

    // --- GŁÓWNA FUNKCJA AKTUALIZUJĄCA UI ---
    function updateUI(data) {
        renderReaktory(data.all_reactors);
        renderBeczki(data.beczki_brudne, beczkiBrudneContainer, true);
        renderBeczki(data.beczki_czyste, beczkiCzysteContainer, false);
        renderAlarms(data.alarmy);
        renderStockSummary(data.stock_summary);
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
            // W przyszłości można tu dodać inne warunki:
            // else if (r.partia && r.partia.process_status === 'OCZEKUJE_NA_OCENE') { ... }
            
            
            // --- Logika dla pasków postępu (bez zmian) ---
            
            
            let tempPercent = (r.temperatura_aktualna && r.temperatura_max) ? (r.temperatura_aktualna / r.temperatura_max) * 100 : 0;
            let tempColorClass = 'bg-success';
            if (tempPercent > 95) tempColorClass = 'bg-danger';
            else if (tempPercent > 80) tempColorClass = 'bg-warning';
            const tempProgressBar = `<div class="progress" style="height: 10px;"><div class="progress-bar ${tempColorClass}" role="progressbar" style="width: ${tempPercent}%;"></div></div>`;
            
            let pressurePercent = (r.cisnienie_aktualne && r.cisnienie_max) ? (r.cisnienie_aktualne / r.cisnienie_max) * 100 : 0;
            let pressureColorClass = 'bg-success';
            if (pressurePercent > 95) pressureColorClass = 'bg-danger';
            else if (pressurePercent > 80) pressureColorClass = 'bg-warning';
            const pressureProgressBar = `<div class="progress" style="height: 10px;"><div class="progress-bar ${pressureColorClass}" role="progressbar" style="width: ${pressurePercent}%;"></div></div>`;
            
            // --- Logika dla przełącznika palnika (bez zmian) ---
            const isBurnerOn = r.stan_palnika === 'WLACZONY';
            const burnerSwitchHTML = `
                <div class="form-check form-switch mt-3">
                    <input class="form-check-input action-btn" type="checkbox" role="switch" id="burner-switch-${r.id}"
                           data-action="toggle-burner" data-sprzet-id="${r.id}" ${isBurnerOn ? 'checked' : ''}>
                    <label class="form-check-label" for="burner-switch-${r.id}">
                        Palnik ${isBurnerOn ? '<span class="text-success fw-bold">WŁĄCZONY</span>' : '<span class="text-muted">WYŁĄCZONY</span>'}
                    </label>
                </div>`;
            
            // --- Logika dla statusu i partii (bez zmian) ---
            const statusClass = r.stan_sprzetu === 'W transferze' ? 'status-alarm' : (r.partia ? 'status-ok' : 'status-idle');
            
            // --- NOWA, POPRAWIONA LOGIKA DLA WAGI ---
            const wagaHTML = r.partia ? `<p><strong>Waga:</strong> ${(r.partia.waga_kg/1000).toFixed(1)} t</p>` : '';

        // --- ZMODYFIKOWANA LOGIKA DLA TYPU MATERIAŁU ---
        let materialTypeHTML = '';
        if (r.partia && r.partia.sklad && r.partia.sklad.length > 0) {
            const materialTypes = [...new Set(r.partia.sklad.map(item => item.material_type))];
            const materialTypesText = materialTypes.join(' + '); // Łącznik dla mieszanin
            materialTypeHTML = `
                <div class="text-center bg-light p-2 rounded mb-3">
                    <h4 class="mb-0 text-primary fw-bold">${materialTypesText}</h4>
                </div>
            `;
        }

        // --- Kompletny szablon karty ---
        const cardHTML = `
            <div class="col-xl-4 col-lg-6 mb-4">
                <div class="card h-100 card-reaktor">
                    <div class="card-header d-flex justify-content-between">
                        <h5 class="mb-0"><span class="status-indicator ${statusClass}"></span>${r.nazwa}</h5>
                        <span class="badge bg-info text-dark">${r.stan_sprzetu || 'Brak stanu'}</span>
                    </div>
                    <div class="card-body">
                        ${materialTypeHTML}
                        <p><strong>Partia:</strong> ${r.partia ? r.partia.kod : '<em>Pusty</em>'}</p>
                        ${wagaHTML}
                        <p class="mb-1"><strong>Temperatura:</strong> ${r.temperatura_aktualna ? r.temperatura_aktualna.toFixed(2) : 'N/A'}°C / ${r.temperatura_docelowa || 'N/A'}°C</p>
                        ${tempProgressBar}
                        
                        <p class="mb-1 mt-3"><strong>Ciśnienie:</strong> ${r.cisnienie_aktualne || 'N/A'} bar</p>
                        ${pressureProgressBar}
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
            container.innerHTML = '<div class="list-group-item">Brak danych.</div>';
            return;
        }
        beczki.forEach(b => {
            // Zawsze pokazuj przycisk transferu dla wszystkich beczek
            const transferButtonHTML = `
                <button class="btn btn-sm btn-info mt-2 action-btn"
                         data-action="open-transfer-modal"
                         data-sprzet-id="${b.id}"
                         data-sprzet-nazwa="${b.nazwa}"
                         data-partia-waga="${b.partia ? b.partia.waga_kg : '0'}">
                    <i class="fas fa-exchange-alt me-1"></i> Przelej
                 </button>`;

            // NOWA LOGIKA: Wyświetlanie typu materiału
            let materialTypeHTML = '';
            if (b.partia && b.partia.sklad && b.partia.sklad.length > 0) {
                const materialTypes = [...new Set(b.partia.sklad.map(item => item.material_type))];
                const materialTypesText = materialTypes.join(' + ');
                materialTypeHTML = `
                    <div class="text-center bg-light p-1 rounded mt-2 mb-1">
                        <strong class="text-primary">${materialTypesText}</strong>
                    </div>
                `;
            }

            const itemHTML = `
                <div class="list-group-item">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${b.nazwa}</h6>
                        <small>${b.stan_sprzetu}</small>
                    </div>
                    ${materialTypeHTML}
                    <p class="mb-1">
                        ${b.partia ? `Zawartość: <strong>${b.partia.kod}</strong> (${(b.partia.waga_kg/1000).toFixed(1)} t)` : '<em>Pusta</em>'}
                    </p>
                    ${transferButtonHTML}
                </div>`;
            container.innerHTML += itemHTML;
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
            <table class="table table-sm table-bordered">
                <thead class="table-light">
                    <tr>
                        <th>Typ Surowca</th>
                        <th class="text-end">Strefa Brudna (t)</th>
                        <th class="text-end">W Reaktorach (t)</th>
                        <th class="text-end">Strefa Czysta (t)</th>
                        <th class="text-end fw-bold">Suma (t)</th>
                    </tr>
                </thead>
                <tbody>
        `;

        summaryData.sort((a, b) => a.material_type.localeCompare(b.material_type));

        let totalDirty = 0;
        let totalClean = 0;
        let totalReactors = 0;
        let grandTotal = 0;

        summaryData.forEach(item => {
            const dirtyTonnes = (item.dirty_stock_kg || 0) / 1000;
            const cleanTonnes = (item.clean_stock_kg || 0) / 1000;
            const reactorsTonnes = (item.reactors_stock_kg || 0) / 1000;
            const rowTotal = dirtyTonnes + cleanTonnes + reactorsTonnes;

            totalDirty += dirtyTonnes;
            totalClean += cleanTonnes;
            totalReactors += reactorsTonnes;
            grandTotal += rowTotal;

            tableHTML += `
                <tr>
                    <td><strong>${item.material_type}</strong></td>
                    <td class="text-end">${dirtyTonnes.toFixed(2)}</td>
                    <td class="text-end">${reactorsTonnes.toFixed(2)}</td>
                    <td class="text-end">${cleanTonnes.toFixed(2)}</td>
                    <td class="text-end fw-bold">${rowTotal.toFixed(2)}</td>
                </tr>
            `;
        });

        tableHTML += `
                </tbody>
                <tfoot class="table-group-divider">
                    <tr class="table-secondary fw-bold">
                        <td>SUMA CAŁKOWITA</td>
                        <td class="text-end">${totalDirty.toFixed(2)}</td>
                        <td class="text-end">${totalReactors.toFixed(2)}</td>
                        <td class="text-end">${totalClean.toFixed(2)}</td>
                        <td class="text-end bg-dark text-white">${grandTotal.toFixed(2)}</td>
                    </tr>
                </tfoot>
            </table>
        `;
        stockSummaryContainer.innerHTML = tableHTML;
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
    function showToast(message, type = 'info') {
        // Sprawdź czy Bootstrap Toast jest dostępny
        if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
            // Stwórz dynamicznie toast
            const toastHTML = `
                <div class="toast align-items-center text-white bg-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info'} border-0" role="alert" aria-live="assertive" aria-atomic="true">
                    <div class="d-flex">
                        <div class="toast-body">
                            ${message}
                        </div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                    </div>
                </div>
            `;
            
            const toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            toastContainer.style.zIndex = '9999';
            toastContainer.innerHTML = toastHTML;
            
            document.body.appendChild(toastContainer);
            
            const toastElement = toastContainer.querySelector('.toast');
            const toast = new bootstrap.Toast(toastElement);
            toast.show();
            
            // Usuń toast po zakończeniu
            toastElement.addEventListener('hidden.bs.toast', () => {
                document.body.removeChild(toastContainer);
            });
        } else {
            // Fallback - użyj alert jeśli Bootstrap nie jest dostępny
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