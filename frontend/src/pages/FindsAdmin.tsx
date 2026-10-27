import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  BarChart3, Bot, CheckCircle2, ClipboardList, Clock, ExternalLink, Eye, EyeOff,
  FileUp, Film, IndianRupee, Link2, MousePointerClick, Package, Play, Plus,
  RefreshCw, ShieldCheck, ShoppingBag, Sparkles, Trash2, TrendingUp, Upload,
  Zap, type LucideIcon,
} from 'lucide-react';
import clsx from 'clsx';
import api, { Envelope, errorMessage } from '../services/apiClient';

interface AdminProduct {
  id: string;
  external_id?: string;
  title: string;
  title_ta: string;
  category: string;
  price: number;
  mrp: number;
  rating: number;
  orders_count: number;
  return_risk: string;
  commission_percent: number;
  affiliate_url: string;
  image_url: string;
  features: string[];
  cautions: string[];
  score: number;
  active: boolean;
  demo: boolean;
  clicks: number;
  orders: number;
  commission_earned: number;
  discount_percent: number;
  buy_url: string;
}

interface FindsAnalytics {
  products: number;
  active_products: number;
  clicks: number;
  clicks_7d: number;
  clicks_period: number;
  clicks_by_platform: { platform: string; clicks: number }[];
  orders: number;
  orders_period: number;
  sales: number;
  sales_all: number;
  commission: number;
  commission_all: number;
  conversion_percent: number;
  statuses: Record<string, number>;
  top_products: { id: string; title: string; orders: number; commission: number; clicks: number }[];
  daily: { date: string; clicks: number; orders: number; commission: number }[];
  period_days: number;
}

interface FindsOrder {
  id: string;
  order_id: string;
  product_id: string | null;
  product_title: string | null;
  platform: string;
  sale_amount: number;
  commission: number;
  status: string;
  ordered_at: string | null;
}

interface AgentStage {
  status: string;
  at: string;
  detail: string;
}

interface AgentRun {
  id: string;
  day: string;
  product_id: string;
  status: string;
  stage: string;
  approved: boolean;
  job_id?: string | null;
  stages: Record<string, AgentStage>;
  note: string;
  created_at: string;
  updated_at: string;
}

interface AgentMonetization {
  ready: boolean;
  issues: string[];
  warnings: string[];
  demo: boolean;
  commission_percent: number;
  host: string;
  network?: string;
  network_label?: string;
  wrapper?: boolean;
}

interface AgentProduct extends AdminProduct {
  candidate_score: number;
  monetization: AgentMonetization;
  reason?: string;
  recommended?: boolean;
}

interface AgentStatus {
  day: string;
  at: string;
  config: {
    enabled: boolean;
    auto_prepare: boolean;
    prepare_at: string;
    approval_required: boolean;
    require_affiliate_link: boolean;
    auto_publish: boolean;
    auto_mode: boolean;
    auto_publish_platforms: string[];
    publish_grace_minutes: number;
    max_publish_attempts: number;
    feed_url: string;
    feed_path: string;
    feed_sync_at: string;
    platforms: string[];
  };
  feed: {
    configured: boolean;
    url: string;
    path: string;
    inbox: string;
    inbox_files: string[];
    last_sync: string;
    last_imported: number;
    last_error: string;
    sources: string[];
  };
  run: AgentRun | null;
  product: AgentProduct | null;
  pinned: AgentProduct | null;
  monetization: AgentMonetization;
  metrics: {
    clicks: number; orders: number; sales: number; commission: number;
    all_time_clicks: number; all_time_orders: number; all_time_commission: number;
  };
  job: { id: string | null; status: string | null; message: string | null; auto_render: boolean | null };
  schedule: Record<string, { run_time: string; enabled: boolean }>;
  platforms: {
    platform: string; label: string; posted: boolean; stage_status: string;
    stage_detail: string; run_time: string; enabled: boolean;
  }[];
  blockers: string[];
  recommendations: AgentProduct[];
  readiness: {
    id: string; title: string; title_en: string; category: string; price: number;
    score: number; candidate_score: number; demo: boolean; monetization_ready: boolean;
    issues: string[];
  }[];
  recent_runs: AgentRun[];
  events: { id: number; at: string; event: string; detail: string }[];
  scope: string;
}

type Tab = 'overview' | 'autopilot' | 'products' | 'import' | 'orders';

const TABS: { id: Tab; label: string; icon: LucideIcon }[] = [
  { id: 'overview', label: 'Overview', icon: BarChart3 },
  { id: 'autopilot', label: 'Autopilot', icon: Bot },
  { id: 'products', label: 'Catalogue', icon: Package },
  { id: 'import', label: 'CSV Import', icon: FileUp },
  { id: 'orders', label: 'Orders', icon: ClipboardList },
];

const STAGE_ORDER = ['discover', 'score', 'approve', 'script', 'render', 'youtube', 'facebook', 'instagram', 'track'];
const STAGE_LABEL: Record<string, string> = {
  discover: 'Discover', score: 'Score', approve: 'Approve', script: 'Script',
  render: 'Render', youtube: 'YouTube', facebook: 'Facebook', instagram: 'Instagram',
  track: 'Track',
};

const stageTone = (status: string) => {
  if (status === 'done') return 'bg-emerald-100 text-emerald-700 border-emerald-200';
  if (status === 'running') return 'bg-sky-100 text-sky-700 border-sky-200';
  if (status === 'failed') return 'bg-red-100 text-red-700 border-red-200';
  if (status === 'blocked') return 'bg-amber-100 text-amber-700 border-amber-200';
  return 'bg-slate-100 text-slate-500 border-slate-200';
};

const runTone = (status: string) => {
  if (status === 'live') return 'bg-emerald-100 text-emerald-700';
  if (status === 'partial' || status === 'ready_to_publish' || status === 'ready') return 'bg-sky-100 text-sky-700';
  if (status === 'failed') return 'bg-red-100 text-red-700';
  if (status === 'awaiting_approval') return 'bg-amber-100 text-amber-700';
  return 'bg-slate-100 text-slate-600';
};

const EMPTY_FORM = {
  id: '', external_id: '', title: '', title_ta: '', category: 'General',
  price: 0, mrp: 0, rating: 0, orders_count: 0, commission_percent: 0,
  return_risk: 'low', affiliate_url: '', image_url: '', features: '',
  cautions: '', active: true, demo: false,
};

