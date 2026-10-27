import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight, BadgeCheck, ExternalLink, IndianRupee, Search, ShieldCheck,
  ShoppingBag, Sparkles, Star, Truck,
} from 'lucide-react';
import clsx from 'clsx';
import { publicClient, Envelope, errorMessage } from '../services/apiClient';

export interface FindsProduct {
  id: string;
  title: string;
  title_ta: string;
  category: string;
  price: number;
  mrp: number;
  rating: number;
  orders_count: number;
  features: string[];
  cautions: string[];
  image_url: string;
  buy_url: string;
  discount_percent: number;
  demo: boolean;
  active: boolean;
}

interface FindsPayload { products: FindsProduct[]; categories: string[] }

const inr = (value: number) => '₹' + Math.round(Number(value) || 0).toLocaleString('en-IN');

export default function Finds() {
  const [products, setProducts] = useState<FindsProduct[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [category, setCategory] = useState('All');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const previous = document.title;
    document.title = "Tamil Budget Finds – Today's Meesho picks";
    return () => { document.title = previous; };
  }, []);

  useEffect(() => {
    let alive = true;
    publicClient.get<Envelope<FindsPayload>>('/finds/products')
      .then(response => {
        if (!alive) return;
        setProducts(response.data.data.products || []);
        setCategories(response.data.data.categories || []);
      })
      .catch(err => { if (alive) setError(errorMessage(err)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  const visible = useMemo(() => products.filter(product => {
    const matchesCategory = category === 'All' || product.category === category;
    const needle = query.trim().toLowerCase();
    const haystack = `${product.title} ${product.title_ta} ${product.category}`.toLowerCase();
    return matchesCategory && (!needle || haystack.includes(needle));
  }), [products, category, query]);

  const featured = products[0];
  const hasDemo = products.some(product => product.demo);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100" style={{fontFamily: "'Nirmala UI', system-ui, sans-serif"}}>
      <header className="sticky top-0 z-30 border-b border-white/10 bg-slate-950/85 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <Link to="/finds" className="flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-rose-500 to-orange-400 text-xl font-black text-slate-950">த</span>
            <span>
              <span className="block text-lg font-bold tracking-tight">Tamil Budget Finds</span>
              <span className="block text-xs text-slate-400">Meesho finds under ₹999 · Tamil reviews</span>
            </span>
          </Link>
          <nav className="flex items-center gap-2 text-sm sm:gap-5">
            <a href="#finds" className="hidden text-slate-300 transition hover:text-white sm:block">Today&apos;s finds</a>
            <a href="#how" className="hidden text-slate-300 transition hover:text-white sm:block">How it works</a>
            <Link to="/finds-admin" className="rounded-full border border-white/15 px-4 py-2 font-semibold text-slate-200 transition hover:bg-white/10">Admin</Link>
          </nav>
        </div>
      </header>

      <main>
        <section className="relative overflow-hidden border-b border-white/10">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_60%_at_20%_10%,rgba(251,113,133,.22),transparent_70%),radial-gradient(50%_50%_at_85%_30%,rgba(251,146,60,.18),transparent_70%)]" />
          <div className="relative mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 lg:grid-cols-[1.15fr_.85fr] lg:py-20">
            <div>
              <span className="inline-flex items-center gap-2 rounded-full border border-rose-300/30 bg-rose-400/10 px-4 py-2 text-sm font-semibold text-rose-200">
                <Sparkles size={16} /> Daily budget picks · Tamil-ல
              </span>
              <h1 className="mt-6 text-4xl font-black leading-tight tracking-tight sm:text-6xl">
                Smart shopping.<br /><span className="text-rose-300">Budget-க்கு perfect.</span>
              </h1>
              <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-300">
                Every day we pick one useful Meesho find under ₹999, check the price,
                rating and reviews, and explain the good and the caution in simple Tamil.
                No hype. No fake reviews. Just a clear buying guide.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <a href="#finds" className="inline-flex items-center gap-2 rounded-full bg-rose-400 px-6 py-3 font-bold text-slate-950 transition hover:bg-rose-300">
                  Browse today&apos;s finds <ArrowRight size={18} />
                </a>
                <a href="#how" className="inline-flex items-center gap-2 rounded-full border border-white/15 px-6 py-3 font-semibold text-slate-200 transition hover:bg-white/10">
                  How it works
                </a>
              </div>
              <div className="mt-10 grid max-w-xl grid-cols-3 gap-3 text-center">
                {[
                  ['1', 'new find / day'],
                  ['₹999', 'budget cap'],
                  ['3', 'platforms'],
                ].map(([value, label]) => (
                  <div key={label} className="rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-4">
                    <p className="text-2xl font-black text-white">{value}</p>
                    <p className="mt-1 text-xs text-slate-400">{label}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="relative flex items-center justify-center">
              <div className="absolute h-72 w-72 rounded-full bg-rose-400/20 blur-3xl" />
              {featured ? (
                <div className="relative w-full max-w-md overflow-hidden rounded-[2rem] border border-white/15 bg-white/[0.06] p-4 shadow-2xl shadow-black/40">
                  <div className="relative aspect-square overflow-hidden rounded-[1.5rem] bg-slate-100">
                    {featured.image_url ? (
                      <img src={featured.image_url} alt={featured.title} className="h-full w-full object-contain" />
                    ) : (
                      <div className="grid h-full w-full place-items-center bg-gradient-to-br from-rose-400 to-orange-300 text-7xl">🛍️</div>
                    )}
                    {featured.discount_percent > 0 && (
                      <span className="absolute left-3 top-3 rounded-full bg-slate-950/85 px-3 py-1 text-xs font-bold text-rose-200">
                        {featured.discount_percent}% OFF
                      </span>
                    )}
                    {featured.demo && (
                      <span className="absolute right-3 top-3 rounded-full bg-amber-300 px-3 py-1 text-xs font-bold text-slate-950">SAMPLE</span>
                    )}
                  </div>
                  <div className="px-2 pb-2 pt-5">
                    <p className="text-xs font-bold uppercase tracking-[0.18em] text-rose-300">Today&apos;s pick</p>
                    <h2 className="mt-2 text-2xl font-bold leading-snug">{featured.title_ta || featured.title}</h2>
                    <div className="mt-3 flex items-end gap-3">
                      <span className="text-3xl font-black text-white">{inr(featured.price)}</span>
                      {featured.mrp > featured.price && <span className="pb-1 text-sm text-slate-400 line-through">{inr(featured.mrp)}</span>}
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-slate-300">
                      {featured.rating > 0 && <span className="inline-flex items-center gap-1"><Star size={15} className="fill-amber-300 text-amber-300" />{featured.rating.toFixed(1)}</span>}
                      {featured.orders_count > 0 && <span>{featured.orders_count.toLocaleString('en-IN')}+ orders</span>}
                    </div>
                    <a href={`${featured.buy_url}?p=web`} target="_blank" rel="noopener noreferrer sponsored"
                       className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-white px-5 py-3 font-bold text-slate-950 transition hover:bg-rose-100">
                      Buy on Meesho <ExternalLink size={17} />
                    </a>
                  </div>
                </div>
              ) : (
                <div className="relative w-full max-w-md rounded-[2rem] border border-white/15 bg-white/[0.04] p-10 text-center text-slate-400">
                  <ShoppingBag size={44} className="mx-auto text-rose-300" />
                  <p className="mt-4 font-semibold text-slate-200">Today&apos;s find is being prepared.</p>
                  <p className="mt-2 text-sm">Open the admin catalogue to add the first product.</p>
                </div>
              )}
            </div>
          </div>
        </section>

        <section id="finds" className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm font-bold uppercase tracking-[0.2em] text-rose-300">The catalogue</p>
              <h2 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Today&apos;s budget finds</h2>
              <p className="mt-3 max-w-2xl text-slate-400">Hand-picked products with a clear price, the good parts and one honest caution.</p>
            </div>
            <div className="relative w-full lg:w-80">
              <Search size={18} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
              <input value={query} onChange={event => setQuery(event.target.value)}
                     placeholder="Search products..."
                     className="w-full rounded-full border border-white/15 bg-white/[0.06] py-3 pl-11 pr-4 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-rose-300/60" />
            </div>
          </div>

          <div className="mt-7 flex flex-wrap gap-2">
            {['All', ...categories].map(item => (
              <button key={item} onClick={() => setCategory(item)}
                      className={clsx('rounded-full border px-4 py-2 text-sm font-semibold transition',
                        category === item
                          ? 'border-rose-300 bg-rose-300 text-slate-950'
                          : 'border-white/15 bg-white/[0.04] text-slate-300 hover:bg-white/10')}>
                {item}
              </button>
            ))}
          </div>

          {hasDemo && (
            <div className="mt-6 rounded-2xl border border-amber-300/25 bg-amber-300/10 px-5 py-4 text-sm text-amber-100">
              <strong className="font-bold">Demo catalogue:</strong> these are sample products for the end-to-end test.
              Replace them with real Meesho finds from the admin page before sharing the landing page with shoppers.
            </div>
          )}

          {loading && (
            <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({length: 6}).map((_, index) => (
                <div key={index} className="h-96 animate-pulse rounded-3xl border border-white/10 bg-white/[0.04]" />
              ))}
            </div>
          )}

          {!loading && error && (
            <div className="mt-8 rounded-3xl border border-rose-300/25 bg-rose-400/10 p-6 text-rose-100">
              <p className="font-bold">Could not load the catalogue.</p>
              <p className="mt-2 text-sm text-rose-200/80">{error}</p>
              <button onClick={() => window.location.reload()} className="mt-4 rounded-full bg-white px-5 py-2 text-sm font-bold text-slate-950">Try again</button>
            </div>
          )}

          {!loading && !error && visible.length === 0 && (
            <div className="mt-8 rounded-3xl border border-white/10 bg-white/[0.04] p-10 text-center text-slate-400">
              <ShoppingBag size={42} className="mx-auto text-slate-500" />
              <p className="mt-4 font-semibold text-slate-200">No products match that search.</p>
              <button onClick={() => { setCategory('All'); setQuery(''); }} className="mt-3 text-sm font-bold text-rose-300 underline">Clear filters</button>
            </div>
          )}

          {!loading && !error && visible.length > 0 && (
            <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {visible.map(product => (
                <article key={product.id} className="group flex flex-col overflow-hidden rounded-3xl border border-white/10 bg-white/[0.045] transition duration-200 hover:-translate-y-1 hover:border-rose-300/40 hover:bg-white/[0.07]">
                  <div className="relative aspect-[4/3] overflow-hidden bg-slate-100">
                    {product.image_url ? (
                      <img src={product.image_url} alt={product.title} className="h-full w-full object-contain transition duration-300 group-hover:scale-105" />
                    ) : (
                      <div className="grid h-full w-full place-items-center bg-gradient-to-br from-rose-400 to-orange-300 text-6xl">🛍️</div>
                    )}
                    <div className="absolute left-3 top-3 flex gap-2">
                      {product.discount_percent > 0 && <span className="rounded-full bg-slate-950/85 px-3 py-1 text-xs font-bold text-rose-200">{product.discount_percent}% OFF</span>}
                      {product.demo && <span className="rounded-full bg-amber-300 px-3 py-1 text-xs font-bold text-slate-950">SAMPLE</span>}
                    </div>
                  </div>
                  <div className="flex flex-1 flex-col p-5">
                    <p className="text-xs font-bold uppercase tracking-[0.16em] text-rose-300">{product.category}</p>
                    <h3 className="mt-2 text-lg font-bold leading-snug">{product.title_ta || product.title}</h3>
                    {product.title_ta && <p className="mt-1 text-sm text-slate-400">{product.title}</p>}
                    <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-slate-300">
                      {product.rating > 0 && <span className="inline-flex items-center gap-1"><Star size={15} className="fill-amber-300 text-amber-300" />{product.rating.toFixed(1)}</span>}
                      {product.orders_count > 0 && <span>{product.orders_count.toLocaleString('en-IN')}+ orders</span>}
                    </div>
                    <ul className="mt-4 space-y-2 text-sm text-slate-300">
                      {(product.features || []).slice(0, 2).map(feature => (
                        <li key={feature} className="flex gap-2"><BadgeCheck size={16} className="mt-0.5 shrink-0 text-emerald-300" />{feature}</li>
                      ))}
                    </ul>
                    <div className="mt-auto flex items-end justify-between gap-3 pt-6">
                      <div>
                        <span className="text-2xl font-black text-white">{inr(product.price)}</span>
                        {product.mrp > product.price && <span className="ml-2 text-sm text-slate-500 line-through">{inr(product.mrp)}</span>}
                      </div>
                      <a href={`${product.buy_url}?p=web`} target="_blank" rel="noopener noreferrer sponsored"
                         className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-bold text-slate-950 transition hover:bg-rose-100">
                        Buy <ExternalLink size={15} />
                      </a>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section id="how" className="border-y border-white/10 bg-white/[0.03]">
          <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
            <div className="max-w-2xl">
              <p className="text-sm font-bold uppercase tracking-[0.2em] text-rose-300">Simple process</p>
              <h2 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">How Tamil Budget Finds works</h2>
              <p className="mt-3 text-slate-400">We do the boring research. You make the final decision on Meesho.</p>
            </div>
            <div className="mt-8 grid gap-4 md:grid-cols-3">
              {[
                { icon: Search, title: '1. We shortlist', body: 'One useful product under ₹999 is picked from the catalogue and checked for price, rating and reviews.' },
                { icon: ShieldCheck, title: '2. We explain', body: 'A short Tamil video and post explain the benefits and one honest caution. No fake urgency.' },
                { icon: Truck, title: '3. You buy safely', body: 'The button opens the Meesho listing. Check size, colour, delivery date and return policy before paying.' },
              ].map(item => (
                <div key={item.title} className="rounded-3xl border border-white/10 bg-slate-950/50 p-6">
                  <span className="grid h-12 w-12 place-items-center rounded-2xl bg-rose-400/15 text-rose-300"><item.icon size={22} /></span>
                  <h3 className="mt-5 text-lg font-bold">{item.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-400">{item.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
          <div className="grid gap-5 rounded-3xl border border-white/10 bg-white/[0.04] p-6 sm:p-8 lg:grid-cols-[1fr_auto] lg:items-center">
            <div className="flex gap-4">
              <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-emerald-400/15 text-emerald-300"><IndianRupee size={22} /></span>
              <div>
                <h2 className="text-lg font-bold">Affiliate disclosure</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
                  Tamil Budget Finds is an independent buying guide. When you buy through our links,
                  Meesho may pay us a small commission at no extra cost to you. Prices and availability
                  can change on Meesho; always confirm the final price, size and return policy there.
                </p>
              </div>
            </div>
            <Link to="/" className="inline-flex items-center justify-center gap-2 rounded-full border border-white/15 px-5 py-3 text-sm font-semibold text-slate-200 transition hover:bg-white/10">
              Creator Platform <ArrowRight size={16} />
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/10 px-4 py-8 text-center text-sm text-slate-500">
        <p>© {new Date().getFullYear()} Tamil Budget Finds · A separate affiliate brand from the educational channels.</p>
        <p className="mt-2">Every pick is checked by hand before it appears here.</p>
      </footer>
    </div>
  );
}
