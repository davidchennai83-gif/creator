import { useState } from 'react';
import { Share2, Youtube, Facebook, Instagram } from 'lucide-react';

export const platforms = [
  { name: 'YouTube', icon: Youtube, url: 'https://www.youtube.com/upload', login: 'https://accounts.google.com/ServiceLogin?service=youtube', color: 'text-red-600', instruction: 'Select your downloaded MP4 in YouTube Studio.' },
  { name: 'Facebook', icon: Facebook, url: 'https://www.facebook.com/', login: 'https://www.facebook.com/login/', color: 'text-blue-600', instruction: 'Open your Page or profile, then Create post → Photo/video.' },
  { name: 'Instagram', icon: Instagram, url: 'https://www.instagram.com/', login: 'https://www.instagram.com/accounts/login/', color: 'text-pink-600', instruction: 'Choose Create (+), then select your downloaded MP4.' },
];

export default function ShareMenu() {
  const [open, setOpen] = useState(false);
  return <div>
    <button type="button" aria-expanded={open} onClick={()=>setOpen(!open)} className="inline-flex items-center gap-2 bg-indigo-700 text-white px-4 py-2 rounded"><Share2 size={18} aria-hidden="true"/> Share</button>
    {open && <div className="rounded border bg-white text-slate-900 p-3 mt-2 space-y-3">
      <p className="text-sm">Download the MP4, then open a platform to upload and publish it.</p>
      <div className="flex flex-wrap gap-4">{platforms.map(({name, icon: Icon, url, color})=><a key={name} href={url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${name}`} className={`flex flex-col items-center gap-1 ${color}`}><Icon size={28} aria-hidden="true"/><span className="text-xs">{name}</span></a>)}</div>
    </div>}
  </div>;
}
