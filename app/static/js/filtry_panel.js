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
        const statusEl = document.getElementById(`${filterId.toLowerCase()}-status`);
        const operacjaEl = document.getElementById(`${filterId.toLowerCase()}-operacja`);
        const partiaEl = document.getElementById(`${filterId.toLowerCase()}-partia`);
        const kodPartiiEl = document.getElementById(`${filterId.toLowerCase()}-kod-partii`);
        const trasaEl = document.getElementById(`${filterId.toLowerCase()}-trasa`);

        if (data && data.status_operacji === 'aktywna') {
            statusEl.textContent = data.stan_sprzetu || 'Zajęty';
            operacjaEl.textContent = data.typ_operacji || '---';
            partiaEl.textContent = data.nazwa_partii || '---';
            trasaEl.textContent = `${data.sprzet_zrodlowy || '?'} → ${data.sprzet_docelowy || '?'}`;
            updateTimer(filterId, data.czas_zakonczenia_iso);
        } else {
            statusEl.textContent = data ? (data.stan_sprzetu || 'Wolny') : 'Wolny';
            operacjaEl.textContent = '---';
            partiaEl.textContent = '---';
            trasaEl.textContent = '---';
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