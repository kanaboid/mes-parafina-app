// app/static/js/cykle_monitor.js
// JavaScript dla monitoringu cykli filtracyjnych

document.addEventListener('DOMContentLoaded', () => {
    // Główne kontenery
    const filtryContainer = document.getElementById('filtry-container');
    const partieTableBody = document.getElementById('partie-tbody');
    
    let timery = {};
    
    // === FUNKCJE POMOCNICZE ===
    
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
    
    function formatCzas(minuty) {
        if (!minuty) return '---';
        if (minuty < 0) return `Przekroczono o ${Math.abs(minuty)} min`;
        const h = Math.floor(minuty / 60);
        const m = minuty % 60;
        return h > 0 ? `${h}h ${m}min` : `${m}min`;
    }
    
    function getTimerClass(pozostaleMinuty) {
        if (!pozostaleMinuty) return 'normalny';
        if (pozostaleMinuty < 0) return 'przekroczony';
        if (pozostaleMinuty < 5) return 'wkrotce';
        return 'normalny';
    }
    
    function getEtapOpis(etap) {
        const opisy = {
            'W magazynie brudnym': 'W magazynie brudnym',
            'Surowy w reaktorze': 'Surowiec w reaktorze',
            'Budowanie placka': 'Budowanie placka',
            'Przelewanie': 'Przelew do reaktora',
            'Filtrowanie': 'Filtracja w koło',
            'Oczekiwanie na ocenę': 'Oczekiwanie na ocenę',
            'Do ponownej filtracji': 'Do ponownej filtracji',
            'Dobielanie': 'Dobielanie',
            'Gotowy do wysłania': 'Gotowy',
            'W magazynie czystym': 'W magazynie czystym',
            // Stare wartości dla kompatybilności
            'surowy': 'Surowiec w reaktorze',
            'placek': 'Budowanie placka',
            'przelew': 'Przelew do reaktora',
            'w_kole': 'Filtracja w koło',
            'ocena_probki': 'Oczekiwanie na ocenę',
            'dmuchanie': 'Dmuchanie filtra',
            'gotowy': 'Gotowy',
            'wydmuch': 'Wydmuch'
        };
        return opisy[etap] || etap;
    }
    
    function getEtapBadgeClass(etap) {
        const klasy = {
            'W magazynie brudnym': 'bg-secondary',
            'Surowy w reaktorze': 'bg-info',
            'Budowanie placka': 'bg-warning',
            'Przelewanie': 'bg-primary',
            'Filtrowanie': 'bg-success',
            'Oczekiwanie na ocenę': 'bg-warning',
            'Do ponownej filtracji': 'bg-danger',
            'Dobielanie': 'bg-info',
            'Gotowy do wysłania': 'bg-success',
            'W magazynie czystym': 'bg-primary',
            // Stare wartości dla kompatybilności
            'surowy': 'bg-secondary',
            'placek': 'bg-warning',
            'przelew': 'bg-info',
            'w_kole': 'bg-success',
            'ocena_probki': 'bg-warning',
            'dmuchanie': 'bg-danger',
            'gotowy': 'bg-primary',
            'wydmuch': 'bg-dark'
        };
        return klasy[etap] || 'bg-secondary';
    }
    
    // === FUNKCJE ŁADOWANIA DANYCH ===
    
    async function zaladujFiltry() {
        try {
            const response = await fetch('/api/filtry/szczegolowy-status');
            const filtry = await response.json();
            
            filtryContainer.innerHTML = '';
            
            filtry.forEach(filtr => {
                const filtrDiv = utworzKarteFitra(filtr);
                filtryContainer.appendChild(filtrDiv);
            });
            
        } catch (error) {
            console.error('Błąd ładowania filtrów:', error);
            showToast('Błąd ładowania statusu filtrów', 'error');
        }
    }
    
    async function zaladujPartie() {
        try {
            const response = await fetch('/api/partie/aktywne');
            const partie = await response.json();
            
            partieTableBody.innerHTML = '';
            
            if (partie.length === 0) {
                partieTableBody.innerHTML = '<tr><td colspan="8" class="text-center">Brak aktywnych partii</td></tr>';
                return;
            }
            
            partie.forEach(partia => {
                const row = utworzWierszPartii(partia);
                partieTableBody.appendChild(row);
                
                // Uruchom timer jeśli potrzebny
                if (partia.czas_trwania_operacji_minuty !== null && partia.id_operacji) {
                    uruchomTimer(partia.id, partia.czas_trwania_operacji_minuty);
                }
            });
            
        } catch (error) {
            console.error('Błąd ładowania partii:', error);
            showToast('Błąd ładowania aktywnych partii', 'error');
        }
    }
    
    // === TWORZENIE ELEMENTÓW UI ===
    
    function utworzKarteFitra(filtr) {
        const col = document.createElement('div');
        col.className = 'col-md-6 mb-4';
        
        let statusClass = 'filtr-wolny';
        let statusText = 'Wolny';
        let aktywnaOperacjaHTML = '';
        let kolejkaHTML = '';
        
        if (filtr.aktywna_operacja) {
            statusClass = 'filtr-zajety';
            statusText = 'Zajęty';
            const op = filtr.aktywna_operacja;
            
            aktywnaOperacjaHTML = `
                <div class="mt-3">
                    <h6><i class="bi bi-gear-fill"></i> Aktywna Operacja:</h6>
                    <div class="row">
                        <div class="col-6">
                            <strong>Partia:</strong> ${op.unikalny_kod || 'N/A'}<br>
                            <strong>Etap:</strong> <span class="badge ${getEtapBadgeClass(op.aktualny_etap_procesu)} status-badge">
                                ${getEtapOpis(op.aktualny_etap_procesu)}
                            </span><br>
                            <strong>Cykl:</strong> ${op.numer_cyklu_aktualnego || 0}
                        </div>
                        <div class="col-6">
                            <strong>Trasa:</strong> ${op.reaktor_startowy || '?'} → ${op.reaktor_docelowy || '?'}<br>
                            <strong>Pozostały czas:</strong> 
                            <span class="timer ${getTimerClass(op.pozostale_minuty)}" id="timer-${op.id_partii_surowca}">
                                ${formatCzas(op.pozostale_minuty)}
                            </span>
                        </div>
                    </div>
                    <div class="mt-2">
                        <button class="btn btn-sm btn-warning me-2" onclick="zakonczCykl(${op.id_partii_surowca})">
                            <i class="bi bi-stop-fill"></i> Zakończ Cykl
                        </button>
                        <button class="btn btn-sm btn-info" onclick="pokazSzczegoly(${op.id_partii_surowca})">
                            <i class="bi bi-info-circle"></i> Szczegóły
                        </button>
                    </div>
                </div>
            `;
            
            // Uruchom timer
            if (op.pozostale_minuty !== null) {
                uruchomTimer(op.id_partii_surowca, op.pozostale_minuty);
            }
        } else {
            // Pokaż kolejkę oczekujących
            if (filtr.kolejka_oczekujacych && filtr.kolejka_oczekujacych.length > 0) {
                kolejkaHTML = `
                    <div class="mt-3">
                        <h6><i class="bi bi-clock"></i> Kolejka Oczekujących:</h6>
                        ${filtr.kolejka_oczekujacych.map(partia => `
                            <div class="kolejka-item">
                                <strong>${partia.unikalny_kod}</strong> 
                                <span class="badge ${getEtapBadgeClass(partia.aktualny_etap_procesu)} status-badge">
                                    ${getEtapOpis(partia.aktualny_etap_procesu)}
                                </span>
                                <br>
                                <small>Na reaktorze: ${partia.nazwa_reaktora}</small>
                                <button class="btn btn-sm btn-success float-end" onclick="rozpocznijCyklDlaPartii(${partia.id}, '${filtr.nazwa_filtra}')">
                                    <i class="bi bi-play"></i> Start
                                </button>
                            </div>
                        `).join('')}
                    </div>
                `;
            }
        }
        
        col.innerHTML = `
            <div class="filtr-status ${statusClass}">
                <div class="d-flex justify-content-between align-items-center">
                    <h4><i class="bi bi-funnel-fill"></i> ${filtr.nazwa_filtra}</h4>
                    <span class="badge bg-secondary">${statusText}</span>
                </div>
                <p class="mb-2"><strong>Stan sprzętu:</strong> ${filtr.stan_sprzetu || 'Nieznany'}</p>
                
                ${aktywnaOperacjaHTML}
                ${kolejkaHTML}
            </div>
        `;
        
        return col;
    }
    
    function utworzWierszPartii(partia) {
        const row = document.createElement('tr');
        row.className = `etap-card ${partia.status_partii.replace(/\s+/g, '_')}`;
        
        const czasClass = getTimerClass(partia.czas_trwania_operacji_minuty);
        const timerId = `timer-partia-${partia.id}`;
        
        row.innerHTML = `
            <td><strong>${partia.unikalny_kod}</strong></td>
            <td>${partia.nazwa_partii || 'N/A'}</td>
            <td>${partia.typ_surowca || 'N/A'}</td>
            <td>
                <span class="badge ${getEtapBadgeClass(partia.status_partii)} status-badge">
                    ${getEtapOpis(partia.status_partii)}
                </span>
            </td>
            <td>${partia.ilosc_cykli_filtracyjnych || 0}</td>
            <td>${partia.nazwa_sprzetu || 'N/A'}</td>
            <td>
                <span class="timer ${czasClass}" id="${timerId}">
                    ${formatCzas(partia.czas_trwania_operacji_minuty)}
                </span>
            </td>
            <td>
                <button class="btn btn-sm btn-primary me-1" onclick="rozpocznijCyklDlaPartii(${partia.id})">
                    <i class="bi bi-play"></i>
                </button>
                <button class="btn btn-sm btn-info me-1" onclick="pokazHistoriePartii(${partia.id})">
                    <i class="bi bi-clock-history"></i>
                </button>
                ${partia.status_partii !== 'Gotowy do wysłania' ? `
                    <button class="btn btn-sm btn-warning" onclick="zakonczCykl(${partia.id})">
                        <i class="bi bi-stop"></i>
                    </button>
                ` : ''}
            </td>
        `;
        
        return row;
    }
    
    // === TIMERY ===
    
    function uruchomTimer(id, pozostaleMinuty) {
        // Usuń istniejący timer jeśli istnieje
        if (timery[id]) {
            clearInterval(timery[id]);
        }
        
        let minuty = pozostaleMinuty;
        
        timery[id] = setInterval(() => {
            minuty--;
            
            const timerElements = document.querySelectorAll(`#timer-${id}, #timer-partia-${id}`);
            timerElements.forEach(element => {
                if (element) {
                    element.textContent = formatCzas(minuty);
                    element.className = `timer ${getTimerClass(minuty)}`;
                }
            });
            
            // Zatrzymaj timer gdy dojdzie do -60 minut
            if (minuty < -60) {
                clearInterval(timery[id]);
                delete timery[id];
            }
        }, 60000); // Co minutę
    }
    
    // === AKCJE UŻYTKOWNIKA ===
    
    window.rozpocznijCyklDlaPartii = function(partiaId, preferowanyFiltr = null) {
        document.getElementById('partia-id').value = partiaId;
        if (preferowanyFiltr) {
            document.getElementById('filtr-select').value = preferowanyFiltr;
        }
        
        const modal = new bootstrap.Modal(document.getElementById('nowyCoklModal'));
        modal.show();
    };
    
    window.rozpocznijCykl = async function() {
        const formData = {
            id_partii: parseInt(document.getElementById('partia-id').value),
            typ_cyklu: document.getElementById('typ-cyklu').value,
            id_filtra: document.getElementById('filtr-select').value,
            reaktor_startowy: document.getElementById('reaktor-startowy').value,
            reaktor_docelowy: document.getElementById('reaktor-docelowy').value || null
        };
        
        try {
            const response = await fetch('/api/cykle/rozpocznij', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
            
            const result = await response.json();
            
            if (response.ok) {
                showToast(result.message, 'success');
                bootstrap.Modal.getInstance(document.getElementById('nowyCoklModal')).hide();
                document.getElementById('nowy-cykl-form').reset();
                odswiezWszystko();
            } else {
                showToast(result.error, 'error');
            }
        } catch (error) {
            showToast('Błąd sieciowy: ' + error.message, 'error');
        }
    };
    
    window.zakonczCykl = async function(partiaId) {
        if (!confirm('Czy na pewno chcesz zakończyć aktualny cykl?')) return;
        
        try {
            const response = await fetch('/api/cykle/zakoncz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id_partii: partiaId })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                showToast(result.message, 'success');
                odswiezWszystko();
            } else {
                showToast(result.error, 'error');
            }
        } catch (error) {
            showToast('Błąd sieciowy: ' + error.message, 'error');
        }
    };
    
    window.pokazHistoriePartii = async function(partiaId) {
        try {
            const response = await fetch(`/api/cykle-filtracyjne/${partiaId}`);
            const historia = await response.json();
            
            let historiaHTML = '<h5>Historia Cykli Filtracyjnych</h5><div class="table-responsive"><table class="table table-sm"><thead><tr><th>Cykl</th><th>Typ</th><th>Filtr</th><th>Trasa</th><th>Czas</th><th>Wynik</th></tr></thead><tbody>';
            
            historia.forEach(cykl => {
                historiaHTML += `
                    <tr>
                        <td>${cykl.numer_cyklu}</td>
                        <td>${cykl.typ_cyklu}</td>
                        <td>${cykl.id_filtra}</td>
                        <td>${cykl.reaktor_startowy} → ${cykl.reaktor_docelowy || '?'}</td>
                        <td>${cykl.rzeczywisty_czas_minut || '?'} min</td>
                        <td><span class="badge ${cykl.wynik_oceny === 'pozytywna' ? 'bg-success' : cykl.wynik_oceny === 'negatywna' ? 'bg-danger' : 'bg-warning'}">${cykl.wynik_oceny}</span></td>
                    </tr>
                `;
            });
            
            historiaHTML += '</tbody></table></div>';
            
            // Można pokazać w modalu lub nowym oknie
            alert(historiaHTML); // Tymczasowo, można zrobić ładniejszy modal
            
        } catch (error) {
            showToast('Błąd ładowania historii: ' + error.message, 'error');
        }
    };
    
    window.odswiezWszystko = function() {
        zaladujFiltry();
        zaladujPartie();
        showToast('Dane odświeżone', 'info');
    };
    
    window.pokazSzczegoly = function(partiaId) {
        // TODO: Implementacja szczegółów partii
        showToast('Funkcja w przygotowaniu', 'info');
    };
    
    window.pokazHistorie = function() {
        // TODO: Implementacja globalnej historii
        showToast('Historia globalna - funkcja w przygotowaniu', 'info');
    };
    
    // === INICJALIZACJA ===
    
    // Pierwsze załadowanie
    odswiezWszystko();
    
    // Automatyczne odświeżanie co 30 sekund
    setInterval(odswiezWszystko, 30000);
});
