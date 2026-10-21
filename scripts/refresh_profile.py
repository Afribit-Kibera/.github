"""Build the profile's own chart assets from an explicitly public GitHub dataset."""

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import html
import json
from pathlib import Path
import subprocess
from urllib.parse import urlencode
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile"
CONFIG = json.loads((PROFILE / "projects.json").read_text(encoding="utf-8"))
DATA = PROFILE / "data" / "public-stats.json"
ASSETS = PROFILE / "assets"
BASE = "https://raw.githubusercontent.com/Afribit-Kibera/.github/main/profile/assets"
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
PALETTES = {
    "light": {"bg":"#F6F9F8", "ink":"#15231D", "muted":"#53655D", "line":"#D6E1DA", "accent":"#146A48", "track":"#E2EAE6"},
    "dark": {"bg":"#101C17", "ink":"#F4F8F5", "muted":"#B5C6BC", "line":"#35483D", "accent":"#7ED7A5", "track":"#2A3B31"},
}


def api(endpoint):
    result = subprocess.run(["gh", "api", endpoint], capture_output=True, text=True, encoding="utf-8", timeout=45)
    if result.returncode:
        raise RuntimeError(f"Public GitHub read failed: {endpoint}; no partial dataset was published")
    return json.loads(result.stdout) if result.stdout.strip() else None


def paged(endpoint):
    values = []
    for page in range(1, 101):
        separator = "&" if "?" in endpoint else "?"
        result = api(f"{endpoint}{separator}per_page=100&page={page}")
        if not isinstance(result, list):
            raise ValueError(f"Expected a public list: {endpoint}")
        values.extend(result)
        if len(result) < 100:
            return values
    raise RuntimeError("Pagination limit reached; refusing to publish incomplete public data")


def public_metadata(value):
    if value.get("private") or value.get("visibility") != "public":
        raise ValueError("Refusing to collect or publish metrics from a non-public repository")
    if value["owner"]["login"] != CONFIG["organisation"]:
        raise ValueError("Unexpected repository owner")
    return {key: value[key] for key in ["name", "full_name", "html_url", "fork", "default_branch", "pushed_at"]}


def normalise_week(timestamp):
    date = datetime.fromtimestamp(timestamp, timezone.utc).date()
    return (date - timedelta(days=(date.weekday() + 1) % 7)).isoformat()


def activity_from_commits(repo, weeks, as_of):
    start = datetime.fromisoformat(weeks[0]).replace(tzinfo=timezone.utc)
    query = urlencode({"sha":repo["default_branch"], "since":start.isoformat(), "until":as_of.isoformat()})
    result = paged(f"repos/{repo['full_name']}/commits?{query}")
    counts = {week:0 for week in weeks}
    seen = set()
    for commit in result:
        sha = commit["sha"]
        if sha in seen:
            continue
        seen.add(sha)
        date = datetime.fromisoformat(commit["commit"]["committer"]["date"].replace("Z", "+00:00"))
        if date.tzinfo is None:
            raise ValueError("Commit date must include a timezone")
        if len(commit["parents"]) > 1 or not start <= date <= as_of:
            continue
        week = normalise_week(date.timestamp())
        if week in counts:
            counts[week] += 1
    return counts


