import { Link } from 'react-router-dom';
import { Film, Clock, Share2 } from 'lucide-react';
import { Card } from '../components/common/Card';

const shortcuts = [
  { to: '/video-creator', title: 'Video Creator', text: 'Generate Tamil History, Indian Law, How to Make Money, Tamil News, Thirukkural, Spoken English, Amazing Facts, Health Tips, Life Lessons and Kids Learning, then download the MP4.', icon: Film },
  { to: '/scheduler', title: 'Task Scheduler', text: 'Schedule daily, weekly or monthly video generation.', icon: Clock },
  { to: '/social', title: 'Social Media', text: 'Open YouTube, Facebook and Instagram to upload your videos.', icon: Share2 },
];

export default function Dashboard() {
  return <div className="space-y-6">
    <div><h1 className="text-3xl font-bold">Creator dashboard</h1><p className="text-gray-500 mt-2">Your personal video workspace</p></div>
    <div className="grid md:grid-cols-3 gap-4">
      {shortcuts.map(({to, title, text, icon: Icon}) => <Link key={to} to={to} className="card block hover:border-primary-500 transition-colors">
        <Icon className="text-primary-600 mb-3" aria-hidden="true" />
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="text-sm text-gray-500 mt-1">{text}</p>
      </Link>)}
    </div>
    <Card title="Publishing status"><p>Videos are generated daily and posted automatically to <b>YouTube</b>. <b>Facebook</b> and <b>Instagram</b> post automatically too, but need a one-time connect on the PC (desktop shortcut <b>“Connect-Facebook-Instagram”</b>). Until then, you can always download the MP4 and upload it from each platform's website.</p></Card>
  </div>;
}
