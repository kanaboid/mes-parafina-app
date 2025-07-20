document.addEventListener('DOMContentLoaded', function() {
    const reaktoryContainer = document.getElementById('reaktory-container');
    const beczkiBrudneContainer = document.getElementById('beczki-brudne-container');
    const beczkiCzysteContainer = document.getElementById('beczki-czyste-container');

    function createSprzetCard(sprzet) {
        const card = document.createElement('div');
        card.className = 'col-md-4 mb-4';
        
        const partia = sprzet.partia;
        let cardBody = `
            <div class="card-body">
                <h5 class="card-title">${sprzet.nazwa_unikalna}</h5>
                <p class="card-text"><strong>Stan:</strong> ${sprzet.stan_sprzetu}</p>
        `;

        if (partia) {
            cardBody += `
                <hr>
                <p><strong>Partia:</strong> ${partia.unikalny_kod}</p>
                <p><strong>Typ:</strong> ${partia.typ_surowca}</p>
                <p><strong>Waga:</strong> ${partia.waga_aktualna_kg} kg</p>
            `;
            
            // Jeśli partia jest mieszaniną i ma zdefiniowany skład, wyświetl go
            if (partia.sklad && partia.sklad.length > 0) {
                cardBody += `<h6>Skład Procentowy:</h6><ul class="list-group list-group-flush">`;
                partia.sklad.forEach(skl => {
                    cardBody += `<li class="list-group-item d-flex justify-content-between align-items-center">
                        ${skl.typ_surowca}
                        <span class="badge bg-primary rounded-pill">${skl.procent}%</span>
                    </li>`;
                });
                cardBody += `</ul>`;
            }

        } else {
             cardBody += `<p class="text-muted">Brak partii</p>`;
        }
        
        cardBody += `</div>`;
        card.innerHTML = `<div class="card h-100">${cardBody}</div>`; // Użyj h-100 dla równej wysokości kart
        return card;
    }

    async function fetchAndDisplaySprzet() {
        try {
            const response = await fetch('/api/sprzet/stan-partii');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            // Czyszczenie kontenerów
            reaktoryContainer.innerHTML = '';
            beczkiBrudneContainer.innerHTML = '';
            beczkiCzysteContainer.innerHTML = '';

            data.reaktory.forEach(sprzet => reaktoryContainer.appendChild(createSprzetCard(sprzet)));
            data.beczki_brudne.forEach(sprzet => beczkiBrudneContainer.appendChild(createSprzetCard(sprzet)));
            data.beczki_czyste.forEach(sprzet => beczkiCzysteContainer.appendChild(createSprzetCard(sprzet)));

        } catch (error) {
            console.error("Błąd podczas pobierania danych o sprzęcie:", error);
            reaktoryContainer.innerHTML = '<p class="text-danger">Nie udało się załadować danych.</p>';
        }
    }

    fetchAndDisplaySprzet();
    setInterval(fetchAndDisplaySprzet, 15000); // Odświeżanie co 15 sekund
}); 