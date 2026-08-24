"""Generates every image/chart about the 3W community.

Generates the following images:
- citation_progress
- citations_all_institutions_by_country
- citations_main_institutions_by_country
- forks_by_country
- stars_by_country

The image-generation methods share utility functions for fonts, text
measurement, summary boxes, map/bar charts by country, country normalization,
and GitHub request caching.

The GitHub token, used to generate the forks_by_country and stars_by_country
images, is requested only once at the start of execution through an interactive
prompt.

To create and manage a GitHub personal access token, follow the official
documentation:
https://docs.github.com/pt/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens

Paste the token only when prompted. Never add it directly to the source code
or commit it to the repository.

Before running this script, install the `images` optional dependency group
declared in pyproject.toml, from the repository root:

    uv sync --extra images

or:

    pip install -e ".[images]"
"""

import base64
import io
import json
import re
import unicodedata
import warnings
from math import ceil
from pathlib import Path
from time import sleep

import geonamescache
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import requests
import svgwrite
from PIL import Image, ImageDraw, ImageFont

matplotlib.use("Agg")
warnings.filterwarnings("ignore")

# --------------------------------------------------------------------------
# Shared paths and constants
# --------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent.resolve()
EXCEL_PATH = BASE_DIR / "citations.xlsx"
OUTPUT_DIR = BASE_DIR.parent / "images"
LOGO_PATH = OUTPUT_DIR / "3w_logo.png"
CACHE_DIR = BASE_DIR / "__pycache__"
FLAG_CACHE_DIR = CACHE_DIR / ".flag_cache"
FORKS_CACHE_PATH = CACHE_DIR / ".forks_cache.json"
STARS_CACHE_PATH = CACHE_DIR / ".stars_cache.json"

SHEET_CITATIONS = "citations1"
SHEET_AUTHORS = "citations2"

REPO_OWNER = "petrobras"
REPO_NAME = "3W"
GITHUB_API = "https://api.github.com"
FORKS_ENDPOINT = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/forks"
STARS_ENDPOINT = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/stargazers"

FLAG_API_URL = "https://flagsapi.com/{code}/flat/64.png"
FLAG_SIZE = 32

LOCATION_WITHOUT_COUNTRY = {"beda", "martins", "neto", "online"}
LOCATION_OVERRIDES = {
    "godoy cruz": "Argentina",
    "innopolis": "Russia",
    "itamogi": "Brazil",
    "parana": "Brazil",
    "sergipe": "Brazil",
}

GEONAMES = geonamescache.GeonamesCache()
GEONAMES_COUNTRIES = GEONAMES.get_countries()
COUNTRY_CODES = {
    country["name"]: country["iso"] for country in GEONAMES_COUNTRIES.values()
}


def _fold_text(text: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(char)
    )


COUNTRY_ALIASES = {
    _fold_text(country["name"]): country["name"]
    for country in GEONAMES_COUNTRIES.values()
}
COUNTRY_ALIASES.update({
    "brasil": "Brazil",
    "deutschland": "Germany",
    "espanha": "Spain",
    "espana": "Spain",
    "korea": "South Korea",
    "tuerkiye": "Turkey",
    "uae": "United Arab Emirates",
    "uk": "United Kingdom",
    "us": "United States",
    "usa": "United States",
})


def _build_city_index() -> dict[str, str]:
    city_index: dict[str, tuple[int, str]] = {}
    for city in GEONAMES.get_cities().values():
        country = GEONAMES_COUNTRIES.get(city["countrycode"])
        if not country:
            continue
        key = _fold_text(city["name"])
        candidate = (int(city.get("population", 0)), country["name"])
        if key not in city_index or candidate[0] > city_index[key][0]:
            city_index[key] = candidate
    return {key: country for key, (_, country) in city_index.items()}


CITY_TO_COUNTRY = _build_city_index()

COLORS = {
    "background": "#FFFFFF",
    "header_bg": "#404040",
    "header_text": "#FFFFFF",
    "row_bg": "#E8E8E8",
    "text": "#000000",
}
BOX_COLORS = ["#B6E084", "#F6C5A3", "#A5D6F3", "#F2B1D8"]

IMAGE_WIDTH = 1700
MARGIN = 40

LOGO_SIZE = 130
BOX_HEIGHT = 75
BOX_GAP = 25

MAP_WIDTH = 850
MAP_HEIGHT = 500
BAR_WIDTH = IMAGE_WIDTH - MAP_WIDTH - 2 * MARGIN - 30
BAR_HEIGHT = 500


# --------------------------------------------------------------------------
# Shared utilities (fonts, text, boxes, map/chart, GitHub)
# --------------------------------------------------------------------------

# Fonts and text

