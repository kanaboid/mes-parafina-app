document.addEventListener('DOMContentLoaded', function () {
    const cysternyStatusContainer = document.getElementById('cysterny-status-container');
    const activeTransfersContainer = document.getElementById('active-transfers-container');
    const noActiveTransfers = document.getElementById('no-active-transfers');
    const refreshButton = document.getElementById('refresh-cysterny-status');

    const startTransferModal = new bootstrap.Modal(document.getElementById('start-transfer-modal'));
    const startTransferForm = document.getElementById('start-transfer-form');
    const startTransferCysternaName = document.getElementById('start-transfer-cysterna-name');
    const startTransferCysternaId = document.getElementById('start-transfer-cysterna-id');
    const destinationRadiosContainer = document.getElementById('destination-radios-container');

    const endTransferModal = new bootstrap.Modal(document.getElementById('end-transfer-modal'));
    const endTransferForm = document.getElementById('end-transfer-form');
    const endOperationIdInput = document.getElementById('end-operation-id');
    const endOperationIdDisplay = document.getElementById('end-transfer-operation-id-display');

    async function fetchData(url) {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    }

    function createCysternaCard(cysterna) {
        const cardClass = cysterna.stan_sprzetu === 'W transferze' ? 'border-primary' : 'border-secondary';
        const headerClass = cysterna.stan_sprzetu === 'W transferze' ? 'bg-primary text-white' : 'bg-light';

        let buttons = '';
        if (cysterna.stan_sprzetu !== 'W transferze') {
            buttons = `<button class="btn btn-success btn-sm action-btn" data-action="start-transfer" data-id="${cysterna.id}" data-name="${cysterna.nazwa_unikalna}">Rozpocznij roztankowanie</button>`;
        }

        return `
            <div class="col-md-6 col-lg-4">
                <div class="card h-100 ${cardClass}">
                    <div class="card-header ${headerClass}">
                        <h5 class="card-title mb-0">${cysterna.nazwa_unikalna}</h5>
                    </div>
                    <div class="card-body">
                        <p class="card-text"><strong>Status:</strong> ${cysterna.stan_sprzetu}</p>
                    </div>
                    <div class="card-footer bg-transparent">
                        ${buttons}
                    </div>
                </div>
            </div>
        `;
    }

    function createActiveTransferItem(op) {
        return `
            <div class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                <div>
                    <h6 class="mb-1">Operacja ID: ${op.id}</h6>
                    <p class="mb-1 text-muted">${op.opis}</p>
                    <small>Rozpoczęto: ${op.czas_rozpoczecia}</small>
                </div>
                <div>
                    <button class="btn btn-warning btn-sm me-2 action-btn" data-action="end-transfer" data-id="${op.id}">Zakończ</button>
                    <button class="btn btn-danger btn-sm action-btn" data-action="cancel-transfer" data-id="${op.id}">Anuluj</button>
                </div>
            </div>
        `;
    }

    async function updateUI() {
        try {
            const sprzet = await fetchData('/api/sprzet');
            const cysterny = sprzet.filter(s => s.typ_sprzetu.toLowerCase() === 'cysterna');
            cysternyStatusContainer.innerHTML = cysterny.map(createCysternaCard).join('');

            const operacje = await fetchData('/api/operations/aktywne');
            const transferyCystern = operacje.filter(op => op.typ_operacji === 'ROZTANKOWANIE_CYSTERNY');

            if (transferyCystern.length > 0) {
                activeTransfersContainer.innerHTML = transferyCystern.map(createActiveTransferItem).join('');
                noActiveTransfers.style.display = 'none';
            } else {
                activeTransfersContainer.innerHTML = '';
                noActiveTransfers.style.display = 'block';
            }
        } catch (error) {
            console.error('Błąd podczas aktualizacji UI:', error);
            showToast('Nie udało się załadować danych. Spróbuj odświeżyć stronę.', 'error');
        }
    }

    async function handleStartTransferClick(id, name) {
        startTransferCysternaId.value = id;
        startTransferCysternaName.textContent = name;
        
        try {
            const response = await fetch('/api/sprzet/dostepne-cele');
            if (!response.ok) throw new Error('Błąd sieci podczas pobierania celów.');

            const destinations = await response.json();
            
            destinationRadiosContainer.innerHTML = ''; // Wyczyść kontener
            if (destinations.length > 0) {
                destinations.forEach((item, index) => {
                    let labelContent = `
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1">${item.nazwa_unikalna} <span class="badge bg-info">${item.typ_sprzetu}</span></h6>
                            <small>Stan: ${item.stan_sprzetu}</small>
                        </div>
                    `;
                    if (item.stan_sprzetu !== 'Pusty' && item.typ_surowca) {
                        labelContent += `<p class="mb-1 small">Zawartość: <strong>${item.typ_surowca}</strong> (${item.waga_aktualna_kg || 0} / ${item.pojemnosc_kg || 'N/A'} kg)</p>`;
                    } else {
                        labelContent += `<p class="mb-1 small">Pojemność: ${item.pojemnosc_kg || 'N/A'} kg</p>`;
                    }

                    const radioId = `dest-radio-${item.id}`;
                    const radioHTML = `
                        <label for="${radioId}" class="list-group-item list-group-item-action">
                            <input class="form-check-input me-2" type="radio" name="destination" value="${item.id}" id="${radioId}" required>
                            ${labelContent}
                        </label>
                    `;
                    destinationRadiosContainer.innerHTML += radioHTML;
                });
            } else {
                destinationRadiosContainer.innerHTML = '<p class="text-danger">Brak dostępnych celów transferu (reaktorów, zbiorników, beczek brudnych).</p>';
            }

            startTransferModal.show();
        } catch (error) {
            console.error('Błąd podczas pobierania celów transferu:', error);
            showToast('Nie udało się załadować listy celów.', 'error');
        }
    }

    // Dodaj modal potwierdzenia konfliktu
    const confirmConflictModalHtml = `
    <div class="modal fade" id="confirm-conflict-modal" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header bg-warning-subtle">
            <h5 class="modal-title text-warning">Cel nie jest pusty</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <p id="conflict-modal-message">Wybrany cel nie jest pusty lub występuje konflikt zasobów.<br>Czy na pewno chcesz rozpocząć operację mimo to?</p>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">OK</button>
            
          </div>
        </div>
      </div>
    </div>`;
    document.body.insertAdjacentHTML('beforeend', confirmConflictModalHtml);
    const confirmConflictModal = new bootstrap.Modal(document.getElementById('confirm-conflict-modal'));
    let pendingForcePayload = null;

    startTransferForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const cysternaId = startTransferCysternaId.value;
        const celId = this.elements['destination'].value;
        const payload = { id_cysterny: cysternaId, id_celu: celId };
        try {
            const response = await fetch('/api/operations/roztankuj-cysterne/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            if (response.ok) {
                showToast('Operacja roztankowania rozpoczęta pomyślnie!', 'success');
                startTransferModal.hide();
                updateUI();
            } 
            else if (response.status === 409) {
                // Pokaż toast o konflikcie
                showToast(result.message || 'Cel nie jest pusty lub występuje konflikt zasobów.', 'error');
                // Pokaż modal potwierdzenia
                pendingForcePayload = { ...payload, force: true };
                document.getElementById('conflict-modal-message').textContent = result.message || 'Cel nie jest pusty lub występuje konflikt zasobów. Czy kontynuować?';
                confirmConflictModal.show();
            }
            else {
                throw new Error(result.message || 'Nieznany błąd');
            }
        } catch (error) {
            showToast(`Błąd: ${error.message}`, 'error');
        }
    });

    // document.getElementById('confirm-conflict-btn').addEventListener('click', async function() {
    //     if (!pendingForcePayload) return;
    //     try {
    //         const response = await fetch('/api/operations/roztankuj-cysterne/start', {
    //             method: 'POST',
    //             headers: { 'Content-Type': 'application/json' },
    //             body: JSON.stringify(pendingForcePayload)
    //         });
    //         const result = await response.json();
    //         if (response.ok) {
    //             showToast('Operacja roztankowania rozpoczęta mimo konfliktu.', 'success');
    //             confirmConflictModal.hide();
    //             startTransferModal.hide();
    //             updateUI();
    //         } else {
    //             throw new Error(result.message || 'Nieznany błąd');
    //         }
    //     } catch (error) {
    //         showToast(`Błąd: ${error.message}`, 'error');
    //     } finally {
    //         pendingForcePayload = null;
    //     }
    // });

    function handleEndTransferClick(id) {
        endOperationIdInput.value = id;
        endOperationIdDisplay.textContent = id;
        endTransferForm.reset();
        endTransferModal.show();
    }
    
    endTransferForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const id_operacji = endOperationIdInput.value;
        const formData = {
            id_operacji: id_operacji,
            typ_surowca: this.elements['end-transfer-typ-surowca'].value,
            waga_netto_kg: this.elements['end-transfer-waga-netto'].value,
            nr_rejestracyjny: this.elements['end-transfer-nr-rejestracyjny'].value,
            nr_dokumentu_dostawy: this.elements['end-transfer-nr-dokumentu'].value,
            nazwa_dostawcy: this.elements['end-transfer-dostawca'].value
        };

        try {
            const response = await fetch('/api/operations/roztankuj-cysterne/zakoncz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
            const result = await response.json();
            if (response.ok) {
                showToast('Operacja zakończona pomyślnie.', 'success');
                endTransferModal.hide();
                updateUI();
            } else {
                throw new Error(result.message || result.error || 'Nieznany błąd');
            }
        } catch (error) {
            showToast(`Błąd podczas kończenia operacji: ${error.message}`, 'error');
        }
    });

    async function handleCancelTransferClick(id) {
        if (!confirm(`Czy na pewno chcesz anulować operację o ID ${id}?`)) return;

        try {
            const response = await fetch('/api/operations/roztankuj-cysterne/anuluj', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id_operacji: id })
            });
            const result = await response.json();
            if (response.ok) {
                showToast(`Operacja ${id} została anulowana.`, 'info');
                updateUI();
            } else {
                throw new Error(result.error || 'Nieznany błąd');
            }
        } catch (error) {
            showToast(`Błąd podczas anulowania operacji: ${error.message}`, 'error');
        }
    }
    
    document.body.addEventListener('click', function(e) {
        const target = e.target.closest('.action-btn');
        if (!target) return;

        const action = target.dataset.action;
        const id = target.dataset.id;
        const name = target.dataset.name;
        
        if (action === 'start-transfer') handleStartTransferClick(id, name);
        if (action === 'end-transfer') handleEndTransferClick(id);
        if (action === 'cancel-transfer') handleCancelTransferClick(id);
    });

    refreshButton.addEventListener('click', updateUI);
    
    // Toast function
    function showToast(message, type = 'info') {
        Toastify({
            text: message,
            duration: 3000,
            close: true,
            gravity: "top",
            position: "right",
            backgroundColor: type === 'success' ? '#28a745' : (type === 'error' ? '#dc3545' : '#17a2b8'),
        }).showToast();
    }

    updateUI();
    setInterval(updateUI, 30000); // Auto-refresh every 30 seconds
}); 