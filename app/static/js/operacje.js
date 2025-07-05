// Operacje - JavaScript dla formularza tankowania brudnego surowca

document.addEventListener('DOMContentLoaded', function() {
    // Inicjalizacja
    inicjalizujFormularz();
    inicjalizujTransferReaktorow();
    zaladujStatusReaktorow();
    
    // Odśwież status reaktorów co 30 sekund
    setInterval(zaladujStatusReaktorow, 30000);
});

/**
 * Inicjalizuje formularz - ładuje dane do select-ów
 */
async function inicjalizujFormularz() {
    try {
        // Załaduj równolegle wszystkie potrzebne dane
        const [reaktory, beczki, typySupowca] = await Promise.all([
            fetch('/api/sprzet/reaktory-puste').then(r => r.json()),
            fetch('/api/sprzet/beczki-brudne').then(r => r.json()),
            fetch('/api/typy-surowca').then(r => r.json())
        ]);

        // Wypełnij listy select
        wypelnijSelect('reaktorSelect', reaktory, 'id', 'nazwa_unikalna');
        wypelnijSelect('beczkaSelect', beczki, 'id', 'nazwa_unikalna');
        wypelnijSelect('typSurowcaSelect', typySupowca, 'nazwa', 'nazwa', 'opis');
        
        // Przypisz obsługę formularza
        document.getElementById('tankowanieBrudnegoForm').addEventListener('submit', obsluzWyslaniePormu);
        
    } catch (error) {
        console.error('Błąd inicjalizacji formularza:', error);
        pokazBlad('Błąd ładowania danych formularza: ' + error.message);
    }
}

/**
 * Wypełnia select element opcjami
 */
function wypelnijSelect(selectId, dane, valueField, textField, opisField = null) {
    const select = document.getElementById(selectId);
    
    // Wyczyść istniejące opcje (oprócz pierwszej - placeholder)
    while (select.children.length > 1) {
        select.removeChild(select.lastChild);
    }
    
    // Dodaj nowe opcje
    dane.forEach(item => {
        const option = document.createElement('option');
        option.value = item[valueField];
        option.textContent = item[textField];
        
        if (opisField && item[opisField]) {
            option.textContent += ` (${item[opisField]})`;
        }
        
        select.appendChild(option);
    });
}

/**
 * Ładuje i wyświetla aktualny status reaktorów
 */
async function zaladujStatusReaktorow() {
    try {
        const response = await fetch('/api/sprzet?typ=reaktor');
        const reaktory = await response.json();
        
        const statusDiv = document.getElementById('reaktoryStatus');
        
        if (reaktory.length === 0) {
            statusDiv.innerHTML = '<div class="text-muted small">Brak reaktorów</div>';
            return;
        }
        
        let html = '';
        reaktory.forEach(reaktor => {
            const statusClass = reaktor.stan_sprzetu === 'Pusty' ? 'text-success' : 'text-warning';
            const icon = reaktor.stan_sprzetu === 'Pusty' ? 'bi-circle' : 'bi-circle-fill';
            
            html += `
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="small">${reaktor.nazwa_unikalna}</span>
                    <span class="small ${statusClass}">
                        <i class="bi ${icon}"></i> ${reaktor.stan_sprzetu}
                    </span>
                </div>
            `;
        });
        
        statusDiv.innerHTML = html;
        
    } catch (error) {
        console.error('Błąd ładowania statusu reaktorów:', error);
        document.getElementById('reaktoryStatus').innerHTML = 
            '<div class="text-danger small">Błąd ładowania</div>';
    }
}

/**
 * Obsługuje wysłanie formularza tankowania
 */
