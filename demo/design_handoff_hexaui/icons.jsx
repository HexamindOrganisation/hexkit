/* icons.jsx — line icon set + Hexamind logo mark. Exports to window. */
const I = ({ d, s = 18, sw = 1.6, fill = "none", children, ...p }) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill={fill} stroke="currentColor"
       strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" {...p}>
    {d ? <path d={d} /> : children}
  </svg>
);

/* Hexamind mark — a hexagon with an inscribed node-link "mind" glyph */
const HexLogo = ({ s = 22 }) => (
  <svg width={s} height={s} viewBox="0 0 32 32" fill="none">
    <path d="M16 2.4 27.4 9v14L16 29.6 4.6 23V9L16 2.4Z"
          stroke="var(--accent)" strokeWidth="1.7" strokeLinejoin="round" />
    <circle cx="16" cy="11" r="2.1" fill="var(--accent)" />
    <circle cx="11" cy="20" r="1.7" fill="var(--accent)" opacity=".55" />
    <circle cx="21" cy="20" r="1.7" fill="var(--accent)" opacity=".55" />
    <path d="M16 13.1 11.6 18.4M16 13.1 20.4 18.4M11.6 20.4h8.8"
          stroke="var(--accent)" strokeWidth="1.4" strokeLinecap="round" opacity=".7" />
  </svg>
);

const Icons = {
  plus:    (p) => <I d="M12 5v14M5 12h14" {...p} />,
  search:  (p) => <I {...p}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.2-3.2" /></I>,
  chat:    (p) => <I d="M4 5h16v11H8l-4 3.5V5Z" {...p} />,
  layers:  (p) => <I {...p}><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 13 9 5 9-5" /></I>,
  grid:    (p) => <I {...p}><rect x="3.5" y="3.5" width="7" height="7" rx="1.2"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.2"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.2"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.2"/></I>,
  book:    (p) => <I d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 0-3 3V4Z" {...p} />,
  sliders: (p) => <I {...p}><path d="M5 8h9M18 8h1M5 16h1M10 16h9"/><circle cx="16" cy="8" r="2"/><circle cx="8" cy="16" r="2"/></I>,
  spark:   (p) => <I d="M12 3v6M12 15v6M3 12h6M15 12h6M6 6l3.5 3.5M14.5 14.5 18 18M18 6l-3.5 3.5M9.5 14.5 6 18" {...p} />,
  bolt:    (p) => <I d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" {...p} />,
  cmd:     (p) => <I d="M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6Z" {...p} />,
  mic:     (p) => <I {...p}><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></I>,
  wave:    (p) => <I {...p}><path d="M4 10v4M8 6v12M12 8v8M16 5v14M20 10v4"/></I>,
  arrowUp: (p) => <I d="M12 19V6M6 12l6-6 6 6" {...p} />,
  chevDown:(p) => <I d="m6 9 6 6 6-6" {...p} />,
  sidebar: (p) => <I {...p}><rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M9.5 4.5v15"/></I>,
  copy:    (p) => <I {...p}><rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M5.5 15.5H5a1.5 1.5 0 0 1-1.5-1.5V5A1.5 1.5 0 0 1 5 3.5h9A1.5 1.5 0 0 1 15.5 5v.5"/></I>,
  refresh: (p) => <I d="M20 11a8 8 0 1 0-.5 4M20 5v6h-6" {...p} />,
  attach:  (p) => <I d="M20 11.5 12 19.5a5 5 0 0 1-7-7l8-8a3.3 3.3 0 0 1 4.7 4.7l-7.8 7.8a1.6 1.6 0 0 1-2.4-2.3l7.4-7.4" {...p} />,
  history: (p) => <I {...p}><path d="M3.5 12a8.5 8.5 0 1 1 2.6 6.1M3.5 18v-4h4"/><path d="M12 8v4l3 2"/></I>,
  folder:  (p) => <I d="M3.5 6.5a2 2 0 0 1 2-2h3l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5.5a2 2 0 0 1-2-2v-11Z" {...p} />,
  cpu:     (p) => <I {...p}><rect x="6.5" y="6.5" width="11" height="11" rx="2"/><rect x="10" y="10" width="4" height="4" rx="1"/><path d="M9 3.5v2M15 3.5v2M9 18.5v2M15 18.5v2M3.5 9h2M3.5 15h2M18.5 9h2M18.5 15h2"/></I>,
  shield:  (p) => <I d="M12 3 5 6v5c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3Z" {...p} />,
  pen:     (p) => <I d="M4 20l4-1 10.5-10.5a2 2 0 0 0-2.8-2.8L5.2 16 4 20Z" {...p} />,
  doc:     (p) => <I {...p}><path d="M6 3.5h7l5 5V20a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z"/><path d="M13 3.5V8.5h5M8 13h8M8 16.5h8"/></I>,
  flow:    (p) => <I {...p}><rect x="3.5" y="4" width="7" height="5" rx="1.2"/><rect x="13.5" y="15" width="7" height="5" rx="1.2"/><path d="M7 9v3.5a2 2 0 0 0 2 2h4.5"/></I>,
  globe:   (p) => <I {...p}><circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.4 2.5 14.6 0 17M12 3.5c-2.5 2.4-2.5 14.6 0 17"/></I>,
  dots:    (p) => <I {...p}><circle cx="5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/></I>,
  ghost:   (p) => <I {...p}><path d="M5 20V11a7 7 0 0 1 14 0v9l-2.3-1.6L14.3 20 12 18.4 9.7 20 7.3 18.4 5 20Z"/><circle cx="9.5" cy="10.5" r="1" fill="currentColor"/><circle cx="14.5" cy="10.5" r="1" fill="currentColor"/></I>,
  check:   (p) => <I d="M5 12.5 10 17.5 19 6.5" {...p} />,
  enter:   (p) => <I d="M20 6v5a3 3 0 0 1-3 3H5m0 0 4-4m-4 4 4 4" {...p} />,
};

Object.assign(window, { I, HexLogo, Icons });
