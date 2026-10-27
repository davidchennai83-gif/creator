import { useEffect, useMemo, useState } from 'react';
import {
  ShoppingCart, Search, Heart, X, Plus, Minus, Trash2,
  ChevronRight, CreditCard, Truck, ShieldCheck, BadgeCheck,
  Store as StoreIcon, ExternalLink, Banknote,
} from 'lucide-react';
import api, { Envelope, errorMessage } from '../services/apiClient';
import clsx from 'clsx';

export interface StoreProduct {
  id: string; name: string; category: string; price: number; mrp: number;
  rating: number; reviews: number; emoji: string; gradient: string;
  tagline: string; highlight: string; features: string[];
  delivery_days: number; stock: number;
  kind: 'own' | 'affiliate'; affiliate_url?: string; platform?: string;
  published?: boolean;
}
export interface StoreOrder {
  id: string; created: string; items: { product_id: string; name: string; emoji: string; qty: number; price: number; line_total: number; delivery_days: number }[];
  customer: { name: string; phone: string; address: string; city: string; pincode: string };
  payment: 'upi' | 'cod'; pay_status?: string | null; upi_intent?: string | null;
  summary: { subtotal: number; delivery: number; total: number };
  status: string; shipment?: Record<string, any>;
}
export interface StoreSettings { upi_id: string; merchant_name: string; partner_name: string; partner_phone: string; amazon_tag?: string; flipkart_affid?: string; }
export interface StoreReadiness {
  upi_id: boolean; amazon_tag: boolean; flipkart_affid: boolean;
  has_own: boolean; has_affiliate: boolean; merchant_name: string; partner_name: string;
}
export interface StoreAnalytics {
  orders_total: number; orders_pending: number; revenue_confirmed: number;
  cod_orders: number; upi_orders: number; affiliate_clicks: number;
  products_live: number; products_affiliate: number;
  top_products: { name: string; qty: number; revenue: number }[];
  top_clicks: { name: string; clicks: number }[];
}

const CATEGORIES = ['All', 'Own', 'Affiliate', 'Mobiles', 'Electronics', 'Fashion', 'Home & Kitchen', 'Beauty', 'Books'];
const inr = (n: number) => '₹' + n.toLocaleString('en-IN');
const pct = (p: StoreProduct) => p.mrp > p.price ? Math.round(((p.mrp - p.price) / p.mrp) * 100) : 0;
const starRow = (r: number) => '★'.repeat(Math.round(r)) + '☆'.repeat(5 - Math.round(r));
const qtyOf = (cart: Record<string, number>, id: string) => cart[id] || 0;

export const STATUS_STYLE: Record<string, string> = {
  PaymentPending: 'bg-amber-100 text-amber-700',
  Placed: 'bg-blue-100 text-blue-700',
  Shipped: 'bg-violet-100 text-violet-700',
  Delivered: 'bg-emerald-100 text-emerald-700',
  Cancelled: 'bg-red-100 text-red-700',
};

async function openAffiliate(url?: string, id?: string) {
  let target = url;
  if (id) {
    try {
      const r = await api.post<Envelope<{ url: string }>>(`/store/click/${id}`);
      target = r.data.data.url || target;
    } catch { /* tracking is best-effort; still open the deal */ }
  }
  if (target) window.open(target, '_blank', 'noopener,noreferrer');
}

