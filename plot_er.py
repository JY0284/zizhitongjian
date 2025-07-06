#!/usr/bin/env python3

import argparse, json, re, sys, webbrowser, pathlib
from collections import Counter
import plotly.graph_objects as go
from plotly.io import write_html


# ────────────────────── utility helpers ───────────────────────────────
def year_num(s):
    if not s:
        return None
    m = re.search(r"前(\d+)年?", s)  # 前403年 → -403
    if m:
        return -int(m.group(1))
    m = re.search(r"(\d+)年?", s)
    return int(m.group(1)) if m else None


def bloc(name, lookup):
    "Return the actor’s power (bloc) or fall back to the name itself."
    return lookup.get(name, {}).get("power") or name


# ────────────────────── build the diagram data ────────────────────────
def build_sankey(data, start, end, include_loops, prefixes):
    actors = {e["name"]: e for e in data["entities"]}
    flows = Counter()

    for rel in data["relations"]:
        y = year_num(rel["time"])
        if None not in (start, end, y) and not (start <= y <= end):
            continue

        tag = rel.get("event_name") or rel["action"] or ""
        if prefixes and not tag.startswith(prefixes):
            continue

        for f in rel["from"]:
            for t in rel["to"]:
                src, dst = bloc(f, actors), bloc(t, actors)
                if not include_loops and src == dst:
                    continue
                key = (src, dst)
                if key not in flows:
                    flows[key] = {"count": 0, "tags": Counter()}
                flows[key]["count"] += 1
                flows[key]["tags"][tag] += 1

    if not flows:
        print(
            "No qualifying flows – try widening the time window "
            "or adjusting the action prefixes.",
            file=sys.stderr,
        )
        sys.exit()

    nodes = sorted({x for pair in flows for x in pair})
    idx = {n: i for i, n in enumerate(nodes)}

    # Slight left-to-right arrangement: source blocs on left half,
    # others on right.  Plotly auto-orders within those x coordinates.
    x_pos = [0.2] * len(nodes)
    if flows:
        src_blobs = {s for (s, _) in flows}
        for n in nodes:
            if n not in src_blobs:
                x_pos[idx[n]] = 0.6

    src, tgt, val, hover = [], [], [], []
    for (p_from, p_to), bundle in flows.items():
        src.append(idx[p_from])
        tgt.append(idx[p_to])
        val.append(bundle["count"])

        # format:  三家分晋 (1)；立为继承人 (2)；…
        tag_str = "；".join(f"{t} ({c})" for t, c in bundle["tags"].items())
        hover.append(
            f"{p_from} → {p_to}<br>{tag_str}<br><b>{bundle['count']} event(s)</b>"
        )

    return dict(
        node=dict(label=nodes, x=x_pos),
        link=dict(
            source=src,
            target=tgt,
            value=val,
            customdata=hover,
            hovertemplate="%{customdata}<extra></extra>",
        ),
    )


# ────────────────────── CLI wrapper ───────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Plot Warring-States authority transfers")
    ap.add_argument("json_file")
    ap.add_argument("-s", "--start", type=int, help="first year (e.g. -453)")
    ap.add_argument("-e", "--end", type=int, help="last  year (e.g. -350)")
    ap.add_argument(
        "--keep-loops",
        action="store_true",
        help="include self-loops (source == target)",
    )
    ap.add_argument(
        "--all-actions", action="store_true", help="don’t filter by verb prefix at all"
    )
    ap.add_argument(
        "-o",
        "--output",
        metavar="HTML",
        help="save to HTML file instead of opening immediately",
    )
    args = ap.parse_args()

    data = json.load(open(args.json_file, encoding="utf-8"))

    prefixes = None if args.all_actions else ("分封", "背叛", "代", "立", "刺杀")
    sankey = build_sankey(data, args.start, args.end, args.keep_loops, prefixes)

    title = "Authority transfers"
    if None not in (args.start, args.end):
        title += f" ({abs(args.start)}–{abs(args.end)} BCE)"

    fig = go.Figure(go.Sankey(**sankey))
    fig.update_layout(title=title, width=960, height=540)

    if args.output:
        write_html(fig, args.output, auto_open=True)
        print("saved", pathlib.Path(args.output).resolve())
    else:
        fig.show()


if __name__ == "__main__":
    main()
