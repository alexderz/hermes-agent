/**
 * Table handling for `::preview` HTML widgets (inline-preview-directive.tsx).
 *
 * Agent-written dashboards often carry tables that are far wider or longer than
 * a phone column: a nowrap id column pushes the table past the frame edge, and a
 * few hundred rows turn the card into a wall. Inside the sandboxed frame every
 * <table> is wrapped in its own horizontal scroller (so the page itself never
 * scrolls sideways), its first column stays pinned while a wide table scrolls,
 * and a long table shows its first rows with "Show all" and "Hide table"
 * buttons. Header rows (thead, or rows of only <th>) always stay visible.
 *
 * Opt out per table with `data-hx-skip`, or for the whole page with
 * `<meta name="hermes-tables" content="native">`.
 *
 * Plain ES5 strings, not compiled functions: the script runs inside an
 * opaque-origin iframe, so it must not depend on bundler helpers.
 */

/** Body rows shown before a long table folds behind "Show all". */
export const TABLE_PREVIEW_ROWS = 10

/** Defaults injected with the theme prelude, so a page's own rules still win. */
export const INLINE_TABLE_CSS =
  '.hx-table{max-width:100%;margin:4px 0}' +
  '.hx-table-scroll{max-width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain}' +
  '.hx-table-scroll[hidden]{display:none}' +
  // A table wider than its frame scrolls sideways. Its first column (usually the
  // row's name) stays pinned but narrow and wraps anywhere, so a long nowrap id
  // can no longer take the whole width and squeeze every other column to one
  // word per line; long-text cells get a readable minimum width.
  '.hx-table.hx-wide .hx-table-scroll>table tr>:first-child{position:sticky;left:0;z-index:1;width:9em;' +
  'min-width:7em;white-space:normal;overflow-wrap:anywhere;word-break:break-all;' +
  'background:var(--card,Canvas);box-shadow:1px 0 0 var(--border,transparent)}' +
  '.hx-table.hx-wide .hx-table-scroll>table td,.hx-table.hx-wide .hx-table-scroll>table th{min-width:4em}' +
  '.hx-table.hx-wide .hx-table-scroll>table .hx-long{min-width:18em}' +
  // Long cells show three lines in a wide table; a tap opens the rest.
  '.hx-table.hx-wide .hx-clamp{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;' +
  'overflow:hidden;cursor:pointer}' +
  '.hx-table.hx-wide .hx-clamp.hx-open{display:block}' +
  '.hx-table-bar{display:flex;flex-wrap:wrap;gap:6px;margin:2px 0 4px}' +
  '.hx-table-btn{font:inherit;font-size:12px;line-height:1.4;border:1px solid var(--border,currentColor);' +
  'background:transparent;color:var(--muted-foreground,inherit);border-radius:6px;padding:2px 8px;cursor:pointer}' +
  '.hx-table-btn[hidden]{display:none}'

/** The enhancer, run inside the frame after the page's markup. Idempotent. */
export const INLINE_TABLE_SCRIPT_SOURCE =
  '(function(){' +
  'var LIMIT=' +
  String(TABLE_PREVIEW_ROWS) +
  ';' +
  'if(document.querySelector(\'meta[name="hermes-tables"][content="native"]\'))return;' +
  'function isHead(r){if(r.parentNode&&r.parentNode.tagName==="THEAD")return true;var c=r.cells;' +
  'if(!c||!c.length)return false;for(var i=0;i<c.length;i++){if(c[i].tagName!=="TH")return false}return true}' +
  'function markWide(box,scroll){var w=scroll.scrollWidth>scroll.clientWidth+1;' +
  'if(w)box.classList.add("hx-wide");else box.classList.remove("hx-wide")}' +
  'function enhance(t){' +
  'if(t.hasAttribute("data-hx-skip")||!t.parentNode)return;' +
  'var p=t.parentNode;while(p&&p.nodeType===1){if(p.hasAttribute("data-hx-table"))return;p=p.parentNode}' +
  'var box=document.createElement("div");box.className="hx-table";box.setAttribute("data-hx-table","");' +
  'var scroll=document.createElement("div");scroll.className="hx-table-scroll";' +
  't.parentNode.insertBefore(box,t);' +
  'var rows=[];for(var i=0;i<t.rows.length;i++){if(!isHead(t.rows[i]))rows.push(t.rows[i])}' +
  'var cells=t.querySelectorAll("td");for(var k=0;k<cells.length;k++){var cell=cells[k];' +
  'if((cell.textContent||"").length<=60)continue;cell.classList.add("hx-long");' +
  'var clamp=document.createElement("div");clamp.className="hx-clamp";' +
  'while(cell.firstChild)clamp.appendChild(cell.firstChild);cell.appendChild(clamp);' +
  'clamp.addEventListener("click",function(e){if(e.target.closest&&e.target.closest("a,button"))return;' +
  'this.classList.toggle("hx-open")})}' +
  'var n=rows.length;' +
  'if(n>LIMIT){' +
  'var bar=document.createElement("div");bar.className="hx-table-bar";' +
  'var tog=document.createElement("button");tog.type="button";tog.className="hx-table-btn";tog.setAttribute("data-hx-toggle","");' +
  'var more=document.createElement("button");more.type="button";more.className="hx-table-btn";more.setAttribute("data-hx-more","");' +
  'var collapsed=false,all=false;' +
  'var paint=function(){scroll.hidden=collapsed;more.hidden=collapsed;' +
  'tog.textContent=(collapsed?"\\u25B8 Show table":"\\u25BE Hide table")+" \\u00B7 "+n+" rows";' +
  'more.textContent=all?"Show first "+LIMIT:"Show all "+n;' +
  'for(var j=LIMIT;j<n;j++)rows[j].hidden=!all};' +
  'tog.addEventListener("click",function(){collapsed=!collapsed;paint()});' +
  'more.addEventListener("click",function(){all=!all;paint()});' +
  'bar.appendChild(tog);bar.appendChild(more);box.appendChild(bar);paint()}' +
  'box.appendChild(scroll);scroll.appendChild(t);' +
  'markWide(box,scroll);' +
  'if(typeof ResizeObserver==="function"){new ResizeObserver(function(){markWide(box,scroll)}).observe(scroll)}' +
  '}' +
  'function run(){var ts=document.querySelectorAll("table");for(var i=0;i<ts.length;i++)enhance(ts[i])}' +
  'run();if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",run)' +
  '})()'

export function inlineTableScript(): string {
  return '<script>' + INLINE_TABLE_SCRIPT_SOURCE + '</script>'
}