export default function Store() {
  const [products, setProducts] = useState<StoreProduct[]>([]);
  const [settings, setSettings] = useState<StoreSettings | null>(null);
  const [error, setError] = useState('');
  const [cat, setCat] = useState('All');
  const [sort, setSort] = useState<'popular' | 'price-asc' | 'price-desc' | 'discount'>('popular');
  const [query, setQuery] = useState('');
  const [view, setView] = useState<StoreProduct | null>(null);
  const [cartOpen, setCartOpen] = useState(false);
  const [cart, setCart] = useState<Record<string, number>>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('creator.store.cart') || '{}');
      if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return {};
      return Object.fromEntries(Object.entries(saved).filter(([, qty]) => Number.isFinite(Number(qty)) && Number(qty) > 0)
        .map(([id, qty]) => [id, Number(qty)]));
    } catch { return {}; }
  });
  const [wish, setWish] = useState<string[]>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('creator.store.wishlist') || '[]');
      return Array.isArray(saved) ? saved.filter((id): id is string => typeof id === 'string') : [];
    } catch { return []; }
  });
  const [step, setStep] = useState<'cart' | 'checkout' | 'done'>('cart');
  const [placed, setPlaced] = useState<StoreOrder | null>(null);
  const [orders, setOrders] = useState<StoreOrder[]>([]);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: '', phone: '', address: '', city: '', pincode: '', payment: 'upi' as 'upi' | 'cod' });

  useEffect(() => { localStorage.setItem('creator.store.cart', JSON.stringify(cart)); }, [cart]);
  useEffect(() => { localStorage.setItem('creator.store.wishlist', JSON.stringify(wish)); }, [wish]);

  const load = () => api.get<Envelope<{ products: StoreProduct[] }>>('/store/catalog')
    .then(r => setProducts(r.data.data.products))
    .catch(e => setError(errorMessage(e)));
  const loadOrders = () => api.get<Envelope<{ orders: StoreOrder[] }>>('/store/orders')
    .then(r => setOrders(r.data.data.orders || []))
    .catch(() => { /* optional */ });
  useEffect(() => {
    void load(); void loadOrders();
    api.get<Envelope<StoreSettings>>('/store/settings').then(r => setSettings(r.data.data)).catch(() => {});
  }, []);
  useEffect(() => { if (placed) void loadOrders(); }, [placed]);

  const upiAvailable = !!settings?.upi_id?.trim();

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const base = products.filter(p => {
      if (cat === 'Own' && p.kind !== 'own') return false;
      if (cat === 'Affiliate' && p.kind !== 'affiliate') return false;
      if (cat !== 'All' && cat !== 'Own' && cat !== 'Affiliate' && p.category !== cat) return false;
      return !q || p.name.toLowerCase().includes(q) || p.category.toLowerCase().includes(q);
    });
    const disc = (p: StoreProduct) => pct(p);
    if (sort === 'price-asc') return [...base].sort((a, b) => a.price - b.price);
    if (sort === 'price-desc') return [...base].sort((a, b) => b.price - a.price);
    if (sort === 'discount') return [...base].sort((a, b) => disc(b) - disc(a));
    return [...base].sort((a, b) => (b.reviews || 0) - (a.reviews || 0));
  }, [products, cat, query, sort]);

  const cartEntries = useMemo(() =>
    products.filter(p => p.kind === 'own' && qtyOf(cart, p.id) > 0).map(p => ({ p, qty: qtyOf(cart, p.id) })),
    [products, cart]);
  const subtotal = cartEntries.reduce((s, e) => s + e.p.price * e.qty, 0);
  const delivery = subtotal === 0 ? 0 : (subtotal >= 499 ? 0 : 49);
  const total = subtotal + delivery;
  const cartCount = cartEntries.reduce((s, e) => s + e.qty, 0);

  const setQty = (id: string, n: number) => {
    setCart(c => { const next = { ...c }; if (n <= 0) delete next[id]; else next[id] = Math.min(n, 20); return next; });
  };
  const toggleWish = (id: string) => setWish(w => w.includes(id) ? w.filter(x => x !== id) : [...w, id]);

  async function placeOrder() {
    if (!form.name.trim() || !form.phone.trim() || !form.address.trim() || !form.city.trim() || !form.pincode.trim()) {
      setError('Please fill every delivery field before placing the order.'); return;
    }
    if (form.payment === 'upi' && !upiAvailable) { setError('UPI is not configured on this store yet — use Cash on Delivery.'); return; }
    setBusy(true); setError('');
    try {
      const r = await api.post<Envelope<StoreOrder>>('/store/orders', {
        items: cartEntries.map(e => ({ id: e.p.id, qty: e.qty })),
        customer: { name: form.name, phone: form.phone, address: form.address, city: form.city, pincode: form.pincode },
        payment: form.payment,
      });
      setPlaced(r.data.data);
      setCart({}); setStep('done'); setCartOpen(true);
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }

  const eta = view?.delivery_days ?? 1;

  return (
    <section className="space-y-4 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl text-orange-500"><StoreIcon size={26} /></span>
          <h1 className="text-2xl font-extrabold tracking-tight">Creator<span className="text-orange-500">Mart</span></h1>
        </div>
        <button onClick={() => { setStep('cart'); setCartOpen(true); }}
          className="relative flex items-center gap-2 bg-orange-500 text-white px-4 py-2 rounded-lg font-semibold shadow">
          <ShoppingCart size={18} /> <span className="hidden sm:inline">Cart</span>
          {cartCount > 0 && <span className="absolute -top-2 -right-2 bg-slate-900 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">{cartCount}</span>}
        </button>
      </div>

      {/* Banner */}
      <div className="rounded-2xl bg-gradient-to-r from-orange-500 via-amber-500 to-yellow-400 text-white p-5 sm:p-8 shadow-lg">
        <p className="text-xs sm:text-sm font-medium uppercase tracking-widest opacity-90">Mega Savings Days</p>
        <h2 className="text-lg sm:text-3xl font-extrabold mt-1">Shop our stock · or grab best deals on Amazon &amp; Flipkart.</h2>
        <p className="text-xs sm:text-sm mt-2 opacity-90">Own products: UPI or Cash on Delivery · Affiliate links send you to the deal page</p>
        <div className="flex gap-3 mt-3 text-[10px] sm:text-xs">
          <span className="bg-white/20 rounded-full px-2 py-1">🚚 Free delivery over ₹499</span>
          <span className="bg-white/20 rounded-full px-2 py-1">🔗 Affiliate deals</span>
          <span className="bg-white/20 rounded-full px-2 py-1">💵 COD supported</span>
        </div>
      </div>

      {/* Search + sort */}
      <div className="flex gap-2">
        <div className="flex-1 relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search products, deals…"
            className="w-full border rounded-lg pl-9 pr-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
        </div>
        <select value={sort} onChange={e => setSort(e.target.value as any)}
          className="border rounded-lg px-2 py-2.5 text-sm bg-white text-slate-700 focus:outline-none">
          <option value="popular">Popular</option>
          <option value="discount">Biggest discount</option>
          <option value="price-asc">Price: low → high</option>
          <option value="price-desc">Price: high → low</option>
        </select>
      </div>

      {/* Category chips */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {CATEGORIES.map(c => (
          <button key={c} onClick={() => setCat(c)} className={clsx(
            'whitespace-nowrap px-3 py-1.5 rounded-full text-sm border',
            cat === c ? 'bg-orange-500 text-white border-orange-500 font-semibold' : 'bg-white border-slate-200 text-slate-700')}>
            {c}
          </button>
        ))}
      </div>

      {error && <p role="alert" className="bg-red-50 p-4 text-red-700 text-sm rounded">{error}</p>}

      {visible.length === 0 && !error && <p className="text-sm text-slate-500 py-8 text-center">No products match your filter yet.</p>}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
        {visible.map(p => (
          <article key={p.id} className="bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition flex flex-col overflow-hidden">
            <div className="relative">
              <button onClick={() => setView(p)} className="w-full text-left">
                <div className={clsx('h-28 sm:h-36 flex items-center justify-center text-5xl sm:text-6xl bg-gradient-to-br', p.gradient)}>
                  <span aria-hidden="true">{p.emoji}</span>
                </div>
              </button>
              <button onClick={() => toggleWish(p.id)} aria-label="Toggle wishlist"
                className="absolute top-1.5 left-1.5 bg-white/90 rounded-full p-1 shadow">
                <Heart size={16} className={wish.includes(p.id) ? 'text-red-500 fill-red-500' : 'text-red-400'} />
              </button>
              <span className={clsx('absolute top-1.5 right-1.5 text-white text-[10px] font-bold px-1.5 py-0.5 rounded',
                p.kind === 'affiliate' ? 'bg-sky-600' : 'bg-red-600')}>
                {p.kind === 'affiliate' ? `🔗 ${p.platform || 'Deal'}` : `-${pct(p)}%`}
              </span>
            </div>
            <div className="p-2.5 sm:p-3 flex flex-col flex-1">
              <p className="text-[10px] uppercase tracking-wide text-slate-400">{p.category}
                <span className="ml-1 text-orange-500 normal-case">{p.kind === 'affiliate' ? '· via partner' : '· our stock'}</span></p>
              <h3 className="text-xs sm:text-sm font-semibold line-clamp-2 min-h-[2.2em]">{p.name}</h3>
              <p className="mt-1"><span className="font-bold text-base sm:text-lg">{inr(p.price)}</span>
                {p.mrp > p.price && <span className="line-through text-slate-400 text-xs ml-1.5">{inr(p.mrp)}</span>}</p>
              <p className="text-[11px] text-amber-600 font-medium">{starRow(p.rating)} {
                p.reviews > 0 && <span className="text-slate-400">({p.reviews.toLocaleString('en-IN')})</span>}</p>
              <div className="mt-2">
                {p.kind === 'affiliate' ? (
                  <button onClick={() => void openAffiliate(p.affiliate_url, p.id)}
                    className="flex items-center justify-center gap-1 w-full bg-sky-600 hover:bg-sky-700 text-white text-sm font-semibold rounded-lg py-2">
                    Buy on {p.platform || 'partner'} <ExternalLink size={13} />
                  </button>
                ) : (p.stock ?? 0) <= 0 ? (
                  <button disabled className="w-full bg-slate-200 text-slate-500 text-sm font-semibold rounded-lg py-2 cursor-not-allowed">Out of stock</button>
                ) : (
                  <button onClick={() => setQty(p.id, qtyOf(cart, p.id) + 1)}
                    className="w-full bg-orange-500 hover:bg-orange-600 text-white text-sm font-semibold rounded-lg py-2">
                    {qtyOf(cart, p.id) > 0 ? `In cart · ${qtyOf(cart, p.id)}` : 'Add to Cart'}
                  </button>
                )}
              </div>
            </div>
          </article>
        ))}
      </div>

      {/* Product detail modal */}
      {view && (
        <div className="fixed inset-0 z-40 bg-black/50 flex items-end sm:items-center justify-center" onClick={() => setView(null)}>
          <div className="bg-white w-full sm:max-w-lg rounded-t-2xl sm:rounded-2xl p-5 max-h-[92vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-start">
              <h2 className="text-lg font-bold pr-6">{view.name}</h2>
              <button onClick={() => setView(null)} aria-label="Close"><X size={20} /></button>
            </div>
            <div className={clsx('h-44 rounded-xl flex items-center justify-center text-7xl bg-gradient-to-br mt-3', view.gradient)}>{view.emoji}</div>
            <p className="mt-3 text-sm text-slate-600">{view.highlight || view.tagline}</p>
            <p className="mt-1 text-sm font-medium">{inr(view.price)} {view.mrp > view.price && <span className="line-through text-slate-400 text-xs">{inr(view.mrp)}</span>}
              {pct(view) > 0 && <span className="text-emerald-600 text-xs ml-2">{pct(view)}% off</span>}</p>
            {view.kind === 'affiliate'
              ? <p className="text-xs mt-1 text-sky-600">Affiliate deal — your purchase goes through {view.platform || 'the partner site'}.</p>
              : <p className="text-xs mt-1 text-slate-500">Own stock · delivery in ~{view.delivery_days} days · UPI or COD</p>}
            {view.features?.length > 0 && <ul className="mt-3 space-y-1.5 text-sm">
              {view.features.map(f => <li key={f} className="flex gap-2"><BadgeCheck size={16} className="text-emerald-500 shrink-0" /><span>{f}</span></li>)}
            </ul>}
            <div className="grid grid-cols-2 gap-2 mt-4">
              {view.kind === 'affiliate' ? (
                <button onClick={() => void openAffiliate(view.affiliate_url, view.id)} className="col-span-2 bg-sky-600 text-white py-2.5 rounded-lg font-semibold text-sm">
                  Buy on {view.platform || 'partner'} ↗
                </button>
              ) : (view.stock ?? 0) > 0 ? (
                <>
                  <button onClick={() => { setQty(view.id, qtyOf(cart, view.id) + 1); }} className="bg-orange-500 text-white py-2.5 rounded-lg font-semibold text-sm">Add to Cart</button>
                  <button onClick={() => { setQty(view.id, 1); setView(null); setStep('cart'); setCartOpen(true); }}
                    className="bg-slate-900 text-white py-2.5 rounded-lg font-semibold text-sm">Buy Now</button>
                </>
              ) : <p className="col-span-2 text-center text-red-500 text-sm py-2">Out of stock — check back soon.</p>}
            </div>
          </div>
        </div>
      )}

      {/* Cart drawer */}
      {cartOpen && (
        <div className="fixed inset-0 z-40 bg-black/40" onClick={() => setCartOpen(false)}>
          <aside className="fixed right-0 top-0 h-full w-full sm:w-96 bg-white shadow-2xl flex flex-col" onClick={e => e.stopPropagation()}>
            <header className="flex items-center justify-between p-4 border-b">
              <h3 className="font-bold text-lg">{step === 'done' ? 'Order' : 'My Cart'} <span className="text-slate-400 text-sm">({cartCount})</span></h3>
              <button onClick={() => setCartOpen(false)} aria-label="Close cart"><X size={20} /></button>
            </header>
            {step === 'done' && placed ? (
              <div className="p-6 text-center space-y-3">
                <div className="text-5xl">{placed.payment === 'upi' && placed.status === 'PaymentPending' ? '💳' : '🎉'}</div>
                <h3 className="text-xl font-extrabold text-emerald-600">
                  {placed.payment === 'upi' ? 'Pay to confirm' : 'Order placed!'}</h3>
                <p className="text-sm text-slate-600">Order ID: <b>{placed.id}</b></p>
                <p className="text-sm">Amount: <b>{inr(placed.summary.total)}</b></p>
                {placed.payment === 'upi' && placed.status === 'PaymentPending' && (
                  <div className="space-y-2">
                    {placed.upi_intent ? (
                      <>
                        <a href={placed.upi_intent} className="block bg-emerald-600 text-white py-3 rounded-lg font-bold">
                          Open UPI app &amp; pay {inr(placed.summary.total)} <Banknote size={16} className="inline" />
                        </a>
                        <p className="text-[11px] text-slate-500">UPI ID: {settings?.upi_id} · Pay then the store confirms your order.</p>
                      </>
                    ) : (
                      <p className="text-xs text-slate-500">UPI isn't configured yet on this store — use Cash on Delivery instead.</p>
                    )}
                  </div>
                )}
                {placed.payment === 'cod' && <p className="text-xs text-slate-500">Pay {inr(placed.summary.total)} cash when it arrives.</p>}
                <p className="text-xs text-slate-500">Arriving in ~{Math.max(...placed.items.map(i => i.delivery_days))} days</p>
                <button onClick={() => { setStep('cart'); setPlaced(null); setCartOpen(false); }}
                  className="w-full bg-slate-900 text-white py-2.5 rounded-lg mt-3 font-semibold text-sm">Continue shopping</button>
              </div>
            ) : cartEntries.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center gap-2 text-slate-400">
                <ShoppingCart size={40} /><p>Your cart is empty.</p>
                <button onClick={() => setCartOpen(false)} className="text-orange-500 text-sm underline">Browse products</button>
              </div>
            ) : (
              <>
                <div className="flex-1 overflow-y-auto p-4 space-y-3">
                  {cartEntries.map(({ p, qty }) => (
                    <div key={p.id} className="flex gap-3 border rounded-lg p-2.5">
                      <div className={clsx('w-16 h-16 rounded-lg flex items-center justify-center text-3xl bg-gradient-to-br shrink-0', p.gradient)}>{p.emoji}</div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-semibold line-clamp-2">{p.name}</p>
                        <p className="text-sm font-bold mt-0.5">{inr(p.price)}</p>
                        <div className="flex items-center gap-2 mt-1.5">
                          <button onClick={() => setQty(p.id, qty - 1)} className="border rounded px-1.5 py-0.5"><Minus size={12} /></button>
                          <span className="text-sm font-semibold w-6 text-center">{qty}</span>
                          <button onClick={() => setQty(p.id, qty + 1)} className="border rounded px-1.5 py-0.5"><Plus size={12} /></button>
                          <button onClick={() => setQty(p.id, 0)} className="ml-auto text-red-500"><Trash2 size={14} /></button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <footer className="border-t p-4 space-y-2">
                  <div className="flex justify-between text-sm"><span>Subtotal</span><span>{inr(subtotal)}</span></div>
                  <div className="flex justify-between text-sm"><span>Delivery</span><span>{delivery === 0 ? <b className="text-emerald-600">FREE</b> : inr(delivery)}</span></div>
                  <div className="flex justify-between font-bold text-base"><span>Total</span><span>{inr(total)}</span></div>
                  {step === 'cart' && <button onClick={() => setStep('checkout')} className="w-full bg-orange-500 text-white py-3 rounded-lg font-bold">Checkout <ChevronRight size={16} className="inline" /></button>}
                  {step === 'checkout' && (
                    <div className="space-y-2">
                      <input placeholder="Full name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="w-full border rounded p-2 text-sm" />
                      <input placeholder="Mobile number" inputMode="numeric" value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} className="w-full border rounded p-2 text-sm" />
                      <input placeholder="Full address" value={form.address} onChange={e => setForm(f => ({ ...f, address: e.target.value }))} className="w-full border rounded p-2 text-sm" />
                      <div className="grid grid-cols-2 gap-2">
                        <input placeholder="City" value={form.city} onChange={e => setForm(f => ({ ...f, city: e.target.value }))} className="w-full border rounded p-2 text-sm" />
                        <input placeholder="PIN code" inputMode="numeric" value={form.pincode} onChange={e => setForm(f => ({ ...f, pincode: e.target.value }))} className="w-full border rounded p-2 text-sm" />
                      </div>
                      <div className="flex gap-2 pt-1">
                        <button disabled={!upiAvailable} onClick={() => setForm(f => ({ ...f, payment: 'upi' }))}
                          className={clsx('flex-1 border rounded-lg p-2 text-sm', form.payment === 'upi' ? 'border-orange-500 bg-orange-50 text-orange-700 font-semibold' : 'text-slate-600', !upiAvailable && 'opacity-40 cursor-not-allowed')}>
                          <CreditCard size={14} className="inline mr-1" />UPI
                        </button>
                        <button onClick={() => setForm(f => ({ ...f, payment: 'cod' }))}
                          className={clsx('flex-1 border rounded-lg p-2 text-sm', form.payment === 'cod' ? 'border-orange-500 bg-orange-50 text-orange-700 font-semibold' : 'text-slate-600')}>
                          💵 Cash on Delivery
                        </button>
                      </div>
                      {!upiAvailable && <p className="text-[11px] text-slate-500">UPI button is off until the store sets its UPI ID (Store Admin → Settings).</p>}
                      {error && <p role="alert" className="text-red-600 text-xs">{error}</p>}
                      <button disabled={busy} onClick={() => void placeOrder()} className="w-full bg-emerald-600 text-white py-3 rounded-lg font-bold disabled:opacity-60">
                        {busy ? 'Placing…' : `Place Order · ${inr(total)}`}</button>
                      <button onClick={() => setStep('cart')} className="w-full text-sm text-slate-500 underline py-1">← Back to cart</button>
                    </div>
                  )}
                </footer>
              </>
            )}
          </aside>
        </div>
      )}

      {/* My Orders */}
      {orders.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-5">
          <h3 className="font-bold text-base mb-3 flex items-center gap-2"><Truck size={18} className="text-orange-500" /> My Orders</h3>
          <div className="space-y-3">
            {orders.map(o => {
              const st = STATUS_STYLE[o.status] || 'bg-slate-100 text-slate-700';
              return (
                <div key={o.id} className="border rounded-lg p-3 bg-slate-50">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                    <span className="font-semibold">{o.id}</span>
                    <span className={clsx('rounded-full px-2 py-0.5 text-xs font-semibold', st)}>{o.status}{o.pay_status === 'pending' ? ' · UPI awaiting payment' : ''}</span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">{new Date(o.created).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</p>
                  <div className="flex flex-wrap gap-2 mt-2 text-2xl">
                    {o.items.map(i => <span key={i.product_id} title={`${i.name} × ${i.qty}`}>{i.emoji}<sup className="text-[9px] text-slate-400">×{i.qty}</sup></span>)}
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2 mt-2 text-xs text-slate-600">
                    <span>{o.payment === 'upi' ? 'UPI' : 'Cash on Delivery'} · {o.items.length} item(s)</span>
                    <span className="font-bold text-sm">Total {inr(o.summary.total)}</span>
                  </div>
                  {o.payment === 'upi' && o.status === 'PaymentPending' && o.upi_intent && (
                    <a href={o.upi_intent} className="mt-2 inline-block bg-emerald-600 text-white px-3 py-1.5 rounded text-xs font-bold">Pay now via UPI</a>
                  )}
                  {o.shipment?.partner && <p className="text-[11px] text-violet-600 mt-1">🚚 {o.shipment.partner}{o.shipment.tracking ? ` · ${o.shipment.tracking}` : ''}</p>}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}