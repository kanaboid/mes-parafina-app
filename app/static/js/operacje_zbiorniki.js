/**
 * Operacje zbiorniki – kompaktowy widok operacji.
 * Uproszczona logika wyekstrahowana z dashboard.js (przelewy, log operacji, dmuchanie).
 */
document.addEventListener('DOMContentLoaded', () => {
    let latestDashboardData = {};

    const gridReaktory = document.getElementById('grid-reaktory');
    const gridBeczkiBrudne = document.getElementById('grid-beczki-brudne');
    const gridBeczkiCzyste = document.getElementById('grid-beczki-czyste');
    const activeOperationsContainer = document.getElementById('active-operations-log');
    const lastUpdatedEl = document.getElementById('oz-last-updated');
    const tanksRoot = document.getElementById('oz-tanks-root');

    const modals = {
        transferTankToTank: new bootstrap.Modal(document.getElementById('transfer-tank-to-tank-modal')),
        finishTransferTankToTank: new bootstrap.Modal(document.getElementById('finish-transfer-tank-to-tank-modal')),
        przelewDest: new bootstrap.Modal(document.getElementById('przelew-dest-modal')),
        ocenaProbki: new bootstrap.Modal(document.getElementById('ocena-probki-modal')),
        naMagazyn: new bootstrap.Modal(document.getElementById('na-magazyn-modal')),
        dmuchanieChangeDest: new bootstrap.Modal(document.getElementById('dmuchanie-change-dest-modal')),
        wyborDmuchania: new bootstrap.Modal(document.getElementById('wybor-dmuchania-modal')),
        dmuchanieCzyszczenie: new bootstrap.Modal(document.getElementById('dmuchanie-czyszczenie-modal')),
        dmuchanieRurociagu: new bootstrap.Modal(document.getElementById('dmuchanie-rurociagu-modal')),
        startFiltration: new bootstrap.Modal(document.getElementById('start-filtration-modal')),
        filtracjaNaPlacku: new bootstrap.Modal(document.getElementById('filtracja-na-placku-modal')),
        dobielanie: new bootstrap.Modal(document.getElementById('dobielanie-modal'))
    };

    const forms = {
        transferTankToTank: document.getElementById('transfer-tank-to-tank-form'),
        finishTransferTankToTank: document.getElementById('finish-transfer-tank-to-tank-form'),
        przelewDest: document.getElementById('przelew-dest-form'),
        ocenaProbki: document.getElementById('ocena-probki-form'),
        naMagazyn: document.getElementById('na-magazyn-form'),
        dmuchanieChangeDest: document.getElementById('dmuchanie-change-dest-form'),
        wyborDmuchania: document.getElementById('wybor-dmuchania-form'),
        dmuchanieCzyszczenie: document.getElementById('dmuchanie-czyszczenie-form'),
        dmuchanieRurociagu: document.getElementById('dmuchanie-rurociagu-form'),
        startFiltration: document.getElementById('start-filtration-form'),
        filtracjaNaPlacku: document.getElementById('filtracja-na-placku-form'),
        dobielanie: document.getElementById('dobielanie-form')
    };

    function formatValue(value, unit = '', decimalPlaces = 1) {
        if (value === null || typeof value === 'undefined') {
            return 'B/D';
        }
        if (typeof value === 'number') {
            return `${value.toFixed(decimalPlaces)}${unit}`;
        }
        return `${value}${unit}`;
    }

    function showToast(message, type = 'info') {
        if (typeof Toastify !== 'undefined') {
            const bg = type === 'error' ? '#dc3545' : type === 'success' ? '#198754' : '#0d6efd';
            Toastify({
                text: message,
                duration: 4000,
                gravity: 'top',
                position: 'right',
                style: { background: bg }
            }).showToast();
            return;
        }
        if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
            const bgClass = type === 'error' ? 'bg-danger' : type === 'success' ? 'bg-success' : 'bg-info';
            const toastHTML = `
                <div class="toast align-items-center text-white ${bgClass} border-0" role="alert">
                    <div class="d-flex">
                        <div class="toast-body">${message}</div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                    </div>
                </div>`;
            const container = document.createElement('div');
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            container.innerHTML = toastHTML;
            document.body.appendChild(container);
            const toastEl = container.querySelector('.toast');
            const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
            toast.show();
            toastEl.addEventListener('hidden.bs.toast', () => container.remove());
            return;
        }
        alert(message);
    }

    function getMaterialLabel(partia) {
        if (!partia || !partia.sklad || partia.sklad.length === 0) {
            return '';
        }
        const types = [...new Set(partia.sklad.map(item => item.material_type))];
        return types.join(' + ');
    }

    function buildLevelHtml(item) {
        if (item.odczyt_mm == null) {
            return '';
        }
        if (item.poziom_tony != null) {
            return `<div class="oz-tank-level"><i class="fas fa-weight me-1"></i>${formatValue(item.poziom_tony, ' t', 2)} <span class="text-muted">(${formatValue(item.odczyt_mm / 10, ' cm', 0)})</span></div>`;
        }
        if (item.ma_kalibracje === false) {
            return `<div class="oz-tank-level text-warning"><i class="fas fa-exclamation-triangle me-1"></i>Brak kalibracji (${formatValue(item.odczyt_mm / 10, ' cm', 0)})</div>`;
        }
        return `<div class="oz-tank-level"><i class="fas fa-ruler-vertical me-1"></i>${formatValue(item.odczyt_mm / 10, ' cm', 0)}</div>`;
    }

    /** Menu operacji reaktora (logika jak w dashboard.js). */
    function buildReactorOpsDropdownHtml(r) {
        const esc = (s) => (s || '').replace(/"/g, '&quot;');
        const id = r.id;
        const nazwa = esc(r.nazwa);
        const waga = r.partia ? r.partia.waga_kg : '0';
        const mixId = r.partia ? r.partia.id : '';
        const items = [];

        const isOnlyWydmuch = r.partia && r.partia.sklad && r.partia.sklad.length > 0 &&
            r.partia.sklad.every(item => (item.material_type || '').toUpperCase() === 'WYDMUCH');

        const canDobielanie = r.partia && !isOnlyWydmuch &&
            ['SUROWY', 'PODGRZEWANY', 'DO_PONOWNEJ_FILTRACJI', 'FILTRACJA_PRZELEW_PRZERWANE'].includes(r.partia.process_status);
        if (canDobielanie) {
            items.push(`
                <li><button type="button" class="dropdown-item action-btn" data-action="open-dobielanie-modal"
                    data-sprzet-id="${id}" data-sprzet-nazwa="${nazwa}" data-mix-id="${mixId}">
                    <i class="fas fa-cube me-1"></i>Dobielanie
                </button></li>`);
        }

        if (r.partia && !isOnlyWydmuch) {
            const ps = r.partia.process_status;
            if (ps === 'DOBIELONY_OCZEKUJE') {
                items.push(`
                    <li><button type="button" class="dropdown-item action-btn" data-action="open-start-filtration-modal"
                        data-sprzet-id="${id}" data-sprzet-nazwa="${nazwa}" data-mix-id="${mixId}">
                        <i class="fas fa-filter me-1"></i>Start filtracji
                    </button></li>`);
            } else if (ps === 'FILTRACJA_KOLO' || ps === 'OCZEKUJE_NA_OCENE') {
                items.push(`
                    <li><button type="button" class="dropdown-item action-btn" data-action="open-start-filtration-modal"
                        data-sprzet-id="${id}" data-sprzet-nazwa="${nazwa}" data-mix-id="${mixId}">
                        <i class="fas fa-filter me-1"></i>Start filtracji (koło)
                    </button></li>`);
            }

            const AKTYWNA_FILTRACJA = [
                'DOBIELONY_OCZEKUJE',
                'FILTRACJA_PLACEK_KOLO', 'FILTRACJA_PLACEK_PRZELEW',
                'FILTRACJA_PRZELEW', 'FILTRACJA_WYDMUCH', 'FILTRACJA_NA_PLACKU'
            ];
            if (!AKTYWNA_FILTRACJA.includes(ps)) {
                items.push(`
                    <li><button type="button" class="dropdown-item action-btn" data-action="open-filtracja-na-placku-modal"
                        data-sprzet-id="${id}" data-sprzet-nazwa="${nazwa}" data-mix-id="${mixId}">
                        <i class="fas fa-filter me-1"></i>Filtracja na placku
                    </button></li>`);
            }
        }

        if (r.partia && r.partia.process_status === 'ZATWIERDZONA') {
            items.push(`
                <li><button type="button" class="dropdown-item action-btn" data-action="open-transfer-modal"
                    data-sprzet-id="${id}" data-sprzet-nazwa="${nazwa}" data-partia-waga="${waga}">
                    <i class="fas fa-warehouse me-1"></i>Na magazyn (przelew)
                </button></li>`);
        }

        const menuBody = items.length > 0
            ? items.join('')
            : '<li><span class="dropdown-item-text text-muted small">Brak operacji dla tego statusu</span></li>';

        return `
            <div class="dropdown oz-reactor-ops">
                <button type="button" class="btn btn-outline-primary btn-sm dropdown-toggle w-100"
                    data-bs-toggle="dropdown" data-bs-auto-close="true" aria-expanded="false"
                    id="oz-ops-dd-${id}">
                    <i class="fas fa-bolt me-1"></i>Operacje
                </button>
                <ul class="dropdown-menu dropdown-menu-end oz-reactor-ops-menu" aria-labelledby="oz-ops-dd-${id}">
                    ${menuBody}
                </ul>
            </div>`;
    }

    function renderCompactTanks(container, items, options = {}) {
        if (!container) return;
        container.innerHTML = '';
        if (!items || items.length === 0) {
            container.innerHTML = '<p class="text-muted small mb-0">Brak danych.</p>';
            return;
        }

        const variant = options.variant || 'reactor';

        items.forEach(item => {
            const isEmpty = !item.partia || !item.partia.waga_kg || item.partia.waga_kg <= 0;
            const inTransfer = item.stan_sprzetu === 'W transferze';
            let cardClass = 'oz-tank-card';
            if (variant === 'dirty') cardClass += ' oz-dirty';
            else if (variant === 'clean') cardClass += ' oz-clean';
            else cardClass += ' oz-reactor';
            if (isEmpty) cardClass += ' oz-empty';
            if (inTransfer) cardClass += ' oz-transfer';

            const material = getMaterialLabel(item.partia);
            const materialHtml = material
                ? `<div class="oz-tank-material" title="${material}">${material}</div>`
                : '';

            let processHtml = '';
            if (item.partia && item.partia.process_status) {
                processHtml = `<div class="oz-tank-process"><span class="badge bg-secondary">${item.partia.process_status}</span></div>`;
            } else if (isEmpty) {
                processHtml = '<div class="oz-tank-process"><span class="text-muted">Pusty</span></div>';
            }

            let weightHtml = '';
            let progressHtml = '';
            if (item.partia && item.partia.waga_kg > 0) {
                const wagaTon = (item.partia.waga_kg / 1000).toFixed(2);
                const pojTon = item.pojemnosc_kg ? (item.pojemnosc_kg / 1000).toFixed(1) : null;
                weightHtml = `<div class="oz-tank-weight"><span>Waga</span><strong>${wagaTon} t${pojTon ? ` / ${pojTon} t` : ''}</strong></div>`;
                if (item.pojemnosc_kg && item.pojemnosc_kg > 0) {
                    const pct = Math.min(100, (item.partia.waga_kg / item.pojemnosc_kg) * 100);
                    let barClass = 'bg-info';
                    if (pct > 95) barClass = 'bg-danger';
                    else if (pct > 80) barClass = 'bg-warning';
                    progressHtml = `
                        <div class="progress oz-tank-progress">
                            <div class="progress-bar ${barClass}" style="width:${pct.toFixed(0)}%"></div>
                        </div>
                        <div class="text-end" style="font-size:0.58rem;color:#6c757d">${pct.toFixed(0)}%</div>`;
                }
            }

            const levelHtml = buildLevelHtml(item);
            const wagaAttr = item.partia ? item.partia.waga_kg : '0';
            const escNazwa = (item.nazwa || '').replace(/"/g, '&quot;');

            let actionsHtml = `
                <button type="button" class="btn btn-info action-btn"
                    data-action="open-transfer-modal"
                    data-sprzet-id="${item.id}"
                    data-sprzet-nazwa="${escNazwa}"
                    data-partia-waga="${wagaAttr}">
                    <i class="fas fa-exchange-alt"></i> Przelej
                </button>
                <a class="btn btn-outline-secondary"
                    href="/sprzet/${item.id}/details"
                    title="Szczegóły zbiornika">
                    <i class="fas fa-info-circle"></i>
                </a>`;

            if (variant === 'reactor') {
                actionsHtml += buildReactorOpsDropdownHtml(item);
            }

            container.insertAdjacentHTML('beforeend', `
                <article class="${cardClass}" id="oz-tank-${item.id}">
                    <div class="oz-tank-head">
                        <span class="oz-tank-name">${item.nazwa}</span>
                        <span class="oz-tank-status" title="${item.stan_sprzetu || 'Gotowy'}">${item.stan_sprzetu || 'Gotowy'}</span>
                    </div>
                    ${materialHtml}
                    ${processHtml}
                    ${weightHtml}
                    ${progressHtml}
                    ${levelHtml}
                    <div class="oz-tank-actions">
                        ${actionsHtml}
                    </div>
                </article>
            `);
        });
    }

    function renderActiveOperations(operations) {
        if (!activeOperationsContainer) return;
        activeOperationsContainer.innerHTML = '';
        if (!operations || operations.length === 0) {
            activeOperationsContainer.innerHTML = '<div class="list-group-item"><p class="text-muted mb-0">Brak aktywnych operacji.</p></div>';
            return;
        }

        operations.forEach(op => {
            const startTime = new Date(op.czas_rozpoczecia);
            const timeSince = Math.round((new Date() - startTime) / 1000 / 60);
            const typ = (op.typ_operacji || '').toString().trim();
            const canContinueToPrzelew = typ === 'FILTRACJA_PLACEK_KOLO' || typ === 'FILTRACJA_WYDMUCH';
            const canContinueToKolo = typ === 'FILTRACJA_PRZELEW' || typ === 'FILTRACJA_PLACEK_PRZELEW' || typ === 'FILTRACJA_NA_PLACKU';
            const canContinueToOcena = typ === 'FILTRACJA_KOLO';
            const canContinueToMagazyn = typ === 'FILTRACJA_KOLO_ZATWIERDZONA';
            const canContinueToDmuchanie =
                typ === 'NA_MAGAZYN' ||
                typ === 'FILTRACJA_KOLO_DO_PONOWNEJ' ||
                (op.opis && (String(op.opis).indexOf('NA_MAGAZYN') === 0 || String(op.opis).indexOf('FILTRACJA_KOLO_DO_PONOWNEJ') === 0));
            const isDmuchanie = typ === 'DMUCHANIE' || (op.opis && String(op.opis).indexOf('DMUCHANIE:') === 0);
            const isDmuchanieCzyszczenie = typ === 'DMUCHANIE_CZYSZCZENIE';
            const isDmuchanieRurociagu = typ === 'DMUCHANIE_RUROCIAGU';
            const isTransferTankToTank = typ === 'TRANSFER_TANK_TO_TANK';

            let continueBtn = '';
            let changeDestBtn = '';
            if (canContinueToPrzelew) {
                continueBtn = `<button type="button" class="btn btn-sm btn-outline-primary continue-to-przelew-btn" data-op-id="${op.id}" data-zrodlo="${(op.zrodlo || '').replace(/"/g, '&quot;')}">Następny (PRZELEW)</button>`;
            } else if (canContinueToKolo) {
                continueBtn = `<button type="button" class="btn btn-sm btn-outline-primary continue-to-kolo-btn" data-op-id="${op.id}">Następny (KOŁO)</button>`;
            } else if (canContinueToOcena) {
                continueBtn = `<button type="button" class="btn btn-sm btn-outline-primary continue-to-ocena-btn" data-op-id="${op.id}">Ocena próbki</button>`;
            } else if (canContinueToMagazyn) {
                continueBtn = `<button type="button" class="btn btn-sm btn-outline-success continue-to-magazyn-btn" data-op-id="${op.id}">NA_MAGAZYN</button>`;
            } else if (canContinueToDmuchanie) {
                continueBtn = `<button type="button" class="btn btn-sm btn-outline-secondary continue-to-dmuchanie-btn"
                    data-op-id="${op.id}" data-zrodlo-nazwa="${(op.zrodlo || '').replace(/"/g, '&quot;')}"
                    data-id-zrodla="${op.id_sprzetu_zrodlowego || ''}">DMUCHANIE</button>`;
            }
            if (isDmuchanie) {
                const zrodloAttr = `data-zrodlo-nazwa="${(op.zrodlo || '').replace(/"/g, '&quot;')}" data-id-zrodla="${op.id_sprzetu_zrodlowego || ''}"`;
                changeDestBtn = `
                    <button type="button" class="btn btn-sm btn-outline-primary dmuchanie-change-dest-btn" data-op-id="${op.id}">Zmień cel</button>
                    <button type="button" class="btn btn-sm btn-outline-warning konwersja-dmuchanie-btn" data-op-id="${op.id}" ${zrodloAttr}>Na czyszczenie</button>`;
            }

            let endBtn = '';
            if (isDmuchanieCzyszczenie) {
                endBtn = `<button type="button" class="btn btn-sm btn-outline-warning finish-dmuchanie-czyszczenie-btn" data-op-id="${op.id}">Zakończ czyszczenie</button>`;
            } else if (isDmuchanieRurociagu) {
                endBtn = `<button type="button" class="btn btn-sm btn-outline-secondary finish-dmuchanie-rurociagu-btn" data-op-id="${op.id}">Zakończ rurociąg</button>`;
            } else if (isTransferTankToTank) {
                endBtn = `<button type="button" class="btn btn-sm btn-outline-secondary finish-transfer-tank-to-tank-btn" data-op-id="${op.id}">Zakończ transfer</button>`;
            } else {
                endBtn = `<button type="button" class="btn btn-sm btn-outline-danger end-operation-btn" data-op-id="${op.id}">Zakończ</button>`;
            }

            activeOperationsContainer.insertAdjacentHTML('beforeend', `
                <div class="list-group-item d-flex justify-content-between align-items-start flex-wrap gap-2">
                    <div class="flex-grow-1 min-w-0">
                        <div class="d-flex w-100 justify-content-between gap-1">
                            <h6 class="mb-1 text-info text-truncate">${op.opis}</h6>
                            <small class="text-muted flex-shrink-0">${timeSince} min</small>
                        </div>
                        <p class="mb-0 small">
                            <span class="badge bg-secondary">${op.zrodlo}</span>
                            <i class="fas fa-long-arrow-alt-right mx-1"></i>
                            <span class="badge bg-success">${op.cel}</span>
                        </p>
                    </div>
                    <div class="d-flex gap-1 flex-wrap">${continueBtn}${changeDestBtn}${endBtn}</div>
                </div>
            `);
        });
    }

    function updateUI(data) {
        latestDashboardData = data;
        renderCompactTanks(gridReaktory, data.all_reactors, { variant: 'reactor' });
        renderCompactTanks(gridBeczkiBrudne, data.beczki_brudne, { variant: 'dirty' });
        renderCompactTanks(gridBeczkiCzyste, data.beczki_czyste, { variant: 'clean' });
        renderActiveOperations(data.active_operations);
        if (lastUpdatedEl) {
            lastUpdatedEl.textContent = `Aktualizacja: ${new Date().toLocaleTimeString()}`;
        }
    }

    async function initialLoad() {
        try {
            const response = await fetch('/api/dashboard/main-status');
            if (!response.ok) throw new Error('Błąd pobierania danych');
            const data = await response.json();
            updateUI(data);
        } catch (error) {
            console.error(error);
            if (gridReaktory) {
                gridReaktory.innerHTML = '<p class="text-danger small">Nie udało się załadować danych.</p>';
            }
            showToast(error.message, 'error');
        }
    }

    async function handleOpenTransferModal(sourceId, sourceName) {
        document.getElementById('transfer-source-id').value = sourceId;
        document.getElementById('transfer-source-name').textContent = sourceName;
        const destinationSelect = document.getElementById('transfer-destination-id');
        destinationSelect.innerHTML = '<option>Ładowanie celów...</option>';
        destinationSelect.disabled = true;
        modals.transferTankToTank.show();

        try {
            const response = await fetch('/api/sprzet/dostepne-cele');
            if (!response.ok) throw new Error('Błąd ładowania listy celów');
            const destinations = await response.json();
            destinationSelect.innerHTML = '<option value="">-- Wybierz cel --</option>';
            const grouped = destinations.reduce((acc, dest) => {
                if (dest.id.toString() === sourceId.toString()) return acc;
                const type = dest.typ_sprzetu;
                if (!acc[type]) acc[type] = [];
                acc[type].push(dest);
                return acc;
            }, {});
            for (const type in grouped) {
                const optgroup = document.createElement('optgroup');
                optgroup.label = type;
                grouped[type].forEach(dest => {
                    const option = document.createElement('option');
                    option.value = dest.id;
                    let label = dest.nazwa_unikalna;
                    if (dest.mix_info && dest.mix_info.total_weight > 0.01) {
                        const waga = (dest.mix_info.total_weight / 1000).toFixed(2);
                        const mats = dest.mix_info.components.map(c => c.material_type).join(', ');
                        label += ` (${waga} t, ${mats})`;
                    } else {
                        label += ' (Pusty)';
                    }
                    option.textContent = label;
                    optgroup.appendChild(option);
                });
                destinationSelect.appendChild(optgroup);
            }
            destinationSelect.disabled = false;
        } catch (error) {
            destinationSelect.innerHTML = `<option value="">Błąd: ${error.message}</option>`;
            showToast(error.message, 'error');
        }
    }

    function fillReaktoryCelSelect(selectId) {
        const reaktory = (latestDashboardData.all_reactors || []).map(r => ({
            id: r.id,
            nazwa: r.nazwa || String(r.id)
        }));
        const sel = document.getElementById(selectId);
        if (!sel) return;
        sel.innerHTML = '<option value="">-- wybierz reaktor --</option>';
        reaktory.forEach(r => {
            const opt = document.createElement('option');
            opt.value = r.id;
            opt.textContent = r.nazwa;
            sel.appendChild(opt);
        });
    }

    function fillSprzetSelects(zrodloSelectId, celSelectId) {
        const allSprzet = [
            ...(latestDashboardData.all_reactors || []).map(r => ({ id: r.id, nazwa: r.nazwa })),
            ...(latestDashboardData.beczki_czyste || []).map(b => ({ id: b.id, nazwa: b.nazwa })),
            ...(latestDashboardData.beczki_brudne || []).map(b => ({ id: b.id, nazwa: b.nazwa }))
        ];
        [zrodloSelectId, celSelectId].forEach(selectId => {
            const sel = document.getElementById(selectId);
            if (!sel) return;
            const currentVal = sel.value;
            sel.innerHTML = '<option value="">-- wybierz --</option>';
            allSprzet.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.nazwa;
                sel.appendChild(opt);
            });
            if (currentVal) sel.value = currentVal;
        });
    }

    // Socket.IO
    const socket = io();
    socket.on('dashboard_update', (data) => updateUI(data));

    async function handleOpenStartFiltrationModal(mixId, reaktorNazwa, idReaktoraZrodlowego) {
        document.getElementById('start-filtration-mix-id').value = mixId;
        document.getElementById('start-filtration-reaktor-name').textContent = reaktorNazwa;
        document.getElementById('start-filtration-reaktor-nazwa').value = reaktorNazwa;
        const container = document.getElementById('start-filtration-destinations-container');
        container.innerHTML = '<div class="list-group-item text-muted">Ładowanie celów...</div>';
        document.getElementById('start-filtration-error').classList.add('d-none');
        modals.startFiltration.show();

        if (!idReaktoraZrodlowego) {
            container.innerHTML = '<p class="text-danger mb-0 p-2">Brak reaktora źródłowego.</p>';
            return;
        }
        try {
            const response = await fetch(`/api/operations/start-filtration-destinations?id_reaktora_zrodlowego=${idReaktoraZrodlowego}`);
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.message || 'Błąd ładowania listy celów');
            }
            const data = await response.json();
            const destinations = data.destinations || [];
            container.innerHTML = '';
            if (destinations.length === 0) {
                container.innerHTML = '<p class="text-muted mb-0 p-2">Brak celów z możliwą trasą.</p>';
                return;
            }
            destinations.forEach((dest, index) => {
                const radioId = `start-filtration-dest-${dest.id}`;
                const title = dest.is_same_reactor ? `${dest.nazwa_unikalna} (koło)` : dest.nazwa_unikalna;
                container.insertAdjacentHTML('beforeend', `
                    <label class="list-group-item list-group-item-action" for="${radioId}">
                        <input class="form-check-input me-2" type="radio" name="start-filtration-destination"
                            value="${dest.id}" id="${radioId}" data-nazwa="${dest.nazwa_unikalna}" ${index === 0 ? 'checked' : ''}>
                        ${title}
                    </label>`);
            });
        } catch (error) {
            container.innerHTML = `<p class="text-danger mb-0 p-2">${error.message}</p>`;
        }
    }

    function handleReactorTankAction(btn) {
        const action = btn.dataset.action;
        const sprzetId = btn.dataset.sprzetId;
        const sprzetNazwa = btn.dataset.sprzetNazwa;

        if (action === 'open-transfer-modal') {
            handleOpenTransferModal(sprzetId, sprzetNazwa);
        } else if (action === 'open-dobielanie-modal') {
            document.getElementById('dobielanie-mix-id').value = btn.dataset.mixId || '';
            document.getElementById('dobielanie-reaktor-name').textContent = sprzetNazwa || '—';
            document.getElementById('dobielanie-bags').value = 6;
            document.getElementById('dobielanie-weight').value = 25;
            document.getElementById('dobielanie-error').classList.add('d-none');
            modals.dobielanie.show();
        } else if (action === 'open-start-filtration-modal') {
            handleOpenStartFiltrationModal(btn.dataset.mixId, sprzetNazwa, sprzetId);
        } else if (action === 'open-filtracja-na-placku-modal') {
            document.getElementById('filtracja-na-placku-id-zrodla').value = sprzetId;
            document.getElementById('filtracja-na-placku-zrodlo-name').textContent = sprzetNazwa || '—';
            document.getElementById('filtracja-na-placku-error').classList.add('d-none');
            const destContainer = document.getElementById('filtracja-na-placku-destinations-container');
            destContainer.innerHTML = '<div class="list-group-item text-muted">Ładowanie...</div>';
            modals.filtracjaNaPlacku.show();
            fetch(`/api/operations/filtracja-na-placku-destinations?id_sprzetu_zrodlowego=${sprzetId}`)
                .then(res => res.ok ? res.json() : Promise.reject(new Error('Błąd ładowania')))
                .then(data => {
                    const destinations = data.destinations || [];
                    destContainer.innerHTML = '';
                    if (destinations.length === 0) {
                        destContainer.innerHTML = '<p class="text-muted mb-0 p-2">Brak pustych reaktorów z trasą.</p>';
                        return;
                    }
                    destinations.forEach((destItem, index) => {
                        const radioId = `fnp-dest-${destItem.id}`;
                        destContainer.insertAdjacentHTML('beforeend', `
                            <label class="list-group-item list-group-item-action" for="${radioId}">
                                <input class="form-check-input me-2" type="radio" name="fnp-destination"
                                    value="${destItem.id}" id="${radioId}" ${index === 0 ? 'checked' : ''}>
                                ${destItem.nazwa_unikalna || destItem.id}
                            </label>`);
                    });
                })
                .catch(() => {
                    destContainer.innerHTML = '<p class="text-danger mb-0 p-2">Nie udało się załadować celów.</p>';
                });
        }
    }

    // Kliknięcia na kafelkach zbiorników
    if (tanksRoot) {
        tanksRoot.addEventListener('click', (e) => {
            const btn = e.target.closest('.action-btn');
            if (!btn || !btn.dataset.action) return;
            e.preventDefault();
            e.stopPropagation();
            handleReactorTankAction(btn);
        });
    }

    // Log operacji – delegacja zdarzeń
    if (activeOperationsContainer) {
        activeOperationsContainer.addEventListener('click', async (e) => {
            const continueOcenaBtn = e.target.closest('.continue-to-ocena-btn');
            const continuePrzelewBtn = e.target.closest('.continue-to-przelew-btn');
            const continueMagazynBtn = e.target.closest('.continue-to-magazyn-btn');
            const continueDmuchanieBtn = e.target.closest('.continue-to-dmuchanie-btn');
            const dmuchanieChangeDestBtn = e.target.closest('.dmuchanie-change-dest-btn');
            const konwersjaDmuchanieBtn = e.target.closest('.konwersja-dmuchanie-btn');
            const finishCzyszczenieBtn = e.target.closest('.finish-dmuchanie-czyszczenie-btn');
            const finishRurociaguBtn = e.target.closest('.finish-dmuchanie-rurociagu-btn');
            const finishTransferTankBtn = e.target.closest('.finish-transfer-tank-to-tank-btn');
            const continueKoloBtn = e.target.closest('.continue-to-kolo-btn');
            const endBtn = e.target.closest('.end-operation-btn');

            if (continueOcenaBtn) {
                e.preventDefault();
                const opId = continueOcenaBtn.getAttribute('data-op-id');
                document.getElementById('ocena-probki-id-operacji').value = opId;
                document.querySelector('#ocena-ok').checked = true;
                document.getElementById('ocena-powod').value = '';
                document.getElementById('ocena-powod-wrap').classList.add('d-none');
                document.getElementById('ocena-probki-error').classList.add('d-none');
                modals.ocenaProbki.show();
                return;
            }

            if (continuePrzelewBtn) {
                e.preventDefault();
                const opId = continuePrzelewBtn.getAttribute('data-op-id');
                document.getElementById('przelew-dest-id-operacji').value = opId;
                document.getElementById('przelew-dest-zrodlo-name').textContent = continuePrzelewBtn.getAttribute('data-zrodlo') || '—';
                document.getElementById('przelew-dest-error').classList.add('d-none');
                const container = document.getElementById('przelew-dest-container');
                container.innerHTML = '<div class="list-group-item text-muted">Ładowanie...</div>';
                modals.przelewDest.show();
                fetch(`/api/operations/przelew-destinations?id_operacji=${opId}`)
                    .then(res => res.ok ? res.json() : Promise.reject())
                    .then(data => {
                        const destinations = data.destinations || [];
                        container.innerHTML = '';
                        if (destinations.length === 0) {
                            container.innerHTML = '<p class="text-muted mb-0 p-2">Brak celów.</p>';
                            return;
                        }
                        destinations.forEach((item, index) => {
                            const radioId = `przelew-dest-${item.id}`;
                            container.insertAdjacentHTML('beforeend', `
                                <label class="list-group-item list-group-item-action" for="${radioId}">
                                    <input class="form-check-input me-2" type="radio" name="przelew-dest-reaktor"
                                        value="${item.id}" id="${radioId}" ${index === 0 ? 'checked' : ''}>
                                    ${item.nazwa_unikalna || item.id}
                                </label>`);
                        });
                    })
                    .catch(() => { container.innerHTML = '<p class="text-danger mb-0 p-2">Błąd ładowania.</p>'; });
                return;
            }

            if (continueMagazynBtn) {
                e.preventDefault();
                const opId = continueMagazynBtn.getAttribute('data-op-id');
                document.getElementById('na-magazyn-id-operacji').value = opId;
                document.getElementById('na-magazyn-error').classList.add('d-none');
                const container = document.getElementById('na-magazyn-destinations-container');
                const beczki = latestDashboardData.beczki_czyste || [];
                container.innerHTML = '';
                if (beczki.length === 0) {
                    container.innerHTML = '<p class="text-muted mb-0">Brak beczek czystych.</p>';
                } else {
                    beczki.forEach((b, index) => {
                        let zawartosc = 'Pusty';
                        if (b.partia && b.partia.sklad && b.partia.sklad.length > 0) {
                            const wagaTon = b.partia.waga_kg ? (b.partia.waga_kg / 1000).toFixed(2) : '0';
                            zawartosc = `${wagaTon} t, ${b.partia.sklad.map(c => c.material_type).join(', ')}`;
                        }
                        const radioId = `na-magazyn-dest-${b.id}`;
                        container.insertAdjacentHTML('beforeend', `
                            <label class="list-group-item list-group-item-action" for="${radioId}">
                                <input class="form-check-input me-2" type="radio" name="na-magazyn-destination"
                                    value="${b.id}" id="${radioId}" ${index === 0 ? 'checked' : ''}>
                                <strong>${b.nazwa}</strong> – <small class="text-muted">${zawartosc}</small>
                            </label>`);
                    });
                }
                modals.naMagazyn.show();
                return;
            }

            if (continueDmuchanieBtn) {
                e.preventDefault();
                const opId = continueDmuchanieBtn.getAttribute('data-op-id');
                document.getElementById('wybor-dmuchania-id-operacji').value = opId;
                document.getElementById('wybor-dmuchania-id-zrodla').value = continueDmuchanieBtn.getAttribute('data-id-zrodla') || '';
                document.getElementById('wybor-dmuchania-mode').value = 'continue';
                document.getElementById('wybor-dmuchania-zrodlo-info').textContent = continueDmuchanieBtn.getAttribute('data-zrodlo-nazwa') || '—';
                document.getElementById('dmuchanie-typ-standard').checked = true;
                document.getElementById('wybor-dmuchania-cel-wrap').style.display = 'none';
                document.querySelectorAll('.wybor-dmuchania-typ-wrap').forEach(el => { el.style.display = ''; });
                document.getElementById('wybor-dmuchania-error').classList.add('d-none');
                fillReaktoryCelSelect('wybor-dmuchania-cel');
                modals.wyborDmuchania.show();
                return;
            }

            if (dmuchanieChangeDestBtn) {
                e.preventDefault();
                const opId = dmuchanieChangeDestBtn.getAttribute('data-op-id');
                document.getElementById('dmuchanie-change-dest-id-operacji').value = opId;
                document.getElementById('dmuchanie-change-dest-error').classList.add('d-none');
                const container = document.getElementById('dmuchanie-change-dest-container');
                container.innerHTML = '<div class="list-group-item text-muted">Ładowanie...</div>';
                modals.dmuchanieChangeDest.show();
                fetch(`/api/operations/dmuchanie-destinations?id_operacji=${opId}`)
                    .then(res => res.ok ? res.json() : Promise.reject())
                    .then(data => {
                        const destinations = data.destinations || [];
                        container.innerHTML = '';
                        destinations.forEach((item, index) => {
                            const radioId = `dmuchanie-dest-${item.id}`;
                            container.insertAdjacentHTML('beforeend', `
                                <label class="list-group-item list-group-item-action" for="${radioId}">
                                    <input class="form-check-input me-2" type="radio" name="dmuchanie-change-dest"
                                        value="${item.id}" id="${radioId}" ${index === 0 ? 'checked' : ''}>
                                    ${item.nazwa_unikalna || item.id}
                                </label>`);
                        });
                    })
                    .catch(() => { container.innerHTML = '<p class="text-danger mb-0 p-2">Błąd ładowania.</p>'; });
                return;
            }

            if (konwersjaDmuchanieBtn) {
                e.preventDefault();
                const opId = konwersjaDmuchanieBtn.getAttribute('data-op-id');
                document.getElementById('wybor-dmuchania-id-operacji').value = opId;
                document.getElementById('wybor-dmuchania-id-zrodla').value = konwersjaDmuchanieBtn.getAttribute('data-id-zrodla') || '';
                document.getElementById('wybor-dmuchania-mode').value = 'convert';
                document.getElementById('wybor-dmuchania-zrodlo-info').textContent = konwersjaDmuchanieBtn.getAttribute('data-zrodlo-nazwa') || '—';
                document.querySelectorAll('.wybor-dmuchania-typ-wrap').forEach(el => { el.style.display = 'none'; });
                document.getElementById('dmuchanie-typ-czyszczenie').checked = true;
                document.getElementById('wybor-dmuchania-cel-wrap').style.display = '';
                document.getElementById('wybor-dmuchania-error').classList.add('d-none');
                const celSelect = document.getElementById('wybor-dmuchania-cel');
                celSelect.innerHTML = '<option value="">Ładowanie...</option>';
                fetch(`/api/operations/dmuchanie-czyszczenie-destinations?id_operacji=${opId}`)
                    .then(res => res.ok ? res.json() : { destinations: [] })
                    .then(data => {
                        celSelect.innerHTML = '<option value="">-- wybierz reaktor --</option>';
                        (data.destinations || []).forEach(d => {
                            const opt = document.createElement('option');
                            opt.value = d.id;
                            opt.textContent = d.nazwa_unikalna || d.id;
                            celSelect.appendChild(opt);
                        });
                    });
                modals.wyborDmuchania.show();
                return;
            }

            if (finishCzyszczenieBtn) {
                e.preventDefault();
                const opId = finishCzyszczenieBtn.getAttribute('data-op-id');
                finishCzyszczenieBtn.disabled = true;
                try {
                    const response = await fetch('/api/operations/finish-dmuchanie-czyszczenie', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ id_operacji: parseInt(opId, 10), operator: 'GUI' })
                    });
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.message || result.error);
                    showToast(result.message || 'Zakończono.', 'success');
                    initialLoad();
                } catch (err) {
                    showToast(err.message, 'error');
                    finishCzyszczenieBtn.disabled = false;
                }
                return;
            }

            if (finishRurociaguBtn) {
                e.preventDefault();
                const opId = finishRurociaguBtn.getAttribute('data-op-id');
                finishRurociaguBtn.disabled = true;
                try {
                    const response = await fetch('/api/operations/finish-dmuchanie-rurociagu', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ id_operacji: parseInt(opId, 10), operator: 'GUI' })
                    });
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.message || result.error);
                    showToast(result.message || 'Zakończono.', 'success');
                    initialLoad();
                } catch (err) {
                    showToast(err.message, 'error');
                    finishRurociaguBtn.disabled = false;
                }
                return;
            }

            if (finishTransferTankBtn) {
                e.preventDefault();
                document.getElementById('finish-transfer-id-operacji').value = finishTransferTankBtn.getAttribute('data-op-id');
                document.getElementById('finish-transfer-quantity').value = '';
                modals.finishTransferTankToTank.show();
                return;
            }

            if (continueKoloBtn) {
                e.preventDefault();
                const opId = continueKoloBtn.getAttribute('data-op-id');
                continueKoloBtn.disabled = true;
                try {
                    const response = await fetch('/api/operations/continue-to-kolo', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ id_operacji: parseInt(opId, 10) })
                    });
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.message || result.error);
                    showToast(result.message || 'FILTRACJA_KOLO rozpoczęta.', 'success');
                    initialLoad();
                } catch (err) {
                    showToast(err.message, 'error');
                    continueKoloBtn.disabled = false;
                }
                return;
            }

            if (!endBtn) return;
            e.preventDefault();
            const opId = endBtn.getAttribute('data-op-id');
            endBtn.disabled = true;
            try {
                const response = await fetch('/api/operations/zakoncz', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id_operacji: parseInt(opId, 10) })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || result.error);
                showToast(result.message || 'Operacja zakończona.', 'success');
                initialLoad();
            } catch (err) {
                showToast(err.message, 'error');
                endBtn.disabled = false;
            }
        });
    }

    // Formularze
    forms.transferTankToTank.addEventListener('submit', async (e) => {
        e.preventDefault();
        const sourceId = document.getElementById('transfer-source-id').value;
        const destinationId = document.getElementById('transfer-destination-id').value;
        if (!destinationId) {
            showToast('Wybierz zbiornik docelowy.', 'error');
            return;
        }
        try {
            const response = await fetch('/api/operations/start-transfer-tank-to-tank', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_tank_id: parseInt(sourceId, 10),
                    destination_tank_id: parseInt(destinationId, 10),
                    operator: 'GUI'
                })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || result.error);
            showToast(result.message || 'Transfer rozpoczęty.', 'success');
            modals.transferTankToTank.hide();
            initialLoad();
        } catch (error) {
            showToast(error.message, 'error');
        }
    });

    forms.finishTransferTankToTank.addEventListener('submit', async (e) => {
        e.preventDefault();
        const idOperacji = document.getElementById('finish-transfer-id-operacji').value;
        const quantity = document.getElementById('finish-transfer-quantity').value;
        if (!quantity || parseFloat(quantity) <= 0) {
            showToast('Podaj ilość (kg).', 'error');
            return;
        }
        try {
            const response = await fetch('/api/operations/finish-transfer-tank-to-tank', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id_operacji: parseInt(idOperacji, 10),
                    quantity_kg: parseFloat(quantity),
                    operator: 'GUI'
                })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || result.error);
            showToast(result.message || 'Transfer zakończony.', 'success');
            modals.finishTransferTankToTank.hide();
            initialLoad();
        } catch (err) {
            showToast(err.message, 'error');
        }
    });

    forms.przelewDest.addEventListener('submit', async (e) => {
        e.preventDefault();
        const idOperacji = document.getElementById('przelew-dest-id-operacji').value;
        const selected = document.querySelector('input[name="przelew-dest-reaktor"]:checked');
        const errorDiv = document.getElementById('przelew-dest-error');
        if (!selected) {
            errorDiv.textContent = 'Wybierz reaktor.';
            errorDiv.classList.remove('d-none');
            return;
        }
        errorDiv.classList.add('d-none');
        try {
            const response = await fetch('/api/operations/continue-to-przelew', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id_operacji: parseInt(idOperacji, 10),
                    id_reaktora_docelowego: parseInt(selected.value, 10)
                })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || result.error);
            showToast(result.message || 'FILTRACJA_PRZELEW rozpoczęta.', 'success');
            modals.przelewDest.hide();
            initialLoad();
        } catch (error) {
            errorDiv.textContent = error.message;
            errorDiv.classList.remove('d-none');
        }
    });

    forms.naMagazyn.addEventListener('submit', async (e) => {
        e.preventDefault();
        const idOperacji = document.getElementById('na-magazyn-id-operacji').value;
        const selected = document.querySelector('input[name="na-magazyn-destination"]:checked');
        const errorDiv = document.getElementById('na-magazyn-error');
        if (!selected) {
            errorDiv.textContent = 'Wybierz beczkę.';
            errorDiv.classList.remove('d-none');
            return;
        }
        errorDiv.classList.add('d-none');
        try {
            const response = await fetch('/api/operations/continue-to-magazyn', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id_operacji: parseInt(idOperacji, 10),
                    id_beczki_czystej: parseInt(selected.value, 10),
                    operator: 'GUI'
                })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || result.error);
            showToast(result.message || 'Przelano na magazyn.', 'success');
            modals.naMagazyn.hide();
            initialLoad();
        } catch (error) {
            errorDiv.textContent = error.message;
            errorDiv.classList.remove('d-none');
        }
    });

    forms.dmuchanieChangeDest.addEventListener('submit', async (e) => {
        e.preventDefault();
        const idOperacji = document.getElementById('dmuchanie-change-dest-id-operacji').value;
        const selected = document.querySelector('input[name="dmuchanie-change-dest"]:checked');
        const errorDiv = document.getElementById('dmuchanie-change-dest-error');
        if (!selected) {
            errorDiv.textContent = 'Wybierz cel.';
            errorDiv.classList.remove('d-none');
            return;
        }
        errorDiv.classList.add('d-none');
        try {
            const response = await fetch('/api/operations/dmuchanie-change-destination', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id_operacji: parseInt(idOperacji, 10),
                    id_sprzetu_docelowego: parseInt(selected.value, 10),
                    operator: 'GUI'
                })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || result.error);
            showToast(result.message || 'Cel zaktualizowany.', 'success');
            modals.dmuchanieChangeDest.hide();
            initialLoad();
        } catch (error) {
            errorDiv.textContent = error.message;
            errorDiv.classList.remove('d-none');
        }
    });

    document.querySelectorAll('input[name="ocena-wynik"]').forEach(radio => {
        radio.addEventListener('change', () => {
            const wrap = document.getElementById('ocena-powod-wrap');
            if (document.getElementById('ocena-do-ponownej').checked) {
                wrap.classList.remove('d-none');
            } else {
                wrap.classList.add('d-none');
            }
        });
    });

    forms.ocenaProbki.addEventListener('submit', async (e) => {
        e.preventDefault();
        const idOperacji = document.getElementById('ocena-probki-id-operacji').value;
        const wynikRadio = document.querySelector('input[name="ocena-wynik"]:checked');
        const errorDiv = document.getElementById('ocena-probki-error');
        if (!wynikRadio) {
            errorDiv.textContent = 'Wybierz wynik.';
            errorDiv.classList.remove('d-none');
            return;
        }
        const payload = { id_operacji: parseInt(idOperacji, 10), wynik_oceny: wynikRadio.value };
        const powod = document.getElementById('ocena-powod').value.trim();
        if (powod) payload.powod = powod;
        errorDiv.classList.add('d-none');
        try {
            const response = await fetch('/api/operations/continue-to-ocena', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || result.error);
            showToast(result.message || 'Ocena zapisana.', 'success');
            modals.ocenaProbki.hide();
            initialLoad();
        } catch (error) {
            errorDiv.textContent = error.message;
            errorDiv.classList.remove('d-none');
        }
    });

    document.querySelectorAll('input[name="wybor-dmuchania-typ"]').forEach(radio => {
        radio.addEventListener('change', async () => {
            const celWrap = document.getElementById('wybor-dmuchania-cel-wrap');
            if (celWrap) {
                celWrap.style.display = radio.value === 'DMUCHANIE_CZYSZCZENIE' ? '' : 'none';
            }
            if (radio.value === 'DMUCHANIE_CZYSZCZENIE') {
                const idOperacji = document.getElementById('wybor-dmuchania-id-operacji').value;
                const celSelect = document.getElementById('wybor-dmuchania-cel');
                if (idOperacji && celSelect) {
                    const res = await fetch(`/api/operations/dmuchanie-czyszczenie-destinations?id_operacji=${idOperacji}`);
                    const data = res.ok ? await res.json() : { destinations: [] };
                    celSelect.innerHTML = '<option value="">-- wybierz reaktor --</option>';
                    (data.destinations || []).forEach(d => {
                        const opt = document.createElement('option');
                        opt.value = d.id;
                        opt.textContent = d.nazwa_unikalna || d.id;
                        celSelect.appendChild(opt);
                    });
                }
            }
        });
    });

    forms.wyborDmuchania.addEventListener('submit', async (e) => {
        e.preventDefault();
        const idOperacji = document.getElementById('wybor-dmuchania-id-operacji').value;
        const mode = document.getElementById('wybor-dmuchania-mode').value;
        const errorDiv = document.getElementById('wybor-dmuchania-error');
        errorDiv.classList.add('d-none');

        if (mode === 'convert') {
            const idCelu = document.getElementById('wybor-dmuchania-cel').value;
            if (!idCelu) {
                errorDiv.textContent = 'Wybierz reaktor.';
                errorDiv.classList.remove('d-none');
                return;
            }
            try {
                const response = await fetch('/api/operations/convert-dmuchanie-to-czyszczenie', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id_operacji: parseInt(idOperacji, 10),
                        id_sprzetu_docelowego: parseInt(idCelu, 10),
                        operator: 'GUI'
                    })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || result.error);
                showToast(result.message || 'Przekształcono operację.', 'success');
                modals.wyborDmuchania.hide();
                initialLoad();
            } catch (err) {
                errorDiv.textContent = err.message;
                errorDiv.classList.remove('d-none');
            }
            return;
        }

        const selectedTyp = document.querySelector('input[name="wybor-dmuchania-typ"]:checked');
        const typ = selectedTyp ? selectedTyp.value : 'DMUCHANIE';
        if (typ === 'DMUCHANIE') {
            try {
                const response = await fetch('/api/operations/continue-to-dmuchanie', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id_operacji: parseInt(idOperacji, 10), operator: 'GUI' })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || result.error);
                showToast(result.message || 'DMUCHANIE rozpoczęte.', 'success');
                modals.wyborDmuchania.hide();
                initialLoad();
            } catch (err) {
                errorDiv.textContent = err.message;
                errorDiv.classList.remove('d-none');
            }
        } else {
            const idCelu = document.getElementById('wybor-dmuchania-cel').value;
            if (!idCelu) {
                errorDiv.textContent = 'Wybierz reaktor.';
                errorDiv.classList.remove('d-none');
                return;
            }
            try {
                const response = await fetch('/api/operations/continue-to-dmuchanie-czyszczenie', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id_operacji: parseInt(idOperacji, 10),
                        id_sprzetu_docelowego: parseInt(idCelu, 10),
                        operator: 'GUI'
                    })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || result.error);
                showToast(result.message || 'DMUCHANIE_CZYSZCZENIE rozpoczęte.', 'success');
                modals.wyborDmuchania.hide();
                initialLoad();
            } catch (err) {
                errorDiv.textContent = err.message;
                errorDiv.classList.remove('d-none');
            }
        }
    });

    const openDmuchanieCzyszczenieBtn = document.getElementById('open-dmuchanie-czyszczenie-btn');
    if (openDmuchanieCzyszczenieBtn) {
        openDmuchanieCzyszczenieBtn.addEventListener('click', async () => {
            const zrodloSelect = document.getElementById('dmuchanie-czyszczenie-zrodlo');
            const celSelect = document.getElementById('dmuchanie-czyszczenie-cel');
            const allSprzet = [
                ...(latestDashboardData.all_reactors || []).map(r => ({ id: r.id, nazwa: `${r.nazwa} (reaktor)` })),
                ...(latestDashboardData.beczki_czyste || []).map(b => ({ id: b.id, nazwa: `${b.nazwa} (beczka)` })),
                ...(latestDashboardData.beczki_brudne || []).map(b => ({ id: b.id, nazwa: `${b.nazwa} (beczka)` }))
            ];
            try {
                const res = await fetch('/api/sprzet/filtry');
                const filtry = res.ok ? await res.json() : [];
                filtry.forEach(f => {
                    allSprzet.push({ id: f.id, nazwa: `${f.nazwa_unikalna || f.id} (filtr)` });
                });
            } catch (_) { /* ignore */ }
            zrodloSelect.innerHTML = '<option value="">-- wybierz źródło --</option>';
            allSprzet.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.nazwa;
                zrodloSelect.appendChild(opt);
            });
            celSelect.innerHTML = '<option value="">-- wybierz najpierw źródło --</option>';
            document.getElementById('dmuchanie-czyszczenie-error').classList.add('d-none');
            modals.dmuchanieCzyszczenie.show();
        });
    }

    const dmuchanieCzyszczenieZrodlo = document.getElementById('dmuchanie-czyszczenie-zrodlo');
    if (dmuchanieCzyszczenieZrodlo) {
        dmuchanieCzyszczenieZrodlo.addEventListener('change', async () => {
            const idZrodla = dmuchanieCzyszczenieZrodlo.value;
            const celSelect = document.getElementById('dmuchanie-czyszczenie-cel');
            if (!idZrodla) {
                celSelect.innerHTML = '<option value="">-- wybierz najpierw źródło --</option>';
                return;
            }
            celSelect.innerHTML = '<option value="">Ładowanie...</option>';
            celSelect.disabled = true;
            try {
                const res = await fetch(`/api/operations/dmuchanie-czyszczenie-destinations?id_sprzetu_zrodlowego=${idZrodla}`);
                const data = res.ok ? await res.json() : { destinations: [] };
                celSelect.innerHTML = '<option value="">-- wybierz cel --</option>';
                (data.destinations || []).forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d.id;
                    opt.textContent = (d.nazwa_unikalna || d.id) + (d.material_types_text ? ` (${d.material_types_text})` : '');
                    celSelect.appendChild(opt);
                });
            } catch {
                celSelect.innerHTML = '<option value="">Błąd ładowania</option>';
            }
            celSelect.disabled = false;
        });
    }

    const openDmuchanieRurociaguBtn = document.getElementById('open-dmuchanie-rurociagu-btn');
    if (openDmuchanieRurociaguBtn) {
        openDmuchanieRurociaguBtn.addEventListener('click', () => {
            fillSprzetSelects('dmuchanie-rurociagu-zrodlo', 'dmuchanie-rurociagu-cel');
            document.getElementById('dmuchanie-rurociagu-error').classList.add('d-none');
            modals.dmuchanieRurociagu.show();
        });
    }

    forms.dmuchanieCzyszczenie.addEventListener('submit', async (e) => {
        e.preventDefault();
        const idZrodla = document.getElementById('dmuchanie-czyszczenie-zrodlo').value;
        const idCelu = document.getElementById('dmuchanie-czyszczenie-cel').value;
        const errorDiv = document.getElementById('dmuchanie-czyszczenie-error');
        if (!idZrodla || !idCelu) {
            errorDiv.textContent = 'Wybierz źródło i cel.';
            errorDiv.classList.remove('d-none');
            return;
        }
        errorDiv.classList.add('d-none');
        try {
            const response = await fetch('/api/operations/start-dmuchanie-czyszczenie', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id_sprzetu_zrodlowego: parseInt(idZrodla, 10),
                    id_sprzetu_docelowego: parseInt(idCelu, 10),
                    operator: 'GUI'
                })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || result.error);
            showToast(result.message || 'Operacja rozpoczęta.', 'success');
            modals.dmuchanieCzyszczenie.hide();
            initialLoad();
        } catch (error) {
            errorDiv.textContent = error.message;
            errorDiv.classList.remove('d-none');
        }
    });

    forms.dmuchanieRurociagu.addEventListener('submit', async (e) => {
        e.preventDefault();
        const idZrodla = document.getElementById('dmuchanie-rurociagu-zrodlo').value;
        const idCelu = document.getElementById('dmuchanie-rurociagu-cel').value;
        const errorDiv = document.getElementById('dmuchanie-rurociagu-error');
        if (!idZrodla || !idCelu) {
            errorDiv.textContent = 'Wybierz źródło i cel.';
            errorDiv.classList.remove('d-none');
            return;
        }
        errorDiv.classList.add('d-none');
        try {
            const response = await fetch('/api/operations/start-dmuchanie-rurociagu', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id_sprzetu_zrodlowego: parseInt(idZrodla, 10),
                    id_sprzetu_docelowego: parseInt(idCelu, 10),
                    operator: 'GUI'
                })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || result.error);
            showToast(result.message || 'Operacja rozpoczęta.', 'success');
            modals.dmuchanieRurociagu.hide();
            initialLoad();
        } catch (error) {
            errorDiv.textContent = error.message;
            errorDiv.classList.remove('d-none');
        }
    });

    if (forms.startFiltration) {
        forms.startFiltration.addEventListener('submit', async (e) => {
            e.preventDefault();
            const mixId = document.getElementById('start-filtration-mix-id').value;
            const reaktorNazwa = document.getElementById('start-filtration-reaktor-nazwa').value.trim();
            const selectedRadio = document.querySelector('input[name="start-filtration-destination"]:checked');
            const errorDiv = document.getElementById('start-filtration-error');
            if (!selectedRadio) {
                errorDiv.textContent = 'Wybierz reaktor docelowy.';
                errorDiv.classList.remove('d-none');
                return;
            }
            errorDiv.classList.add('d-none');
            const celNazwa = selectedRadio.getAttribute('data-nazwa');
            const payload = {
                start: `${reaktorNazwa}_OUT`,
                cel: `${celNazwa}_IN`
            };
            try {
                const response = await fetch(`/api/workflow/mix/${mixId}/start-filtration`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || result.message || 'Błąd serwera');
                showToast('Filtracja została uruchomiona.', 'success');
                modals.startFiltration.hide();
                initialLoad();
            } catch (error) {
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('d-none');
            }
        });
    }

    if (forms.filtracjaNaPlacku) {
        forms.filtracjaNaPlacku.addEventListener('submit', async (e) => {
            e.preventDefault();
            const idZrodla = document.getElementById('filtracja-na-placku-id-zrodla').value;
            const selected = document.querySelector('input[name="fnp-destination"]:checked');
            const errorDiv = document.getElementById('filtracja-na-placku-error');
            if (!idZrodla || !selected) {
                errorDiv.textContent = 'Wybierz reaktor docelowy.';
                errorDiv.classList.remove('d-none');
                return;
            }
            errorDiv.classList.add('d-none');
            try {
                const response = await fetch('/api/operations/start-filtracja-na-placku', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id_sprzetu_zrodlowego: parseInt(idZrodla, 10),
                        id_sprzetu_docelowego: parseInt(selected.value, 10),
                        operator: 'GUI'
                    })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || result.error);
                showToast(result.message || 'Filtracja na placku rozpoczęta.', 'success');
                modals.filtracjaNaPlacku.hide();
                initialLoad();
            } catch (error) {
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('d-none');
            }
        });
    }

    if (forms.dobielanie) {
        forms.dobielanie.addEventListener('submit', async (e) => {
            e.preventDefault();
            const mixId = document.getElementById('dobielanie-mix-id').value;
            const bags = parseInt(document.getElementById('dobielanie-bags').value, 10);
            const weight = parseFloat(document.getElementById('dobielanie-weight').value);
            const errorDiv = document.getElementById('dobielanie-error');
            if (!mixId || bags < 1 || !weight || weight <= 0) {
                errorDiv.textContent = 'Wprowadź poprawną ilość worków i wagę.';
                errorDiv.classList.remove('d-none');
                return;
            }
            errorDiv.classList.add('d-none');
            try {
                const response = await fetch(`/api/workflow/mix/${mixId}/add-bleach`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        bags_count: bags,
                        bag_weight: weight,
                        operator: 'GUI'
                    })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || result.message);
                showToast(result.message || 'Dobielanie zarejestrowane.', 'success');
                modals.dobielanie.hide();
                initialLoad();
            } catch (error) {
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('d-none');
            }
        });
    }

    initialLoad();
});
