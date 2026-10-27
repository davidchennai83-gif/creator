import { useEffect, useState, type ReactNode } from 'react';
import {
  Plus, Trash2, Eye, EyeOff, ExternalLink, Search, Paperclip, RefreshCw,
  Settings as SettingsIcon, Package, Link2, ClipboardList, Banknote, Truck,
  CheckCircle2, Circle, BarChart3, TrendingUp, MousePointerClick,
} from 'lucide-react';
import api, { Envelope, errorMessage } from '../services/apiClient';
import clsx from 'clsx';
import { StoreProduct, StoreOrder, StoreSettings, StoreReadiness, StoreAnalytics, STATUS_STYLE } from './Store';

const inr = (n: number) => '₹' + n.toLocaleString('en-IN');
const TABS = [
  { id: 'products', label: 'My Products', icon: Package },
  { id: 'affiliate', label: 'Affiliate Deals', icon: Link2 },
  { id: 'orders', label: 'Orders & Delivery', icon: ClipboardList },
  { id: 'earnings', label: 'Earnings', icon: BarChart3 },
  { id: 'settings', label: 'Payment Setup', icon: SettingsIcon },
] as const;

const EMPTY_FORM = {
  id: '', name: '', category: 'Mobiles', price: 0, mrp: 0, stock: 10,
  emoji: '🛍️', tagline: '', highlight: '', features: '', delivery_days: 3,
};

function Check({ ok, label, tab }: { ok: boolean; label: string; tab: () => void }) {
  return (
    <button onClick={tab} className="flex items-center gap-2 text-left hover:bg-slate-50 rounded p-1">
      {ok ? <CheckCircle2 size={16} className="text-emerald-500 shrink-0" /> : <Circle size={16} className="text-slate-300 shrink-0" />}
      <span className={clsx('text-xs', ok ? 'text-slate-700' : 'text-slate-500')}>{label}</span>
    </button>
  );
}

const TONES: Record<string, string> = {
  emerald: 'text-emerald-600', blue: 'text-blue-600', amber: 'text-amber-600', sky: 'text-sky-600',
};
function Stat({ label, value, icon, tone }: { label: string; value: string; icon: ReactNode; tone: keyof typeof TONES }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-3">
      <p className={clsx('flex items-center gap-1 text-xs font-semibold', TONES[tone])}>{icon}{label}</p>
      <p className="text-xl font-extrabold mt-1">{value}</p>
    </div>
  );
}

