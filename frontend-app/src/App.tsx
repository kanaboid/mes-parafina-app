import React, { useState, useEffect, useCallback } from 'react';
import { FaSyncAlt, FaTruck, FaGasPump, FaFlask, FaPlusCircle, FaWarehouse, FaTimesCircle, FaCheckCircle, FaExclamationTriangle, FaChevronDown, FaChevronUp } from 'react-icons/fa';

// --- Komponenty Pomocnicze UI ---

// Komponent do wyświetlania powiadomień (sukces/błąd)
const Notification = ({ message, type, onDismiss }) => {
  if (!message) return null;
  const baseClasses = "fixed top-5 right-5 p-4 rounded-lg shadow-lg flex items-center gap-3 z-50 animate-fade-in-down";
  const typeClasses = {
    success: "bg-green-500 text-white",
    error: "bg-red-500 text-white",
  };
  return (
    <div className={`${baseClasses} ${typeClasses[type]}`}>
      {type === 'success' ? <FaCheckCircle /> : <FaExclamationTriangle />}
      <span>{message}</span>
      <button onClick={onDismiss} className="ml-4 text-xl">&times;</button>
    </div>
  );
};

// Input stylizowany pod Tailwind
const FormInput = ({ label, name, value, onChange, placeholder, type = "text" }) => (
  <div>
    <label htmlFor={name} className="block text-sm font-medium text-gray-400 mb-1">{label}</label>
    <input
      type={type}
      id={name}
      name={name}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      className="w-full bg-slate-700 border border-slate-600 rounded-md p-2 text-white focus:ring-2 focus:ring-cyan-500 focus:outline-none transition"
    />
  </div>
);