def _font(bold: bool = False, size: int = 14):
    candidates = []
    if Path("C:/Windows/Fonts").exists():
        if bold:
            candidates.append(Path("C:/Windows/Fonts/arialbd.ttf"))
        candidates.append(Path("C:/Windows/Fonts/arial.ttf"))
        candidates.append(Path("C:/Windows/Fonts/segoeuib.ttf"))
        candidates.append(Path("C:/Windows/Fonts/segoeui.ttf"))
    candidates.extend([
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if bold else None,
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Helvetica.ttc"),
    ])
    candidates = [p for p in candidates if p]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default()


def _measure_text(text: str, font) -> tuple[int, int]:
    img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _text_attrs(bold: bool = False, size: int = 14) -> dict[str, str]:
    weight = "bold" if bold else "normal"
    return {
        "font_family": "Arial, sans-serif",
        "font_size": f"{size}px",
        "font_weight": weight,
    }


def _truncate_text(text: str, font, max_width: int) -> str:
    width, _ = _measure_text(text, font)
    if width <= max_width:
        return text
    while len(text) > 1:
        text = text[:-1]
        candidate = text + "..."
        if _measure_text(candidate, font)[0] <= max_width:
            return candidate
    return text


def _baseline_y(y: int, height: int, text_height: int) -> int:
    return y + (height - text_height) // 2 + int(text_height * 0.75)


def _draw_cell_text(
    dwg: svgwrite.Drawing,
    x: int,
    y: int,
    width: int,
    text: str,
    font,
    bold: bool = False,
    size: int = 14,
    align: str = "left",
    padding: int = 0,
) -> None:
    if align == "middle":
        text_w, _ = _measure_text(text, font)
        text_x = x + (width - text_w) // 2
    else:
        text_x = x + padding
    dwg.add(
        dwg.text(
            text,
            insert=(text_x, y),
            fill=COLORS["text"],
            **_text_attrs(bold=bold, size=size),
            text_anchor="start",
        )
    )


def _draw_col_separators(
    dwg: svgwrite.Drawing, x: int, y: int, widths: list[int], height: int, include_bottom: bool = False
) -> None:
    for i in range(len(widths)):
        x_line = x + sum(widths[: i + 1])
        dwg.add(dwg.line(start=(x_line, y), end=(x_line, y + height), stroke=COLORS["background"], stroke_width=1))
    if include_bottom:
        total_width = sum(widths)
        dwg.add(dwg.line(start=(x, y + height), end=(x + total_width, y + height), stroke=COLORS["background"], stroke_width=1))


