function toggleView(viewType) {
    const chartsView = document.getElementById('charts-view');
    const tableView = document.getElementById('table-view');
    const chartsBtn = document.getElementById('charts-btn');
    const tableBtn = document.getElementById('table-btn');
    
    if (viewType === 'charts') {
        chartsView.style.display = 'grid';
        tableView.style.display = 'none';
        chartsBtn.classList.add('active');
        tableBtn.classList.remove('active');
    } else {
        chartsView.style.display = 'none';
        tableView.style.display = 'block';
        chartsBtn.classList.remove('active');
        tableBtn.classList.add('active');
        updateMeasurementsTable();
    }
}

async function updateMeasurementsTable() {
    try {
        const response = await fetch('/api/pomiary/historia');
        const data = await response.json();
        
        const tbody = document.getElementById('measurements-tbody');
        tbody.innerHTML = data.map(pomiar => `
            <tr>
                <td>${pomiar.nazwa_unikalna}</td>
                <td>${pomiar.temperatura}°C</td>
                <td>${pomiar.cisnienie} bar</td>
                <td>${pomiar.czas_pomiaru}</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Błąd podczas aktualizacji tabeli pomiarów:', error);
        showToast('Błąd podczas ładowania danych pomiarowych', 'error');
    }
}

// Ten plik zawiera logikę JavaScript dla aplikacji MES Parafina

document.addEventListener('DOMContentLoaded', () => {

    // --- SEKCJA 1: STAŁE I ZMIENNE GLOBALNE ---

    const ALARM_CHECK_INTERVAL = 30000; // 30 sekund

    // Elementy DOM
    const sprzetContainer = document.getElementById('sprzet-container');
    const valvesContainer = document.getElementById('valves-container');
    const operationsTableBody = document.getElementById('operations-table-body');
    const visualizationContainer = document.querySelector('#visualization-section .mermaid');
    const flowchartContainer = document.getElementById('flowchart-container');
    const visualizationSection = document.getElementById('visualization-section');
    const flowchartSection = document.getElementById('flowchart-section');
    const temperatureForm = document.getElementById('temperature-form');
    const equipmentSelect = document.getElementById('equipment-select');
    // Formularz tras
    const routeForm = document.getElementById('route-form');
    const startPointSelect = document.getElementById('start-point');
    const intermediatePointSelect = document.getElementById('intermediate-point');
    const endPointSelect = document.getElementById('end-point');
    const valveSuggestionContainer = document.getElementById('valve-suggestion-container');
    const valveListDiv = document.getElementById('valve-list');
    const runOperationBtn = document.getElementById('run-operation-btn');
    
    // Formularz tankowania
    const tankingForm = document.getElementById('tanking-form');
    const tankingSourceSelect = document.getElementById('tanking-source');
    const tankingDestSelect = document.getElementById('tanking-dest');
    const tankingTypeInput = document.getElementById('tanking-type');
    const tankingWeightInput = document.getElementById('tanking-weight');

    // Formularz dobielania
    const bleachingForm = document.getElementById('bleaching-form');
    const bleachReactorSelect = document.getElementById('bleach-reactor');
    const bleachBagsInput = document.getElementById('bleach-bags');
    const bleachWeightInput = document.getElementById('bleach-weight');

    // Zmienne stanu
    let lastOperationData = {};
    let isMouseOverVisuals = false;
    let lastTopologyData = null;
    let lastMermaidDefinition = '';
    let lastFlowchartDefinition = '';
    let isHighlightActive = false;
    
    // --- SEKCJA 2: FUNKCJE POMOCNICZE ---

    async function updateFiltryStatus() {
    try {
        const response = await fetch('/api/filtry/status');
        const data = await response.json();

        // Logika do aktualizacji karty dla Filtra Zielonego
        const fz_data = data.find(f => f.nazwa_filtra === 'FZ');
        if (fz_data) {
            document.getElementById('fz-status').textContent = fz_data.stan_sprzetu;
            document.getElementById('fz-operacja').textContent = fz_data.typ_operacji || '---';
            document.getElementById('fz-partia').textContent = fz_data.nazwa_partii || '---';
            document.getElementById('fz-trasa').textContent = `${fz_data.sprzet_zrodlowy || '?'} -> ${fz_data.sprzet_docelowy || '?'}`;
            // Tutaj logika do obliczania i wyświetlania timera
        }

        // Logika do aktualizacji karty dla Filtra Niebieskiego
        const fn_data = data.find(f => f.nazwa_filtra === 'FN');
        if (fn_data) {
            // ... analogicznie jak dla FZ ...
        }

    } catch (error) {
        console.error("Błąd podczas aktualizacji statusu filtrów:", error);
    }
}

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
        Toastify(options).showToast();
    }

    async function populateSelect(selectElement, apiUrl, isFilter = false) {
        try {
            const response = await fetch(apiUrl);
            const data = await response.json();
            selectElement.innerHTML = '';
            if (isFilter) {
                selectElement.appendChild(new Option('-- Brak --', ''));
                data.forEach(item => selectElement.appendChild(new Option(item, item)));
            } else {
                data.forEach(item => selectElement.appendChild(new Option(`${item.nazwa_sprzetu} (${item.nazwa_portu})`, item.nazwa_portu)));
            }
        } catch (error) {
            showToast(`Błąd ładowania danych dla listy: ${error.message}`, 'error');
        }
    }

    // --- SEKCJA 3: FUNKCJE POBIERAJĄCE I WYŚWIETLAJĄCE DANE ---

    async function fetchAndDisplayStatus() {
        if (isMouseOverVisuals) return;
        try {
            const response = await fetch('/api/sprzet');
            const sprzetList = await response.json();
            sprzetContainer.innerHTML = ''; 
            sprzetList.forEach(item => {
                const div = document.createElement('div');
                div.className = 'sprzet-item';
                let innerHTML = `<strong>${item.nazwa_unikalna}</strong> (${item.typ_sprzetu})<br><span>${item.stan_sprzetu || 'Brak stanu'}</span>`;
                if (item.id_partii) {
                    innerHTML += `<div class="partia-info">
                                    <hr>
                                    <strong>Partia:</strong> ${item.unikalny_kod}<br>
                                    <strong>Typ:</strong> ${item.typ_surowca}<br>
                                    <strong>Waga:</strong> ${item.waga_aktualna_kg} kg<br>
                                    <strong>Statusy:</strong> <span class="status-tags">${item.statusy_partii || 'Brak'}</span>
                                  </div>`;
                }
                div.innerHTML = innerHTML;
                sprzetContainer.appendChild(div);
            });
        } catch (error) {
            showToast(`Błąd ładowania sprzętu: ${error.message}`, 'error');
        }
    }

    async function fetchAndDisplayValves() {
        if (isMouseOverVisuals) return;
        try {
            const response = await fetch('/api/zawory');
            const valves = await response.json();
            valvesContainer.innerHTML = '';
            valves.forEach(valve => {
                const div = document.createElement('div');
                div.className = `valve-item ${valve.stan.toLowerCase()}`;
                div.innerHTML = `<strong>${valve.nazwa_zaworu}</strong>`;
                div.dataset.id = valve.id;
                div.dataset.stan = valve.stan;
                valvesContainer.appendChild(div);
            });
        } catch (error) {
            showToast(`Błąd ładowania zaworów: ${error.message}`, 'error');
        }
    }

    async function fetchAndDisplayActiveOperations() {
        if (isMouseOverVisuals) return;
        try {
            const response = await fetch('/api/operations/aktywne');
            const operations = await response.json();
            operationsTableBody.innerHTML = '';
            if (operations.length === 0) {
                operationsTableBody.innerHTML = '<tr><td colspan="6" style="text-align: center;">Brak aktywnych operacji.</td></tr>';
            } else {
                operations.forEach(op => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${op.id}</td>
                        <td>${op.typ_operacji}</td>
                        <td>${op.id_partii_surowca || 'B/D'}</td>
                        <td>${op.czas_rozpoczecia}</td>
                        <td>${op.opis}</td>
                        <td><button class="end-operation-btn" data-op-id="${op.id}">Zakończ</button></td>
                    `;
                    operationsTableBody.appendChild(row);
                });
            }
        } catch (error) {
            showToast(`Błąd ładowania operacji: ${error.message}`, 'error');
        }
    }

    // --- SEKCJA 4: FUNKCJE WIZUALIZACJI (MERMAID) ---

    function renderDiagram(container, definition) {
        if (!definition) return;
        container.innerHTML = definition;
        container.removeAttribute('data-processed');
        mermaid.init(undefined, container);
    }

    function renderMermaid(topologyData, highlight = {}, useFlowchart = false) {
        let definition = 'graph TD;\n\n';
        const styles = {
            sugerowany: 'stroke:#3498db,stroke-width:4px',
            zajety: 'stroke:#d35400,stroke-width:4px',
            otwarty: 'stroke:#2ecc71,stroke-width:2px',
            zamkniety: 'stroke:#c0392b,stroke-width:2px,stroke-dasharray: 5 5'
        };

        if (useFlowchart) {
            const nodeDefinitions = {};
            topologyData.forEach(seg => {
                [seg.punkt_startowy, seg.punkt_koncowy].forEach(point => {
                    if (point && !nodeDefinitions[point]) {
                        const cleanName = point.replace(/[^a-zA-Z0-9_]/g, '_');
                        let shape = ['([', '])']; // Domyślnie węzeł
                        if (point.startsWith('R')) shape = ['[', ']'];
                        else if (point.startsWith('F')) shape = ['[/', '/]'];
                        else if (point.startsWith('B') || point.startsWith('Ap')) shape = ['[(', ')]'];
                        nodeDefinitions[point] = `    ${cleanName}${shape[0]}"${point}"${shape[1]};\n`;
                    }
                });
            });
            for (const key in nodeDefinitions) {
                definition += nodeDefinitions[key];
            }
        }

        let linkStyleDefinitions = '';
        topologyData.forEach((seg, index) => {
            const start = (seg.punkt_startowy || 'N_S').replace(/[^a-zA-Z0-9_]/g, '_');
            const end = (seg.punkt_koncowy || 'N_K').replace(/[^a-zA-Z0-9_]/g, '_');
            definition += `    ${start} -- "${seg.nazwa_segmentu}" --> ${end}\n`;

            let styleKey = 'zamkniety';
            if (highlight.segmenty && highlight.segmenty.includes(seg.nazwa_segmentu)) styleKey = 'sugerowany';
            else if (seg.zajety) styleKey = 'zajety';
            else if (seg.stan_zaworu === 'OTWARTY') styleKey = 'otwarty';
            linkStyleDefinitions += `    linkStyle ${index} ${styles[styleKey]};\n`;
        });
        
        return definition + '\n' + linkStyleDefinitions;
    }

    async function refreshVisualizations(highlight = {}) {
        if (isHighlightActive && Object.keys(highlight).length === 0) return;

        if (isMouseOverVisuals && Object.keys(highlight).length === 0) return;
        
        try {
            if (!lastTopologyData || Object.keys(highlight).length === 0) {
                const response = await fetch('/api/topologia');
                lastTopologyData = await response.json();
            }
            
            lastMermaidDefinition = renderMermaid(lastTopologyData, highlight, false);
            renderDiagram(visualizationContainer, lastMermaidDefinition);

            lastFlowchartDefinition = renderMermaid(lastTopologyData, highlight, true);
            renderDiagram(flowchartContainer, lastFlowchartDefinition);
        } catch (error) {
            showToast(`Błąd rysowania diagramów: ${error.message}`, 'error');
        }
    }
    
    // --- SEKCJA 5: OBSŁUGA ZDARZEŃ (HANDLERY) ---

    async function findSuggestedRoute(event) {
        event.preventDefault();
        showToast('Szukam sugerowanej trasy...', 'info');
        valveSuggestionContainer.style.display = 'none';
        refreshVisualizations(); // Anulowanie podświetlenia

        const routeData = {
            start: startPointSelect.value,
            cel: endPointSelect.value,
            sprzet_posredni: intermediatePointSelect.value || null
        };
        
        try {
            const response = await fetch('/api/trasy/sugeruj', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(routeData)
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message);

            refreshVisualizations({ segmenty: result.segmenty_trasy }); // Podświetl trasę

            valveListDiv.innerHTML = result.sugerowane_zawory.map(v => `<span>${v}</span>`).join('<br>');
            valveSuggestionContainer.style.display = 'block';

            lastOperationData = {
                ...routeData,
                otwarte_zawory: result.sugerowane_zawory,
                typ_operacji: `DYNAMIC_${routeData.start}_${routeData.cel}`
            };
            
            showToast('Trasa znaleziona. Sprawdź i uruchom operację.', 'success');
        } catch (error) {
            showToast(`Błąd znajdowania trasy: ${error.message}`, 'error');
            refreshVisualizations();
        }
    }

    async function runOperation() {
        if (!lastOperationData.start) {
            showToast('Błąd: Najpierw znajdź trasę.', 'error');
            return;
        }
        showToast(`Uruchamiam operację: ${lastOperationData.typ_operacji}`, 'info');
        
        try {
            const response = await fetch('/api/operacje/rozpocznij_trase', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(lastOperationData)
            });
            const result = await response.json();
            
            if (response.ok) {
                showToast(`SUKCES: ${result.message}`, 'success');
                valveSuggestionContainer.style.display = 'none';
                updateAllViews();
            } else {
                showToast(`BŁĄD (${response.status}): ${result.message}`, 'error');
                if(result.zajete_segmenty) showToast(`Konflikt: ${result.zajete_segmenty.join(', ')}`, 'error');
            }
        } catch(error) {
            showToast(`Błąd sieciowy: ${error.message}`, 'error');
        }
    }

    async function handleValveClick(event) {
        const valveDiv = event.target.closest('.valve-item');
        if (!valveDiv) return;
        const valveId = parseInt(valveDiv.dataset.id);
        const newStan = valveDiv.dataset.stan === 'OTWARTY' ? 'ZAMKNIETY' : 'OTWARTY';
        
        try {
            await fetch('/api/zawory/zmien_stan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id_zaworu: valveId, stan: newStan })
            });
            fetchAndDisplayValves(); // Szybkie odświeżenie tylko zaworów
        } catch (error) {
            showToast(`Błąd zmiany stanu zaworu: ${error.message}`, 'error');
        }
    }

    async function handleEndOperationClick(event) {
        if (!event.target.classList.contains('end-operation-btn')) return;
        const operationId = parseInt(event.target.dataset.opId);
        if (!confirm(`Czy na pewno chcesz zakończyć operację o ID ${operationId}?`)) return;

        try {
            const response = await fetch('/api/operacje/zakoncz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id_operacji: operationId })
            });
            const result = await response.json();
            if (response.ok) showToast(`SUKCES: ${result.message}`, 'success');
            else showToast(`BŁĄD (${response.status}): ${result.message}`, 'error');
            updateAllViews();
        } catch (error) {
            showToast(`Błąd sieciowy: ${error.message}`, 'error');
        }
    }

    async function handleTankingSubmit(event) {
        event.preventDefault();
        let response;
        
        const tankingData = {
            nazwa_portu_zrodlowego: tankingSourceSelect.value,
            nazwa_portu_docelowego: tankingDestSelect.value,
            typ_surowca: tankingTypeInput.value,
            waga_kg: parseFloat(tankingWeightInput.value),
            zrodlo_pochodzenia: 'apollo'
        };

        // Walidacja
        if (!tankingData.nazwa_portu_zrodlowego || !tankingData.nazwa_portu_docelowego || 
            !tankingData.typ_surowca || isNaN(tankingData.waga_kg)) {
            showToast('Wszystkie pola w formularzu tankowania są wymagane!', 'error');
            return;
        }

        console.log('Wysyłam dane:', tankingData); // Debug log
        showToast('Rozpoczynam tankowanie...', 'info');
        
        try {
            response = await fetch('/api/operacje/tankowanie', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(tankingData)
            });

            // Próbujemy najpierw pobrać tekst odpowiedzi
            const responseText = await response.text();
            console.log('Odpowiedź serwera:', responseText); // Debug log

            // Próbujemy sparsować JSON tylko jeśli to możliwe
            let result;
            try {
                result = JSON.parse(responseText);
            } catch (e) {
                throw new Error(`Nieprawidłowa odpowiedź serwera: ${responseText}`);
            }

            if (response.ok) {
                showToast(`SUKCES: ${result.message}`, 'success');
                tankingForm.reset();
                await updateAllViews();
            } else {
                let errorMessage = result.message || 'Nieznany błąd';
                if (response.status === 500) {
                    errorMessage = `Błąd serwera: ${result.message || responseText}`;
                    console.error('Szczegóły błędu:', result);
                }
                showToast(`BŁĄD (${response.status}): ${errorMessage}`, 'error');
            }
        } catch(error) {
            console.error('Pełny błąd:', error);
            showToast(`Błąd operacji: ${error.message}`, 'error');
        }
    }
    
    async function handleBleachingSubmit(event) {
    event.preventDefault(); // Zapobiegaj przeładowaniu strony
    
    // Zbieramy dane z formularza
    const bleachingData = {
        id_reaktora: parseInt(bleachReactorSelect.value),
        ilosc_workow: parseInt(bleachBagsInput.value),
        waga_worka_kg: parseFloat(bleachWeightInput.value)
    };

    // Prosta walidacja
    if (!bleachingData.id_reaktora) {
        showToast('Proszę wybrać reaktor do dobielania!', 'error');
        return;
    }

    showToast('Dodaję ziemię bielącą...', 'info');
    try {
        const response = await fetch('/api/operacje/dobielanie', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(bleachingData)
        });
        const result = await response.json();

        if (response.ok) {
            showToast(`SUKCES: ${result.message}`, 'success');
            bleachingForm.reset(); // Wyczyść formularz
            updateAllViews(); // Odśwież widok, aby zobaczyć zmiany w wadze i statusie
        } else {
            showToast(`BŁĄD (${response.status}): ${result.message}`, 'error');
        }
    } catch(error) {
        showToast(`Błąd sieciowy: ${error.message}`, 'error');
    }
}
async function confirmAlarm(alarmId) {
    try {
        const response = await fetch('/api/alarmy/potwierdz', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id_alarmu: alarmId })
        });

        const result = await response.json();
        
        if (response.ok) {
            showToast('Alarm potwierdzony', 'success');
            // Odśwież widok alarmów
            checkAlarms();
        } else {
            showToast(`Błąd potwierdzania alarmu: ${result.message}`, 'error');
        }
    } catch (error) {
        console.error('Błąd podczas potwierdzania alarmu:', error);
        showToast('Błąd podczas potwierdzania alarmu', 'error');
    }
}
    async function checkAlarms() {
    try {
        const alarmContainer = document.getElementById('alarm-container');
        if (!alarmContainer) {
            console.error('Element alarm-container not found!');
            return;
        }

        const response = await fetch('/api/alarmy/aktywne');
        const alarmy = await response.json();
        
        if (alarmy.length > 0) {
            alarmContainer.innerHTML = alarmy.map(alarm => `
                <div class="alarm-item ${alarm.status_alarmu.toLowerCase()}">
                    <span class="alarm-type">${alarm.typ_alarmu}</span>
                    <span class="alarm-equipment">${alarm.nazwa_sprzetu}</span>
                    <span class="alarm-value">${alarm.wartosc} / ${alarm.limit_przekroczenia}</span>
                    <span class="alarm-time">${alarm.czas_wystapienia}</span>
                    ${alarm.status_alarmu === 'AKTYWNY' ? 
                        `<button class="confirm-alarm-btn" data-alarm-id="${alarm.id}">Potwierdź</button>` : ''}
                </div>
            `).join('');

            // Add event listeners for confirm buttons
            const confirmButtons = alarmContainer.querySelectorAll('.confirm-alarm-btn');
            confirmButtons.forEach(btn => {
                btn.addEventListener('click', () => confirmAlarm(btn.dataset.alarmId));
            });
        } else {
            alarmContainer.innerHTML = '<p class="no-alarms">Brak aktywnych alarmów</p>';
        }
    } catch (error) {
        console.error('Błąd podczas sprawdzania alarmów:', error);
        showToast('Błąd podczas sprawdzania alarmów', 'error');
    }
}
    
    function getPointBackgroundColor(value, limit) {
    return value > limit ? 'rgba(255, 99, 132, 0.5)' : 'rgba(54, 162, 235, 0.2)';
    }

    async function loadSensorHistory() {
    try {
        console.log('Rozpoczynam ładowanie historii pomiarów...');
        
        const response = await fetch('/api/pomiary/historia');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Otrzymane dane:', data);

        if (!data || data.length === 0) {
            console.log('Brak danych pomiarowych');
            return;
        }

        const tempContainer = document.getElementById('temperature-charts');
        const pressContainer = document.getElementById('pressure-charts');
        tempContainer.innerHTML = '';
        pressContainer.innerHTML = '';

        // Grupuj dane według sprzętu
        const groupedData = data.reduce((acc, pomiar) => {
            if (!acc[pomiar.nazwa_unikalna]) {
                acc[pomiar.nazwa_unikalna] = {
                    temperatury: [],
                    cisnienia: [],
                    czasy: [],
                    temperatura_max: pomiar.temperatura_max || 90, // Default max temp
                    cisnienie_max: pomiar.cisnienie_max || 6     // Default max pressure
                };
                
                tempContainer.innerHTML += `
                    <div class="chart-wrapper">
                        <h3>Temperatura - ${pomiar.nazwa_unikalna}</h3>
                        <canvas id="chart-temp-${pomiar.nazwa_unikalna}"></canvas>
                    </div>`;
                
                pressContainer.innerHTML += `
                    <div class="chart-wrapper">
                        <h3>Ciśnienie - ${pomiar.nazwa_unikalna}</h3>
                        <canvas id="chart-press-${pomiar.nazwa_unikalna}"></canvas>
                    </div>`;
            }
            
            acc[pomiar.nazwa_unikalna].temperatury.push(pomiar.temperatura);
            acc[pomiar.nazwa_unikalna].cisnienia.push(pomiar.cisnienie);
            acc[pomiar.nazwa_unikalna].czasy.push(pomiar.czas_pomiaru);
            return acc;
        }, {});

        // Twórz wykresy
        Object.entries(groupedData).forEach(([nazwa, dane]) => {
            try {
                new Chart(
                    document.getElementById(`chart-temp-${nazwa}`),
                    {
                        type: 'line',
                        data: {
                            labels: dane.czasy,
                            datasets: [{
                                label: 'Temperatura [°C]',
                                data: dane.temperatury,
                                borderColor: 'rgb(255, 99, 132)',
                                backgroundColor: dane.temperatury.map(t => 
                                    getPointBackgroundColor(t, dane.temperatura_max)
                                ),
                                tension: 0.1,
                                pointRadius: 5
                            }]
                        },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: { position: 'top' },
                                tooltip: {
                                    callbacks: {
                                        label: function(context) {
                                            return `Temperatura: ${context.raw}°C`;
                                        }
                                    }
                                }
                            }
                        }
                    }
                );

                new Chart(
                    document.getElementById(`chart-press-${nazwa}`),
                    {
                        type: 'line',
                        data: {
                            labels: dane.czasy,
                            datasets: [{
                                label: 'Ciśnienie [bar]',
                                data: dane.cisnienia,
                                borderColor: 'rgb(54, 162, 235)',
                                backgroundColor: dane.cisnienia.map(p => 
                                    getPointBackgroundColor(p, dane.cisnienie_max)
                                ),
                                tension: 0.1,
                                pointRadius: 5
                            }]
                        },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: { position: 'top' },
                                tooltip: {
                                    callbacks: {
                                        label: function(context) {
                                            return `Ciśnienie: ${context.raw} bar`;
                                        }
                                    }
                                }
                            }
                        }
                    }
                );
            } catch (chartError) {
                console.error(`Błąd podczas tworzenia wykresu dla ${nazwa}:`, chartError);
            }
        });
        
    } catch (error) {
        console.error('Szczegóły błędu:', error);
        showToast('Błąd podczas ładowania historii pomiarów: ' + error.message, 'error');
    }
}
    // --- SEKCJA 6: INICJALIZACJA ---

    // Jedna funkcja do odświeżania wszystkiego, co nie jest wizualizacją
    function updateAllViews() {
        fetchAndDisplayStatus();
        fetchAndDisplayValves();
        fetchAndDisplayActiveOperations();
        refreshVisualizations();
    }
    
    // Podpięcie eventów
    routeForm.addEventListener('submit', findSuggestedRoute);
    runOperationBtn.addEventListener('click', runOperation);
    valvesContainer.addEventListener('click', handleValveClick);
    operationsTableBody.addEventListener('click', handleEndOperationClick);
    tankingForm.addEventListener('submit', handleTankingSubmit);
    bleachingForm.addEventListener('submit', handleBleachingSubmit);
    visualizationSection.addEventListener('mouseenter', () => { isMouseOverVisuals = true; });
    visualizationSection.addEventListener('mouseleave', () => { isMouseOverVisuals = false; });
    flowchartSection.addEventListener('mouseenter', () => { isMouseOverVisuals = true; });
    flowchartSection.addEventListener('mouseleave', () => { isMouseOverVisuals = false; });

    // Inicjalizacja selectów
    populateSelect(startPointSelect, '/api/punkty_startowe');
    populateSelect(endPointSelect, '/api/punkty_docelowe');
    populateSelect(intermediatePointSelect, '/api/sprzet/filtry', true);
    populateSelect(tankingSourceSelect, '/api/punkty_startowe');
    populateSelect(tankingDestSelect, '/api/punkty_docelowe');
    
    // Inicjalizacja selecta z reaktorami (potrzebuje innej logiki)
    async function populateReactorsForBleaching() {
        try {
            const response = await fetch('/api/sprzet');
            const sprzetList = await response.json();
            bleachReactorSelect.innerHTML = '<option value="">-- Wybierz --</option>';
            sprzetList.filter(s => s.typ_sprzetu === 'reaktor').forEach(r => {
                bleachReactorSelect.appendChild(new Option(r.nazwa_unikalna, r.id));
            });
        } catch(e) { /* ... */ }
    }

 async function loadEquipment() {
        try {
            const response = await fetch('/api/sprzet');
            const equipment = await response.json();
            
            equipmentSelect.innerHTML = equipment
                .filter(item => item.stan_sprzetu !== 'Wyłączony')
                .map(item => `
                    <option value="${item.id}">${item.nazwa_unikalna}</option>
                `).join('');
        } catch (error) {
            console.error('Błąd podczas ładowania listy sprzętu:', error);
            showToast('Nie udało się załadować listy sprzętu', 'error');
        }
    }

    // Handle temperature form submission
    temperatureForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        
        const sprzet_id = equipmentSelect.value;
        const temperatura = document.getElementById('temperature-input').value;
        
        try {
            const response = await fetch(`/api/sprzet/${sprzet_id}/temperatura`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ temperatura: parseFloat(temperatura) })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                showToast(`Ustawiono temperaturę ${temperatura}°C`, 'success');
            } else {
                showToast(result.message, 'error');
            }
        } catch (error) {
            console.error('Błąd podczas ustawiania temperatury:', error);
            showToast('Nie udało się ustawić temperatury', 'error');
        }
    });

    populateReactorsForBleaching();
    
    // Pierwsze załadowanie i cykliczne odświeżanie
    updateAllViews();
    setInterval(updateAllViews, 15000); // Ustawmy jeden, rozsądny interwał na wszystko
    setInterval(checkAlarms, ALARM_CHECK_INTERVAL);
    checkAlarms(); // Pierwsze sprawdzenie
    loadSensorHistory();
    setInterval(loadSensorHistory, 300000);
    loadEquipment();
    updateFiltryStatus();
    setInterval(updateFiltryStatus, 10000);

    // --- SEKCJA 7: OBSŁUGA WIDOKÓW POMIARÓW ---

});