// Przycisk stylizowany pod Tailwind
const ActionButton = ({ children, onClick, type = "submit", variant = "primary", disabled = false }) => {
  const variants = {
    primary: "bg-cyan-600 hover:bg-cyan-700",
    secondary: "bg-slate-600 hover:bg-slate-700",
    danger: "bg-red-600 hover:bg-red-700",
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`px-4 py-2 rounded-md font-semibold text-white transition ${variants[variant]} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      {children}
    </button>
  );
};

// Składany panel dla formularzy
const CollapsibleSection = ({ title, icon, children }) => {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <div className="bg-slate-800 rounded-lg shadow-xl mb-6">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex justify-between items-center p-4 text-left"
      >
        <div className="flex items-center gap-3">
          {icon}
          <h3 className="font-bold text-lg text-white">{title}</h3>
        </div>
        {isOpen ? <FaChevronUp /> : <FaChevronDown />}
      </button>
      {isOpen && (
        <div className="p-4 border-t border-slate-700">
          {children}
        </div>
      )}
    </div>
  );
};


// --- Komponenty Operacji ---

// Formularz: Tankowanie Brudnego Surowca
const TankowanieBrudnegoForm = ({ onOperationStart }) => {
  const [formData, setFormData] = useState({
    id_beczki: '',
    id_reaktora: '',
    typ_surowca: '',
    waga_kg: '',
    temperatura_surowca: '',
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    onOperationStart('/api/operations/tankowanie-brudnego', formData, "Tankowanie brudnego surowca rozpoczęte.");
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <FormInput label="ID Beczki źródłowej" name="id_beczki" value={formData.id_beczki} onChange={handleChange} placeholder="np. 12" />
      <FormInput label="ID Reaktora docelowego" name="id_reaktora" value={formData.id_reaktora} onChange={handleChange} placeholder="np. 3" />
      <FormInput label="Typ surowca" name="typ_surowca" value={formData.typ_surowca} onChange={handleChange} placeholder="np. Olej Rzepakowy" />
      <FormInput label="Waga (kg)" name="waga_kg" value={formData.waga_kg} onChange={handleChange} type="number" placeholder="np. 8500" />
      <FormInput label="Temperatura surowca (°C)" name="temperatura_surowca" value={formData.temperatura_surowca} onChange={handleChange} type="number" placeholder="np. 25" />
      <ActionButton>Rozpocznij Tankowanie</ActionButton>
    </form>
  );
};

// Formularz: Transfer między reaktorami
const TransferReaktorowForm = ({ onOperationStart }) => {
  const [formData, setFormData] = useState({
    id_reaktora_zrodlowego: '',
    id_reaktora_docelowego: '',
    id_filtra: '',
  });

  const handleChange = (e) => setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }));

  const handleSubmit = (e) => {
    e.preventDefault();
    const payload = { ...formData };
    if (!payload.id_filtra) delete payload.id_filtra; // Usuń jeśli puste
    onOperationStart('/api/operations/transfer-reaktorow', payload, "Transfer między reaktorami rozpoczęty.");
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <FormInput label="ID Reaktora źródłowego" name="id_reaktora_zrodlowego" value={formData.id_reaktora_zrodlowego} onChange={handleChange} placeholder="np. 3" />
      <FormInput label="ID Reaktora docelowego" name="id_reaktora_docelowego" value={formData.id_reaktora_docelowego} onChange={handleChange} placeholder="np. 5" />
      <FormInput label="ID Filtra (opcjonalnie)" name="id_filtra" value={formData.id_filtra} onChange={handleChange} placeholder="np. F1" />
      <ActionButton>Rozpocznij Transfer</ActionButton>
    </form>
  );
};

// Formularz: Rozpocznij roztankowanie cysterny
const StartCysternaForm = ({ onOperationStart }) => {
    const [formData, setFormData] = useState({ id_cysterny: '', id_celu: '' });
    const handleChange = (e) => setFormData(p => ({ ...p, [e.target.name]: e.target.value }));
    const handleSubmit = (e) => {
        e.preventDefault();
        onOperationStart('/api/operations/roztankuj-cysterne/start', formData, "Roztankowanie cysterny rozpoczęte.");
    };
    return (
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormInput label="ID Cysterny" name="id_cysterny" value={formData.id_cysterny} onChange={handleChange} placeholder="np. 15" />
        <FormInput label="ID Celu (Reaktor/Beczka/Zbiornik)" name="id_celu" value={formData.id_celu} onChange={handleChange} placeholder="np. 4" />
        <ActionButton>Rozpocznij Roztankowanie</ActionButton>
      </form>
    );
}

// Formularz: Zakończ roztankowanie cysterny
const EndCysternaForm = ({ onOperationStart, operationId }) => {
    const [formData, setFormData] = useState({
        id_operacji: operationId,
        waga_netto_kg: '',
        typ_surowca: '',
        nr_rejestracyjny: '',
        nr_dokumentu_dostawy: '',
        nazwa_dostawcy: '',
    });

    useEffect(() => {
        setFormData(p => ({...p, id_operacji: operationId }));
    }, [operationId]);

    const handleChange = (e) => setFormData(p => ({ ...p, [e.target.name]: e.target.value }));

    const handleSubmit = (e) => {
        e.preventDefault();
        onOperationStart('/api/operations/roztankuj-cysterne/zakoncz', formData, "Zakończono roztankowanie cysterny.");
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-4 mt-4 p-4 border-t-2 border-slate-700">
             <h4 className="font-bold text-md text-white">Zakończ operację #{operationId}</h4>
            <FormInput label="Waga netto (kg)" name="waga_netto_kg" value={formData.waga_netto_kg} onChange={handleChange} type="number" placeholder="np. 22000" />
            <FormInput label="Typ surowca" name="typ_surowca" value={formData.typ_surowca} onChange={handleChange} placeholder="np. Olej Posmażalniczy" />
            <FormInput label="Nr rejestracyjny pojazdu" name="nr_rejestracyjny" value={formData.nr_rejestracyjny} onChange={handleChange} placeholder="np. WZ 12345" />
            <FormInput label="Nr dokumentu dostawy" name="nr_dokumentu_dostawy" value={formData.nr_dokumentu_dostawy} onChange={handleChange} placeholder="np. WZ/2023/10/123" />
            <FormInput label="Nazwa dostawcy" name="nazwa_dostawcy" value={formData.nazwa_dostawcy} onChange={handleChange} placeholder="np. EkoTrans" />
            <ActionButton>Zakończ i Zapisz Partię</ActionButton>
        </form>
    );
};


// Komponent wyświetlający listę aktywnych operacji
const ActiveOperationsList = ({ operations, onAction }) => {
  return (
    <div className="bg-slate-800 rounded-lg shadow-xl p-6">
      <h3 className="font-bold text-xl text-white mb-4">Aktywne Operacje ({operations.length})</h3>
      {operations.length === 0 ? (
        <p className="text-gray-400">Brak aktywnych operacji.</p>
      ) : (
        <div className="space-y-4">
          {operations.map(op => (
            <div key={op.id} className="bg-slate-900 p-4 rounded-md flex justify-between items-center">
              <div>
                <p className="font-bold text-cyan-400">ID: {op.id}</p>
                <p className="text-white">{op.typ_operacji}</p>
                <p className="text-sm text-gray-400">{op.opis}</p>
                <p className="text-xs text-gray-500">Rozpoczęto: {op.czas_rozpoczecia}</p>
              </div>
              <div className="flex gap-2">
                 {/* Przyciski zakończenia / anulowania w zależności od typu operacji */}
                {op.typ_operacji.includes("CYSTERNY") && (
                  <ActionButton onClick={() => onAction('/api/operations/roztankuj-cysterne/anuluj', { id_operacji: op.id }, `Anulowano operację #${op.id}`)} variant="danger">Anuluj</ActionButton>
                )}
                {op.typ_operacji.includes("APOLLO") && (
                  <>
                    <ActionButton onClick={() => {
                        const waga = prompt(`Podaj wagę dla zakończenia operacji #${op.id} (kg):`);
                        if(waga) onAction('/api/operations/apollo-transfer/end', { id_operacji: op.id, waga_kg: parseFloat(waga) }, `Zakończono operację #${op.id}`);
                    }} variant="primary">Zakończ</ActionButton>
                    <ActionButton onClick={() => onAction('/api/operations/apollo-transfer/anuluj', { id_operacji: op.id }, `Anulowano operację #${op.id}`)} variant="danger">Anuluj</ActionButton>
                  </>
                )}
                 {!op.typ_operacji.includes("APOLLO") && !op.typ_operacji.includes("CYSTERNY") && (
                    <ActionButton onClick={() => onAction('/api/operations/zakoncz', { id_operacji: op.id }, `Zakończono operację #${op.id}`)} variant="primary">Zakończ</ActionButton>
                 )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// --- Główny Komponent Aplikacji ---
function App() {
  const [activeOperations, setActiveOperations] = useState([]);
  const [notification, setNotification] = useState({ message: null, type: 'success' });

  const fetchActiveOperations = useCallback(async () => {
    try {
      const response = await fetch('/api/operations/aktywne');
      if (!response.ok) throw new Error('Błąd pobierania danych');
      const data = await response.json();
      setActiveOperations(data);
    } catch (error) {
      showNotification(error.message, 'error');
    }
  }, []);

  useEffect(() => {
    fetchActiveOperations();
    const interval = setInterval(fetchActiveOperations, 10000); // Odświeżaj co 10 sekund
    return () => clearInterval(interval);
  }, [fetchActiveOperations]);

  const showNotification = (message, type = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification({ message: null, type: 'success' }), 5000);
  };

  const handleApiCall = async (endpoint, payload, successMessage) => {
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.message || `Błąd serwera: ${response.status}`);
      }
      showNotification(data.message || successMessage, 'success');
      fetchActiveOperations(); // Odśwież listę po udanej operacji
    } catch (error) {
      showNotification(error.message, 'error');
    }
  };
  
  const cysternaOps = activeOperations.filter(op => op.typ_operacji === 'ROZTANKOWANIE_CYSTERNY');

  return (
    <div className="bg-slate-900 text-gray-300 min-h-screen font-sans p-4 sm:p-8">
      <Notification message={notification.message} type={notification.type} onDismiss={() => setNotification({ message: null })} />
      <header className="mb-10 text-center">
        <h1 className="text-4xl md:text-5xl font-extrabold text-white">Panel Operacyjny</h1>
        <p className="text-slate-400 mt-2">Zarządzaj operacjami przemysłowymi w czasie rzeczywistym</p>
      </header>

      <main className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Kolumna z formularzami operacji */}
        <div className="lg:col-span-2 space-y-6">
            <CollapsibleSection title="Tankowanie Brudnego Surowca" icon={<FaGasPump className="text-yellow-400" />}>
                <TankowanieBrudnegoForm onOperationStart={handleApiCall} />
            </CollapsibleSection>

            <CollapsibleSection title="Transfer Między Reaktorami" icon={<FaSyncAlt className="text-blue-400" />}>
                <TransferReaktorowForm onOperationStart={handleApiCall} />
            </CollapsibleSection>

            <CollapsibleSection title="Roztankowanie Cysterny" icon={<FaTruck className="text-green-400" />}>
                <StartCysternaForm onOperationStart={handleApiCall} />
                {cysternaOps.length > 0 && (
                    <div className="mt-6">
                        <h4 className="font-bold text-lg mb-2 text-white">Wybierz aktywną operację do zakończenia:</h4>
                        {cysternaOps.map(op => (
                           <EndCysternaForm key={op.id} onOperationStart={handleApiCall} operationId={op.id} />
                        ))}
                    </div>
                )}
            </CollapsibleSection>

            {/* TODO: Dodaj więcej formularzy dla reszty endpointów, np. Dobielanie, Apollo itp. */}
            {/* Przykład: */}
            <CollapsibleSection title="Operacje Apollo" icon={<FaWarehouse className="text-purple-400" />}>
              <p className="text-gray-400">Formularze dla /apollo-transfer/start i /apollo-transfer/end do implementacji.</p>
            </CollapsibleSection>

            <CollapsibleSection title="Dobielanie" icon={<FaPlusCircle className="text-lime-400" />}>
              <p className="text-gray-400">Formularz dla /dobielanie do implementacji.</p>
            </CollapsibleSection>
        </div>

        {/* Kolumna z aktywnymi operacjami */}
        <div className="lg:col-span-1">
          <ActiveOperationsList operations={activeOperations} onAction={handleApiCall} />
        </div>
      </main>
    </div>
  );
}

export default App;