def _rgb_to_hex(rgb: str) -> str:
    match = re.match(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", rgb)
    if match:
        r, g, b = (int(v) for v in match.groups())
        return f"#{r:02x}{g:02x}{b:02x}"
    return rgb


def _country_colors(country_values: pd.DataFrame) -> dict[str, str]:
    palette = px.colors.qualitative.Pastel + px.colors.qualitative.Light24
    palette = [_rgb_to_hex(c) for c in palette]
    return {row["Country"]: palette[i % len(palette)] for i, row in country_values.iterrows()}


# Images and SVG components

def _load_logo(size: int = LOGO_SIZE) -> tuple[str | None, int, int]:
    if not LOGO_PATH.exists():
        return None, 0, 0
    data = LOGO_PATH.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    href = f"data:image/png;base64,{b64}"
    with Image.open(LOGO_PATH) as logo_img:
        logo_img.thumbnail((size, size), Image.Resampling.LANCZOS)
        return href, logo_img.width, logo_img.height


def _draw_centered_title(dwg: svgwrite.Drawing, title: str, title_y: int, size: int = 18) -> None:
    font = _font(bold=True, size=size)
    width, height = _measure_text(title, font)
    x = (IMAGE_WIDTH - width) // 2
    baseline = title_y + int(height * 0.75)
    dwg.add(
        dwg.text(
            title,
            insert=(x, baseline),
            fill=COLORS["text"],
            **_text_attrs(bold=True, size=size),
            text_anchor="start",
        )
    )


def _draw_summary_box(
    dwg: svgwrite.Drawing,
    x: int,
    y: int,
    width: int,
    height: int,
    label: str,
    value: int,
    color: str,
    title_size: int = 14,
    number_size: int = 26,
    label_top: int = 8,
    value_top: int = 36,
) -> None:
    dwg.add(
        dwg.rect(
            insert=(x, y),
            size=(width, height),
            rx=8,
            ry=8,
            fill=color,
            stroke="#000000",
            stroke_width=1,
        )
    )
    title_font = _font(bold=True, size=title_size)
    number_font = _font(bold=True, size=number_size)
    _, label_h = _measure_text(label, title_font)
    _, value_h = _measure_text(str(value), number_font)
    center_x = x + width // 2
    label_y = y + label_top + int(label_h * 0.75)
    value_y = y + value_top + int(value_h * 0.75)
    dwg.add(
        dwg.text(
            label,
            insert=(center_x, label_y),
            fill="#000000",
            **_text_attrs(bold=True, size=title_size),
            text_anchor="middle",
        )
    )
    dwg.add(
        dwg.text(
            str(value),
            insert=(center_x, value_y),
            fill="#000000",
            **_text_attrs(bold=True, size=number_size),
            text_anchor="middle",
        )
    )


def _render_map(country_values: pd.DataFrame, country_colors: dict[str, str]) -> bytes:
    fig = px.choropleth(
        country_values,
        locations="Country",
        locationmode="country names",
        color="Country",
        color_discrete_map=country_colors,
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="white",
    )
    fig.update_geos(
        showframe=False,
        showcoastlines=True,
        coastlinecolor="#AAAAAA",
        coastlinewidth=1,
        projection_type="natural earth",
        showocean=False,
        showland=True,
        landcolor="#FFFFFF",
        showcountries=True,
        countrycolor="#AAAAAA",
        countrywidth=1,
        showlakes=False,
        showrivers=False,
        showsubunits=False,
    )
    img_bytes = io.BytesIO()
    fig.write_image(img_bytes, format="png", width=MAP_WIDTH, height=MAP_HEIGHT, scale=2)
    return img_bytes.getvalue()


def _render_bar_chart(
    country_values: pd.DataFrame,
    country_colors: dict[str, str],
    title: str,
    xlim: tuple[float, float],
    xticks: list[float] | None = None,
    value_offset: float = 1,
    value_fontsize: int = 7,
) -> bytes:
    df = country_values.iloc[::-1].copy()
    bar_colors = [country_colors[c] for c in df["Country"]]
    fig, ax = plt.subplots(figsize=(BAR_WIDTH / 100, BAR_HEIGHT / 100), dpi=100)
    bars = ax.barh(df["Country"], df["Value"], color=bar_colors)
    ax.set_xlim(*xlim)
    if xticks is not None:
        ax.set_xticks(xticks)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel("")
    for spine in ("top", "right", "bottom", "left"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(axis="both", which="both", length=0)
    for bar, val in zip(bars, df["Value"]):
        ax.text(
            bar.get_width() + value_offset,
            bar.get_y() + bar.get_height() / 2,
            str(val),
            ha="left",
            va="center",
            fontsize=value_fontsize,
        )
    plt.xticks(fontsize=8)
    plt.yticks(fontsize=7)
    img_bytes = io.BytesIO()
    plt.savefig(img_bytes, format="png", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    return img_bytes.getvalue()


def _build_map_bar_svg(
    output_path: Path,
    title: str,
    bar_title: str,
    country_values: pd.DataFrame,
    boxes: list[tuple[str, int]],
    box_width: int,
    bar_xlim: tuple[float, float] | None = None,
    bar_xticks: list[float] | None = None,
    value_offset: float = 1,
    extra_height: int = 0,
    draw_extra=None,
) -> None:
    """Builds the layout shared by the logo + summary boxes + map + bar chart
    by country images, used by institutions, forks and stars.
    `draw_extra(dwg, y)`, if provided, draws extra content below the
    map/chart (e.g. the institutions table), taking up `extra_height` px.
    """
    country_colors = _country_colors(country_values)
    map_bytes = _render_map(country_values, country_colors)
    if bar_xlim is None:
        bar_xlim = (0, country_values["Value"].max() * 1.15)
    bar_bytes = _render_bar_chart(
        country_values, country_colors, bar_title, xlim=bar_xlim, xticks=bar_xticks, value_offset=value_offset
    )

    logo_href, logo_width, logo_height = _load_logo()
    header_total_width = logo_width + 4 * (box_width + BOX_GAP)
    logo_x = (IMAGE_WIDTH - header_total_width) // 2
    boxes_start_x = logo_x + logo_width + BOX_GAP
    logo_y = MARGIN + (BOX_HEIGHT - logo_height) // 2
    box_y = MARGIN

    title_y = box_y + BOX_HEIGHT + 25
    map_y = title_y + 40
    map_x = MARGIN
    bar_x = map_x + MAP_WIDTH + 30
    content_y = map_y + MAP_HEIGHT + 40
    image_height = (content_y + extra_height if draw_extra else map_y + MAP_HEIGHT) + MARGIN

    dwg = svgwrite.Drawing(str(output_path), size=(IMAGE_WIDTH, image_height), profile="tiny")
    dwg.viewbox(0, 0, IMAGE_WIDTH, image_height)
    dwg.add(dwg.rect(insert=(0, 0), size=(IMAGE_WIDTH, image_height), fill=COLORS["background"]))

    _draw_centered_title(dwg, title, title_y)

    if logo_href is not None:
        dwg.add(dwg.image(href=logo_href, insert=(logo_x, logo_y), size=(logo_width, logo_height)))

    for i, (label, value) in enumerate(boxes):
        _draw_summary_box(
            dwg,
            boxes_start_x + i * (box_width + BOX_GAP),
            box_y,
            box_width,
            BOX_HEIGHT,
            label,
            value,
            BOX_COLORS[i % len(BOX_COLORS)],
        )

    map_href = f"data:image/png;base64,{base64.b64encode(map_bytes).decode('ascii')}"
    bar_href = f"data:image/png;base64,{base64.b64encode(bar_bytes).decode('ascii')}"
    dwg.add(dwg.image(href=map_href, insert=(map_x, map_y), size=(MAP_WIDTH, MAP_HEIGHT)))
    dwg.add(dwg.image(href=bar_href, insert=(bar_x, map_y), size=(BAR_WIDTH, BAR_HEIGHT)))

    if draw_extra is not None:
        draw_extra(dwg, content_y)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dwg.save()
    print(f"SVG saved at: {output_path}")


# Data input

def _load_citations_data() -> tuple[pd.DataFrame, int, int, int, int]:
    df_citations = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_CITATIONS)
    df_authors = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_AUTHORS)
    total_citations = len(df_citations)
    total_countries = df_authors["Countries"].nunique()
    total_institutions = df_authors["Institutions"].nunique()
    total_authors = len(df_authors)
    return df_authors, total_citations, total_countries, total_institutions, total_authors


def _summary_boxes(
    total_citations: int, total_countries: int, total_institutions: int, total_authors: int
) -> list[tuple[str, int]]:
    return [
        ("Total Citations", total_citations),
        ("Total Countries", total_countries),
        ("Total Institutions", total_institutions),
        ("Total Authors", total_authors),
    ]


# GitHub and geolocation

def _get_token() -> str:
    return input("Enter GitHub API token: ").strip()


def _save_cache(cache_path: Path, data: dict) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _fetch_paginated(endpoint: str, token: str) -> list[dict]:
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    session = requests.Session()
    items = []
    page = 1
    while True:
        url = f"{endpoint}?per_page=100&page={page}"
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        items.extend(data)
        if len(data) < 100:
            break
        page += 1
        sleep(0.5)
    return items


def _fetch_user_locations(logins: list[str], token: str) -> dict[str, str | None]:
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    session = requests.Session()
    locations: dict[str, str | None] = {}
    for i, login in enumerate(logins):
        url = f"{GITHUB_API}/users/{login}"
        for attempt in range(3):
            try:
                response = session.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                locations[login] = response.json().get("location")
                break
            except requests.RequestException:
                if attempt == 2:
                    locations[login] = None
                sleep(2)
        if i % 50 == 0 and i > 0:
            sleep(1)
    return locations


def _load_github_data(
    cache_path: Path,
    items_key: str,
    endpoint: str,
    token: str,
    login_extractor,
) -> tuple[list[dict], dict[str, str | None]]:
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        if "locations" in cached:
            return cached[items_key], cached["locations"]
        if items_key in cached:
            items = cached[items_key]
            logins = [login_extractor(item) for item in items]
            locations = _fetch_user_locations(logins, token)
            _save_cache(cache_path, {items_key: items, "locations": locations})
            return items, locations

    items = _fetch_paginated(endpoint, token)
    logins = [login_extractor(item) for item in items]
    locations = _fetch_user_locations(logins, token)
    _save_cache(cache_path, {items_key: items, "locations": locations})
    return items, locations


def _normalize_country(location: str | None) -> str | None:
    if not location or not location.strip():
        return None
    text = _fold_text(location.strip())
    if text in ("", "n/a", "na", "none", "unknown", "uninformed", "world", "earth", "internet", "global", "space", "south"):
        return None
    for phrase in sorted(LOCATION_OVERRIDES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(phrase)}\b", text):
            return LOCATION_OVERRIDES[phrase]

    for phrase in sorted(COUNTRY_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(phrase)}\b", text):
            return COUNTRY_ALIASES[phrase]

    words = re.findall(r"[a-z0-9]+", text)
    for size in range(min(5, len(words)), 0, -1):
        for start in range(len(words) - size + 1):
            phrase = " ".join(words[start : start + size])
            if phrase in CITY_TO_COUNTRY:
                return CITY_TO_COUNTRY[phrase]
    return None


def _aggregate_by_country(items: list[dict], locations: dict[str, str | None], login_extractor) -> pd.DataFrame:
    rows = []
    for item in items:
        login = login_extractor(item)
        location = locations.get(login)
        country = _normalize_country(location)
        rows.append({"Login": login, "Country": country if country else "Uninformed", "Location": location})
    df = pd.DataFrame(rows)
    counts = df.groupby("Country").size().reset_index(name="Value")
    counts = counts.sort_values(["Value", "Country"], ascending=[False, True]).reset_index(drop=True)
    return counts


# --------------------------------------------------------------------------
# 1. citation_progress
# --------------------------------------------------------------------------

# Citation progress chart

def citation_progress() -> None:
    output_file = OUTPUT_DIR / "progress_over_the_years.svg"

    mpl_style = matplotlib.rcParams.copy()
    matplotlib.rc("text", usetex=True)
    matplotlib.rc("font", family="serif", size=11)

    df_raw = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_CITATIONS, usecols="E:F")
    df_raw = df_raw.rename(columns={"Category": "Category", "Year": "Year"})

    df_count = df_raw.groupby(["Year", "Category"]).size().unstack(fill_value=0)

    ordered_columns = [
        "Books",
        "Conference Papers",
        "Data Articles",
        "Doctoral Theses",
        "Final Graduation Projects",
        "Journal Articles",
        "Master's Degree Dissertations",
        "Other Articles",
        "Repository Articles",
        "Specialization Monographs",
    ]
    for col in ordered_columns:
        if col not in df_count.columns:
            df_count[col] = 0
    df_count = df_count[ordered_columns].sort_index()

    df_cumulative = df_count.cumsum()

    fig, ax = plt.subplots(figsize=(12, 9))
    df_cumulative.plot(kind="bar", stacked=True, ax=ax, width=0.5)

    plt.ylabel("Number of Citations")
    plt.xlabel("Year")
    plt.xticks(rotation=0)
    ax.legend(title=None)
    plt.grid(False)

    totals = df_cumulative.sum(axis=1)
    for i, total in enumerate(totals):
        ax.text(
            i,
            total + 0.5,
            str(int(total)),
            ha="center",
            va="bottom",
            fontsize=12,
            weight="bold",
            color="black",
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_file, format="svg", bbox_inches="tight")
    plt.close(fig)
    matplotlib.rcParams.update(mpl_style)
    print(f"SVG saved at: {output_file}")


