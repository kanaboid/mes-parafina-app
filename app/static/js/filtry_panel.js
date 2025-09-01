document.addEventListener('DOMContentLoaded', () => {
    const timers = {
        FZ: null,
        FN: null
    };

    function updateTimer(filterId, endTime) {
        const timerElement = document.getElementById(`${filterId.toLowerCase()}-timer`);
        if (!timerElement) return;

        // Wyczyść stary timer, jeśli istnieje
        if (timers[filterId]) {
            clearInterval(timers[filterId]);
        }

        if (!endTime) {
            timerElement.textContent = '--:--:--';
            return;
        }

        const end = new Date(endTime);

        timers[filterId] = setInterval(() => {
            const now = new Date();
            const remaining = end - now;

            if (remaining <= 0) {
                clearInterval(timers[filterId]);
                timerElement.textContent = '00:00:00';
                // Można dodać efekt wizualny, np. miganie
                timerElement.classList.add('text-danger');
                return;
            }

            const hours = Math.floor((remaining / (1000 * 60 * 60)) % 24).toString().padStart(2, '0');
            const minutes = Math.floor((remaining / 1000 / 60) % 60).toString().padStart(2, '0');
            const seconds = Math.floor((remaining / 1000) % 60).toString().padStart(2, '0');

            timerElement.textContent = `${hours}:${minutes}:${seconds}`;
            timerElement.classList.remove('text-danger');
        }, 1000);
    }

    function updateFilterCard(filterId, data) {
        // Funkcja pomocnicza do bezpiecznego ustawiania tekstu
        const setText = (elementId, text) => {
            const el = document.getElementById(elementId);
            if (el) {
                el.textContent = text;
            } else {
                console.warn(`Nie znaleziono elementu o ID: ${elementId}`);
            }
        };

        const prefix = filterId.toLowerCase();

        if (data && data.status_operacji === 'aktywna') {
            setText(`${prefix}-status`, data.stan_sprzetu || 'Zajęty');
            setText(`${prefix}-operacja`, data.typ_operacji || '---');
            setText(`${prefix}-partia`, data.nazwa_partii || '---');
            setText(`${prefix}-kod-partii`, data.unikalny_kod || '---');
            setText(`${prefix}-trasa`, `${data.sprzet_zrodlowy || '?'} → ${data.sprzet_docelowy || '?'}`);
            updateTimer(filterId, data.czas_zakonczenia_iso);
        } else {
            const statusText = data ? (data.stan_sprzetu || 'Wolny') : 'Wolny';
            setText(`${prefix}-status`, statusText);
            setText(`${prefix}-operacja`, '---');
            setText(`${prefix}-partia`, '---');
            setText(`${prefix}-kod-partii`, '---');
            setText(`${prefix}-trasa`, '---');
            updateTimer(filterId, null);
        }
    }

    async function fetchAndUpdateStatus() {
        try {
            const response = await fetch('/api/filtry/status');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            
            const fz_data = data.find(f => f.nazwa_filtra === 'FZ');
            const fn_data = data.find(f => f.nazwa_filtra === 'FN');

            updateFilterCard('FZ', fz_data);
            updateFilterCard('FN', fn_data);

        } catch (error) {
            console.error("Błąd podczas aktualizacji statusu filtrów:", error);
        }
    }

    fetchAndUpdateStatus();
    setInterval(fetchAndUpdateStatus, 5000); // Odświeżaj co 5 sekund
});