export default function StoreAdmin() {
  const [tab, setTab] = useState<'products' | 'affiliate' | 'orders' | 'earnings' | 'settings'>('products');
  const [products, setProducts] = useState<StoreProduct[]>([]);
  const [orders, setOrders] = useState<StoreOrder[]>([]);
  const [stats, setStats] = useState<StoreAnalytics | null>(null);
  const [settings, setSettings] = useState<StoreSettings>({ upi_id: '', merchant_name: 'CreatorMart', partner_name: '', partner_phone: '', amazon_tag: '', flipkart_affid: '' });
  const [ready, setReady] = useState<StoreReadiness | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [ok, setOk] = useState('');

  // product form
  const [form, setForm] = useState(EMPTY_FORM);
  // affiliate form
  const [aff, setAff] = useState({ url: '', name: '', price: 0, mrp: 0, category: 'Electronics', platform: '', emoji: '🔗', tagline: '', features: '' });
  const [metaBusy, setMetaBusy] = useState(false);

  const notify = (m: string) => { setOk(m); setTimeout(() => setOk(''), 4000); };
  const fail = (e: unknown) => setError(errorMessage(e));

  const load = () => {
    api.get<Envelope<{ products: StoreProduct[] }>>('/store/admin/products').then(r => setProducts(r.data.data.products)).catch(fail);
    api.get<Envelope<{ orders: StoreOrder[] }>>('/store/admin/orders').then(r => setOrders(r.data.data.orders)).catch(fail);
    api.get<Envelope<StoreSettings>>('/store/settings').then(r => setSettings(r.data.data)).catch(fail);
    api.get<Envelope<StoreReadiness>>('/store/readiness').then(r => setReady(r.data.data)).catch(() => {});
    api.get<Envelope<StoreAnalytics>>('/store/admin/analytics').then(r => setStats(r.data.data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  async function saveProduct(kind: 'own' | 'affiliate') {
    setBusy(true); setError(''); setOk('');
    try {
      const payload: any = {
        id: form.id || undefined,
        kind,
        name: form.name.trim(),
        category: (kind === 'affiliate' ? aff.category : form.category).trim(),
        price: Number(form.price) || 0,
        mrp: Number(form.mrp) || 0,
        stock: Number(form.stock) || 0,
        emoji: form.emoji.trim() || '🛍️',
        tagline: form.tagline.trim(),
        highlight: form.highlight.trim(),
        features: form.features.split(',').map(s => s.trim()).filter(Boolean),
        delivery_days: Number(form.delivery_days) || 3,
        published: true,
      };
      if (kind === 'affiliate') {
        payload.affiliate_url = aff.url.trim();
        payload.platform = aff.platform.trim();
        payload.name = (aff.name || form.name).trim();
        payload.price = Number(aff.price) || Number(form.price) || 0;
        payload.mrp = Number(aff.mrp) || payload.price;
        payload.emoji = aff.emoji || '🔗';
        payload.tagline = aff.tagline;
        payload.features = aff.features.split(',').map(s => s.trim()).filter(Boolean);
      }
      await api.post<Envelope<StoreProduct>>('/store/admin/products', payload);
      notify(kind === 'affiliate' ? 'Affiliate deal published!' : 'Product saved & published.');
      setForm(EMPTY_FORM);
      if (kind === 'affiliate') setAff({ url: '', name: '', price: 0, mrp: 0, category: 'Electronics', platform: '', emoji: '🔗', tagline: '', features: '' });
      load();
    } catch (e) { fail(e); } finally { setBusy(false); }
  }

  async function togglePublish(p: StoreProduct) {
    try { await api.post<Envelope<any>>(`/store/admin/products/${p.id}/publish?published=${!p.published}`); load(); }
    catch (e) { fail(e); }
  }
  async function removeProduct(p: StoreProduct) {
    if (!window.confirm(`Delete "${p.name}"?`)) return;
    try { await api.delete(`/store/admin/products/${p.id}`); notify('Deleted.'); load(); }
    catch (e) { fail(e); }
  }

  async function fetchMeta() {
    setMetaBusy(true); setError('');
    try {
      const r = await api.post<Envelope<any>>('/store/meta', { url: aff.url.trim() });
      const m = r.data.data;
      setAff(a => ({ ...a, name: m.title || a.name, platform: m.platform || a.platform, price: m.price || a.price }));
      if (m.error) setError(m.error);
      else notify('Product details fetched — check & save.');
    } catch (e) { fail(e); } finally { setMetaBusy(false); }
  }

  async function orderAction(o: StoreOrder, action: 'paid' | 'ship' | 'deliver') {
    if (action === 'ship') {
      const partner = window.prompt('Delivery partner name?', settings.partner_name || 'DTDC');
      if (partner === null) return;
      const tracking = window.prompt('Tracking number (optional)?', '') || '';
      try { await api.post<Envelope<StoreOrder>>(`/store/admin/orders/${o.id}/ship`, { partner, tracking }); load(); notify('Marked as shipped to partner.'); }
      catch (e) { fail(e); }
      return;
    }
    try {
      await api.post<Envelope<StoreOrder>>(`/store/admin/orders/${o.id}/${action}`);
      notify(action === 'paid' ? 'UPI payment confirmed.' : 'Order delivered — cash collected.'); load();
    } catch (e) { fail(e); }
  }

  async function saveSettings() {
    setBusy(true); setError('');
    try {
      const r = await api.post<Envelope<StoreSettings>>('/store/settings', settings);
      setSettings(r.data.data); notify('Payment settings saved.');
    } catch (e) { fail(e); } finally { setBusy(false); }
  }

  const own = products.filter(p => p.kind === 'own');
  const affs = products.filter(p => p.kind === 'affiliate');
  const pending = orders.filter(o => !['Delivered', 'Cancelled', 'Returned'].includes(o.status));

  return (
    <section className="space-y-4 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold">Store Admin</h1>
        <div className="flex gap-2 overflow-x-auto">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={clsx('whitespace-nowrap flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border',
                tab === t.id ? 'bg-slate-900 text-white border-slate-900' : 'bg-white border-slate-200 text-slate-700')}>
              <t.icon size={14} />{t.label}
            </button>
          ))}
        </div>
      </div>

      {error && <p role="alert" className="bg-red-50 border border-red-200 text-red-700 text-sm p-3 rounded">{error}</p>}
      {ok && <p role="status" className="bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm p-3 rounded">{ok}</p>}

      {/* ============================== GO-LIVE CHECKLIST ============================== */}
      {ready && (
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <div className="flex items-center justify-between">
            <h2 className="font-bold text-sm">Store go-live checklist</h2>
            <span className={clsx('text-xs font-bold rounded-full px-2 py-0.5',
              [ready.upi_id, ready.amazon_tag, ready.flipkart_affid, ready.has_own, ready.has_affiliate].every(Boolean)
                ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700')}>
              {[ready.upi_id, ready.amazon_tag, ready.flipkart_affid, ready.has_own, ready.has_affiliate].filter(Boolean).length}/5 ready
            </span>
          </div>
          <div className="grid sm:grid-cols-2 gap-1.5 mt-3 text-sm">
            <Check ok={ready.upi_id} label="UPI ID set (online payments on)" tab={() => setTab('settings')} />
            <Check ok={ready.amazon_tag} label="Amazon Associates tag added" tab={() => setTab('settings')} />
            <Check ok={ready.flipkart_affid} label="Flipkart Affiliate ID added" tab={() => setTab('settings')} />
            <Check ok={ready.has_own} label="At least 1 own product live" tab={() => setTab('products')} />
            <Check ok={ready.has_affiliate} label="At least 1 affiliate deal live" tab={() => setTab('affiliate')} />
          </div>
          <p className="text-[11px] text-slate-500 mt-2">Tick pannaadha items-a neenga provide pannanum — avlo dhaan. Ellam ✅ aana pinbu store full-auto run aagum.</p>
        </div>
      )}

      {/* ============================== MY PRODUCTS ============================== */}
      {tab === 'products' && (
        <div className="grid md:grid-cols-5 gap-4">
          <div className="md:col-span-2 bg-white rounded-xl border border-slate-200 p-4 space-y-3">
            <h2 className="font-bold">{form.id ? 'Edit product' : 'Add my product'}</h2>
            <p className="text-xs text-slate-500">Found a product you sell — add it here, it publishes on the store immediately.</p>
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Product name" className="w-full border rounded p-2 text-sm" />
            <div className="grid grid-cols-2 gap-2">
              <input type="number" value={form.price || ''} onChange={e => setForm(f => ({ ...f, price: +e.target.value }))} placeholder="Selling price ₹" className="w-full border rounded p-2 text-sm" />
              <input type="number" value={form.mrp || ''} onChange={e => setForm(f => ({ ...f, mrp: +e.target.value }))} placeholder="MRP ₹" className="w-full border rounded p-2 text-sm" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input type="number" value={form.stock || ''} onChange={e => setForm(f => ({ ...f, stock: +e.target.value }))} placeholder="Stock" className="w-full border rounded p-2 text-sm" />
              <input value={form.emoji} onChange={e => setForm(f => ({ ...f, emoji: e.target.value }))} placeholder="Emoji 🛍️" className="w-full border rounded p-2 text-sm" />
            </div>
            <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))} className="w-full border rounded p-2 text-sm bg-white">
              <option>Mobiles</option><option>Electronics</option><option>Fashion</option>
              <option>Home & Kitchen</option><option>Beauty</option><option>Books</option><option>General</option>
            </select>
            <input value={form.tagline} onChange={e => setForm(f => ({ ...f, tagline: e.target.value }))} placeholder="Short tagline" className="w-full border rounded p-2 text-sm" />
            <input value={form.highlight} onChange={e => setForm(f => ({ ...f, highlight: e.target.value }))} placeholder="Highlight / offer line" className="w-full border rounded p-2 text-sm" />
            <input value={form.features} onChange={e => setForm(f => ({ ...f, features: e.target.value }))} placeholder="Features (comma separated)" className="w-full border rounded p-2 text-sm" />
            <input type="number" value={form.delivery_days} onChange={e => setForm(f => ({ ...f, delivery_days: +e.target.value }))} placeholder="Delivery in days" className="w-full border rounded p-2 text-sm" />
            <button disabled={busy} onClick={() => void saveProduct('own')} className="w-full bg-orange-500 text-white py-2.5 rounded-lg font-bold disabled:opacity-60">
              <Plus size={16} className="inline mr-1" />{form.id ? 'Save changes' : 'Publish product'}</button>
          </div>
          <div className="md:col-span-3 space-y-2">
            {own.map(p => (
              <div key={p.id} className="flex items-center gap-3 bg-white border border-slate-200 rounded-xl p-3">
                <div className={clsx('w-12 h-12 rounded-lg flex items-center justify-center text-2xl bg-gradient-to-br shrink-0', p.gradient)}>{p.emoji}</div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold truncate">{p.name}</p>
                  <p className="text-xs text-slate-500">{inr(p.price)} · stock {p.stock} · {p.published ? <span className="text-emerald-600">live</span> : <span className="text-slate-400">hidden</span>}</p>
                </div>
                <button onClick={() => setForm({
                  id: p.id, name: p.name, category: p.category, price: p.price, mrp: p.mrp, stock: p.stock,
                  emoji: p.emoji, tagline: p.tagline || '', highlight: p.highlight || '',
                  features: (p.features || []).join(', '), delivery_days: p.delivery_days,
                })} className="text-slate-500 border rounded-lg p-1.5" title="Edit">✏️</button>
                <button onClick={() => void togglePublish(p)} className="border rounded-lg p-1.5" title={p.published ? 'Hide' : 'Publish'}>
                  {p.published ? <EyeOff size={14} /> : <Eye size={14} className="text-emerald-600" />}</button>
                <button onClick={() => void removeProduct(p)} className="text-red-500 border rounded-lg p-1.5" title="Delete"><Trash2 size={14} /></button>
              </div>
            ))}
            {own.length === 0 && <p className="text-sm text-slate-400 text-center py-8">No products yet — add your first one.</p>}
          </div>
        </div>
      )}

      {/* ============================== AFFILIATE ============================== */}
      {tab === 'affiliate' && (
        <div className="grid md:grid-cols-2 gap-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
            <h2 className="font-bold">Add an affiliate deal</h2>
            <p className="text-xs text-slate-500">Paste the Amazon/Flipkart product URL you want to promote, tap <b>Fetch</b> to auto-fill, then Save. Shoppers will be redirected to that link and you earn your affiliate commission on their purchase.</p>
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input value={aff.url} onChange={e => setAff(a => ({ ...a, url: e.target.value }))} placeholder="https://www.amazon.in/dp/…  or  flipkart.com/…"
                  className="w-full border rounded-lg pl-8 pr-2 py-2 text-sm" />
              </div>
              <button disabled={metaBusy} onClick={() => void fetchMeta()} className="bg-sky-600 text-white px-3 rounded-lg text-sm disabled:opacity-60">
                <RefreshCw size={14} className={clsx('inline mr-1', metaBusy && 'animate-spin')} />Fetch</button>
            </div>
            {(() => {
              const u = aff.url.toLowerCase();
              const plat = u.includes('amazon') ? 'Amazon' : u.includes('flipkart') ? 'Flipkart' : '';
              if (!plat) return aff.platform ? <p className="text-xs text-sky-600">Detected platform: {aff.platform}</p> : null;
              const readyTag = plat === 'Amazon' ? !!settings.amazon_tag?.trim() : !!settings.flipkart_affid?.trim();
              const word = plat === 'Amazon' ? 'tag' : 'Affiliate ID';
              return (
                <p className={clsx('text-xs rounded p-2', readyTag ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700')}>
                  {readyTag
                    ? `✓ Your ${plat} ${word} will be attached automatically. Paste any normal product link — commission follows.`
                    : `⚠️ Your ${plat} ${word} not set yet — add it in “Payment Setup” tab so your commission is tracked.`}
                </p>
              );
            })()}
            <input value={aff.name} onChange={e => setAff(a => ({ ...a, name: e.target.value }))} placeholder="Deal title" className="w-full border rounded p-2 text-sm" />
            <div className="grid grid-cols-2 gap-2">
              <input type="number" value={aff.price || ''} onChange={e => setAff(a => ({ ...a, price: +e.target.value }))} placeholder="Deal price ₹" className="w-full border rounded p-2 text-sm" />
              <input type="number" value={aff.mrp || ''} onChange={e => setAff(a => ({ ...a, mrp: +e.target.value }))} placeholder="MRP ₹" className="w-full border rounded p-2 text-sm" />
            </div>
            <select value={aff.category} onChange={e => setAff(a => ({ ...a, category: e.target.value }))} className="w-full border rounded p-2 text-sm bg-white">
              <option>Mobiles</option><option>Electronics</option><option>Fashion</option>
              <option>Home & Kitchen</option><option>Beauty</option><option>Books</option><option>General</option>
            </select>
            <input value={aff.emoji} onChange={e => setAff(a => ({ ...a, emoji: e.target.value }))} placeholder="Emoji" className="w-full border rounded p-2 text-sm" />
            <input value={aff.tagline} onChange={e => setAff(a => ({ ...a, tagline: e.target.value }))} placeholder="Short tagline" className="w-full border rounded p-2 text-sm" />
            <input value={aff.features} onChange={e => setAff(a => ({ ...a, features: e.target.value }))} placeholder="Features (comma separated)" className="w-full border rounded p-2 text-sm" />
            <button disabled={busy} onClick={() => void saveProduct('affiliate')} className="w-full bg-sky-600 text-white py-2.5 rounded-lg font-bold disabled:opacity-60">
              <Plus size={16} className="inline mr-1" />Publish deal</button>
          </div>
          <div className="space-y-2">
            {affs.map(p => (
              <div key={p.id} className="flex items-center gap-3 bg-white border border-slate-200 rounded-xl p-3">
                <div className={clsx('w-12 h-12 rounded-lg flex items-center justify-center text-2xl bg-gradient-to-br shrink-0', p.gradient)}>{p.emoji}</div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold truncate">{p.name}</p>
                  <p className="text-xs text-slate-500 text-ellipsis overflow-hidden">{inr(p.price)} · {p.platform || 'partner'}
                    <span className={clsx('ml-2', p.published ? 'text-emerald-600' : 'text-slate-400')}>{p.published ? 'live' : 'hidden'}</span></p>
                  {p.affiliate_url && <a href={p.affiliate_url} target="_blank" rel="noopener noreferrer" className="text-[11px] text-sky-600 truncate block">Open link <ExternalLink size={10} className="inline" /></a>}
                </div>
                <button onClick={() => void togglePublish(p)} className="border rounded-lg p-1.5" title="Show/Hide">
                  {p.published ? <EyeOff size={14} /> : <Eye size={14} className="text-emerald-600" />}</button>
                <button onClick={() => void removeProduct(p)} className="text-red-500 border rounded-lg p-1.5" title="Delete"><Trash2 size={14} /></button>
              </div>
            ))}
            {affs.length === 0 && <p className="text-sm text-slate-400 text-center py-8">No affiliate deals yet — paste your first Amazon/Flipkart link.</p>}
          </div>
        </div>
      )}

      {/* ============================== ORDERS ============================== */}
      {tab === 'orders' && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <Banknote size={16} className="text-emerald-600" />
            {pending.length} order(s) to fulfil · cash pickup on COD · confirm UPI once the money arrives.
          </div>
          {orders.length === 0 && <p className="text-sm text-slate-400 text-center py-8">No orders yet.</p>}
          {orders.map(o => {
            const st = STATUS_STYLE[o.status] || 'bg-slate-100 text-slate-700';
            return (
              <div key={o.id} className="bg-white border border-slate-200 rounded-xl p-4 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="font-bold text-sm">{o.id}</span>
                    <span className="ml-2 text-xs text-slate-500">{o.customer.name} · {o.customer.phone}</span>
                  </div>
                  <span className={clsx('rounded-full px-2 py-0.5 text-xs font-semibold', st)}>{o.status}</span>
                </div>
                <p className="text-xs text-slate-500">{o.customer.address}, {o.customer.city} — {o.customer.pincode}</p>
                <div className="flex flex-wrap gap-1.5">
                  {o.items.map(i => (
                    <span key={i.product_id} className="text-[11px] bg-slate-100 rounded px-2 py-1">{i.emoji} {i.name} ×{i.qty}</span>
                  ))}
                </div>
                <div className="text-xs text-slate-600">Payment: <b>{o.payment === 'upi' ? `UPI${o.pay_status === 'paid' ? ' (paid)' : o.pay_status === 'pending' ? ' (awaiting)' : ''}` : 'Cash on Delivery'}</b> · Total <b>{inr(o.summary.total)}</b></div>
                {o.shipment?.partner && <p className="text-[11px] text-violet-600">🚚 {o.shipment.partner}{o.shipment.tracking ? ` · ${o.shipment.tracking}` : ''}</p>}
                <div className="flex flex-wrap gap-2 pt-1">
                  {o.payment === 'upi' && o.status === 'PaymentPending' && (
                    <button onClick={() => void orderAction(o, 'paid')} className="bg-emerald-600 text-white text-xs font-bold px-3 py-1.5 rounded">✓ Confirm UPI payment</button>
                  )}
                  {o.status === 'Placed' && (o.payment !== 'upi' || o.pay_status === 'paid') && (
                    <button onClick={() => void orderAction(o, 'ship')} className="bg-violet-600 text-white text-xs font-bold px-3 py-1.5 rounded"><Truck size={12} className="inline mr-1" />Handover to delivery partner</button>
                  )}
                  {o.status === 'Shipped' && (
                    <button onClick={() => void orderAction(o, 'deliver')} className="bg-slate-900 text-white text-xs font-bold px-3 py-1.5 rounded">✓ Mark delivered (cash collected)</button>
                  )}
                  {o.status === 'Delivered' && (
                    <span className="text-emerald-600 text-xs font-bold px-3 py-1.5">Delivered ✓</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ============================== EARNINGS ============================== */}
      {tab === 'earnings' && (
        <div className="space-y-4">
          {!stats ? <p className="text-sm text-slate-400 py-8 text-center">Loading earnings…</p> : (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Stat label="Revenue (placed+)" value={inr(stats.revenue_confirmed)} icon={<TrendingUp size={16} />} tone="emerald" />
                <Stat label="Orders (all)" value={String(stats.orders_total)} icon={<ClipboardList size={16} />} tone="blue" />
                <Stat label="To fulfil" value={String(stats.orders_pending)} icon={<Truck size={16} />} tone="amber" />
                <Stat label="Affiliate clicks" value={String(stats.affiliate_clicks)} icon={<MousePointerClick size={16} />} tone="sky" />
              </div>
              <div className="grid md:grid-cols-2 gap-3">
                <div className="bg-white rounded-xl border border-slate-200 p-4">
                  <h3 className="font-bold text-sm mb-2">Payment mix</h3>
                  <p className="text-sm text-slate-600">💳 UPI: <b>{stats.upi_orders}</b> · 💵 COD: <b>{stats.cod_orders}</b></p>
                  <p className="text-sm text-slate-600 mt-1">🛍️ Live products: <b>{stats.products_live}</b> · 🔗 Affiliate deals: <b>{stats.products_affiliate}</b></p>
                </div>
                <div className="bg-white rounded-xl border border-slate-200 p-4">
                  <h3 className="font-bold text-sm mb-2">Top affiliate deals (clicks)</h3>
                  {stats.top_clicks.length === 0 ? <p className="text-xs text-slate-400">No clicks yet.</p> :
                    <ul className="space-y-1 text-sm">{stats.top_clicks.map(c => (
                      <li key={c.name} className="flex justify-between gap-2"><span className="truncate">{c.name}</span><b>{c.clicks}</b></li>))}</ul>}
                </div>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <h3 className="font-bold text-sm mb-2">Best-selling products</h3>
                {stats.top_products.length === 0 ? <p className="text-xs text-slate-400">No sales yet.</p> :
                  <ul className="space-y-1 text-sm">{stats.top_products.map(p => (
                    <li key={p.name} className="flex justify-between gap-2"><span className="truncate">{p.name}</span><span>{p.qty} sold · <b>{inr(p.revenue)}</b></span></li>))}</ul>}
              </div>
              <p className="text-[11px] text-slate-500">Revenue counts orders that are Placed / Shipped / Delivered. Affiliate commission is paid by the partner; the click count shows shopper interest here.</p>
            </>
          )}
        </div>
      )}

      {/* ============================== PAYMENT SETUP ============================== */}
      {tab === 'settings' && (
        <div className="max-w-lg bg-white rounded-xl border border-slate-200 p-5 space-y-3">
          <h2 className="font-bold">Payment &amp; delivery setup</h2>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-slate-600">Your UPI ID (where customers pay) — e.g. name@okaxis / name@ybl</label>
              <input value={settings.upi_id} onChange={e => setSettings(s => ({ ...s, upi_id: e.target.value }))} placeholder="yourname@okhdfcbank"
                className="w-full border rounded-lg p-2.5 text-sm mt-1" />
              <p className="text-[11px] text-slate-500 mt-1">Set this and customers see a "Pay via UPI" button during checkout (works with GPay/PhonePe/Paytm).</p>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Store name shown in UPI</label>
              <input value={settings.merchant_name} onChange={e => setSettings(s => ({ ...s, merchant_name: e.target.value }))}
                className="w-full border rounded-lg p-2.5 text-sm mt-1" />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Amazon Associates tracking tag (commission)</label>
              <input value={settings.amazon_tag || ''} onChange={e => setSettings(s => ({ ...s, amazon_tag: e.target.value }))} placeholder="yoursite-21"
                className="w-full border rounded-lg p-2.5 text-sm mt-1" />
              <p className="text-[11px] text-slate-500 mt-1">Amazon Associates-la unga tracking ID (`-21` la mudiyum, e.g. davidmart-21). Idha podunga — Amazon link add panna automatic-ah tag attach aagum.</p>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Flipkart Affiliate ID (affid)</label>
              <input value={settings.flipkart_affid || ''} onChange={e => setSettings(s => ({ ...s, flipkart_affid: e.target.value }))} placeholder="your-affiliate-id"
                className="w-full border rounded-lg p-2.5 text-sm mt-1" />
              <p className="text-[11px] text-slate-500 mt-1">Flipkart Affiliate dashboard-la irukkura Affiliate ID. Flipkart link-ku automatic-ah `affid` add aagum.</p>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Delivery partner (default for COD handover)</label>
              <input value={settings.partner_name} onChange={e => setSettings(s => ({ ...s, partner_name: e.target.value }))} placeholder="DTDC / Delhivery / your courier"
                className="w-full border rounded-lg p-2.5 text-sm mt-1" />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Partner phone (optional)</label>
              <input value={settings.partner_phone} onChange={e => setSettings(s => ({ ...s, partner_phone: e.target.value }))} placeholder="98XXXXXXXX"
                className="w-full border rounded-lg p-2.5 text-sm mt-1" />
            </div>
            <button disabled={busy} onClick={() => void saveSettings()} className="w-full bg-slate-900 text-white py-2.5 rounded-lg font-bold disabled:opacity-60">
              Save payment settings</button>
            <div className="text-[11px] text-slate-500 bg-slate-50 rounded-lg p-3">
              <p><b>How orders flow:</b></p>
              <p>· UPI order → customer pays you via UPI app → you tap <b>Confirm UPI payment</b> → order becomes Placed.</p>
              <p>· COD order → customer pays cash on delivery → you <b>hand over to delivery partner</b> (Shipped) → partner confirms → <b>Mark delivered</b>.</p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}