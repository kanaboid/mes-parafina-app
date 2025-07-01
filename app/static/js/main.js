// Czekaj, aż cała strona się załaduje
document.addEventListener('DOMContentLoaded', () => {

   const sprzetContainer = document.getElementById('sprzet-container');
    const valvesContainer = document.getElementById('valves-container');
    const operationsTableBody = document.getElementById('operations-table-body');
    const logOutput = document.getElementById('log-output');
    const runButton = document.getElementById('run-r3-fz-r5');

    // Funkcja do logowania wiadomości na stronie
    function log(message) {
        logOutput.textContent = `${new Date().toLocaleTimeString()}: ${message}\n` + logOutput.textContent;
    }

    // Funkcja do pobierania i wyświetlania stanu sprzętu
    async function fetchAndDisplayStatus() {
        log('Pobieram aktualny stan sprzętu...');
        try {
            const response = await fetch('/api/sprzet');
            if (!response.ok) {
                throw new Error(`Błąd sieci: ${response.statusText}`);
            }
            const sprzetList = await response.json();
            
            sprzetContainer.innerHTML = ''; // Wyczyść kontener
            sprzetList.forEach(item => {
                const div = document.createElement('div');
                div.className = 'sprzet-item';
                div.innerHTML = `<strong>${item.nazwa_unikalna}</strong> (${item.typ_sprzetu})<br><span>${item.stan_sprzetu || 'Brak stanu'}</span>`;
                sprzetContainer.appendChild(div);
            });
            log('Stan sprzętu został zaktualizowany.');
        } catch (error) {
            log(`Błąd: ${error.message}`);
            sprzetContainer.innerHTML = '<p style="color: red;">Nie udało się załadować stanu sprzętu.</p>';
        }
    }
// NOWA funkcja do pobierania i wyświetlania stanu zaworów
    async function fetchAndDisplayValves() {
        try {
            const response = await fetch('/api/zawory');
            const valves = await response.json();
            
            valvesContainer.innerHTML = '';
            valves.forEach(valve => {
                const div = document.createElement('div');
                div.className = `valve-item ${valve.stan.toLowerCase()}`; // np. valve-item otwarty
                div.innerHTML = `<strong>${valve.nazwa_zaworu}</strong>`;
                div.dataset.id = valve.id; // Zapisujemy ID w atrybucie data-
                div.dataset.stan = valve.stan;
                valvesContainer.appendChild(div);
            });
        } catch (error) {
            log(`Błąd ładowania zaworów: ${error.message}`);
        }
    }

    // NOWA funkcja do pobierania i wyświetlania aktywnych operacji
    async function fetchAndDisplayActiveOperations() {
        try {
            const response = await fetch('/api/operacje/aktywne');
            const operations = await response.json();

            operationsTableBody.innerHTML = ''; // Wyczyść tabelę
            if (operations.length === 0) {
                operationsTableBody.innerHTML = '<tr><td colspan="6" style="text-align: center;">Brak aktywnych operacji.</td></tr>';
            } else {
                operations.forEach(op => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${op.id}</td>
                        <td>${op.typ_operacji}</td>
                        <td>${op.id_partii_surowca || 'B/D'}</td>
                        <td>${op.czas_rozpoczecia}</td>
                        <td>${op.opis}</td>
                        <td><button class="end-operation-btn" data-op-id="${op.id}">Zakończ</button></td>
                    `;
                    operationsTableBody.appendChild(row);
                });
            }
        } catch (error) {
            log(`Błąd ładowania operacji: ${error.message}`);
        }
    }
    
    // NOWA funkcja do obsługi kliknięcia na zawór
    async function handleValveClick(event) {
        const valveDiv = event.target.closest('.valve-item');
        if (!valveDiv) return;

        const valveId = valveDiv.dataset.id;
        const currentStan = valveDiv.dataset.stan;
        const newStan = currentStan === 'OTWARTY' ? 'ZAMKNIETY' : 'OTWARTY';
        
        log(`Zmieniam stan zaworu ${valveId} na ${newStan}...`);

        try {
            await fetch('/api/zawory/zmien_stan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id_zaworu: valveId, stan: newStan })
            });
            // Po sukcesie, odśwież widok zaworów
            fetchAndDisplayValves();
        } catch (error) {
            log(`Błąd zmiany stanu zaworu: ${error.message}`);
        }
    }

    // NOWA funkcja do obsługi kliknięcia przycisku "Zakończ"
    async function handleEndOperationClick(event) {
        if (!event.target.classList.contains('end-operation-btn')) return;

        const operationId = event.target.dataset.opId;
        if (!confirm(`Czy na pewno chcesz zakończyć operację o ID ${operationId}?`)) return;

        log(`Kończę operację ${operationId}...`);
        try {
            const response = await fetch('/api/operacje/zakoncz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id_operacji: parseInt(operationId) })
            });
            const result = await response.json();

            if (response.ok) {
                log(`SUKCES: ${result.message}`);
            } else {
                log(`BŁĄD (${response.status}): ${result.message}`);
            }
            // Odśwież wszystko
            updateAllViews();
        } catch (error) {
            log(`Błąd sieciowy: ${error.message}`);
        }
    }
    // Funkcja do uruchamiania operacji
    async function runOperation() {
        log('Wysyłam żądanie uruchomienia trasy R3->FZ->R5...');
        
        // Dane operacji, które wysyłamy do API
        const operationData = {
            start: "R3_OUT",
            cel: "R5_IN", // Trasa R3->FZ i potem FZ->R5
            otwarte_zawory: [
                "V_R3_OUT_W_R2_R3", "V_W_R2_R3_W_R1_R2", "V_W_R1_R2_W_R1_FZ",
                "V_W_R1_FZ_W_FZ_IN", "V_W_FZ_IN_FZ_IN", "V_FZ_OUT_W_FZ_OUT", "V_W_FZ_OUT_R5_IN", "V_FZ_IN_FZ_OUT"
            ],
            "typ_operacji": "FILTRACJA_R3_R5",
            "id_partii": 1 // Założenie, że partia 1 jest w R3
        };

        try {
            const response = await fetch('/api/operacje/rozpocznij_trase', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(operationData)
            });

            const result = await response.json();

            if (response.ok) {
                log(`SUKCES: ${result.message}`);
            } else {
                log(`BŁĄD (${response.status}): ${result.message}`);
                if (result.zajete_segmenty) {
                    log(`Konflikt na segmentach: ${result.zajete_segmenty.join(', ')}`);
                }
            }
        } catch (error) {
            log(`Błąd sieciowy: ${error.message}`);
        }
        
        // Odśwież stan sprzętu po operacji
        fetchAndDisplayStatus();
    }

    // Nasłuchuj kliknięcia na przycisk
    runButton.addEventListener('click', runOperation);
    valvesContainer.addEventListener('click', handleValveClick);
    operationsTableBody.addEventListener('click', handleEndOperationClick);
    // Pobierz stan sprzętu od razu po załadowaniu strony
    function updateAllViews() {
        fetchAndDisplayStatus();
        fetchAndDisplayValves();
        fetchAndDisplayActiveOperations();
    }
    // I odświeżaj go co 10 sekund
    updateAllViews();
    setInterval(updateAllViews, 1000);
});