def collect():
    as_of = datetime.now(timezone.utc).replace(microsecond=0)
    repositories = []
    accounts = {}
    language_totals = Counter()
    for project in CONFIG["projects"]:
        if "repo" not in project:
            continue
        endpoint = f"repos/{CONFIG['organisation']}/{project['repo']}"
        record = public_metadata(api(endpoint))
        record["project"] = project["name"]
        if not record["fork"]:
            record["languages"] = api(endpoint + "/languages")
            language_totals.update(record["languages"])
            for account in paged(endpoint + "/contributors"):
                login = account["login"]
                bot = account.get("type") == "Bot" or login.lower() in CONFIG["automation_logins"]
                if bot:
                    continue
                entry = accounts.setdefault(login, {"login":login, "url":account["html_url"], "avatar":account["avatar_url"], "automation":False, "repositories":[]})
                entry["repositories"].append(record["name"])
        repositories.append(record)
        print(f"Read public metadata: {record['full_name']}", flush=True)

    originals = [repo for repo in repositories if not repo["fork"]]
    last_week = datetime.fromisoformat(normalise_week(as_of.timestamp()))
    weeks = [(last_week - timedelta(weeks=11-index)).date().isoformat() for index in range(12)]
    repository_weeks = {}
    unavailable = []
    for repo in originals:
        try:
            repository_weeks[repo["name"]] = activity_from_commits(repo, weeks, as_of)
        except (RuntimeError, ValueError, KeyError, TypeError):
            unavailable.append(repo["name"])
        print(f"Read public activity: {repo['name']}", flush=True)

    complete_activity = not unavailable
    activity = [{"week":week, "commits":sum(counts[week] for counts in repository_weeks.values())} for week in weeks] if complete_activity else []
    matrix = [{"repository":repo["name"], "project":repo["project"], "commits":[repository_weeks[repo["name"]][item["week"]] for item in activity]} for repo in originals] if complete_activity else []
    return {
        "schema_version":2,
        "generated_at":as_of.isoformat(timespec="seconds"),
        "scope":"Public project repositories only; excludes .github and private source. Forks are excluded from language, activity and contributor aggregates.",
        "showcased_projects":len(CONFIG["projects"]),
        "public_repositories":len(repositories),
        "original_repositories":len(originals),
        "repositories":repositories,
        "languages":dict(language_totals.most_common()),
        "contributors":sorted(accounts.values(), key=lambda item:(item["automation"], item["login"].lower())),
        "activity":{"complete":complete_activity, "unavailable_repositories":unavailable, "method":"Default-branch non-merge commits by committer date; UTC Sunday weeks; all authors included", "weeks":activity, "repositories":matrix},
    }


class Canvas:
    def __init__(self, width, height, theme, title, description):
        self.width, self.height = width, height
        self.p = PALETTES[theme]
        self.root = ET.Element(f"{{{NS}}}svg", {"width":str(width), "height":str(height), "viewBox":f"0 0 {width} {height}", "role":"img", "aria-labelledby":"title description"})
        ET.SubElement(self.root, "title", {"id":"title"}).text = title
        ET.SubElement(self.root, "desc", {"id":"description"}).text = description
        self.rect(0, 0, width, height, self.p["bg"], rx=6)

    def el(self, tag, **attrs):
        return ET.SubElement(self.root, tag, {key.replace("_", "-"):str(value) for key, value in attrs.items()})

    def rect(self, x, y, width, height, fill, **extra):
        return self.el("rect", x=x, y=y, width=width, height=height, fill=fill, **extra)

    def line(self, x1, y1, x2, y2):
        self.el("line", x1=x1, y1=y1, x2=x2, y2=y2, stroke=self.p["line"], stroke_width=1)

    def text(self, x, y, content, size=18, color=None, weight=400, **extra):
        element = self.el("text", x=x, y=y, fill=color or self.p["ink"], font_family="Arial, Helvetica, sans-serif", font_size=size, font_weight=weight, **extra)
        element.text = str(content)
        return element

    def write(self, filename):
        ET.indent(self.root)
        ET.ElementTree(self.root).write(ASSETS / filename, encoding="utf-8", xml_declaration=True)


def header(theme, mobile):
    width, height = (360, 330) if mobile else (900, 280)
    c = Canvas(width, height, theme, "Afribit Builders", "Community software from Kibera: field work, local trade and community tools.")
    pad = 24 if mobile else 36
    c.rect(pad, pad, 88, 88, "#FFFFFF", rx=4)
    logo = base64.b64encode((ASSETS / "afribit-logo.png").read_bytes()).decode("ascii")
    c.el("image", x=pad+3, y=pad+3, width=82, height=82, href="data:image/png;base64,"+logo)
    if mobile:
        c.text(132, 52, "AFRIBIT", 20, weight=700)
        c.text(132, 82, "BUILDERS", 20, weight=700)
        c.text(132, 108, "Kibera, Nairobi", 14, c.p["muted"])
        c.text(24, 166, "Community software.", 27, weight=700)
        c.text(24, 202, "Built from Kibera.", 27, weight=700)
        c.text(24, 240, "Tools for a Bitcoin circular economy.", 16, c.p["muted"])
        c.line(24, 263, 336, 263)
        for x, title, color in [(24,"FIELD WORK","#F7931A"),(135,"LOCAL TRADE",c.p["accent"]),(254,"LEARNING","#32A4B7")]:
            c.rect(x, 284, 5, 16, color)
            c.text(x+10, 297, title, 11, weight=700)
    else:
        c.text(148, 57, "KIBERA / NAIROBI / KENYA", 14, c.p["accent"], 700)
        c.text(148, 108, "Afribit Builders", 48, weight=700)
        c.text(36, 171, "Community software for a Bitcoin circular economy.", 26, weight=700)
        c.line(36, 202, 864, 202)
        for x, title, color in [(36,"FIELD WORK","#F7931A"),(330,"LOCAL TRADE",c.p["accent"]),(624,"COMMUNITY TOOLS","#32A4B7")]:
            c.rect(x, 229, 5, 18, color)
            c.text(x+15, 244, title, 15, weight=700)
    return c


