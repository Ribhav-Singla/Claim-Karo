"use client";

// The Paytm app's home screen, with Claim Karo living inside it as "Insurance & Claims".
// Everything here except the Claims tile is decorative: the prototype's one real journey is
// the claim. Phone-first; on wider screens the same sections lay out across the width.

import type { Profile } from "@/lib/api";

const initials = (name: string) =>
  name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

const icon = {
  width: 26,
  height: 26,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

const QrIcon = () => (
  <svg {...icon}>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
    <path d="M14 14h3v3h-3zM20 14v2M17 20h3M14 20h1" />
  </svg>
);
const ContactIcon = () => (
  <svg {...icon}>
    <rect x="4" y="3" width="16" height="18" rx="2" />
    <circle cx="12" cy="10" r="2.5" />
    <path d="M8 17c1-2 7-2 8 0M9 3v2M15 3v2" />
  </svg>
);
const BankIcon = () => (
  <svg {...icon}>
    <path d="M3 10h18L12 4zM5 10v7M9 10v7M15 10v7M19 10v7M3 20h18" />
  </svg>
);
const HistoryIcon = () => (
  <svg {...icon}>
    <rect x="5" y="3" width="14" height="18" rx="2" />
    <path d="M9 8h6M9 12h6M9 16h4" />
  </svg>
);
const PhoneIcon = () => (
  <svg {...icon}>
    <rect x="7" y="2" width="10" height="20" rx="2" />
    <path d="M12 13l1.5-3h-3L12 7" />
  </svg>
);
const CardIcon = () => (
  <svg {...icon}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M3 10h18M7 15h4" />
  </svg>
);
const BulbIcon = () => (
  <svg {...icon}>
    <path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.5.4.5 1.1.5 1.1v1h6v-1s0-.7.5-1.1A6 6 0 0 0 12 3z" />
    <path d="M12 8l-1.5 3h3L12 14" />
  </svg>
);
const TagIcon = () => (
  <svg {...icon}>
    <rect x="3" y="7" width="18" height="10" rx="2" />
    <path d="M7 12h10" />
  </svg>
);
const ShieldIcon = () => (
  <svg {...icon}>
    <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" />
    <path d="M9 12l2 2 4-4" />
  </svg>
);
const CarIcon = () => (
  <svg {...icon}>
    <path d="M5 13l1.5-5h11L19 13M4 13h16v5H4zM7 18v2M17 18v2" />
    <circle cx="8" cy="15.5" r="1" fill="currentColor" />
    <circle cx="16" cy="15.5" r="1" fill="currentColor" />
  </svg>
);
const PlaneIcon = () => (
  <svg {...icon} width={30} height={30}>
    <path d="M2 14l8-2 4-8 2 1-2 7 7 2-1 2-7-1-3 5-2-1 1-5-6-2z" />
  </svg>
);
const SilverIcon = () => (
  <svg {...icon} width={30} height={30}>
    <path d="M4 16l3-6h10l3 6zM8 10l2-4h4l2 4" />
  </svg>
);
const MoneyIcon = () => (
  <svg {...icon} width={30} height={30}>
    <path d="M3 17l9-11 9 11M7 17l5-6 5 6" />
  </svg>
);
const SearchIcon = () => (
  <svg {...icon} width={22} height={22}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-4-4" />
  </svg>
);
const BellIcon = () => (
  <svg {...icon} width={22} height={22}>
    <path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 20a2 2 0 0 0 4 0" />
  </svg>
);

function RoundAction({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <button className="flex flex-col items-center gap-2 text-center" type="button">
      <span className="grid h-[72px] w-[72px] place-items-center rounded-full bg-[#0b3d91] text-white shadow-sm transition hover:bg-navy">
        {children}
      </span>
      <span className="text-[15px] leading-tight text-ink">{label}</span>
    </button>
  );
}

function BillAction({ label, badge, children }: { label: string; badge?: string; children: React.ReactNode }) {
  return (
    <button className="relative flex flex-col items-center gap-2 pt-3 text-center" type="button">
      {badge && (
        <span className="absolute -top-0.5 rounded-md bg-amber-300 px-1.5 py-0.5 text-[11px] font-semibold text-ink">
          {badge}
        </span>
      )}
      <span className="grid h-11 w-11 place-items-center text-[#0b3d91]">{children}</span>
      <span className="text-[15px] leading-tight text-ink">{label}</span>
    </button>
  );
}

export default function PaytmHome({
  profile,
  onOpenClaims,
  onLogout,
}: {
  profile: Profile;
  onOpenClaims: () => void;
  onLogout: () => void;
}) {
  const openClaims = profile.vehicles.length;
  return (
    <div className="mx-auto w-full max-w-6xl pb-28">
      {/* top bar: avatar, promo, search, bell */}
      <div className="flex items-center gap-4 px-4 pt-4">
        <button
          onClick={onLogout}
          title="Log out"
          className="grid h-14 w-14 shrink-0 place-items-center rounded-full bg-pink-100 text-xl font-medium text-pink-900"
        >
          {initials(profile.full_name)}
        </button>
        <div className="min-w-0 flex-1 leading-tight">
          <p className="text-[17px] font-semibold text-ink">Roz ₹21 se SIP</p>
          <p className="flex items-center gap-1 text-[17px] text-ink">
            with Paytm Money
            <span className="grid h-4 w-4 place-items-center rounded-full bg-red-600 text-[10px] text-white">›</span>
          </p>
        </div>
        <button className="p-2 text-ink" aria-label="Search">
          <SearchIcon />
        </button>
        <button className="p-2 text-ink" aria-label="Notifications">
          <BellIcon />
        </button>
      </div>

      <div className="grid gap-6 px-4 pt-8 md:grid-cols-2 md:gap-8 lg:grid-cols-3">
        {/* UPI */}
        <section className="lg:col-span-3">
          <h1 className="text-[28px] font-semibold tracking-tight text-ink md:text-3xl">UPI Money Transfer</h1>
          <div className="mt-6 grid grid-cols-4 gap-2 md:max-w-2xl">
            <RoundAction label="Scan any QR">
              <QrIcon />
            </RoundAction>
            <RoundAction label="Pay Anyone">
              <ContactIcon />
            </RoundAction>
            <RoundAction label="To Bank & Self A/c">
              <BankIcon />
            </RoundAction>
            <RoundAction label="Balance & History">
              <HistoryIcon />
            </RoundAction>
          </div>
        </section>

        {/* Insurance & Claims: the real journey */}
        <section className="rounded-3xl border border-sky/40 bg-white p-5 shadow-sm lg:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="text-[22px] font-semibold text-ink">Insurance &amp; Claims</h2>
            <button onClick={onOpenClaims} className="flex items-center gap-1 text-[15px] font-medium text-sky-dark">
              View All →
            </button>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2">
            <button
              onClick={onOpenClaims}
              className="group flex flex-col items-center gap-2 rounded-2xl bg-sky-soft px-2 py-4 text-center ring-2 ring-sky transition hover:bg-sky/20"
            >
              <span className="grid h-12 w-12 place-items-center rounded-full bg-sky text-white shadow">
                <ShieldIcon />
              </span>
              <span className="text-[15px] font-semibold leading-tight text-navy">Claims</span>
              <span className="text-[11px] leading-tight text-muted">
                {openClaims} vehicle{openClaims === 1 ? "" : "s"} insured
              </span>
            </button>
            <BillAction label="Motor Insurance">
              <CarIcon />
            </BillAction>
            <BillAction label="Health Insurance" badge="New">
              <ShieldIcon />
            </BillAction>
          </div>
          <p className="mt-4 rounded-xl bg-canvas px-3 py-2 text-[13px] text-muted">
            Vehicle damaged? Tap <span className="font-semibold text-navy">Claims</span> and tell Claim Karo what
            happened, in Hindi or English.
          </p>
        </section>

        {/* Recharge & Bills */}
        <section className="rounded-3xl bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-[22px] font-semibold text-ink">Recharge &amp; Bills</h2>
            <button className="flex items-center gap-1 text-[15px] font-medium text-sky-dark">View All →</button>
          </div>
          <div className="mt-2 grid grid-cols-4 gap-1">
            <BillAction label="Mobile Recharge">
              <PhoneIcon />
            </BillAction>
            <BillAction label="Credit Card Bill" badge="Get ₹50">
              <CardIcon />
            </BillAction>
            <BillAction label="Electricity Bill">
              <BulbIcon />
            </BillAction>
            <BillAction label="FASTag Recharge">
              <TagIcon />
            </BillAction>
          </div>
          <div className="mt-3 flex justify-center gap-1">
            <span className="h-1 w-6 rounded-full bg-ink/60" />
            <span className="h-1 w-6 rounded-full bg-line" />
          </div>
        </section>

        {/* promo cards */}
        <section className="grid grid-cols-2 gap-3 lg:col-span-3 lg:grid-cols-4">
          <article className="row-span-2 flex flex-col justify-between rounded-3xl bg-white p-5 shadow-sm lg:row-span-1">
            <span className="text-[#0b3d91]">
              <MoneyIcon />
            </span>
            <div className="mt-6">
              <p className="text-[18px] font-semibold text-ink">Paytm Money</p>
              <p className="mt-1 text-[15px] leading-snug text-muted">₹5,000 monthly SIP. Build real wealth.</p>
            </div>
          </article>
          <article className="flex items-center gap-4 rounded-3xl bg-white p-5 shadow-sm">
            <span className="text-ink">
              <PlaneIcon />
            </span>
            <p className="text-[18px] font-medium leading-snug text-ink">₹1200* OFF on Flights</p>
          </article>
          <article className="flex items-center gap-4 rounded-3xl bg-white p-5 shadow-sm">
            <span className="text-ink">
              <SilverIcon />
            </span>
            <div>
              <p className="text-[18px] font-medium leading-snug text-ink">Buy Silver</p>
              <p className="text-[15px] text-muted">2% Off*</p>
            </div>
          </article>
          <article className="hidden items-center gap-4 rounded-3xl bg-white p-5 shadow-sm lg:flex">
            <span className="text-ink">
              <CarIcon />
            </span>
            <p className="text-[18px] font-medium leading-snug text-ink">FASTag at ₹0 fee</p>
          </article>
        </section>

        {/* chips */}
        <div className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-1 [scrollbar-width:none] lg:col-span-3">
          {["🏆 Golden Diwali", "🎁 Refer & Win ₹400", "💸 Cashback Offers", "🛡️ Claim Karo"].map((c) => (
            <span key={c} className="shrink-0 rounded-full bg-white px-5 py-3 text-[16px] text-ink shadow-sm">
              {c}
            </span>
          ))}
        </div>

        {/* banner */}
        <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#0b2a8a] via-[#0b3d91] to-[#06246b] p-6 text-white shadow-sm lg:col-span-3">
          <div className="grid gap-4 md:grid-cols-2 md:items-center">
            <div>
              <p className="text-[12px] font-semibold uppercase tracking-wider text-sky">paytm</p>
              <p className="mt-1 text-3xl font-extrabold leading-none text-amber-300 md:text-4xl">GOLDEN DIWALI</p>
            </div>
            <div className="md:text-right">
              <p className="text-[17px]">Pay using Paytm</p>
              <p className="text-[20px] font-bold text-amber-200">Win 1g Gold Every Hour</p>
              <button className="mt-3 rounded-full bg-white px-4 py-1.5 text-sm font-semibold text-navy">Know more →</button>
              <p className="mt-2 text-[10px] opacity-60">T&amp;C apply</p>
            </div>
          </div>
          <div className="mt-4 flex justify-center gap-1.5">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <span key={i} className={`h-1.5 w-1.5 rounded-full ${i === 0 ? "bg-white" : "bg-white/40"}`} />
            ))}
          </div>
        </section>
      </div>

      {/* floating Scan QR */}
      <div className="pointer-events-none fixed inset-x-0 bottom-5 z-20 flex justify-center">
        <button className="pointer-events-auto flex items-center gap-3 rounded-full bg-gradient-to-b from-[#1b5fd6] to-[#0b3d91] px-8 py-3.5 text-[22px] font-medium text-white shadow-xl ring-4 ring-white/70">
          <QrIcon />
          Scan QR
        </button>
      </div>
    </div>
  );
}
