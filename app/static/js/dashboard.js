// app/static/js/dashboard.js

document.addEventListener('DOMContentLoaded', () => {
    
    // --- ELEMENTY DOM, MODALE, FORMULARZE ---
    let latestDashboardData = {}; // Globalne przechowywanie danych
    const reaktoryContainer = document.getElementById('reaktory-container');
    const pusteReaktoryContainer = document.getElementById('puste-reaktory-container');
    const beczkiBrudneContainer = document.getElementById('beczki-brudne-container');
    const beczkiCzysteContainer = document.getElementById('beczki-czyste-container');
    const alarmsContainer = document.getElementById('alarms-container');
    const lastUpdatedTime = document.getElementById('last-updated-time');
    const stockSummaryContainer = document.getElementById('stock-summary-container');

    const modals = {
        planTransfer: new bootstrap.Modal(document.getElementById('plan-transfer-modal')),
        startHeating: new bootstrap.Modal(document.getElementById('start-heating-modal')),
        simulationSettings: new bootstrap.Modal(document.getElementById('simulation-settings-modal'))
    };
    const forms = {
        planTransfer: document.getElementById('plan-transfer-form'),
        startHeating: document.getElementById('start-heating-form'),
        simulationSettings: document.getElementById('simulation-settings-form')
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
        renderReaktory(data.reaktory_w_procesie); // <-- Użyj nowego klucza
        renderPusteReaktory(data.reaktory_puste);   // <-- Użyj nowego klucza
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
            reaktoryContainer.innerHTML = '<div class="col"><p class="text-muted">Brak reaktorów w aktywnym procesie.</p></div>';
            return;
        }

        reaktory.forEach(r => {
            
            // --- LOGIKA DLA PRZYCISKÓW ---
            let actionButtonsHTML = `
                <button class="btn btn-primary action-btn btn-lg" 
                        data-action="show-details" 
                        data-sprzet-id="${r.id}"
                        data-sprzet-nazwa="${r.nazwa}">
                    Szczegóły
                </button>
                <button class="btn btn-secondary action-btn btn-lg" 
                        data-action="open-simulation-settings" 
                        data-sprzet-id="${r.id}"
                        data-sprzet-nazwa="${r.nazwa}">
                    Ustawienia
                </button>
            `;
            
            // Sprawdź, czy należy dodać przycisk kontekstowy
            if (r.partia && r.partia.process_status === 'SUROWY') {
                actionButtonsHTML += `
                    <button class="btn btn-warning action-btn btn-lg" 
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

            // --- Kompletny szablon karty ---
            const cardHTML = `
                <div class="col-xl-4 col-lg-6 mb-4">
                    <div class="card h-100 card-reaktor">
                        <div class="card-header d-flex justify-content-between">
                            <h5 class="mb-0"><span class="status-indicator ${statusClass}"></span>${r.nazwa}</h5>
                            <span class="badge bg-info text-dark">${r.stan_sprzetu || 'Brak stanu'}</span>
                        </div>
                        <div class="card-body">
                            <p><strong>Partia:</strong> ${r.partia ? r.partia.kod : '<em>Pusty</em>'}</p>
                            ${wagaHTML} 
                            <p class="mb-1"><strong>Temperatura:</strong> ${r.temperatura_aktualna.toFixed(2)|| 'N/A'}°C / ${r.temperatura_docelowa || 'N/A'}°C</p>
                            ${tempProgressBar}
                            <p class="mb-1 mt-3"><strong>Ciśnienie:</strong> ${r.cisnienie_aktualne || 'N/A'} bar</p>
                            ${pressureProgressBar}
                            ${burnerSwitchHTML}
                        </div>
                        <div class="card-footer p-2">
                            <div class="btn-group w-100" role="group">
                                ${actionButtonsHTML}
                            </div>
                        </div>
                    </div>
                </div>`;
            reaktoryContainer.innerHTML += cardHTML;
        });
    }

    function renderPusteReaktory(puste_reaktory) { // Zmieniamy nazwę argumentu dla jasności
        pusteReaktoryContainer.innerHTML = '';
        
        // Nie musimy już filtrować!
        if (!puste_reaktory || puste_reaktory.length === 0) {
            pusteReaktoryContainer.innerHTML = '<span class="badge bg-warning text-dark">Brak wolnych reaktorów</span>';
            return;
        }
        puste_reaktory.forEach(r => {
            pusteReaktoryContainer.innerHTML += `<span class="badge bg-success">${r.nazwa}</span>`;
        });
    }

    function renderBeczki(beczki, container, isBrudna) {
        container.innerHTML = '';
        if (!beczki || beczki.length === 0) {
            container.innerHTML = '<div class="list-group-item">Brak danych.</div>';
            return;
        }
        beczki.forEach(b => {
            const transferButtonHTML = (isBrudna && b.partia) ? 
                `<button class="btn btn-sm btn-outline-primary mt-2 action-btn"
                         data-action="plan-transfer"
                         data-source-id="${b.id}"
                         data-source-name="${b.nazwa}"
                         data-mix-id="${b.partia.id}">
                    Zaplanuj Transfer
                 </button>` : '';
            const itemHTML = `
                <div class="list-group-item">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${b.nazwa}</h6>
                        <small>${b.stan_sprzetu}</small>
                    </div>
                    <p class="mb-1">
                        ${b.partia ? `Zawartość: <strong>${b.partia.kod}</strong> (${(b.partia.waga_kg/1000)} t)` : '<em>Pusta</em>'}
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
                        <th class="text-end">W Magazynie Brudnym (t)</th>
                        <th class="text-end">W Magazynie Czystym (t)</th>
                    </tr>
                </thead>
                <tbody>
        `;

        // Sortujemy alfabetycznie po typie surowca
        summaryData.sort((a, b) => a.material_type.localeCompare(b.material_type));

        summaryData.forEach(item => {
            tableHTML += `
                <tr>
                    <td><strong>${item.material_type}</strong></td>
                    <td class="text-end">${(item.dirty_stock_kg/1000).toFixed(1)}</td>
                    <td class="text-end">${(item.clean_stock_kg/1000).toFixed(1)}</td>
                </tr>
            `;
        });

        tableHTML += '</tbody></table>';
        stockSummaryContainer.innerHTML = tableHTML;
    }

    // --- OBSŁUGA ZDARZEŃ ---
    reaktoryContainer.addEventListener('click', (e) => {
        const targetElement = e.target.closest('.action-btn');
        if (!targetElement) return;
        
        const action = targetElement.dataset.action;
        const sprzetId = targetElement.dataset.sprzetId;
        const sprzetNazwa = targetElement.dataset.sprzetNazwa;

        if (action === 'show-details') {
            handleShowDetails(sprzetId, sprzetNazwa);
        } else if (action === 'toggle-burner') {
            const isChecked = targetElement.checked;
            const newState = isChecked ? 'WLACZONY' : 'WYLACZONY';
            handleToggleBurner(sprzetId, newState);
        } else if (action === 'open-simulation-settings') {
            handleOpenSimulationSettings(sprzetId, sprzetNazwa);
        }
    });

    beczkiBrudneContainer.addEventListener('click', (e) => {
        const button = e.target.closest('.action-btn');
        if (!button) return;
        const action = button.dataset.action;
        if (action === 'plan-transfer') {
            const sourceId = button.dataset.sourceId;
            const sourceName = button.dataset.sourceName;
            handlePlanTransfer(sourceId, sourceName);
        }
    });

    // --- FUNKCJE OBSŁUGUJĄCE AKCJE ---
    function handleShowDetails(id, nazwa) {
        window.location.href = `/sprzet/${id}/details`;
    }

    async function handleToggleBurner(id, newState) {
        console.log(`Wysyłanie żądania zmiany stanu palnika dla ID ${id} na ${newState}`);
        try {
            const response = await fetch(`/api/sprzet/${id}/palnik`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newState })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Wystąpił nieznany błąd');
        } catch (error) {
            console.error('Błąd podczas zmiany stanu palnika:', error);
            initialLoad();
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

        try {
            const response = await fetch(`/api/sprzet/${sprzetId}/simulation-params`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    szybkosc_grzania: newHeating,
                    szybkosc_chlodzenia: newCooling
                })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Wystąpił nieznany błąd');
            
            showToast('Parametry symulacji zaktualizowane!', 'success');
            modals.simulationSettings.hide();
        } catch (error) {
            console.error('Błąd podczas aktualizacji parametrów symulacji:', error);
            showToast(`Błąd: ${error.message}`, 'error');
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

        // Pokaż stan ładowania
        heatingInput.value = 'Ładowanie...';
        coolingInput.value = 'Ładowanie...';
        heatingInput.disabled = true;
        coolingInput.disabled = true;

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

        } catch (error) {
            console.error('Błąd podczas pobierania parametrów symulacji:', error);
            showToast(error.message, 'error');
            // W przypadku błędu, zamknij modal
            modals.simulationSettings.hide();
        } finally {
            // Zawsze włączaj pola po zakończeniu operacji
            heatingInput.disabled = false;
            coolingInput.disabled = false;
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
});