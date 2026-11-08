(function () {
  "use strict";
  // model-routing dashboard tab: one card per subscription, big used percent and the pace delta
  // ("98%  P: -47%": minus = over pace), most over pace first. Status colour is always paired with a word.
  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !window.__HERMES_PLUGINS__) return;
  const React = SDK.React;
  const h = React.createElement;
  const { useState, useEffect } = SDK.hooks;

  function fmtPct(v) { return v == null ? "–" : Math.round(v) + "%"; }

  function Card(props) {
    const c = props.card;
    const over = c.pace_delta != null && c.pace_delta < 0;
    const tone = !c.fresh ? "mr-stale" : !c.eligible ? "mr-blocked" : over ? "mr-over" : "mr-under";
    const word = !c.fresh ? "no data" : !c.eligible ? "not eligible" : over ? "over pace" : "under pace";
    const delta = c.pace_delta == null ? "" : (c.pace_delta > 0 ? "+" : "") + Math.round(c.pace_delta) + "%";
    return h("div", { className: "mr-card " + tone + (c.picked ? " mr-picked" : "") },
      h("div", { className: "mr-head" },
        h("span", { className: "mr-name" }, c.name + " " + (c.plan || "")),
        c.picked ? h("span", { className: "mr-pick" }, "current pick") : null),
      h("div", { className: "mr-main" },
        h("span", { className: "mr-used" }, fmtPct(c.used_percent)),
        h("span", { className: "mr-delta" }, "P: " + delta)),
      h("div", { className: "mr-status" }, word + (c.eligible || !c.reason ? "" : ": " + c.reason)),
      h("div", { className: "mr-sub" },
        "Week resets " + c.reset_label +
        (c.short_used_percent != null ? " · 5-hour " + fmtPct(c.short_used_percent) : "") +
        (c.pace_used_percent != null ? " · pace " + fmtPct(c.pace_used_percent) : "")));
  }

  function UsagePage() {
    const [data, setData] = useState(null);
    const [err, setErr] = useState(null);
    useEffect(function () {
      let alive = true;
      function load() {
        SDK.fetchJSON("/api/plugins/model-routing/state")
          .then(function (d) { if (alive) { setData(d); setErr(null); } })
          .catch(function (e) { if (alive) setErr(String(e)); });
      }
      load();
      const t = setInterval(load, 60000);
      return function () { alive = false; clearInterval(t); };
    }, []);
    if (err) return h("div", { className: "mr-wrap" }, h("p", null, "Could not load usage: " + err));
    if (!data) return h("div", { className: "mr-wrap" }, h("p", null, "Loading usage…"));
    const o = data.openrouter || {};
    const pick = data.pick;
    return h("div", { className: "mr-wrap" },
      h("h2", { className: "mr-title" }, "Subscription usage"),
      data.warning && data.warning.active
        ? h("div", { className: "mr-warn" }, "Warning: usage data unavailable for " + data.warning.subscriptions.join(", "))
        : null,
      h("div", { className: "mr-grid" }, (data.cards || []).map(function (c) { return h(Card, { key: c.id, card: c }); })),
      h("div", { className: "mr-card mr-od" },
        h("div", { className: "mr-head" }, h("span", { className: "mr-name" }, "OpenRouter (pay per use)")),
        h("div", { className: "mr-main" }, h("span", { className: "mr-used" }, "$" + (o.week || 0).toFixed(2)),
          h("span", { className: "mr-delta" }, "this week")),
        h("div", { className: "mr-sub" }, "$" + (o.today || 0).toFixed(2) + " today · $" + (o.month || 0).toFixed(2) +
          " this month · balance $" + (o.balance || 0).toFixed(2))),
      h("p", { className: "mr-foot" },
        (data.on_demand && data.on_demand.active ? "Routing would use on-demand OpenRouter. " :
          pick ? "Routing would pick " + pick.subscription + " (" + pick.model + "). " : "No routing pick. ") +
        "Advisory only for now. Read " + (data.written_at ? SDK.utils.isoTimeAgo(data.written_at) : "never") + "."));
  }

  // Compact meter: dot + used % + pace sign per subscription, plus OpenRouter spend today.
  // Rendered as a footer line under the chat (chat:bottom) and in the sidebar footer (header-right).
  function Meter(props) {
    const [data, setData] = useState(null);
    useEffect(function () {
      let alive = true;
      function load() {
        SDK.fetchJSON("/api/plugins/model-routing/state")
          .then(function (d) { if (alive) setData(d); })
          .catch(function () {});
      }
      load();
      const t = setInterval(load, 60000);
      return function () { alive = false; clearInterval(t); };
    }, []);
    if (!data || !data.cards || !data.cards.length) return null;
    const SHORT = { claude: "Claude", codex: "GPT", supergrok: "Grok" };
    const o = data.openrouter || {};
    const items = data.cards.map(function (c) {
      const over = c.pace_delta != null && c.pace_delta < 0;
      const tone = !c.fresh ? "mr-stale" : !c.eligible ? "mr-blocked" : over ? "mr-over" : "mr-under";
      const word = !c.fresh ? "no data" : !c.eligible ? "not eligible" : over ? "over pace" : "under pace";
      const p = c.pace_delta == null ? "" : " P" + (c.pace_delta > 0 ? "+" : "") + Math.round(c.pace_delta);
      return h("span", { key: c.id, className: "mr-hchip " + tone, title: c.name + ": " + word },
        h("span", { className: "mr-dot" }), (SHORT[c.id] || c.name) + " " + fmtPct(c.used_percent) + p);
    });
    items.push(h("span", { key: "or", className: "mr-hchip", title: "OpenRouter spend today" }, "OR $" + (o.today || 0).toFixed(2)));
    return h("a", { href: (window.__HERMES_BASE_PATH__ || "") + "/usage-routing",
      className: "mr-header" + (props && props.footer ? " mr-footer" : ""), "aria-label": "Subscription usage" }, items);
  }
  function FooterMeter() { return h(Meter, { footer: true }); }
  function SidebarMeter() { return h(Meter, { footer: false }); }

  window.__HERMES_PLUGINS__.register("model-routing", UsagePage);
  if (window.__HERMES_PLUGINS__.registerSlot) {
    window.__HERMES_PLUGINS__.registerSlot("model-routing", "chat:bottom", FooterMeter);
    window.__HERMES_PLUGINS__.registerSlot("model-routing", "header-right", SidebarMeter);
  }
})();
