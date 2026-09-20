import { useState } from 'react';
import { authService, errorMessage } from '../services/apiClient';
import { useUIStore, useAuthStore } from '../stores';
export default function Topbar(){
  const [error,setError]=useState('');const [busy,setBusy]=useState(false);const user=useAuthStore(s=>s.user);const toggle=useUIStore(s=>s.toggleSidebar);
  async function logout(){setBusy(true);try{await authService.logout();}catch(e){setError(errorMessage(e));}finally{setBusy(false);}}
  return <header className="bg-white border-b p-4 flex items-center flex-wrap gap-4"><button className="md:hidden" onClick={toggle} aria-label="Open menu">☰</button><div className="ml-auto flex gap-4 items-center"><span>{user?.display_name || user?.username}</span><button disabled={busy} onClick={()=>void logout()} className="text-blue-700">Sign out</button></div>{error && <p role="alert" className="text-red-700 w-full">{error}</p>}</header>;
}