async function obsluzWyslaniePormu(event) {
    event.preventDefault();
    
    const form = event.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    
    // Wyłącz przycisk i pokaż loader
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Tankowanie...';
    
    try {
        // Zbierz dane z formularza
        const formData = new FormData(form);
        const dane = {
            id_reaktora: parseInt(formData.get('id_reaktora')),
            id_beczki: parseInt(formData.get('id_beczki')),
            typ_surowca: formData.get('typ_surowca'),
            waga_kg: parseFloat(formData.get('waga_kg')),
            temperatura_surowca: parseFloat(formData.get('temperatura_surowca'))
        };
        
        // Walidacja po stronie klienta
        if (!walidujDane(dane)) {
            return;
        }
        
        // Wyślij dane do API
        const response = await fetch('/api/operacje/tankowanie-brudnego', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(dane)
        });
        
        const wynik = await response.json();
        
        if (response.ok) {
            // Sukces - pokaż komunikat operatorski
            pokazKomunikatOperatorski(wynik);
            
            // Zapisz informacje o ostatniej operacji
            zapiszOstatniaOperacje(wynik, dane);
            
            // Wyczyść formularz
            form.reset();
            
            // Odśwież dane formularza i status reaktorów
            await inicjalizujFormularz();
            await zaladujStatusReaktorow();
            
        } else {
            // Błąd - pokaż komunikat błędu
            pokazBlad(wynik.message || 'Wystąpił nieznany błąd');
        }
        
    } catch (error) {
        console.error('Błąd podczas tankowania:', error);
        pokazBlad('Błąd komunikacji z serwerem: ' + error.message);
    } finally {
        // Przywróć przycisk
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
}

/**
 * Waliduje dane formularza po stronie klienta
 */
function walidujDane(dane) {
    // Sprawdź czy wszystkie pola są wypełnione
    if (!dane.id_reaktora || !dane.id_beczki || !dane.typ_surowca || 
        !dane.waga_kg || dane.temperatura_surowca === null || dane.temperatura_surowca === undefined) {
        pokazBlad('Wszystkie pola muszą być wypełnione');
        return false;
    }
    
    // Sprawdź wagę
    if (dane.waga_kg <= 0 || dane.waga_kg > 9000) {
        pokazBlad('Waga musi być w zakresie 1-9000 kg');
        return false;
    }
    
    // Sprawdź temperaturę (rozumny zakres)
    if (dane.temperatura_surowca < -50 || dane.temperatura_surowca > 200) {
        pokazBlad('Temperatura musi być w zakresie -50°C do 200°C');
        return false;
    }
    
    return true;
}

/**
 * Pokazuje komunikat operatorski w modal-u
 */
function pokazKomunikatOperatorski(wynik) {
    const modalElement = document.getElementById('komunikatModal');
    const komunikatTresc = document.getElementById('komunikatTresc');
    
    // Wypełnij treść komunikatu
    komunikatTresc.innerHTML = `
        <div class="mb-3">
            <h5 class="text-success">
                <i class="bi bi-check-circle"></i> ${wynik.message}
            </h5>
        </div>
        
        <div class="row text-start">
            <div class="col-sm-6">
                <strong>Kod partii:</strong><br>
                <code>${wynik.partia_kod}</code>
            </div>
            <div class="col-sm-6">
                <strong>Reaktor:</strong><br>
                ${wynik.reaktor}
            </div>
        </div>
        
        <div class="row text-start mt-2">
            <div class="col-sm-6">
                <strong>Temperatura początkowa:</strong><br>
                ${wynik.temperatura_poczatkowa}°C
            </div>
        </div>
        
        <div class="alert alert-warning mt-3">
            <i class="bi bi-exclamation-triangle"></i>
            <strong>${wynik.komunikat_operatorski}</strong>
        </div>
    `;
    
    // Pokaż modal
    const modal = new bootstrap.Modal(modalElement);
    modal.show();
}

/**
 * Zapisuje informacje o ostatniej operacji
 */