# --------------------------------------------------------------------------
# 2. citations_all_institutions_by_country
# --------------------------------------------------------------------------

# Data and table for all institutions

INSTITUTIONS_BOX_WIDTH = 260
INSTITUTIONS_TABLE_COLS = 3
INSTITUTIONS_TABLE_COL_WIDTHS = [280, 200]
INSTITUTIONS_TABLE_HEADER_HEIGHT = 32
INSTITUTIONS_TABLE_ROW_HEIGHT = 20
INSTITUTIONS_TABLE_GAP = 24
INSTITUTIONS_TABLE_TOTAL_WIDTH = (
    INSTITUTIONS_TABLE_COLS * sum(INSTITUTIONS_TABLE_COL_WIDTHS)
    + (INSTITUTIONS_TABLE_COLS - 1) * INSTITUTIONS_TABLE_GAP
)
INSTITUTIONS_TABLE_START_X = (IMAGE_WIDTH - INSTITUTIONS_TABLE_TOTAL_WIDTH) // 2


def _country_citation_values(df_authors: pd.DataFrame) -> pd.DataFrame:
    df = df_authors.copy()
    df["Countries"] = df["Countries"].astype(str).str.strip()
    values = df.groupby("Countries")["Quantify"].sum().reset_index()
    values.columns = ["Country", "Value"]
    return values.sort_values(["Value", "Country"], ascending=[False, True]).reset_index(drop=True)


