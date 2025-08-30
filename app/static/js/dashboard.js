// app/static/js/dashboard.js

document.addEventListener('DOMContentLoaded', () => {
    
    // --- ELEMENTY DOM, MODALE, FORMULARZE ---
    const reaktoryContainer = document.getElementById('reaktory-container');
    const pusteReaktoryContainer = document.getElementById('puste-reaktory-container');
    const beczkiBrudneContainer = document.getElementById('beczki-brudne-container');
    const beczkiCzysteContainer = document.getElementById('beczki-czyste-container');
    const alarmsContainer = document.getElementById('alarms-container');
    const lastUpdatedTime = document.getElementById('last-updated-time');
    const stockSummaryContainer = document.getElementById('stock-summary-container');

    // Elementy kontroli schedulerów
    const schedulerStatusContainer = document.getElementById('scheduler-status-container');
    const startSchedulerBtn = document.getElementById('start-scheduler-btn');
    const stopSchedulerBtn = document.getElementById('stop-scheduler-btn');
    const resetSchedulerBtn = document.getElementById('reset-scheduler-btn');

    const modals = {
        planTransfer: new bootstrap.Modal(document.getElementById('plan-transfer-modal')),
        startHeating: new bootstrap.Modal(document.getElementById('start-heating-modal'))
    };
    const forms = {
        planTransfer: document.getElementById('plan-transfer-form'),
        startHeating: document.getElementById('start-heating-form')
    };
    
    // --- SOCKET.IO ---
    const socket = io();
    socket.on('connect', () => console.log("Połączono z dashboardem przez WebSocket."));
    
    socket.on('dashboard_update', (data) => {
        console.log("Otrzymano aktualizację dashboardu:", data);
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
                            <p class="mb-1"><strong>Temperatura:</strong> ${r.temperatura_aktualna || 'N/A'}°C / ${r.temperatura_docelowa || 'N/A'}°C</p>
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

    // --- FUNKCJE ZARZĄDZANIA SCHEDULERAMI ---
    async function loadSchedulerStatus() {
        try {
            const response = await fetch('/api/scheduler/status');
            if (!response.ok) throw new Error('Błąd pobierania statusu schedulerów');
            const data = await response.json();
            renderSchedulerStatus(data);
        } catch (error) {
            console.error('Błąd podczas ładowania statusu schedulerów:', error);
            schedulerStatusContainer.innerHTML = '<p class="text-danger">Błąd ładowania statusu schedulerów</p>';
        }
    }

    function renderSchedulerStatus(data) {
        const { jobs, scheduler_running, total_jobs, active_jobs } = data;
        
        let html = `
            <div class="row">
                <div class="col-md-12 mb-3">
                    <div class="d-flex align-items-center">
                        <span class="me-2">Status główny:</span>
                        <span class="badge ${scheduler_running ? 'bg-success' : 'bg-danger'}">
                            ${scheduler_running ? 'DZIAŁA' : 'ZATRZYMANY'}
                        </span>
                        <span class="ms-3 text-muted">Zadania: ${active_jobs}/${total_jobs} aktywne</span>
                    </div>
                </div>
            </div>
            <div class="row">
        `;

        jobs.forEach(job => {
            const statusBadge = job.active ? 
                '<span class="badge bg-success">AKTYWNE</span>' : 
                '<span class="badge bg-warning">WYŁĄCZONE</span>';
            
            const intervalMatch = job.trigger.match(/interval\(0:00:(\d+)\)/);
            const currentInterval = intervalMatch ? parseInt(intervalMatch[1]) : 'N/A';
            
            html += `
                <div class="col-md-6 mb-3">
                    <div class="card border">
                        <div class="card-header py-2">
                            <div class="d-flex justify-content-between align-items-center">
                                <strong>${job.id}</strong>
                                ${statusBadge}
                            </div>
                        </div>
                        <div class="card-body py-2">
                            <p class="mb-1"><small>Funkcja: ${job.func}</small></p>
                            <p class="mb-2"><small>Interwał: ${currentInterval}s</small></p>
                            <div class="btn-group btn-group-sm w-100" role="group">
                                <button type="button" class="btn btn-outline-primary scheduler-toggle-btn" 
                                        data-job-id="${job.id}" data-current-status="${job.active ? 'active' : 'paused'}">
                                    ${job.active ? 'Wyłącz' : 'Włącz'}
                                </button>
                                <button type="button" class="btn btn-outline-secondary dropdown-toggle" 
                                        data-bs-toggle="dropdown" aria-expanded="false">
                                    Interwał
                                </button>
                                <ul class="dropdown-menu">
                                    <li><a class="dropdown-item interval-option" href="#" data-seconds="1">1 sekunda</a></li>
                                    <li><a class="dropdown-item interval-option" href="#" data-seconds="5">5 sekund</a></li>
                                    <li><a class="dropdown-item interval-option" href="#" data-seconds="10">10 sekund</a></li>
                                    <li><a class="dropdown-item interval-option" href="#" data-seconds="30">30 sekund</a></li>
                                    <li><a class="dropdown-item interval-option" href="#" data-seconds="60">1 minuta</a></li>
                                    <li><a class="dropdown-item interval-option" href="#" data-seconds="600">10 minut</a></li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        schedulerStatusContainer.innerHTML = html;
        
        // Dodaj event listenery dla nowych przycisków
        addSchedulerEventListeners();
    }

    function addSchedulerEventListeners() {
        // Przyciski włączania/wyłączania zadań
        document.querySelectorAll('.scheduler-toggle-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const jobId = e.target.dataset.jobId;
                await toggleSchedulerJob(jobId);
            });
        });

        // Opcje zmiany interwału
        document.querySelectorAll('.interval-option').forEach(option => {
            option.addEventListener('click', async (e) => {
                e.preventDefault();
                const seconds = parseInt(e.target.dataset.seconds);
                const jobId = e.target.closest('.card').querySelector('.scheduler-toggle-btn').dataset.jobId;
                await changeJobInterval(jobId, seconds);
            });
        });
    }

    async function toggleSchedulerJob(jobId) {
        try {
            const response = await fetch(`/api/scheduler/job/${jobId}/toggle`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();
            
            if (!response.ok) throw new Error(result.error);
            
            showToast(result.message, 'success');
            await loadSchedulerStatus(); // Odśwież status
        } catch (error) {
            console.error('Błąd podczas przełączania zadania:', error);
            showToast(error.message, 'error');
        }
    }

    async function changeJobInterval(jobId, seconds) {
        try {
            const response = await fetch(`/api/scheduler/job/${jobId}/interval`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ seconds: seconds })
            });
            const result = await response.json();
            
            if (!response.ok) throw new Error(result.error);
            
            showToast(result.message, 'success');
            await loadSchedulerStatus(); // Odśwież status
        } catch (error) {
            console.error('Błąd podczas zmiany interwału:', error);
            showToast(error.message, 'error');
        }
    }

    async function startScheduler() {
        try {
            const response = await fetch('/api/scheduler/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();
            
            if (!response.ok) throw new Error(result.error);
            
            showToast(result.message, 'success');
            await loadSchedulerStatus(); // Odśwież status
        } catch (error) {
            console.error('Błąd podczas uruchamiania schedulera:', error);
            showToast(error.message, 'error');
        }
    }

    async function stopScheduler() {
        try {
            const response = await fetch('/api/scheduler/stop', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();
            
            if (!response.ok) throw new Error(result.error);
            
            showToast(result.message, 'success');
            await loadSchedulerStatus(); // Odśwież status
        } catch (error) {
            console.error('Błąd podczas zatrzymywania schedulera:', error);
            showToast(error.message, 'error');
        }
    }

    async function resetScheduler() {
        try {
            const response = await fetch('/api/scheduler/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();
            
            if (!response.ok) throw new Error(result.error);
            
            showToast(result.message, 'success');
            await loadSchedulerStatus(); // Odśwież status
        } catch (error) {
            console.error('Błąd podczas resetowania schedulera:', error);
            showToast(error.message, 'error');
        }
    }

    // --- OBSŁUGA ZDARZEŃ ---
    reaktoryContainer.addEventListener('click', (e) => {
        const targetElement = e.target.closest('.action-btn');
        if (!targetElement) return;
        const action = targetElement.dataset.action;
        const sprzetId = targetElement.dataset.sprzetId;
        if (action === 'show-details') {
            const sprzetNazwa = targetElement.dataset.sprzetNazwa;
            handleShowDetails(sprzetId, sprzetNazwa);
        } else if (action === 'toggle-burner') {
            const isChecked = targetElement.checked;
            const newState = isChecked ? 'WLACZONY' : 'WYLACZONY';
            handleToggleBurner(sprzetId, newState);
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

    // Event listenery dla kontroli schedulerów
    startSchedulerBtn.addEventListener('click', startScheduler);
    stopSchedulerBtn.addEventListener('click', stopScheduler);
    resetSchedulerBtn.addEventListener('click', resetScheduler);

    // --- INICJALIZACJA ---
    async function initialLoad() {
        try {
            const response = await fetch('/api/dashboard/main-status');
            if (!response.ok) throw new Error('Błąd pobierania danych z API');
            const data = await response.json();
            updateUI(data);
            await loadSchedulerStatus(); // Załaduj status schedulerów
        } catch (error) {
            console.error(error);
            reaktoryContainer.innerHTML = '<p class="text-danger">Nie udało się załadować danych.</p>';
        }
    }
    initialLoad();

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
});