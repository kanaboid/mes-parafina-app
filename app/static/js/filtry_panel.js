// SCADA Panel for Filters Control
document.addEventListener('DOMContentLoaded', () => {
    const timers = {
        FZ: null,
        FN: null
    };

    let connectionStatus = true;
    let lastUpdateTime = null;
    let updatesPaused = false;
    let soundsEnabled = true;
    let updateInterval = null;
    let systemStartTime = Date.now();
    let totalFilters = 2;
    let systemMetrics = {
        activeFilters: 0,
        queueTotal: 0,
        efficiency: 0
    };

    // Audio notifications
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    
    function playNotificationSound(type = 'info') {
        if (!soundsEnabled) return;
        
        const frequencies = {
            'info': 800,
            'warning': 600,
            'error': 400,
            'success': 1000
        };
        
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.setValueAtTime(frequencies[type] || 800, audioContext.currentTime);
        oscillator.type = 'sine';
        
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
        
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.3);
    }

    // Initialize SCADA interface
    initializeSCADA();
    
    function initializeSCADA() {
        updateCurrentTime();
        setInterval(updateCurrentTime, 1000);
        
        if (!updatesPaused) {
            fetchAndUpdateStatus();
            updateInterval = setInterval(fetchAndUpdateStatus, 3000);
        }
        
        // Connection monitoring
        setInterval(checkConnection, 5000);
        
        // Control buttons
        setupControlButtons();
    }

    function setupControlButtons() {
        const muteBtn = document.getElementById('mute-sounds');
        const pauseBtn = document.getElementById('pause-updates');
        const refreshBtn = document.getElementById('force-refresh');
        
        if (muteBtn) {
            muteBtn.addEventListener('click', () => {
                soundsEnabled = !soundsEnabled;
                muteBtn.innerHTML = soundsEnabled ? 
                    '<i class="fas fa-volume-up"></i> DŹWIĘK' : 
                    '<i class="fas fa-volume-mute"></i> WYCISZ';
                muteBtn.className = soundsEnabled ? 'btn btn-sm btn-warning' : 'btn btn-sm btn-danger';
                playNotificationSound(soundsEnabled ? 'success' : 'warning');
            });
        }
        
        if (pauseBtn) {
            pauseBtn.addEventListener('click', () => {
                updatesPaused = !updatesPaused;
                if (updatesPaused) {
                    clearInterval(updateInterval);
                    pauseBtn.innerHTML = '<i class="fas fa-play"></i> WZNÓW';
                    pauseBtn.className = 'btn btn-sm btn-danger';
                } else {
                    updateInterval = setInterval(fetchAndUpdateStatus, 3000);
                    pauseBtn.innerHTML = '<i class="fas fa-pause"></i> PAUZA';
                    pauseBtn.className = 'btn btn-sm btn-info';
                }
                playNotificationSound('info');
            });
        }
        
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                fetchAndUpdateStatus();
                playNotificationSound('info');
                refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ODŚWIEŻ';
                setTimeout(() => {
                    refreshBtn.innerHTML = '<i class="fas fa-sync"></i> ODŚWIEŻ';
                }, 1000);
            });
        }
    }

    function updateCurrentTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('pl-PL', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        const element = document.getElementById('current-time');
        if (element) {
            element.textContent = timeString;
        }
        
        // Update system uptime
        const uptimeElement = document.getElementById('system-uptime');
        if (uptimeElement) {
            const uptime = now - systemStartTime;
            const hours = Math.floor(uptime / (1000 * 60 * 60));
            const minutes = Math.floor((uptime % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((uptime % (1000 * 60)) / 1000);
            uptimeElement.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }
        
        // Update last update time
        const lastUpdateElement = document.getElementById('last-update');
        if (lastUpdateElement && lastUpdateTime) {
            const lastUpdate = new Date(lastUpdateTime);
            lastUpdateElement.textContent = lastUpdate.toLocaleTimeString('pl-PL', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
        }
    }

    function checkConnection() {
        const statusElement = document.getElementById('connection-status');
        const dataStatusDot = document.getElementById('data-status');
        const dataStatusText = document.getElementById('data-status-text');
        
        if (!lastUpdateTime || (Date.now() - lastUpdateTime) > 10000) {
            // No update for 10 seconds
            connectionStatus = false;
            statusElement.className = 'connection-status disconnected';
            statusElement.innerHTML = '<i class="fas fa-wifi-slash"></i> BŁĄD POŁĄCZENIA';
            
            dataStatusDot.className = 'status-dot status-error';
            dataStatusText.textContent = 'BŁĄD DANYCH';
        } else {
            connectionStatus = true;
            statusElement.className = 'connection-status connected';
            statusElement.innerHTML = '<i class="fas fa-wifi"></i> POŁĄCZONO';
            
            dataStatusDot.className = 'status-dot status-online';
            dataStatusText.textContent = 'DANE AKTUALNE';
        }
    }

    function updateTimer(filterId, endTime, startTime) {
        const timerElement = document.getElementById(`${filterId.toLowerCase()}-timer`);
        const progressElement = document.getElementById(`${filterId.toLowerCase()}-progress`);
        const progressText = document.getElementById(`${filterId.toLowerCase()}-progress-text`);
        
        if (!timerElement) return;

        // Clear existing timer
        if (timers[filterId]) {
            clearInterval(timers[filterId]);
        }

        if (!endTime) {
            timerElement.textContent = '--:--:--';
            timerElement.classList.remove('timer-expired');
            if (progressElement) progressElement.style.width = '0%';
            if (progressText) progressText.textContent = '0%';
            return;
        }

        const start = startTime ? new Date(startTime) : new Date();
        const end = new Date(endTime);
        const totalDuration = end - start;

        timers[filterId] = setInterval(() => {
            const now = new Date();
            const remaining = end - now;
            const elapsed = now - start;

            if (remaining <= 0) {
                clearInterval(timers[filterId]);
                timerElement.textContent = '00:00:00';
                timerElement.classList.add('timer-expired');
                if (progressElement) progressElement.style.width = '100%';
                if (progressText) progressText.textContent = '100%';
                return;
            }

            // Calculate time
            const hours = Math.floor((remaining / (1000 * 60 * 60)) % 24).toString().padStart(2, '0');
            const minutes = Math.floor((remaining / 1000 / 60) % 60).toString().padStart(2, '0');
            const seconds = Math.floor((remaining / 1000) % 60).toString().padStart(2, '0');

            timerElement.textContent = `${hours}:${minutes}:${seconds}`;
            timerElement.classList.remove('timer-expired');

            // Calculate progress
            if (totalDuration > 0 && progressElement && progressText) {
                const progress = Math.min(100, Math.max(0, (elapsed / totalDuration) * 100));
                progressElement.style.width = `${progress}%`;
                progressText.textContent = `${Math.round(progress)}%`;
            }
        }, 1000);
    }

    function updateFilterPanel(filterId, data) {
        const prefix = filterId.toLowerCase();
        const panel = document.getElementById(`filter-${prefix}`);
        
        // Store previous state for change detection
        const prevState = panel.dataset.lastState;
        const currentState = data && data.aktywna_operacja ? 'active' : 'idle';
        
        // Update operation status
        const statusElement = document.getElementById(`${prefix}-status-text`);
        const operationStatus = document.getElementById(`${prefix}-operation-status`);
        const operationIcon = operationStatus.querySelector('.operation-icon');
        
        if (data && data.aktywna_operacja) {
            const operation = data.aktywna_operacja;
            
            // Detect state change
            if (prevState !== 'active') {
                playNotificationSound('success');
            }
            
            // Update status
            statusElement.textContent = 'AKTYWNA';
            operationIcon.className = 'fas fa-cog operation-icon';
            operationStatus.style.color = '#ffffff';
            panel.classList.remove('inactive-filter');
            panel.classList.add('active-filter');
            
            // Update parameters
            setText(`${prefix}-operation`, operation.typ_operacji || 'NIEZNANA');
            setText(`${prefix}-batch`, operation.nazwa_partii || '---');
            setText(`${prefix}-batch-code`, operation.unikalny_kod || '---');
            setText(`${prefix}-route`, `${operation.reaktor_startowy || '?'} → ${operation.reaktor_docelowy || '?'}`);
            
            // Update timer with progress
            updateTimer(filterId, operation.planowany_czas_zakonczenia, operation.czas_rozpoczecia_etapu);
            
            // Clear queue display
            const queueElement = document.getElementById(`${prefix}-queue`);
            queueElement.innerHTML = '<div style="text-align: center; opacity: 0.6; color: #000080;"><i class="fas fa-cog fa-spin"></i> Filtr zajęty</div>';
            
        } else {
            // Detect state change
            if (prevState === 'active') {
                playNotificationSound('info');
            }
            
            // Filter is idle
            statusElement.textContent = 'STANDBY';
            operationIcon.className = 'fas fa-circle-pause operation-icon';
            operationStatus.style.color = '#ffffff';
            panel.classList.add('inactive-filter');
            panel.classList.remove('active-filter');
            
            // Clear parameters
            setText(`${prefix}-operation`, '---');
            setText(`${prefix}-batch`, '---');
            setText(`${prefix}-batch-code`, '---');
            setText(`${prefix}-route`, '---');
            
            // Clear timer
            updateTimer(filterId, null);
            
            // Update queue
            updateQueue(prefix, data ? data.kolejka_oczekujacych : []);
        }
        
        // Store current state
        panel.dataset.lastState = currentState;
    }

    function updateSystemMetrics() {
        // Update active filters count
        const activeFiltersElement = document.getElementById('active-filters');
        if (activeFiltersElement) {
            activeFiltersElement.textContent = `${systemMetrics.activeFilters}/${totalFilters}`;
        }
        
        // Update queue total
        const queueTotalElement = document.getElementById('queue-total');
        if (queueTotalElement) {
            queueTotalElement.textContent = systemMetrics.queueTotal;
        }
        
        // Calculate and update efficiency
        const efficiency = totalFilters > 0 ? Math.round((systemMetrics.activeFilters / totalFilters) * 100) : 0;
        const efficiencyElement = document.getElementById('system-efficiency');
        if (efficiencyElement) {
            efficiencyElement.textContent = efficiency;
            // Change color based on efficiency - PROMOTIC style colors
            if (efficiency >= 80) {
                efficiencyElement.style.color = '#008000'; // Dark green
            } else if (efficiency >= 50) {
                efficiencyElement.style.color = '#808000'; // Dark yellow/olive
            } else {
                efficiencyElement.style.color = '#800000'; // Dark red
            }
        }
    }

    function updateQueue(prefix, queueData) {
        const queueElement = document.getElementById(`${prefix}-queue`);
        
        if (!queueData || queueData.length === 0) {
            queueElement.innerHTML = '<div style="text-align: center; opacity: 0.6; color: #808080; font-style: italic;">Brak partii w kolejce</div>';
            return;
        }

        const queueHTML = queueData.map((item, index) => `
            <div class="queue-item">
                <div>
                    <div class="batch-code">${item.unikalny_kod || 'Brak kodu'}</div>
                    <div style="font-size: 9px; color: #404040;">${item.nazwa_reaktora || 'Nieznany reaktor'}</div>
                </div>
                <div style="font-size: 9px; color: #000080; font-weight: bold;">
                    #${index + 1}
                </div>
            </div>
        `).join('');
        
        queueElement.innerHTML = queueHTML;
    }

    function setText(elementId, text) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = text;
        }
    }

    async function fetchAndUpdateStatus() {
        try {
            const response = await fetch('/api/filtry/szczegolowy-status');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            lastUpdateTime = Date.now();
            
            // Reset metrics
            systemMetrics.activeFilters = 0;
            systemMetrics.queueTotal = 0;
            
            // Find data for each filter and update metrics
            const fzData = data.find(f => f.nazwa_filtra === 'FZ');
            const fnData = data.find(f => f.nazwa_filtra === 'FN');

            // Count active filters and queue
            if (fzData && fzData.aktywna_operacja) systemMetrics.activeFilters++;
            if (fnData && fnData.aktywna_operacja) systemMetrics.activeFilters++;
            
            if (fzData && fzData.kolejka_oczekujacych) systemMetrics.queueTotal += fzData.kolejka_oczekujacych.length;
            if (fnData && fnData.kolejka_oczekujacych) systemMetrics.queueTotal += fnData.kolejka_oczekujacych.length;

            updateFilterPanel('FZ', fzData);
            updateFilterPanel('FN', fnData);
            updateSystemMetrics();

        } catch (error) {
            console.error("Błąd podczas aktualizacji statusu filtrów:", error);
            
            // Update connection status on error
            const dataStatusDot = document.getElementById('data-status');
            const dataStatusText = document.getElementById('data-status-text');
            
            if (dataStatusDot) dataStatusDot.className = 'status-dot status-error';
            if (dataStatusText) dataStatusText.textContent = 'BŁĄD KOMUNIKACJI';
            
            playNotificationSound('error');
        }
    }

    // Expose functions for debugging
    window.SCADAFilters = {
        refreshStatus: fetchAndUpdateStatus,
        checkConnection: checkConnection,
        timers: timers
    };
});