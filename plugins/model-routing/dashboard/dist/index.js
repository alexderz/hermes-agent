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

  function agyPercent(value) {
    if (typeof value !== "number" || !isFinite(value)) return "–";
    if (value > 0 && value < 1) return "<1%";
    return Math.round(value) + "%";
  }

  function agyTitle(c) {
    var summary = c.fresh ? c.summary : null;
    if (!c.fresh || !summary || typeof summary.remaining_percent !== "number" || !isFinite(summary.remaining_percent)) {
      return c.fresh
        ? "Antigravity has no weekly group reading. Other model groups are separate."
        : "Antigravity quota unavailable. Other model groups are separate.";
    }
    if (summary.remaining_percent === 0) {
      return "Antigravity " + summary.group_name + " weekly allowance is exhausted, 0% remaining. Other model groups are separate.";
    }
    var word = summary.window === "5h" ? "5-hour" : (summary.window || "weekly");
    return "Antigravity " + summary.group_name + " " + word + " " + agyPercent(summary.remaining_percent) +
      " remaining. Other model groups are separate.";
  }

  function agyChip(c) {
    var summary = c.fresh ? c.summary : null;
    var tag = summary && summary.tag ? " " + summary.tag : "";
    return h("span", { key: c.id, className: "mr-hchip mr-stale", title: agyTitle(c) },
      "Ag" + tag + " " + agyPercent(summary && summary.remaining_percent));
  }

  function DisplayCard(props) {
    var c = props.card;
    var groups = c.fresh && c.groups ? c.groups : [];
    var lines = groups.map(function (group) {
      var bits = (group.buckets || []).map(function (bucket) {
        var word = bucket.window === "5h" ? "5-hour" : (bucket.window || "window");
        return word + " " + agyPercent(bucket.remaining_percent) + " remaining, resets " + (bucket.reset_label || "?");
      });
      return group.name + (bits.length ? ": " + bits.join("; ") : "");
    });
    return h("div", { className: "mr-card mr-stale" },
      h("div", { className: "mr-head" }, h("span", { className: "mr-name" }, "Antigravity")),
      h("div", { className: "mr-sub" }, lines.length ? lines.join(" · ") : (c.reason || "quota unavailable")));
  }

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
      h("div", { className: "mr-grid" }, (data.cards || []).map(function (c) {
        return h(c.display_only ? DisplayCard : Card, { key: c.id, card: c });
      })),
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
      if (c.display_only) return agyChip(c);
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
