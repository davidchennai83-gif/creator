import { Link } from 'react-router-dom';
import { platforms } from '../components/ShareMenu';

export default function Social() {
  return <section className="space-y-6 max-w-4xl">
    <h1 className="text-3xl font-bold">Social Media</h1>
    <p>Sign in on each platform's official website. Your existing browser session will be used there.</p>
    <div className="grid gap-4 sm:grid-cols-3">
      {platforms.map(({name, icon: Icon, login, url, color, instruction})=><article key={name} className="bg-white border rounded-xl p-5 space-y-4">
        <h2 className={`font-bold flex items-center gap-2 ${color}`}><Icon aria-hidden="true"/>{name}</h2>
        <a href={login} target="_blank" rel="noopener noreferrer" className="block bg-indigo-700 text-white rounded px-3 py-2">Log in to {name}</a>
        <a href={url} target="_blank" rel="noopener noreferrer" className="block underline">Open {name}</a>
        <p className="text-sm">{instruction}</p>
      </article>)}
    </div>
    <p className="text-sm">YouTube posts automatically. Facebook and Instagram post automatically once you connect them once on the PC: run the desktop shortcut <b>“Connect-Facebook-Instagram”</b> (or ask the agent to run it) and log in to each site in the Chrome window that opens. No password is stored — only the browser session.</p>
    <p className="text-sm text-slate-500">Website login here is only for your browser; the automatic uploader uses a saved session on the PC.</p>
    <Link to="/video-creator" className="text-teal-700 underline">Choose a video to download and share</Link>
  </section>;
}
