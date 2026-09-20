import { FormEvent, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { contentService, ContentInput, errorMessage } from '../services/apiClient';
import { Input, Select } from '../components/common/Form';
import { Button } from '../components/common/Button';

export default function ContentStudio() {
  const {id} = useParams(); const navigate = useNavigate(); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const [data, setData] = useState<ContentInput>({title:'', description:'', category:'OTHER', language:'en'});
  useEffect(() => { let active = true; if (id) contentService.get(id).then(r => {if (active) {const d=r.data.data; setData({title:d.title,description:d.description,category:d.category,language:d.language});}}).catch(e=>{if(active)setError(errorMessage(e));}); return ()=>{active=false;}; }, [id]);
  async function submit(e: FormEvent) { e.preventDefault(); setBusy(true); setError(''); try { if(id) await contentService.update(id,data); else await contentService.create(data); navigate('/content/library'); } catch(e) {setError(errorMessage(e));} finally {setBusy(false);} }
  return <section className="card max-w-3xl"><h1 className="text-2xl font-bold mb-6">{id ? 'Edit content' : 'Content Studio'}</h1><form onSubmit={submit} className="space-y-5">
    <Input label="Title" required maxLength={500} value={data.title} onChange={e=>setData({...data,title:e.target.value})} />
    <label className="block">Description / idea<textarea className="input-field mt-2" rows={8} maxLength={20000} value={data.description || ''} onChange={e=>setData({...data,description:e.target.value})} /></label>
    <Select label="Category" value={data.category} onChange={e=>setData({...data,category:e.target.value})} options={['TUTORIAL','VLOG','REVIEW','EDUCATION','ENTERTAINMENT','PROMOTION','NEWS','OTHER'].map(value=>({value,label:value}))} />
    <Input label="Language code" required minLength={2} maxLength={10} value={data.language} onChange={e=>setData({...data,language:e.target.value})} />
    {error && <p role="alert" className="text-red-700">{error}</p>}<Button type="submit" loading={busy}>Save draft</Button>
  </form></section>;
}
