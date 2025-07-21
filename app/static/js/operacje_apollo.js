document.addEventListener('DOMContentLoaded', () => {

    const API_URLS = {
        apolloStatus: '/api/apollo/lista-stanow',
        destinations: '/api/sprzet/dostepne-cele',
        activeOperations: '/api/operations/aktywne',
        startSession: '/api/apollo/rozpocznij-sesje',
        endSession: '/api/apollo/zakoncz-sesje',
        addSurowiec: '/api/apollo/dodaj-surowiec',
        startTransfer: '/api/operations/apollo-transfer/start',
        endTransfer: '/api/operations/apollo-transfer/end',
        cancelTransfer: '/api/operations/apollo-transfer/anuluj',
        sessionHistory: (sessionId) => `/api/apollo/sesja/${sessionId}/historia`
    };

    // --- Elementy DOM ---
    const apolloStatusContainer = document.getElementById('apollo-status-container');
    const activeTransfersContainer = document.getElementById('active-transfers-container');
    const noActiveTransfersMsg = document.getElementById('no-active-transfers');
    const refreshButton = document.getElementById('refresh-apollo-status');

    // --- Modale ---
    const modals = {
        startSession: new bootstrap.Modal(document.getElementById('start-session-modal')),
        addSurowiec: new bootstrap.Modal(document.getElementById('add-surowiec-modal')),
        startTransfer: new bootstrap.Modal(document.getElementById('start-transfer-modal')),
        endTransfer: new bootstrap.Modal(document.getElementById('end-transfer-modal')),
        history: new bootstrap.Modal(document.getElementById('history-modal'))
    };

    // --- Formularze ---
    const forms = {
        startSession: document.getElementById('start-session-form'),
        addSurowiec: document.getElementById('add-surowiec-form'),
        startTransfer: document.getElementById('start-transfer-form'),
        endTransfer: document.getElementById('end-transfer-form')
    };

    const loadingHistoryModal = new bootstrap.Modal(document.getElementById('loading-history-modal'));
    const loadingHistoryApolloName = document.getElementById('loading-history-apollo-name');
    const loadingHistoryTableBody = document.getElementById('loading-history-table-body');

    // --- FUNKCJE RENDERUJĄCE ---

    /**
     * Tworzy i zwraca kartę statusu dla pojedynczego Apollo.
     * @param {object} apollo - Obiekt z danymi Apollo.
     */
    function createApolloCard(apollo) {
        const isActive = apollo.aktywna_sesja;
        const cardClass = isActive ? 'border-primary' : 'border-secondary';
        const headerClass = isActive ? 'bg-primary text-white' : 'bg-light';

        let buttons = '';
        if (apollo.aktywna_sesja) {
            buttons = `
                <div class="btn-group w-100" role="group" aria-label="Akcje dla Apollo">
                    <button class="btn btn-success action-btn" data-action="start-transfer" data-id="${apollo.id_sprzetu}" data-name="${apollo.nazwa_apollo}">Transfer</button>
                    <button class="btn btn-danger action-btn" data-action="end-session" data-id="${apollo.id_sprzetu}" data-name="${apollo.nazwa_apollo}">Zakończ</button>
                    
                    <div class="btn-group" role="group">
                        <button type="button" class="btn btn-secondary dropdown-toggle" data-bs-toggle="dropdown" aria-expanded="false">
                            Więcej
                        </button>
                        <ul class="dropdown-menu dropdown-menu-end">
                            <li><a class="dropdown-item action-btn" href="#" data-action="add-surowiec" data-id="${apollo.id_sprzetu}" data-name="${apollo.nazwa_apollo}">Dodaj surowiec</a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item action-btn" href="#" data-action="history" data-id="${apollo.id_sprzetu}" data-name="${apollo.nazwa_apollo}" data-session-id="${apollo.id_sesji}">Historia transferów</a></li>
                            <li><a class="dropdown-item action-btn" href="#" data-action="show-loading-history" data-id="${apollo.id_sprzetu}" data-name="${apollo.nazwa_apollo}" data-session-id="${apollo.id_sesji}">Historia załadunku</a></li>
                        </ul>
                    </div>
                </div>
            `;
        } else {
            buttons = `
                <button class="btn btn-primary w-100 action-btn" data-action="start-session" data-id="${apollo.id_sprzetu}" data-name="${apollo.nazwa_apollo}">Rozpocznij sesję</button>
            `;
        }

        const cardHTML = `
            <div class="col-md-6">
                <div class="card h-100 ${cardClass}">
                    <div class="card-header ${headerClass}">
                        <h5 class="card-title mb-0">${apollo.nazwa_apollo}</h5>
                    </div>
                    <div class="card-body">
                        ${isActive 
                            ? `
                                <p><strong>Status:</strong> <span class="badge bg-success">Aktywna sesja</span></p>
                                <p><strong>Typ surowca:</strong> ${apollo.typ_surowca}</p>
                                <p class="mb-1"><strong>Wytopione:</strong> <span class="fw-bold fs-5">${apollo.dostepne_kg} kg</span></p>
                                <p class="text-muted"><strong>Całkowity bilans sesji:</strong> ${apollo.bilans_sesji_kg} kg</p>
                                ${apollo.ostatni_transfer_czas 
                                    ? `<p class="text-info-emphasis small mt-2">Ostatnie roztankowanie: ${apollo.ostatni_transfer_kg} kg o ${apollo.ostatni_transfer_czas}</p>`
                                    : '<p class="text-muted small mt-2">Brak transferów w tej sesji.</p>'
                                }
                            `
                            : `
                                <p><strong>Status:</strong> <span class="badge bg-secondary">Nieaktywny</span></p>
                                <p>Brak aktywnej sesji wytapiania.</p>
                            `
                        }
                    </div>
                    <div class="card-footer bg-transparent">
                        ${buttons}
                    </div>
                </div>
            </div>
        `;
        return cardHTML;
    }

    // --- FUNKCJE OBSŁUGI DANYCH ---

    /**
     * Ładuje i wyświetla status wszystkich Apollo.
     */
    async function loadApolloStatus() {
        try {
            const res = await fetch(API_URLS.apolloStatus);
            const apolloList = await res.json();
            
            apolloStatusContainer.innerHTML = '';
            if (apolloList.length > 0) {
                apolloList.forEach(apollo => {
                    apolloStatusContainer.innerHTML += createApolloCard(apollo);
                });
            } else {
                apolloStatusContainer.innerHTML = '<p class="text-muted">Nie znaleziono żadnych urządzeń Apollo.</p>';
            }
        } catch (error) {
            console.error('Błąd ładowania statusu Apollo:', error);
            showToast('Nie udało się załadować statusu Apollo.', 'error');
        }
    }

    /**
     * Ładuje i wyświetla aktywne transfery.
     */
    async function loadActiveTransfers() {
        try {
            const res = await fetch(API_URLS.activeOperations);
            const allOperations = await res.json();
            const apolloTransfers = allOperations.filter(op => op.typ_operacji === 'ROZTANKOWANIE_APOLLO');
            
            activeTransfersContainer.innerHTML = ''; 
            if (apolloTransfers.length === 0) {
                activeTransfersContainer.innerHTML = '<p class="text-muted">Brak aktywnych transferów.</p>';
            } else {
                apolloTransfers.forEach(op => {
                    const opElement = document.createElement('div');
                    opElement.className = 'list-group-item d-flex justify-content-between align-items-center';
                    opElement.innerHTML = `
                        <div>
                            <strong>ID: ${op.id}</strong> - ${op.opis}
                            <small class="text-muted d-block">Rozpoczęto: ${op.czas_rozpoczecia}</small>
                        </div>
                        <div class="btn-group" role="group">
                            <button class="btn btn-success btn-sm" data-action="end-transfer" data-op-id="${op.id}">Zakończ</button>
                            <button class="btn btn-danger btn-sm" data-action="cancel-transfer" data-op-id="${op.id}">Anuluj</button>
                        </div>
                    `;
                    activeTransfersContainer.appendChild(opElement);
                });
            }
        } catch (error) {
            console.error('Błąd ładowania aktywnych transferów:', error);
            showToast('Nie udało się załadować aktywnych operacji.', 'error');
        }
    }

    /**
     * Wypełnia kontener przyciskami radio z celami transferu.
     * @param {HTMLElement} containerElement 
     */
    async function populateDestinationRadios(containerElement) {
        try {
            const res = await fetch(API_URLS.destinations);
            const destinations = await res.json();
            
            containerElement.innerHTML = '';
            if (destinations.length > 0) {
                destinations.forEach((item, index) => {
                    let labelContent = `
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1">${item.nazwa_unikalna} [${item.typ_sprzetu}]</h6>
                            <small>Stan: ${item.stan_sprzetu}</small>
                        </div>
                    `;
                    if (item.stan_sprzetu !== 'Pusty' && item.typ_surowca) {
                        labelContent += `<p class="mb-1 small">Zawartość: ${item.typ_surowca} (${item.waga_aktualna_kg || 0} / ${item.pojemnosc_kg || 'N/A'} kg)</p>`;
                    } else {
                        labelContent += `<p class="mb-1 small">Pojemność: ${item.pojemnosc_kg || 'N/A'} kg</p>`;
                    }

                    const radioId = `dest-radio-${item.id}`;
                    const radioHTML = `
                        <label for="${radioId}" class="list-group-item list-group-item-action">
                            <input class="form-check-input me-2" type="radio" name="destination" value="${item.id}" id="${radioId}" ${index === 0 ? 'checked' : ''}>
                            ${labelContent}
                        </label>
                    `;
                    containerElement.innerHTML += radioHTML;
                });
            } else {
                containerElement.innerHTML = '<p class="text-muted">Brak dostępnych celów transferu.</p>';
            }
        } catch (error) {
            console.error('Błąd ładowania celów:', error);
            containerElement.innerHTML = '<p class="text-danger">Nie udało się załadować listy celów.</p>';
        }
    }

    /**
     * Pobiera i wyświetla historię transferów dla sesji.
     * @param {number} sessionId 
     * @param {string} apolloName 
     */
    async function showHistory(sessionId, apolloName) {
        document.getElementById('history-apollo-name').textContent = apolloName;
        const tableBody = document.getElementById('history-table-body');
        tableBody.innerHTML = '<tr><td colspan="3">Ładowanie historii...</td></tr>';
        modals.history.show();

        try {
            const res = await fetch(API_URLS.sessionHistory(sessionId));
            const historyData = await res.json();

            if (res.ok) {
                tableBody.innerHTML = '';
                if (historyData.length > 0) {
                    historyData.forEach(row => {
                        tableBody.innerHTML += `
                            <tr>
                                <td>${row.czas_zakonczenia}</td>
                                <td>${row.ilosc_kg}</td>
                                <td>${row.nazwa_celu || 'Brak danych'}</td>
                            </tr>
                        `;
                    });
                } else {
                    tableBody.innerHTML = '<tr><td colspan="3">Brak zakończonych transferów w tej sesji.</td></tr>';
                }
            } else {
                throw new Error(historyData.error || 'Nieznany błąd');
            }
        } catch (error) {
            console.error('Błąd ładowania historii:', error);
            tableBody.innerHTML = `<tr><td colspan="3" class="text-danger">Błąd ładowania historii: ${error.message}</td></tr>`;
        }
    }
    
    // NOWA FUNKCJA do pokazywania historii załadunku
    async function showLoadingHistory(apolloId, apolloName, sesjaId) {
        loadingHistoryApolloName.textContent = apolloName;
        loadingHistoryTableBody.innerHTML = '<tr><td colspan="5">Ładowanie...</td></tr>';
        loadingHistoryModal.show();

        try {
            const response = await fetch(`/api/apollo/sesja/${sesjaId}/historia-zaladunku`);
            if (!response.ok) throw new Error('Błąd sieci');
            
            const historia = await response.json();
            loadingHistoryTableBody.innerHTML = '';

            if (historia.length > 0) {
                historia.forEach(wpis => {
                    const row = `
                        <tr>
                            <td>${new Date(wpis.czas_zdarzenia).toLocaleString()}</td>
                            <td>${wpis.typ_zdarzenia === 'DODANIE_SUROWCA' ? 'Dodanie surowca' : 'Korekta ręczna'}</td>
                            <td>${wpis.waga_kg}</td>
                            <td>${wpis.operator || '-'}</td>
                            <td>${wpis.uwagi || '-'}</td>
                        </tr>
                    `;
                    loadingHistoryTableBody.insertAdjacentHTML('beforeend', row);
                });
            } else {
                loadingHistoryTableBody.innerHTML = '<tr><td colspan="5" class="text-center">Brak historii załadunków dla tej sesji.</td></tr>';
            }
        } catch (error) {
            console.error('Błąd podczas pobierania historii załadunku:', error);
            loadingHistoryTableBody.innerHTML = '<tr><td colspan="5" class="text-danger text-center">Nie udało się załadować historii.</td></tr>';
        }
    }


    // --- OBSŁUGA ZDARZEŃ ---
    
    // Odświeżanie
    refreshButton.addEventListener('click', () => {
        loadApolloStatus();
        loadActiveTransfers();
        showToast('Dane odświeżone.');
    });

    // Delegacja zdarzeń dla przycisków akcji
    apolloStatusContainer.addEventListener('click', e => {
        const button = e.target.closest('.action-btn');
        if (button) {
            e.preventDefault(); // Zapobiega domyślnej akcji (np. przeładowaniu strony dla linków)
            const action = button.dataset.action;
            const id = button.dataset.id;
            const name = button.dataset.name;

            switch (action) {
                case 'start-session':
                    document.getElementById('start-session-apollo-id').value = id;
                    document.getElementById('start-session-apollo-name').textContent = name;
                    forms.startSession.reset();
                    modals.startSession.show();
                    break;
                case 'add-surowiec':
                    document.getElementById('add-surowiec-apollo-id').value = id;
                    document.getElementById('add-surowiec-apollo-name').textContent = name;
                    forms.addSurowiec.reset();
                    modals.addSurowiec.show();
                    break;
                case 'start-transfer':
                    document.getElementById('start-transfer-apollo-id').value = id;
                    document.getElementById('start-transfer-apollo-name').textContent = name;
                    populateDestinationRadios(document.getElementById('destination-radios-container'));
                    forms.startTransfer.reset();
                    modals.startTransfer.show();
                    break;
                case 'end-session':
                    if (confirm(`Czy na pewno chcesz zakończyć aktywną sesję w ${name}?`)) {
                        handleEndSession(id);
                    }
                    break;
                case 'history': {
                    const sessionId = button.dataset.sessionId;
                    showHistory(sessionId, name);
                    break;
                }
                case 'show-loading-history': {
                    const sesjaId = button.dataset.sessionId;
                    showLoadingHistory(id, name, sesjaId);
                    break;
                }
            }
        }
    });

    // Delegacja zdarzeń dla kończenia transferu
    activeTransfersContainer.addEventListener('click', e => {
        const action = e.target.dataset.action;
        const opId = e.target.dataset.opId;

        if (action === 'end-transfer') {
            document.getElementById('end-operation-id').value = opId;
            forms.endTransfer.reset();
            modals.endTransfer.show();
        } else if (action === 'cancel-transfer') {
            if (confirm(`Czy na pewno chcesz anulować operację o ID ${opId}? Tej akcji nie można cofnąć.`)) {
                handleCancelTransfer(opId);
            }
        }
    });

    // --- OBSŁUGA FORMULARZY ---

    forms.startSession.addEventListener('submit', async e => {
        e.preventDefault();
        const payload = {
            id_sprzetu: parseInt(document.getElementById('start-session-apollo-id').value),
            typ_surowca: document.getElementById('start-session-surowiec-type').value,
            waga_kg: parseFloat(document.getElementById('start-session-waga-kg').value)
        };
        handleApiCall(API_URLS.startSession, payload, 'Sesja rozpoczęta pomyślnie!', modals.startSession);
    });

    forms.addSurowiec.addEventListener('submit', async e => {
        e.preventDefault();
        const payload = {
            id_sprzetu: parseInt(document.getElementById('add-surowiec-apollo-id').value),
            waga_kg: parseFloat(document.getElementById('add-surowiec-waga-kg').value)
        };
        handleApiCall(API_URLS.addSurowiec, payload, 'Surowiec dodany pomyślnie!', modals.addSurowiec);
    });

    forms.startTransfer.addEventListener('submit', async e => {
        e.preventDefault();
        const selectedDestination = document.querySelector('input[name="destination"]:checked');
        if (!selectedDestination) {
            showToast('Musisz wybrać cel transferu.', 'error');
            return;
        }

        const payload = {
            id_zrodla: parseInt(document.getElementById('start-transfer-apollo-id').value),
            id_celu: parseInt(selectedDestination.value)
        };
        handleApiCall(API_URLS.startTransfer, payload, 'Transfer rozpoczęty!', modals.startTransfer);
    });

    forms.endTransfer.addEventListener('submit', async e => {
        e.preventDefault();
        const payload = {
            id_operacji: parseInt(document.getElementById('end-operation-id').value),
            waga_kg: parseFloat(document.getElementById('final-weight-input').value)
        };
        handleApiCall(API_URLS.endTransfer, payload, 'Transfer zakończony!', modals.endTransfer, false);
    });

    async function handleEndSession(id) {
        handleApiCall(API_URLS.endSession, { id_sprzetu: id }, 'Sesja zakończona pomyślnie!', null, false);
    }
    
    /**
     * Generyczna funkcja do obsługi wywołań API z formularzy
     * @param {string} url 
     * @param {object} payload 
     * @param {string} successMessage 
     * @param {bootstrap.Modal} modal 
     * @param {boolean} refreshStatus - Czy odświeżyć statusy Apollo
     */
    async function handleApiCall(url, payload, successMessage, modal, refreshStatus = true) {
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await res.json();
            if (!res.ok) throw new Error(result.error || 'Wystąpił nieznany błąd.');
            
            showToast(successMessage);
            if (modal) modal.hide();
            
            if(refreshStatus) loadApolloStatus();
            loadActiveTransfers();

        } catch (error) {
            console.error(`Błąd podczas wywołania ${url}:`, error);
            showToast(`Błąd: ${error.message}`, 'error');
        }
    }

    async function handleCancelTransfer(opId) {
        try {
            const res = await fetch(API_URLS.cancelTransfer, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id_operacji: opId })
            });
            const result = await res.json();
            if (!res.ok) throw new Error(result.error || 'Wystąpił nieznany błąd.');
            
            showToast('Operacja została anulowana.');
            loadActiveTransfers();
            loadApolloStatus(); // Odświeżamy też statusy, bo sprzęt zmienia stan

        } catch (error) {
            console.error(`Błąd podczas anulowania operacji ${opId}:`, error);
            showToast(`Błąd: ${error.message}`, 'error');
        }
    }

    // --- INNE ---
    
    function showToast(message, type = 'success') {
        const prefix = type === 'error' ? 'Błąd: ' : '';
        Toastify({
            text: prefix + message,
            duration: 3000,
            newWindow: true,
            close: true,
            gravity: "top", 
            position: "right", 
            stopOnFocus: true,
            className: "info-toast",
            style: {
                background: type === 'success' ? "linear-gradient(to right, #00b09b, #96c93d)" : "linear-gradient(to right, #ff5f6d, #ffc371)",
            }
        }).showToast();
    }

    // --- Inicjalizacja ---
    loadApolloStatus();
    loadActiveTransfers();
});