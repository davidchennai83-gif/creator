import { useEffect, useState } from 'react';
import api, { errorMessage } from '../services/apiClient';
import { Button } from '../components/common/Button';
interface Log {id:string;action:string;timestamp:string;result:string}
export default function ActivityLogs(){
  const [items,setItems]=useState<Log[]>([]); const [page,setPage]=useState(1); const [error,setError]=useState('');
  useEffect(()=>{let active=true;api.get('/audit-logs',{params:{page}}).then(r=>{if(active)setItems(r.data.data.items);}).catch(e=>{if(active)setError(errorMessage(e));});return()=>{active=false;};},[page]);
  return <section className="card"><h1 className="text-2xl font-bold mb-5">Activity logs</h1>{error && <p role="alert">{error}</p>}<ul>{items.map(i=><li className="py-3 border-b" key={i.id}>{i.action} · {i.result}<time className="block text-sm text-gray-500">{new Date(i.timestamp).toLocaleString()}</time></li>)}</ul><div className="flex gap-4 mt-5"><Button disabled={page===1} onClick={()=>setPage(p=>p-1)}>Previous</Button><span>{page}</span><Button disabled={items.length<20} onClick={()=>setPage(p=>p+1)}>Next</Button></div></section>;
}
