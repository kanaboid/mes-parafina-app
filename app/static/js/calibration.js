// app/static/js/calibration.js

let currentTankId = null;
let calibrationData = null;

document.addEventListener('DOMContentLoaded', () => {
    loadTanksList();
    
    // Event listeners
    document.getElementById('save-all-btn').addEventListener('click', saveCalibrationTable);
    document.getElementById('save-capacity-btn').addEventListener('click', updateTankCapacity);
    document.getElementById('import-csv-btn').addEventListener('click', () => {
        document.getElementById('csv-file-input').click();
    });
    document.getElementById('csv-file-input').addEventListener('change', handleCsvImport);
    document.getElementById('test-conversion-btn').addEventListener('click', () => {
        const modal = new bootstrap.Modal(document.getElementById('testConversionModal'));
        modal.show();
    });
    document.getElementById('test-convert-btn').addEventListener('click', testConversion);
});

async function loadTanksList() {
    try {
        const response = await fetch('/api/calibration/tanks');
        const tanks = await response.json();
        
        const container = document.getElementById('tanks-list');
        container.innerHTML = '';
        
        if (tanks.length === 0) {
            container.innerHTML = '<p class="text-muted">Brak zbiorników z czujnikami</p>';
            return;
        }
        
        tanks.forEach(tank => {
            const item = document.createElement('a');
            item.href = '#';
            item.className = `list-group-item list-group-item-action ${tank.ma_kalibracje ? 'list-group-item-success' : 'list-group-item-warning'}`;
            item.innerHTML = `
                <div class="d-flex w-100 justify-content-between">
                    <h6 class="mb-1">${tank.nazwa}</h6>
                    <small>ID: ${tank.id}</small>
                </div>
                <p class="mb-1">
                    ${tank.ma_kalibracje ? 
                        `<i class="fas fa-check-circle text-success"></i> ${tank.liczba_punktow} punktów` : 
                        '<i class="fas fa-exclamation-triangle text-warning"></i> Brak kalibracji'}
                </p>
                ${tank.pojemnosc_tony ? `<small>Pojemność: ${tank.pojemnosc_tony}T</small>` : ''}
            `;
            item.addEventListener('click', (e) => {
                e.preventDefault();
                // Zaznacz aktywny element w liście
                document.querySelectorAll('#tanks-list .list-group-item').forEach(i => {
                    i.classList.remove('active');
                });
                item.classList.add('active');
                selectTank(tank.id);
            });
            container.appendChild(item);
        });
    } catch (error) {
        console.error('Błąd podczas ładowania listy zbiorników:', error);
        showToast('Błąd podczas ładowania listy zbiorników', 'error');
    }
}

async function selectTank(tankId) {
    currentTankId = tankId;
    
    try {
        const response = await fetch(`/api/calibration/tank/${tankId}/points`);
        const data = await response.json();
        
        calibrationData = data;
        
        // Pobierz nazwę zbiornika
        const tanksResponse = await fetch('/api/calibration/tanks');
        const tanks = await tanksResponse.json();
        const tank = tanks.find(t => t.id === tankId);
        
        document.getElementById('tank-name-header').textContent = 
            `Kalibracja zbiornika: ${tank ? tank.nazwa : 'ID ' + tankId} (ID: ${tankId})`;
        
        document.getElementById('pojemnosc-input').value = data.pojemnosc_tony || '';
        
        renderCalibrationTable(data);
        
        document.getElementById('calibration-panel').style.display = 'block';
        document.getElementById('no-tank-selected').style.display = 'none';
        
    } catch (error) {
        console.error('Błąd podczas ładowania kalibracji:', error);
        showToast('Błąd podczas ładowania kalibracji', 'error');
    }
}

function renderCalibrationTable(data) {
    const tbody = document.getElementById('calibration-table-body');
    tbody.innerHTML = '';
    
    const pojemnosc = data.pojemnosc_tony || 90;
    const pointsMap = {};
    data.points.forEach(p => {
        pointsMap[p.tona] = p;
    });
    
    // Generuj wiersze od 1T do 90T
    for (let tona = 1; tona <= 90; tona++) {
        const row = document.createElement('tr');
        const isOutOfRange = tona > pojemnosc;
        
        if (isOutOfRange) {
            row.classList.add('table-secondary');
            row.style.opacity = '0.6';
        }
        
        const point = pointsMap[tona];
        const cmValue = point ? point.cm : '';
        const hasValue = point !== undefined;
        
        row.innerHTML = `
            <td class="text-center fw-bold">${tona}T</td>
            <td>
                <input type="number" 
                       class="form-control form-control-sm calibration-cm-input" 
                       data-tona="${tona}"
                       value="${cmValue}"
                       step="0.1"
                       ${isOutOfRange ? 'disabled' : ''}
                       placeholder="CM">
            </td>
            <td class="text-center">
                ${hasValue ? 
                    '<i class="fas fa-check-circle text-success" title="Wartość wprowadzona"></i>' : 
                    '<i class="fas fa-circle text-muted" title="Brak wartości"></i>'}
            </td>
        `;
        
        tbody.appendChild(row);
    }
    
    // Aktualizuj status ikon przy zmianie wartości
    document.querySelectorAll('.calibration-cm-input').forEach(input => {
        input.addEventListener('input', function() {
            const row = this.closest('tr');
            const statusCell = row.querySelector('td:last-child');
            if (this.value && this.value.trim() !== '') {
                statusCell.innerHTML = '<i class="fas fa-check-circle text-success" title="Wartość wprowadzona"></i>';
            } else {
                statusCell.innerHTML = '<i class="fas fa-circle text-muted" title="Brak wartości"></i>';
            }
        });
    });
}