def _all_institutions(df_authors: pd.DataFrame) -> pd.DataFrame:
    df = df_authors.copy()
    for col in ("Institutions", "Countries"):
        df[col] = df[col].astype(str).str.strip()
    return df[["Institutions", "Countries"]].drop_duplicates().sort_values("Institutions").reset_index(drop=True)


def _draw_institutions_table_header(dwg: svgwrite.Drawing, x: int, y: int, widths: list[int]) -> None:
    dwg.add(dwg.rect(insert=(x, y), size=(sum(widths), INSTITUTIONS_TABLE_HEADER_HEIGHT), fill=COLORS["header_bg"]))
    header_font = _font(bold=True, size=12)
    for i, (w, label) in enumerate(zip(widths, ["Institutions", "Countries"])):
        text_w, text_h = _measure_text(label, header_font)
        text_x = x + sum(widths[:i]) + (w - text_w) // 2
        text_y = y + (INSTITUTIONS_TABLE_HEADER_HEIGHT - text_h) // 2 + int(text_h * 0.75)
        dwg.add(
            dwg.text(
                label,
                insert=(text_x, text_y),
                fill=COLORS["header_text"],
                **_text_attrs(bold=True, size=12),
                text_anchor="start",
            )
        )


def _draw_institutions_table_rows(dwg: svgwrite.Drawing, x: int, y: int, data: pd.DataFrame, start: int, end: int) -> None:
    body_font = _font(size=11)
    for i in range(start, end):
        row_y = y + INSTITUTIONS_TABLE_HEADER_HEIGHT + (i - start) * INSTITUTIONS_TABLE_ROW_HEIGHT
        dwg.add(
            dwg.rect(
                insert=(x, row_y),
                size=(sum(INSTITUTIONS_TABLE_COL_WIDTHS), INSTITUTIONS_TABLE_ROW_HEIGHT),
                fill=COLORS["row_bg"],
            )
        )
        _, text_h = _measure_text("A", body_font)
        text_y = row_y + 3 + int(text_h * 0.75)
        col_x = x
        for value, width in zip(data.iloc[i][["Institutions", "Countries"]], INSTITUTIONS_TABLE_COL_WIDTHS):
            text = _truncate_text(str(value), body_font, width - 12)
            _draw_cell_text(dwg, col_x, text_y, width, text, body_font, size=11, padding=6)
            col_x += width
        _draw_col_separators(dwg, x, row_y, INSTITUTIONS_TABLE_COL_WIDTHS, INSTITUTIONS_TABLE_ROW_HEIGHT)


