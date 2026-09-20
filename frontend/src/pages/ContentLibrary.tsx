import { FormEvent, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Content, contentService, errorMessage } from '../services/apiClient';
import { Button } from '../components/common/Button';
export default function ContentLibrary() {
  const [items,setItems] = useState<Content[]>([]); const [total,setTotal] = useState(0); const [page,setPage] = useState(1); const [search,setSearch] = useState(''); const [query,setQuery] = useState(''); const [error,setError] = useState(''); const [loading,setLoading] = useState(true); const [version,setVersion] = useState(0);
  useEffect(()=>{let active=true;setLoading(true);setError('');contentService.list(page,query).then(r=>{if(active){setItems(r.data.data.items);setTotal(r.data.data.total);}}).catch(e=>{if(active)setError(errorMessage(e));}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[page,query,version]);
  async function archive(id:string){try{await contentService.archive(id);setVersion(v=>v+1);}catch(e){setError(errorMessage(e));}}
  function submit(e:FormEvent){e.preventDefault();setPage(1);setQuery(search);}
  return <section className="space-y-5"><h1 className="text-2xl font-bold">Content library</h1><form onSubmit={submit} className="flex gap-2"><input aria-label="Search content" className="input-field" maxLength={200} placeholder="Search titles" value={search} onChange={e=>setSearch(e.target.value)} /><Button type="submit">Search</Button></form>
    {error && <p role="alert" className="text-red-700">{error}</p>}{loading ? <p role="status">Loading content…</p> : <><div className="grid md:grid-cols-2 gap-4">{items.map(item=><article className="card" key={item.id}><span className="badge badge-info">{item.status}</span><h2 className="text-lg font-bold my-3 break-words">{item.title}</h2><p className="text-gray-500 line-clamp-3">{item.description}</p><div className="flex items-center gap-4 mt-4"><Link className="text-blue-700 underline" to={`/content/${item.id}/edit`}>Edit</Link><Button variant="secondary" onClick={()=>void archive(item.id)}>Archive</Button></div></article>)}</div>{items.length===0 && <p>No drafts found. <Link className="underline" to="/content/studio">Create one</Link>.</p>}<div className="flex items-center gap-4"><Button variant="secondary" disabled={page===1} onClick={()=>setPage(p=>p-1)}>Previous</Button><span>Page {page} · {total} items</span><Button variant="secondary" disabled={page*20>=total} onClick={()=>setPage(p=>p+1)}>Next</Button></div></>}
  </section>;
}
