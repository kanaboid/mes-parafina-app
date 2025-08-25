// app/static/js/dashboard.js
document.addEventListener('DOMContentLoaded', () => {
    
    // --- ELEMENTY DOM ---
    const reaktoryContainer = document.getElementById('reaktory-container');
    const beczkiBrudneContainer = document.getElementById('beczki-brudne-container');
    const beczkiCzysteContainer = document.getElementById('beczki-czyste-container');
    const alarmsContainer = document.getElementById('alarms-container');
    const lastUpdatedTime = document.getElementById('last-updated-time');

    // --- SOCKET.IO ---
    const socket = io();
    socket.on('connect', () => console.log("Połączono z dashboardem przez WebSocket."));
    
    // TODO: Stworzyć na backendzie event 'dashboard_update', który będzie wysyłał dane
    // socket.on('dashboard_update', (data) => {
    //     console.log("Otrzymano aktualizację dashboardu:", data);
    //     updateUI(data);
    // });

    // --- GŁÓWNA FUNKCJA AKTUALIZUJĄCA UI ---
    function updateUI(data) {
        renderReaktory(data.reaktory);
        renderBeczki(data.beczki_brudne, beczkiBrudneContainer);
        renderBeczki(data.beczki_czyste, beczkiCzysteContainer);
        renderAlarms(data.alarmy);
        lastUpdatedTime.textContent = `Ostatnia aktualizacja: ${new Date().toLocaleTimeString()}`;
    }

    // --- FUNKCJE RENDERUJĄCE ---
    function renderReaktory(reaktory) {
        reaktoryContainer.innerHTML = '';
        if (!reaktory || reaktory.length === 0) {
            reaktoryContainer.innerHTML = '<p>Brak danych o reaktorach.</p>';
            return;
        }
        reaktory.forEach(r => {
            const statusClass = r.stan_sprzetu === 'W transferze' ? 'status-alarm' : (r.partia ? 'status-ok' : 'status-idle');
            const cardHTML = `
                <div class="col-xl-4 col-lg-6 mb-4">
                    <div class="card h-100 card-reaktor">
                        <div class="card-header d-flex justify-content-between">
                            <h5 class="mb-0"><span class="status-indicator ${statusClass}"></span>${r.nazwa}</h5>
                            <span class="badge bg-info text-dark">${r.stan_sprzetu || 'Brak stanu'}</span>
                        </div>
                        <div class="card-body">
                            <p><strong>Partia:</strong> ${r.partia ? r.partia.kod : '<em>Pusty</em>'}</p>
                            <p><strong>Temperatura:</strong> ${r.temperatura_aktualna || 'N/A'}°C / ${r.temperatura_docelowa || 'N/A'}°C</p>
                            <p><strong>Ciśnienie:</strong> ${r.cisnienie_aktualne || 'N/A'} bar</p>
                        </div>
                        <div class="card-footer text-center">
                            <button class="btn btn-primary btn-sm">Szczegóły</button>
                        </div>
                    </div>
                </div>`;
            reaktoryContainer.innerHTML += cardHTML;
        });
    }

    function renderBeczki(beczki, container) {
        container.innerHTML = '';
        if (!beczki || beczki.length === 0) {
            container.innerHTML = '<div class="list-group-item">Brak danych.</div>';
            return;
        }
        beczki.forEach(b => {
            const itemHTML = `
                <a href="#" class="list-group-item list-group-item-action">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${b.nazwa}</h6>
                        <small>${b.stan_sprzetu}</small>
                    </div>
                    <p class="mb-1">
                        ${b.partia ? `Zawartość: <strong>${b.partia.kod}</strong> (${b.partia.typ})` : '<em>Pusta</em>'}
                    </p>
                </a>`;
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

    // --- INICJALIZACJA ---
    async function initialLoad() {
        try {
            const response = await fetch('/api/dashboard/main-status');
            if (!response.ok) throw new Error('Błąd pobierania danych z API');
            const data = await response.json();
            updateUI(data);
        } catch (error) {
            console.error(error);
            reaktoryContainer.innerHTML = '<p class="text-danger">Nie udało się załadować danych.</p>';
        }
    }

    initialLoad();
});