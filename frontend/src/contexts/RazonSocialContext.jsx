import { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../lib/apiClient';

const RazonSocialContext = createContext(null);

export function RazonSocialProvider({ children }) {
  const [razonSociales, setRazonSociales] = useState([]);
  const [activeRS, setActiveRSState] = useState(() => {
    const saved = localStorage.getItem('logos_active_rs');
    return saved ? Number(saved) : null;
  });

  useEffect(() => {
    api.get('/api/razones-sociales')
      .then(data => setRazonSociales(data.razones_sociales ?? []))
      .catch(() => {});
  }, []);

  function setActiveRS(id) {
    const val = id ? Number(id) : null;
    setActiveRSState(val);
    if (val) {
      localStorage.setItem('logos_active_rs', String(val));
    } else {
      localStorage.removeItem('logos_active_rs');
    }
  }

  return (
    <RazonSocialContext.Provider value={{ razonSociales, activeRS, setActiveRS }}>
      {children}
    </RazonSocialContext.Provider>
  );
}

export function useRazonSocial() {
  return useContext(RazonSocialContext);
}
