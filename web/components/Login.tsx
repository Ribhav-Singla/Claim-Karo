"use client";

import { useState } from "react";
import { lookupUser, type Profile } from "@/lib/api";

// Synthetic wallet numbers (api/data/users.json), shown as one-tap shortcuts for the demo.
const DEMO_NUMBERS = [
  { mobile: "9000011111", label: "Ravi · Hindi" },
  { mobile: "9000022222", label: "Priya · English" },
];

export default function Login({ onLogin }: { onLogin: (p: Profile) => void }) {
  const [mobile, setMobile] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(number: string) {
    if (number.length !== 10) {
      setError("Enter a 10-digit mobile number");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      onLogin(await lookupUser(number));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-4rem)] max-w-md flex-col justify-center pb-16">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-navy">Vehicle damaged?</h1>
        <p className="mt-2 text-sm text-muted">
          Tell us what happened in Hindi or English. We&apos;ll check if a claim is worth it and
          file it for you.
        </p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(mobile);
        }}
        className="rounded-2xl border border-line bg-white p-6 shadow-sm"
      >
        <label htmlFor="mobile" className="text-sm font-medium text-ink">
          Mobile number
        </label>
        <div
          className={`mt-2 flex items-center rounded-xl border bg-white transition focus-within:ring-4 ${
            error ? "border-red-400 focus-within:ring-red-100" : "border-line focus-within:border-sky focus-within:ring-sky-soft"
          }`}
        >
          <span className="border-r border-line px-3 py-3 text-sm text-muted">+91</span>
          <input
            id="mobile"
            inputMode="numeric"
            autoComplete="tel-national"
            autoFocus
            maxLength={10}
            value={mobile}
            onChange={(e) => {
              setMobile(e.target.value.replace(/\D/g, "").slice(0, 10));
              setError(null);
            }}
            placeholder="10-digit number linked to Paytm"
            className="w-full rounded-r-xl px-3 py-3 text-base tracking-wide outline-none placeholder:text-sm placeholder:tracking-normal"
          />
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={loading || mobile.length !== 10}
          className="mt-5 w-full rounded-xl bg-sky py-3 text-sm font-semibold text-white transition hover:bg-sky-dark disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? "Fetching your policies…" : "Continue"}
        </button>

        <div className="mt-6 border-t border-line pt-4">
          <p className="text-xs text-muted">Demo accounts</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {DEMO_NUMBERS.map((d) => (
              <button
                key={d.mobile}
                type="button"
                onClick={() => {
                  setMobile(d.mobile);
                  submit(d.mobile);
                }}
                className="rounded-full border border-line px-3 py-1.5 text-xs text-ink transition hover:border-sky hover:bg-sky-soft"
              >
                {d.mobile.replace(/(\d{5})(\d{5})/, "$1 $2")} · {d.label}
              </button>
            ))}
          </div>
        </div>
      </form>

      <p className="mt-6 text-center text-xs text-muted">
        Prototype with synthetic data. No real insurer or Paytm account is contacted.
      </p>
    </div>
  );
}
