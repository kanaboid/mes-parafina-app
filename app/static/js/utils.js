// app/static/js/utils.js

/**
 * Konwertuje string z datą w formacie UTC (np. "YYYY-MM-DD HH:MM:SS")
 * na sformatowaną, lokalną datę i czas (np. "16.08.2025, 09:30:15").
 * Bezpiecznie obsługuje nullowe lub puste wartości.
 * 
 * @param {string | null} utcDateString Data z backendu.
 * @returns {string} Sformatowana data w lokalnej strefie czasowej lub 'Brak danych'.
 */
// function formatUTCDateToLocal(utcDateString) {
//     // 1. Sprawdzenie, czy data istnieje
//     if (!utcDateString) {
//         return 'Brak danych';
//     }

//     // 2. Upewnienie się, że data jest w formacie ISO 8601 z 'T'
//     //    i dodanie 'Z' na końcu, aby jawnie oznaczyć ją jako UTC.
//     const isoString = utcDateString.replace(' ', 'T') + 'Z';

//     const date = new Date(isoString);

//     // 4. Sprawdzenie, czy data jest poprawna
//     if (isNaN(date.getTime())) {
//         return 'Nieprawidłowa data';
//     }

//     // 5. Użycie Intl.DateTimeFormat dla najlepszego, lokalizowanego formatowania.
//     const options = {
//         year: 'numeric', month: '2-digit', day: '2-digit',
//         hour: '2-digit', minute: '2-digit', second: '2-digit',
//         hour12: false
//     };

//     return new Intl.DateTimeFormat('pl-PL', options).format(date);
// }

function formatUTCDateToLocal(utcDateString) {
    if (!utcDateString) return 'Brak danych';
    const s = utcDateString.includes('T') ? utcDateString : utcDateString.replace(' ', 'T');
    const isoString = s.endsWith('Z') ? s : s + 'Z';
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return 'Nieprawidłowa data';
    return new Intl.DateTimeFormat('pl-PL', {
      year:'numeric', month:'2-digit', day:'2-digit',
      hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false
    }).format(date);
  }
// W przyszłości możesz dodawać tutaj inne globalne funkcje, np.:
// function showToast(message, type = 'success') { ... }