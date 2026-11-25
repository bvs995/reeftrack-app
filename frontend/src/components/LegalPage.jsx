import React, { useEffect, useState } from 'react';

// Página pública de Política de Privacidad / Términos de Uso (/privacidad, /terminos).
// El texto vive en PRIVACY.md y TERMS.md y lo sirve el backend en /api/legal/*.
// Sirve también como URL pública de privacidad para Google Play.

const DOCS = {
  privacy: { endpoint: '/api/legal/privacy', title: 'Política de Privacidad' },
  terms: { endpoint: '/api/legal/terms', title: 'Términos de Uso' },
};

const LEGAL_PATHS = {
  '/privacidad': 'privacy',
  '/privacy': 'privacy',
  '/terminos': 'terms',
  '/terms': 'terms',
};

export function legalDocForPath(pathname) {
  const clean = (pathname || '').replace(/\/+$/, '').toLowerCase();
  return LEGAL_PATHS[clean] || null;
}

// Negritas y código en línea como elementos React (sin innerHTML).
function renderInline(text, keyPrefix) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={key} className="text-white font-semibold">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={key} className="px-1 py-0.5 rounded bg-slate-800 text-cyan-300 text-[0.9em]">{part.slice(1, -1)}</code>;
    }
    return <React.Fragment key={key}>{part}</React.Fragment>;
  });
}

// Markdown mínimo: títulos, listas con viñeta o numeradas, separadores y párrafos.
function renderMarkdown(md) {
  const lines = (md || '').replace(/\r\n/g, '\n').split('\n');
  const blocks = [];
  let list = null;
  let paragraph = [];

  const flushParagraph = () => {
    if (paragraph.length) {
      const k = `p-${blocks.length}`;
      blocks.push(<p key={k} className="text-slate-300 leading-relaxed mb-4">{renderInline(paragraph.join(' '), k)}</p>);
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list) {
      const k = `l-${blocks.length}`;
      const Tag = list.ordered ? 'ol' : 'ul';
      blocks.push(
        <Tag key={k} className={`${list.ordered ? 'list-decimal' : 'list-disc'} pl-6 mb-4 space-y-1.5 text-slate-300`}>
          {list.items.map((item, i) => <li key={`${k}-${i}`} className="leading-relaxed">{renderInline(item, `${k}-${i}`)}</li>)}
        </Tag>
      );
      list = null;
    }
  };

  for (const raw of lines) {
    const line = raw.trim();
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    const bullet = line.match(/^[*-]\s+(.*)$/);
    const numbered = line.match(/^\d+\.\s+(.*)$/);

    if (!line) { flushParagraph(); flushList(); continue; }
    if (/^(-{3,}|\*{3,})$/.test(line)) { flushParagraph(); flushList(); blocks.push(<hr key={`hr-${blocks.length}`} className="border-slate-700 my-6" />); continue; }
    if (heading) {
      flushParagraph(); flushList();
      const level = heading[1].length;
      const k = `h-${blocks.length}`;
      const cls = level === 1 ? 'text-2xl sm:text-3xl font-black text-white mb-4'
        : level === 2 ? 'text-lg sm:text-xl font-bold text-cyan-300 mt-8 mb-3'
        : 'text-base font-bold text-white mt-5 mb-2';
      const Tag = `h${Math.min(level + 1, 4)}`;
      blocks.push(<Tag key={k} className={cls}>{renderInline(heading[2], k)}</Tag>);
      continue;
    }
    if (bullet || numbered) {
      flushParagraph();
      const ordered = Boolean(numbered);
      if (!list || list.ordered !== ordered) { flushList(); list = { ordered, items: [] }; }
      list.items.push((bullet || numbered)[1]);
      continue;
    }
    flushList();
    paragraph.push(line);
  }
  flushParagraph(); flushList();
  return blocks;
}

export default function LegalPage({ doc }) {
  const meta = DOCS[doc] || DOCS.privacy;
  const [content, setContent] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    document.title = `${meta.title} | AquaReef`;
    let cancelled = false;
    fetch(meta.endpoint)
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then((data) => { if (!cancelled) setContent(data.content || ''); })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [meta.endpoint, meta.title]);

  const other = doc === 'terms'
    ? { href: '/privacidad', label: 'Política de Privacidad' }
    : { href: '/terminos', label: 'Términos de Uso' };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
          <a href="/" className="flex items-center gap-2 font-black text-white">
            <img src="/logo-reef-icon.png" alt="" className="w-7 h-7 rounded-lg" />
            AquaReef
          </a>
          <a href={other.href} className="text-xs font-semibold text-cyan-400 hover:text-cyan-300">{other.label}</a>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">
        {error && (
          <div className="rounded-xl border border-red-500/40 bg-red-950/40 p-4 text-sm text-red-200">
            No se pudo cargar el documento. Revisa tu conexión e inténtalo de nuevo.
          </div>
        )}
        {!error && content === null && <p className="text-slate-400 text-sm">Cargando…</p>}
        {!error && content !== null && <article>{renderMarkdown(content)}</article>}

        <div className="mt-10 pt-6 border-t border-slate-800">
          <a href="/" className="text-sm font-semibold text-cyan-400 hover:text-cyan-300">← Volver a AquaReef</a>
        </div>
      </main>
    </div>
  );
}