def citations_all_institutions_by_country() -> None:
    output_path = OUTPUT_DIR / "citations_all_institutions_by_country.svg"
    df_authors, total_citations, total_countries, total_institutions, total_authors = _load_citations_data()
    country_values = _country_citation_values(df_authors)
    all_institutions = _all_institutions(df_authors)

    split_size = ceil(len(all_institutions) / INSTITUTIONS_TABLE_COLS)
    table_heights = []
    for c in range(INSTITUTIONS_TABLE_COLS):
        start = c * split_size
        end = min((c + 1) * split_size, len(all_institutions))
        rows = end - start
        table_heights.append(INSTITUTIONS_TABLE_HEADER_HEIGHT + rows * INSTITUTIONS_TABLE_ROW_HEIGHT)
    tables_total_height = max(table_heights)

    def draw_extra(dwg: svgwrite.Drawing, tables_y: int) -> None:
        for c in range(INSTITUTIONS_TABLE_COLS):
            start = c * split_size
            end = min((c + 1) * split_size, len(all_institutions))
            x = INSTITUTIONS_TABLE_START_X + c * (sum(INSTITUTIONS_TABLE_COL_WIDTHS) + INSTITUTIONS_TABLE_GAP)
            _draw_institutions_table_header(dwg, x, tables_y, INSTITUTIONS_TABLE_COL_WIDTHS)
            _draw_institutions_table_rows(dwg, x, tables_y, all_institutions, start, end)

    boxes = _summary_boxes(total_citations, total_countries, total_institutions, total_authors)
    _build_map_bar_svg(
        output_path=output_path,
        title="Countries with Representatives in the 3W Community",
        bar_title="Number of Citations by Country",
        country_values=country_values,
        boxes=boxes,
        box_width=INSTITUTIONS_BOX_WIDTH,
        bar_xlim=(0, 600),
        bar_xticks=[0, 200, 400],
        value_offset=5,
        extra_height=tables_total_height,
        draw_extra=draw_extra,
    )


# --------------------------------------------------------------------------
# 3. citations_main_institutions_by_country
# --------------------------------------------------------------------------

# Main institution ranking and flags

MAIN_LOGO_SIZE = 150
MAIN_BOX_WIDTH = 240
MAIN_BOX_HEIGHT = 90
MAIN_BOX_GAP = 15
MAIN_MARGIN_LEFT = 40
MAIN_MARGIN_TOP = 40
MAIN_MARGIN_BOTTOM = 30

MAIN_TABLE_X_LEFT = 320
MAIN_TABLE_X_RIGHT = 1000
MAIN_TABLE_Y = 40
MAIN_HEADER_HEIGHT = 38
MAIN_ROW_HEIGHT = 32
MAIN_COL_WIDTHS = [60, 170, 360, 70]
MAIN_TABLE_PADDING = 8