function zapiszOstatniaOperacje(wynik, dane) {
    const lastOpDiv = document.getElementById('lastOperation');
    const lastOpDetails = document.getElementById('lastOperationDetails');
    
    const teraz = new Date().toLocaleString('pl-PL');
    
    lastOpDetails.innerHTML = `
        <div><strong>Czas:</strong> ${teraz}</div>
        <div><strong>Partia:</strong> ${wynik.partia_kod}</div>
        <div><strong>Reaktor:</strong> ${wynik.reaktor}</div>
        <div><strong>Waga:</strong> ${dane.waga_kg} kg</div>
    `;
    
    lastOpDiv.style.display = 'block';
}

/**
 * Pokazuje komunikat błędu
 */
function pokazBlad(wiadomosc) {
    // Utwórz toast dla błędu
    const toastHtml = `
        <div class="toast align-items-center text-white bg-danger border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi bi-exclamation-triangle"></i> ${wiadomosc}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    // Dodaj toast do kontenera (lub utwórz kontener jeśli nie istnieje)
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    // Pokaż toast
    const toastElement = toastContainer.lastElementChild;
    const toast = new bootstrap.Toast(toastElement, { delay: 5000 });
    toast.show();
    
    // Usuń element po zamknięciu
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}

/**
 * Inicjalizuje formularz transferu reaktorów
 */
async function inicjalizujTransferReaktorow() {
    try {
        // Załaduj dane do formularza transferu
        await zaladujDaneTransferu();
        
        // Przypisz obsługę formularza transferu
        document.getElementById('transferReaktorowForm').addEventListener('submit', obsluzTransfer);
        
        // Obsługa checkboxa "przez filtr"
        document.getElementById('przezFiltrCheck').addEventListener('change', function(e) {
            const filtrSelect = document.getElementById('filtrSelect');
            filtrSelect.disabled = !e.target.checked;
            if (!e.target.checked) {
                filtrSelect.value = '';
            }
        });
        
        // Obsługa przycisku podglądu trasy
        document.getElementById('podgladTrasyBtn').addEventListener('click', pokazPodgladTrasy);
        
    } catch (error) {
        console.error('Błąd inicjalizacji transferu reaktorów:', error);
        pokazBlad('Błąd ładowania danych transferu: ' + error.message);
    }
}

/**
 * Ładuje dane potrzebne do formularza transferu
 */
async function zaladujDaneTransferu() {
    try {
        // Załaduj równolegle wszystkie potrzebne dane
        const [reaktoryZSurowcem, reaktoryPuste, filtry] = await Promise.all([
            fetch('/api/sprzet/reaktory-z-surowcem').then(r => r.json()),
            fetch('/api/sprzet/reaktory-puste').then(r => r.json()),
            fetch('/api/sprzet/filtry').then(r => r.json())
        ]);

        // Wypełnij listy select
        wypelnijSelect('reaktorZrodlowySelect', reaktoryZSurowcem, 'id', 'nazwa_unikalna');
        wypelnijSelect('reaktorDocelowySelect', reaktoryPuste, 'id', 'nazwa_unikalna');
        wypelnijSelect('filtrSelect', filtry, 'id', 'nazwa_unikalna');
        
    } catch (error) {
        console.error('Błąd ładowania danych transferu:', error);
        throw error;
    }
}

/**
 * Pokazuje podgląd trasy transferu
 */
async function pokazPodgladTrasy() {
    const reaktorZrodlowy = document.getElementById('reaktorZrodlowySelect').value;
    const reaktorDocelowy = document.getElementById('reaktorDocelowySelect').value;
    const przezFiltr = document.getElementById('przezFiltrCheck').checked;
    const filtr = document.getElementById('filtrSelect').value;
    
    // Walidacja podstawowa
    if (!reaktorZrodlowy || !reaktorDocelowy) {
        pokazBlad('Wybierz reaktor źródłowy i docelowy');
        return;
    }
    
    if (przezFiltr && !filtr) {
        pokazBlad('Wybierz filtr gdy transfer ma być przez filtr');
        return;
    }
    
    try {
        // Przygotuj dane do żądania podglądu
        const dane = {
            id_reaktora_zrodlowego: parseInt(reaktorZrodlowy),
            id_reaktora_docelowego: parseInt(reaktorDocelowy),
            przez_filtr: przezFiltr,
            id_filtra: filtr ? parseInt(filtr) : null,
            podglad: true  // Flaga że to tylko podgląd
        };
        
        // Wyślij żądanie podglądu
        const response = await fetch('/api/operacje/transfer-reaktorow', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(dane)
        });
        
        const wynik = await response.json();
        
        if (response.ok && wynik.trasa) {
            // Pokaż podgląd trasy
            const podgladDiv = document.getElementById('podgladTrasy');
            const podgladTresc = document.getElementById('podgladTrasyTresc');
            
            let html = `<strong>Trasa transferu:</strong><br>`;
            html += `${wynik.trasa.join(' → ')}<br><br>`;
            
            if (wynik.zawory && wynik.zawory.length > 0) {
                html += `<strong>Zawory do otwarcia:</strong><br>`;
                wynik.zawory.forEach(zawor => {
                    html += `<span class="badge bg-primary me-1">${zawor}</span>`;
                });
                html += '<br><br>';
            }
            
            if (wynik.segmenty_do_zablokowania && wynik.segmenty_do_zablokowania.length > 0) {
                html += `<strong>Segmenty do zablokowania:</strong><br>`;
                wynik.segmenty_do_zablokowania.forEach(segment => {
                    html += `<span class="badge bg-warning me-1">${segment}</span>`;
                });
            }
            
            podgladTresc.innerHTML = html;
            podgladDiv.style.display = 'block';
            
        } else {
            pokazBlad(wynik.message || 'Nie można wygenerować podglądu trasy');
        }
        
    } catch (error) {
        console.error('Błąd podglądu trasy:', error);
        pokazBlad('Błąd podczas generowania podglądu trasy: ' + error.message);
    }
}

/**
 * Obsługuje wysłanie formularza transferu
 */
async function obsluzTransfer(event) {
    event.preventDefault();
    
    const form = event.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    
    // Wyłącz przycisk i pokaż loader
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Transfer w toku...';
    
    try {
        // Zbierz dane z formularza
        const formData = new FormData(form);
        const dane = {
            id_reaktora_zrodlowego: parseInt(formData.get('id_reaktora_zrodlowego')),
            id_reaktora_docelowego: parseInt(formData.get('id_reaktora_docelowego')),
            przez_filtr: formData.has('przez_filtr'),
            id_filtra: formData.get('id_filtra') ? parseInt(formData.get('id_filtra')) : null
        };
        
        // Walidacja po stronie klienta
        if (!walidujDaneTransferu(dane)) {
            return;
        }
        
        // Wyślij dane do API
        const response = await fetch('/api/operacje/transfer-reaktorow', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(dane)
        });
        
        const wynik = await response.json();
        
        if (response.ok) {
            // Sukces - pokaż komunikat operatorski
            pokazKomunikatTransferu(wynik);
            
            // Zapisz informacje o ostatnim transferze
            zapiszOstatniTransfer(wynik, dane);
            
            // Wyczyść formularz
            form.reset();
            document.getElementById('filtrSelect').disabled = true;
            document.getElementById('podgladTrasy').style.display = 'none';
            
            // Odśwież dane formularzy i status reaktorów
            await zaladujDaneTransferu();
            await inicjalizujFormularz();
            await zaladujStatusReaktorow();
            
        } else {
            // Błąd - pokaż komunikat błędu
            pokazBlad(wynik.message || 'Wystąpił nieznany błąd podczas transferu');
        }
        
    } catch (error) {
        console.error('Błąd podczas transferu:', error);
        pokazBlad('Błąd komunikacji z serwerem: ' + error.message);
    } finally {
        // Przywróć przycisk
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
}

/**
 * Waliduje dane transferu po stronie klienta
 */
function walidujDaneTransferu(dane) {
    // Sprawdź czy reaktory są wybrane
    if (!dane.id_reaktora_zrodlowego || !dane.id_reaktora_docelowego) {
        pokazBlad('Musisz wybrać reaktor źródłowy i docelowy');
        return false;
    }
    
    // Sprawdź czy to nie ten sam reaktor
    if (dane.id_reaktora_zrodlowego === dane.id_reaktora_docelowego) {
        pokazBlad('Reaktor źródłowy i docelowy nie mogą być tym samym reaktorem');
        return false;
    }
    
    // Sprawdź filtr jeśli transfer przez filtr
    if (dane.przez_filtr && !dane.id_filtra) {
        pokazBlad('Wybierz filtr gdy transfer ma być przez filtr');
        return false;
    }
    
    return true;
}

/**
 * Pokazuje komunikat operatorski transferu w modal-u
 */
function pokazKomunikatTransferu(wynik) {
    const modalElement = document.getElementById('komunikatModal');
    const komunikatTresc = document.getElementById('komunikatTresc');
    
    // Wypełnij treść komunikatu
    let html = `
        <div class="mb-3">
            <h5 class="text-success">
                <i class="bi bi-check-circle"></i> ${wynik.message}
            </h5>
        </div>
        
        <div class="row text-start">
            <div class="col-sm-6">
                <strong>Reaktor źródłowy:</strong><br>
                ${wynik.reaktor_zrodlowy}
            </div>
            <div class="col-sm-6">
                <strong>Reaktor docelowy:</strong><br>
                ${wynik.reaktor_docelowy}
            </div>
        </div>
    `;
    
    if (wynik.przez_filtr && wynik.filtr) {
        html += `
            <div class="row text-start mt-2">
                <div class="col-12">
                    <strong>Transfer przez filtr:</strong><br>
                    ${wynik.filtr}
                </div>
            </div>
        `;
    }
    
    if (wynik.trasa && wynik.trasa.length > 0) {
        html += `
            <div class="row text-start mt-2">
                <div class="col-12">
                    <strong>Trasa:</strong><br>
                    <small>${wynik.trasa.join(' → ')}</small>
                </div>
            </div>
        `;
    }
    
    if (wynik.zawory && wynik.zawory.length > 0) {
        html += `
            <div class="row text-start mt-2">
                <div class="col-12">
                    <strong>Otwarte zawory:</strong><br>
                    ${wynik.zawory.map(z => `<span class="badge bg-primary me-1">${z}</span>`).join('')}
                </div>
            </div>
        `;
    }
    
    html += `
        <div class="alert alert-info mt-3">
            <i class="bi bi-info-circle"></i>
            <strong>${wynik.komunikat_operatorski || 'Transfer rozpoczęty pomyślnie'}</strong>
        </div>
    `;
    
    komunikatTresc.innerHTML = html;
    
    // Pokaż modal
    const modal = new bootstrap.Modal(modalElement);
    modal.show();
}

/**
 * Zapisuje informacje o ostatnim transferze
 */
function zapiszOstatniTransfer(wynik, dane) {
    const lastTransferDiv = document.getElementById('lastTransfer');
    const lastTransferDetails = document.getElementById('lastTransferDetails');
    
    const teraz = new Date().toLocaleString('pl-PL');
    
    let html = `
        <div><strong>Czas:</strong> ${teraz}</div>
        <div><strong>Z:</strong> ${wynik.reaktor_zrodlowy}</div>
        <div><strong>Do:</strong> ${wynik.reaktor_docelowy}</div>
    `;
    
    if (dane.przez_filtr && wynik.filtr) {
        html += `<div><strong>Filtr:</strong> ${wynik.filtr}</div>`;
    }
    
    lastTransferDetails.innerHTML = html;
    lastTransferDiv.style.display = 'block';
}