async function saveCalibrationTable() {
    if (!currentTankId) {
        showToast('Nie wybrano zbiornika', 'error');
        return;
    }
    
    const inputs = document.querySelectorAll('.calibration-cm-input:not(:disabled)');
    const points = [];
    
    inputs.forEach(input => {
        const cm = parseFloat(input.value);
            if (!isNaN(cm) && cm > 0) {
                points.push({
                    tona: parseInt(input.dataset.tona),
                    cm: cm
                });
            }
    });
    
    const pojemnosc = parseFloat(document.getElementById('pojemnosc-input').value);
    
    try {
        const response = await fetch(`/api/calibration/tank/${currentTankId}/points/bulk`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                points: points,
                pojemnosc_tony: pojemnosc || null
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Błąd podczas zapisywania');
        }
        
        const result = await response.json();
        showToast(`Zapisano: ${result.created} nowych, ${result.updated} zaktualizowanych punktów`, 'success');
        
        // Przeładuj dane
        await selectTank(currentTankId);
        await loadTanksList();
        
    } catch (error) {
        console.error('Błąd podczas zapisywania kalibracji:', error);
        showToast('Błąd podczas zapisywania: ' + error.message, 'error');
    }
}

async function updateTankCapacity() {
    if (!currentTankId) {
        showToast('Nie wybrano zbiornika', 'error');
        return;
    }
    
    const pojemnosc = parseFloat(document.getElementById('pojemnosc-input').value);
    
    if (isNaN(pojemnosc) || pojemnosc < 0 || pojemnosc > 90) {
        showToast('Nieprawidłowa wartość pojemności (0-90T)', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/api/calibration/sprzet/${currentTankId}/pojemnosc`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                pojemnosc_tony: pojemnosc
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Błąd podczas aktualizacji pojemności');
        }
        
        showToast('Pojemność zbiornika zaktualizowana', 'success');
        
        // Przeładuj tabelę, aby zaktualizować oznaczenia zakresu
        await selectTank(currentTankId);
        
    } catch (error) {
        console.error('Błąd podczas aktualizacji pojemności:', error);
        showToast('Błąd podczas aktualizacji pojemności: ' + error.message, 'error');
    }
}

async function handleCsvImport(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    if (!currentTankId) {
        showToast('Nie wybrano zbiornika', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch(`/api/calibration/tank/${currentTankId}/import-csv`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Błąd podczas importu CSV');
        }
        
        const result = await response.json();
        showToast(`Import zakończony: ${result.created} nowych, ${result.updated} zaktualizowanych punktów`, 'success');
        
        // Przeładuj dane
        await selectTank(currentTankId);
        await loadTanksList();
        
        // Wyczyść input
        event.target.value = '';
        
    } catch (error) {
        console.error('Błąd podczas importu CSV:', error);
        showToast('Błąd podczas importu CSV: ' + error.message, 'error');
    }
}

async function testConversion() {
    if (!currentTankId) {
        showToast('Nie wybrano zbiornika', 'error');
        return;
    }
    
    const cm = parseFloat(document.getElementById('test-cm-input').value);
    
    if (isNaN(cm) || cm <= 0) {
        showToast('Wprowadź prawidłową wartość CM', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/api/calibration/tank/${currentTankId}/test`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                odczyt_cm: cm
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Błąd podczas testu konwersji');
        }
        
        const result = await response.json();
        const resultDiv = document.getElementById('test-result');
        
        if (result.waga_tony !== null) {
            resultDiv.className = 'alert alert-success';
            resultDiv.innerHTML = `
                <strong>Wynik konwersji:</strong><br>
                Odczyt: ${result.odczyt_cm.toFixed(1)} cm (${result.odczyt_mm.toFixed(0)} mm)<br>
                Waga: <strong>${result.waga_tony.toFixed(3)} ton</strong><br>
                ${result.uzyto_interpolacji ? '<small class="text-muted">Użyto interpolacji liniowej</small>' : '<small class="text-muted">Dokładne dopasowanie</small>'}
            `;
        } else {
            resultDiv.className = 'alert alert-warning';
            resultDiv.innerHTML = `
                <strong>Brak wyniku:</strong><br>
                Odczyt ${result.odczyt_cm.toFixed(1)} cm jest poza zakresem kalibracji dla tego zbiornika.
            `;
        }
        
        resultDiv.style.display = 'block';
        
    } catch (error) {
        console.error('Błąd podczas testu konwersji:', error);
        showToast('Błąd podczas testu konwersji: ' + error.message, 'error');
    }
}

function showToast(message, type = 'info') {
    const bgColor = type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#17a2b8';
    Toastify({
        text: message,
        duration: 3000,
        gravity: "top",
        position: "right",
        backgroundColor: bgColor,
    }).showToast();
}