def _flag_href(country: str) -> str | None:
    code = COUNTRY_CODES.get(country)
    if not code:
        return None
    FLAG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = FLAG_CACHE_DIR / f"{code}.png"
    if not cache_path.exists():
        url = FLAG_API_URL.format(code=code)
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
        except requests.RequestException:
            return None
        flag = Image.open(io.BytesIO(response.content)).convert("RGBA")
        flag = flag.resize((FLAG_SIZE, FLAG_SIZE), Image.Resampling.LANCZOS)
        flag.save(cache_path)
    data = cache_path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _main_institutions(df_authors: pd.DataFrame) -> pd.DataFrame:
    df = df_authors.copy()
    for col in ("Countries", "Institutions"):
        df[col] = df[col].astype(str).str.strip()
    counts = df.groupby(["Countries", "Institutions"]).size().reset_index(name="Count")
    max_counts = counts.groupby("Countries")["Count"].max().to_dict()
    rows = []
    for country, max_count in max_counts.items():
        top = counts[(counts["Countries"] == country) & (counts["Count"] == max_count)]
        for _, r in top.iterrows():
            rows.append((country, r["Institutions"], int(max_count)))
    result = pd.DataFrame(rows, columns=("Country", "Institution", "Count"))
    return result.sort_values(["Count", "Country", "Institution"], ascending=[False, True, True]).reset_index(drop=True)


