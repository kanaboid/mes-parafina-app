// Ten plik zawiera logikę JavaScript dla aplikacji MES Parafina

document.addEventListener('DOMContentLoaded', () => {

    // --- SEKCJA 1: Deklaracja stałych dla elementów DOM ---
    const sprzetContainer = document.getElementById('sprzet-container');
    const valvesContainer = document.getElementById('valves-container');
    const operationsTableBody = document.getElementById('operations-table-body');
    const visualizationContainer = document.querySelector('#visualization-section .mermaid');
    const flowchartContainer = document.getElementById('flowchart-container');
    const visualizationSection = document.getElementById('visualization-section');
    const flowchartSection = document.getElementById('flowchart-section');

    const routeForm = document.getElementById('route-form');
    const startPointSelect = document.getElementById('start-point');
    const intermediatePointSelect = document.getElementById('intermediate-point');
    const endPointSelect = document.getElementById('end-point');
    const valveSuggestionContainer = document.getElementById('valve-suggestion-container');
    const valveListDiv = document.getElementById('valve-list');
    const runOperationBtn = document.getElementById('run-operation-btn');

    const tankingForm = document.getElementById('tanking-form');
    const tankingSourceSelect = document.getElementById('tanking-source');
    const tankingDestSelect = document.getElementById('tanking-dest');
    const tankingTypeInput = document.getElementById('tanking-type');
    const tankingWeightInput = document.getElementById('tanking-weight');

    const bleachingForm = document.getElementById('bleaching-form');
    const bleachReactorSelect = document.getElementById('bleach-reactor');
    const bleachBagsInput = document.getElementById('bleach-bags');
    const bleachWeightInput = document.getElementById('bleach-weight');

    // --- SEKCJA 2: Zmienne stanu aplikacji ---
    let lastOperationData = {}; // Przechowuje dane dla operacji, która ma być uruchomiona
    let isMouseOverVisuals = false; // Zapobiega odświeżaniu diagramów, gdy kursor jest nad nimi
    let lastTopologyData = null; // Cache dla danych o topologii, aby unikać zbędnych zapytań API

    // --- SEKCJA 3: Funkcje pomocnicze ---

    function showToast(message, type = 'info') {
        const options = {
            text: message,
            duration: 3000,
            gravity: "top",
            position: "right",
            stopOnFocus: true,
        };
        if (type === 'success') {
            options.style = { background: "linear-gradient(to right, #00b09b, #96c93d)" };
        } else if (type === 'error') {
            options.style = { background: "linear-gradient(to right, #ff5f6d, #ffc371)" };
        }
        Toastify(options).showToast();
    }

    async function populateSelect(selectElement, apiUrl, options = {}) {
        try {
            const response = await fetch(apiUrl);
            const data = await response.json();
            
            // Zachowaj aktualną wartość, jeśli istnieje
            const currentValue = selectElement.value;
            selectElement.innerHTML = '';
            
            if (options.isFilter) {
                selectElement.appendChild(new Option('-- Brak --', ''));
            } else if (options.isReactorList) {
                selectElement.appendChild(new Option('-- Wybierz reaktor --', ''));
            }

            data.forEach(item => {
                let text, value;
                if(options.isFilter) {
                    text = item; value = item;
                } else if (options.isReactorList) {
                    text = item.nazwa_unikalna; value = item.id;
                } else {
                    text = `${item.nazwa_sprzetu} (${item.nazwa_portu})`; value = item.nazwa_portu;
                }
                selectElement.appendChild(new Option(text, value));
            });
            // Przywróć poprzednią wartość, jeśli to możliwe
            selectElement.value = currentValue;

        } catch (error) {
            showToast(`Błąd ładowania listy: ${error.message}`, 'error');
        }
    }
    
    // --- SEKCJA 4: Funkcje renderujące widoki ---
    
    function renderDiagram(container, definition) {
        if (!container || !definition) return;
        container.innerHTML = definition;
        container.removeAttribute('data-processed');
        mermaid.init(undefined, container);
    }
    
    function generateMermaidCode(topology, highlight = {}, useFlowchart = false) {
        let definition = 'graph TD;\n\n';
        const styles = {
            sugerowany: 'stroke:#3498db,stroke-width:4px',
            zajety: 'stroke:#d35400,stroke-width:4px',
            otwarty: 'stroke:#2ecc71,stroke-width:2px',
            zamkniety: 'stroke:#c0392b,stroke-width:2px,stroke-dasharray: 5 5'
        };

        if (useFlowchart) {
            const nodeDefinitions = {};
            topology.forEach(seg => {
                [seg.punkt_startowy, seg.punkt_koncowy].forEach(point => {
                    if (point && !nodeDefinitions[point]) {
                        const cleanName = point.replace(/[^a-zA-Z0-9_]/g, '_');
                        let shape = ['([', '])']; // Węzeł
                        if (point.startsWith('R')) shape = ['[', ']']; // Reaktor
                        else if (point.startsWith('F')) shape = ['[/', '/]']; // Filtr
                        else if (point.startsWith('B') || point.startsWith('Ap')) shape = ['[(', ')]']; // Beczka
                        nodeDefinitions[point] = `    ${cleanName}${shape[0]}"${point}"${shape[1]};\n`;
                    }
                });
            });
            for (const key in nodeDefinitions) {
                definition += nodeDefinitions[key];
            }
        }
        
        let linkStyleDefinitions = '';
        topology.forEach((seg, index) => {
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
        if (isMouseOverVisuals && Object.keys(highlight).length === 0) return;
        try {
            if (!lastTopologyData || Object.keys(highlight).length === 0) {
                const response = await fetch('/api/topologia');
                lastTopologyData = await response.json();
            }
            const graphDef = generateMermaidCode(lastTopologyData, highlight, false);
            renderDiagram(visualizationContainer, graphDef);
            const flowchartDef = generateMermaidCode(lastTopologyData, highlight, true);
            renderDiagram(flowchartContainer, flowchartDef);
        } catch (error) {
            showToast(`Błąd rysowania diagramów: ${error.message}`, 'error');
        }
    }
    
    // --- SEKCJA 5: Główna logika (pobieranie danych i obsługa zdarzeń) ---

    async function updateAllData() {
        if(isMouseOverVisuals) return;
        
        // Funkcje, które muszą być zawsze aktualne
        fetchAndDisplayStatus();
        fetchAndDisplayValves();
        fetchAndDisplayActiveOperations();
        refreshVisualizations(); // Odśwież diagramy ze standardowymi kolorami
    }

    // Handlery zdarzeń
    async function handleRouteSuggest(event) {
        event.preventDefault();
        showToast('Szukam sugerowanej trasy...', 'info');
        valveSuggestionContainer.style.display = 'none';
        refreshVisualizations(); // Anuluj poprzednie podświetlenie

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
    
    async function handleRunOperation() {
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
            } else {
                showToast(`BŁĄD (${response.status}): ${result.message}`, 'error');
                if(result.zajete_segmenty) showToast(`Konflikt: ${result.zajete_segmenty.join(', ')}`, 'error');
            }
            updateAllData(); // Zawsze odśwież widok po próbie
        } catch(error) {
            showToast(`Błąd sieciowy: ${error.message}`, 'error');
        }
    }
    
    // Pozostałe handlery... (skopiuj swoje działające wersje handleValveClick, handleEndOperationClick itd. tutaj)
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
            fetchAndDisplayValves();
            refreshVisualizations(); // Odśwież diagramy po zmianie zaworu
        } catch (error) { showToast(`Błąd zmiany stanu zaworu: ${error.message}`, 'error'); }
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
            updateAllData();
        } catch (error) { showToast(`Błąd sieciowy: ${error.message}`, 'error'); }
    }
    
    async function handleTankingSubmit(event) {
        event.preventDefault();
        const tankingData = {
            nazwa_portu_zrodlowego: tankingSourceSelect.value, // Zmieniamy na bardziej precyzyjne nazwy
            nazwa_portu_docelowego: tankingDestSelect.value,
            typ_surowca: tankingTypeInput.value,
            waga_kg: parseFloat(tankingWeightInput.value),
            zrodlo_pochodzenia: 'apollo'
        };
        try {
            const response = await fetch('/api/operacje/tankowanie', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(tankingData)
            });
            const result = await response.json();
            if (response.ok) { showToast(`SUKCES: ${result.message}`, 'success'); updateAllData(); }
            else { showToast(`BŁĄD (${response.status}): ${result.message}`, 'error'); }
        } catch(error) { showToast(`Błąd sieciowy: ${error.message}`, 'error'); }
    }
    
    async function handleBleachingSubmit(event) {
        event.preventDefault();
        const bleachingData = {
            id_reaktora: parseInt(bleachReactorSelect.value),
            ilosc_workow: parseInt(bleachBagsInput.value),
            waga_worka_kg: parseFloat(bleachWeightInput.value)
        };
        if (!bleachingData.id_reaktora) { showToast('Proszę wybrać reaktor!', 'error'); return; }
        try {
            const response = await fetch('/api/operacje/dobielanie', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(bleachingData)
            });
            const result = await response.json();
            if (response.ok) { showToast(`SUKCES: ${result.message}`, 'success'); updateAllData(); }
            else { showToast(`BŁĄD (${response.status}): ${result.message}`, 'error'); }
        } catch(error) { showToast(`Błąd sieciowy: ${error.message}`, 'error'); }
    }
    
    // --- SEKCJA 7: INICJALIZACJA APLIKACJI ---
    
    // Podpięcie event listenerów
    routeForm.addEventListener('submit', handleRouteSuggest);
    runOperationBtn.addEventListener('click', handleRunOperation);
    valvesContainer.addEventListener('click', handleValveClick);
    operationsTableBody.addEventListener('click', handleEndOperationClick);
    tankingForm.addEventListener('submit', handleTankingSubmit);
    bleachingForm.addEventListener('submit', handleBleachingSubmit);
    visualizationSection.addEventListener('mouseenter', () => { isMouseOverVisuals = true; });
    visualizationSection.addEventListener('mouseleave', () => { isMouseOverVisuals = false; });
    flowchartSection.addEventListener('mouseenter', () => { isMouseOverVisuals = true; });
    flowchartSection.addEventListener('mouseleave', () => { isMouseOverVisuals = false; });

    // Wypełnienie list rozwijanych
    populateSelect(startPointSelect, '/api/punkty_startowe');
    populateSelect(endPointSelect, '/api/punkty_docelowe');
    populateSelect(intermediatePointSelect, '/api/sprzet/filtry', { isFilter: true });
    populateSelect(tankingSourceSelect, '/api/punkty_startowe');
    populateSelect(tankingDestSelect, '/api/punkty_docelowe');
    
    // Specjalna logika dla listy reaktorów
    async function populateReactorsList() {
        try {
            const response = await fetch('/api/sprzet');
            const sprzetList = await response.json();
            const reaktory = sprzetList.filter(s => s.typ_sprzetu === 'reaktor');
            
            bleachReactorSelect.innerHTML = '<option value="">-- Wybierz --</option>';
            reaktory.forEach(r => {
                bleachReactorSelect.appendChild(new Option(r.nazwa_unikalna, r.id));
            });
        } catch(e) { showToast(`Błąd ładowania reaktorów: ${e.message}`, 'error'); }
    }
    populateReactorsList();
    
    // Pierwsze załadowanie danych i ustawienie cyklicznego odświeżania
    updateAllData();
    setInterval(updateAllData, 15000); // Odświeżaj wszystko co 15 sekund
});