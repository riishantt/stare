import { useState } from "react";
import { api } from "../api/client";
import type { CitationCheck, FirewallCheckOut } from "../api/types";
import SourceCard from "../components/SourceCard";
import OpinionDrawer from "../components/OpinionDrawer";
import { ErrorBox } from "../components/Spinner";
import type { SourceItem } from "../lib/sources";
import { errMsg } from "../util";

const MATA =
  "Plaintiff's claim is not time-barred, and the Montreal Convention's limitations period was tolled during the carrier's bankruptcy. " +
  "See Varghese v. China Southern Airlines Co., Ltd., 925 F.3d 1339 (11th Cir. 2019); " +
  "Shaboon v. Egyptair, 2013 IL App (1st) 111279-U (Ill. App. Ct. 2013); " +
  "Petersen v. Iran Air, 905 F. Supp. 2d 121 (D.D.C. 2012); " +
  "Martinez v. Delta Air Lines, Inc., 2019 WL 4639462 (Tex. App. Sept. 25, 2019); " +
  "Estate of Durden v. KLM Royal Dutch Airlines, 2017 WL 2418825 (Ga. Ct. App. June 5, 2017); " +
  "Miller v. United Airlines, Inc., 174 F.3d 366 (4th Cir. 1999). " +
  "These authorities confirm that the discovery rule applies. Cf. McDonnell Douglas Corp. v. Green, 411 U.S. 792 (1973).";

function toItem(c: CitationCheck, i: number): SourceItem {
  return {
    key: `chk${i}`, authority: null, check: c, status: c.status, adverse: false,
    citation: c.citation.cite || c.citation.raw, caseName: c.matched_case_name || c.citation.case_name,
    opinionId: c.opinion_id ?? null, quote: c.citation.quote,
  };
}

export default function CheckDraft() {
  const [text, setText] = useState("");
  const [res, setRes] = useState<FirewallCheckOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [drawer, setDrawer] = useState<SourceItem | null>(null);

  async function run() {
    setBusy(true);
    setErr("");
    try { setRes(await api.firewallCheck(text)); } catch (e) { setErr(errMsg(e)); setRes(null); } finally { setBusy(false); }
  }

  // strike removed sentences/spans in the cleaned text view: show original with removed strings struck
  const struck = res ? strike(text, res.removed) : null;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-navy">Check a draft (Citation Firewall)</h1>
        <p className="text-muted">Paste a brief or draft. Every citation is extracted and verified against the case index; fabricated or unsupported authorities are blocked. Personal details are redacted before checking.</p>
      </div>
      <div className="card card-b space-y-3">
        <label className="label" htmlFor="draft">Draft text</label>
        <textarea id="draft" className="input legal h-56" value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste the text of a brief, motion or memo here..." />
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-amber" disabled={busy || !text.trim()} onClick={run}>{busy ? "Checking citations..." : "Check citations"}</button>
          <button className="btn" onClick={() => { setText(MATA); setRes(null); }}>Load the Mata v. Avianca example</button>
          {text && <button className="btn" onClick={() => { setText(""); setRes(null); }}>Clear</button>}
        </div>
      </div>
      {err && <ErrorBox message={err} />}
      {res && (
        <>
          <div className={`alert text-base font-semibold ${res.counts.blocked ? "alert-bad" : res.counts.warning ? "alert-warn" : "alert-ok"}`} role="status">
            {res.summary}
            {res.redaction_count > 0 && <span className="ml-3 text-xs font-normal">({res.redaction_count} personal detail(s) redacted before checking)</span>}
          </div>
          <div className="grid items-start gap-4 xl:grid-cols-2">
            <section aria-label="Citation results">
              <h2 className="mb-2 font-bold text-navy">Citations ({res.checks.length})</h2>
              {res.checks.length === 0 ? <p className="text-muted">No citations were found in this text.</p> : (
                <ul className="space-y-2.5">{res.checks.map((c, i) => <SourceCard key={i} item={toItem(c, i)} onView={setDrawer} />)}</ul>
              )}
            </section>
            <section aria-label="Cleaned text" className="card">
              <div className="card-h"><h2>Cleaned text</h2><span className="chip chip-bad">{res.removed.length} removed</span></div>
              <div className="card-b space-y-3">
                <p className="legal whitespace-pre-wrap">{res.cleaned_text || <span className="text-muted">Nothing left after removing unverified authority.</span>}</p>
                {res.removed.length > 0 && (
                  <div>
                    <h3 className="label">Removed by the Citation Firewall</h3>
                    <p className="legal whitespace-pre-wrap rounded-md bg-bad-bg p-3 text-[14px]">
                      {struck!.map((p, i) => p.removed ? <del key={i} className="text-bad">{p.t}</del> : <span key={i}>{p.t}</span>)}
                    </p>
                    <ul className="mt-2 space-y-1">{res.removed.map((r, i) => <li key={i} className="alert alert-bad text-[13px]"><del>{r}</del></li>)}</ul>
                  </div>
                )}
              </div>
            </section>
          </div>
        </>
      )}
      {drawer?.opinionId != null && <OpinionDrawer opinionId={drawer.opinionId} quote={drawer.quote} onClose={() => setDrawer(null)} />}
    </div>
  );
}

function strike(text: string, removed: string[]): { t: string; removed: boolean }[] {
  let parts: { t: string; removed: boolean }[] = [{ t: text, removed: false }];
  for (const r of removed.filter((x) => x.trim().length > 3)) {
    parts = parts.flatMap((p) => {
      if (p.removed) return [p];
      const i = p.t.indexOf(r);
      if (i < 0) return [p];
      return [{ t: p.t.slice(0, i), removed: false }, { t: r, removed: true }, { t: p.t.slice(i + r.length), removed: false }];
    });
  }
  return parts.filter((p) => p.t !== "");
}