def _draw_main_header_cell(dwg: svgwrite.Drawing, x: int, y: int, width: int, height: int, text: str, sort_arrow: bool = False) -> None:
    dwg.add(dwg.rect(insert=(x, y), size=(width, height), fill=COLORS["header_bg"]))
    font = _font(bold=True, size=14)
    text_w, text_h = _measure_text(text, font)
    text_x = x + (width - text_w) // 2
    text_y = _baseline_y(y + (height - text_h) // 2, text_h, text_h)
    dwg.add(
        dwg.text(
            text,
            insert=(text_x, text_y),
            fill=COLORS["header_text"],
            **_text_attrs(bold=True, size=14),
            text_anchor="start",
        )
    )
    if sort_arrow:
        tip_x = text_x + text_w + 10
        tip_y = text_y - text_h // 2
        dwg.add(
            dwg.polygon(
                points=[(tip_x, tip_y), (tip_x + 8, tip_y - 5), (tip_x + 8, tip_y + 5)],
                fill=COLORS["header_text"],
            )
        )


def _draw_main_row(
    dwg: svgwrite.Drawing,
    x: int,
    y: int,
    widths: list[int],
    height: int,
    country: str,
    institution: str,
    count: int,
    flag_href: str | None,
    font,
) -> None:
    total_width = sum(widths)
    dwg.add(dwg.rect(insert=(x, y), size=(total_width, height), fill=COLORS["row_bg"]))
    _, text_h = _measure_text("A", font)
    text_y = _baseline_y(y + (height - 14) // 2, 14, text_h)
    if flag_href:
        flag_x = x + (widths[0] - FLAG_SIZE) // 2
        flag_y = y + (height - FLAG_SIZE) // 2
        dwg.add(dwg.image(href=flag_href, insert=(flag_x, flag_y), size=(FLAG_SIZE, FLAG_SIZE)))
    cells = [(country, widths[1], "left"), (institution, widths[2], "left"), (str(count), widths[3], "middle")]
    col_x = x + widths[0]
    for text, width, align in cells:
        text = _truncate_text(text, font, width - 2 * MAIN_TABLE_PADDING)
        _draw_cell_text(dwg, col_x, text_y, width, text, font, size=14, align=align, padding=MAIN_TABLE_PADDING)
        col_x += width
    _draw_col_separators(dwg, x, y, widths, height, include_bottom=True)


MAIN_HEADERS = ["Flags", "Countries", "Institutions", "Ranking"]


def _draw_main_table(dwg: svgwrite.Drawing, x: int, y: int, data: pd.DataFrame, flag_hrefs: dict[str, str | None]) -> None:
    font = _font(size=14)
    col_x = x
    for label, width in zip(MAIN_HEADERS, MAIN_COL_WIDTHS):
        _draw_main_header_cell(dwg, col_x, y, width, MAIN_HEADER_HEIGHT, label, sort_arrow=label == "Ranking")
        col_x += width
    for i, row in data.iterrows():
        row_y = y + MAIN_HEADER_HEIGHT + i * MAIN_ROW_HEIGHT
        _draw_main_row(
            dwg, x, row_y, MAIN_COL_WIDTHS, MAIN_ROW_HEIGHT, row["Country"], row["Institution"], row["Count"],
            flag_hrefs.get(row["Country"]), font,
        )


def citations_main_institutions_by_country() -> None:
    output_path = OUTPUT_DIR / "citations_main_institutions_by_country.svg"
    df_authors, total_citations, total_countries, total_institutions, total_authors = _load_citations_data()
    main_institutions = _main_institutions(df_authors)

    split = ceil(len(main_institutions) / 2)
    left_data = main_institutions.iloc[:split].reset_index(drop=True)
    right_data = main_institutions.iloc[split:].reset_index(drop=True)

    logo_href, logo_width, logo_height = _load_logo(size=MAIN_LOGO_SIZE)

    left_table_height = MAIN_TABLE_Y + MAIN_HEADER_HEIGHT + len(left_data) * MAIN_ROW_HEIGHT
    right_table_height = MAIN_TABLE_Y + MAIN_HEADER_HEIGHT + len(right_data) * MAIN_ROW_HEIGHT
    table_height = max(left_table_height, right_table_height)
    boxes_height = MAIN_MARGIN_TOP + logo_height + 30 + 4 * MAIN_BOX_HEIGHT + 3 * MAIN_BOX_GAP
    image_height = max(table_height, boxes_height) + MAIN_MARGIN_BOTTOM

    dwg = svgwrite.Drawing(str(output_path), size=(IMAGE_WIDTH, image_height), profile="tiny")
    dwg.viewbox(0, 0, IMAGE_WIDTH, image_height)
    dwg.add(dwg.rect(insert=(0, 0), size=(IMAGE_WIDTH, image_height), fill=COLORS["background"]))

    if logo_href is not None:
        logo_x = MAIN_MARGIN_LEFT + (MAIN_BOX_WIDTH - logo_width) // 2
        dwg.add(dwg.image(href=logo_href, insert=(logo_x, MAIN_MARGIN_TOP), size=(logo_width, logo_height)))

    boxes = _summary_boxes(total_citations, total_countries, total_institutions, total_authors)
    box_y = MAIN_MARGIN_TOP + logo_height + 30
    for i, (label, value) in enumerate(boxes):
        _draw_summary_box(
            dwg, MAIN_MARGIN_LEFT, box_y, MAIN_BOX_WIDTH, MAIN_BOX_HEIGHT, label, value, BOX_COLORS[i % len(BOX_COLORS)],
            title_size=16, number_size=30, label_top=12, value_top=44,
        )
        box_y += MAIN_BOX_HEIGHT + MAIN_BOX_GAP

    flag_hrefs = {country: _flag_href(country) for country in main_institutions["Country"].unique()}

    _draw_main_table(dwg, MAIN_TABLE_X_LEFT, MAIN_TABLE_Y, left_data, flag_hrefs)
    _draw_main_table(dwg, MAIN_TABLE_X_RIGHT, MAIN_TABLE_Y, right_data, flag_hrefs)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dwg.save()
    print(f"SVG saved at: {output_path}")


# --------------------------------------------------------------------------
# 4. forks_by_country / 5. stars_by_country
# --------------------------------------------------------------------------

# Fork and star images

GITHUB_BOX_WIDTH = 280


def _github_country_image(
    token: str,
    cache_path: Path,
    items_key: str,
    endpoint: str,
    output_name: str,
    total_label: str,
    title: str,
    bar_title: str,
    login_extractor,
) -> None:
    items, locations = _load_github_data(
        cache_path, items_key, endpoint, token, login_extractor=login_extractor
    )
    counts = _aggregate_by_country(items, locations, login_extractor=login_extractor)

    total_items = len(items)
    total_without = int(
        counts[counts["Country"] == "Uninformed"]["Value"].sum()
    )
    total_with = total_items - total_without
    total_countries = int(counts[counts["Country"] != "Uninformed"]["Country"].nunique())

    boxes = [
        (f"Total {total_label}", total_items),
        ("Total with Location", total_with),
        ("Total without Location", total_without),
        ("Total Countries", total_countries),
    ]
    _build_map_bar_svg(
        output_path=OUTPUT_DIR / output_name,
        title=title,
        bar_title=bar_title,
        country_values=counts,
        boxes=boxes,
        box_width=GITHUB_BOX_WIDTH,
    )


def forks_by_country(token: str) -> None:
    _github_country_image(
        token=token,
        cache_path=FORKS_CACHE_PATH,
        items_key="forks",
        endpoint=FORKS_ENDPOINT,
        output_name="forks_by_country.svg",
        total_label="Forks",
        title="Countries with Fork Representatives in the 3W Community",
        bar_title="Number of Forks by Country",
        login_extractor=lambda item: item["owner"]["login"],
    )


def stars_by_country(token: str) -> None:
    _github_country_image(
        token=token,
        cache_path=STARS_CACHE_PATH,
        items_key="stars",
        endpoint=STARS_ENDPOINT,
        output_name="stars_by_country.svg",
        total_label="Stars",
        title="Countries with Stars Representatives in the 3W Community",
        bar_title="Number of Stars by Country",
        login_extractor=lambda item: item["login"],
    )


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------

# Full execution

def main() -> None:
    token = _get_token()
    citation_progress()
    citations_all_institutions_by_country()
    citations_main_institutions_by_country()
    forks_by_country(token)
    stars_by_country(token)


if __name__ == "__main__":
    main()
