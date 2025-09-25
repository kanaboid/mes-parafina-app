document.addEventListener('DOMContentLoaded', () => {
    // --- ZMIENNA GLOBALNA ---
    let apolloTimers = {}; // Przechowuje ID interwałów, aby je czyścić: { apolloId: intervalId }

    // --- ELEMENTY DOM, MODALE, FORMULARZE I API URLS ---
    const apolloStatusContainer = document.getElementById('apollo-status-container');
    const activeTransfersContainer = document.getElementById('active-transfers-container');
    const refreshButton = document.getElementById('refresh-apollo-status');

    const modals = {
        startSession: new bootstrap.Modal(document.getElementById('start-session-modal')),
        addSurowiec: new bootstrap.Modal(document.getElementById('add-surowiec-modal')),
        startTransfer: new bootstrap.Modal(document.getElementById('start-transfer-modal')),
        endTransfer: new bootstrap.Modal(document.getElementById('end-transfer-modal')),
        history: new bootstrap.Modal(document.getElementById('history-modal')),
        loadingHistory: new bootstrap.Modal(document.getElementById('loading-history-modal'))
    };

    const forms = {
        startSession: document.getElementById('start-session-form'),
        addSurowiec: document.getElementById('add-surowiec-form'),
        startTransfer: document.getElementById('start-transfer-form'),
        endTransfer: document.getElementById('end-transfer-form')
    };
    
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
        sessionHistory: (sessionId) => `/api/apollo/sesja/${sessionId}/historia`,
        loadingHistory: (sessionId) => `/api/apollo/sesja/${sessionId}/historia-zaladunku`
    };

    const loadingHistoryApolloName = document.getElementById('loading-history-apollo-name');
    const loadingHistoryTableBody = document.getElementById('loading-history-table-body');
    const historyApolloName = document.getElementById('history-apollo-name');
    const historyTableBody = document.getElementById('history-table-body');

    // --- SOCKET.IO ---
    const socket = io();
    socket.on('connect', () => console.log('Połączono z serwerem przez WebSocket.'));
    socket.on('apollo_update', (data) => {
        console.log('Otrzymano aktualizację przez WebSocket:', data);
        showToast('Otrzymano aktualizację na żywo...', 'info');
        updateUI(data.apollo_list, data.active_transfers);
    });

    // --- GŁÓWNA FUNKCJA AKTUALIZUJĄCA UI ---
    function updateUI(apolloList, activeTransfers) {
        Object.values(apolloTimers).forEach(clearInterval);
        apolloTimers = {};

        let apolloHTML = '';
        if (apolloList && apolloList.length > 0) {
            apolloList.forEach(apollo => { apolloHTML += createApolloCardHTML(apollo); });
        } else {
            apolloHTML = '<p class="text-muted">Nie znaleziono urządzeń Apollo.</p>';
        }
        apolloStatusContainer.innerHTML = apolloHTML;

        let transfersHTML = '';
        if (activeTransfers && activeTransfers.length > 0) {
            activeTransfers.forEach(op => { transfersHTML += createActiveTransferHTML(op); });
        } else {
            transfersHTML = '<p class="text-muted">Brak aktywnych transferów.</p>';
        }
        activeTransfersContainer.innerHTML = transfersHTML;
        
        if (apolloList) {
            apolloList.forEach(apollo => {
                if (apollo.aktywna_sesja) {
                    startTimerForApollo(apollo);
                }
            });
        }
    }

    // --- LOGIKA TIMERA ---
    function startTimerForApollo(apolloData) {
        const apolloId = apolloData.id_sprzetu;
        const valueElement = document.querySelector(`#apollo-card-${apolloId} .apollo-value`);
        
        if (!valueElement) return;

        let currentValue = apolloData.dostepne_kg;
        const bilans = apolloData.bilans_sesji_kg;
        const ratePerSecond = (apolloData.szybkosc_topnienia_kg_h || 0) / 3600;

        if (ratePerSecond <= 0) return;
        if (apolloTimers[apolloId]) clearInterval(apolloTimers[apolloId]);

        apolloTimers[apolloId] = setInterval(() => {
            const currentElement = document.querySelector(`#apollo-card-${apolloId} .apollo-value`);
            if (!currentElement) {
                clearInterval(apolloTimers[apolloId]);
                delete apolloTimers[apolloId];
                return;
            }
            currentValue = Math.min(bilans, currentValue + ratePerSecond);
            currentElement.textContent = currentValue.toFixed(2);
        }, 1000);
    }
    
    // --- FUNKCJE GENERUJĄCE HTML ---
    function createApolloCardHTML(apollo) {
        const isActive = apollo.aktywna_sesja;
        const lastTransferTime = formatUTCDateToLocal(apollo.ostatni_transfer_czas);
        const cardClass = isActive ? 'border-primary' : 'border-secondary';
        const headerClass = isActive ? 'bg-primary text-white' : 'bg-light';
        let buttons = '';

        if (isActive) {
            buttons = `
                <div class="btn-group w-100" role="group" aria-label="Akcje dla Apollo">
                    <button class="btn btn-success action-btn" data-action="start-transfer" data-id="${apollo.id_sprzetu}" data-name="${apollo.nazwa_apollo}">Transfer</button>
                    <button class="btn btn-danger action-btn" data-action="end-session" data-id="${apollo.id_sprzetu}" data-name="${apollo.nazwa_apollo}">Zakończ</button>
                    <div class="btn-group" role="group">
                        <button type="button" class="btn btn-secondary dropdown-toggle" data-bs-toggle="dropdown" aria-expanded="false">Więcej</button>
                        <ul class="dropdown-menu dropdown-menu-end">
                            <li><a class="dropdown-item action-btn" href="#" data-action="add-surowiec" data-id="${apollo.id_sprzetu}" data-name="${apollo.nazwa_apollo}">Dodaj surowiec</a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item action-btn" href="#" data-action="history" data-id="${apollo.id_sprzetu}" data-name="${apollo.nazwa_apollo}" data-session-id="${apollo.id_sesji}">Historia transferów</a></li>
                            <li><a class="dropdown-item action-btn" href="#" data-action="show-loading-history" data-id="${apollo.id_sprzetu}" data-name="${apollo.nazwa_apollo}" data-session-id="${apollo.id_sesji}">Historia załadunku</a></li>
                        </ul>
                    </div>
                </div>`;
        } else {
            buttons = `<button class="btn btn-primary w-100 action-btn" data-action="start-session" data-id="${apollo.id_sprzetu}" data-name="${apollo.nazwa_apollo}">Rozpocznij sesję</button>`;
        }

        return `
            <div class="col-md-6" id="apollo-card-${apollo.id_sprzetu}"> 
                <div class="card h-100 ${cardClass}">
                    <div class="card-header ${headerClass}"><h5 class="card-title mb-0">${apollo.nazwa_apollo}</h5></div>
                    <div class="card-body">
                        ${isActive ? `
                            <p><strong>Status:</strong> <span class="badge bg-success">Aktywna sesja</span></p>
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span><strong>Typ surowca:</strong> ${apollo.typ_surowca}</span>
                                <div class="btn-group btn-group-sm" role="group">
                                    <button class="btn btn-outline-secondary action-btn" data-action="add-predefined-surowiec" data-id="${apollo.id_sprzetu}" data-name="${apollo.nazwa_apollo}" data-waga="1000">+1000 kg</button>
                                    <button class="btn btn-outline-secondary action-btn" data-action="add-predefined-surowiec" data-id="${apollo.id_sprzetu}" data-name="${apollo.nazwa_apollo}" data-waga="1500">+1500 kg</button>
                                </div>
                            </div>
                            <p class="mb-1"><strong>Wytopione:</strong> <span class="fw-bold fs-5"><span class="apollo-value">${apollo.dostepne_kg.toFixed(2)}</span> kg</span></p>
                            <p class="text-muted"><strong>Całkowity bilans sesji:</strong> ${apollo.bilans_sesji_kg} kg</p>
                            ${apollo.ostatni_transfer_czas ? `<p class="text-info-emphasis small mt-2">Ostatnie roztankowanie: ${apollo.ostatni_transfer_kg} kg o ${lastTransferTime}</p>` : '<p class="text-muted small mt-2">Brak transferów w tej sesji.</p>'}` : `
                            <p><strong>Status:</strong> <span class="badge bg-secondary">Nieaktywny</span></p>
                            <p>Brak aktywnej sesji wytapiania.</p>
                        `}
                    </div>
                    <div class="card-footer bg-transparent">${buttons}</div>
                </div>
            </div>`;
    }

    function createActiveTransferHTML(op) {
        const startTimeLocal = formatUTCDateToLocal(op.czas_rozpoczecia);
        return `
            <div class="list-group-item d-flex justify-content-between align-items-center">
                <div>
                    <strong>ID: ${op.id}</strong> - ${op.opis || 'Brak opisu'}
                    <small class="text-muted d-block">Rozpoczęto: ${startTimeLocal}</small>
                </div>
                <div class="btn-group" role="group">
                    <button class="btn btn-success btn-sm" data-action="end-transfer" data-op-id="${op.id}">Zakończ</button>
                    <button class="btn btn-danger btn-sm" data-action="cancel-transfer" data-op-id="${op.id}">Anuluj</button>
                </div>
            </div>`;
    }

    // --- FUNKCJE POBIERAJĄCE DANE ---
    async function initialLoad() {
        try {
            const [statusRes, opsRes] = await Promise.all([
                fetch(API_URLS.apolloStatus),
                fetch(API_URLS.activeOperations)
            ]);
            if (!statusRes.ok || !opsRes.ok) throw new Error("Błąd sieci.");
            
            const apolloList = await statusRes.json();
            const allOperations = await opsRes.json();
            const apolloTransfers = allOperations.filter(op => op.typ_operacji === 'ROZTANKOWANIE_APOLLO');
            
            updateUI(apolloList, apolloTransfers);
        } catch (error) {
            console.error('Błąd ładowania danych:', error);
            showToast('Nie udało się załadować danych.', 'error');
        }
    }
    
    // --- OBSŁUGA ZDARZEŃ I FORMULARZY ---
    
    refreshButton.addEventListener('click', () => { initialLoad(); showToast('Dane odświeżone.'); });

    apolloStatusContainer.addEventListener('click', e => {
        const button = e.target.closest('.action-btn');
        if (!button) return;
        e.preventDefault();
        const { action, id, name, sessionId, waga } = button.dataset;
        switch (action) {
            case 'start-session':
                document.getElementById('start-session-apollo-id').value = id;
                document.getElementById('start-session-apollo-name').textContent = name;
                forms.startSession.reset(); modals.startSession.show(); break;
            case 'add-surowiec':
                document.getElementById('add-surowiec-apollo-id').value = id;
                document.getElementById('add-surowiec-apollo-name').textContent = name;
                forms.addSurowiec.reset(); modals.addSurowiec.show(); break;
            case 'add-predefined-surowiec':
                if (confirm(`Dodać ${waga} kg surowca do ${name}?`)) {
                    const payload = {
                        id_sprzetu: parseInt(id),
                        waga_kg: parseFloat(waga)
                    };
                    handleApiCall(API_URLS.addSurowiec, payload, `Dodano ${waga} kg surowca.`);
                }
                break;
            case 'start-transfer':
                document.getElementById('start-transfer-apollo-id').value = id;
                document.getElementById('start-transfer-apollo-name').textContent = name;
                populateDestinationRadios(document.getElementById('destination-radios-container'));
                forms.startTransfer.reset(); modals.startTransfer.show(); break;
            case 'end-session':
                if (confirm(`Zakończyć sesję w ${name}?`)) handleApiCall(API_URLS.endSession, { id_sprzetu: id }, 'Sesja zakończona.', null); break;
            case 'history':
                showHistory(sessionId, name); break;
            case 'show-loading-history':
                showLoadingHistory(id, name, sessionId); break;
        }
    });

    activeTransfersContainer.addEventListener('click', e => {
        const button = e.target.closest('button');
        if (!button) return;
        const { action, opId } = button.dataset;
        if (action === 'end-transfer') {
            document.getElementById('end-operation-id').value = opId;
            forms.endTransfer.reset();
            modals.endTransfer.show();
        } else if (action === 'cancel-transfer') {
            if (confirm(`Anulować operację ID ${opId}?`)) handleApiCall(API_URLS.cancelTransfer, { id_operacji: opId }, 'Operacja anulowana.', null);
        }
    });

    forms.startSession.addEventListener('submit', e => {
        e.preventDefault();
        const payload = {
            id_sprzetu: parseInt(document.getElementById('start-session-apollo-id').value),
            typ_surowca: document.getElementById('start-session-surowiec-type').value,
            waga_kg: parseFloat(document.getElementById('start-session-waga-kg').value)
        };
        handleApiCall(API_URLS.startSession, payload, 'Sesja rozpoczęta!', modals.startSession);
    });

    forms.addSurowiec.addEventListener('submit', e => {
        e.preventDefault();
        const payload = {
            id_sprzetu: parseInt(document.getElementById('add-surowiec-apollo-id').value),
            waga_kg: parseFloat(document.getElementById('add-surowiec-waga-kg').value)
        };
        handleApiCall(API_URLS.addSurowiec, payload, 'Surowiec dodany!', modals.addSurowiec);
    });

    forms.startTransfer.addEventListener('submit', e => {
        e.preventDefault();
        const selected = document.querySelector('input[name="destination"]:checked');
        if (!selected) return showToast('Musisz wybrać cel transferu.', 'error');
        const payload = {
            id_zrodla: parseInt(document.getElementById('start-transfer-apollo-id').value),
            id_celu: parseInt(selected.value)
        };
        handleApiCall(API_URLS.startTransfer, payload, 'Transfer rozpoczęty!', modals.startTransfer);
    });

    forms.endTransfer.addEventListener('submit', e => {
        e.preventDefault();
        const payload = {
            id_operacji: parseInt(document.getElementById('end-operation-id').value),
            waga_kg: parseFloat(document.getElementById('final-weight-input').value)
        };
        handleApiCall(API_URLS.endTransfer, payload, 'Transfer zakończony!', modals.endTransfer);
    });
    
    // --- FUNKCJE POMOCNICZE ---

    async function populateDestinationRadios(containerElement) {
        try {
            const res = await fetch(API_URLS.destinations);
            const destinations = await res.json();
            containerElement.innerHTML = '';
            if (destinations.length > 0) {
                destinations.forEach((item, index) => {
                    let labelContent = `<div class="d-flex w-100 justify-content-between"><h6 class="mb-1">${item.nazwa_unikalna} [${item.typ_sprzetu}]</h6><small>Stan: ${item.stan_sprzetu}</small></div>`;
                    if (item.stan_sprzetu !== 'Pusty' && item.typ_surowca) {
                        labelContent += `<p class="mb-1 small">Zawartość: ${item.typ_surowca} (${item.waga_aktualna_kg || 0} / ${item.pojemnosc_kg || 'N/A'} kg)</p>`;
                    } else {
                        labelContent += `<p class="mb-1 small">Pojemność: ${item.pojemnosc_kg || 'N/A'} kg</p>`;
                    }
                    containerElement.innerHTML += `<label for="dest-radio-${item.id}" class="list-group-item list-group-item-action"><input class="form-check-input me-2" type="radio" name="destination" value="${item.id}" id="dest-radio-${item.id}" ${index === 0 ? 'checked' : ''}>${labelContent}</label>`;
                });
            } else {
                containerElement.innerHTML = '<p class="text-muted">Brak dostępnych celów transferu.</p>';
            }
        } catch (error) {
            console.error('Błąd ładowania celów:', error);
            containerElement.innerHTML = '<p class="text-danger">Nie udało się załadować listy celów.</p>';
        }
    }

    async function showHistory(sessionId, apolloName) {
        historyApolloName.textContent = apolloName;
        historyTableBody.innerHTML = '<tr><td colspan="3">Ładowanie...</td></tr>';
        modals.history.show();
        try {
            const res = await fetch(API_URLS.sessionHistory(sessionId));
            const historyData = await res.json();
            if (!res.ok) throw new Error(historyData.error || 'Błąd serwera');
            historyTableBody.innerHTML = '';
            if (historyData.length > 0) {
                historyData.forEach(row => {
                    historyTableBody.innerHTML += `<tr><td>${formatUTCDateToLocal(row.czas_zakonczenia)}</td><td>${row.ilosc_kg}</td><td>${row.nazwa_celu || '-'}</td></tr>`;
                });
            } else {
                historyTableBody.innerHTML = '<tr><td colspan="3">Brak transferów w tej sesji.</td></tr>';
            }
        } catch (error) {
            historyTableBody.innerHTML = `<tr><td colspan="3" class="text-danger">${error.message}</td></tr>`;
        }
    }

    async function showLoadingHistory(apolloId, apolloName, sessionId) {
        loadingHistoryApolloName.textContent = apolloName;
        loadingHistoryTableBody.innerHTML = '<tr><td colspan="5">Ładowanie...</td></tr>';
        modals.loadingHistory.show();
        try {
            const res = await fetch(API_URLS.loadingHistory(sessionId));
            const historyData = await res.json();
            if (!res.ok) throw new Error(historyData.error || 'Błąd serwera');
            loadingHistoryTableBody.innerHTML = '';
            if (historyData.length > 0) {
                historyData.forEach(wpis => {
                    loadingHistoryTableBody.innerHTML += `<tr><td>${formatUTCDateToLocal(wpis.czas_zdarzenia)}</td><td>${wpis.typ_zdarzenia.replace('_', ' ')}</td><td>${wpis.waga_kg}</td><td>${wpis.operator || '-'}</td><td>${wpis.uwagi || '-'}</td></tr>`;
                });
            } else {
                loadingHistoryTableBody.innerHTML = '<tr><td colspan="5">Brak historii załadunku.</td></tr>';
            }
        } catch (error) {
            loadingHistoryTableBody.innerHTML = `<tr><td colspan="5" class="text-danger">${error.message}</td></tr>`;
        }
    }

    async function handleApiCall(url, payload, successMessage, modal) {
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await res.json();
            if (!res.ok) {
                let errorMsg = result.message || result.error || 'Wystąpił błąd.';
                if (res.status === 409 && result.zajete_segmenty) {
                    errorMsg += '<br><b>Zajęte:</b> ' + result.zajete_segmenty.join(', ');
                }
                throw new Error(errorMsg);
            }
            showToast(successMessage);
            if (modal) modal.hide();
        } catch (error) {
            console.error(`Błąd API (${url}):`, error);
            if (modal) showModalError(error.message, modal);
            else showToast(error.message, 'error');
        }
    }

    function showToast(message, type = 'success') {
        const classMap = { success: "linear-gradient(to right, #00b09b, #96c93d)", error: "linear-gradient(to right, #ff5f6d, #ffc371)", info: "linear-gradient(to right, #2196F3, #80DEEA)" };
        Toastify({ text: message, duration: 3000, close: true, gravity: "top", position: "right", stopOnFocus: true, style: { background: classMap[type] } }).showToast();
    }

    function showModalError(message, modal) {
        const errorDiv = document.getElementById('start-transfer-error');
        if (modal && modal._element.id === 'start-transfer-modal' && errorDiv) {
            errorDiv.innerHTML = message;
            errorDiv.classList.remove('d-none');
        } else {
            showToast(message, 'error');
        }
    }
    
    // --- Inicjalizacja ---
    initialLoad();
});