def overview(data, theme, mobile):
    c = Canvas(360 if mobile else 900, 238 if mobile else 154, theme, "Afribit project overview", "Counts from the public catalogue. Private source and activity are not collected.")
    entries = [(data["showcased_projects"],"Projects in the catalogue"),(data["public_repositories"],"Public repositories"),(data["original_repositories"],"Non-fork public repositories")]
    for index, (number, label) in enumerate(entries):
        x, y = (24, 48 + index*68) if mobile else (32 + index*292, 68)
        if mobile:
            c.text(x, y, number, 34, weight=700)
            c.text(83, y-5, label, 15, c.p["muted"])
            if index < 2:
                c.line(24, y+22, 336, y+22)
        else:
            c.text(x, y, number, 42, weight=700)
            c.text(x, y+34, label, 16, c.p["muted"])
            if index < 2:
                c.line(x+264, 30, x+264, 116)
    return c


def community_header(theme, mobile):
    width, height = (360, 306) if mobile else (900, 264)
    c = Canvas(width, height, theme, "Afribit Africa", "Learn. Earn. Spend. A community-led Bitcoin circular economy in Kibera, Nairobi.")
    pad = 24 if mobile else 36
    c.rect(pad, pad, 88, 88, "#FFFFFF", rx=4)
    logo = base64.b64encode((ASSETS / "afribit-logo.png").read_bytes()).decode("ascii")
    c.el("image", x=pad+3, y=pad+3, width=82, height=82, href="data:image/png;base64,"+logo)
    if mobile:
        c.text(132, 53, "AFRIBIT", 24, weight=700)
        c.text(132, 83, "AFRICA", 24, weight=700)
        c.text(132, 108, "Kibera, Nairobi", 14, c.p["muted"])
        for index, (word, color) in enumerate([("Learn.",c.p["accent"]),("Earn.","#C1760A" if theme=="light" else "#F7B14F"),("Spend.","#228EA4" if theme=="light" else "#68C7D9")]):
            c.text(24+index*110, 177, word, 29, color, 700)
        c.line(24, 204, 336, 204)
        c.text(24, 244, "A community-led", 21, weight=700)
        c.text(24, 275, "Bitcoin circular economy.", 21, weight=700)
    else:
        c.text(148, 57, "KIBERA / NAIROBI / KENYA", 14, c.p["accent"], 700)
        c.text(148, 108, "Afribit Africa", 48, weight=700)
        for x, word, color in [(36,"Learn.",c.p["accent"]),(240,"Earn.","#C1760A" if theme=="light" else "#F7B14F"),(444,"Spend.","#228EA4" if theme=="light" else "#68C7D9")]:
            c.text(x, 182, word, 40, color, 700)
        c.text(36, 232, "A community-led Bitcoin circular economy.", 21, c.p["muted"])
    return c


def render_charts(data):
    result = subprocess.run(["node", str(ROOT / "scripts" / "render_charts.mjs")], input=json.dumps(data), capture_output=True, text=True, encoding="utf-8", timeout=60, cwd=ROOT)
    if result.returncode:
        raise RuntimeError("Chart rendering failed; no README was published: " + result.stderr[-1200:])
    for filename, chart in json.loads(result.stdout).items():
        root = ET.fromstring(chart["svg"])
        root.set("role", "img")
        root.set("aria-labelledby", "title description")
        title = ET.Element(f"{{{NS}}}title", {"id":"title"})
        title.text = chart["title"]
        description = ET.Element(f"{{{NS}}}desc", {"id":"description"})
        description.text = chart["description"]
        root.insert(0, title)
        root.insert(1, description)
        ET.ElementTree(root).write(ASSETS / filename, encoding="utf-8", xml_declaration=True)


