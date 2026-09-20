import { Link } from 'react-router-dom';

export function PlannedPage({title}: {title: string}) {
  return <section className="card space-y-4"><h1 className="text-2xl font-bold capitalize">{title}</h1>
    <p>This module is planned and is not available yet.</p>
    <p>You can use the Video Creator, Task Scheduler, Social Media links and your activity log.</p>
    <Link className="text-blue-700 underline" to="/">Back to dashboard</Link>
  </section>;
}

export function NotFoundPage() {
  return <section className="card space-y-4"><h1 className="text-2xl font-bold">Page not found</h1>
    <p>This page does not exist.</p>
    <Link className="text-blue-700 underline" to="/">Back to dashboard</Link>
  </section>;
}