const inr = (value: number) => '₹' + Math.round(Number(value) || 0).toLocaleString('en-IN');

function Stat({ label, value, hint, icon }: { label: string; value: string; hint?: string; icon: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="flex items-center gap-1.5 text-xs font-semibold text-slate-500">{icon}{label}</p>
      <p className="mt-1 text-2xl font-extrabold text-slate-900">{value}</p>
      {hint && <p className="mt-1 text-[11px] text-slate-500">{hint}</p>}
    </div>
  );
}

export default function FindsAdmin() {
  const [tab, setTab] = useState<Tab>('overview');
  const [products, setProducts] = useState<AdminProduct[]>([]);
  const [analytics, setAnalytics] = useState<FindsAnalytics | null>(null);
  const [orders, setOrders] = useState<FindsOrder[]>([]);
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [productCsv, setProductCsv] = useState('');
  const [orderCsv, setOrderCsv] = useState('');
  const [importErrors, setImportErrors] = useState<{ line: number; error: string }[]>([]);
  const [agent, setAgent] = useState<AgentStatus | null>(null);
  const [agentDay, setAgentDay] = useState('');
  const [agentBusy, setAgentBusy] = useState(false);
  const [agentLinks, setAgentLinks] = useState('');
  const [agentReal, setAgentReal] = useState(false);
  const [agentCategory, setAgentCategory] = useState('General');
  const [feedUrl, setFeedUrl] = useState('');
  const [feedPath, setFeedPath] = useState('');
  const [feedTouched, setFeedTouched] = useState(false);

  const notify = (message: string) => { setOk(message); setTimeout(() => setOk(''), 5000); };
  const fail = (err: unknown) => setError(errorMessage(err));

  const loadAgent = () => api.get<Envelope<AgentStatus>>('/finds/admin/agent/status')
    .then(response => {
      setAgent(response.data.data);
      setAgentDay(current => current || response.data.data.day);
      if (!feedTouched) {
        setFeedUrl(response.data.data.config.feed_url || '');
        setFeedPath(response.data.data.config.feed_path || '');
      }
    })
    .catch(fail);

  const load = () => {
    api.get<Envelope<{ products: AdminProduct[] }>>('/finds/admin/products')
      .then(response => setProducts(response.data.data.products || [])).catch(fail);
    api.get<Envelope<FindsAnalytics>>('/finds/admin/analytics?days=30')
      .then(response => setAnalytics(response.data.data)).catch(fail);
    api.get<Envelope<FindsOrder[]>>('/finds/admin/orders?limit=100')
      .then(response => setOrders(response.data.data || [])).catch(() => {});
    void loadAgent();
  };
  useEffect(() => { load(); }, []);

  async function agentAction(action: () => Promise<unknown>, message: string) {
    setAgentBusy(true); setError(''); setOk('');
    try {
      await action();
      notify(message);
      await loadAgent();
      load();
    } catch (err) { fail(err); } finally { setAgentBusy(false); }
  }

  const agentPrepare = (productId?: string) => agentAction(
    () => api.post('/finds/admin/agent/prepare', { day: agentDay, force: true, product_id: productId || undefined }),
    productId ? 'Product pinned for the selected day.' : 'Autopilot auto-picked the best product.');

  const agentApprove = (approved: boolean) => {
    if (!agent?.run) return;
    return agentAction(
      () => api.post('/finds/admin/agent/approve', { run_id: agent.run!.id, approved }),
      approved ? 'Product approved.' : 'Approval revoked.');
  };

  const agentPublish = (platform?: string) => {
    if (!agent?.run) return;
    return agentAction(
      () => api.post('/finds/admin/agent/publish', { run_id: agent.run!.id, platform }),
      platform ? `${platform} upload started.` : 'Next upload started.');
  };

  const agentTick = () => agentAction(
    () => api.post('/finds/admin/agent/tick'), 'Autopilot pass completed.');

  const agentConfig = (patch: Partial<AgentStatus['config']>) => agentAction(
    () => api.post('/finds/admin/agent/config', patch), 'Autopilot settings saved.');

  const toggleAutoPlatform = (platform: string) => {
    const current = agent?.config.auto_publish_platforms || [];
    const next = current.includes(platform)
      ? current.filter(item => item !== platform)
      : [...current, platform];
    void agentConfig({ auto_publish_platforms: next.length ? next : ['instagram'] });
  };

  const saveFeed = (sync: boolean) => agentAction(
    async () => {
      await api.post('/finds/admin/agent/config', {
        feed_url: feedUrl.trim(), feed_path: feedPath.trim(),
      });
      if (sync) await api.post('/finds/admin/agent/feed/sync');
      setFeedTouched(false);
    },
    sync ? 'Feed saved and synced.' : 'Feed settings saved.');

  const syncFeedNow = () => agentAction(
    () => api.post('/finds/admin/agent/feed/sync'), 'Feed sync completed.');

  const agentImport = () => agentAction(
    () => api.post('/finds/admin/agent/links', {
      links: agentLinks, real: agentReal, category: agentCategory || 'General',
    }).then(() => setAgentLinks('')),
    'Meesho links imported. Review the new products below.');

  const demos = products.filter(product => product.demo).length;

  async function saveProduct() {
    setBusy(true); setError(''); setOk('');
    try {
      const payload = {
        ...form,
        id: form.id || undefined,
        external_id: form.external_id.trim() || undefined,
        title: form.title.trim(),
        title_ta: form.title_ta.trim(),
        category: form.category.trim() || 'General',
        price: Number(form.price) || 0,
        mrp: Number(form.mrp) || 0,
        rating: Number(form.rating) || 0,
        orders_count: Number(form.orders_count) || 0,
        commission_percent: Number(form.commission_percent) || 0,
        affiliate_url: form.affiliate_url.trim(),
        image_url: form.image_url.trim(),
        features: form.features.split(/\n|\|/).map(value => value.trim()).filter(Boolean),
        cautions: form.cautions.split(/\n|\|/).map(value => value.trim()).filter(Boolean),
      };
      await api.post<Envelope<AdminProduct>>('/finds/admin/products', payload);
      notify(form.id ? 'Product updated.' : 'Product added to the catalogue.');
      setForm(EMPTY_FORM);
      load();
    } catch (err) { fail(err); } finally { setBusy(false); }
  }

  async function toggleProduct(product: AdminProduct) {
    try {
      await api.post(`/finds/admin/products/${product.id}/toggle`, { active: !product.active });
      notify(product.active ? 'Product hidden from the public page.' : 'Product is now live.');
      load();
    } catch (err) { fail(err); }
  }

  async function removeProduct(product: AdminProduct) {
    if (!window.confirm(`Delete "${product.title}" from the catalogue? Clicks and orders stay in analytics.`)) return;
    try {
      await api.delete(`/finds/admin/products/${product.id}`);
      notify('Product deleted.');
      load();
    } catch (err) { fail(err); }
  }

  async function seedDemo() {
    setBusy(true); setError('');
    try {
      const response = await api.post<Envelope<{ seeded: number }>>('/finds/admin/seed-demo');
      notify(`${response.data.data.seeded} demo product(s) ready. They are marked SAMPLE.`);
      load();
    } catch (err) { fail(err); } finally { setBusy(false); }
  }

  async function importCsv(kind: 'products' | 'orders') {
    setBusy(true); setError(''); setOk(''); setImportErrors([]);
    try {
      const endpoint = kind === 'products' ? '/finds/admin/import' : '/finds/admin/orders/import';
      const csv = kind === 'products' ? productCsv : orderCsv;
      const response = await api.post<Envelope<{ imported: number; errors: { line: number; error: string }[]; error_count: number }>>(
        endpoint, { csv });
      const data = response.data.data;
      notify(`Imported ${data.imported} row(s).`);
      setImportErrors(data.errors || []);
      if (kind === 'products') setProductCsv(''); else setOrderCsv('');
      load();
    } catch (err) { fail(err); } finally { setBusy(false); }
  }

  async function readFile(file: File | null, target: 'products' | 'orders') {
    if (!file) return;
    const text = await file.text();
    if (target === 'products') setProductCsv(text); else setOrderCsv(text);
    notify(`${file.name} loaded. Review the rows, then import.`);
  }

  const maxDaily = useMemo(() => Math.max(1, ...(analytics?.daily || []).map(day => Math.max(day.clicks, day.orders))), [analytics]);
  const directLink = `${window.location.origin}/finds`;

  return (
    <section className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-extrabold">Meesho Finds Admin</h1>
          <p className="mt-1 text-sm text-slate-500">Tamil Budget Finds catalogue, clicks, orders and daily video controls.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a href="/finds" target="_blank" rel="noopener noreferrer"
             className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
            <ExternalLink size={15} /> Public page
          </a>
          <Link to="/video-creator"
                className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800">
            <Film size={15} /> Video Creator
          </Link>
          <button onClick={load} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
            <RefreshCw size={15} /> Refresh
          </button>
        </div>
      </div>

      <div className="flex gap-2 overflow-x-auto">
        {TABS.map(item => (
          <button key={item.id} onClick={() => setTab(item.id)}
                  className={clsx('flex items-center gap-1.5 whitespace-nowrap rounded-lg border px-3 py-1.5 text-sm',
                    tab === item.id ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-200 bg-white text-slate-700')}>
            <item.icon size={14} /> {item.label}
          </button>
        ))}
      </div>

      {error && <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {ok && <p role="status" className="rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">{ok}</p>}

      {tab === 'overview' && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Active products" value={String(analytics?.active_products ?? products.filter(p => p.active).length)}
                  hint={`${products.length} total · ${demos} demo`} icon={<ShoppingBag size={14} />} />
            <Stat label="Clicks (30 days)" value={String(analytics?.clicks_period ?? 0)}
                  hint={`${analytics?.clicks_7d ?? 0} in the last 7 days`} icon={<MousePointerClick size={14} />} />
            <Stat label="Orders (30 days)" value={String(analytics?.orders_period ?? 0)}
                  hint={`${analytics?.conversion_percent ?? 0}% click → order`} icon={<ClipboardList size={14} />} />
            <Stat label="Commission (30 days)" value={inr(analytics?.commission ?? 0)}
                  hint={`${inr(analytics?.sales ?? 0)} sales value`} icon={<IndianRupee size={14} />} />
          </div>

          <div className="grid gap-4 lg:grid-cols-[1.45fr_.55fr]">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between">
                <h2 className="flex items-center gap-2 font-bold"><TrendingUp size={17} /> Last 14 days</h2>
                <span className="text-xs text-slate-500">Clicks / orders</span>
              </div>
              <div className="mt-5 flex h-48 items-end gap-1.5">
                {(analytics?.daily || []).map(day => (
                  <div key={day.date} className="group flex h-full flex-1 flex-col items-center justify-end gap-1">
                    <div className="flex h-full w-full items-end justify-center gap-0.5">
                      <div title={`${day.clicks} clicks`} className="w-1/3 rounded-t bg-sky-400/80" style={{height: `${Math.max(2, day.clicks / maxDaily * 100)}%`}} />
                      <div title={`${day.orders} orders`} className="w-1/3 rounded-t bg-emerald-500/80" style={{height: `${Math.max(2, day.orders / maxDaily * 100)}%`}} />
                    </div>
                    <span className="text-[9px] text-slate-400">{day.date.slice(5)}</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex gap-4 text-xs text-slate-500">
                <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-sky-400" /> Clicks</span>
                <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500" /> Orders</span>
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <h2 className="flex items-center gap-2 font-bold"><MousePointerClick size={17} /> Clicks by platform</h2>
                <div className="mt-3 space-y-2">
                  {(analytics?.clicks_by_platform || []).length === 0 && <p className="text-sm text-slate-400">No clicks yet. Share the public page or video link.</p>}
                  {(analytics?.clicks_by_platform || []).map(item => (
                    <div key={item.platform} className="flex items-center justify-between text-sm">
                      <span className="capitalize text-slate-600">{item.platform}</span>
                      <span className="font-bold">{item.clicks}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <h2 className="flex items-center gap-2 font-bold"><Sparkles size={17} /> Daily automation</h2>
                <p className="mt-2 text-xs leading-5 text-slate-500">
                  Video 19:00 · YouTube 19:30 · Facebook 19:45 · Instagram 20:00 (IST).
                  Manage it in the <Link to="/scheduler" className="font-semibold text-blue-700 underline">Task Scheduler</Link>.
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="flex items-center gap-2 font-bold"><BarChart3 size={17} /> Top products</h2>
            {(analytics?.top_products || []).length === 0 ? (
              <p className="mt-2 text-sm text-slate-400">No order data yet. Import a Meesho orders CSV after your first sale.</p>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b text-left text-xs uppercase tracking-wide text-slate-500"><th className="py-2">Product</th><th>Clicks</th><th>Orders</th><th>Commission</th></tr></thead>
                  <tbody>{analytics?.top_products.map(item => (
                    <tr key={item.id} className="border-b border-slate-100 last:border-0">
                      <td className="py-2 font-medium">{item.title}</td>
                      <td>{item.clicks}</td><td>{item.orders}</td><td>{inr(item.commission)}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'autopilot' && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h2 className="flex items-center gap-2 text-lg font-bold"><Bot size={19} /> Meesho Autopilot</h2>
                <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-500">
                  Selects and pins the product at 18:00, then the existing 19:00 render and
                  19:30 / 19:45 / 20:00 upload schedules publish it. This panel observes the real
                  jobs and uploader logs — it never creates fake clicks or engagement.
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                  <span className={clsx('rounded-full px-2.5 py-1 font-bold capitalize', runTone(agent?.run?.status || 'planned'))}>
                    {(agent?.run?.status || 'no run').replace(/_/g, ' ')}
                  </span>
                  {agent?.run && <span className="text-slate-500">Stage: <strong>{STAGE_LABEL[agent.run.stage] || agent.run.stage}</strong></span>}
                  {agent?.job?.status && <span className="text-slate-500">Video job: <strong>{agent.job.status}</strong></span>}
                  <span className="text-slate-400">{agent?.at ? new Date(agent.at).toLocaleString('en-IN') : ''}</span>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <label className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-semibold text-slate-600">
                  <Clock size={13} /> Day
                  <input type="date" value={agentDay} min={agent?.day} onChange={event => setAgentDay(event.target.value)}
                         className="bg-transparent text-xs outline-none" />
                </label>
                <button onClick={() => void agentPrepare()} disabled={agentBusy || !agent}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-orange-500 px-3 py-2 text-sm font-bold text-white hover:bg-orange-600 disabled:opacity-60">
                  <Sparkles size={15} /> Auto-pick
                </button>
                <button onClick={() => void agentTick()} disabled={agentBusy}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60">
                  <Zap size={15} /> Run pass
                </button>
                <button onClick={() => void loadAgent()} disabled={agentBusy}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60">
                  <RefreshCw size={15} /> Refresh
                </button>
              </div>
            </div>
            {(agent?.blockers || []).length > 0 && (
              <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                <p className="font-bold">Needs attention</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-5">
                  {agent?.blockers.map(item => <li key={item}>{item}</li>)}
                </ul>
              </div>
            )}
          </div>

          <div className="grid gap-4 lg:grid-cols-[1.05fr_.95fr]">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between gap-2">
                <h2 className="flex items-center gap-2 font-bold"><ShoppingBag size={17} /> Selected product</h2>
                {agent?.product?.demo && <span className="rounded bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-700">SAMPLE / NO COMMISSION</span>}
              </div>
              {agent?.product ? (
                <div className="mt-3 flex gap-3">
                  <div className="h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-slate-100">
                    {agent.product.image_url
                      ? <img src={agent.product.image_url} alt="" className="h-full w-full object-contain" />
                      : <div className="grid h-full w-full place-items-center text-3xl">🛍️</div>}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-bold text-slate-900">{agent.product.title_ta || agent.product.title}</p>
                    <p className="mt-0.5 truncate text-xs text-slate-500">{agent.product.title}</p>
                    <p className="mt-1 text-sm font-extrabold text-slate-800">
                      {inr(agent.product.price)} <span className="text-xs font-normal text-slate-400 line-through">{inr(agent.product.mrp)}</span>
                      <span className="ml-2 text-xs font-semibold text-emerald-700">score {agent.product.candidate_score}</span>
                    </p>
                    <p className="mt-1 text-[11px] text-slate-500">
                      {agent.product.category} · {agent.product.rating}★ · {agent.product.orders_count} orders ·
                      {' '}{agent.product.commission_percent}% commission
                      {agent.monetization.network_label ? ` · ${agent.monetization.network_label}` : ''}
                    </p>
                    {(agent.monetization.issues || []).length > 0 && (
                      <ul className="mt-2 space-y-0.5 text-[11px] font-medium text-amber-700">
                        {agent.monetization.issues.map(item => <li key={item}>• {item}</li>)}
                      </ul>
                    )}
                    {(agent.monetization.warnings || []).length > 0 && (
                      <ul className="mt-1 space-y-0.5 text-[11px] text-slate-500">
                        {agent.monetization.warnings.map(item => <li key={item}>• {item}</li>)}
                      </ul>
                    )}
                  </div>
                </div>
              ) : (
                <div className="mt-6 rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
                  No product selected yet. Use <strong>Auto-pick</strong> or pin a candidate below.
                </div>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                {agent?.run && !agent.run.approved && (
                  <button onClick={() => void agentApprove(true)} disabled={agentBusy}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-bold text-white disabled:opacity-60">
                    <CheckCircle2 size={15} /> Approve product
                  </button>
                )}
                {agent?.run?.approved && (
                  <span className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-700">
                    <CheckCircle2 size={14} /> Approved
                  </span>
                )}
                {agent?.pinned && <span className="inline-flex items-center gap-1.5 rounded-lg bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-700">
                  <ShieldCheck size={14} /> Pinned for {agent.day}
                </span>}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h2 className="flex items-center gap-2 font-bold"><TrendingUp size={17} /> Pipeline</h2>
              <p className="mt-1 text-[11px] text-slate-500">Live status from the real video job and uploader logs.</p>
              <div className="mt-3 space-y-1.5">
                {STAGE_ORDER.map(stage => {
                  const item = agent?.run?.stages?.[stage];
                  const status = item?.status || 'pending';
                  return (
                    <div key={stage} className="flex items-start gap-2">
                      <span className={clsx('mt-0.5 w-20 shrink-0 rounded-full border px-2 py-0.5 text-center text-[10px] font-bold capitalize', stageTone(status))}>
                        {status}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-semibold text-slate-700">{STAGE_LABEL[stage]}</p>
                        <p className="truncate text-[10px] text-slate-400" title={item?.detail || ''}>{item?.detail || 'Waiting…'}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-4">
            <Stat label="Clicks today" value={String(agent?.metrics.clicks ?? 0)} hint={`${agent?.metrics.all_time_clicks ?? 0} all time`} icon={<MousePointerClick size={14} />} />
            <Stat label="Orders today" value={String(agent?.metrics.orders ?? 0)} hint={`${agent?.metrics.all_time_orders ?? 0} all time`} icon={<ClipboardList size={14} />} />
            <Stat label="Commission today" value={inr(agent?.metrics.commission ?? 0)} hint={`${inr(agent?.metrics.all_time_commission ?? 0)} all time`} icon={<IndianRupee size={14} />} />
            <Stat label="Conversion" value={`${agent && agent.metrics.clicks ? ((agent.metrics.orders / agent.metrics.clicks) * 100).toFixed(1) : '0.0'}%`} hint="click → order today" icon={<BarChart3 size={14} />} />
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="flex items-center gap-2 font-bold"><Play size={17} /> Publishing</h2>
              <span className="text-xs text-slate-500">Scheduled times are IST · the existing upload schedules remain the executor</span>
            </div>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2">Platform</th><th>Schedule</th><th>Status</th><th>Detail</th><th className="text-right">Action</th>
                </tr></thead>
                <tbody>{ (agent?.platforms || []).map(item => (
                  <tr key={item.platform} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 font-semibold">{item.label}</td>
                    <td className="text-xs text-slate-500">{item.run_time} IST {item.enabled ? '' : '(paused)'}</td>
                    <td>
                      <span className={clsx('rounded-full px-2 py-0.5 text-[11px] font-bold', item.posted ? 'bg-emerald-100 text-emerald-700' : item.stage_status === 'running' ? 'bg-sky-100 text-sky-700' : 'bg-slate-100 text-slate-500')}>
                        {item.posted ? 'posted' : item.stage_status}
                      </span>
                    </td>
                    <td className="max-w-[280px] truncate text-xs text-slate-500" title={item.stage_detail}>{item.stage_detail || '—'}</td>
                    <td className="text-right">
                      <button onClick={() => void agentPublish(item.platform)}
                              disabled={agentBusy || !agent?.run || item.posted || agent?.job?.status !== 'complete'}
                              className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40">
                        {item.posted ? 'Done' : 'Post now'}
                      </button>
                    </td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </div>

          <div className={clsx('rounded-xl border p-4', agent?.config.auto_mode ? 'border-emerald-300 bg-emerald-50/50' : 'border-slate-200 bg-white')}>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="flex items-center gap-2 font-bold"><Zap size={17} /> Zero-touch mode</h2>
                <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-600">
                  Feed → auto-pick → 19:00 render → the normal 19:30/19:45/20:00 schedules post.
                  If a schedule fails, the Autopilot retries the missing Instagram/Facebook post after the grace window.
                  No clicks, no fake engagement. A real affiliate link is still required for commission.
                </p>
              </div>
              <label className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-bold">
                <input type="checkbox" checked={!!agent?.config.auto_mode}
                       onChange={event => void agentConfig({ auto_mode: event.target.checked })} />
                Full autonomy
              </label>
            </div>

            <div className="mt-3 grid gap-3 lg:grid-cols-[1.15fr_.85fr]">
              <div className="rounded-lg border border-slate-200 bg-white p-3">
                <p className="text-xs font-bold text-slate-700">Product feed</p>
                <p className="mt-1 text-[11px] leading-5 text-slate-500">
                  Paste a CSV/link-list URL (Google Sheets "Publish to web", network export) or a local CSV path.
                  The agent syncs once a day at {agent?.config.feed_sync_at || '06:00'} IST and is idempotent.
                </p>
                <input value={feedUrl} onChange={event => { setFeedTouched(true); setFeedUrl(event.target.value); }}
                       placeholder="https://docs.google.com/spreadsheets/.../pub?output=csv"
                       className="mt-2 w-full rounded border p-2 text-xs" />
                <input value={feedPath} onChange={event => { setFeedTouched(true); setFeedPath(event.target.value); }}
                       placeholder={`Optional local file/folder (default: ${agent?.feed?.inbox || 'storage/finds/feed'})`}
                       className="mt-2 w-full rounded border p-2 text-xs" />
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <button onClick={() => void saveFeed(true)} disabled={agentBusy}
                          className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white disabled:opacity-60">
                    Save & sync now
                  </button>
                  <button onClick={() => void syncFeedNow()} disabled={agentBusy}
                          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-60">
                    <RefreshCw size={12} className="mr-1 inline" /> Sync feed
                  </button>
                  <span className="text-[11px] text-slate-500">
                    {agent?.feed?.last_sync ? `Last sync ${new Date(agent.feed.last_sync).toLocaleString('en-IN')}` : 'Not synced yet'}
                    {agent?.feed?.last_imported ? ` · ${agent.feed.last_imported} imported` : ''}
                  </span>
                </div>
                {agent?.feed?.last_error && <p className="mt-1 text-[11px] font-medium text-red-600">{agent.feed.last_error}</p>}
                <p className="mt-2 break-all text-[10px] text-slate-400">
                  Inbox: {agent?.feed?.inbox || 'storage/finds/feed'}
                  {agent?.feed?.inbox_files?.length ? ` · ${agent.feed.inbox_files.join(', ')}` : ' · empty'}
                </p>
                <p className="mt-1 text-[10px] leading-4 text-slate-400">
                  Supported: Meesho · Amazon · Flipkart · Myntra · AJIO · Tata CLiQ · Snapdeal ·
                  EarnKaro · Cuelinks · INRDeals · vCommission · Admitad · Impact
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-700">
                <p className="text-xs font-bold text-slate-700">Autonomous publishing</p>
                <label className="mt-2 flex items-center justify-between gap-3">
                  <span>Instagram retry</span>
                  <input type="checkbox" checked={(agent?.config.auto_publish_platforms || []).includes('instagram')}
                         onChange={() => toggleAutoPlatform('instagram')} />
                </label>
                <label className="mt-1 flex items-center justify-between gap-3">
                  <span>Facebook retry</span>
                  <input type="checkbox" checked={(agent?.config.auto_publish_platforms || []).includes('facebook')}
                         onChange={() => toggleAutoPlatform('facebook')} />
                </label>
                <label className="mt-1 flex items-center justify-between gap-3">
                  <span>YouTube retry</span>
                  <input type="checkbox" checked={(agent?.config.auto_publish_platforms || []).includes('youtube')}
                         onChange={() => toggleAutoPlatform('youtube')} />
                </label>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                  <label className="space-y-1">
                    <span className="text-[11px] text-slate-500">Grace (min)</span>
                    <input key={agent?.config.publish_grace_minutes} type="number" min={0} max={180}
                           defaultValue={agent?.config.publish_grace_minutes ?? 20}
                           onBlur={event => void agentConfig({ publish_grace_minutes: Number(event.target.value) })}
                           className="w-full rounded border px-2 py-1" />
                  </label>
                  <label className="space-y-1">
                    <span className="text-[11px] text-slate-500">Max attempts</span>
                    <input key={agent?.config.max_publish_attempts} type="number" min={1} max={10}
                           defaultValue={agent?.config.max_publish_attempts ?? 2}
                           onBlur={event => void agentConfig({ max_publish_attempts: Number(event.target.value) })}
                           className="w-full rounded border px-2 py-1" />
                  </label>
                </div>
                <p className="mt-2 text-[10px] leading-4 text-slate-500">
                  YouTube retries should stay off until the channel verification is complete.
                </p>
              </div>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h2 className="flex items-center gap-2 font-bold"><ShieldCheck size={17} /> Automation settings</h2>
              <div className="mt-3 space-y-2 text-sm text-slate-700">
                <label className="flex items-center justify-between gap-3">
                  <span>Autopilot enabled</span>
                  <input type="checkbox" checked={!!agent?.config.enabled} onChange={event => void agentConfig({ enabled: event.target.checked })} />
                </label>
                <label className="flex items-center justify-between gap-3">
                  <span>Auto-select the product</span>
                  <input type="checkbox" checked={!!agent?.config.auto_prepare} onChange={event => void agentConfig({ auto_prepare: event.target.checked })} />
                </label>
                <label className="flex items-center justify-between gap-3">
                  <span>Require owner approval</span>
                  <input type="checkbox" checked={!!agent?.config.approval_required} onChange={event => void agentConfig({ approval_required: event.target.checked })} />
                </label>
                <label className="flex items-center justify-between gap-3">
                  <span>Block demo links from publishing</span>
                  <input type="checkbox" checked={!!agent?.config.require_affiliate_link} onChange={event => void agentConfig({ require_affiliate_link: event.target.checked })} />
                </label>
                <label className="flex items-center justify-between gap-3">
                  <span>Auto-publish missing platforms</span>
                  <input type="checkbox" checked={!!agent?.config.auto_publish} onChange={event => void agentConfig({ auto_publish: event.target.checked })} />
                </label>
                <label className="flex items-center justify-between gap-3">
                  <span>Select product at</span>
                  <input key={agent?.config.prepare_at} type="time" defaultValue={agent?.config.prepare_at || '18:00'}
                         onBlur={event => void agentConfig({ prepare_at: event.target.value })}
                         className="rounded border px-2 py-1 text-sm" />
                </label>
                <p className="pt-1 text-[11px] leading-5 text-slate-500">
                  The 19:30/19:45/20:00 schedules still post first. Auto-publish waits for the grace
                  window and retries only the platforms that are still missing, so it does not duplicate a post.
                </p>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h2 className="flex items-center gap-2 font-bold"><Link2 size={17} /> Add affiliate links</h2>
              <p className="mt-1 text-[11px] leading-5 text-slate-500">
                One product per line: <code>Title | https://... | price | MRP | category | commission %</code>.
                Meesho, Amazon, Flipkart, Myntra, AJIO, Tata CLiQ, Snapdeal, EarnKaro, Cuelinks,
                INRDeals and vCommission are recognised. Untracked product URLs stay marked SAMPLE.
              </p>
              <textarea value={agentLinks} onChange={event => setAgentLinks(event.target.value)} rows={5}
                        placeholder="Steel bottle | https://www.meesho.com/... | 299 | 699 | Kitchen"
                        className="mt-2 w-full rounded border p-2 font-mono text-xs" />
              <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-600">
                <label className="inline-flex items-center gap-1.5">
                  <input type="checkbox" checked={agentReal} onChange={event => setAgentReal(event.target.checked)} />
                  Mark as real affiliate links
                </label>
                <input value={agentCategory} onChange={event => setAgentCategory(event.target.value)}
                       placeholder="Default category" className="rounded border px-2 py-1" />
              </div>
              <button onClick={() => void agentImport()} disabled={agentBusy || !agentLinks.trim()}
                      className="mt-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-60">
                Import links
              </button>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between gap-2">
              <h2 className="flex items-center gap-2 font-bold"><Sparkles size={17} /> Next product candidates</h2>
              <span className="text-xs text-slate-500">Pin before 19:00 · score + past performance − recent use</span>
            </div>
            <div className="mt-3 space-y-2">
              {(agent?.recommendations || []).map(item => (
                <div key={item.id} className="flex items-center gap-3 rounded-lg border border-slate-100 p-2">
                  <div className="h-12 w-12 shrink-0 overflow-hidden rounded-lg bg-slate-100">
                    {item.image_url ? <img src={item.image_url} alt="" className="h-full w-full object-contain" /> : <div className="grid h-full w-full place-items-center">🛍️</div>}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-semibold">{item.title_ta || item.title}</p>
                      {item.demo && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">SAMPLE</span>}
                      {item.recommended && <span className="rounded bg-sky-100 px-1.5 py-0.5 text-[10px] font-bold text-sky-700">TOP PICK</span>}
                    </div>
                    <p className="text-[11px] text-slate-500">{inr(item.price)} · score {item.candidate_score} · {item.reason || item.category}</p>
                    {(item.monetization?.issues || []).length > 0 && (
                      <p className="truncate text-[10px] text-amber-700">{item.monetization.issues.join(' · ')}</p>
                    )}
                  </div>
                  <button onClick={() => void agentPrepare(item.id)}
                          disabled={agentBusy || (!!agent?.job?.id && agentDay === agent.day)}
                          title={agent?.job?.id && agentDay === agent.day ? "Today's video already exists — pick a future day to change the product" : 'Pin this product'}
                          className="shrink-0 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">
                    Pin
                  </button>
                </div>
              ))}
              {(agent?.recommendations || []).length === 0 && <p className="text-sm text-slate-400">No active products yet.</p>}
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-[1.1fr_.9fr]">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h2 className="flex items-center gap-2 font-bold"><Clock size={17} /> Recent runs</h2>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="py-2">Day</th><th>Product</th><th>Status</th><th>Video</th><th>Updated</th>
                  </tr></thead>
                  <tbody>{(agent?.recent_runs || []).map(item => (
                    <tr key={item.id} className="border-b border-slate-100 last:border-0">
                      <td className="py-2 font-mono text-xs">{item.day}</td>
                      <td className="max-w-[220px] truncate text-xs">{item.product_id}</td>
                      <td><span className={clsx('rounded-full px-2 py-0.5 text-[10px] font-bold capitalize', runTone(item.status))}>{item.status.replace(/_/g, ' ')}</span></td>
                      <td className="text-xs text-slate-500">{item.job_id ? item.job_id.slice(0, 8) : '—'}</td>
                      <td className="text-xs text-slate-400">{item.updated_at?.slice(11, 16) || '—'}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h2 className="flex items-center gap-2 font-bold"><Zap size={17} /> Recent events</h2>
              <ul className="mt-3 space-y-2">
                {(agent?.events || []).map(item => (
                  <li key={item.id} className="text-xs">
                    <span className="font-mono text-[10px] text-slate-400">{item.at?.slice(11, 19)}</span>
                    <span className="ml-2 font-semibold text-slate-700">{item.event.replace(/_/g, ' ')}</span>
                    {item.detail && <p className="ml-12 truncate text-[10px] text-slate-500" title={item.detail}>{item.detail}</p>}
                  </li>
                ))}
                {(agent?.events || []).length === 0 && <li className="text-sm text-slate-400">No events yet.</li>}
              </ul>
            </div>
          </div>

          <p className="px-1 text-[11px] leading-5 text-slate-500">{agent?.scope}</p>
        </div>
      )}

      {tab === 'products' && (
        <div className="grid gap-4 lg:grid-cols-[.9fr_1.1fr]">
          <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h2 className="font-bold">{form.id ? 'Edit product' : 'Add a Meesho find'}</h2>
                <p className="mt-1 text-xs text-slate-500">Use the real Meesho affiliate link. The public button redirects through /go and records a click.</p>
              </div>
              <button onClick={seedDemo} disabled={busy}
                      className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-60">
                <Sparkles size={13} /> Seed demo
              </button>
            </div>
            <input value={form.title} onChange={event => setForm(value => ({...value, title: event.target.value}))} placeholder="Product title (English)" className="w-full rounded border p-2 text-sm" />
            <input value={form.title_ta} onChange={event => setForm(value => ({...value, title_ta: event.target.value}))} placeholder="Tamil title (for the video and landing page)" className="w-full rounded border p-2 text-sm" />
            <div className="grid grid-cols-2 gap-2">
              <input value={form.category} onChange={event => setForm(value => ({...value, category: event.target.value}))} placeholder="Category" className="w-full rounded border p-2 text-sm" />
              <select value={form.return_risk} onChange={event => setForm(value => ({...value, return_risk: event.target.value}))} className="w-full rounded border bg-white p-2 text-sm">
                <option value="low">Low return risk</option><option value="medium">Medium return risk</option><option value="high">High return risk</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input type="number" value={form.price || ''} onChange={event => setForm(value => ({...value, price: +event.target.value}))} placeholder="Selling price ₹" className="w-full rounded border p-2 text-sm" />
              <input type="number" value={form.mrp || ''} onChange={event => setForm(value => ({...value, mrp: +event.target.value}))} placeholder="MRP ₹" className="w-full rounded border p-2 text-sm" />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <input type="number" step="0.1" max="5" value={form.rating || ''} onChange={event => setForm(value => ({...value, rating: +event.target.value}))} placeholder="Rating" className="w-full rounded border p-2 text-sm" />
              <input type="number" value={form.orders_count || ''} onChange={event => setForm(value => ({...value, orders_count: +event.target.value}))} placeholder="Orders" className="w-full rounded border p-2 text-sm" />
              <input type="number" step="0.1" value={form.commission_percent || ''} onChange={event => setForm(value => ({...value, commission_percent: +event.target.value}))} placeholder="Comm. %" className="w-full rounded border p-2 text-sm" />
            </div>
            <input value={form.affiliate_url} onChange={event => setForm(value => ({...value, affiliate_url: event.target.value}))} placeholder="https://www.meesho.com/... (affiliate link)" className="w-full rounded border p-2 text-sm" />
            <textarea value={form.image_url} onChange={event => setForm(value => ({...value, image_url: event.target.value}))} rows={2} placeholder="Image URL (https://... or data:image/...)" className="w-full rounded border p-2 text-sm" />
            <textarea value={form.features} onChange={event => setForm(value => ({...value, features: event.target.value}))} rows={3} placeholder="Benefits — one per line" className="w-full rounded border p-2 text-sm" />
            <textarea value={form.cautions} onChange={event => setForm(value => ({...value, cautions: event.target.value}))} rows={2} placeholder="Cautions — one per line" className="w-full rounded border p-2 text-sm" />
            <div className="flex flex-wrap gap-4 text-sm text-slate-600">
              <label className="inline-flex items-center gap-2"><input type="checkbox" checked={form.active} onChange={event => setForm(value => ({...value, active: event.target.checked}))} /> Active</label>
              <label className="inline-flex items-center gap-2"><input type="checkbox" checked={form.demo} onChange={event => setForm(value => ({...value, demo: event.target.checked}))} /> Demo / sample</label>
            </div>
            <div className="flex gap-2">
              <button onClick={() => void saveProduct()} disabled={busy || !form.title.trim() || !form.affiliate_url.trim()}
                      className="flex-1 rounded-lg bg-orange-500 py-2.5 font-bold text-white disabled:opacity-60">
                <Plus size={16} className="mr-1 inline" />{form.id ? 'Save changes' : 'Add product'}
              </button>
              {form.id && <button onClick={() => setForm(EMPTY_FORM)} className="rounded-lg border border-slate-200 px-4 text-sm font-semibold text-slate-600">Cancel</button>}
            </div>
          </div>

          <div className="space-y-2">
            {products.map(product => (
              <div key={product.id} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3">
                <div className="h-14 w-14 shrink-0 overflow-hidden rounded-lg bg-slate-100">
                  {product.image_url ? <img src={product.image_url} alt="" className="h-full w-full object-contain" /> : <div className="grid h-full w-full place-items-center text-2xl">🛍️</div>}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="truncate text-sm font-semibold">{product.title}</p>
                    {product.demo && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">SAMPLE</span>}
                    {!product.active && <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-500">HIDDEN</span>}
                  </div>
                  <p className="text-xs text-slate-500">{inr(product.price)} · MRP {inr(product.mrp)} · score {product.score.toFixed(1)} · {product.clicks} clicks · {product.orders} orders</p>
                  <p className="truncate text-[11px] text-slate-400">{product.category}</p>
                </div>
                <button onClick={() => setForm({
                  id: product.id, external_id: product.external_id || '', title: product.title,
                  title_ta: product.title_ta || '', category: product.category, price: product.price,
                  mrp: product.mrp, rating: product.rating, orders_count: product.orders_count,
                  commission_percent: product.commission_percent, return_risk: product.return_risk,
                  affiliate_url: product.affiliate_url, image_url: product.image_url,
                  features: (product.features || []).join('\n'), cautions: (product.cautions || []).join('\n'),
                  active: product.active, demo: product.demo,
                })} className="rounded-lg border p-1.5 text-slate-500" title="Edit">✏️</button>
                <button onClick={() => void toggleProduct(product)} className="rounded-lg border p-1.5" title={product.active ? 'Hide' : 'Show'}>
                  {product.active ? <EyeOff size={14} /> : <Eye size={14} className="text-emerald-600" />}
                </button>
                <button onClick={() => void removeProduct(product)} className="rounded-lg border p-1.5 text-red-500" title="Delete"><Trash2 size={14} /></button>
              </div>
            ))}
            {products.length === 0 && (
              <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-400">
                <ShoppingBag size={34} className="mx-auto text-slate-300" />
                <p className="mt-3">No products yet. Add a Meesho find or load the demo catalogue.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'import' && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="flex items-center gap-2 font-bold"><Upload size={17} /> Import products</h2>
            <p className="text-xs leading-5 text-slate-500">
              CSV headers supported: <code>external_id, title, title_ta, category, price, mrp, rating, orders_count,
              commission_percent, affiliate_url, image_url, features, cautions, return_risk, active, demo</code>.
              Separate features/cautions with <code>|</code>.
            </p>
            <input type="file" accept=".csv,text/csv" onChange={event => void readFile(event.target.files?.[0] || null, 'products')} className="block w-full text-sm" />
            <textarea value={productCsv} onChange={event => setProductCsv(event.target.value)} rows={10}
                      placeholder="Paste product CSV here..." className="w-full rounded border p-2 font-mono text-xs" />
            <button onClick={() => void importCsv('products')} disabled={busy || !productCsv.trim()}
                    className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-60">Import products</button>
          </div>
          <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="flex items-center gap-2 font-bold"><Upload size={17} /> Import orders / commission</h2>
            <p className="text-xs leading-5 text-slate-500">
              CSV headers supported: <code>order_id, product_id, sale_amount, commission, status, ordered_at, platform</code>.
              Use the Meesho order id so repeated imports update, not duplicate.
            </p>
            <input type="file" accept=".csv,text/csv" onChange={event => void readFile(event.target.files?.[0] || null, 'orders')} className="block w-full text-sm" />
            <textarea value={orderCsv} onChange={event => setOrderCsv(event.target.value)} rows={10}
                      placeholder="Paste order CSV here..." className="w-full rounded border p-2 font-mono text-xs" />
            <button onClick={() => void importCsv('orders')} disabled={busy || !orderCsv.trim()}
                    className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-60">Import orders</button>
          </div>
          {importErrors.length > 0 && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 lg:col-span-2">
              <p className="font-bold">Rows that need attention</p>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {importErrors.map(item => <li key={`${item.line}-${item.error}`}>Line {item.line}: {item.error}</li>)}
              </ul>
            </div>
          )}
          <div className="rounded-xl border border-slate-200 bg-white p-4 text-xs leading-5 text-slate-500 lg:col-span-2">
            <strong className="text-slate-700">Quick test:</strong> create a two-line order CSV with
            <code className="mx-1 rounded bg-slate-100 px-1">order_id,product_id,sale_amount,commission,status</code>
            and a demo product id. The overview cards and top-products table will update immediately.
          </div>
        </div>
      )}

      {tab === 'orders' && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 font-bold"><ClipboardList size={17} /> Imported orders</h2>
            <span className="text-xs text-slate-500">{orders.length} shown</span>
          </div>
          {orders.length === 0 ? (
            <div className="mt-6 rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
              No orders yet. Use the CSV Import tab after your first Meesho sale.
            </div>
          ) : (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2">Order</th><th>Product</th><th>Platform</th><th>Sale</th><th>Commission</th><th>Status</th><th>Date</th>
                </tr></thead>
                <tbody>{orders.map(order => (
                  <tr key={order.id} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 font-mono text-xs">{order.order_id}</td>
                    <td>{order.product_title || order.product_id || '—'}</td>
                    <td className="capitalize">{order.platform}</td>
                    <td>{inr(order.sale_amount)}</td><td>{inr(order.commission)}</td>
                    <td><span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold capitalize">{order.status}</span></td>
                    <td className="text-xs text-slate-500">{order.ordered_at?.slice(0, 10) || '—'}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="flex items-center gap-2 font-bold"><CheckCircle2 size={17} /> Launch checklist</h2>
            <p className="mt-1 text-xs text-slate-500">Public URL: <a href="/finds" target="_blank" rel="noopener noreferrer" className="font-semibold text-blue-700 underline">{directLink}</a></p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className={clsx('rounded-full px-2.5 py-1 font-semibold', products.length ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700')}>{products.length ? '✓ products' : 'add products'}</span>
            <span className={clsx('rounded-full px-2.5 py-1 font-semibold', demos === 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700')}>{demos === 0 ? '✓ no demo products' : `${demos} demo product(s)`}</span>
            <span className={clsx('rounded-full px-2.5 py-1 font-semibold', (analytics?.clicks || 0) > 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500')}>{analytics?.clicks || 0} clicks</span>
          </div>
        </div>
      </div>
    </section>
  );
}