def asset_url(filename):
    version = hashlib.sha256((ASSETS / filename).read_text(encoding="utf-8").encode("utf-8")).hexdigest()[:12]
    return f"{BASE}/{filename}?v={version}"


def picture(name, alt):
    return "\n".join([
        "<picture>",
        f'  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="{asset_url(name+"-mobile-dark.svg")}">',
        f'  <source media="(max-width: 640px)" srcset="{asset_url(name+"-mobile-light.svg")}">',
        f'  <source media="(prefers-color-scheme: dark)" srcset="{asset_url(name+"-desktop-dark.svg")}">',
        f'  <img src="{asset_url(name+"-desktop-light.svg")}" alt="{html.escape(alt, quote=True)}" width="100%">',
        "</picture>",
    ])


def update_region(readme, name, content):
    start, end = f"<!-- {name}:start -->", f"<!-- {name}:end -->"
    if start not in readme or end not in readme:
        raise ValueError(f"Missing generation markers: {name}")
    before, tail = readme.split(start, 1)
    _, after = tail.split(end, 1)
    return before + start + "\n" + content.strip() + "\n" + end + after


def generate_readme(data):
    path = PROFILE / "README.md"
    readme = (PROFILE / "README.template.md").read_text(encoding="utf-8")
    for name, alt in [("banner","Afribit Builders. Community software built from Kibera."),("overview",f"{data['showcased_projects']} projects, {data['public_repositories']} public repos, {data['original_repositories']} non-fork repos."),("code-mix","Language composition and leading language per public project; private source and the Blink fork are excluded."),("activity","Weekly public commit trend and repository heatmap; current week is partial, not a measure of community impact.")]:
        readme = update_region(readme, name, picture(name, alt))
    catalogue = []
    previous_group = None
    for project in CONFIG["projects"]:
        if project["group"] != previous_group:
            catalogue.extend(["", f"### {project['group']}", ""])
            previous_group = project["group"]
        links = []
        if project.get("repo"):
            links.append(f"[Source](https://github.com/{CONFIG['organisation']}/{project['repo']})")
        if project.get("url"):
            links.append(f"[{project['link_label']}]({project['url']})")
        if project.get("source") == "private":
            links.append("Source private")
        catalogue.extend([f"**{project['name']}**", f"{project['summary']}", "", " | ".join(links), ""])
    readme = update_region(readme, "catalogue", "\n".join(catalogue))
    humans = [entry for entry in data["contributors"] if not entry["automation"] and entry["login"].lower() not in CONFIG["automation_logins"]]
    people = []
    for person in humans:
        login = html.escape(person["login"], quote=True)
        people.append(f'<a href="{person["url"]}"><img src="{person["avatar"]}&amp;s=128" width="64" height="64" alt="{login}"></a>')
    if humans:
        people.extend(["", "Public code contributions: " + ", ".join(f"[@{entry['login']}]({entry['url']})" for entry in humans) + "."])
    people.extend(["", "Attribution comes from the original public repositories, not a complete team roster. Blink's upstream contributors remain credited in the wallet repository."])
    readme = update_region(readme, "contributors", "\n".join(people))
    source_text = ", ".join(f"{name} {count/sum(data['languages'].values())*100:.1f}%" for name,count in list(data["languages"].items())[:5])
    timestamp = data["generated_at"].split("T")[0]
    readme = update_region(readme, "data-note", f"Snapshot: **{timestamp} UTC**. {source_text}.\n\n[Public data](https://github.com/Afribit-Kibera/.github/blob/main/profile/data/public-stats.json) | [Calculation and refresh notes](https://github.com/Afribit-Kibera/.github/blob/main/profile/MAINTENANCE.md). Private activity and inherited wallet history are excluded.")
    path.write_text(readme, encoding="utf-8")


def render(data):
    ASSETS.mkdir(exist_ok=True)
    for theme in PALETTES:
        for mobile in [False, True]:
            suffix = f"{'mobile' if mobile else 'desktop'}-{theme}.svg"
            for name, canvas in [("banner",header(theme,mobile)),("community",community_header(theme,mobile)),("overview",overview(data,theme,mobile))]:
                canvas.write(f"{name}-{suffix}")
    render_charts(data)
    generate_readme(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args()
    data = json.loads(DATA.read_text(encoding="utf-8")) if args.render_only else collect()
    render(data)
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered 20 responsive/theme assets for {data['public_repositories']} public repositories.")


if __name__ == "__main__":
    main()
