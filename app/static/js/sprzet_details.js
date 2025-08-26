document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('composition-data');
    if (!container) return; // Jeśli nie ma mieszaniny, zakończ skrypt

    const mixId = container.dataset.mixId;
    const summaryContainer = document.getElementById('summary-composition-container');
    const detailedContainer = document.getElementById('detailed-composition-container');

    async function loadComposition() {
        try {
            const response = await fetch(`/api/batches/mixes/${mixId}/composition`);
            if (!response.ok) throw new Error('Błąd pobierania danych o składzie.');
            
            const data = await response.json();

            renderSummaryTable(data.summary_by_material, data.total_weight);
            renderDetailedTable(data.components_by_batch);

        } catch (error) {
            console.error(error);
            summaryContainer.innerHTML = '<p class="text-danger">Nie udało się załadować danych.</p>';
            detailedContainer.innerHTML = '';
        }
    }

    function renderSummaryTable(summaryData, totalWeight) {
        if (!summaryData || summaryData.length === 0) {
            summaryContainer.innerHTML = '<p>Brak danych do podsumowania.</p>';
            return;
        }

        let tableHTML = `
            <p><strong>Całkowita waga: ${totalWeight.toFixed(2)} kg</strong></p>
            <table class="table table-bordered">
                <thead class="table-light">
                    <tr>
                        <th>Typ Materiału</th>
                        <th class="text-end">Waga (kg)</th>
                        <th class="text-end">Udział Procentowy</th>
                    </tr>
                </thead>
                <tbody>`;
        
        summaryData.forEach(item => {
            tableHTML += `
                <tr>
                    <td><strong>${item.material_type}</strong></td>
                    <td class="text-end">${item.total_quantity.toFixed(2)}</td>
                    <td class="text-end">${item.percentage.toFixed(2)} %</td>
                </tr>`;
        });

        tableHTML += '</tbody></table>';
        summaryContainer.innerHTML = tableHTML;
    }

    function renderDetailedTable(detailedData) {
        if (!detailedData || detailedData.length === 0) {
            detailedContainer.innerHTML = '<p>Brak partii pierwotnych w tej mieszaninie.</p>';
            return;
        }

        let tableHTML = `
            <table class="table table-striped table-hover">
                <thead>
                    <tr>
                        <th>Kod Partii Pierwotnej</th>
                        <th>Typ Materiału</th>
                        <th class="text-end">Waga w Mieszaninie (kg)</th>
                        <th class="text-end">Udział Procentowy</th>
                    </tr>
                </thead>
                <tbody>`;
        
        detailedData.forEach(item => {
            tableHTML += `
                <tr>
                    <td>${item.batch_code}</td>
                    <td>${item.material_type}</td>
                    <td class="text-end">${item.quantity_in_mix.toFixed(2)}</td>
                    <td class="text-end">${item.percentage.toFixed(2)} %</td>
                </tr>`;
        });

        tableHTML += '</tbody></table>';
        detailedContainer.innerHTML = tableHTML;
    }

    loadComposition();
});